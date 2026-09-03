"""src 包。

刻意不做顶层 eager import：包初始化阶段一口气串起
characters → retrievers → memory → agents 的导入链（连带 langchain 等重模块），
在并发导入场景（Streamlit Cloud 冷启动时运行时线程与脚本线程同时穿过本包）
会触发 `_frozen_importlib._DeadlockError`（import 锁竞态死锁，
报错点即旧版第 5 行 `from .agents import ...`；本仓库可用
`python3 /tmp/import_stress.py` 复现，修复前多轮必现该错误）。

改为 PEP 562 惰性 `__getattr__`：包本身初始化零成本，真正导入推迟到
首次访问对应属性时才发生。`from src import X` 的既有用法保持不变
（实际仓库内无任何调用方依赖顶层再导出，均直接 `from src.子模块 import ...`）。
"""

# 惰性属性表：名字 -> (子模块名, 属性名)，仅首次访问时 import 对应子模块
_LAZY_EXPORTS = {
    "CharacterManager": ("characters", "CharacterManager"),
    "HistoricalCharacter": ("characters", "HistoricalCharacter"),
    "character_manager": ("characters", "character_manager"),
    "VectorStoreManager": ("retrievers", "VectorStoreManager"),
    "ConversationMemory": ("memory", "ConversationMemory"),
    "conversation_memory": ("memory", "conversation_memory"),
    "HistoryCharacterAgent": ("agents", "HistoryCharacterAgent"),
    "AgentManager": ("agents", "AgentManager"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        import importlib

        submodule, attr = _LAZY_EXPORTS[name]
        module = importlib.import_module(f".{submodule}", __name__)
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
