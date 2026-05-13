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


def get_db() -> "DatabaseManager":
    """获取数据库管理器实例"""
    return DatabaseManager()


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

    def get_conversation(self, conversation_id: int) -> Optional[Dict]:
        """获取单个对话"""
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_conversation_time(self, conversation_id: int):
        """更新对话的最后活跃时间"""
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,),
            )

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

            total_messages = conn.execute(
                """SELECT COUNT(*) FROM messages m
                   JOIN conversations c ON m.conversation_id = c.id
                   WHERE c.session_id = ?""",
                (session_id,),
            ).fetchone()[0]

            # 最热门人物
            popular = conn.execute(
                """SELECT character_name, COUNT(*) as cnt
                   FROM conversations
                   WHERE session_id = ?
                   GROUP BY character_name
                   ORDER BY cnt DESC LIMIT 5""",
                (session_id,),
            ).fetchall()

            return {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "popular_characters": [
                    {"name": row[0], "count": row[1]} for row in popular
                ],
            }

    def search_messages(
        self, session_id: str, keyword: str, limit: int = 20
    ) -> List[Dict]:
        """搜索消息内容"""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """SELECT m.id, m.conversation_id, m.role, m.content, m.created_at,
                          c.character_name, c.title as conv_title
                   FROM messages m
                   JOIN conversations c ON m.conversation_id = c.id
                   WHERE c.session_id = ? AND m.content LIKE ?
                   ORDER BY m.created_at DESC LIMIT ?""",
                (session_id, f"%{keyword}%", limit),
            ).fetchall()
            return [dict(row) for row in rows]
