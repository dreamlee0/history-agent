"""引用可验证（grounding 硬化）测试：结构化 cited_sources 的解析与校验。

核心主张：模型自由生成的【参考史料】文本不可信（可能引用不存在的文献）；
改为要求模型输出 {reply, cited_sources:[索引]}，代码侧校验索引落在
本次检索集合内才渲染。本文件覆盖解析与校验逻辑本身。
"""
import pytest

from src.agents.history_agent import HistoryCharacterAgent


class TestParseStructuredReply:
    """_parse_structured_reply：健壮地把模型输出解析为 (reply, cited_sources)。"""

    def test_valid_json(self):
        raw = '{"reply": "李白是唐代诗人。", "cited_sources": [0, 2]}'
        reply, cited = HistoryCharacterAgent._parse_structured_reply(raw)
        assert reply == "李白是唐代诗人。"
        assert cited == [0, 2]

    def test_fenced_json_codeblock(self):
        raw = '```json\n{"reply": "回答", "cited_sources": [1]}\n```'
        reply, cited = HistoryCharacterAgent._parse_structured_reply(raw)
        assert reply == "回答"
        assert cited == [1]

    def test_json_surrounded_by_text(self):
        raw = '好的，以下是回答：{"reply": "回答A", "cited_sources": [0, 1]} 完毕'
        reply, cited = HistoryCharacterAgent._parse_structured_reply(raw)
        assert reply == "回答A"
        assert cited == [0, 1]

    def test_plain_text_falls_back_none(self):
        # 模型没按 JSON 输出（如旧版/闲聊）→ 返回 None，调用方回退纯文本
        assert HistoryCharacterAgent._parse_structured_reply("（模拟回复）") is None

    def test_empty_and_none(self):
        assert HistoryCharacterAgent._parse_structured_reply("") is None
        assert HistoryCharacterAgent._parse_structured_reply(None) is None

    def test_missing_reply_field(self):
        # 有 cited_sources 但没有 reply → 视为无效结构化输出
        assert HistoryCharacterAgent._parse_structured_reply('{"cited_sources": [0]}') is None

    def test_cited_sources_non_list(self):
        # cited_sources 不是数组时容错为空列表，不报错
        raw = '{"reply": "x", "cited_sources": "notalist"}'
        reply, cited = HistoryCharacterAgent._parse_structured_reply(raw)
        assert reply == "x"
        assert cited == []


class TestValidateCited:
    """_validate_cited：只保留落在检索集合内的索引，去重升序。"""

    def test_filters_out_of_range_and_dups(self):
        # 5 越界、-1 越界、1 重复 → 只剩 [0, 1]
        assert HistoryCharacterAgent._validate_cited([0, 1, 5, -1, 1], 3) == [0, 1]

    def test_all_invalid(self):
        assert HistoryCharacterAgent._validate_cited([9, 10], 3) == []


def test_chat_filters_sources_to_cited(monkeypatch):
    """回归：模型引用越界（引用了不存在的文献）时，来源只保留合法命中。

    这是"引用可验证"的端到端行为：即使模型 JSON 里写了 99，
    渲染/返回的来源也只能是本次检索集合内存在的史料（0 号）。
    """
    from config import get_settings
    from src.characters import character_manager
    from src.memory import conversation_memory
    from src.agents.history_agent import HistoryCharacterAgent, RAGContext
    from langchain_core.documents import Document

    char = character_manager.get_character("李白")
    agent = HistoryCharacterAgent.__new__(HistoryCharacterAgent)
    agent.settings = get_settings()
    agent.character = char
    agent.vector_store = None
    agent.db = None

    fake_docs = [
        Document(page_content="内容A", metadata={"title": "甲书", "source": "s1", "url": "", "character": "李白"}),
        Document(page_content="内容B", metadata={"title": "乙书", "source": "s2", "url": "", "character": "李白"}),
        Document(page_content="内容C", metadata={"title": "丙书", "source": "s3", "url": "", "character": "杜甫"}),
    ]
    fake_sources = [
        {"index": 1, "title": "甲书", "source": "s1", "url": "", "character": "李白"},
        {"index": 2, "title": "乙书", "source": "s2", "url": "", "character": "李白"},
        {"index": 3, "title": "丙书", "source": "s3", "url": "", "character": "杜甫"},
    ]

    def _fake_retrieve(query, request_id=None):
        return RAGContext(
            query=query, documents=fake_docs,
            context_text="[史料1] 来源: s1 - 甲书\n内容A",
            sources=fake_sources,
        )

    monkeypatch.setattr(agent, "_retrieve_knowledge", _fake_retrieve)
    # 模型引用了 0 和 99：99 越界，应被丢弃
    monkeypatch.setattr(
        agent, "_call_api_with_retry",
        lambda messages, **kw: '{"reply": "回答。", "cited_sources": [0, 99]}',
    )

    reply, sources, _ = agent.chat("测试", session_id="t1")
    assert "回答。" in reply
    assert "【参考史料】" in reply and "[1]《甲书》" in reply
    assert [s["title"] for s in sources] == ["甲书"]

    conversation_memory.clear_all()
