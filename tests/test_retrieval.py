"""RAG 检索行为测试（依赖本地 Embedding 缓存，未缓存时自动跳过）"""
import pytest

from src.characters import character_manager


def _agent(vs, name):
    """构造一个不触发 API 调用的 Agent（仅用于检索与 prompt 构建）"""
    from config import get_settings
    from src.agents import HistoryCharacterAgent

    char = character_manager.get_character(name)
    agent = HistoryCharacterAgent.__new__(HistoryCharacterAgent)
    agent.settings = get_settings()
    agent.character = char
    agent.vector_store = vs
    return agent


def _source_chars(agent, query):
    rag = agent._retrieve_knowledge(query)
    return [s["character"] for s in rag.sources] if rag else []


def test_same_person_query_stays_filtered(vector_store):
    """问自己的事 → 检索应聚焦本人史料"""
    srcs = _source_chars(_agent(vector_store, "李白"), "你自己最著名的诗作是什么")
    assert "李白" in srcs


def test_cross_person_query_falls_back_to_global(vector_store):
    """回归：李白问杜甫 → 不得把李白传记当史料注入，应命中杜甫。

    修复前 search_by_character 返回李白传记（非空），全局兜底不触发，
    导致上下文与引用来源错标为李白。
    """
    srcs = _source_chars(_agent(vector_store, "李白"), "介绍一下杜甫的生平和诗歌成就")
    assert "杜甫" in srcs


def test_cross_person_does_not_pollute_with_own_bio(vector_store):
    """跨人物提问时，当事人自己的传记不应排在史料首位"""
    srcs = _source_chars(_agent(vector_store, "李白"), "介绍一下杜甫的生平和诗歌成就")
    assert srcs[0] != "李白"


def test_mengtian_has_own_knowledge(vector_store):
    """回归：蒙恬补齐知识后，按人物检索能命中本人"""
    srcs = _source_chars(_agent(vector_store, "蒙恬"), "你修筑长城的事迹")
    assert "蒙恬" in srcs


def test_sui_wendi_canal_question(vector_store):
    """隋文帝被问大运河：不应把文帝传记当'相关史料'强行作答，
    检索要么给出炀帝的史料（澄清事实），要么保持文帝本人聚焦。"""
    srcs = _source_chars(_agent(vector_store, "隋文帝"), "开凿大运河的事")
    # 至少要有检索结果，且来源必须是隋朝相关人物（文帝或炀帝）
    assert srcs, "隋文帝大运河问题检索为空"
    assert any(c in ("隋文帝", "隋炀帝") for c in srcs)


# ─── filtered_score_ratio 阈值边界测试（纯逻辑，不依赖向量库/embedding）───

def _plain_agent(name="李白"):
    """构造一个仅含 settings/character 的 Agent（不依赖向量库）"""
    from config import get_settings
    from src.agents import HistoryCharacterAgent

    char = character_manager.get_character(name)
    agent = HistoryCharacterAgent.__new__(HistoryCharacterAgent)
    agent.settings = get_settings()
    agent.character = char
    return agent


def test_filtered_ratio_equals_threshold_keeps_filtered():
    """边界：过滤结果分数刚好等于阈值（best_global * ratio）→ 保留人物聚焦结果"""
    agent = _plain_agent()
    ratio = agent.settings.filtered_score_ratio
    assert agent._should_use_filtered(best_filtered=1.0 * ratio, best_global=1.0) is True


def test_filtered_ratio_clearly_worse_falls_back_to_global():
    """明显劣于阈值（> best_global * ratio）→ 退回全局检索"""
    agent = _plain_agent()
    ratio = agent.settings.filtered_score_ratio
    assert agent._should_use_filtered(best_filtered=1.0 * ratio + 0.5, best_global=1.0) is False


def test_filtered_ratio_no_global_keeps_filtered():
    """全局检索无结果时，保留人物聚焦结果"""
    agent = _plain_agent()
    assert agent._should_use_filtered(best_filtered=999.0, best_global=None) is True


# ───────────────── 数据源双轨：真实史源 vs persona 标注 ─────────────────
# （纯逻辑测试不依赖向量库；严格模式检索测试依赖重建后的向量库含 doc_type）

