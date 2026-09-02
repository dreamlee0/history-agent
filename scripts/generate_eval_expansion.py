"""
评测集扩容：44 条 → ~200 条，带 train/holdout 分层切分。

金标来源（确定性、可复现，不依赖 LLM）：
  - same / cross：直接复用人物 YAML 的 knowledge_focus（每人 2-6 个史实要点），
    查询模板措辞即金标真值（"介绍你的X" → 该人物；"介绍X的Y" → 目标人物）。
  - cross_trap：人工选取"易混淆"人物对（同文坛/同武将/同朝名臣），金标为被问者。
  - event：人工池（事件 → 亲历人物，asker=亲历者，expected=asker）。
  - negative：人工库外人物池（现代/外国/未收录历史人物），expected=None。
  - multi：人工分类枚举池（期望列表 ⊂ 97 人物全表）。

切分：按 type 分层随机 80/20 → train / holdout。阈值只在 train 上标定，
holdout 出泛化指标（回应"同集调参、泛化无证据"）。

用法：
  python scripts/generate_eval_expansion.py            # 生成（确定性 seed=42）
  python scripts/generate_eval_expansion.py --dry-run  # 只打印统计，不写文件
  python scripts/generate_eval_expansion.py --seed 42
"""
import os
import re
import sys
import json
import random
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.characters.character_manager import character_manager

EVAL_FILE = Path(__file__).resolve().parent.parent / "data" / "eval" / "retrieval_eval_full.json"
KB_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"

# 库外人物池（负样本：须确不在 97 人知识库中）
OUT_OF_KB = [
    "钱学森", "袁隆平", "屠呦呦", "钟南山", "拿破仑", "华盛顿",
    "爱因斯坦", "牛顿", "莎士比亚", "达芬奇", "贝多芬", "伽利略",
    "哥伦布", "马克思", "甘地", "林肯", "达尔文", "爱迪生",
    "居里夫人", "卓别林", "莫扎特", "特斯拉", "爱迪生", "罗斯福",
    "项羽", "勾践", "西施", "王昭君", "貂蝉", "郑成功",
    "鉴真", "徐志摩", "张爱玲", "老舍", "金庸", "莫言",
]

# 事件题：asker=亲历者，expected=asker（与既有 event 题口径一致）
EVENTS = [
    ("林则徐", "你主持的虎门销烟，当时销毁了多少鸦片，采取了哪些措施"),
    ("王安石", "你发起的熙宁变法主要内容有哪些，为什么阻力很大"),
    ("范仲淹", "你主导的庆历新政涉及哪些方面，为何未能持续推行"),
    ("梁启超", "你参与推动的戊戌变法的核心主张和结局是什么"),
    ("孙中山", "你领导的辛亥革命取得了哪些成果，三民主义的内涵是什么"),
    ("鲁迅", "你参与的新文化运动批判了什么，提倡了什么"),
    ("刘邦", "你与项羽的楚汉之争经过了哪些关键战役"),
    ("玄奘", "你西行取经的路线和带回的经书情况如何"),
    ("张骞", "你两次出使西域的经过和意义是什么"),
    ("卫青", "你率军北击匈奴的几次大战经过如何"),
    ("霍去病", "你漠北之战大破匈奴的经过是怎样的"),
    ("戚继光", "你在东南沿海抗倭的主要战绩有哪些"),
    ("文天祥", "你在崖山海战前后的抗元事迹和结局如何"),
    ("岳飞", "你率岳家军北伐的主要战事与最终结局"),
    ("李时珍", "你编写《本草纲目》的经历和贡献是什么"),
]

# 跨人陷阱题：asker→target（被问者与 asker 易混淆：同文坛/同武将/同朝名臣）
CROSS_TRAP_PAIRS = [
    ("苏轼", "辛弃疾", "辛弃疾的豪放词风和苏轼相比有什么异同"),
    ("白居易", "杜甫", "杜甫诗作的现实主义风格体现在哪些方面"),
    ("王维", "李白", "李白的浪漫主义诗风有哪些突出特点"),
    ("关羽", "张飞", "张飞的性格特点和主要战绩有哪些"),
    ("张飞", "赵云", "赵云在长坂坡救阿斗的事迹经过如何"),
    ("周瑜", "诸葛亮", "诸葛亮在东吴舌战群儒的故事是怎样的"),
    ("卫青", "霍去病", "霍去病封狼居胥的战绩经过如何"),
    ("张良", "韩信", "韩信的背水一战战术是怎么回事"),
    ("欧阳修", "苏轼", "苏轼的文学成就主要有哪些方面"),
    ("王安石", "司马光", "司马光编纂《资治通鉴》的经过和体例"),
    ("李商隐", "杜牧", "杜牧咏史怀古诗的风格特点是什么"),
    ("颜真卿", "王羲之", "王羲之《兰亭集序》的书法地位与价值"),
    ("曾国藩", "左宗棠", "左宗棠收复新疆的经过和意义"),
    ("左宗棠", "李鸿章", "李鸿章在洋务运动中的主要作为有哪些"),
    ("康熙", "雍正", "雍正皇帝推行摊丁入亩的主要内容是什么"),
    ("雍正", "乾隆", "乾隆盛世的主要成就表现在哪些方面"),
    ("杜甫", "李白", "李白游历名山大川的经历与诗作"),
    ("诸葛亮", "周瑜", "周瑜在赤壁之战中的关键作用是什么"),
]

