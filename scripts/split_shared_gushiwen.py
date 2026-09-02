"""
A 类人物分章归位：把"共享正史章节"的既有 gushiwen 原文按人物生成独立知识文件。

背景：gushiwen 的合传/合卷章节（如 史记·五帝本纪、三国志·关张马黄赵传第六）
被 crawl_cache 按 URL 去重——同一章节只能落到第一个处理的人物名下（黄帝/周文王/
卫青/关羽），其余同章人物（炎帝/尧/舜/周武王/霍去病/张飞/赵云）因此缺失独立
【人物】文件，检索时按人物过滤命中不到，退到 persona 兜底。

本脚本离线完成"分章归位"（内容与既有共享文件相同，无需重抓）：
  1. 对每个指定人物，从 character_sources.json 取 (book, chapter)；
  2. 经 gushiwen_resolution.json 解析出章节 URL；
  3. 在 data/knowledge 找到该 URL 对应的既有 gushiwen 文件（共享原文）；
  4. 生成独立文件 biography_<人物>_gushiwen_<书>.txt：【人物】归位、篇卷取本人
     章节名、【白话】取自本人 persona 摘要（与 GushiwenFetcher._persona_gloss 同口径）。

用法：
  python scripts/split_shared_gushiwen.py --dry-run          # 打印计划
  python scripts/split_shared_gushiwen.py                    # 实际生成
  python scripts/split_shared_gushiwen.py --characters 张飞,赵云
"""
import os
import re
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SOURCES_FILE = Path(__file__).resolve().parent.parent / "data" / "sources" / "character_sources.json"
RESOLUTION_FILE = Path(__file__).resolve().parent.parent / "data" / "sources" / "gushiwen_resolution.json"
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"

# A 类 7 人（共享章节原文已在库，仅缺独立【人物】文件）
A_CLASS = ["炎帝", "尧", "舜", "周武王", "霍去病", "张飞", "赵云"]


def persona_gloss(character: str) -> str:
    """从同人物 persona 摘要取前两句作白话导读（与 crawl_knowledge 口径一致）。"""
    p = KNOWLEDGE_DIR / f"biography_{character}_内置.txt"
    if not p.exists():
        return ""
    txt = p.read_text(encoding="utf-8")
    body = txt.split("---", 1)[1] if "---" in txt else txt
    body = re.sub(r"^#.*$", "", body, flags=re.M).strip()
    sents = [s for s in re.split(r"(?<=[。！？])", body) if s.strip()]
    gloss = re.sub(r"\s+", "", "".join(sents[:2]))
    return gloss[:80]


def find_shared_file(url: str) -> Path:
    """在 data/knowledge 里找 front-matter 【URL】== 该章节 URL 的 gushiwen 文件。"""
    for p in sorted(KNOWLEDGE_DIR.glob("biography_*_gushiwen_*.txt")):
        head = p.read_text(encoding="utf-8")[:600]
        m = re.search(r"【URL】(.+)", head)
        if m and m.group(1).strip() == url:
            return p
    return None


def split_person(mapping: dict, resolution: dict, name: str, dry_run: bool) -> str:
    entry = mapping.get(name)
    if not entry or not entry.get("books"):
        return f"[跳过] {name}: 映射表无 books"
    b = entry["books"][0]
    res = resolution.get(f"{b['book']}|{b['chapter']}")
    if not res:
        return f"[跳过] {name}: gushiwen 解析表无 {b['book']}|{b['chapter']}"
    url = res["url"]
    shared = find_shared_file(url)
    if shared is None:
        return f"[失败] {name}: 未找到共享文件（URL={url}）"

    out = KNOWLEDGE_DIR / f"biography_{name}_gushiwen_{b['book']}.txt"
    if out.exists():
        return f"[跳过] {name}: 已存在 {out.name}"
    if dry_run:
        return f"[计划] {name} ← {shared.name}（{b['book']}·{b['chapter']}）→ {out.name}"
    if out.exists():
        return f"[跳过] {name}: 已存在 {out.name}"

    text = shared.read_text(encoding="utf-8")
    head, sep, body = text.partition("---")
    if not sep:
        return f"[失败] {name}: 共享文件 {shared.name} 无 front-matter 分隔"
    # 保留共享文件 front-matter，仅替换 人物/标题/篇卷，追加 白话
    lines = head.rstrip().splitlines()
    new_lines = []
    for ln in lines:
        if ln.startswith("# "):
            new_lines.append(f"# {name}（{b['book']}·{b['chapter']}节选）")
        elif ln.startswith("【人物】"):
            new_lines.append(f"【人物】{name}")
        elif ln.startswith("【篇卷】"):
            new_lines.append(f"【篇卷】{b['chapter']}")
        elif ln.startswith("【白话】"):
            continue  # 用本人生成的白话
        else:
            new_lines.append(ln)
    gloss = persona_gloss(name)
    # 【白话】插在 人物 之后（与 crawl 产出顺序一致）
    insert_at = next(
        (i + 1 for i, ln in enumerate(new_lines) if ln.startswith("【人物】")),
        len(new_lines),
    )
    if gloss:
        new_lines.insert(insert_at, f"【白话】{gloss}")
    # 与既有文件一致：空行 + 独占一行的 --- 分隔符 + 空行
    out.write_text("\n".join(new_lines) + "\n\n---\n\n" + body.lstrip("\n"), encoding="utf-8")
    return f"[OK] {name} ← {shared.name} → {out.name}（{len(body.strip())} 字正文）"


def main():
    ap = argparse.ArgumentParser(description="A 类共享章节分章归位")
    ap.add_argument("--characters", default="",
                    help="只处理指定人物，逗号分隔（默认 A 类 7 人）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划")
    args = ap.parse_args()

    mapping = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    resolution = json.loads(RESOLUTION_FILE.read_text(encoding="utf-8"))
    chars = [c.strip() for c in args.characters.split(",") if c.strip()] or A_CLASS

    print(f"== A 类分章归位 | {len(chars)} 人 | dry_run={args.dry_run} ==")
    for name in chars:
        print("  " + split_person(mapping, resolution, name, args.dry_run))


if __name__ == "__main__":
    main()
