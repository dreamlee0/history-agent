"""
历史人物对话系统（RAG 对话机器人） - 集成RAG知识检索 + SQLite持久化
支持知识溯源，回复时引用史料来源

说明：本项目本质是「检索增强(RAG)的对话应用」，不包含工具调用/规划/推理链，
因此模块文档统一表述为"历史人物对话系统 / RAG 对话机器人"而非"Agent"。
类名 HistoryCharacterAgent 予以保留，以兼容既有 import 与测试。
"""
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass, field
import time
import json
import uuid
from functools import lru_cache

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from config import get_settings
from src.characters import HistoricalCharacter, character_manager
from src.memory import conversation_memory
from src.logger import get_logger
from src.retrievers.vector_store import merge_filters
from src.knowledge.aliases import (
    has_out_of_kb_entity,
    is_self_referential,
    resolve_characters_in_text,
)

logger = get_logger("history_agent")

# OpenAI兼容 SDK (可接智谱/DeepSeek/OpenAI等)
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# ── 多人物联合检索：枚举意图 / 点名式检测（阶段3）──
# 枚举词："唐朝有哪些诗人"→"有哪些/哪些"；分类名词：人物枚举题的类别词
# （诗人/文学家/将领/皇帝…）——负面题（"X有哪些主要成就和贡献"）无分类词，
# 天然不触发；时代上下文词："汉武帝时期有哪些名将"里 汉武帝 是背景不是目标。
_ENUM_WORDS = ("有哪些", "哪些是", "哪些", "列举", "分别有", "包括哪些")
_ERA_WORDS = ("时期", "时代", "年间", "之世")
_CATEGORY_NOUNS = frozenset({
    "诗人", "文学家", "词人", "作家", "散文家", "史学家", "思想家", "政治家",
    "军事家", "科学家", "发明家", "名将", "武将", "将领", "名臣", "文臣",
    "大臣", "臣子", "宰相", "皇帝", "帝王", "君主", "君王", "人物", "名人",
    "文化名人", "航海家", "地理学家", "大家", "功臣", "开国功臣", "代表人物",
    "领袖", "统治者", "英雄", "豪杰", "词作大家",
})


def _is_enumeration_query(query: str) -> bool:
    return any(w in query for w in _ENUM_WORDS)


def _has_category_noun(query: str) -> bool:
    return any(n in query for n in _CATEGORY_NOUNS)


def _detect_multi(query: str, asker: str) -> Optional[List[str]]:
    """检测多人物联合检索意图，返回多人物名单（None=不走 multi 分支）。

    - 点名式：查询点名 ≥2 位库内他人（"曹操、刘备、孙权…"）→ 返回名单，
      检索走 {"character": {"$in": 名单}} 联合池；
    - 枚举式：查询含枚举词 + 人物分类名词、非自指、且未点名单个目标人物
      （无点名，或点名仅是时代上下文如"汉武帝时期"）→ 返回空名单，
      检索走多样性全局池（每人物最多 1 条）。

    单点名他人题（如"张飞的性格特点有哪些"，named=1 且非时代上下文）属于
    单目标题，交给 named_other 门，不进 multi——避免改变 cross_trap 路径。
    """
    named = [n for n in resolve_characters_in_text(query) if n != asker]
    if len(named) >= 2 and not is_self_referential(query, asker):
        return named
    if (
        _is_enumeration_query(query)
        and _has_category_noun(query)
        and not is_self_referential(query, asker)
        and (not named or any(w in query for w in _ERA_WORDS))
    ):
        return []
    return None


@lru_cache(maxsize=4)
def _shared_openai_client(api_key: str, base_url: str) -> OpenAI:
    """返回共享的 OpenAI 兼容客户端（按 api_key+base_url 缓存）。

    为什么需要：AgentManager 按人物缓存最多 97 个 Agent，若每个 Agent 各自
    new 一个 OpenAI(api_key=...)，长进程会累积大量 httpx 连接池对象。
    OpenAI 客户端本身线程安全、可在多请求间复用，故全局共享一份，
    api_key/base_url 相同时所有 Agent 复用同一连接池。
    """
    return OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)


@dataclass
class RAGContext:
    """RAG检索上下文"""
    query: str
    documents: List[Document]
    context_text: str
    sources: List[dict]
    # 可观测性：记录本次检索的关键决策数据（过滤/全局最优距离、实际采用路径、
    # 耗时等），供 TRACE 日志回放"这次回答为什么是它"。
    scores: dict = field(default_factory=dict)


