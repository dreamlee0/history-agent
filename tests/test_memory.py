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
        # （chat 会传入 temperature 关键字参数，mock 需兼容）
        monkeypatch.setattr(
            a, "_call_api_with_retry", lambda messages, **kwargs: "（模拟回复）"
        )
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


def test_api_failure_rolls_back_user_message(make_agent, monkeypatch):
    """回归：API 调用失败时，刚写入 DB 的用户消息必须回滚。

    否则对话里会残留"有问无答"的孤儿消息，用户重试时该问题会被当作
    已答复内容再次注入 LLM 上下文，造成重复提问与上下文错乱。
    """
    import tempfile
    from pathlib import Path
    from src.database.db import DatabaseManager

    a = make_agent("李白")
    with tempfile.TemporaryDirectory() as tmp:
        a.db = DatabaseManager(db_path=str(Path(tmp) / "test.db"))

        def _boom(messages, **kwargs):
            raise Exception("API挂")

        monkeypatch.setattr(a, "_call_api_with_retry", _boom)

        with pytest.raises(Exception, match="API挂"):
            a.chat("你好", session_id="sessX")

        convs = a.db.get_conversations("sessX", "李白")
        assert len(convs) == 1, "应创建一次对话"
        assert a.db.get_messages(convs[0]["id"]) == [], "API 失败后不应残留用户消息"
