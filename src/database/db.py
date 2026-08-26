"""
SQLite 数据库管理 - 对话持久化
轻量级实现，不依赖 SQLAlchemy
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from contextlib import contextmanager

# 数据库路径
DB_PATH = os.getenv("DB_PATH", "./data/history_chat.db")


def _ensure_db_dir(db_path: str):
    """确保数据库目录存在"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection(db_path: str = DB_PATH):
    """获取数据库连接（上下文管理器）"""
    _ensure_db_dir(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class DatabaseManager:
    """数据库管理器 - 封装所有 CRUD 操作"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with get_connection(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    character_name TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_conversations_session
                    ON conversations(session_id);
                CREATE INDEX IF NOT EXISTS idx_conversations_character
                    ON conversations(character_name);
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id);
            """)

    # ─── 对话管理 ───

    def create_conversation(
        self, session_id: str, character_name: str, title: str = ""
    ) -> int:
        """创建新对话，返回对话 ID"""
        if not title:
            title = f"与{character_name}的对话"
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO conversations (session_id, character_name, title)
                   VALUES (?, ?, ?)""",
                (session_id, character_name, title),
            )
            return cursor.lastrowid

    def get_conversations(
        self, session_id: str, character_name: Optional[str] = None, limit: int = 50
    ) -> List[Dict]:
        """获取对话列表"""
        with get_connection(self.db_path) as conn:
            if character_name:
                rows = conn.execute(
                    """SELECT id, session_id, character_name, title, created_at, updated_at
                       FROM conversations
                       WHERE session_id = ? AND character_name = ?
                       ORDER BY updated_at DESC LIMIT ?""",
                    (session_id, character_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, session_id, character_name, title, created_at, updated_at
                       FROM conversations
                       WHERE session_id = ?
                       ORDER BY updated_at DESC LIMIT ?""",
                    (session_id, limit),
                ).fetchall()
            return [dict(row) for row in rows]

    def delete_conversation(self, conversation_id: int) -> bool:
        """删除对话及其所有消息"""
        with get_connection(self.db_path) as conn:
            conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )
            cursor = conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
            return cursor.rowcount > 0

    # ─── 消息管理 ───

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        sources: Optional[List[Dict]] = None,
    ) -> int:
        """添加消息"""
        sources_json = json.dumps(sources, ensure_ascii=False) if sources else None
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO messages (conversation_id, role, content, sources_json)
                   VALUES (?, ?, ?, ?)""",
                (conversation_id, role, content, sources_json),
            )
            # 同时更新对话的活跃时间
            conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,),
            )
            return cursor.lastrowid

    def delete_message(self, message_id: int) -> bool:
        """删除单条消息"""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE id = ?", (message_id,)
            )
            return cursor.rowcount > 0

    def get_messages(self, conversation_id: int) -> List[Dict]:
        """获取对话的所有消息"""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, conversation_id, role, content, sources_json, created_at
                   FROM messages
                   WHERE conversation_id = ?
                   ORDER BY created_at ASC""",
                (conversation_id,),
            ).fetchall()
            result = []
            for row in rows:
                msg = dict(row)
                if msg["sources_json"]:
                    msg["sources"] = json.loads(msg["sources_json"])
                else:
                    msg["sources"] = []
                del msg["sources_json"]
                result.append(msg)
            return result

    # ─── 统计 ───

    def get_stats(self, session_id: str) -> Dict:
        """获取统计数据"""
        with get_connection(self.db_path) as conn:
            total_conversations = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]

            return {
                "total_conversations": total_conversations,
            }

    def restore_recent_messages(
        self,
        session_id: str,
        character_name: str,
        memory,
        mem_key: str,
        max_messages: int = 10,
        conversation_id: Optional[int] = None,
    ) -> int:
        """按 session_id+人物名 从 SQLite 恢复最近 N 条消息到内存记忆。

        为什么需要：内存记忆（conversation_memory）是进程内单例，多进程部署
        （如 gunicorn 多 worker / Streamlit 多实例）下各进程内存彼此独立、
        互不可见，不能依赖进程内记忆做跨进程上下文恢复；SQLite 才是唯一
        可靠来源。

        正确用法（多进程部署）：
            1. 会话开始时按当前 session_id+人物 调用本方法，把最近 N 条
               从 SQLite 恢复到当前进程的内存记忆，再交给 LLM 拼上下文；
            2. 每轮对话后照常写 SQLite（写库是持久的，进程无关）。
        这样任何进程都能从"冷内存"重建出最近上下文。

        conversation_id 传入时，从该指定对话恢复（chat() 携带 conversation_id
        续聊的场景）；缺省时恢复该 session+人物 最近更新的一条对话。

        返回恢复的消息条数（0 表示该会话尚无消息）。
        """
        with get_connection(self.db_path) as conn:
            if conversation_id is not None:
                row = conn.execute(
                    "SELECT id FROM conversations WHERE id = ?",
                    (conversation_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT id FROM conversations
                       WHERE session_id = ? AND character_name = ?
                       ORDER BY updated_at DESC LIMIT 1""",
                    (session_id, character_name),
                ).fetchone()
        if not row:
            return 0

        messages = self.get_messages(row["id"])[-max_messages:]
        memory.load_from_db(mem_key, messages)
        return len(messages)

    def purge_old_conversations(self, days: int) -> int:
        """删除超过 days 天未更新的对话及其消息，返回删除的对话数。

        为什么需要：对话表会无限增长，多用户长期使用后积累无价值的旧记录；
        提供按更新时间清理的策略（由 scripts/cleanup_db.py 或部署方定时调用）。
        依赖 messages 的外键 ON DELETE CASCADE，删对话即连带删消息。
        days <= 0 时视为禁用（不删除任何数据）。
        """
        if days <= 0:
            return 0
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """DELETE FROM conversations
                   WHERE updated_at < datetime('now', ?)""",
                (f"-{days} days",),
            )
            return cursor.rowcount
