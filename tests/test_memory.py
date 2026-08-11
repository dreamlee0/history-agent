"""会话记忆隔离测试：composite key = f"{session_id}:{character.name}"。

防止多角色会话互相串记忆，以及同角色不同浏览器会话串记。
不触发真实 API 调用（monkeypatch _call_api_with_retry）。
"""
import pytest

from src.memory import conversation_memory


@pytest.fixture(autouse=True)
def _clean_memory():
    """每个用例前清空全局记忆，避免用例间污染"""
    conversation_memory.clear_all()
    yield


@pytest.fixture
def make_agent(monkeypatch):
    from config import get_settings
    from src.characters import character_manager
    from src.agents import HistoryCharacterAgent

    def _make(name):
        a = HistoryCharacterAgent.__new__(HistoryCharacterAgent)
        a.settings = get_settings()
        a.character = character_manager.get_character(name)
        a.vector_store = None
        a.db = None  # 绕过 __init__，需手动补齐属性
        # 用假回复替代真实 API 调用
        monkeypatch.setattr(a, "_call_api_with_retry", lambda messages: "（模拟回复）")
        return a

    return _make


def test_composite_key_includes_character(make_agent):
    """同一 session 下不同角色，记忆 key 必须互不相同（不串记）"""
    a = make_agent("李白")
    a.chat("我是李白", session_id="sess1")
    b = make_agent("杜甫")
    b.chat("我是杜甫", session_id="sess1")

    li_msgs = conversation_memory.get_messages("sess1:李白")
    du_msgs = conversation_memory.get_messages("sess1:杜甫")
    assert li_msgs, "李白记忆未写入"
    assert du_msgs, "杜甫记忆未写入"
    assert "李白" in li_msgs[0].content and "杜甫" in du_msgs[0].content


def test_same_character_different_session_isolated(make_agent):
    """同一角色不同浏览器会话不串记"""
    a1 = make_agent("李白")
    a1.chat("记住我喜欢酒", session_id="sessA")
    a2 = make_agent("李白")
    a2.chat("记住我喜欢剑", session_id="sessB")

    msgs_a = conversation_memory.get_messages("sessA:李白")
    msgs_b = conversation_memory.get_messages("sessB:李白")
    assert "喜欢酒" in msgs_a[0].content
    assert "喜欢剑" in msgs_b[0].content
    assert "喜欢酒" not in msgs_b[0].content


def test_clear_memory_uses_composite_key(make_agent):
    """clear_memory 只清当前 session+角色，不动其它会话"""
    a1 = make_agent("李白")
    a1.chat("记住我喜欢酒", session_id="sessA")
    a1.clear_memory(session_id="sessA")

    # sessA 已被清空
    assert conversation_memory.get_messages("sessA:李白") == []

    # 另一会话不受影响
    a2 = make_agent("李白")
    a2.chat("记住我喜欢剑", session_id="sessB")
    assert conversation_memory.get_messages("sessB:李白") != []
