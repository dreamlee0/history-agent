"""
向量数据库管理器 - RAG知识库核心
支持历史人物资料的存储、检索和溯源
使用本地 HuggingFace Embedding (免费，无需 API Key)
"""
import os
import sys
from typing import List, Optional, Dict
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings
from src.logger import get_logger

# HuggingFace 模型下载超时设置（云端首次加载更宽容，避免慢连接直接失败）
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")

logger = get_logger("vector_store")


def merge_filters(*filters) -> Optional[Dict]:
    """把多个 Chroma where 条件合并为合法表达式。

    Chroma 的单层 where dict 只能表达"单一操作符"（如 {"character": "孔子"}
    是 $eq 简写）；多条件必须用 {"$and": [...]} 包裹，否则抛
    "Expected where to have exactly one operator"。空条件合并返回 None。
    """
    conds = [f for f in filters if f]
    if not conds:
        return None
    if len(conds) == 1:
        return conds[0]
    return {"$and": conds}


def _metadata_match(meta: Dict, filt: Optional[Dict]) -> bool:
    """元数据过滤匹配，与 Chroma where 语义对齐（覆盖本库实际使用的表达式）。

    支持：单层键值简写（{"character": "x"} 等价 $eq）与 $and/$or 组合
    （merge_filters 产出 {"$and": [...]}），以及 $in/$ne 操作符。
    """
    if not filt:
        return True
    if "$and" in filt:
        return all(_metadata_match(meta, c) for c in filt["$and"])
    if "$or" in filt:
        return any(_metadata_match(meta, c) for c in filt["$or"])
    for key, val in filt.items():
        if key.startswith("$"):
            continue
        mv = meta.get(key)
        if isinstance(val, dict):
            if "$in" in val and mv not in val["$in"]:
                return False
            if "$ne" in val and mv == val["$ne"]:
                return False
            continue
        if mv != val:
            return False
    return True


def _extract_filter_terms(filt: Optional[Dict]) -> tuple:
    """从 Chroma where 表达式提取 character/doc_type 过滤值（供 BM25 侧过滤）。

    支持单层简写（{"character": "x"}）、$in 多人物（{"character": {"$in": [...]}}）
    与 merge_filters 产出的 $and 包裹形式；提取不到时返回 None
    （BM25 侧不按该键过滤）。返回 (char, chars, doc_type)：
      - char：单人物名（$eq 简写）
      - chars：多人物名单（$in 列表，多人物联合检索用）
      - doc_type：文档类型
    """
    conds = filt.get("$and") if filt and "$and" in filt else ([filt] if filt else [])
    char = chars = doc_type = None
    for c in conds:
        if not isinstance(c, dict):
            continue
        v = c.get("character")
        if isinstance(v, str):
            char = v
        elif isinstance(v, dict) and isinstance(v.get("$in"), list):
            chars = v["$in"]
        d = c.get("doc_type")
        if isinstance(d, str):
            doc_type = d
    return char, chars, doc_type


def _resolve_embedding_model() -> str:
    """解析本地缓存的 Embedding 模型路径。

    sentence-transformers 加载模型时会对 huggingface.co 发起版本校验请求。
    新版 huggingface_hub(0.36+) 的 hf_hub_download 默认 local_files_only=False，
    会强制做远端 HEAD 校验，受限网络下反复重试可挂起数十秒甚至超时（实测 >200s）。

    这里把模型解析成本地缓存快照路径传入，加载时完全走本地（约 5s），
    顺带启用离线环境变量以防其它 HF 调用联网。若本地无缓存（如云端首次部署），
    保持仓库 id 不变，让其正常下载。
    """
    model_name = get_settings().embedding_model

    # 本身就是本地路径
    if Path(model_name).exists():
        return model_name

    # 查找 HF hub 缓存中的模型快照
    cache_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface"))
    cache_root = Path(os.environ.get("HF_HUB_CACHE", cache_home / "hub"))
    model_cache = cache_root / f"models--{model_name.replace('/', '--')}"
    snapshots = model_cache / "snapshots"
    if snapshots.exists():
        snap_dirs = [p for p in snapshots.iterdir() if p.is_dir()]
        if snap_dirs:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            return str(snap_dirs[0])

    return model_name


