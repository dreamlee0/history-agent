"""多格式文档解析测试：tmp 目录生成 10 种格式夹具（txt/md/html/xml/json/csv/tsv/pdf/docx/xlsx），断言统一元数据与正文抽取。

PDF 用手工构造的最小合法 PDF（pypdf 可抽取文本）；DOCX 用 python-docx；
XLSX 用 pandas/openpyxl 生成——全部离线可跑，不依赖网络。
"""
import json
import re
from pathlib import Path

import pytest

from src.retrievers.document_loader import load_documents

TXT = """# 张衡：候风地动仪
【来源】测试语料
【人物】张衡
【分类】biography
---
张衡造候风地动仪，以精铜铸成，能测知地震方位。
"""

MD = """# 张衡：浑天说

【来源】测试语料
【人物】张衡
---
张衡著《灵宪》，阐发浑天说。
"""

HTML = """<html><head><title>张衡</title></head><body>
<p>【来源】测试语料</p><p>【人物】张衡</p><p>---</p>
<p>张衡创制漏水转浑天仪，演示星象运行。</p></body></html>"""

XML = """<?xml version="1.0" encoding="utf-8"?>
<doc><meta>【人物】张衡</meta><meta>【来源】测试语料</meta><meta>---</meta>
<content>张衡观测天象，著《灵宪》。</content></doc>"""

JSON_ARRAY = json.dumps([
    {"title": "张衡地动仪", "content": "阳嘉元年造候风地动仪，以测地震。",
     "source": "测试语料", "character": "张衡", "category": "biography"},
    {"title": "张衡圆周率", "text": "张衡取圆周率约为根号十。",
     "source": "测试语料", "character": "张衡"},
], ensure_ascii=False)

CSV = """title,content,source,character,category
张衡地动仪,张衡造候风地动仪测知地震。,测试语料,张衡,biography
"""

TSV = "title\tcontent\tsource\tcharacter\tcategory\n张衡浑天说\t张衡著《灵宪》阐发浑天说。\t测试语料\t张衡\tbiography\n"


def _make_pdf(text: str) -> bytes:
    """构造一个最小合法 PDF（含文本对象），供 PyPDFLoader 抽取。"""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = ("BT /F1 12 Tf 72 720 Td (" + text + ") Tj ET").encode("latin-1")
    objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


@pytest.fixture
def fixtures(tmp_path):
    """在 tmp 目录生成全部格式夹具，返回 {ext: path}。"""
    paths = {}
    (tmp_path / "a.txt").write_text(TXT, encoding="utf-8"); paths["txt"] = tmp_path / "a.txt"
    (tmp_path / "a.md").write_text(MD, encoding="utf-8"); paths["md"] = tmp_path / "a.md"
    (tmp_path / "a.html").write_text(HTML, encoding="utf-8"); paths["html"] = tmp_path / "a.html"
    (tmp_path / "a.xml").write_text(XML, encoding="utf-8"); paths["xml"] = tmp_path / "a.xml"
    (tmp_path / "a.json").write_text(JSON_ARRAY, encoding="utf-8"); paths["json"] = tmp_path / "a.json"
    (tmp_path / "a.csv").write_text(CSV, encoding="utf-8"); paths["csv"] = tmp_path / "a.csv"
    (tmp_path / "a.tsv").write_text(TSV, encoding="utf-8"); paths["tsv"] = tmp_path / "a.tsv"
    (tmp_path / "a.pdf").write_bytes(_make_pdf("Zhang Heng di dong yi"))
    paths["pdf"] = tmp_path / "a.pdf"

    from docx import Document as DocxDocument
    d = DocxDocument()
    for line in ["【人物】张衡", "【来源】测试语料", "---", "张衡著《灵宪》。"]:
        d.add_paragraph(line)
    docx_path = tmp_path / "a.docx"
    d.save(str(docx_path)); paths["docx"] = docx_path

    import pandas as pd
    xlsx_path = tmp_path / "a.xlsx"
    pd.DataFrame({
        "title": ["张衡地动仪"],
        "content": ["张衡造候风地动仪以测地震"],
        "source": ["测试语料"], "character": ["张衡"], "category": ["biography"],
    }).to_excel(str(xlsx_path), index=False)
    paths["xlsx"] = xlsx_path
    return paths


