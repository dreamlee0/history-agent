"""
配置管理 - 支持智谱AI
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # 智谱AI
    zhipu_api_key: str = Field(default="", env="ZHIPU_API_KEY")
    zhipu_model: str = Field(default="glm-4-flash", env="ZHIPU_MODEL")

    # Embedding配置 (使用智谱AI的embedding)
    embedding_model: str = Field(default="embedding-3", env="EMBEDDING_MODEL")

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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