class HistoryCharacterAgent:
    """历史人物对话系统（RAG 对话机器人） - 支持RAG知识增强 + 持久化"""

    def __init__(
        self,
        character: HistoricalCharacter,
        vector_store=None,
        db_manager=None,
        llm_backend=None,
    ):
        self.settings = get_settings()
        self.character = character
        self.vector_store = vector_store
        self.db = db_manager
        # 结构化引用 JSON 模式（response_format={"type":"json_object"}）：
        # 从 API 层强制模型输出合法 JSON，而非只靠提示词"自觉"——这是
        # 真实模型下结构化引用渲染率低的根因。若端点不支持该参数
        # （部分 OpenAI 兼容 API 会 400/422），_call_api_with_retry 会
        # 自动降级为普通输出并置 False（见 _is_unsupported_param_error）。
        self._json_mode = True
        # 可注入的 LLM 后端：callable(messages, temperature) -> str。
        # 测试/评测（scripts/evaluate_end_to_end.py）注入确定性 mock 以离线
        # 跑通完整 chat 链路；生产默认 None 走下方 OpenAI 兼容客户端。
        self._llm_backend = llm_backend

        if llm_backend is not None:
            self.client = None
        else:
            if not HAS_OPENAI:
                raise ImportError("请安装 openai SDK: pip install openai")

            if not self.settings.llm_api_key:
                raise ValueError("LLM_API_KEY 未配置，请在环境变量或 Streamlit Secrets 中设置")

            # 复用全局共享客户端（同 key/base_url 共用连接池），
            # 避免 97 个 Agent 各持一个连接对象在长进程中累积。
            self.client = _shared_openai_client(
                self.settings.llm_api_key, self.settings.llm_base_url
            )

    def _retrieve_knowledge(
        self, query: str, k: Optional[int] = None, request_id: Optional[str] = None
    ) -> Optional[RAGContext]:
        """检索相关知识。

        未显式传 k 时用 settings.rag_top_k（默认 3）——把死配置接入真实
        检索路径，.env 可覆盖；评测脚本显式传 k 不受影响。

        按人物过滤优先，但会用相关性分数做兜底判断：
        - 过滤结果明显劣于全局最优（如用户问的是别人）→ 退回全局检索；
        - 过滤结果为空 → 退回全局检索。
        避免把当事人自己的传记误当"相关史料"注入，导致引用错误。

        重排开启（Settings.rerank_mode != "none"）时，流程为
        「召回候选池 k_fetch → 过滤/全局路径决策 → 池内重排 → top-k」：
        路径决策始终基于相似度分数（防跨人物污染依赖它），重排只调整
        选定池内的顺序（详见 src/retrievers/reranker.py）。

        此外两道决策门修正已知失效用例（阈值见 Settings，可 .env 覆盖）：
        - 决策门 1（strong_global）：全局强相关但过滤明显更差 → 退回全局；
        - 决策门 2（out_of_kb_refusal）：库外提问（无自称+双侧弱匹配+点名库外
          实体，三条缺一不可）→ 走 no-RAG 分支，拒绝注入被问人物自传。

        retrieval_mode="hybrid" 时，召回层改为稠密 + BM25 词法的 RRF 融合
        （见 vector_store.hybrid_search_with_score），把纯稠密漏掉的精确人名/
        罕见词/多人物枚举片段拉回候选池；路径决策（best_filtered/best_global/
        两道门）仍基于稠密距离（_min_dense 取池内稠密 top-1），口径与纯
        相似度一致。hybrid 模式自动跳过 MMR 分支。

        scores["timings"]：分阶段耗时（ms）——search_filtered/search_global/
        bm25（仅 hybrid，首次为 BM25 索引构建的一次性成本）/rerank/total，
        供 scripts/benchmark_retrieval.py 做延迟剖析。

        request_id 仅用于 TRACE 日志关联（可观测性：记录过滤/全局最优距离、
        实际采用路径与耗时，供"这次回答为什么是它"的排障回放）。
        """
        if k is None:
            k = self.settings.rag_top_k
        if not self.vector_store:
            return None

        rid = request_id or "?"
        start = time.monotonic()
        scores: dict = {}
        timings: dict = {}
        try:
            # 候选池大小：重排开启时多召回（k_fetch）再精排取 top-k；
            # 关闭重排时直接取 k，行为与旧版一致。
            rerank_on = self.settings.rerank_mode != "none"
            k_fetch = self.settings.rerank_k_fetch if rerank_on else k

            # 混合检索模式（retrieval_mode="hybrid"）：候选池改用稠密 + BM25
            # 词法的 RRF 融合召回，把纯稠密漏掉的精确人名/罕见词片段拉回
            # 候选池。路径决策距离仍取稠密 top-1（与纯相似度口径完全一致）：
            # 融合池按 RRF 截断到 k_fetch，dense top-1 可能不在池内，不能用
            # 池内 min dense 代替——故 hybrid 下另取 k=1 的稠密结果做决策。
            hybrid_mode = self.settings.retrieval_mode == "hybrid"
            if hybrid_mode:
                # 预热 BM25 词法索引（懒构建缓存）：一次性构建成本记入 bm25
                # 阶段（此后每次查询近似 0）；BM25 搜索本身并入了下方检索阶段
                # （hybrid 调用内部含 dense+bm25 两步，无法再细分）。
                _t0 = time.monotonic()
                self.vector_store._bm25_index()
                timings["bm25"] = round((time.monotonic() - _t0) * 1000, 1)

            # 严格模式（PERSONA_FALLBACK=off）：只检索真实史源，persona（内置
            # 摘要）完全移出史实检索；默认（fallback=on）双轨——persona 可参与
            # 检索但标注非权威、史源优先。
            strict_filter = (
                {"doc_type": "historical"} if not self.settings.persona_fallback else None
            )

            # 多人物联合检索（阶段3）：枚举题（"唐朝有哪些诗人"）与点名题
            # （"曹操、刘备、孙权…"）走独立 multi 分支——枚举题 filtered 池
            # 只含被问者自传、global top-3 装不下 3-7 个期望人物，故按枚举
            # 意图/点名人数检出后取 top-multi_top_k 多样性池（见 _retrieve_multi）。
            # 检出返回名单（非 None）即提前分支，跳过单人物 filtered/ratio/库外门。
            multi_chars = _detect_multi(query, self.character.name)
            if multi_chars is not None:
                return self._retrieve_multi(
                    query, multi_chars, k, rid, strict_filter, hybrid_mode, timings, start
                )

            # 1) 按人物过滤检索（带分数，距离越小越相关）
            _t0 = time.monotonic()
            if hybrid_mode:
                filtered_dense = self.vector_store.search_by_character_with_score(
                    query, self.character.name, k=1, extra_filter=strict_filter
                )
                filtered = self.vector_store.hybrid_search_with_score(
                    query, k=k_fetch, fetch_k=k_fetch,
                    filter=merge_filters(
                        {"character": self.character.name}, strict_filter
                    ),
                    bm25_k=self.settings.hybrid_bm25_k,
                )
            else:
                filtered_dense = filtered = (
                    self.vector_store.search_by_character_with_score(
                        query, self.character.name, k=k_fetch,
                        extra_filter=strict_filter,
                    )
                )
            timings["search_filtered"] = round(
                (time.monotonic() - _t0) * 1000, 1
            )

            # 2) 全局检索（带分数），用于相关性对比与兜底
            _t0 = time.monotonic()
            if hybrid_mode:
                global_dense = self.vector_store.similarity_search_with_score(
                    query, k=1, filter=strict_filter
                )
                global_results = self.vector_store.hybrid_search_with_score(
                    query, k=k_fetch, fetch_k=k_fetch,
                    filter=strict_filter,
                    bm25_k=self.settings.hybrid_bm25_k,
                )
            else:
                global_dense = global_results = (
                    self.vector_store.similarity_search_with_score(
                        query, k=k_fetch, filter=strict_filter
                    )
                )
            timings["search_global"] = round(
                (time.monotonic() - _t0) * 1000, 1
            )

            use_filtered_path = False
            if filtered:
                best_filtered = (
                    filtered_dense[0][1] if filtered_dense else None
                )
                best_global = global_dense[0][1] if global_dense else None
                # 记录决策数据：过滤/全局最优距离与比值，供阈值评估与排障
                scores["best_filtered"] = best_filtered
                scores["best_global"] = best_global
                scores["ratio"] = (
                    round(best_filtered / best_global, 3)
                    if best_filtered is not None and best_global
                    else None
                )
                # 过滤结果不比全局最优差太多时，保留人物聚焦的结果。
                # hybrid 模式下 BM25 独有命中不带稠密距离、无法参与距离决策，
                # 池内无稠密命中（病理情况）时视为不佳、直接走全局。
                use_filtered_path = (
                    self._should_use_filtered(best_filtered, best_global)
                    if best_filtered is not None
                    else False
                )

                # 决策门 1（强相关全局门）：全局最优是强相关、过滤结果却明显
                # 更差时，即使比值未超 filtered_score_ratio 也退回全局——
                # 修"问曹操却注入诸葛亮自传(ratio=1.192 恰好漏过)"类自传陷阱题。
                if (
                    use_filtered_path
                    and best_global is not None
                    and best_global < self.settings.strong_global_threshold
                    and (best_filtered - best_global) > self.settings.gap_threshold
                ):
                    logger.info(
                        "[TRACE:%s] gate=strong_global 全局强相关(best_g=%.3f<%.2f)"
                        "且过滤明显更差(Δ=%.3f>%.2f) → 退回全局",
                        rid, best_global, self.settings.strong_global_threshold,
                        best_filtered - best_global, self.settings.gap_threshold,
                    )
                    use_filtered_path = False
                    scores["gate"] = "strong_global"

                # 决策门 1b（点名他人门）：查询点名了知识库内、且不是提问人本人的
                # 其他人物（如"曹操的军事谋略"问者=诸葛亮）时，提问对象是他人在先，
                # 走全局池——避免把提问人本人的史料当"相关史料"注入。真实史源入库后
                # 高相似跨人陷阱加剧：诸葛亮传·用兵与"曹操军事谋略"语义接近、距离比
                # 门(1.2x)漏过，需专名证据拉回全局。自我指涉题（含"你"或提问人本人）
                # 不受影响（那是"问本人"路径）。
                named_others = [
                    n for n in resolve_characters_in_text(query)
                    if n != self.character.name
                ]
                if (
                    use_filtered_path
                    and named_others
                    and not is_self_referential(query, self.character.name)
                ):
                    logger.info(
                        "[TRACE:%s] gate=named_other 查询点名他人 %s（非提问人%s）"
                        " → 退回全局，避免自传注入",
                        rid, "/".join(named_others), self.character.name,
                    )
                    use_filtered_path = False
                    scores["gate"] = "named_other"

            # 决策门 2（库外注入拒绝）：查询无自称（非"问本人"）、未点名任何库内
            # 人物、且点名了库外人物专名（如钱学森/拿破仑——知识库 97 人之外）时，
            # 判定提问对象不在知识库，走 no-RAG 分支而不是把被问人物自传当
            # "相关史料"注入。判定只依赖人物名信号（resolve + has_out_of_kb_entity），
            # 不再要求双侧弱匹配——旧版距离条件（best>0.90）让钟南山/郑成功等
            # 强相关误报漏过（best_global 0.83/0.75 <0.90），本轮改为人物名判据
            # 后 198 条评测单相关题零误伤（见 RAG_EVALUATION_REPORT_FULL.md）。
            if (
                filtered
                and not is_self_referential(query, self.character.name)
                and not resolve_characters_in_text(query)
                and has_out_of_kb_entity(query)
            ):
                logger.info(
                    "[TRACE:%s] gate=out_of_kb_refusal 库外提问(无自称、未点名"
                    "库内人物且点名库外专名) → 走 no-RAG 分支",
                    rid,
                )
                scores["path"] = "none"
                scores["gate"] = "out_of_kb_refusal"
                timings["total"] = round((time.monotonic() - start) * 1000, 1)
                scores["timings"] = timings
                scores["latency_ms"] = timings["total"]
                logger.info(
                    "[TRACE:%s] retrieval: path=none gate=out_of_kb_refusal query=%s",
                    rid, query,
                )
                return None

            # 3) 选定最终候选池（过滤 or 全局），再按配置排序/重排。
            #    路径决策始终基于相似度分数（防跨人物污染依赖它）；重排/MMR
            #    只对选定池内的顺序做调整，不改变路径选择。
            if use_filtered_path:
                pool = [(d, s) for d, s in filtered]
            elif global_results:
                pool = [(d, s) for d, s in global_results]
            else:
                pool = []

            if not pool:
                scores["path"] = "none"
                timings["total"] = round((time.monotonic() - start) * 1000, 1)
                scores["timings"] = timings
                logger.info("[TRACE:%s] retrieval: path=none query=%s", rid, query)
                return None

            scores["path"] = "filtered" if use_filtered_path else "global"

            # 重排优先于 MMR：rerank_mode != "none" 时对候选池精排取 top-k。
            use_mmr = self.settings.retrieval_mode == "mmr"
            if rerank_on:
                reranker = self._get_reranker()
                if reranker is not None:
                    _t0 = time.monotonic()
                    ranked = reranker.rerank(query, pool)
                    timings["rerank"] = round((time.monotonic() - _t0) * 1000, 1)
                    docs = [doc for doc, _ in ranked[:k]]
                    scores["rerank"] = self.settings.rerank_mode
                else:
                    docs = [doc for doc, _ in pool[:k]]
                    scores["rerank"] = "none"
            elif use_mmr:
                # MMR 模式：仅在选定路径内重排提升多样性
                if use_filtered_path:
                    docs = self.vector_store.mmr_search(
                        query, k=k, fetch_k=k * 5,
                        filter=merge_filters(
                            {"character": self.character.name}, strict_filter
                        ),
                    )
                else:
                    docs = self.vector_store.mmr_search(
                        query, k=k, fetch_k=k * 5, filter=strict_filter
                    )
                scores["rerank"] = "mmr"
            else:
                docs = [doc for doc, _ in pool[:k]]
                scores["rerank"] = "none"

            # 双轨分区（fallback=on）：真实史源（doc_type=historical）优先按原序，
            # persona（内置摘要·非权威）补位——保证"有史源引史源、无史源才退摘要"。
            docs = self._partition_docs_by_type(docs)

            return self._finalize_rag(
                query, docs, rid, timings, scores, start,
                used_mmr=use_mmr,
            )

        except Exception as e:
            logger.warning("[TRACE:%s] RAG检索错误: %s", rid, e)
            return None

    def _finalize_rag(
        self, query: str, docs, rid: str, timings: dict, scores: dict,
        start: float, used_mmr: bool = False,
    ) -> RAGContext:
        """主路径与 multi 分支共用的 RAGContext 组装：分区已在调用方完成，
        这里负责 source 序列化、TRACE 日志与 RAGContext 构造。"""
        scores["used_mmr"] = used_mmr
        timings["total"] = round((time.monotonic() - start) * 1000, 1)
        scores["timings"] = timings
        scores["latency_ms"] = timings["total"]

        context_parts = []
        sources = []
        for i, doc in enumerate(docs, 1):
            source_info = {
                "index": i,
                "title": doc.metadata.get("title", "未知"),
                "source": doc.metadata.get("source", "未知"),
                "url": doc.metadata.get("url", ""),
                "character": doc.metadata.get("character", ""),
                "doc_type": doc.metadata.get("doc_type", "historical"),
                "dynasty": doc.metadata.get("dynasty", ""),
                "book": doc.metadata.get("book", ""),
                "chapter": doc.metadata.get("chapter", ""),
            }
            sources.append(source_info)

            context_parts.append(
                f"[史料{i}] {self._source_label(doc)}\n"
                f"{doc.page_content}"
            )

        # 可回放：检索用了哪条路径、命中了哪些来源、决策用到的分数
        logger.info(
            "[TRACE:%s] retrieval: path=%s mmr=%s latency_ms=%.1f "
            "best_filtered=%s best_global=%s ratio=%s sources=%s",
            rid, scores["path"], used_mmr, scores["latency_ms"],
            scores.get("best_filtered"), scores.get("best_global"),
            scores.get("ratio"),
            [s["title"] for s in sources],
        )

        return RAGContext(
            query=query,
            documents=docs,
            context_text="\n\n".join(context_parts),
            sources=sources,
            scores=scores,
        )

    def _retrieve_multi(
        self, query: str, chars: List[str], k: int, rid: str,
        strict_filter: Optional[Dict], hybrid_mode: bool, timings: dict, start: float,
    ) -> Optional[RAGContext]:
        """多人物联合检索（阶段3）：枚举/点名题返回 top-multi_top_k 覆盖多人物。

        - chars 非空（点名式 ≥2 人）：{"character": {"$in": chars}} 联合池——
          直接把候选限定在被点名的几个人内，避免 global 池被无关人物霸榜；
        - chars 为空（枚举式）：全局池召回后按人物去重（每人物最多 1 条），
          保证"唐朝有哪些诗人"不被单人物多 chunk 霸榜漏掉其它诗人。

        路径固定 path=multi，跳过单人物 filtered/ratio/strong_global/named_other/
        库外门——枚举/点名题与"问本人自传"无关（检测已排除自指与库外专名）。
        不做标准重排（人物多样性优先，重排会打乱去重后的人物覆盖）。
        """
        multi_top_k = self.settings.multi_top_k
        k = max(k, multi_top_k)
        # 候选池放大：去重需要足够多的人物候选（≥3 倍目标条数）
        fetch_k = max(k * 3, self.settings.rerank_k_fetch)
        filt = merge_filters(
            {"character": {"$in": chars}} if chars else None, strict_filter
        )

        _t0 = time.monotonic()
        if hybrid_mode:
            pool = self.vector_store.hybrid_search_with_score(
                query, k=fetch_k, fetch_k=fetch_k, filter=filt,
                bm25_k=self.settings.hybrid_bm25_k,
            )
        else:
            pool = self.vector_store.similarity_search_with_score(
                query, k=fetch_k, filter=filt
            )
        timings["search_multi"] = round((time.monotonic() - _t0) * 1000, 1)

        # 人物去重：每人物最多保留 1 条（保留检索序最优者），保证多人物覆盖。
        # 命中的人物按检索序 = 相关度序，恰好服务枚举题"由相关到一般"的列举。
        seen: set = set()
        docs: List = []
        for d, _s in pool:
            c = d.metadata.get("character", "")
            if c in seen:
                continue
            seen.add(c)
            docs.append(d)
            if len(docs) >= k:
                break

        if not docs:
            scores = {"path": "none", "gate": "multi_empty"}
            timings["total"] = round((time.monotonic() - start) * 1000, 1)
            scores["timings"] = timings
            logger.info("[TRACE:%s] retrieval: path=none gate=multi_empty query=%s", rid, query)
            return None

        # 双轨分区：史源优先，persona 补位（与主路径一致）
        docs = self._partition_docs_by_type(docs)

        scores = {
            "path": "multi",
            "multi_chars": chars,
            "multi_top_k": len(docs),
            "search_multi_ms": timings["search_multi"],
        }
        logger.info(
            "[TRACE:%s] gate=multi 联合检索 chars=%s n=%d → path=multi",
            rid, "/".join(chars) if chars else "(枚举)", len(docs),
        )
        return self._finalize_rag(query, docs, rid, timings, scores, start)

    def _should_use_filtered(self, best_filtered: float, best_global: Optional[float]) -> bool:
        """判断按人物过滤的结果是否值得保留（分数为距离，越小越相关）。

        过滤结果明显劣于全局最优（best_filtered > best_global * filtered_score_ratio）
        时，判定用户问题与本人物无关，退回全局检索，避免把当事人自己的传记
        误当"相关史料"注入。阈值来自 Settings.filtered_score_ratio，可配置。
        """
        if best_global is None:
            return True
        return best_filtered <= best_global * self.settings.filtered_score_ratio

    # ── 数据源双轨：真实史源（historical）与 persona（内置摘要·非权威）──

    @staticmethod
    def _partition_docs_by_type(docs) -> list:
        """双轨分区：真实史源按原序在前，persona（内置摘要）补位在后。

        保证"有史源引史源、无史源才退摘要"；排序稳定（同类型内保持原序），
        不改变决策门基于稠密距离的语义（分区发生在路径决策之后）。
        """
        hist = [
            d for d in docs
            if d.metadata.get("doc_type", "historical") == "historical"
        ]
        pers = [
            d for d in docs
            if d.metadata.get("doc_type", "historical") != "historical"
        ]
        return hist + pers

    @staticmethod
    def _source_label(doc) -> str:
        """[史料N] 块头：史源显示 朝代·《书·篇卷》- 来源；persona 标注非权威。"""
        m = doc.metadata
        if m.get("doc_type") == "historical":
            book = (m.get("book") or "").strip()
            chapter = (m.get("chapter") or "").strip()
            dynasty = (m.get("dynasty") or "").strip()
            if book:
                loc = f"{book}" + (f"·{chapter}" if chapter else "")
                prefix = f"{dynasty}·" if dynasty else ""
                return f"出处: {prefix}《{loc}》 - {m.get('source', '')}"
            return f"来源: {m.get('source', '')} - {m.get('title', '')}"
        return (
            f"来源: {m.get('source', '')} - {m.get('title', '')}"
            "（内置摘要·非权威史源，仅风格参考）"
        )

    @staticmethod
    def _footer_label(si: dict) -> str:
        """【参考史料】footer 单条：史源显示《书·篇卷》- 朝代·来源；persona 附注。"""
        if si.get("doc_type") == "historical":
            book = (si.get("book") or "").strip()
            chapter = (si.get("chapter") or "").strip()
            dynasty = (si.get("dynasty") or "").strip()
            src = si.get("source", "")
            if book:
                loc = f"{book}" + (f"·{chapter}" if chapter else "")
                prefix = f"{dynasty}·" if dynasty else ""
                return f"[{si['index']}]《{loc}》- {prefix}{src}"
            return f"[{si['index']}]《{si['title']}》- {src}"
        return f"[{si['index']}]《{si['title']}》- {si['source']}（内置摘要·非权威）"

    def _get_reranker(self):
        """按配置懒加载重排器并缓存（避免每次检索重建；cross_encoder 加载开销大）。

        rerank_mode="none" 返回 None（不重排）；"cross_encoder" 本地无模型时
        由 reranker 内部优雅回退到 hybrid（见 src/retrievers/reranker.py）。
        """
        if self.settings.rerank_mode == "none":
            return None
        if getattr(self, "_reranker", None) is None:
            from src.retrievers.reranker import get_reranker

            self._reranker = get_reranker(
                self.settings.rerank_mode,
                self.settings.rerank_cross_encoder_model,
            )
        return self._reranker

    def _build_system_prompt(self, rag_context: Optional[RAGContext] = None) -> str:
        """构建系统提示词"""
        base_prompt = self.character.get_system_prompt()

        if rag_context:
            base_prompt += f"""

## 相关历史史料
以下是从史料库中检索到的相关信息（[史料1] 对应编号 0，依次类推）：

{rag_context.context_text}

## 史料使用规则（必须严格遵守）
1. 【以史料为准】优先依据上面史料回答；史料已明确记载的内容，直接采用，不得随意增删或虚构细节。
2. 【禁止编造】史料未记载的内容，请明确说明"此事史料记载有限，未有详载"，不得为了角色扮演而编造史实、年份、数字或文献。
3. 【引用必须来自上述列表】cited_sources 中的编号只能从上面史料列表中选择，严禁引用列表中不存在的史料。
4. 【角色与事实平衡】可保持人物口吻与性格，但历史事实必须准确；若问及与本人物无关或超出本人时代之事，依据史料客观回答。

## 结构化输出要求（必须遵守）
请只输出一个 JSON 对象，不要输出任何其他文字，格式如下：
{{"reply": "你的完整回答（不要自行添加【参考史料】段落，引用由系统统一生成）", "cited_sources": [0, 2]}}
- cited_sources：本回答实际引用的史料编号列表（从 0 开始，[史料1]=0、[史料2]=1、以此类推）。
- 若回答未引用任何史料，cited_sources 填 []。
"""
        else:
            base_prompt += """

## 回答约束
本次检索未获取到相关史料。请基于可靠的历史常识回答，保持人物口吻；
若不确定，请如实说明"此事史料记载有限"，切勿编造文献出处或具体数字。
"""
        return base_prompt

    @staticmethod
    def _parse_structured_reply(raw: str) -> Optional[Tuple[str, List[int]]]:
        """从模型输出中解析结构化回答 {"reply": ..., "cited_sources": [...]}。

        为什么需要（引用可验证）：直接信任模型自由生成的【参考史料】文本，
        无法保证引用真的存在于本次检索集合内（grounding 是软的）。改为要求
        模型输出 JSON 结构化字段 cited_sources:[索引]，代码侧再校验索引范围，
        实现"引用一定指向本次检索到的史料"。

        解析尽量健壮：兼容 ```json 代码块包裹、JSON 前后混有解释性文字等
        常见情况；解析失败返回 None，由调用方回退到纯文本（不阻塞对话）。
        """
        if not raw:
            return None
        text = raw.strip()
        # 去掉 ```json ... ``` 代码块包裹（部分模型会额外添加）
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.startswith("json"):
                text = text[4:].strip()
        try:
            # 从第一个 { 起做增量解析，容忍 JSON 前后的解释性文字
            start = text.find("{")
            if start == -1:
                return None
            data, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        reply = data.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            return None
        cited = data.get("cited_sources")
        if not isinstance(cited, list):
            cited = []
        return reply.strip(), [int(i) for i in cited if isinstance(i, int) and not isinstance(i, bool)]

    @staticmethod
    def _validate_cited(cited: List[int], n_sources: int) -> List[int]:
        """校验引用索引落在检索集合内，去重并升序。

        越界/负数索引说明模型引用了不存在的史料，直接丢弃（grounding 校验），
        只保留 0 <= i < n_sources 的合法索引。
        """
        return sorted({i for i in cited if isinstance(i, int) and 0 <= i < n_sources})

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

    @staticmethod
    def _is_unsupported_param_error(e: Exception) -> bool:
        """判断是否是"端点不支持 response_format/json_object 参数"的确定性错误。

        部分 OpenAI 兼容端点（不同版本的智谱/自建网关等）不认识
        response_format，会返回 400/422 及 "unknown parameter" 之类报错。
        这类错误确定性可判断：一旦发生就应关闭 json 模式并原地重试，
        而不是走 _is_retryable_error 的指数退避（那是给瞬时错误的）。
        """
        status = getattr(e, "status_code", None)
        if status not in (400, 422):
            return False
        msg = str(e).lower()
        return any(
            k in msg
            for k in (
                "response_format",
                "json_object",
                "unknown parameter",
                "unsupported parameter",
                "unknown argument",
                "extra fields not permitted",
            )
        )

    def _call_api_with_retry(
        self,
        messages: list,
        max_retries: int = 3,
        temperature: Optional[float] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """带重试机制的 API 调用。

        temperature 为 None 时使用 settings.temperature；
        史实问答（有 RAG 史料命中）时应传 settings.temperature_factual。
        仅对瞬时错误重试（见 _is_retryable_error），4xx 立即抛出；
        返回内容为空（None/空白串）时重试一次，仍为空则抛带提示的异常，
        避免上层把 None 直接拼进 f-string 或写入 DB。

        request_id 用于把 LLM 调用的模型/温度/token 用量/耗时关联到同一
        轮对话（可观测性），不参与重试逻辑。
        """
        if temperature is None:
            temperature = self.settings.temperature

        rid = request_id or "?"
        start = time.monotonic()
        attempt = 0
        while attempt < max_retries:
            try:
                if self._llm_backend is not None:
                    # 测试/评测注入的 mock backend（callable(messages, temperature)->str），
                    # 生产默认 None 走下方真实 OpenAI 兼容客户端。
                    content = self._llm_backend(messages, temperature)
                    usage = None
                else:
                    kwargs = dict(
                        model=self.settings.llm_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=self.settings.llm_max_tokens,
                    )
                    if self._json_mode:
                        # json_object：从 API 层强制合法 JSON，结构化引用
                        # 解析才有高成功率——0/198 的根因正是仅提示词要求
                        # 输出 {reply, cited_sources} 时真实模型不遵守。
                        kwargs["response_format"] = {"type": "json_object"}
                    response = self.client.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content
                    usage = getattr(response, "usage", None)
            except Exception as e:
                error_msg = str(e)
                if self._json_mode and self._is_unsupported_param_error(e):
                    # 端点不认识 response_format 参数（部分兼容 API）：
                    # 关闭 json 模式原地重试，不消耗重试次数、不走指数退避。
                    self._json_mode = False
                    logger.warning(
                        "[TRACE:%s] 端点不支持 response_format=json_object，"
                        "已降级为普通输出（结构化引用回退提示词约束）",
                        rid,
                    )
                    time.sleep(0.2)
                    continue
                if not self._is_retryable_error(e):
                    # 确定性错误（4xx 等）：重试无意义，立即抛出
                    raise Exception(f"API调用失败: {error_msg}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    time.sleep(wait_time)
                    attempt += 1
                    continue
                # 最后一次重试也失败（瞬时错误持续存在）
                if "Connection" in error_msg or "timeout" in error_msg.lower():
                    raise Exception(f"API连接失败，请检查网络或API Key配置。错误: {error_msg}")
                elif "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower():
                    raise Exception(f"API Key无效或未配置。请在Streamlit Cloud的Secrets中设置LLM_API_KEY")
                else:
                    raise Exception(f"API调用失败: {error_msg}")

            if content is None or not content.strip():
                # 模型返回空内容：再试一次（可能是瞬时异常），仍空则明确报错
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    attempt += 1
                    continue
                raise Exception("模型返回了空内容，请重试")
            # 记录 token 用量与耗时（可观测性）；mock backend 无 usage，
            # 部分兼容端点也可能不带 usage，用 getattr 兜底为 "?" 避免崩溃。
            model_tag = "mock" if self._llm_backend is not None else self.settings.llm_model
            logger.info(
                "[TRACE:%s] llm: model=%s temp=%s attempt=%d latency_ms=%.0f "
                "prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                rid, model_tag, temperature, attempt,
                (time.monotonic() - start) * 1000,
                getattr(usage, "prompt_tokens", "?") if usage else "?",
                getattr(usage, "completion_tokens", "?") if usage else "?",
                getattr(usage, "total_tokens", "?") if usage else "?",
            )
            return content
        # 防御：理论上不可达（循环内所有路径要么 return 要么 raise）
        raise Exception("API调用失败: 重试次数耗尽")

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
        # 每轮生成一个请求 ID，把检索/LLM/落库日志串成一条可回放链路
        # （可观测性：排障时按 request_id 查"这次回答为什么是它"）。
        request_id = uuid.uuid4().hex[:12]
        _start = time.monotonic()

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
            # 从数据库恢复最近消息：统一走 restore_recent_messages 恢复路径，
            # 覆盖"换进程/多进程后内存冷启动、仍携带 conversation_id 续聊"场景
            # （内存是进程内单例，冷启动时必须以 SQLite 为准）。
            self.db.restore_recent_messages(
                session_id, self.character.name, conversation_memory, mem_key,
                max_messages=self.settings.max_history,
                conversation_id=conversation_id,
            )
            history = conversation_memory.get_messages(mem_key)

        # 保存用户消息（记录 id，API 失败时回滚，见下方 except）
        user_msg_id = None
        if self.db and conversation_id:
            user_msg_id = self.db.add_message(conversation_id, "user", user_input)

        # RAG检索
        rag_context = self._retrieve_knowledge(user_input, request_id=request_id)

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
            result = self._call_api_with_retry(
                messages, temperature=temperature, request_id=request_id
            )
        except Exception:
            # 回滚刚写入的用户消息，避免"有问无答"的孤儿消息留在对话里：
            # 否则用户重试时，该问题会被当作已答复内容再次注入上下文，
            # 造成重复提问、上下文错乱。
            if user_msg_id is not None:
                self.db.delete_message(user_msg_id)
            raise

        # 引用可验证（grounding 硬化）：解析模型输出的结构化 cited_sources，
        # 只渲染"确实落在本次检索集合内"的引用；解析失败则回退纯文本，
        # 不阻塞对话。
        sources = rag_context.sources if rag_context else []
        if rag_context:
            parsed = self._parse_structured_reply(result)
            if parsed is None:
                # 兜底：json_object 下仍可能拿到"合法 JSON 但缺 reply/格式
                # 走样"（推理模型截断、reasoning 吃预算等）。做一次有针对性
                # 的重试（追加"只输出 JSON"强约束），仍失败才回退纯文本。
                logger.warning(
                    "[TRACE:%s] 结构化引用解析失败，重试一次（强化 JSON 约束）",
                    request_id,
                )
                nudge = {
                    "role": "user",
                    "content": '只输出一个 JSON 对象：{"reply": "你的完整回答", '
                               '"cited_sources": [引用到的史料索引数组]}，'
                               "不要输出任何其他文字。",
                }
                try:
                    result2 = self._call_api_with_retry(
                        messages + [nudge],
                        temperature=temperature,
                        request_id=request_id,
                    )
                except Exception:
                    result2 = None
                if result2 is not None:
                    parsed2 = self._parse_structured_reply(result2)
                    if parsed2 is not None:
                        parsed = parsed2
                        result = result2
                    else:
                        logger.warning(
                            "[TRACE:%s] 结构化引用重试仍解析失败，回退纯文本输出",
                            request_id,
                        )
                else:
                    logger.warning(
                        "[TRACE:%s] 结构化引用重试调用失败，回退纯文本输出",
                        request_id,
                    )
            if parsed is not None:
                reply_text, cited = parsed
                valid = self._validate_cited(cited, len(sources))
                dropped = [i for i in cited if i not in valid]
                # 根据有效引用机器生成【参考史料】段：引用必然可溯源、
                # 顺序确定，不再依赖模型自由拼写文献名。
                result = reply_text
                if valid:
                    footer = "【参考史料】" + " ".join(
                        self._footer_label(sources[i]) for i in valid
                    )
                    result = reply_text.rstrip() + "\n\n" + footer
                sources = [sources[i] for i in valid]
                if dropped:
                    logger.warning(
                        "[TRACE:%s] 丢弃越界引用索引 %s（不在本次检索集合内）",
                        request_id, dropped,
                    )

        # 保存助手消息
        if self.db and conversation_id:
            self.db.add_message(conversation_id, "assistant", result, sources)

        # 更新内存记忆
        conversation_memory.add_message(mem_key, "user", user_input)
        conversation_memory.add_message(mem_key, "assistant", result)

        # 整轮汇总 trace（含检索决策与最终引用来源）
        logger.info(
            "[TRACE:%s] chat done: conv=%s char=%s total_ms=%.0f scores=%s sources=%s",
            request_id, conversation_id, self.character.name,
            (time.monotonic() - _start) * 1000,
            rag_context.scores if rag_context else {},
            [s.get("title") for s in sources],
        )

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

    def __init__(self, vector_store=None, db_manager=None, llm_backend=None):
        self.vector_store = vector_store
        self.db = db_manager
        self._llm_backend = llm_backend
        self._agents: dict[str, HistoryCharacterAgent] = {}

    def get_agent(self, character_name: str) -> Optional[HistoryCharacterAgent]:
        """获取或创建对话机器人"""
        if character_name in self._agents:
            return self._agents[character_name]

        character = character_manager.get_character(character_name)
        if not character:
            return None

        agent = HistoryCharacterAgent(
            character, self.vector_store, self.db, self._llm_backend
        )
        self._agents[character_name] = agent
        return agent

    def list_characters(self) -> List[str]:
        """列出所有可用人物"""
        return character_manager.list_names()
