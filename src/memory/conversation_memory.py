"""
对话记忆管理 - 支持内存缓存 + SQLite 持久化
"""
import threading
from typing import List, Dict, Optional
from collections import deque

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from config import get_settings


class ConversationMemory:
    """对话记忆管理器（内存缓存，用于 LLM 上下文）"""

    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self._memories: Dict[str, deque] = {}  # session_id -> messages
        # 进程内多线程安全：Streamlit 会并发 rerun，同一进程内的读写需互斥，
        # 防止两个请求同时操作同一个 deque 造成数据竞争。
        self._lock = threading.RLock()

    def _get_session_memory(self, session_id: str) -> deque:
        """获取会话记忆"""
        if session_id not in self._memories:
            self._memories[session_id] = deque(maxlen=self.max_history)
        return self._memories[session_id]

    def add_message(self, session_id: str, role: str, content: str):
        """添加消息"""
        with self._lock:
            memory = self._get_session_memory(session_id)
            if role == "user":
                memory.append(HumanMessage(content=content))
            else:
                memory.append(AIMessage(content=content))

    def get_messages(self, session_id: str) -> List[BaseMessage]:
        """获取会话消息列表"""
        with self._lock:
            memory = self._get_session_memory(session_id)
            return list(memory)

    def load_from_db(self, session_id: str, messages: List[Dict]):
        """从数据库加载历史消息到内存"""
        with self._lock:
            memory = self._get_session_memory(session_id)
            memory.clear()
            # 只加载最近的 max_history 条
            for msg in messages[-self.max_history:]:
                if msg["role"] == "user":
                    memory.append(HumanMessage(content=msg["content"]))
                else:
                    memory.append(AIMessage(content=msg["content"]))

    def trim_history(self, session_id: str, keep: Optional[int] = None) -> None:
        """裁剪会话历史到最近 keep 条（默认 max_history）。

        当前策略为「最近 N 条」滑动窗口（deque 天然截断），暂无压缩；
        若后续要支持长会话，可在此接入「滚动摘要」：把较早的轮次交给
        LLM 生成一句话摘要，仅保留摘要 + 最近 N 条原文，避免超出上下文窗口。
        """
        keep = keep or self.max_history
        with self._lock:
            memory = self._get_session_memory(session_id)
            if len(memory) > keep:
                # deque 只能从左侧弹出，转为列表裁剪后再重建
                items = list(memory)[-keep:]
                memory.clear()
                memory.extend(items)

    def clear(self, session_id: str):
        """清空会话记忆"""
        with self._lock:
            if session_id in self._memories:
                self._memories[session_id].clear()

    def clear_all(self):
        """清空所有记忆"""
        with self._lock:
            self._memories.clear()


# 全局记忆管理器（进程内单例）。
# 注意：内存记忆只在当前进程内可靠；多进程部署（gunicorn 多 worker、
# Streamlit 多实例）时各进程内存互不可见，上下文恢复应以 SQLite 为准，
# 见 src/database/db.py::DatabaseManager.restore_recent_messages 的正确用法。
conversation_memory = ConversationMemory(max_history=get_settings().max_history)
