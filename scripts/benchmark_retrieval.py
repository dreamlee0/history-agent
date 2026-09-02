"""
检索延迟 / 成本剖析脚本：对评测集查询跑 _retrieve_knowledge，统计各阶段耗时与成本。

延迟：history_agent._retrieve_knowledge 在 scores["timings"] 注入
  search_filtered / search_global / bm25 / rerank / total（毫秒），本脚本聚合成
  p50 / p90 / mean；另测一次性成本：BM25 索引构建、全库 embedding。

成本报告（诚实标注，均为估算非实调）：
  - Embedding：本地 bge-small-zh-v1.5 = ¥0（无外部调用费）；记录每次查询
    embedding 调用次数，说明省下的外部费用。
  - LLM 生成：离线无法真实调用 → 按提示词（系统提示+检索上下文+用户问题）估算
    input tokens、输出按平均回复长度估算 output tokens，乘价格表（默认
    deepseek-v4-flash：输入 ¥1/1M、输出 ¥2/1M，LLM_PRICE_IN/OUT env 可覆盖）。
  - 网络往返延迟：离线不可测，不虚报，仅说明以 --live 端到端评测为准。

注：hybrid 模式下 search_* 阶段含内部 dense+bm25 两步（hybrid 调用内无法再
细分）；bm25 阶段 = 索引构建（一次性，已单独计时）+ 缓存检查（≈0）。

用法：
  python scripts/benchmark_retrieval.py                        # 默认 similarity
  RETRIEVAL_MODE=hybrid python scripts/benchmark_retrieval.py  # hybrid 模式
  python scripts/benchmark_retrieval.py --limit 20 --out bench.json
"""
import argparse
import json
import os
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


def _make_agent(vs, name: str) -> HistoryCharacterAgent:
    char = character_manager.get_character(name)
    agent = HistoryCharacterAgent.__new__(HistoryCharacterAgent)
    agent.settings = get_settings()
    agent.character = char
    agent.vector_store = vs
    return agent


def _pct(arr, p: float) -> float:
    a = np.asarray(arr, dtype=float)
    return float(np.percentile(a, p)) if a.size else 0.0


def _estimate_tokens(text: str) -> int:
    """中文 token 粗略估算：1 字 ≈ 0.625 token（chars/1.6）。"""
    return max(1, int(len(text) / 1.6))