def test_txt_parses_front_matter_and_body(fixtures):
    docs = load_documents(fixtures["txt"])
    assert len(docs) == 1
    d = docs[0]
    assert d.metadata["character"] == "张衡"
    assert d.metadata["source"] == "测试语料"
    assert d.metadata["title"] == "张衡：候风地动仪"
    assert "以精铜铸成" in d.page_content
    # 前置头/分隔符不进正文
    assert "【来源】" not in d.page_content


@pytest.mark.parametrize("ext", ["md", "html", "xml", "docx", "pdf"])
def test_single_doc_formats(fixtures, ext):
    docs = load_documents(fixtures[ext])
    assert len(docs) == 1, ext
    d = docs[0]
    assert "张衡" in d.page_content or "Zhang Heng" in d.page_content
    # 带前置头时人物应被提取
    assert d.metadata["character"] in ("张衡", "")


def test_json_array_multi_docs(fixtures):
    docs = load_documents(fixtures["json"])
    assert len(docs) == 2
    assert {d.metadata["title"] for d in docs} == {"张衡地动仪", "张衡圆周率"}
    assert all(d.metadata["character"] == "张衡" for d in docs)


def test_csv_and_tsv_per_row(fixtures):
    for ext in ("csv", "tsv"):
        docs = load_documents(fixtures[ext])
        assert len(docs) == 1, ext
        assert docs[0].metadata["character"] == "张衡"
        assert "地动仪" in docs[0].page_content or "浑天说" in docs[0].page_content


def test_xlsx_content_column(fixtures):
    docs = load_documents(fixtures["xlsx"])
    assert len(docs) == 1
    assert docs[0].metadata["character"] == "张衡"
    assert "地动仪" in docs[0].page_content


def test_unknown_extension_skipped(tmp_path):
    p = tmp_path / "a.odt"
    p.write_text("随便什么", encoding="utf-8")
    assert load_documents(p) == []


def test_empty_pdf_skipped(tmp_path):
    """无文本层 PDF（扫描件）→ 明确跳过，不产生空文档"""
    p = tmp_path / "scan.pdf"
    p.write_bytes(_make_pdf(""))  # 空文本的 PDF
    assert load_documents(p) == []


def test_aliases_metadata_written(fixtures):
    """人物别名写入 chunk 元数据（与既有 txt 行为一致）"""
    docs = load_documents(fixtures["json"])
    # 张衡无内置别名 → 空字符串；不为空则应为逗号分隔
    for d in docs:
        assert isinstance(d.metadata["aliases"], str)


# ───────────────── 数据源升级：doc_type / 朝代 / 书 / 篇 透传 ─────────────────

HISTORICAL_TXT = """# 孔子世家节选
【来源】ctext.org（中国哲学书电子化计划）
【URL】https://ctext.org/shiji/kongzi-shi-jia/zh
【分类】biography
【人物】孔子
【朝代】春秋
【出处】《史记》
【篇卷】孔子世家
---
孔子长九尺有六寸，人皆谓之长人而异之。
"""

PERSONA_TXT = """# 孔子
【来源】内置知识库
【人物】孔子
【分类】biography
---
孔子主张仁与礼，强调克己复礼。
"""


