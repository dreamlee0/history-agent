"""抓取器测试：mock requests（绝不联网）→ ctext 原文解析 / 维基 extracts /
去重缓存 / 输出 front-matter（doc_type=historical）。

网络不可达的开发环境里，测试通过 monkeypatch session.get 返回构造的
HTML/JSON 响应。ctext 解析选择器为最佳努力推断，若真实页面结构变化，
本测试用与 _extract 同构的夹具验证"剥离注疏 + 取原文"逻辑本身，不改断言
即能发现解析器失效（抓取器会打印"原文过短"告警而非静默产出）。
"""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from scripts.crawl_knowledge import (
    CtextFetcher,
    CrawlResult,
    GushiwenFetcher,
    WikipediaFetcher,
    fetch_sources,
    save_result,
)


class FakeResp:
    def __init__(self, text="", status_code=200):
        self.text = text
        self.status_code = status_code

    def json(self):
        return json.loads(self.text)


# 与 CtextFetcher._extract 选择器同构的 ctext 章节页夹具（含校注/疏）
CTEXT_HTML = """<html><body>
<div class="ctext" id="ctext_1">
  孔子长九尺有六寸<sup>1</sup><span class="annot">《史记索隐》：身长九尺六寸者……</span>，
  人皆谓之长人而异之。
</div>
<div class="ctext">防叔生伯夏，伯夏生叔梁纥。</div>
<div id="content5">纥与颜氏女野合而生孔子<sup>2</sup>，祷于尼丘得孔子。</div>
</body></html>"""


def _ctext_fetcher(tmp_path, monkeypatch):
    f = CtextFetcher(str(tmp_path), cache_file=str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        f.session, "get",
        lambda url, timeout=20, allow_redirects=True: FakeResp(text=CTEXT_HTML),
    )
    return f


# ───────────────────────── CtextFetcher ─────────────────────────

def test_ctext_extract_strips_annotations(tmp_path, monkeypatch):
    f = _ctext_fetcher(tmp_path, monkeypatch)
    text = f._extract(CTEXT_HTML)
    # 原文段落完整保留
    assert "孔子长九尺有六寸" in text
    assert "人皆谓之长人而异之" in text
    assert "防叔生伯夏" in text
    assert "野合而生孔子" in text
    # 校注/疏（span.annot / sup）已剥离
    assert "索隐" not in text
    assert "九尺六寸者" not in text


def test_ctext_fetch_returns_result_and_dedups(tmp_path, monkeypatch):
    f = _ctext_fetcher(tmp_path, monkeypatch)
    r = f.fetch("https://ctext.org/shiji/kongzi-shi-jia/zh",
                "孔子", "史记", "孔子世家", "春秋")
    assert r is not None
    assert r.doc_type == "historical"
    assert r.book == "史记"
    assert r.chapter == "孔子世家"
    assert r.dynasty == "春秋"
    assert r.source.startswith("ctext.org")
    # 去重缓存：同一 URL 第二次抓取直接跳过
    assert f.fetch("https://ctext.org/shiji/kongzi-shi-jia/zh",
                   "孔子", "史记", "孔子世家", "春秋") is None


def test_ctext_short_content_rejected(tmp_path, monkeypatch):
    f = CtextFetcher(str(tmp_path), cache_file=str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        f.session, "get",
        lambda url, timeout=20, allow_redirects=True: FakeResp(text="<html><body></body></html>"),
    )
    # 解析为空/过短 → 视为失败（页面结构变化或 slug 错误），不产出
    assert f.fetch("https://ctext.org/x/zh", "孔子", "史记", "x", "春秋") is None


# ───────────────────────── GushiwenFetcher ─────────────────────────

# 与 GushiwenFetcher._extract 选择器同构的章节页夹具：
# div.contson 为正文容器，混入 译文/注释 附加区测试防御性截断
GUSHIWEN_HTML = """<html><body>
<div class="main3"><div class="son2">
  <div class="cont"><div class="contson">
    孔子长九尺有六寸，人皆谓之长人而异之。
    防叔生伯夏，伯夏生叔梁纥。纥与颜氏女野合而生孔子，祷于尼丘得孔子。
    译文：孔子身高九尺六寸……
    注释：见《史记索隐》……
  </div></div>
</div></div>
</body></html>"""


