"""
配置管理 - 支持智谱AI
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
        default="https://open.bigmodel.cn/api/paas/v4",
        env="LLM_BASE_URL",
    )
    llm_model: str = Field(default="glm-4-flash", env="LLM_MODEL")

    # Embedding配置 (本地 HuggingFace 模型，免费无需 API Key)
    embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5", env="EMBEDDING_MODEL"
    )

    # 向量数据库
    vector_db_path: str = Field(
        default="./data/vector_db",
        env="VECTOR_DB_PATH"
    )

    # 应用
    app_title: str = Field(default="历史人物对话", env="APP_TITLE")

    # Agent
    temperature: float = 0.8
    max_history: int = 10
    verbose: bool = True

    # RAG配置
    rag_top_k: int = 3
    rag_enabled: bool = True

    # 数据库配置
    db_path: str = Field(default="./data/history_chat.db", env="DB_PATH")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
