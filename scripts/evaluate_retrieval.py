"""
检索评测脚本：在标注评测集上量化检索质量（提供"尺子"）。

背景：单测只能验证内部正确性；filtered_score_ratio=1.25 之前只有边界单测、
没有数据支撑。本脚本在 data/eval/retrieval_eval.json 标注集上计算：
  1. hit@1 / hit@3 / MRR —— 期望人物是否进入检索结果及排位；
  2. 防污染门决策正确率 —— 每项记录 best_filtered/best_global/ratio 与
     实际采用的路径，判断"问自己→保留过滤、问他人→退回全局"是否正确；
  3. 阈值扫描（--sweep）—— 在 ratio ∈ [1.0, 2.0] 上重放决策，输出使
     决策正确率最高的阈值，为 filtered_score_ratio 取值提供数据依据；
  4. 可选 --llm-grounding N —— 真实调用 LLM 走完整 chat()（付费，需
     LLM_API_KEY），统计"引用了史料"的比例与"引用恰好命中期望人物"
     的比例（citation accuracy 的代码可测代理）。

用法：
  python scripts/evaluate_retrieval.py                 # 仅检索层指标
  python scripts/evaluate_retrieval.py --sweep         # 追加阈值扫描
  python scripts/evaluate_retrieval.py --llm-grounding 5   # 追加真实 LLM 引用校验（付费）
  python scripts/evaluate_retrieval.py --k 5           # 改检索条数（默认 3）

说明：本脚本只读现有向量库（为空时才重建），不会改动 data/vector_db。
"""
import os
import sys
import json
import argparse
from pathlib import Path

# 保证从项目根目录或 scripts/ 下都能运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from src.characters import character_manager
from src.agents import HistoryCharacterAgent
from src.retrievers.vector_store import VectorStoreManager, load_knowledge_files

EVAL_PATH = Path(__file__).resolve().parent.parent / "data" / "eval" / "retrieval_eval.json"


def _ensure_vector_store() -> VectorStoreManager:
    """复用现有向量库；为空时用知识文件构建（幂等，不重复入库）。"""
    vs = VectorStoreManager()
    if vs.get_document_count() == 0:
        docs = load_knowledge_files()
        if docs:
            vs.rebuild(docs)
    return vs


def _make_agent(vs, name: str) -> HistoryCharacterAgent:
    """构造一个不触发 API 的 Agent（仅用于检索与 prompt 构建，不走 __init__）。"""
    char = character_manager.get_character(name)
    agent = HistoryCharacterAgent.__new__(HistoryCharacterAgent)
    agent.settings = get_settings()
    agent.character = char
    agent.vector_store = vs
    return agent


def _hit_rank(expected: str, rag) -> int:
    """返回期望人物在检索结果中的 0-based 排位；未命中返回 -1。"""
    if rag is None:
        return -1
    for i, src in enumerate(rag.sources):
        if src.get("character") == expected:
            return i
    return -1


def _correct_path(item: dict) -> str:
    """标注的正确路径：问自己→filtered，问他人→global。"""
    return "filtered" if item["expected"] == item["asker"] else "global"


def _decision_at_ratio(score, threshold: float) -> str:
    """按候选阈值重放防污染门决策（与 _should_use_filtered 的 <= 语义一致）。"""
    if score.get("best_global") is None:
        return "filtered"          # 无全局结果时保留人物聚焦
    ratio = score.get("ratio")
    if ratio is None:
        return "global"            # 过滤检索为空 → 走全局
    return "filtered" if ratio <= threshold else "global"