from langchain_core.documents import Document


def _mk(doc_type="historical", book="", chapter="", dynasty="", source="ctext",
        title="t"):
    return Document(page_content="x", metadata={
        "doc_type": doc_type, "book": book, "chapter": chapter,
        "dynasty": dynasty, "source": source, "title": title,
    })


def test_source_label_historical_with_book():
    """史源块头显示 朝代·《书·篇卷》- 来源"""
    from src.agents import HistoryCharacterAgent
    doc = _mk(book="史记", chapter="孔子世家", dynasty="春秋", source="ctext.org")
    label = HistoryCharacterAgent._source_label(doc)
    assert label == "出处: 春秋·《史记·孔子世家》 - ctext.org"


def test_source_label_historical_without_book():
    from src.agents import HistoryCharacterAgent
    doc = _mk(book="", source="维基百科", title="孔子")
    label = HistoryCharacterAgent._source_label(doc)
    assert "来源: 维基百科 - 孔子" in label
    assert "内置摘要" not in label


def test_source_label_persona_annotated():
    """persona 块头标注「（内置摘要·非权威史源，仅风格参考）」"""
    from src.agents import HistoryCharacterAgent
    doc = _mk(doc_type="persona", source="内置知识库", title="孔子")
    label = HistoryCharacterAgent._source_label(doc)
    assert "（内置摘要·非权威史源，仅风格参考）" in label


def test_footer_label_historical_and_persona():
    from src.agents import HistoryCharacterAgent
    hist = {"index": 1, "doc_type": "historical", "book": "史记",
            "chapter": "孔子世家", "dynasty": "春秋", "source": "ctext.org",
            "title": "t"}
    assert HistoryCharacterAgent._footer_label(hist) == \
        "[1]《史记·孔子世家》- 春秋·ctext.org"
    pers = {"index": 2, "doc_type": "persona", "source": "内置知识库",
            "title": "孔子"}
    assert "（内置摘要·非权威）" in HistoryCharacterAgent._footer_label(pers)


def test_partition_docs_historical_first_stable():
    """双轨分区：史源按原序在前，persona 补位，类型内保持原序（稳定排序）"""
    from src.agents import HistoryCharacterAgent
    p1 = _mk(doc_type="persona", title="p1")
    h1 = _mk(doc_type="historical", title="h1")
    h2 = _mk(doc_type="historical", title="h2")
    p2 = _mk(doc_type="persona", title="p2")
    out = HistoryCharacterAgent._partition_docs_by_type([p1, h1, h2, p2])
    assert [d.metadata["title"] for d in out] == ["h1", "h2", "p1", "p2"]


def test_persona_fallback_off_excludes_persona(vector_store):
    """严格模式（PERSONA_FALLBACK=off）：检索结果不含 persona（内置摘要）。

    向量库需已重建（scripts/build_vector_db.py）含 doc_type 元数据；离线且
    真实史源未入库时检索为空属预期（persona 完全移出史实检索）。
    """
    from config import get_settings
    from src.agents import HistoryCharacterAgent
    char = character_manager.get_character("孔子")
    agent = HistoryCharacterAgent.__new__(HistoryCharacterAgent)
    # model_copy 避免改写共享的 lru_cached settings 单例
    agent.settings = get_settings().model_copy(update={"persona_fallback": False})
    agent.character = char
    agent.vector_store = vector_store
    rag = agent._retrieve_knowledge("你的核心思想是什么")
    if not rag:
        pytest.skip("严格模式离线无史源 → 空检索属预期（persona 已移出）")
    assert all(s["doc_type"] == "historical" for s in rag.sources)


def test_historical_ranked_before_persona(vector_store):
    """双轨（fallback=on）：同人物命中含真实史源时史源排前、persona 补位。"""
    rag = _agent(vector_store, "孔子")._retrieve_knowledge("你的核心思想是什么")
    if not rag or len(rag.sources) < 2:
        pytest.skip("检索结果不足，无法断言排序")
    types = [s["doc_type"] for s in rag.sources]
    if "persona" in types:
        # 分区保证：出现 persona 之后不能再出现 historical
        assert "historical" not in types[types.index("persona"):]