class VectorStoreManager:
    """向量数据库管理器"""

    def __init__(self, collection_name: str = "history_knowledge"):
        self.settings = get_settings()
        self.collection_name = collection_name

        self._embeddings = None
        self._vectorstore = None
        self._bm25 = None  # BM25 词法索引懒加载缓存（hybrid 检索模式使用）
        # 精确稠密检索缓存：全库向量+文档+元数据（见 _all_records）
        self._exact_cache = None

    @property
    def embeddings(self):
        """延迟加载本地 Embedding 模型 (HuggingFace, 免费)"""
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            # 优先用本地缓存快照路径，避免加载时联网校验挂起
            self._embeddings = HuggingFaceEmbeddings(
                model_name=_resolve_embedding_model(),
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self._embeddings

    @property
    def vectorstore(self):
        """延迟加载向量存储"""
        if self._vectorstore is None:
            from langchain_chroma import Chroma

            db_path = Path(self.settings.vector_db_path)
            db_path.mkdir(parents=True, exist_ok=True)

            self._vectorstore = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=str(db_path),
            )
        return self._vectorstore

    def split_documents(
        self,
        documents: List[Document],
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> List[Document]:
        """结构感知分块。

        现状：多数史料（persona 摘要与 gushiwen 原文节选）较短，天然整篇一块；
        长文档（后续扩充的完整传记/原文）按中文语义边界切分并保留元数据
        （RecursiveCharacterTextSplitter 会传播 metadata 到每个 chunk）。
        阈值：≤ chunk_size×1.2 保持整篇不切，避免把已很短的传记切碎成
        无上下文的碎片。
        """
        threshold = chunk_size * 1.2
        short = [d for d in documents if len(d.page_content) <= threshold]
        long_docs = [d for d in documents if len(d.page_content) > threshold]

        result = list(short)
        if long_docs:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
            )
            result.extend(splitter.split_documents(long_docs))
        return result

    def add_documents(
        self,
        documents: List[Document],
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> int:
        """添加文档到向量库（追加语义，不清理已有数据）。

        注意：Chroma 每次入库生成新 ID，重复调用会把同一批文档重复写入。
        需要"清空重建"请使用 rebuild()，而不是在业务代码里循环 add_documents。
        """
        if not documents:
            return 0

        split_docs = self.split_documents(documents, chunk_size, chunk_overlap)
        self.vectorstore.add_documents(split_docs)
        self._exact_cache = None  # 全库变了，精确检索缓存失效
        return len(split_docs)

    def rebuild(
        self,
        documents: List[Document],
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> int:
        """清空并重建向量库（幂等：重复构建不会翻倍）。

        为什么：add_documents 每次生成新 ID，若脚本/初始化逻辑多次调用，
        旧数据不会被覆盖而是一直累积。先 delete_collection() 再入库，
        保证多次构建结果一致。注意这会丢弃已有向量库（如需保留请勿调用）。
        """
        self.clear()  # 删除旧 collection，self._vectorstore 置空以便重建
        logger.info("已清空旧向量库，开始重建...")
        return self.add_documents(documents, chunk_size, chunk_overlap)

    # ── 精确稠密检索（确定性）──
    # Chroma 1.5.8 默认 Rust HNSW 近似索引跨进程重建图（随机种子），得分在
    # 决策边界附近会进程间抖动（如"大运河"题 隋炀帝 0.877 vs 林则徐 0.90），
    # 导致测试/回答不稳定。本库仅 ~1000 条 × 512 维，全量精确平方 L2（与
    # Chroma/hnswlib 同口径）毫秒级且完全确定——稠密检索统一走这里。

    @property
    def _all_records(self) -> Optional[Dict]:
        """一次性取回全库向量+文档+元数据，缓存供精确检索使用。

        返回 None 表示取回失败（向量库未就绪等），调用方回退 Chroma。
        """
        if self._exact_cache is None:
            try:
                data = self.vectorstore._collection.get(
                    include=["embeddings", "documents", "metadatas"]
                )
            except Exception as e:
                logger.warning("全量取回失败，回退 Chroma 近似检索: %s", e)
                return None
            self._exact_cache = {
                "ids": data["ids"],
                "embeddings": np.asarray(data["embeddings"], dtype="float32"),
                "documents": data["documents"],
                "metadatas": data["metadatas"],
            }
        return self._exact_cache

    def _exact_search_with_score(
        self,
        query: str,
        k: int,
        filter: Optional[Dict] = None,
    ) -> Optional[List[tuple]]:
        """精确稠密检索：过滤元数据后按平方 L2 升序取 top-k。

        返回 [(Document, squared_l2)]；None 表示精确路径不可用（回退 Chroma）。
        """
        rec = self._all_records
        if rec is None or not rec["ids"]:
            return None
        try:
            qv = np.asarray(
                self.embeddings.embed_query(query), dtype="float32"
            )
        except Exception as e:
            logger.warning("查询向量化失败，回退 Chroma 近似检索: %s", e)
            return None
        vecs = rec["embeddings"]
        if filter:
            keep = [
                i for i, m in enumerate(rec["metadatas"])
                if _metadata_match(m or {}, filter)
            ]
            if not keep:
                return []
            vecs = vecs[keep]
            idxs = keep
        else:
            idxs = list(range(len(rec["ids"])))
        diff = vecs - qv[None, :]
        # 平方 L2（与 Chroma hnswlib l2 同口径；阈值 0.70/0.90/比值 1.25 按此标定）
        sq = np.einsum("ij,ij->i", diff, diff)
        order = np.argsort(sq, kind="stable")[:k]
        # order 是过滤后数组内的位置，idxs 映射回全库下标；距离取 sq[pos]
        # （pos=argsort 位置，而非返回序号——否则分数错位，路径决策失真）。
        return [
            (
                Document(
                    page_content=rec["documents"][idxs[pos]],
                    metadata=rec["metadatas"][idxs[pos]] or {},
                ),
                float(sq[pos]),
            )
            for pos in order
        ]

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict] = None,
    ) -> List[Document]:
        """相似度搜索（精确路径，确定性）"""
        exact = self._exact_search_with_score(query, k, filter)
        if exact is not None:
            return [d for d, _ in exact]
        return self.vectorstore.similarity_search(query, k=k, filter=filter)

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict] = None,
    ) -> List[tuple]:
        """带分数的相似度搜索（分数为平方 L2 距离，越小越相关，确定性）"""
        exact = self._exact_search_with_score(query, k, filter)
        if exact is not None:
            return exact
        return self.vectorstore.similarity_search_with_score(
            query, k=k, filter=filter
        )

    def search_by_character_with_score(
        self,
        query: str,
        character: str,
        k: int = 3,
        extra_filter: Optional[Dict] = None,
    ) -> List[tuple]:
        """按人物过滤检索（带距离分数，越小越相关）。

        extra_filter: 追加元数据过滤条件（如 {"doc_type": "historical"}），
        供 PERSONA_FALLBACK=off 严格模式排除 persona 文档；多条件经
        merge_filters 合并成 Chroma 合法的 $and 表达式。
        """
        filt = merge_filters({"character": character}, extra_filter)
        exact = self._exact_search_with_score(query, k, filt)
        if exact is not None:
            return exact
        return self.vectorstore.similarity_search_with_score(
            query,
            k=k,
            filter=filt,
        )

    def search_by_character(
        self,
        query: str,
        character: str,
        k: int = 3,
    ) -> List[Document]:
        """按人物搜索"""
        return self.similarity_search(
            query,
            k=k,
            filter={"character": character}
        )

    def mmr_search(
        self,
        query: str,
        k: int = 3,
        fetch_k: int = 20,
        filter: Optional[Dict] = None,
    ) -> List[Document]:
        """MMR（最大边际相关）重排检索，供实验/评估使用。

        为什么需要：纯相似度检索可能把语义相近但冗余的片段都召回，
        MMR 在「与查询相关」和「与已选结果互异」之间取平衡，结果更多样。
        默认不改变现有检索路径（_retrieve_knowledge 仍用纯相似度），
        需要时通过 fetch_k 控制候选池大小、k 控制最终返回条数。
        """
        return self.vectorstore.max_marginal_relevance_search(
            query,
            k=k,
            fetch_k=fetch_k,
            filter=filter,
        )

    # ── 混合检索（稠密 + BM25 词法，RRF 融合召回）──

    def get_all_chunks(self) -> List[Document]:
        """取回向量库全部 chunk（文本+元数据），供 BM25 索引等全库计算使用。

        Chroma 的 get() 直接拿全部记录，全库（千条量级）开销可忽略。
        """
        data = self.vectorstore.get(include=["documents", "metadatas"])
        docs = []
        for text, meta in zip(data["documents"], data["metadatas"]):
            docs.append(Document(page_content=text, metadata=meta or {}))
        return docs

    def _bm25_index(self):
        """懒加载 BM25 词法索引（与当前向量库 chunk 一致）并缓存。

        注意：向量库重建（rebuild/clear）后索引会过期，这里不做失效追踪——
        由重建方（build_vector_db / ingest --rebuild）重新实例化 manager 即可。
        """
        if self._bm25 is None:
            from src.retrievers.bm25 import BM25Index

            self._bm25 = BM25Index().build(self.get_all_chunks())
        return self._bm25

    def hybrid_search_with_score(
        self,
        query: str,
        k: int = 3,
        fetch_k: int = 30,
        filter: Optional[Dict] = None,
        bm25_k: Optional[int] = None,
    ) -> List[tuple]:
        """稠密向量 + BM25 词法的 RRF 融合召回（混合检索）。

        流程：稠密侧取 top(fetch_k)（带距离）↔ BM25 侧取 top(bm25_k，默认
        fetch_k)，两侧按 RRF 常数融合成候选池，返回按融合相关度降序的
        [(doc, dense_distance_or_None), ...]。

        - 命中两侧的 doc 携带稠密距离；BM25 独有命中 dense_distance=None
          （只作候选池扩充，不参与路径决策——决策仍基于稠密距离，见
          history_agent._retrieve_knowledge）；
        - filter: {"character": name} 时两侧都按人物过滤（稠密侧走 Chroma
          元数据过滤，BM25 侧走 filter_char）；
        - 融合 RRF 常数取 settings.hybrid_rrf_k（默认 60），与重排器内部融合
          常数同口径，可 .env 覆盖。

        为什么需要：纯稠密对精确人名/罕见词/多人物枚举查询召回不足，词法
        通道能把 dense 漏掉的片段拉回候选池（池内再经 reranker 精排）。
        """
        rrf_k = self.settings.hybrid_rrf_k
        bm25_k = bm25_k if bm25_k is not None else fetch_k

        def _key(d) -> tuple:
            """同一底层 chunk 在稠密（Chroma 返回）与 BM25（get_all_chunks 重建）
            两侧是不同对象，不能用 id() 去重——以内容+元数据作键合并两侧命中，
            保证同一 chunk 只出现一次（保留稠密一侧的距离）。"""
            return (
                d.page_content,
                str(d.metadata.get("character", "")),
                str(d.metadata.get("title", "")),
            )

        dense = self.similarity_search_with_score(query, k=fetch_k, filter=filter)
        bm25_char, bm25_chars, bm25_doc_type = _extract_filter_terms(filter)
        bm25 = self._bm25_index().search(
            query,
            k=bm25_k,
            filter_char=bm25_char,
            filter_chars=bm25_chars,
            filter_doc_type=bm25_doc_type,
        )

        # RRF 融合（与 reranker.HybridReranker 同口径的排名融合）
        dense_by_key = {_key(d): (d, s) for d, s in dense}
        bm25_by_key = {_key(d): (d, s) for d, s in bm25}
        fused: dict = {}
        for rank, (d, _s) in enumerate(dense):
            key = _key(d)
            fused[key] = fused.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
        for rank, (d, _s) in enumerate(bm25):
            key = _key(d)
            fused[key] = fused.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)

        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
        # 双侧命中的取稠密版本（带距离），BM25 独有命中 dense_distance=None
        result = []
        for key, _score in ranked[:k]:
            doc, s = dense_by_key.get(key) or bm25_by_key[key]
            result.append((doc, s))
        return result

    def get_retriever(self, k: int = 4):
        """获取检索器"""
        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )

    def get_document_count(self) -> int:
        """获取文档数量"""
        try:
            return self.vectorstore._collection.count()
        except Exception:
            # 向量库不存在/未初始化时返回 0，由调用方决定是否触发首次构建
            return 0

    def clear(self):
        """清空向量库"""
        self.vectorstore.delete_collection()
        self._vectorstore = None
        self._exact_cache = None  # 集合已删，缓存失效


