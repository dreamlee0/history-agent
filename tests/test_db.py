"""SQLite 恢复/清理行为测试（真实临时库，不触网、不碰生产数据）。"""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.database.db import DatabaseManager


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmp:
        yield DatabaseManager(db_path=str(Path(tmp) / "test.db"))


class FakeMemory:
    """记录 load_from_db 收到的消息，模拟内存记忆。"""

    def __init__(self):
        self.loaded = None

    def load_from_db(self, mem_key, messages):
        self.loaded = messages


def test_restore_specific_conversation(db):
    """指定 conversation_id 时从该对话恢复（chat() 续聊路径）。"""
    c1 = db.create_conversation("s1", "李白")
    c2 = db.create_conversation("s1", "李白")
    db.add_message(c1, "user", "旧对话")
    db.add_message(c2, "user", "新对话")
    mem = FakeMemory()
    n = db.restore_recent_messages("s1", "李白", mem, "k", conversation_id=c1)
    assert n == 1
    assert mem.loaded[0]["content"] == "旧对话"


def test_restore_most_recent_when_no_id(db):
    """未指定 conversation_id 时，恢复该会话+人物最近更新的对话。"""
    c1 = db.create_conversation("s1", "李白")
    c2 = db.create_conversation("s1", "李白")
    db.add_message(c1, "user", "旧")
    db.add_message(c2, "user", "新")
    # CURRENT_TIMESTAMP 仅秒级精度，同秒创建的两条对话顺序不确定；
    # 显式把 c2 的更新时间拨后 1 分钟，让"最近"确定。
    conn = sqlite3.connect(db.db_path)
    conn.execute(
        "UPDATE conversations SET updated_at = datetime('now','+1 minute') WHERE id = ?",
        (c2,),
    )
    conn.commit()
    conn.close()
    mem = FakeMemory()
    n = db.restore_recent_messages("s1", "李白", mem, "k")
    assert n == 1
    assert mem.loaded[0]["content"] == "新"


def test_restore_max_messages_limit(db):
    """只恢复最近 max_messages 条（内存有界，防止上下文无限增长）。"""
    c1 = db.create_conversation("s1", "李白")
    for i in range(5):
        db.add_message(c1, "user", f"msg{i}")
    mem = FakeMemory()
    n = db.restore_recent_messages("s1", "李白", mem, "k", max_messages=2, conversation_id=c1)
    assert n == 2
    assert [m["content"] for m in mem.loaded] == ["msg3", "msg4"]


def test_purge_old_conversations_cascades(db):
    """超过保留天数的对话连带消息一并删除；保留期内与禁用(0)不动。"""
    c1 = db.create_conversation("s1", "李白")
    c2 = db.create_conversation("s1", "李白")
    db.add_message(c1, "user", "很久以前的对话")
    db.add_message(c2, "user", "最近的对话")

    # 把 c1 的更新时间改成 400 天前，模拟久未更新
    conn = sqlite3.connect(db.db_path)
    conn.execute(
        "UPDATE conversations SET updated_at = datetime('now','-400 days') WHERE id = ?",
        (c1,),
    )
    conn.commit()
    conn.close()

    assert db.purge_old_conversations(0) == 0       # 禁用时不删
    assert db.purge_old_conversations(365) == 1     # 只删 c1
    assert [c["id"] for c in db.get_conversations("s1")] == [c2]