def main():
    ap = argparse.ArgumentParser(description="检索评测")
    ap.add_argument("--k", type=int, default=3, help="检索条数（默认 3）")
    ap.add_argument("--sweep", action="store_true", help="追加阈值扫描")
    ap.add_argument("--llm-grounding", type=int, default=0, metavar="N",
                    help="真实调用 LLM 校验前 N 条引用（付费，需 LLM_API_KEY）")
    args = ap.parse_args()

    items = json.loads(EVAL_PATH.read_text(encoding="utf-8"))["items"]
    settings = get_settings()
    vs = _ensure_vector_store()

    print(f"评测集: {len(items)} 条标注（same/cross/event） | k={args.k} | "
          f"阈值={settings.filtered_score_ratio} 默认")
    print(f"检索模式: {settings.retrieval_mode}")

    rows = []   # 逐项结果
    for idx, item in enumerate(items):
        agent = _make_agent(vs, item["asker"])
        rag = agent._retrieve_knowledge(item["query"], k=args.k, request_id=f"eval-{idx}")
        rank = _hit_rank(item["expected"], rag)
        used = rag.scores.get("path") if rag else "none"
        correct = used == _correct_path(item)
        rows.append({
            "item": item, "rank": rank, "used": used, "correct": correct,
            "scores": rag.scores if rag else {},
        })

    # ── 指标 ──
    n = len(rows)
    hit1 = sum(1 for r in rows if r["rank"] == 0) / n
    hitk = sum(1 for r in rows if 0 <= r["rank"] < args.k) / n
    mrr = sum(1.0 / (r["rank"] + 1) if r["rank"] >= 0 else 0.0 for r in rows) / n
    dec_acc = sum(1 for r in rows if r["correct"]) / n

    print("\n========== 检索层指标 ==========")
    print(f"  hit@1        : {hit1:.3f} ({sum(1 for r in rows if r['rank']==0)}/{n})")
    print(f"  hit@{args.k}       : {hitk:.3f} ({sum(1 for r in rows if 0 <= r['rank'] < args.k)}/{n})")
    print(f"  MRR          : {mrr:.3f}")
    print(f"  防污染门决策正确率 : {dec_acc:.3f} ({sum(1 for r in rows if r['correct'])}/{n})  [默认阈值 {settings.filtered_score_ratio}]")

    # 分类型明细
    for t in ("same", "cross", "event"):
        sub = [r for r in rows if r["item"]["type"] == t]
        if sub:
            h = sum(1 for r in sub if 0 <= r["rank"] < args.k) / len(sub)
            d = sum(1 for r in sub if r["correct"]) / len(sub)
            print(f"  [{t}] n={len(sub)} hit@{args.k}={h:.3f} 决策正确={d:.3f}")

    # 决策失误明细（列出，便于定位阈值与检索问题）
    bad = [r for r in rows if not r["correct"]]
    if bad:
        print("\n  -- 防污染门决策失误明细 --")
        for r in bad:
            s = r["scores"]
            print(f"    {r['item']['asker']}问「{r['item']['query'][:18]}」期望={r['item']['expected']} "
                  f"实际路径={r['used']} ratio={s.get('ratio')} "
                  f"best_f={s.get('best_filtered'):.3f} best_g={s.get('best_global')}")

    # ── 阈值扫描 ──
    if args.sweep:
        print("\n========== filtered_score_ratio 阈值扫描 ==========")
        print("  ratio : 决策正确率")
        best_t, best_acc = settings.filtered_score_ratio, dec_acc
        step = 0.05
        t = 1.0
        while t <= 2.0 + 1e-9:
            acc = sum(
                1 for r in rows
                if _decision_at_ratio(r["scores"], t) == _correct_path(r["item"])
            ) / n if n else 0.0
            marker = ""
            if abs(t - settings.filtered_score_ratio) < 1e-9:
                marker = "  <-- 当前默认值"
            if acc > best_acc:
                best_acc, best_t = acc, t
            print(f"    {t:.2f} : {acc:.3f}{marker}")
            t = round(t + step, 2)
        print(f"  → 最优阈值 {best_t:.2f}（正确率 {best_acc:.3f}），"
              f"当前默认 {settings.filtered_score_ratio:.2f}（正确率 {dec_acc:.3f}）")

    # ── 可选：真实 LLM 引用校验（付费） ──
    if args.llm_grounding > 0:
        print("\n========== LLM 引用校验（--llm-grounding，真实调用，付费） ==========")
        if not settings.llm_api_key:
            print("  LLM_API_KEY 未配置，跳过（如需运行请在 .env / 环境变量配置）")
            return
        cited = grounded = llm_hits = 0
        for idx, item in enumerate(items[: args.llm_grounding]):
            char = character_manager.get_character(item["asker"])
            agent = RealAgent(char, vs, None)   # db=None：仅对话不回写数据库
            try:
                reply, sources, _ = agent.chat(item["query"], session_id="eval")
            except Exception as e:
                print(f"    [{idx}] {item['asker']}问「{item['query'][:16]}」LLM 调用失败: {e}")
                continue
            chars = [s.get("character") for s in sources]
            has_citation = len(chars) > 0
            cited += int(has_citation)
            grounded += int(item["expected"] in chars)
            llm_hits += int(item["expected"] in chars and has_citation)
            print(f"    [{idx}] {item['asker']}问「{item['query'][:16]}」→ 引用={chars} "
                  f"期望={item['expected']} {'✓' if item['expected'] in chars else '✗'}")
        m = min(args.llm_grounding, len(items))
        print(f"\n  引用率   = {cited}/{m} = {cited / m:.3f}（回答至少引用了一条史料）")
        print(f"  引用命中率 = {grounded}/{m} = {grounded / m:.3f}（引用了期望人物史料）")


if __name__ == "__main__":
    main()