def main():
    ap = argparse.ArgumentParser(description="检索延迟/成本剖析")
    ap.add_argument("--k", type=int, default=3, help="检索条数（默认 3）")
    ap.add_argument("--limit", type=int, default=0, help="评测集条数上限（0=全部）")
    ap.add_argument("--split", choices=["train", "holdout", "all"], default="all",
                    help="评测子集：train / holdout / all（默认）")
    ap.add_argument(
        "--avg-reply-len", type=int, default=200,
        help="LLM 输出 token 估算用的平均回复长度（字，默认 200）",
    )
    ap.add_argument("--out", default="", help="JSON 结果落盘路径（可选）")
    args = ap.parse_args()

    settings = get_settings()
    vs = VectorStoreManager()
    mode = settings.retrieval_mode
    items = json.loads(EVAL_PATH.read_text(encoding="utf-8"))["items"]
    if args.split != "all":
        items = [i for i in items if i.get("split") == args.split]
    if args.limit > 0:
        items = items[: args.limit]

    print(f"== 检索延迟/成本剖析 | 模式={mode} | {len(items)} 条查询 | k={args.k} ==")

    # ── 一次性成本 1：BM25 索引构建（hybrid 模式）──
    bm25_build_ms = None
    if mode == "hybrid":
        t0 = time.monotonic()
        vs._bm25_index()
        bm25_build_ms = (time.monotonic() - t0) * 1000
        print(f"一次性：BM25 索引构建 = {bm25_build_ms:.1f} ms（此后缓存，每查询≈0）")

    # ── 一次性成本 2：全库 embedding（CPU 本地，全库 chunk 量级）──
    chunks = vs.get_all_chunks()
    t0 = time.monotonic()
    vs.embeddings.embed_documents([c.page_content for c in chunks])
    embed_all_ms = (time.monotonic() - t0) * 1000
    embed_tokens = _estimate_tokens("\n".join(c.page_content for c in chunks))
    print(
        f"一次性：全库 {len(chunks)} 篇 embedding（CPU 本地） = {embed_all_ms:.1f} ms，"
        f"约 {embed_tokens} tokens（本地=¥0）"
    )

    # ── 逐项检索，收集分阶段耗时 ──
    rows = []
    for idx, item in enumerate(items):
        agent = _make_agent(vs, item["asker"])
        rag = agent._retrieve_knowledge(
            item["query"], k=args.k, request_id=f"bench-{idx}"
        )
        t = rag.scores.get("timings") if rag else {}
        rows.append({
            "idx": idx,
            "item": item,
            "agent": agent,
            "rag": rag,
            "timings": t or {},
            "path": rag.scores.get("path") if rag else None,
        })

    def col(key):
        return [r["timings"].get(key, 0.0) for r in rows if r["timings"]]

    stages = ["search_filtered", "search_global", "rerank", "total"]
    if mode == "hybrid":
        stages.insert(2, "bm25")

    print("\n--- 各阶段延迟（ms；p50/p90/mean）---")
    for s in stages:
        vals = col(s)
        if not vals:
            continue
        print(
            f"  {s:16s} p50={_pct(vals, 50):7.1f}  "
            f"p90={_pct(vals, 90):7.1f}  mean={float(np.mean(vals)):7.1f}"
        )
    if mode == "hybrid":
        print("  （注：hybrid 的 search_* 阶段含内部 dense+bm25；bm25 阶段=索引构建一次性+缓存≈0）")

    # ── LLM 成本估算（离线，非实调）──
    price_in, price_out = settings.llm_price_in, settings.llm_price_out
    total_in = total_out = 0
    per = []
    for r in rows:
        sys_prompt = r["agent"]._build_system_prompt(r["rag"])
        in_tok = _estimate_tokens(sys_prompt) + _estimate_tokens(r["item"]["query"])
        out_tok = max(1, int(args.avg_reply_len / 1.6))
        total_in += in_tok
        total_out += out_tok
        per.append({
            "in": in_tok, "out": out_tok,
            "cost": in_tok / 1e6 * price_in + out_tok / 1e6 * price_out,
        })

    in_vals = [p["in"] for p in per]
    total_cost = total_in / 1e6 * price_in + total_out / 1e6 * price_out
    print("\n--- LLM 成本估算（离线估算，未真实调用；价格 ¥/1M tokens）---")
    print(f"  价格: 输入 ¥{price_in}/1M  输出 ¥{price_out}/1M（{settings.llm_model}）")
    print(
        f"  每查询 input tokens: p50={_pct(in_vals, 50):.0f} "
        f"p90={_pct(in_vals, 90):.0f} mean={float(np.mean(in_vals)):.0f}"
    )
    print(
        f"  {len(per)} 条查询合计: input≈{total_in} output≈{total_out} tokens "
        f"→ 估算成本 ¥{total_cost:.4f}"
    )
    if per:
        print(f"  每查询平均估算成本 ¥{total_cost / len(per):.4f}（未实调，上线后以真实用量为准）")
    print("  embedding 调用: 每次查询 2 次（filtered+global 的 dense 通道），本地 CPU=¥0")
    print("  网络往返延迟: 离线不可测（不虚报）；上线后以 --live 端到端评测为准")

    # ── 落盘（可选）──
    if args.out:
        out = {
            "mode": mode, "k": args.k, "n": len(rows),
            "one_time_ms": {
                "bm25_build": bm25_build_ms,
                "embed_all": embed_all_ms,
                "embed_tokens": embed_tokens,
            },
            "stage_latency_ms": {
                s: {"p50": _pct(col(s), 50), "p90": _pct(col(s), 90),
                    "mean": float(np.mean(col(s))) if col(s) else 0.0}
                for s in stages
            },
            "llm_estimate": {
                "price_in": price_in, "price_out": price_out,
                "total_in_tokens": total_in, "total_out_tokens": total_out,
                "total_cost_yuan": round(total_cost, 6),
                "note": "估算（未实调）；网络恢复后以真实用量为准",
            },
            "per_query": [
                {
                    "idx": r["idx"], "query": r["item"]["query"],
                    "path": r["path"], "timings_ms": r["timings"],
                    "in_tokens": per[i]["in"], "out_tokens": per[i]["out"],
                }
                for i, r in enumerate(rows)
            ],
        }
        Path(args.out).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n结果已写入: {args.out}")


if __name__ == "__main__":
    main()