def test_gushiwen_extract_div_contson(tmp_path, monkeypatch):
    f = GushiwenFetcher(str(tmp_path), cache_file=str(tmp_path / "cache.json"))
    text = f._extract(GUSHIWEN_HTML)
    # 正文原文完整保留
    assert "孔子长九尺有六寸" in text
    assert "野合而生孔子" in text
    # 防御性截断：译文/注释等附加区不进入原文
    assert "译文" not in text
    assert "注释" not in text


def test_gushiwen_resolve_real_resolution_file(tmp_path):
    # 已核验的真实解析条目：史记本传 + 三国志合传（resolution 表驱动）
    # 注意用 tmp_path 隔离输出/缓存，避免固定 /tmp 路径在并行运行/多机间互相污染
    f = GushiwenFetcher(str(tmp_path), cache_file=str(tmp_path / "cache.json"))
    url = f.resolve("史记", "孔子世家")
    assert url and url.startswith("https://www.gushiwen.cn/guwen/bookv_")
    # 解析表缺失 → None（persona 兜底路径）
    assert f.resolve("晋书", "第一章") is None


def test_gushiwen_fetch_returns_result_and_dedups(tmp_path, monkeypatch):
    f = GushiwenFetcher(str(tmp_path), cache_file=str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        f, "resolve",
        lambda book, chapter: "https://www.gushiwen.cn/guwen/bookv_fake.aspx",
    )
    monkeypatch.setattr(
        f.session, "get",
        lambda url, timeout=20, allow_redirects=True: FakeResp(text=GUSHIWEN_HTML),
    )
    r = f.fetch("史记", "孔子世家", "孔子", "春秋")
    assert r is not None
    assert r.doc_type == "historical"
    assert r.book == "史记"
    assert r.chapter == "孔子世家"
    assert r.dynasty == "春秋"
    assert "古诗文网" in r.source
    assert "www.gushiwen.cn" in r.url
    # 去重缓存：同一章节第二次抓取直接跳过
    assert f.fetch("史记", "孔子世家", "孔子", "春秋") is None


def test_gushiwen_unresolved_skips(tmp_path, monkeypatch):
    f = GushiwenFetcher(str(tmp_path), cache_file=str(tmp_path / "cache.json"))
    monkeypatch.setattr(f, "resolve", lambda book, chapter: None)
    # 解析表未覆盖（如晋书）→ 跳过、不产出、persona 兜底
    assert f.fetch("晋书", "第一章", "某人", "唐") is None


# ───────────────────────── WikipediaFetcher ─────────────────────────

WIKI_JSON = json.dumps({
    "query": {"pages": {"123": {
        "title": "孔子",
        "extract": "孔子（前551年—前479年），名丘，字仲尼，鲁国陬邑人，中国春秋末期思想家、教育家，儒家学派创始人。其思想核心是仁与礼，主张克己复礼、有教无类，晚年整理《诗》《书》《礼》《乐》《易》《春秋》六经，被后世尊为至圣先师。",
    }}}
}, ensure_ascii=False)


def test_wikipedia_extracts_parse(tmp_path, monkeypatch):
    f = WikipediaFetcher(str(tmp_path), cache_file=str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        f.session, "get",
        lambda url, timeout=20, allow_redirects=True: FakeResp(text=WIKI_JSON),
    )
    r = f.fetch("孔子", "孔子")
    assert r is not None
    assert "儒家学派创始人" in r.content
    assert r.doc_type == "historical"
    assert "zh.wikipedia.org" in r.url
    # 二次文献声明：正文明确标注"非古籍原文"
    assert "二次文献" in r.content or "非古籍原文" in r.content


