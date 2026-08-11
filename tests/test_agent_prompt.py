"""System prompt 防幻觉约束测试（不触发真实 API 调用）"""
import pytest

from src.characters import character_manager


@pytest.fixture
def agent():
    """用 __new__ 绕过 __init__，避免初始化需要真实 API Key。"""
    from config import get_settings
    from src.agents import HistoryCharacterAgent

    a = HistoryCharacterAgent.__new__(HistoryCharacterAgent)
    a.settings = get_settings()
    a.character = character_manager.get_character("李白")
    return a


def _rag_context():
    """构造一个最小可用的 RAGContext"""
    from langchain_core.documents import Document
    from src.agents.history_agent import RAGContext

    doc = Document(
        page_content="李白，字太白，唐代著名诗人。",
        metadata={
            "title": "内置知识库 - 李白",
            "source": "《新唐书·李白传》",
            "url": "",
            "character": "李白",
            "category": "biography",
        },
    )
    return RAGContext(
        query="介绍你自己",
        documents=[doc],
        context_text=(
            "[史料1] 来源: 《新唐书·李白传》 - 内置知识库 - 李白\n"
            "李白，字太白，唐代著名诗人。"
        ),
        sources=[{
            "index": 1,
            "title": "内置知识库 - 李白",
            "source": "《新唐书·李白传》",
            "url": "",
            "character": "李白",
        }],
    )


def test_prompt_has_grounding_rules(agent):
    """有 RAG 上下文时，prompt 必须包含硬性史实约束"""
    prompt = agent._build_system_prompt(_rag_context())
    assert "禁止编造" in prompt
    assert "以史料为准" in prompt


def test_prompt_limits_citation_to_sources(agent):
    """引用必须受限于提供的史料，不能自由发挥"""
    prompt = agent._build_system_prompt(_rag_context())
    assert "只能从" in prompt and "史料" in prompt


def test_prompt_no_rag_branch_forbids_fabrication(agent):
    """无 RAG 上下文时，明确禁止编造文献出处/具体数字"""
    prompt = agent._build_system_prompt(None)
    assert "切勿编造" in prompt


def test_prompt_role_and_fact_balance(agent):
    """角色扮演与事实之间必须平衡：'史料' 约束与 '人物口吻' 共存"""
    prompt = agent._build_system_prompt(_rag_context())
    assert "史料" in prompt
    assert "口吻" in prompt or "性格" in prompt
