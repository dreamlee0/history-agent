"""引用可验证（grounding 硬化）测试：结构化 cited_sources 的解析与校验。

核心主张：模型自由生成的【参考史料】文本不可信（可能引用不存在的文献）；
改为要求模型输出 {reply, cited_sources:[索引]}，代码侧校验索引落在
本次检索集合内才渲染。本文件覆盖解析与校验逻辑本身。
"""
import pytest
from types import SimpleNamespace

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


class TestJsonModeWireup:
    """结构化引用高成功率的关键：_call_api_with_retry 从 API 层强制
    response_format=json_object，端点不支持时自动降级（不崩溃）。"""

    def _make_agent(self):
        from config import get_settings
        from src.characters import character_manager

        agent = HistoryCharacterAgent.__new__(HistoryCharacterAgent)
        agent.settings = get_settings()
        agent.character = character_manager.get_character("李白")
        agent.vector_store = None
        agent.db = None
        agent._json_mode = True
        agent._llm_backend = None
        return agent

    def _ok_response(self, content):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=None,
        )

    def test_unsupported_param_error_detection(self):
        # 400 + unknown parameter → 判定为"端点不支持 response_format"
        e1 = Exception("unknown parameter 'response_format'")
        e1.status_code = 400
        assert HistoryCharacterAgent._is_unsupported_param_error(e1) is True
        e2 = Exception("BadRequestError: invalid api key")
        e2.status_code = 400
        assert HistoryCharacterAgent._is_unsupported_param_error(e2) is False
        e3 = Exception("timeout")
        e3.status_code = 500
        assert HistoryCharacterAgent._is_unsupported_param_error(e3) is False

    def test_call_api_passes_response_format(self, monkeypatch):
        agent = self._make_agent()
        captured = {}

        def _create(**kwargs):
            captured.update(kwargs)
            return self._ok_response('{"reply": "hi", "cited_sources": [0]}')

        agent.client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )
        out = agent._call_api_with_retry(
            [{"role": "user", "content": "q"}], temperature=0.5
        )
        assert captured["response_format"] == {"type": "json_object"}
        assert out == '{"reply": "hi", "cited_sources": [0]}'

    def test_call_api_degrades_gracefully_when_unsupported(self, monkeypatch):
        agent = self._make_agent()
        calls = []

        def _create(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                err = Exception("unknown parameter 'response_format'")
                err.status_code = 400
                raise err
            return self._ok_response("普通回复")

        agent.client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )
        out = agent._call_api_with_retry(
            [{"role": "user", "content": "q"}], temperature=0.5
        )
        assert out == "普通回复"  # 不崩溃，正常返回
        assert calls[0]["response_format"] == {"type": "json_object"}
        assert "response_format" not in calls[1]  # 第二次降级不再传
        assert agent._json_mode is False  # 实例级标记已关闭

    def test_chat_retries_once_on_parse_failure_then_renders(self, monkeypatch):
        """解析失败 → 一次强 JSON 约束重试 → 成功渲染【参考史料】footer。

        回归点：json_object 下仍可能拿到"合法 JSON 但格式走样"的输出，
        必须有定向重试，而不是直接回退纯文本丢掉引用。
        """
        from config import get_settings
        from src.characters import character_manager
        from src.memory import conversation_memory
        from src.agents.history_agent import RAGContext
        from langchain_core.documents import Document

        agent = self._make_agent()
        fake_docs = [
            Document(
                page_content="内容A",
                metadata={"title": "甲书", "source": "s1", "url": "", "character": "李白"},
            )
        ]
        fake_sources = [
            {"index": 1, "title": "甲书", "source": "s1", "url": "", "character": "李白"}
        ]

        def _fake_retrieve(query, request_id=None):
            return RAGContext(
                query=query, documents=fake_docs,
                context_text="[史料1] 来源: s1 - 甲书\n内容A",
                sources=fake_sources,
            )

        monkeypatch.setattr(agent, "_retrieve_knowledge", _fake_retrieve)
        calls = {"n": 0}

        def _fake_api(messages, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return "（模型第一轮没按 JSON 输出）"
            return '{"reply": "依据甲书回答。", "cited_sources": [0]}'

        monkeypatch.setattr(agent, "_call_api_with_retry", _fake_api)

        reply, sources, _ = agent.chat("测试", session_id="t2")
        assert calls["n"] == 2  # 恰好重试一次
        assert "依据甲书回答。" in reply
        assert "【参考史料】" in reply
        assert [s["title"] for s in sources] == ["甲书"]

        conversation_memory.clear_all()


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
