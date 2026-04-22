"""
历史人物对话Agent - 集成RAG知识检索
支持知识溯源，回复时引用史料来源
"""
from typing import List, Optional, Tuple
from dataclasses import dataclass

from langchain_core.documents import Document

from config import get_settings
from src.characters import HistoricalCharacter, character_manager
from src.memory import conversation_memory

# 智谱AI SDK
try:
    from zhipuai import ZhipuAI
    HAS_ZHIPU = True
except ImportError:
    HAS_ZHIPU = False


@dataclass
class RAGContext:
    """RAG检索上下文"""
    query: str
    documents: List[Document]
    context_text: str
    sources: List[dict]


class HistoryCharacterAgent:
    """历史人物对话Agent - 支持RAG知识增强"""

    def __init__(
        self,
        character: HistoricalCharacter,
        vector_store=None,
    ):
        self.settings = get_settings()
        self.character = character
        self.vector_store = vector_store

        if not HAS_ZHIPU:
            raise ImportError("请安装智谱AI SDK: pip install zhipuai")

        # 添加超时设置，适应云端环境
        self.client = ZhipuAI(
            api_key=self.settings.zhipu_api_key,
            timeout=60.0,  # 60秒超时
        )

    def _retrieve_knowledge(self, query: str, k: int = 3) -> Optional[RAGContext]:
        """检索相关知识"""
        if not self.vector_store:
            return None

        try:
            # 先搜索与当前人物相关的知识
            docs = self.vector_store.search_by_character(
                query, self.character.name, k=k
            )

            # 如果没找到，进行通用搜索
            if not docs:
                docs = self.vector_store.similarity_search(query, k=k)

            if not docs:
                return None

            # 构建上下文文本
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

    def chat(
        self,
        user_input: str,
        session_id: str = "default",
    ) -> Tuple[str, List[dict]]:
        """
        对话
        返回: (回复内容, 引用来源列表)
        """
        # 获取历史消息
        history = conversation_memory.get_messages(session_id)

        # RAG检索
        rag_context = self._retrieve_knowledge(user_input)

        # 构建消息列表
        messages = []

        # 系统提示
        system_prompt = self._build_system_prompt(rag_context)
        messages.append({"role": "system", "content": system_prompt})

        # 历史对话
        for msg in history:
            if hasattr(msg, 'content'):
                role = "user" if msg.__class__.__name__ == "HumanMessage" else "assistant"
                messages.append({"role": role, "content": msg.content})

        # 当前输入
        messages.append({"role": "user", "content": user_input})

        # 调用智谱AI
        try:
            response = self.client.chat.completions.create(
                model=self.settings.zhipu_model,
                messages=messages,
                temperature=self.settings.temperature,
            )
            result = response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            if "Connection" in error_msg or "timeout" in error_msg.lower():
                raise Exception(f"API连接失败，请检查网络或API Key配置。错误: {error_msg}")
            elif "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower():
                raise Exception(f"API Key无效或未配置。请在Streamlit Cloud的Secrets中设置ZHIPU_API_KEY")
            else:
                raise Exception(f"API调用失败: {error_msg}")

        # 保存记忆
        conversation_memory.add_message(session_id, "user", user_input)
        conversation_memory.add_message(session_id, "assistant", result)

        # 返回回复和来源
        sources = rag_context.sources if rag_context else []
        return result, sources

    def clear_memory(self, session_id: str = "default"):
        """清空对话记忆"""
        conversation_memory.clear(session_id)


class AgentManager:
    """Agent管理器"""

    def __init__(self, vector_store=None):
        self.vector_store = vector_store
        self._agents: dict[str, HistoryCharacterAgent] = {}

    def get_agent(self, character_name: str) -> Optional[HistoryCharacterAgent]:
        """获取或创建Agent"""
        if character_name in self._agents:
            return self._agents[character_name]

        character = character_manager.get_character(character_name)
        if not character:
            return None

        agent = HistoryCharacterAgent(character, self.vector_store)
        self._agents[character_name] = agent
        return agent

    def list_characters(self) -> List[str]:
        """列出所有可用人物"""
        return character_manager.list_names()

    def set_vector_store(self, vector_store):
        """设置向量存储"""
        self.vector_store = vector_store
        # 清除现有agent，使其重新创建时使用新的向量存储
        self._agents.clear()
