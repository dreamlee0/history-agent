"""检索重排模块：稠密向量召回之后的第二阶段排序。

背景：纯稠密向量 top-k 只做"召回"，不做"重排"。历史人物名（曹操/苏轼）等
强信号在语义向量里常被稀释，导致 top-3 里混入无关人物的史料。

本模块提供三种模式（Settings.rerank_mode）：
  - "hybrid"（默认）：jieba 中文分词 + TF-IDF 词法打分，与稠密向量分数
    通过 Reciprocal Rank Fusion（RRF）融合排序。完全离线，无需额外模型；
  - "cross_encoder"：尝试加载本地缓存的 bge-reranker 做跨编码器精排；
    本地无缓存时优雅回退到 hybrid（网络恢复后可下载模型启用）；
  - "none"：保持纯相似度，不重排。

注意：本模块只对"已选路径（过滤/全局）"的候选池做排序，不参与
"过滤 vs 全局"的路径决策（路径决策仍在 history_agent 内基于距离比值）。
"""
import os
from pathlib import Path
from typing import List, Optional, Tuple

import jieba

from src.logger import get_logger

logger = get_logger("reranker")

# RRF 融合常数（标准值 60，平滑两个排名的相对重要性）
_RRF_K = 60


def _tokenize(text: str) -> List[str]:
    """jieba 中文分词，去空白与标点，保留有意义词元。"""
    return [w for w in jieba.lcut(text) if w.strip() and not w.isspace()]


def _resolve_local_model(model_name: str) -> Optional[str]:
    """把 HuggingFace 模型 id 解析为本地快照路径；未缓存返回 None。

    与 vector_store._resolve_embedding_model 同思路：只认本地缓存，
    绝不联网校验（避免受限网络下挂起）。
    """
    cache_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface"))
    cache_root = Path(os.environ.get("HF_HUB_CACHE", cache_home / "hub"))
    model_cache = cache_root / f"models--{model_name.replace('/', '--')}"
    snapshots = model_cache / "snapshots"
    if snapshots.exists():
        snap_dirs = [p for p in snapshots.iterdir() if p.is_dir()]
        if snap_dirs:
            return str(snap_dirs[0])
    return None


class LexicalScorer:
    """词法相关度打分：jieba 分词 + TF-IDF 向量余弦相似度（完全离线）。"""

    def __init__(self) -> None:
        self._vectorizer = None

    def score(self, query: str, doc_texts: List[str]) -> List[float]:
        """对候选文档文本计算与查询的词法相似度（0~1，越大越相关）。

        每次按候选集重训 TF-IDF（候选池 ≤ 几十条，开销可忽略），
        避免用一个全局词表产生偏差。
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        if not doc_texts:
            return []
        vectorizer = TfidfVectorizer(tokenizer=_tokenize, lowercase=False)
        doc_matrix = vectorizer.fit_transform(doc_texts)
        query_vec = vectorizer.transform([query])
        sims = cosine_similarity(query_vec, doc_matrix)[0]
        return [float(s) for s in sims]


class HybridReranker:
    """稠密向量排名 + 词法排名 的 RRF 融合重排。"""

    def __init__(self) -> None:
        self._lexical = LexicalScorer()

    def rerank(
        self, query: str, candidates: List[Tuple[object, float]]
    ) -> List[Tuple[object, float]]:
        """重排候选池。

        candidates: (doc, distance) 列表，distance 为稠密向量距离（越小越相关）。
        返回按融合相关度降序的 (doc, fused_score) 列表。
        """
        if not candidates:
            return []

        # 稠密排名：距离升序（越小越相关）
        dense_ordered = sorted(candidates, key=lambda x: x[1])
        # 词法排名：相似度降序
        doc_texts = [doc.page_content for doc, _ in candidates]
        lexical_sims = self._lexical.score(query, doc_texts)
        lexical_ordered = [d for d, _ in sorted(
            zip(candidates, lexical_sims), key=lambda x: x[1], reverse=True
        )]

        # RRF 融合
        fused: dict = {}
        for rank, (doc, _d) in enumerate(dense_ordered):
            fused[id(doc)] = fused.get(id(doc), 0.0) + 1.0 / (_RRF_K + rank + 1)
        for rank, (doc, _d) in enumerate(lexical_ordered):
            fused[id(doc)] = fused.get(id(doc), 0.0) + 1.0 / (_RRF_K + rank + 1)

        by_id = {id(doc): (doc, distance) for doc, distance in candidates}
        ranked = sorted(
            by_id.items(), key=lambda kv: fused[kv[0]], reverse=True
        )
        return [(doc, fused[doc_id]) for doc_id, (doc, _) in ranked]


class CrossEncoderReranker:
    """bge-reranker 跨编码器精排。

    只从本地 HF 缓存加载（local snapshot 路径），无缓存时回退到 HybridReranker
    并记录日志——离线环境不联网下载，也不阻塞。网络恢复后下载模型即自动启用。
    """

    def __init__(self, model_name: str) -> None:
        self._model = None
        self._model_name = model_name
        snapshot = _resolve_local_model(model_name)
        if snapshot:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(snapshot)
                logger.info("cross_encoder 重排模型已从本地缓存加载: %s", model_name)
            except Exception as e:  # 模型损坏/依赖缺失 → 回退
                logger.warning("cross_encoder 加载失败，回退 hybrid: %s", e)
                self._model = None
        else:
            logger.info(
                "cross_encoder 模型 %s 本地未缓存，回退 hybrid（联网后可下载启用）",
                model_name,
            )
        self._fallback = HybridReranker()

    def rerank(self, query: str, candidates: List[Tuple[object, float]]):
        if self._model is None:
            return self._fallback.rerank(query, candidates)
        pairs = [(query, doc.page_content) for doc, _ in candidates]
        try:
            scores = self._model.predict(pairs)
            ranked = [c for _, c in sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)]
            return ranked
        except Exception as e:
            logger.warning("cross_encoder 推理失败，回退 hybrid: %s", e)
            return self._fallback.rerank(query, candidates)


def get_reranker(mode: str, cross_encoder_model: str = "BAAI/bge-reranker-v2-m3"):
    """按配置构造重排器。

    mode: "none" | "hybrid" | "cross_encoder"（后者无本地模型时回退 hybrid）
    """
    mode = (mode or "hybrid").strip().lower()
    if mode == "none":
        return None
    if mode == "cross_encoder":
        return CrossEncoderReranker(cross_encoder_model)
    return HybridReranker()
