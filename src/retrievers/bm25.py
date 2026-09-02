"""BM25 词法索引：为混合检索提供稠密向量之外的稀疏召回通道。

为什么需要：纯稠密向量对"精确人名 / 罕见词 / 多人物枚举"类查询召回不足——
查询里的精确词（如"徐霞客""青蒿素"）在语义空间被稀释，dense top-N 可能
不进候选池，而词法（稀疏）检索能精确命中。BM25（Robertson BM25+）是经典
稀疏打分函数，与稠密检索做 RRF 融合后把这些 dense 漏掉的片段拉回候选池
（见 vector_store.hybrid_search_with_score）。

离线约束：rank_bm25 未安装且网络不可达，故自实现——jieba 分词 + numpy
向量化打分。对全库（千条 chunk 量级）规模开销可忽略；对大规模语料也可满足需求。

注意：本索引只在向量库构建/重建后需要重建（懒加载，见
VectorStoreManager._bm25_index）。切分粒度与向量库 chunk 一致。
"""
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.logger import get_logger

logger = get_logger("bm25")


def _tokenize(text: str) -> List[str]:
    """jieba 中文分词，去空白（与 reranker._tokenize 口径一致）。"""
    import jieba

    return [w for w in jieba.lcut(text) if w.strip() and not w.isspace()]


class BM25Index:
    """jieba 分词的 Robertson BM25+ 索引。

    用法：
        idx = BM25Index().build(docs)          # docs: List[Document]
        idx.search("徐霞客游记", k=10)          # [(doc, score), ...] 降序
        idx.search(q, filter_char="李白")       # 只在该人物 chunk 内排序
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.docs: List = []
        self._doc_chars: List[str] = []
        self._tokenized: List[List[str]] = []
        self._doc_len = np.array([], dtype=np.int64)
        self.avgdl = 0.0
        self._df: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}

    def build(self, docs) -> "BM25Index":
        """用文档列表构建索引。doc 需有 page_content 与 metadata.character。"""
        self.docs = list(docs)
        self._tokenized = [_tokenize(d.page_content) for d in self.docs]
        self._doc_len = np.array([len(t) for t in self._tokenized], dtype=np.int64)
        self._doc_chars = [str(d.metadata.get("character", "")) for d in self.docs]

        n_docs = len(self.docs)
        self.avgdl = float(self._doc_len.mean()) if n_docs else 0.0

        df: Dict[str, int] = {}
        for toks in self._tokenized:
            for term in set(toks):  # 每文档内去重计数
                df[term] = df.get(term, 0) + 1
        self._df = df
        # IDF：ln(1 + (N - df + 0.5)/(df + 0.5))，df 全时也会 >0，避免除零
        self._idf = {
            term: float(np.log(1.0 + (n_docs - f + 0.5) / (f + 0.5)))
            for term, f in df.items()
        }
        logger.info(
            "BM25 索引构建完成：%d 条文档 / %d 个词元 / avgdl=%.1f",
            n_docs, len(df), self.avgdl,
        )
        return self

    def _scores(self, query_tokens: List[str]) -> np.ndarray:
        """返回各文档的 BM25 得分（numpy 向量化）。"""
        n = len(self.docs)
        if n == 0 or not query_tokens:
            return np.zeros(n)
        dl = self._doc_len
        if self.avgdl > 0:
            denom = self.k1 * (1.0 - self.b + self.b * dl / self.avgdl)
        else:
            denom = np.zeros(n)
        total = np.zeros(n)
        for term in query_tokens:
            idf = self._idf.get(term)
            if idf is None:
                continue
            # 每文档该词词频（线性扫描 query 词元，量小）
            tf = np.array(
                [t.count(term) for t in self._tokenized], dtype=np.float64
            )
            mask = tf > 0
            if not mask.any():
                continue
            score = np.zeros(n)
            score[mask] = tf[mask] * (self.k1 + 1.0) / (
                tf[mask] + denom[mask]
            ) * idf
            total += score
        return total

    def search(
        self,
        query: str,
        k: int = 30,
        filter_char: Optional[str] = None,
        filter_chars: Optional[List[str]] = None,
        filter_doc_type: Optional[str] = None,
    ) -> List[Tuple[object, float]]:
        """按 BM25 得分返回 top-k 的 (doc, score)，降序。

        filter_char: 只在该人物的 chunk 内排序（与稠密侧按人物过滤对齐）。
        filter_chars: 多人物名单（$in 联合检索），chunk 人物 ∈ 名单才参与排序。
        filter_doc_type: 只在该文档类型（persona|historical）内排序——严格模式
        （PERSONA_FALLBACK=off）下与稠密侧一致排除 persona。
        """
        tokens = _tokenize(query)
        scores = self._scores(tokens)
        if filter_char:
            mask = np.array(
                [c == filter_char for c in self._doc_chars], dtype=bool
            )
            scores = np.where(mask, scores, -np.inf)
        elif filter_chars:
            keep = set(filter_chars)
            mask = np.array(
                [c in keep for c in self._doc_chars], dtype=bool
            )
            scores = np.where(mask, scores, -np.inf)
        if filter_doc_type:
            mask = np.array(
                [str(d.metadata.get("doc_type", "historical")) == filter_doc_type
                 for d in self.docs],
                dtype=bool,
            )
            scores = np.where(mask, scores, -np.inf)
        order = np.argsort(-scores)[:k]
        # 只返回真正命中（score > 0）的文档：无词法命中时返回空列表，
        # 避免把无关文档以 0 分带进 hybrid 融合池污染排序。
        return [(self.docs[i], float(scores[i])) for i in order if scores[i] > 0]
