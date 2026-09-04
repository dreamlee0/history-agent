"""
生成层在线评测（RAGAS 风格）：在检索评测集子集上量化"生成"环节质量。

完整接入生产生成链路（与 HistoryCharacterAgent.chat 同源，但不落库）：
  检索(含决策门/重排/multi 联合检索) → 构建系统提示词 → 调用 LLM →
  解析结构化 {reply, cited_sources} → 校验引用索引 → 对回答逐指标评估。

三个指标（定义与 RAGAS 同构）：
  - Faithfulness 忠实度：回答中的事实声明有多少被本次检索上下文支持
    （LLM 将回答拆成声明 → LLM 逐条判定是否被史料支持）；
  - Answer Relevancy 回答相关性：回答是否切题（LLM 从回答反向生成若干问题，
    与原问题做 embedding 余弦相似度取平均——完全切题 → 余弦≈1）；
  - Citation Accuracy 引用正确性：回答引用的 cited_sources 编号对应的史料，
    是否真的支撑了回答内容（LLM 逐条判定）。

用法（真实 LLM，需 .env 配置 DeepSeek key）：
  python scripts/evaluate_generation.py --limit 8 --cache /tmp/gen_cache.json
  python scripts/evaluate_generation.py --split train --cache ...   # 全量 train
  python scripts/evaluate_generation.py --split holdout --cache ... # 全量 holdout

LLM 口径：
  - 复用生产 _shared_openai_client（timeout=60，连接池共享）；
  - 统一传 max_tokens=1024：deepseek-v4-flash 的 reasoning_content 会吃掉
    token 预算，max_tokens 过小（<200）时 content 为空（finish_reason=length）。
  - --cache：单条结果增量落盘，重跑跳过已算条目（网络中断可续跑）。

指标口径（与 RAGAS 对齐的简化版）：
  - Faithfulness = 被支持的声明数 / 声明总数（检索上下文为空时记 0 分——没有
    史料支撑的"引用式回答"不应得忠实分；这同时度量 no-RAG 分支的常识回答）；
  - Answer Relevancy = mean(cos(emb(query), emb(llm_regen_q)))；
  - Citation Accuracy = 正确引用数 / 引用总数（对无引用的回答记 None 不参与均值，
    单独报告"引用覆盖率"）。
"""
import os
import sys
import json
import argparse
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from src.characters import character_manager
from src.agents import HistoryCharacterAgent
from src.agents.history_agent import _shared_openai_client
from src.retrievers.vector_store import VectorStoreManager, _resolve_embedding_model

EVAL_PATH = Path(__file__).resolve().parent.parent / "data" / "eval" / "retrieval_eval_full.json"

KEYS = ("faithfulness", "answer_relevancy", "citation_accuracy")

# deepseek-v4-flash 的 reasoning_content 吃 token 预算，max_tokens 过小 content
# 为空（finish_reason=length）。统一给足预算，保证正文完整返回。
MAX_TOKENS = 1024

# 全局计数：LLM JSON 解析失败次数（区分"真 0 分"与"解析失败假 0 分"）
_PARSE_FAILS = 0
_JSON_CALLS = 0


def _chat(client, agent, messages, temperature, max_tokens=None):
    """带 max_tokens 的 LLM 调用（默认复用 settings.llm_max_tokens，与生产口径一致
    规避 reasoning 模型截断；evaluate_end_to_end 已据此修复生产 _call_api_with_retry）。
    max_tokens 可覆盖：评测的拆声明/判定需要更长预算（1024 会被 reasoning 吃空，实测）。"""
    raw = client.chat.completions.create(
        model=agent.settings.llm_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens or agent.settings.llm_max_tokens,
    )
    return raw.choices[0].message.content or ""


# ───────────────────────── 生成链路（与 chat 同源，不落库）─────────────────────────

def _generate_reply(client, agent, item: dict) -> tuple:
    """跑一次完整生成：检索 → 提示词 → LLM → 结构化解析。

    返回 (reply_text, valid_cited_indices, rag_context)。
    """
    rag = agent._retrieve_knowledge(item["query"], request_id="gen-eval")
    system_prompt = agent._build_system_prompt(rag)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": item["query"]},
    ]
    temperature = agent.settings.temperature_factual if rag else agent.settings.temperature
    result = _chat(client, agent, messages, temperature)

    if rag:
        parsed = agent._parse_structured_reply(result)
        if parsed is not None:
            reply_text, cited = parsed
            valid = agent._validate_cited(cited, len(rag.sources))
            return reply_text, valid, rag
    return result, [], rag


