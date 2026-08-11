"""知识文件质量测试"""
from pathlib import Path

from src.retrievers.vector_store import load_knowledge_files

KNOWLEDGE_DIR = Path("data/knowledge")


def _docs():
    return load_knowledge_files(str(KNOWLEDGE_DIR))


def test_knowledge_files_loaded():
    # 97 位人物 + 2 篇事件（赤壁之战/官渡之战）
    assert len(_docs()) >= 97


def test_all_files_have_metadata():
    """每个知识文件都必须解析出 标题/来源/人物 元数据，否则按人物过滤失效"""
    for doc in _docs():
        m = doc.metadata
        assert m.get("title"), f"缺标题: {m.get('file')}"
        assert m.get("source"), f"缺来源: {m.get('file')}"
        assert m.get("character"), f"缺人物: {m.get('file')}"
        assert m.get("category"), f"缺分类: {m.get('file')}"


def test_mengtian_and_lisi_have_knowledge():
    """回归：蒙恬/李斯补齐了知识文件"""
    chars = {d.metadata.get("character") for d in _docs()}
    assert "蒙恬" in chars
    assert "李斯" in chars


def test_sui_wendi_no_canal_fact_error():
    """回归：隋文帝知识条目不得包含'开凿大运河'（那是隋炀帝所为）。

    修复前知识库把大运河记给文帝，模型会据此自信地编造史实。
    """
    docs = {d.metadata.get("character"): d for d in _docs()}
    wendi = docs["隋文帝"]
    assert "大运河" not in wendi.page_content
    assert "科举" in wendi.page_content  # 文帝开科取士仍应保留


def test_sui_yangdi_has_canal():
    """大运河应记在隋炀帝名下"""
    docs = {d.metadata.get("character"): d for d in _docs()}
    yangdi = docs["隋炀帝"]
    assert "大运河" in yangdi.page_content
