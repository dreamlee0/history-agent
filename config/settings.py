"""
配置管理 - 支持 DeepSeek/智谱等 OpenAI 兼容接口
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # LLM (OpenAI兼容接口，可接智谱/DeepSeek/OpenAI等)
    llm_api_key: str = Field(default="", env="LLM_API_KEY")
    llm_base_url: str = Field(
        default="https://api.deepseek.com",
        env="LLM_BASE_URL",
    )
    llm_model: str = Field(default="deepseek-v4-flash", env="LLM_MODEL")

    # Embedding配置 (本地 HuggingFace 模型，免费无需 API Key)
    embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5", env="EMBEDDING_MODEL"
    )

    # 向量数据库
    vector_db_path: str = Field(
        default="./data/vector_db",
        env="VECTOR_DB_PATH"
    )

    # Agent
    # temperature: 闲聊/无史料命中时使用；temperature_factual: RAG 命中史料时使用。
    # 史实问答需要低温度减少幻觉（默认 0.3），闲聊可保持较高的 0.8 更自然。
    temperature: float = 0.8
    temperature_factual: float = 0.3
    # 注入 LLM 上下文的历史消息条数上限（可经环境变量 MAX_HISTORY 覆盖）
    max_history: int = Field(default=10, env="MAX_HISTORY")
    verbose: bool = True

    # RAG配置
    rag_top_k: int = 3
    rag_enabled: bool = True
    # 人物过滤相关性阈值：按人物过滤的最优结果距离若明显劣于全局最优
    # （> 该倍数），判定问题与本人物无关，退回全局检索（防跨人物污染）。
    # 默认值 1.20 由 scripts/evaluate_retrieval.py 在标注评测集
    # （data/eval/retrieval_eval.json，26 条）上的阈值扫描数据支撑：
    # 1.20 决策正确率 0.962 > 1.25 的 0.923（1.25 时"隋文帝问大运河"会把
    # 文帝自传当史料注入，ratio=1.209 恰好漏过），可在 .env 覆盖重调。
    filtered_score_ratio: float = Field(default=1.20, env="FILTERED_SCORE_RATIO")

    # 检索模式："similarity"（纯相似度，默认）| "mmr"（最大边际相关重排）。
    # 默认保持纯相似度以不改变既有行为；史料规模扩大后可切换 mmr 提升
    # 召回多样性（MMR 检索已实现，见 VectorStoreManager.mmr_search）。
    retrieval_mode: str = Field(default="similarity", env="RETRIEVAL_MODE")

    # 数据库配置
    db_path: str = Field(default="./data/history_chat.db", env="DB_PATH")
    # 对话保留天数：超过该天数的对话由 scripts/cleanup_db.py 清理；
    # 0 表示不自动清理（默认，保持既有无限增长行为，由部署者显式开启）。
    conversation_retention_days: int = Field(
        default=0, env="CONVERSATION_RETENTION_DAYS"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