def _llm_json(client, agent, system: str, user: str, max_tokens: int = 4096,
              retries: int = 2) -> list:
    """让 LLM 返回 JSON 数组（temperature=0 稳定输出）。

    max_tokens 默认 4096：拆声明这类"长 JSON 数组"输出在 1024 预算下会被
    DeepSeek reasoning_content 吃空（实测 raw 为空 → 解析失败 → 假 0 分）。
    retries：空响应/解析失败重试，仍失败返回 [] 并计数（区分真 0 分与测量失败）。
    """
    global _JSON_CALLS, _PARSE_FAILS
    for attempt in range(retries + 1):
        _JSON_CALLS += 1
        raw = _chat(client, agent,
                    [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    0.0, max_tokens=max_tokens)
        raw = raw.strip()
        # 容错提取 JSON 数组：兼容 ```json 围栏、前缀文本、截断后的尾部
        import re as _re
        m = _re.search(r"\[.*\]", raw, _re.S)
        if m:
            raw = m.group(0)
        if not raw:
            continue  # 空响应 → 重试
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    _PARSE_FAILS += 1
    return []


def _embed(texts):
    from langchain_huggingface import HuggingFaceEmbeddings
    emb = HuggingFaceEmbeddings(
        model_name=_resolve_embedding_model(),
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return emb.embed_documents(texts)


def _cos(a, b):
    import numpy as np
    return float(np.dot(a, b))


# ───────────────────────── 三个指标 ─────────────────────────

_FAITH_VOTE = 3  # 判定多数投票轮数（消除单次 LLM 判定噪声，见 /tmp/vote_test.py）

# 判定/重相关/引用均为极短 JSON 输出，2048 足够且省 reasoning token；
# 若某模型 2048 下空响应，调用方可预检后回退 4096（见 gen_sample.py preflight）。
_JUDGE_MAX_TOKENS = 2048


def _faithfulness(client, agent, query: str, reply: str, context_text: str,
                  vote_rounds: int = _FAITH_VOTE) -> float:
    """忠实度：声明被史料上下文支持的占比。

    vote_rounds>1 时对每条声明多次判定取多数（判定噪声实测 ~20% 声明在单次
    判定间翻转，0↔1；多数投票收敛到稳定值）。拆声明失败重试 2 次。
    """
    if not context_text or not context_text.strip():
        return 0.0  # 无史料上下文 → 无条件 0 分（no-RAG 设计口径，也省判定调用）
    claims = []
    for _ in range(3):
        claims = _llm_json(
            client, agent,
            "你是评测助手。把用户给出的回答拆成若干条互不重叠的独立事实声明，"
            "只输出 JSON 字符串数组，不要任何解释。",
            f"问题：{query}\n\n回答：{reply}",
        )
        claims = [c for c in claims if isinstance(c, str) and c.strip()][:20]
        if claims:
            break
    if not claims:
        return 0.0
    supported = 0
    for c in claims:
        votes = []
        rounds = 0
        while rounds < max(1, vote_rounds):
            rounds += 1
            v = _llm_json(
                client, agent,
                "你是忠实度评测助手。判断声明是否被史料上下文支持（或由上下文"
                "可直接推出）。特别规则：若声明是「史料未记载/正史未录/无从考"
                "证/不敢妄言」这类否定性表述，当上下文确实未出现该内容时，应视"
                "为被支持（回答如实反映史料缺失，是正确行为）；仅当上下文实际"
                "存在该内容却声称没有时，才判不支持。"
                "只输出 JSON：[{\"supported\": true|false}]",
                f"史料上下文：\n{context_text[:3000]}\n\n声明：{c}",
                max_tokens=_JUDGE_MAX_TOKENS,
            )
            if v and isinstance(v[0], dict) and v[0].get("supported") is True:
                votes.append(True)
            elif v and isinstance(v[0], dict) and v[0].get("supported") is False:
                votes.append(False)
            # 解析失败：不计票（本轮作废）
            # 惰性投票：两票一致即定论（与三票多数完全等价，省 1/3 判定调用）；
            # 前两票分歧才补第三票
            if len(votes) >= 2 and votes[-1] == votes[-2]:
                break
        if votes and sum(votes) / len(votes) > 0.5:
            supported += 1
    return supported / len(claims)


def _answer_relevancy(client, agent, query: str, reply: str) -> float:
    regen = _llm_json(
        client, agent,
        "你是评测助手。根据回答内容，反向生成 3 个该回答能回答的问题。"
        "只输出 JSON 字符串数组，不要任何解释。",
        f"回答：{reply}",
        max_tokens=_JUDGE_MAX_TOKENS,
    )
    regen = [q for q in regen if isinstance(q, str) and q.strip()][:3]
    if not regen:
        return 0.0
    try:
        vecs = _embed([query] + regen)
        return sum(_cos(vecs[0], v) for v in vecs[1:]) / len(regen)
    except Exception:
        return 0.0


def _citation_accuracy(client, agent, reply: str, cited: list, rag) -> float:
    """cited: 校验后的引用索引列表；rag.sources 与索引对应。"""
    if not cited:
        return None
    correct = 0
    for i in cited:
        s = rag.sources[i]
        v = _llm_json(
            client, agent,
            "你是引用评测助手。判断该史料是否确实支撑了回答中的相关内容"
            "（回答确实依据了该史料，而非无关罗列）。只输出 JSON："
            '[{"correct": true|false}]',
            f"史料[{s['title']}（{s['character']}）]\n{rag.documents[i].page_content[:800]}"
            f"\n\n回答：{reply[:1500]}",
            max_tokens=_JUDGE_MAX_TOKENS,
        )
        if v and isinstance(v[0], dict) and v[0].get("correct") is True:
            correct += 1
    return correct / len(cited)


# ───────────────────────── 主流程 ─────────────────────────

def main():
    ap = argparse.ArgumentParser(description="生成层在线评测（RAGAS 风格）")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="最多评测条数（0=全部）")
    ap.add_argument("--split", choices=["train", "holdout", "all"], default="all",
                    help="评测子集：train / holdout / all（默认）")
    ap.add_argument("--cache", default="", help="单条结果增量缓存 JSON 路径（可续跑）")
    ap.add_argument("--out", default="", help="结果 JSON 输出路径（可选）")
    args = ap.parse_args()

    settings = get_settings()
    if not settings.llm_api_key:
        sys.exit("[evaluate_generation] LLM_API_KEY 未配置，无法运行生成层评测。")

    # 复用生产共享客户端（timeout=60 + 连接池缓存），失败即快速退出。
    try:
        client = _shared_openai_client(settings.llm_api_key, settings.llm_base_url)
        client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.0,
            max_tokens=16,
        )
    except Exception as e:
        sys.exit(
            f"[evaluate_generation] LLM 调用失败（检查 .env LLM_API_KEY/网络）：{e}\n"
            "本脚本为在线评测：网络/Key 恢复后重试。"
        )

    # 增量缓存：已算过的条目（按 asker+query 键）直接复用，网络中断可续跑
    cache_path = Path(args.cache) if args.cache else None
    cache = {}
    if cache_path and cache_path.exists():
        cache = {r["key"]: r for r in json.loads(cache_path.read_text(encoding="utf-8"))["rows"]}
        print(f"[cache] 载入 {len(cache)} 条已算结果")

    items = json.loads(EVAL_PATH.read_text(encoding="utf-8"))["items"]
    if args.split != "all":
        items = [i for i in items if i.get("split") == args.split]
    if args.limit > 0:
        items = items[: args.limit]
    vs = VectorStoreManager()

    rows = []
    todo = 0
    for i, item in enumerate(items):
        key = f"{item['asker']}|{item['query']}"
        cached = cache.get(key)
        if cached is not None:
            rows.append(cached)
            continue
        todo += 1
        agent = HistoryCharacterAgent.__new__(HistoryCharacterAgent)
        agent.settings = settings
        agent.character = character_manager.get_character(item["asker"])
        agent.vector_store = vs

        reply, cited, rag = _generate_reply(client, agent, item)
        context_text = rag.context_text if rag else ""
        print(f"[{i+1}/{len(items)}] {item['asker']}问「{item['query'][:18]}」", flush=True)

        m = {
            "faithfulness": _faithfulness(client, agent, item["query"], reply, context_text),
            "answer_relevancy": _answer_relevancy(client, agent, item["query"], reply),
            "citation_accuracy": _citation_accuracy(client, agent, reply, cited, rag),
            "_cited": len(cited),
            "_reply_len": len(reply),
        }
        row = {"key": key, "item": item, "reply": reply, "cited": cited, "metrics": m}
        rows.append(row)
        cache[key] = row
        print(f"    faithfulness={m['faithfulness']:.3f} "
              f"relevancy={m['answer_relevancy']:.3f} "
              f"citation={m['citation_accuracy']}")
        # 每算完一条即落盘，中断后从缓存续跑
        if cache_path:
            cache_path.write_text(
                json.dumps({"rows": list(cache.values())}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    # 汇总全部从 rows 推导（含缓存复用条目），避免缓存与实时指标分叉
    print("\n========== 生成层指标汇总 ==========")
    for k in KEYS:
        vals = [r["metrics"][k] for r in rows if r["metrics"].get(k) is not None]
        print(f"  {k:<22s} = {sum(vals)/len(vals):.3f}  (n={len(vals)})" if vals
              else f"  {k:<22s} = n/a")
    if rows:
        cov = sum(1 for r in rows if r["metrics"]["_cited"] > 0) / len(rows)
        print(f"  引用覆盖率（回答带引用占比） = {cov:.3f}")
    if _JSON_CALLS:
        print(f"  LLM JSON 解析失败率 = {_PARSE_FAILS}/{_JSON_CALLS} "
              f"({_PARSE_FAILS/_JSON_CALLS:.1%})"
              + ("  ← 需检查提示词/模型" if _PARSE_FAILS / _JSON_CALLS > 0.2 else ""))
    if cache_path:
        print(f"[cache] 本次新算 {todo} 条，共 {len(rows)} 条已写入 {args.cache}")

    if args.out:
        Path(args.out).write_text(
            json.dumps({
                "rows": rows,
                "summary": {k: (sum(v) / len(v) if v else None) for k, v in all_metrics.items()},
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n结果已写入 {args.out}")


if __name__ == "__main__":
    main()
