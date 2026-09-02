"""端到端链路测试：注入 Mock LLM 离线跑通真实 chat() 全流程。

覆盖：检索路由（同人 filtered / 跨人 global / 库外 no-RAG）、引用 grounding
（越界索引丢弃、【参考史料】渲染）、Mock backend 注入不破坏生产行为。
依赖本地 Embedding 缓存与既有向量库（conftest 的 vector_store fixture）。
"""
import json
import re

from src.agents import HistoryCharacterAgent
from src.characters import character_manager


class _MockLLM:
    """确定性假 LLM：有 RAG 时引用 [史料1]，否则无引用。"""

    def __init__(self, bad_cite: bool = False):
        self.bad_cite = bad_cite
        self.last_cited: list = []

    def __call__(self, messages, temperature) -> str:
        self.last_cited = []
        sys_prompt = messages[0]["content"]
        m = re.search(r"\[史料(\d)\]", sys_prompt)
        if not m:
            return json.dumps({"reply": "常识回答", "cited_sources": []}, ensure_ascii=False)
        idx = int(m.group(1)) - 1
        self.last_cited = [999] if self.bad_cite else [idx]
        return json.dumps(
            {"reply": "根据史料回答", "cited_sources": self.last_cited},
            ensure_ascii=False,
        )


def _agent(vector_store, name, llm) -> HistoryCharacterAgent:
    char = character_manager.get_character(name)
    return HistoryCharacterAgent(char, vector_store, None, llm_backend=llm)


def test_mock_backend_runs_full_chat(vector_store):
    """mock backend 走完真实 chat()：同人问题 → 带 RAG 引用渲染"""
    llm = _MockLLM()
    agent = _agent(vector_store, "李白", llm)
    reply, sources, conv = agent.chat("你最著名的诗作是什么", session_id="e2e-test-1")
    assert "根据史料" in reply
    assert "【参考史料】" in reply, "带 RAG 的回答应渲染引用 footer"
    assert sources, "带 RAG 应有引用来源"
    assert llm.last_cited == [0]


def test_cross_person_routes_to_global(vector_store):
    """跨人提问 → 全局路径，命中被问者史料"""
    llm = _MockLLM()
    agent = _agent(vector_store, "李白", llm)
    reply, sources, conv = agent.chat("介绍一下杜甫的生平和诗歌成就", session_id="e2e-test-2")
    assert any(s["character"] == "杜甫" for s in sources)


def test_out_of_kb_refusal_no_rag(vector_store):
    """库外提问 → no-RAG 分支：无史料、无引用 footer"""
    llm = _MockLLM()
    agent = _agent(vector_store, "鲁迅", llm)
    reply, sources, conv = agent.chat("钱学森有哪些贡献", session_id="e2e-test-3")
    assert sources == []
    assert "【参考史料】" not in reply


def test_bad_cite_is_dropped(vector_store):
    """越界引用被 grounding 丢弃：不再渲染 footer、来源为空"""
    llm = _MockLLM(bad_cite=True)
    agent = _agent(vector_store, "李白", llm)
    reply, sources, conv = agent.chat("你最著名的诗作是什么", session_id="e2e-test-4")
    assert llm.last_cited == [999]
    assert sources == [], "越界引用应被丢弃"
    assert "【参考史料】" not in reply
