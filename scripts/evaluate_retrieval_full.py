"""
综合检索评测脚本：在扩展评测集 data/eval/retrieval_eval_full.json 上量化检索质量。

评测集三类样本（共 44 条）：
  - 单相关（same/cross/event/cross_trap，expected=字符串）：hit@1 / hit@3 / MRR / 防污染门决策正确率；
  - 多相关（multi，expected=数组）：Recall@K（top-K 中命中期望人物数 / 期望人物数）；
  - 库外负面（negative，expected=null）：检索"拒绝能力"——记录全局最优距离与 top-1 命中的
    人物，并与正样本的距离分布对比，评估是否会把库外人物误判为强相关。

用法：
  python scripts/evaluate_retrieval_full.py            # 全部指标
  python scripts/evaluate_retrieval_full.py --sweep    # 追加防污染门阈值扫描（仅单相关子集）

说明：只读现有向量库，不重建、不改动 data/vector_db；与原 26 条评测集
（retrieval_eval.json）相互独立。
"""
import os
import sys
import json
import argparse
from pathlib import Path

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


def _hit_rank(expected: str, rag) -> int:
    """期望人物在检索结果中的 0-based 排位；未命中返回 -1。"""
    if rag is None:
        return -1
    for i, src in enumerate(rag.sources):
        if src.get("character") == expected:
            return i
    return -1


def _correct_path(item: dict) -> str:
    """标注的正确路径：问自己→filtered，问他人→global（仅单相关样本有意义）。"""
    return "filtered" if item["expected"] == item["asker"] else "global"


def _decision_at_ratio(scores, threshold: float) -> str:
    """按候选阈值重放防污染门决策（与 _should_use_filtered 的 <= 语义一致）。"""
    if scores.get("best_global") is None:
        return "filtered"
    ratio = scores.get("ratio")
    if ratio is None:
        return "global"
    return "filtered" if ratio <= threshold else "global"


