"""pytest 全局配置"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest


@pytest.fixture(scope="session")
def vector_store():
    """可用的向量库实例；本地未缓存 Embedding 模型时跳过相关测试。

    注意：不要在此处设置 HF_HUB_OFFLINE —— vector_store 内部会
    自动把已缓存的模型解析为本地快照路径（见 _resolve_embedding_model）。
    """
    from src.retrievers.vector_store import (
        VectorStoreManager,
        _resolve_embedding_model,
    )

    resolved = _resolve_embedding_model()
    if not Path(resolved).exists():
        pytest.skip("本地未缓存 Embedding 模型，跳过需要 embedding 的测试")

    vs = VectorStoreManager()
    assert vs.get_document_count() > 0, "向量库为空，请先运行 scripts/build_vector_db.py"
    return vs
