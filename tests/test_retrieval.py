"""RAG 检索行为测试（依赖本地 Embedding 缓存，未缓存时自动跳过）"""
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