# 多相关枚举题：asker → 期望人物列表（⊂ 97 人物全表）
MULTI_ITEMS = [
    ("李白", ["李白", "杜甫", "白居易", "王维", "李商隐", "杜牧"], "唐朝有哪些著名的诗人"),
    ("苏轼", ["欧阳修", "苏轼", "王安石", "司马光", "范仲淹"], "北宋有哪些著名的文学家"),
    ("曹操", ["刘备", "关羽", "张飞", "赵云", "诸葛亮"], "三国时期蜀汉有哪些主要人物"),
    ("诸葛亮", ["曹操", "司马懿"], "三国时期曹魏有哪些重要人物"),
    ("孙权", ["孙权", "周瑜"], "三国时期东吴有哪些主要人物"),
    ("孔子", ["老子", "孔子", "墨子", "孙武"], "春秋战国时期有哪些重要的思想家"),
    ("刘邦", ["卫青", "霍去病", "韩信"], "西汉时期有哪些著名的将领"),
    ("辛弃疾", ["岳飞", "辛弃疾", "陆游"], "南宋有哪些抗击金国的重要人物"),
    ("于谦", ["于谦", "海瑞", "王阳明", "张居正"], "明朝有哪些著名的文臣"),
    ("康熙", ["康熙", "雍正", "乾隆"], "清朝有哪些重要的皇帝"),
    ("纪晓岚", ["纪晓岚", "和珅", "林则徐", "曾国藩", "左宗棠", "李鸿章", "张之洞"], "清朝有哪些著名的臣子"),
    ("孙中山", ["孙中山", "鲁迅", "蔡元培", "梁启超"], "民国时期有哪些重要的思想家和文学家"),
    ("成吉思汗", ["成吉思汗", "忽必烈", "关汉卿"], "元朝有哪些重要人物"),
    ("王羲之", ["王羲之", "陶渊明"], "东晋有哪些著名的文化名人"),
    ("隋文帝", ["隋文帝", "隋炀帝"], "隋朝有哪些重要的皇帝"),
    ("曾国藩", ["曾国藩", "左宗棠", "李鸿章", "张之洞"], "晚清洋务派有哪些代表人物"),
    ("刘备", ["曹操", "刘备", "孙权"], "东汉末年至三国有哪些重要的割据领袖"),
    ("李煜", ["李煜", "柴荣"], "五代十国时期有哪些重要的君主"),
    ("商汤", ["商汤", "周文王", "周武王", "周公", "姜子牙"], "商周时期有哪些重要的人物"),
    ("朱元璋", ["朱元璋", "朱棣"], "明朝前期有哪些重要的皇帝"),
    ("武则天", ["武则天", "慈禧"], "中国古代有哪些掌握大权的女性统治者"),
    ("李时珍", ["李时珍", "徐霞客"], "明朝有哪些著名的科学家"),
    ("郑和", ["郑和", "徐霞客"], "明朝有哪些著名的航海家和地理学家"),
    ("霍去病", ["卫青", "霍去病"], "汉武帝时期有哪些抗击匈奴的名将"),
    ("诸葛亮", ["曹操", "刘备", "孙权", "诸葛亮", "周瑜"], "赤壁之战中有哪些主要人物"),
]


def kb_has(character: str) -> bool:
    """该人物在知识库中是否有 historical 文件（金标可检索性前置校验）。"""
    return any(
        f"biography_{character}_" in p.name and "_内置" not in p.name
        for p in KB_DIR.glob(f"biography_{character}_*.txt")
    )


def gen_same(roster, existing_queries, n: int) -> list:
    """同人题：从 knowledge_focus 取模板措辞（asker=expected=本人）。"""
    items, used = [], set()
    for c in roster:
        if len(items) >= n:
            break
        focus = c.knowledge_focus or []
        for f in focus:
            if len(f) < 2 or any(ch.isdigit() for ch in f[:2]):
                continue
            q = f"介绍一下你的{f}"
            if q in used or q in existing_queries:
                continue
            used.add(q)
            items.append({"type": "same", "asker": c.name, "expected": c.name, "query": q})
            break  # 每人 1 条，保证覆盖广度
    return items