def load_knowledge_files(knowledge_dir: str = "./data/knowledge") -> List[Document]:
    """加载知识库文件（多格式：txt/md/html/pdf/docx/xml/json/csv/tsv/xlsx）。

    解析统一走 document_loader.load_documents（元数据/前置头/别名与既有 txt
    语义一致）；*.txt 行为与旧版逐字节等价，其它格式按扩展名分发。
    """
    from src.retrievers.document_loader import SUPPORTED_EXTS, load_documents

    documents = []
    knowledge_path = Path(knowledge_dir)

    if not knowledge_path.exists():
        logger.warning(f"知识库目录不存在: {knowledge_dir}")
        return documents

    files = sorted(
        p for p in knowledge_path.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )
    for file_path in files:
        try:
            docs = load_documents(file_path)
            if docs:
                documents.extend(docs)
                logger.info(f"  加载: {file_path.name} → {len(docs)} 篇")
            else:
                logger.info(f"  跳过（无有效文档）: {file_path.name}")
        except Exception as e:
            logger.error(f"  加载失败 {file_path}: {e}")

    return documents


def build_vector_store():
    """构建向量数据库

    注意：本脚本每次运行都会【清空并重建】向量库（见 VectorStoreManager.rebuild），
    因此可重复执行且不会重复入库；但请勿在已有自定义向量库时误跑本脚本。
    """
    logger.info("=" * 60)
    logger.info("构建历史知识向量数据库（注意：将清空现有向量库后重建）")
    logger.info("=" * 60)

    logger.info("\n[1] 加载知识文件...")
    documents = load_knowledge_files()
    logger.info(f"共加载 {len(documents)} 个文档")

    if not documents:
        logger.error("没有文档，请先添加知识文件到 data/knowledge/ 目录")
        return

    logger.info("\n[2] 构建向量数据库...")
    vs_manager = VectorStoreManager()
    count = vs_manager.rebuild(documents)
    logger.info(f"已添加 {count} 个文本块到向量库")

    logger.info("\n[3] 验证知识库...")
    total = vs_manager.get_document_count()
    logger.info(f"向量库中共有 {total} 个文档")

    logger.info("\n[4] 测试检索...")
    test_queries = [
        "秦始皇统一六国",
        "李白的诗歌",
        "赤壁之战",
    ]

    for query in test_queries:
        logger.info(f"\n查询: {query}")
        results = vs_manager.similarity_search(query, k=2)
        for i, doc in enumerate(results, 1):
            logger.info(f"  [{i}] {doc.metadata.get('title', '未知')}: {doc.page_content[:60]}...")

    logger.info("\n" + "=" * 60)
    logger.info("知识库构建完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    build_vector_store()
