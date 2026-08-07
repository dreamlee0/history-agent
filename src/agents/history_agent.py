"""
历史人物对话Agent - 集成RAG知识检索 + SQLite持久化
支持知识溯源，回复时引用史料来源
"""
from typing import List, Optional, Tuple
from dataclasses import dataclass
import time

from langchain_core.documents import Document

from config import get_settings
from src.characters import HistoricalCharacter, character_manager
from src.memory import conversation_memory

# OpenAI兼容 SDK (可接智谱/DeepSeek/OpenAI等)
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class RAGContext:
    """RAG检索上下文"""
    query: str
    documents: List[Document]
    context_text: str
    sources: List[dict]


class HistoryCharacterAgent:
    """历史人物对话Agent - 支持RAG知识增强 + 持久化"""

    def __init__(
        self,
        character: HistoricalCharacter,
        vector_store=None,
        db_manager=None,
    ):
        self.settings = get_settings()
        self.character = character
        self.vector_store = vector_store
        self.db = db_manager

        if not HAS_OPENAI:
            raise ImportError("请安装 openai SDK: pip install openai")

        if not self.settings.llm_api_key:
            raise ValueError("LLM_API_KEY 未配置，请在环境变量或 Streamlit Secrets 中设置")

        self.client = OpenAI(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            timeout=60.0,
        )

    def _retrieve_knowledge(self, query: str, k: int = 3) -> Optional[RAGContext]:
        """检索相关知识"""
        if not self.vector_store:
            return None

        try:
            docs = self.vector_store.search_by_character(
                query, self.character.name, k=k
            )

            if not docs:
                docs = self.vector_store.similarity_search(query, k=k)

            if not docs:
                return None

            context_parts = []
            sources = []
            for i, doc in enumerate(docs, 1):
                source_info = {
                    "index": i,
                    "title": doc.metadata.get("title", "未知"),
                    "source": doc.metadata.get("source", "未知"),
                    "url": doc.metadata.get("url", ""),
                    "character": doc.metadata.get("character", ""),
                }
                sources.append(source_info)

                context_parts.append(
                    f"[史料{i}] 来源: {source_info['source']} - {source_info['title']}\n"
                    f"{doc.page_content}"
                )

            return RAGContext(
                query=query,
                documents=docs,
                context_text="\n\n".join(context_parts),
                sources=sources
            )

        except Exception as e:
            print(f"RAG检索错误: {e}")
            return None

    def _build_system_prompt(self, rag_context: Optional[RAGContext] = None) -> str:
        """构建系统提示词"""
        base_prompt = self.character.get_system_prompt()

        if rag_context:
            base_prompt += f"""

## 相关历史史料
以下是从史料中检索到的相关信息，请参考这些内容回答，并在回答末尾标注引用来源：

{rag_context.context_text}

## 引用格式要求
回答时请在末尾添加引用标注，格式如：
【参考史料】[1]《标题》- 来源

如果史料内容与问题相关，请优先使用史料中的信息。如果史料与问题无关，可以忽略。
"""
        return base_prompt

    def _call_api_with_retry(self, messages: list, max_retries: int = 3) -> str:
        """带重试机制的 API 调用"""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.settings.llm_model,
                    messages=messages,
                    temperature=self.settings.temperature,
                )
                return response.choices[0].message.content
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    time.sleep(wait_time)
                    continue
                # 最后一次重试失败
                if "Connection" in error_msg or "timeout" in error_msg.lower():
                    raise Exception(f"API连接失败，请检查网络或API Key配置。错误: {error_msg}")
                elif "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower():
                    raise Exception(f"API Key无效或未配置。请在Streamlit Cloud的Secrets中设置LLM_API_KEY")
                else:
                    raise Exception(f"API调用失败: {error_msg}")

    def chat(
        self,
        user_input: str,
        session_id: str = "default",
        conversation_id: Optional[int] = None,
    ) -> Tuple[str, List[dict], int]:
        """
        对话
        返回: (回复内容, 引用来源列表, conversation_id)
        """
        # 如果没有 conversation_id，创建新对话
        if conversation_id is None and self.db:
            conversation_id = self.db.create_conversation(
                session_id=session_id,
                character_name=self.character.name,
                title=user_input[:30] + ("..." if len(user_input) > 30 else ""),
            )

        # 获取历史消息（从内存或数据库）
        history = conversation_memory.get_messages(session_id)
        if not history and conversation_id and self.db:
            # 从数据库恢复历史
            db_messages = self.db.get_messages(conversation_id)
            conversation_memory.load_from_db(session_id, db_messages)
            history = conversation_memory.get_messages(session_id)

        # 保存用户消息
        if self.db and conversation_id:
            self.db.add_message(conversation_id, "user", user_input)

        # RAG检索
        rag_context = self._retrieve_knowledge(user_input)

        # 构建消息列表
        messages = []
        system_prompt = self._build_system_prompt(rag_context)
        messages.append({"role": "system", "content": system_prompt})

        for msg in history:
            if hasattr(msg, 'content'):
                role = "user" if msg.__class__.__name__ == "HumanMessage" else "assistant"
                messages.append({"role": role, "content": msg.content})

        messages.append({"role": "user", "content": user_input})

        # 调用 API（带重试）
        result = self._call_api_with_retry(messages)

        # 保存助手消息
        sources = rag_context.sources if rag_context else []
        if self.db and conversation_id:
            self.db.add_message(conversation_id, "assistant", result, sources)

        # 更新内存记忆
        conversation_memory.add_message(session_id, "user", user_input)
        conversation_memory.add_message(session_id, "assistant", result)

        return result, sources, conversation_id

    def clear_memory(self, session_id: str = "default"):
        """清空对话记忆"""
        conversation_memory.clear(session_id)

    def load_history(self, conversation_id: int, session_id: str):
        """从数据库加载历史对话到内存"""
        if self.db:
            db_messages = self.db.get_messages(conversation_id)
            conversation_memory.load_from_db(session_id, db_messages)


class AgentManager:
    """Agent管理器"""

    def __init__(self, vector_store=None, db_manager=None):
        self.vector_store = vector_store
        self.db = db_manager
        self._agents: dict[str, HistoryCharacterAgent] = {}

    def get_agent(self, character_name: str) -> Optional[HistoryCharacterAgent]:
        """获取或创建Agent"""
        if character_name in self._agents:
            return self._agents[character_name]

        character = character_manager.get_character(character_name)
        if not character:
            return None

        agent = HistoryCharacterAgent(character, self.vector_store, self.db)
        self._agents[character_name] = agent
        return agent

    def list_characters(self) -> List[str]:
        """列出所有可用人物"""
        return character_manager.list_names()

    def set_vector_store(self, vector_store):
        """设置向量存储"""
        self.vector_store = vector_store
        self._agents.clear()
