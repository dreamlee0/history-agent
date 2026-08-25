"""
历史人物对话系统（RAG 对话机器人） - 集成RAG知识检索 + SQLite持久化
支持知识溯源，回复时引用史料来源

说明：本项目本质是「检索增强(RAG)的对话应用」，不包含工具调用/规划/推理链，
因此模块文档统一表述为"历史人物对话系统 / RAG 对话机器人"而非"Agent"。
类名 HistoryCharacterAgent 予以保留，以兼容既有 import 与测试。
"""
from typing import List, Optional, Tuple
from dataclasses import dataclass
import time

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from config import get_settings
from src.characters import HistoricalCharacter, character_manager
from src.memory import conversation_memory
from src.logger import get_logger

logger = get_logger("history_agent")

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
    """历史人物对话系统（RAG 对话机器人） - 支持RAG知识增强 + 持久化"""

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
        """检索相关知识。

        按人物过滤优先，但会用相关性分数做兜底判断：
        - 过滤结果明显劣于全局最优（如用户问的是别人）→ 退回全局检索；
        - 过滤结果为空 → 退回全局检索。
        避免把当事人自己的传记误当"相关史料"注入，导致引用错误。
        """
        if not self.vector_store:
            return None

        try:
            # 1) 按人物过滤检索（带分数，距离越小越相关）
            filtered = self.vector_store.search_by_character_with_score(
                query, self.character.name, k=k
            )
            # 2) 全局检索（带分数），用于相关性对比与兜底
            global_results = self.vector_store.similarity_search_with_score(
                query, k=k
            )

            docs = None
            if filtered:
                best_filtered = filtered[0][1]
                best_global = global_results[0][1] if global_results else None
                # 过滤结果不比全局最优差太多时，保留人物聚焦的结果
                if self._should_use_filtered(best_filtered, best_global):
                    docs = [d for d, _ in filtered]

            if docs is None and global_results:
                docs = [d for d, _ in global_results]

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
            logger.warning(f"RAG检索错误: {e}")
            return None

    def _should_use_filtered(self, best_filtered: float, best_global: Optional[float]) -> bool:
        """判断按人物过滤的结果是否值得保留（分数为距离，越小越相关）。

        过滤结果明显劣于全局最优（best_filtered > best_global * filtered_score_ratio）
        时，判定用户问题与本人物无关，退回全局检索，避免把当事人自己的传记
        误当"相关史料"注入。阈值来自 Settings.filtered_score_ratio，可配置。
        """
        if best_global is None:
            return True
        return best_filtered <= best_global * self.settings.filtered_score_ratio

    def _build_system_prompt(self, rag_context: Optional[RAGContext] = None) -> str:
        """构建系统提示词"""
        base_prompt = self.character.get_system_prompt()

        if rag_context:
            base_prompt += f"""

## 相关历史史料
以下是从史料库中检索到的相关信息：

{rag_context.context_text}

## 史料使用规则（必须严格遵守）
1. 【以史料为准】优先依据上面史料回答；史料已明确记载的内容，直接采用，不得随意增删或虚构细节。
2. 【禁止编造】史料未记载的内容，请明确说明"此事史料记载有限，未有详载"，不得为了角色扮演而编造史实、年份、数字或文献。
3. 【引用受限于史料】末尾的【参考史料】只能从上面列出的史料中选取，严禁引用史料列表中不存在的文献名称。
4. 【角色与事实平衡】可保持人物口吻与性格，但历史事实必须准确；若问及与本人物无关或超出本人时代之事，依据史料客观回答。

## 引用格式要求
回答时请在末尾添加引用标注，格式如：
【参考史料】[1]《标题》- 来源
"""
        else:
            base_prompt += """

## 回答约束
本次检索未获取到相关史料。请基于可靠的历史常识回答，保持人物口吻；
若不确定，请如实说明"此事史料记载有限"，切勿编造文献出处或具体数字。
"""
        return base_prompt

    @staticmethod
    def _is_retryable_error(e: Exception) -> bool:
        """判断错误是否属于瞬时性错误（值得重试）。

        为什么需要区分：对 4xx（400/401/403/404 等确定性错误）重试毫无意义，
        只会放大延迟与成本；只有网络连接/超时、5xx 服务端错误、429 限流
        这类瞬时错误才值得退避重试。注意要把 429 归入可重试（限流是暂时的）。
        """
        import openai
        if isinstance(
            e, (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError)
        ):
            return True
        status = getattr(e, "status_code", None)
        if isinstance(status, int):
            return status >= 500 or status == 429
        # 非 openai 异常：按网络错误关键字兜底判断
        msg = str(e).lower()
        return "connection" in msg or "timeout" in msg

    def _call_api_with_retry(
        self,
        messages: list,
        max_retries: int = 3,
        temperature: Optional[float] = None,
    ) -> str:
        """带重试机制的 API 调用。

        temperature 为 None 时使用 settings.temperature；
        史实问答（有 RAG 史料命中）时应传 settings.temperature_factual。
        仅对瞬时错误重试（见 _is_retryable_error），4xx 立即抛出；
        返回内容为空（None/空白串）时重试一次，仍为空则抛带提示的异常，
        避免上层把 None 直接拼进 f-string 或写入 DB。
        """
        if temperature is None:
            temperature = self.settings.temperature

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.settings.llm_model,
                    messages=messages,
                    temperature=temperature,
                )
            except Exception as e:
                error_msg = str(e)
                if not self._is_retryable_error(e):
                    # 确定性错误（4xx 等）：重试无意义，立即抛出
                    raise Exception(f"API调用失败: {error_msg}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    time.sleep(wait_time)
                    continue
                # 最后一次重试也失败（瞬时错误持续存在）
                if "Connection" in error_msg or "timeout" in error_msg.lower():
                    raise Exception(f"API连接失败，请检查网络或API Key配置。错误: {error_msg}")
                elif "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower():
                    raise Exception(f"API Key无效或未配置。请在Streamlit Cloud的Secrets中设置LLM_API_KEY")
                else:
                    raise Exception(f"API调用失败: {error_msg}")

            content = response.choices[0].message.content
            if content is None or not content.strip():
                # 模型返回空内容：再试一次（可能是瞬时异常），仍空则明确报错
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise Exception("模型返回了空内容，请重试")
            return content

    def chat(
        self,
        user_input: str,
        session_id: str = "default",
        conversation_id: Optional[int] = None,
    ) -> Tuple[str, List[dict], int]:
        """
        对话
        返回: (回复内容, 引用来源列表, conversation_id)

        session_id 用于数据库对话归属（如浏览器会话）；内存记忆按
        "会话:人物" 复合键隔离，避免多用户、多人物之间的上下文串扰。
        """
        # 内存记忆键：会话 + 人物，双重隔离
        mem_key = f"{session_id}:{self.character.name}"

        # 如果没有 conversation_id，创建新对话
        if conversation_id is None and self.db:
            conversation_id = self.db.create_conversation(
                session_id=session_id,
                character_name=self.character.name,
                title=user_input[:30] + ("..." if len(user_input) > 30 else ""),
            )

        # 获取历史消息（从内存或数据库）
        history = conversation_memory.get_messages(mem_key)
        if not history and conversation_id and self.db:
            # 从数据库恢复历史
            db_messages = self.db.get_messages(conversation_id)
            conversation_memory.load_from_db(mem_key, db_messages)
            history = conversation_memory.get_messages(mem_key)

        # 保存用户消息（记录 id，API 失败时回滚，见下方 except）
        user_msg_id = None
        if self.db and conversation_id:
            user_msg_id = self.db.add_message(conversation_id, "user", user_input)

        # RAG检索
        rag_context = self._retrieve_knowledge(user_input)

        # 构建消息列表
        messages = []
        system_prompt = self._build_system_prompt(rag_context)
        messages.append({"role": "system", "content": system_prompt})

        for msg in history:
            if hasattr(msg, 'content'):
                # 用 isinstance 判定角色（比 __class__.__name__ 字符串比较更可靠，
                # 且兼容子类实例）
                role = "user" if isinstance(msg, HumanMessage) else "assistant"
                messages.append({"role": role, "content": msg.content})

        messages.append({"role": "user", "content": user_input})

        # 调用 API（带重试）。有 RAG 史料命中时用更低的 factual 温度
        # 以贴近史实、减少编造；无史料（闲聊/常识）用默认温度更自然。
        temperature = (
            self.settings.temperature_factual
            if rag_context
            else self.settings.temperature
        )
        try:
            result = self._call_api_with_retry(messages, temperature=temperature)
        except Exception:
            # 回滚刚写入的用户消息，避免"有问无答"的孤儿消息留在对话里：
            # 否则用户重试时，该问题会被当作已答复内容再次注入上下文，
            # 造成重复提问、上下文错乱。
            if user_msg_id is not None:
                self.db.delete_message(user_msg_id)
            raise

        # 保存助手消息
        sources = rag_context.sources if rag_context else []
        if self.db and conversation_id:
            self.db.add_message(conversation_id, "assistant", result, sources)

        # 更新内存记忆
        conversation_memory.add_message(mem_key, "user", user_input)
        conversation_memory.add_message(mem_key, "assistant", result)

        return result, sources, conversation_id

    def clear_memory(self, session_id: str = "default"):
        """清空对话记忆"""
        conversation_memory.clear(f"{session_id}:{self.character.name}")

    def load_history(self, conversation_id: int, session_id: str):
        """从数据库加载历史对话到内存"""
        if self.db:
            db_messages = self.db.get_messages(conversation_id)
            conversation_memory.load_from_db(
                f"{session_id}:{self.character.name}", db_messages
            )


class AgentManager:
    """对话机器人管理器（按人物缓存 HistoryCharacterAgent 实例）"""

    def __init__(self, vector_store=None, db_manager=None):
        self.vector_store = vector_store
        self.db = db_manager
        self._agents: dict[str, HistoryCharacterAgent] = {}

    def get_agent(self, character_name: str) -> Optional[HistoryCharacterAgent]:
        """获取或创建对话机器人"""
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