def gen_cross(roster, existing_queries, n: int) -> list:
    """跨人题：asker 与 target 不同朝代，询问 target 的 knowledge_focus。"""
    by_dynasty = {}
    for c in roster:
        by_dynasty.setdefault(c.dynasty, []).append(c)
    dynasties = list(by_dynasty)
    items, used = [], set()
    while len(items) < n:
        # 随机配对，保证 asker/target 不同朝代
        asker_d = random.choice(dynasties)
        target_d = random.choice([d for d in dynasties if d != asker_d])
        asker = random.choice(by_dynasty[asker_d])
        target = random.choice(by_dynasty[target_d])
        focus = target.knowledge_focus or []
        f = random.choice(focus) if focus else target.name
        q = f"介绍一下{target.name}的{f}"
        if q in used or q in existing_queries:
            continue
        used.add(q)
        items.append({"type": "cross", "asker": asker.name, "expected": target.name, "query": q})
    return items


def main():
    ap = argparse.ArgumentParser(description="评测集扩容（44→~200，带 train/holdout）")
    ap.add_argument("--seed", type=int, default=42, help="随机种子（默认 42，确定性）")
    ap.add_argument("--target", type=int, default=200, help="目标总条数")
    ap.add_argument("--dry-run", action="store_true", help="只打印统计不写文件")
    args = ap.parse_args()
    random.seed(args.seed)

    existing = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    seed_items = existing["items"]
    existing_queries = {i["query"] for i in seed_items}

    roster = character_manager.get_all_characters()
    roster_names = {c.name for c in roster}
    roster_list = sorted(roster_names)
    n_same, n_cross, n_trap, n_event, n_neg = 42, 38, len(CROSS_TRAP_PAIRS), len(EVENTS), 16
    n_multi = len(MULTI_ITEMS)
    plan_n = 44 + n_same + n_cross + n_trap + n_event + n_neg + n_multi

    # 先校验人工池金标：全部 ∈ roster 且知识库可检索（负样本除外）
    problems = []
    for typ, exp in [("cross_trap", (t for _, t, _ in CROSS_TRAP_PAIRS)),
                     ("event", (a for a, _ in EVENTS)),
                     ("multi", (c for _, lst, _ in MULTI_ITEMS for c in lst))]:
        for name in exp:
            if name not in roster_names:
                problems.append(f"[{typ}] {name} 不在 97 人全表")
            elif not kb_has(name):
                problems.append(f"[{typ}] {name} 无 historical 知识文件")
    for a, t, _ in CROSS_TRAP_PAIRS:
        if a not in roster_names:
            problems.append(f"[cross_trap] asker {a} 不在全表")
    for neg in OUT_OF_KB:
        if neg in roster_names:
            problems.append(f"[negative] {neg} 竟在全表（库外断言失效）")
    if problems:
        print("⚠️  金标校验失败：")
        for p in problems:
            print("   ", p)
        raise SystemExit(1)

    items = list(seed_items)
    items += gen_same(roster, existing_queries, n_same)
    items += gen_cross(roster, existing_queries, n_cross)
    items += [{"type": "cross_trap", "asker": a, "expected": t, "query": q}
              for a, t, q in CROSS_TRAP_PAIRS]
    items += [{"type": "event", "asker": a, "expected": a, "query": q} for a, q in EVENTS]
    items += [{"type": "negative", "asker": random.choice(roster_list), "expected": None,
               "query": f"{neg}有哪些主要成就和贡献"} for neg in
              random.sample(OUT_OF_KB, n_neg)]
    items += [{"type": "multi", "asker": a, "expected": lst, "query": q}
              for a, lst, q in MULTI_ITEMS]

    # 分层切分：按 type 80/20 → train / holdout
    by_type = {}
    for it in items:
        by_type.setdefault(it["type"], []).append(it)
    train, holdout = [], []
    for t, lst in by_type.items():
        random.shuffle(lst)
        k = max(1, int(round(len(lst) * 0.2)))
        holdout += lst[:k]
        train += lst[k:]
    random.shuffle(train)
    random.shuffle(holdout)
    for it in train:
        it["split"] = "train"
    for it in holdout:
        it["split"] = "holdout"

    from collections import Counter
    tc, hc = Counter(i["type"] for i in train), Counter(i["type"] for i in holdout)
    print(f"== 扩容完成：{len(items)} 条（目标 {args.target}）| seed={args.seed} ==")
    print(f"   train {len(train)} / holdout {len(holdout)}")
    print(f"   type 分布: {dict(Counter(i['type'] for i in items))}")
    print(f"   holdout 分层: {dict(hc)}")
    for it in holdout[:5]:
        exp = ",".join(it["expected"]) if isinstance(it["expected"], list) else it["expected"]
        print(f"   [holdout][{it['type']}] {it['asker']} → {exp} | {it['query'][:36]}")

    if args.dry_run:
        print("\n(dry-run，未写文件)")
        return
    out = {"_comment": f"综合评测集（扩容版）：{len(items)} 条，含 train/holdout 分层（seed={args.seed}）。"
                        "expected=None 表示库外负面；expected=数组表示多相关题。",
           "items": items}
    EVAL_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {EVAL_FILE}")


if __name__ == "__main__":
    main()