def test_doc_type_historical_from_real_source(tmp_path):
    """真实史源文件名（不带 _内置）→ doc_type=historical，朝代/书/篇透传"""
    p = tmp_path / "biography_孔子_ctext_史记.txt"
    p.write_text(HISTORICAL_TXT, encoding="utf-8")
    docs = load_documents(p)
    d = docs[0]
    assert d.metadata["doc_type"] == "historical"
    assert d.metadata["dynasty"] == "春秋"
    assert d.metadata["book"] == "史记"
    assert d.metadata["chapter"] == "孔子世家"
    assert d.metadata["url"].startswith("https://ctext.org")


def test_doc_type_persona_from_builtin_source(tmp_path):
    """来源=内置知识库 → doc_type=persona（即使文件名不带 _内置）"""
    p = tmp_path / "biography_孔子.txt"
    p.write_text(PERSONA_TXT, encoding="utf-8")
    docs = load_documents(p)
    assert docs[0].metadata["doc_type"] == "persona"


def test_doc_type_persona_from_underscore_suffix(tmp_path):
    """文件名含 _内置 → doc_type=persona"""
    p = tmp_path / "biography_孔子_内置.txt"
    p.write_text(PERSONA_TXT, encoding="utf-8")
    docs = load_documents(p)
    assert docs[0].metadata["doc_type"] == "persona"


def test_doc_type_explicit_front_matter_wins(tmp_path):
    """显式 doc_type 优先于文件名校验"""
    txt = HISTORICAL_TXT.replace(
        "【人物】孔子", "【人物】孔子\n【doc_type】persona"
    )
    p = tmp_path / "biography_孔子_ctext_史记.txt"
    p.write_text(txt, encoding="utf-8")
    docs = load_documents(p)
    assert docs[0].metadata["doc_type"] == "persona"


def test_dynasty_backfilled_from_character(tmp_path):
    """朝代缺失时从人物配置（character_manager）补齐"""
    txt = (HISTORICAL_TXT
           .replace("【朝代】春秋\n", "")
           .replace("【人物】孔子", "【人物】李白")
           .replace("【篇卷】孔子世家", "【篇卷】李白传")
           .replace("孔子长九尺有六寸，人皆谓之长人而异之。",
                    "白，兴圣皇帝九世孙。"))
    p = tmp_path / "biography_李白_ctext_新唐书.txt"
    p.write_text(txt, encoding="utf-8")
    docs = load_documents(p)
    assert docs[0].metadata["dynasty"] == "唐朝"


def test_csv_new_columns_passthrough(tmp_path):
    """CSV 新增 doc_type/dynasty/book/chapter 列透传到元数据"""
    csv_path = tmp_path / "c.csv"
    csv_path.write_text(
        "title,content,source,character,category,doc_type,dynasty,book,chapter\n"
        "李白传,李白兴圣皇帝九世孙。,ctext.org,李白,biography,"
        "historical,唐朝,新唐书,李白传\n",
        encoding="utf-8",
    )
    docs = load_documents(csv_path)
    d = docs[0]
    assert d.metadata["doc_type"] == "historical"
    assert d.metadata["dynasty"] == "唐朝"
    assert d.metadata["book"] == "新唐书"
    assert d.metadata["chapter"] == "李白传"


def test_xlsx_new_columns_passthrough(tmp_path):
    """XLSX 新增 doc_type/dynasty/book/chapter 列透传到元数据"""
    import pandas as pd
    xlsx_path = tmp_path / "c.xlsx"
    pd.DataFrame({
        "title": ["李白传"], "content": ["李白兴圣皇帝九世孙。"],
        "source": ["ctext.org"], "character": ["李白"], "category": ["biography"],
        "doc_type": ["historical"], "dynasty": ["唐朝"],
        "book": ["新唐书"], "chapter": ["李白传"],
    }).to_excel(str(xlsx_path), index=False)
    docs = load_documents(xlsx_path)
    d = docs[0]
    assert d.metadata["doc_type"] == "historical"
    assert d.metadata["dynasty"] == "唐朝"
    assert d.metadata["book"] == "新唐书"
    assert d.metadata["chapter"] == "李白传"