def test_wikipedia_missing_page_rejected(tmp_path, monkeypatch):
    f = WikipediaFetcher(str(tmp_path), cache_file=str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        f.session, "get",
        lambda url, timeout=20, allow_redirects=True:
            FakeResp(text=json.dumps({"query": {"pages": {"-1": {"title": "不存在的人物"}}}})),
    )
    assert f.fetch("不存在的人物", "不存在的人物") is None


# ───────────────────────── 输出文件 / 计划 ─────────────────────────

def test_save_result_front_matter(tmp_path):
    """输出 front-matter 含 朝代/出处/篇卷/URL，文件名不带 _内置 → historical"""
    r = CrawlResult(
        title="孔子（史记·孔子世家节选）", content="孔子长九尺有六寸。",
        source="ctext.org（中国哲学书电子化计划）",
        url="https://ctext.org/shiji/kongzi-shi-jia/zh",
        character="孔子", category="biography", dynasty="春秋",
        book="史记", chapter="孔子世家", doc_type="historical",
    )
    fp = Path(save_result(r, tmp_path))
    assert fp.name == "biography_孔子_ctext_史记.txt"
    text = fp.read_text(encoding="utf-8")
    assert "【朝代】春秋" in text
    assert "【出处】《史记》" in text
    assert "【篇卷】孔子世家" in text
    assert "【URL】https://ctext.org" in text
    assert "【人物】孔子" in text


def test_fetch_sources_dry_run_prints_plan_without_network(tmp_path):
    """dry-run 不联网：只打印抓取计划（含构建好的 ctext URL）。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        fetch_sources(
            sources=["ctext"], characters=["孔子"],
            dry_run=True, output_dir=str(tmp_path),
        )
    out = buf.getvalue()
    assert "https://ctext.org/shiji/kongzi-shi-jia/zh" in out
    assert "dry-run" in out
    assert "抓取计划" in out
    # dry-run 不应写出任何知识文件
    assert not list(tmp_path.glob("biography_*.txt"))


def test_main_cli_all_maps_to_gushiwen_wiki(monkeypatch):
    """CLI `--sources all` 必须原样传给 fetch_sources，由后者展开为 gushiwen+wiki。

    回归防护：main() 若像旧版那样把 all 自行展开成 ctext+wiki，会绕过
    fetch_sources 的 all 分支——ctext 403/维基不可达时 `--sources all` 实际
    空抓，与文档及 --help 的"all=gushiwen+wiki"相悖（默认源被静默跳过）。
    "all 展开成哪些源"的唯一权威定义在 fetch_sources（见
    test_character_sources_map_drives_fetch_plan 验证其 → gushiwen+wiki）。
    """
    import sys

    from scripts.crawl_knowledge import main

    captured: dict = {}
    monkeypatch.setattr(
        sys, "argv", ["crawl_knowledge.py", "--sources", "all", "--dry-run"]
    )
    monkeypatch.setattr(
        "scripts.crawl_knowledge.fetch_sources", lambda **kw: captured.update(kw)
    )
    main()
    # main 不得预展开 all（否则 fetch_sources 的默认源逻辑被绕过）
    assert captured["sources"] == ["all"]


def test_character_sources_map_drives_fetch_plan(tmp_path):
    """fetch_sources 从映射表取人物 → 计划覆盖 gushiwen（默认）与维基；ctext 显式。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        fetch_sources(
            sources=["all"], characters=["诸葛亮"],
            dry_run=True, output_dir=str(tmp_path),
        )
    out = buf.getvalue()
    assert "三国志·诸葛亮传" in out
    # 默认 all=gushiwen+wiki：dry-run 解析出 gushiwen 章节 URL
    assert "https://www.gushiwen.cn/guwen/bookv_" in out
    assert "[维基] 诸葛亮" in out
    # ctext 作为显式回退源仍可单独打印计划
    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        fetch_sources(
            sources=["ctext"], characters=["诸葛亮"],
            dry_run=True, output_dir=str(tmp_path),
        )
    out2 = buf2.getvalue()
    assert "https://ctext.org/sanguozhi/zhuge-liang/zh" in out2
