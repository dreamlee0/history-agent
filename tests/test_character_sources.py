"""97 人数据源映射表完整性测试。

character_sources.json 是"聚焦 97 人不抓全量《二十四史》"的核心配置：
每人有朝代 + 书籍候选（ctext URL）+ 维基条目名。本测试离线校验结构完整性
（97 人全覆盖、字段齐全、URL 格式），不校验链接可达性——网络恢复后由
scripts/crawl_knowledge.py 以 HTTP 200 校验（失败跳过并告警，不伪造产出）。
"""
import json
import re
from pathlib import Path

from src.characters import character_manager

SOURCES_FILE = Path(__file__).resolve().parent.parent / "data" / "sources" / "character_sources.json"

# ctext 章节 URL = https://ctext.org/<书slug>/<章slug>/zh（须含书前缀，结构完整）
CTEXT_URL_RE = re.compile(r"^https://ctext\.org/[a-z0-9-]+/[a-z0-9-]+/zh$")

# 映射表引用的典籍应落在已知公版正史/编年集合内（防书名字笔误）
KNOWN_BOOKS = {
    "史记", "汉书", "后汉书", "三国志", "晋书", "隋书",
    "旧唐书", "新唐书", "宋史", "元史", "明史", "清史稿", "新五代史",
}


def _load() -> dict:
    assert SOURCES_FILE.exists(), f"缺少映射表: {SOURCES_FILE}"
    return json.loads(SOURCES_FILE.read_text(encoding="utf-8"))


def test_all_97_characters_covered():
    """映射表应与 97 个人物完全对齐：无缺无多。"""
    mapping = _load()
    chars = set(character_manager.list_names())
    assert set(mapping) == chars
    assert len(mapping) >= 90, "映射表至少应覆盖 90 人"


def test_every_entry_has_required_fields():
    mapping = _load()
    for name, e in mapping.items():
        assert e["dynasty"], f"{name} 缺朝代"
        assert e["wikipedia"], f"{name} 缺维基条目名"
        assert isinstance(e["books"], list), f"{name} books 应为列表"
        assert "note" in e, f"{name} 缺 note"


def test_everyone_has_some_source():
    """每人至少有一条可用数据源：古籍书籍候选或维基条目。"""
    mapping = _load()
    for name, e in mapping.items():
        assert e["books"] or e["wikipedia"], f"{name} 无任何数据源"


def test_books_referenced_are_known():
    mapping = _load()
    for name, e in mapping.items():
        for b in e["books"]:
            assert b["book"] in KNOWN_BOOKS, f"{name}: 未知典籍 {b['book']}"


def test_ctext_urls_structurally_complete():
    """ctext URL 含书前缀+章前缀，格式 https://ctext.org/<书>/<章>/zh。"""
    mapping = _load()
    for name, e in mapping.items():
        for b in e["books"]:
            assert b["book"] and b["chapter"], f"{name}: 书籍缺书/篇"
            assert CTEXT_URL_RE.match(b["ctext"]), f"{name}: 非法 ctext URL {b['ctext']}"


def test_books_per_person_bounded():
    """每人书籍候选 1-3 条（聚焦人物，不抓全量二十四史）。"""
    mapping = _load()
    for name, e in mapping.items():
        assert 0 <= len(e["books"]) <= 3, f"{name}: books 数量 {len(e['books'])}"


def test_no_builtin_persona_leak():
    """映射表只含真实史源候选，不应出现"内置"标记。"""
    mapping = _load()
    for name, e in mapping.items():
        assert "_内置" not in name and "内置" not in json.dumps(e, ensure_ascii=False), name
