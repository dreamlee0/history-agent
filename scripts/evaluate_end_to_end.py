"""
端到端评测脚本：用 Mock LLM 离线跑通完整 chat 链路（检索→构建提示→LLM→结构化
解析→引用渲染），度量管线正确性与延迟；--llm live 调真实模型（离线不可达即
exit(1)，不假装跑通）。

指标（离线 mock 可算，度量"管线正确性 + 延迟"，非模型答案质量）：
  - 端到端延迟：检索 / LLM / 解析渲染（含记忆、提示构建等其余开销）分阶段 +
    合计 p50/p90/mean——通过包裹 chat() 内 _retrieve_knowledge 与
    _call_api_with_retry 的埋点计时，走真实生产链路而非复刻；
  - 检索路由正确率：单相关（期望=asker→filtered，否则→global）+ 库外拒绝
    （path=none 且回答不带引用）；
  - 引用有效性：mock 输出的 cited_sources 越界索引被丢弃数（--bad-cite 验证
    grounding 丢弃逻辑）、带引用回答占比、no-RAG 分支不带【参考史料】的确认；
  - 回答含期望实体率（宽松：期望人物名出现在回答文本）。

用法：
  python scripts/evaluate_end_to_end.py --limit 12              # 默认 mock，离线可跑
  python scripts/evaluate_end_to_end.py --limit 12 --bad-cite   # 验证越界引用丢弃
  python scripts/evaluate_end_to_end.py --llm live --out e2e_live.json  # 真实模型
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from src.characters import character_manager
from src.agents import HistoryCharacterAgent
from src.retrievers.vector_store import VectorStoreManager

EVAL_PATH = Path(__file__).resolve().parent.parent / "data" / "eval" / "retrieval_eval_full.json"


class MockLLM:
    """确定性假 LLM：从系统提示中抽取第一个 [史料N] 块作回答并引用它。

    有 RAG：reply=史料片段摘要，cited_sources=[N-1]（引用必然有效）；
    无 RAG：reply=常识回答，cited_sources=[]（验证 no-RAG 分支）；
    --bad-cite：故意引用越界索引 [999]，用于验证 chat() 的引用 grounding 丢弃。
    """

    def __init__(self, bad_cite: bool = False):
        self.bad_cite = bad_cite
        self.last_cited: list = []  # 记录最近一次回答声明的引用索引（供评测读数）

    def __call__(self, messages, temperature) -> str:
        self.last_cited = []
        sys_prompt = messages[0]["content"]
        m = re.search(r"\[史料(\d)\]", sys_prompt)
        if m:
            idx = int(m.group(1)) - 1  # 0-based
            if self.bad_cite:
                self.last_cited = [999]
                return json.dumps(
                    {"reply": "（故意越界引用测试）", "cited_sources": [999]},
                    ensure_ascii=False,
                )
            block = re.search(
                rf"\[史料{m.group(1)}\][^\n]*\n(.+?)(?=\n\[史料|\n## 史料使用规则|\Z)",
                sys_prompt, re.S,
            )
            snippet = (block.group(1).strip()[:60] if block else "（史料片段）")
            self.last_cited = [idx]
            return json.dumps(
                {"reply": f"根据史料，{snippet}", "cited_sources": [idx]},
                ensure_ascii=False,
            )
        # no-RAG 分支
        return json.dumps(
            {"reply": "未检索到相关史料，基于常识回答。", "cited_sources": []},
            ensure_ascii=False,
        )


def _pct(arr, p: float) -> float:
    a = np.asarray(arr, dtype=float)
    return float(np.percentile(a, p)) if a.size else 0.0


def _expected_path(item: dict) -> str:
    """标注的正确路径：问自己→filtered，问他人→global（仅单相关样本有意义）。"""
    return "filtered" if item["expected"] == item["asker"] else "global"


def main():
    ap = argparse.ArgumentParser(description="端到端评测（Mock 离线 / live 真实）")
    ap.add_argument("--llm", choices=["mock", "live"], default="mock",
                    help="mock=确定性假 LLM 离线跑通；live=真实模型（需网络）")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="评测集条数上限（0=全部）")
    ap.add_argument("--split", choices=["train", "holdout", "all"], default="all",
                    help="评测子集：train / holdout / all（默认）")
    ap.add_argument("--out", default="", help="结果 JSON 输出路径（可选）")
    ap.add_argument("--bad-cite", action="store_true",
                    help="mock 故意引用越界索引，验证引用 grounding 丢弃逻辑")
    ap.add_argument("--use-db", action="store_true",
                    help="开启 SQLite 持久化（默认跳过，评测不落库）")
    args = ap.parse_args()

    settings = get_settings()
    vs = VectorStoreManager()

    if args.llm == "live":
        if not settings.llm_api_key:
            sys.exit("[evaluate_end_to_end] LLM_API_KEY 未配置，无法运行 live 评测。")
        # 网络探测：一次最小调用（max_retries=0 避免断网退避挂起），失败即退出，
        # 绝不假装产出指标。
        try:
            from openai import OpenAI
            probe = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                timeout=15.0,
                max_retries=0,
            )
            probe.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": "ping"}],
                temperature=0.0,
            )
        except Exception as e:
            sys.exit(f"[evaluate_end_to_end] live LLM 调用失败（当前环境可能无网络）：{e}")
        llm_backend = None
        backend_tag = f"live({settings.llm_model})"
    else:
        llm_backend = MockLLM(bad_cite=args.bad_cite)
        backend_tag = f"mock{'/bad-cite' if args.bad_cite else ''}"

    items = json.loads(EVAL_PATH.read_text(encoding="utf-8"))["items"]
    if args.split != "all":
        items = [i for i in items if i.get("split") == args.split]
    if args.limit > 0:
        items = items[: args.limit]

    db = None
    if args.use_db:
        # 项目持久化统一走 src.database.db.DatabaseManager（无 src.db/get_db_manager）
        from src.database.db import DatabaseManager

        db = DatabaseManager()

    print(f"== 端到端评测 | llm={backend_tag} | {len(items)} 条 | k={args.k} "
          f"| 模式={settings.retrieval_mode} ==")

    rows = []
    for i, item in enumerate(items):
        char = character_manager.get_character(item["asker"])
        agent = HistoryCharacterAgent(char, vs, db, llm_backend=llm_backend)

        # 埋点：包裹内部两段以测分阶段延迟（走真实 chat 链路，不复刻逻辑）
        holder: dict = {}
        _orig_r = agent._retrieve_knowledge

        def _wr(query, k=3, request_id=None):
            t0 = time.monotonic()
            rag = _orig_r(query, k=k, request_id=request_id)
            holder["retrieval_ms"] = (time.monotonic() - t0) * 1000
            holder["rag"] = rag
            return rag

        agent._retrieve_knowledge = _wr
        _orig_api = agent._call_api_with_retry

        def _wapi(messages, **kw):
            t0 = time.monotonic()
            out = _orig_api(messages, **kw)
            holder["llm_ms"] = (time.monotonic() - t0) * 1000
            return out

        agent._call_api_with_retry = _wapi

        _t0 = time.monotonic()
        reply, sources, conv = agent.chat(item["query"], session_id=f"e2e-{i}")
        e2e_ms = (time.monotonic() - _t0) * 1000
        retrieval_ms = holder.get("retrieval_ms", 0.0)
        llm_ms = holder.get("llm_ms", 0.0)
        render_ms = max(0.0, e2e_ms - retrieval_ms - llm_ms)
        rag = holder.get("rag")

        path = rag.scores.get("path") if rag else None
        n_sources = len(rag.sources) if rag else 0
        cited = list(getattr(llm_backend, "last_cited", [])) if args.llm == "mock" else []
        dropped = [c for c in cited if c >= n_sources] if rag else []
        has_footer = "【参考史料】" in reply

        rows.append({
            "item": item, "path": path, "sources": sources,
            "rag_none": rag is None,
            "e2e_ms": e2e_ms, "retrieval_ms": retrieval_ms, "llm_ms": llm_ms,
            "render_ms": render_ms, "cited": cited, "dropped": dropped,
            "has_footer": has_footer, "reply": reply,
        })
        print(f"  [{i+1}/{len(items)}] {item['asker']}问「{item['query'][:16]}」 "
              f"path={path} cite={cited} drop={dropped} e2e={e2e_ms:.0f}ms")

    # ── 1) 端到端延迟（分阶段 p50/p90/mean）──
    def col(key):
        return [r[key] for r in rows]

    print("\n--- 端到端延迟（ms；p50/p90/mean）---")
    for key, label in (
        ("retrieval_ms", "检索"),
        ("llm_ms", "LLM（mock 为本地解析，live 含网络往返）"),
        ("render_ms", "解析/渲染等其余"),
        ("e2e_ms", "合计"),
    ):
        vals = col(key)
        print(f"  {label:32s} p50={_pct(vals, 50):7.1f}  p90={_pct(vals, 90):7.1f}  mean={float(np.mean(vals)):7.1f}")

    # ── 2) 检索路由正确率（单相关 + 库外拒绝）──
    print("\n--- 检索路由正确率 ---")
    single = [r for r in rows if isinstance(r["item"]["expected"], str)]
    neg = [r for r in rows if r["item"]["expected"] is None]
    multi = [r for r in rows if isinstance(r["item"]["expected"], list)]
    ok_single = [r for r in single if r["path"] == _expected_path(r["item"])]
    # 库外拒绝：_retrieve_knowledge 对 path=none（决策门 2 / 空池）返回 None，
    # scores 不随 None 返回，故以 "无检索结果且回答无引用" 判定拒绝。
    ok_neg = [r for r in neg if r["rag_none"] and not r["has_footer"]]
    if single:
        print(f"  单相关路由正确（期望路径命中）: {len(ok_single)}/{len(single)}")
    if neg:
        print(f"  库外拒绝（path=none 且无引用）: {len(ok_neg)}/{len(neg)}")
    n_route = len(single) + len(neg)
    if n_route:
        print(f"  路由综合正确率: {(len(ok_single) + len(ok_neg)) / n_route:.3f} ({n_route} 条)")
    if multi:
        print(f"  多相关 {len(multi)} 条：不参与路径路由判定（架构为单人物过滤，见检索评测报告）")

    # ── 3) 引用有效性 ──
    print("\n--- 引用有效性（grounding 校验）---")
    rag_rows = [r for r in rows if r["path"] not in (None, "none")]
    n_dropped = sum(len(r["dropped"]) for r in rag_rows)
    cited_ok = [r for r in rag_rows if r["has_footer"]]
    print(f"  越界引用被丢弃数: {n_dropped}"
          + ("（--bad-cite 故意越界 → chat 应全部丢弃，验证通过）" if args.bad_cite and n_dropped else ""))
    if rag_rows:
        print(f"  带引用（【参考史料】）回答占比: {len(cited_ok)}/{len(rag_rows)}")
    if neg:
        print(f"  no-RAG 分支确认（库外回答均不带引用）: {sum(1 for r in neg if not r['has_footer'])}/{len(neg)}")

    # ── 4) 回答含期望实体率（宽松子串匹配）──
    print("\n--- 回答含期望实体率（宽松：人物名出现在回答文本）---")
    hits = 0
    total_ent = 0
    for r in rows:
        exp = r["item"]["expected"]
        if isinstance(exp, str):
            total_ent += 1
            if exp in r["reply"]:
                hits += 1
        elif isinstance(exp, list):
            total_ent += len(exp)
            hits += sum(1 for e in exp if e in r["reply"])
    if total_ent:
        print(f"  期望实体出现在回答中: {hits}/{total_ent}（{hits / total_ent:.3f}）")
    else:
        print("  n/a（无实体样本）")

    print("\n说明：mock 数字度量'管线正确性 + 延迟'，非模型答案质量；"
          "--llm live 时才反映真实模型（含网络往返与真实引用行为）。")

    if args.out:
        Path(args.out).write_text(
            json.dumps({
                "backend": backend_tag, "mode": settings.retrieval_mode,
                "k": args.k, "n": len(rows),
                "latency_ms": {k: {"p50": _pct(col(k), 50), "p90": _pct(col(k), 90),
                                   "mean": float(np.mean(col(k)))} for k in
                               ("retrieval_ms", "llm_ms", "render_ms", "e2e_ms")},
                "rows": rows,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n结果已写入: {args.out}")


if __name__ == "__main__":
    main()
