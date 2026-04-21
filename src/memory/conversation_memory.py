"""
对话记忆管理
"""
from typing import List, Dict, Optional
from collections import deque

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class ConversationMemory:
    """对话记忆管理器"""

    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self._memories: Dict[str, deque] = {}  # session_id -> messages

    def _get_session_memory(self, session_id: str) -> deque:
        """获取会话记忆"""
        if session_id not in self._memories:
            self._memories[session_id] = deque(maxlen=self.max_history)
        return self._memories[session_id]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ):
        """添加消息"""
        memory = self._get_session_memory(session_id)
        if role == "user":
            memory.append(HumanMessage(content=content))
        else:
            memory.append(AIMessage(content=content))

    def get_messages(self, session_id: str) -> List[BaseMessage]:
        """获取会话消息列表"""
        memory = self._get_session_memory(session_id)
        return list(memory)

    def get_history_string(self, session_id: str) -> str:
        """获取历史对话字符串"""
        messages = self.get_messages(session_id)
        history = []
        for msg in messages:
            role = "用户" if isinstance(msg, HumanMessage) else "我"
            history.append(f"{role}: {msg.content}")
        return "\n".join(history)

    def clear(self, session_id: str):
        """清空会话记忆"""
        if session_id in self._memories:
            self._memories[session_id].clear()

    def clear_all(self):
        """清空所有记忆"""
        self._memories.clear()


# 全局记忆管理器
conversation_memory = ConversationMemory()