def main():
    ap = argparse.ArgumentParser(description="综合检索评测")
    ap.add_argument("--k", type=int, default=3, help="检索条数（默认 3）")
    ap.add_argument("--sweep", action="store_true", help="追加阈值扫描（单相关子集）")
    ap.add_argument("--split", choices=["train", "holdout", "all"], default="all",
                    help="评测子集：train（标定）/ holdout（泛化）/ all（默认全量）")
    args = ap.parse_args()

    items = json.loads(EVAL_PATH.read_text(encoding="utf-8"))["items"]
    if args.split != "all":
        items = [i for i in items if i.get("split") == args.split]
    settings = get_settings()
    vs = VectorStoreManager()
    k = args.k

    n_total = len(items)
    single = [i for i in items if isinstance(i["expected"], str)]
    multi = [i for i in items if isinstance(i["expected"], list)]
    negative = [i for i in items if i["expected"] is None]

    print(f"评测集: 共 {n_total} 条（单相关 {len(single)} / 多相关 {len(multi)} / 库外负面 {len(negative)}）"
          f" | split={args.split} | k={k} | 阈值={settings.filtered_score_ratio}")

    # ── 逐项检索 ──
    rows = {}
    for idx, item in enumerate(items):
        agent = _make_agent(vs, item["asker"])
        rag = agent._retrieve_knowledge(item["query"], k=k, request_id=f"full-{idx}")
        scores = rag.scores if rag else {}
        srcs = [s.get("character") for s in rag.sources] if rag else []
        rows[idx] = {"item": item, "rag": rag, "scores": scores, "srcs": srcs}

    # ══════════ 1) 单相关子集 ══════════
    print("\n========== 单相关子集（same/cross/event/cross_trap）==========")
    single_rows = []
    for idx, r in rows.items():
        if r["item"] not in single:
            continue
        rank = _hit_rank(r["item"]["expected"], r["rag"])
        used = r["scores"].get("path") if r["rag"] else "none"
        correct = used == _correct_path(r["item"])
        single_rows.append({"item": r["item"], "rank": rank, "used": used, "correct": correct,
                            "scores": r["scores"], "srcs": r["srcs"]})

    n = len(single_rows)
    hit1 = sum(1 for r in single_rows if r["rank"] == 0) / n
    hitk = sum(1 for r in single_rows if 0 <= r["rank"] < k) / n
    mrr = sum(1.0 / (r["rank"] + 1) if r["rank"] >= 0 else 0.0 for r in single_rows) / n
    dec_acc = sum(1 for r in single_rows if r["correct"]) / n

    print(f"  hit@1        : {hit1:.3f} ({sum(1 for r in single_rows if r['rank']==0)}/{n})")
    print(f"  hit@{k} / Recall@{k} : {hitk:.3f} ({sum(1 for r in single_rows if 0 <= r['rank'] < k)}/{n})")
    print(f"  MRR          : {mrr:.3f}")
    print(f"  防污染门决策正确率 : {dec_acc:.3f} ({sum(1 for r in single_rows if r['correct'])}/{n})")

    for t in ("same", "cross", "event", "cross_trap"):
        sub = [r for r in single_rows if r["item"]["type"] == t]
        if sub:
            h = sum(1 for r in sub if 0 <= r["rank"] < k) / len(sub)
            d = sum(1 for r in sub if r["correct"]) / len(sub)
            print(f"  [{t}] n={len(sub)} hit@{k}={h:.3f} 决策正确={d:.3f}")

    # 单相关中"自传陷阱"命中失败明细（期望人物没进 top-k）
    miss = [r for r in single_rows if not (0 <= r["rank"] < k)]
    if miss:
        print("\n  -- 单相关未命中明细（期望人物未进 top-%d）--" % k)
        for r in miss:
            print(f"    {r['item']['asker']}问「{r['item']['query'][:16]}」期望={r['item']['expected']} "
                  f"path={r['used']} top3={r['srcs']}")
    else:
        print("\n  -- 单相关全部命中 --")

    # 决策失误明细
    bad = [r for r in single_rows if not r["correct"]]
    if bad:
        print("  -- 防污染门决策失误明细 --")
        for r in bad:
            s = r["scores"]
            print(f"    {r['item']['asker']}问「{r['item']['query'][:16]}」期望={r['item']['expected']} "
                  f"实际={r['used']} 期望路径={_correct_path(r['item'])} ratio={s.get('ratio')}")

    # ══════════ 2) 多相关子集 ══════════
    # 多相关题走多人物联合检索（path=multi）返回 top-multi_top_k（默认 7），
    # Recall 按 multi_top_k 口径计算（阶段3 起取代默认 k=3——旧口径下枚举题
    # filtered 池只含被问者自传，Recall@3 失真）。
    k_multi = settings.multi_top_k
    print(f"\n========== 多相关子集（multi，Recall@{k_multi}）==========")
    multi_rows = []
    for idx, r in rows.items():
        if r["item"] not in multi:
            continue
        exp_set = r["item"]["expected"]
        hit = [e for e in exp_set if e in r["srcs"]]
        rec = len(hit) / len(exp_set)
        any_hit = 1 if hit else 0
        multi_rows.append({"item": r["item"], "hit": hit, "recall": rec, "any_hit": any_hit,
                           "srcs": r["srcs"], "n_exp": len(exp_set)})
        print(f"  {r['item']['asker']}问「{r['item']['query'][:16]}」 期望[{len(exp_set)}]="
              f"{','.join(exp_set)} 命中={hit} recall@{k_multi}={rec:.2f}")
    if multi_rows:
        avg_rec = sum(r["recall"] for r in multi_rows) / len(multi_rows)
        avg_any = sum(r["any_hit"] for r in multi_rows) / len(multi_rows)
        print(f"  平均 Recall@{k_multi} = {avg_rec:.3f}；至少命中 1 个期望人物占比 = {avg_any:.3f}")

    # ══════════ 2.5) RAGAS 风格上下文指标（单相关+多相关，离线可算）══════════
    # Context Recall@K：检索上下文（top-K）覆盖了多少比例的相关信息（期望人物）；
    # Context Precision@K：检索上下文里有多少比例是相关的（相关文档数 / K）。
    # 两者与 RAGAS 的 context_precision / context_recall 同构，只是"相关性"在
    # 这里用标注的期望人物（characters）判定，无需 LLM 打分。
    print("\n========== RAGAS 风格上下文指标（单相关+多相关共 %d 条）==========" % (len(single) + len(multi)))
    relevant_rows = []
    for idx, r in rows.items():
        item = r["item"]
        if item not in single and item not in multi:
            continue
        exp = item["expected"]
        exp_set = exp if isinstance(exp, list) else [exp]
        srcs = r["srcs"]
        hit = [e for e in exp_set if e in srcs]
        # Precision 分母：单相关用 top-k，多相关用 top-multi_top_k（口径与
        # 检索分支一致——multi 分支返回 multi_top_k 条）。
        denom = k_multi if isinstance(exp, list) else k
        relevant_rows.append({
            "item": item,
            "ctx_rec": len(hit) / len(exp_set),
            "ctx_prec": len(hit) / denom if denom else 0.0,
        })
    n_rel = len(relevant_rows)
    if n_rel:
        avg_ctx_rec = sum(r["ctx_rec"] for r in relevant_rows) / n_rel
        avg_ctx_prec = sum(r["ctx_prec"] for r in relevant_rows) / n_rel
        # 单相关 / 多相关分开看
        single_ctx = [r for r in relevant_rows if isinstance(r["item"]["expected"], str)]
        multi_ctx = [r for r in relevant_rows if isinstance(r["item"]["expected"], list)]
        print(f"  全体 Context Recall@{k}   = {avg_ctx_rec:.3f} ({n_rel} 条)")
        print(f"  全体 Context Precision@{k} = {avg_ctx_prec:.3f} ({n_rel} 条)")
        if single_ctx:
            sr = sum(r["ctx_rec"] for r in single_ctx) / len(single_ctx)
            sp = sum(r["ctx_prec"] for r in single_ctx) / len(single_ctx)
            print(f"    其中单相关:  Context Recall@{k}={sr:.3f}  Precision@{k}={sp:.3f} ({len(single_ctx)} 条)")
        if multi_ctx:
            mr = sum(r["ctx_rec"] for r in multi_ctx) / len(multi_ctx)
            mp = sum(r["ctx_prec"] for r in multi_ctx) / len(multi_ctx)
            print(f"    其中多相关:  Context Recall@{k_multi}={mr:.3f}  Precision@{k_multi}={mp:.3f} ({len(multi_ctx)} 条)")

    # ══════════ 3) 库外负面子集 ══════════
    print("\n========== 库外负面子集（negative，拒绝能力）==========")
    neg_rows = []
    for idx, r in rows.items():
        if r["item"] not in negative:
            continue
        bg = r["scores"].get("best_global")
        top1 = r["srcs"][0] if r["srcs"] else "(无)"
        refused = r["rag"] is None
        neg_rows.append({"item": r["item"], "best_global": bg, "top1": top1,
                         "path": r["scores"].get("path"), "refused": refused})
        bg_str = f"{bg:.3f}" if bg is not None else "  n/a"
        path_str = "none(no-RAG)" if refused else r["scores"].get("path")
        print(f"  {r['item']['asker']}问「{r['item']['query'][:16]}」 top1={top1} "
              f"best_global={bg_str} path={path_str}")

    # 拒绝能力：库外提问是否走 no-RAG 分支 / 是否把被问人物自传当史料注入
    refused = sum(1 for r in neg_rows if r["refused"])
    self_bio = sum(1 for r in neg_rows if r["top1"] == r["item"]["asker"])
    print(f"\n  库外提问拒绝率（path=none，走 no-RAG）: {refused}/{len(neg_rows)}")
    print(f"  自传注入率（top1 是被问人物自传）: {self_bio}/{len(neg_rows)}")

    # 与正样本距离分布对比（距离越小越相关）
    pos_bg = [r["scores"].get("best_global") for r in single_rows if r["scores"].get("best_global")]
    neg_bg = [r["best_global"] for r in neg_rows if r["best_global"]]
    if pos_bg and neg_bg:
        pos_min = min(pos_bg); pos_max = max(pos_bg)
        neg_min = min(neg_bg); neg_max = max(neg_bg)
        print(f"\n  正样本 best_global 距离区间 [{pos_min:.3f}, {pos_max:.3f}]（{len(pos_bg)} 条）")
        print(f"  库外样本 best_global 距离区间 [{neg_min:.3f}, {neg_max:.3f}]（{len(neg_bg)} 条）")
        # 误报：库外样本的距离 <= 正样本区间上限（即匹配强度与真实相关文档相当）
        fp = [r for r in neg_rows if r["best_global"] is not None and r["best_global"] <= pos_max]
        print(f"  强相关误报（库外样本距离 ≤ 正样本区间上限 {pos_max:.3f}）: "
              f"{len(fp)}/{len(neg_rows)}"
              + ("" if not fp else f" → {[r['item']['query'][:12] for r in fp]}"))
        # 拒绝间隔：正样本最差 vs 库外样本最好
        gap = neg_min - pos_max
        print(f"  拒绝间隔（库外样本最小距离 - 正样本最大距离）= {gap:+.3f}"
              + ("  → 完全可分，无误报" if gap > 0 else "  → 存在重叠"))

    # ══════════ 4) 阈值扫描（单相关子集） ══════════
    if args.sweep:
        print("\n========== 防污染门阈值扫描（单相关子集） ==========")
        best_t, best_acc = settings.filtered_score_ratio, dec_acc
        t = 1.0
        while t <= 2.0 + 1e-9:
            acc = sum(1 for r in single_rows
                      if _decision_at_ratio(r["scores"], t) == _correct_path(r["item"])) / n if n else 0.0
            marker = "  <-- 当前默认值" if abs(t - settings.filtered_score_ratio) < 1e-9 else ""
            if acc > best_acc:
                best_acc, best_t = acc, t
            print(f"    {t:.2f} : {acc:.3f}{marker}")
            t = round(t + 0.05, 2)
        print(f"  → 最优阈值 {best_t:.2f}（正确率 {best_acc:.3f}），"
              f"当前默认 {settings.filtered_score_ratio:.2f}（正确率 {dec_acc:.3f}）")


if __name__ == "__main__":
    main()
