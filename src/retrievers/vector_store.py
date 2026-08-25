"""
向量数据库管理器 - RAG知识库核心
支持历史人物资料的存储、检索和溯源
使用本地 HuggingFace Embedding (免费，无需 API Key)
"""
import os
import sys
from typing import List, Optional, Dict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings
from src.logger import get_logger

# HuggingFace 模型下载超时设置（云端首次加载更宽容，避免慢连接直接失败）
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")

logger = get_logger("vector_store")


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
        """分割文档为小块"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
        )
        return splitter.split_documents(documents)

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

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict] = None,
    ) -> List[Document]:
        """相似度搜索"""
        return self.vectorstore.similarity_search(query, k=k, filter=filter)

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict] = None,
    ) -> List[tuple]:
        """带分数的相似度搜索（分数为距离，越小越相关）"""
        return self.vectorstore.similarity_search_with_score(
            query, k=k, filter=filter
        )

    def search_by_character_with_score(
        self,
        query: str,
        character: str,
        k: int = 3,
    ) -> List[tuple]:
        """按人物过滤检索（带距离分数，越小越相关）"""
        return self.vectorstore.similarity_search_with_score(
            query,
            k=k,
            filter={"character": character},
        )

    def search_by_character(
        self,
        query: str,
        character: str,
        k: int = 3,
    ) -> List[Document]:
        """按人物搜索"""
        return self.vectorstore.similarity_search(
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


def load_knowledge_files(knowledge_dir: str = "./data/knowledge") -> List[Document]:
    """加载知识库文件"""
    documents = []
    knowledge_path = Path(knowledge_dir)

    if not knowledge_path.exists():
        logger.warning(f"知识库目录不存在: {knowledge_dir}")
        return documents

    for file_path in knowledge_path.glob("*.txt"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            lines = content.split("\n")
            title = ""
            source = "未知"
            url = ""
            character = ""
            category = "biography"

            for line in lines[:10]:
                if line.startswith("# "):
                    title = line[2:].strip()
                elif line.startswith("【来源】"):
                    source = line[4:].strip()
                elif line.startswith("【URL】"):
                    url = line[5:].strip()
                elif line.startswith("【人物】"):
                    character = line[4:].strip()
                elif line.startswith("【分类】"):
                    category = line[4:].strip()

            content_start = False
            real_content = []
            for line in lines:
                if line.startswith("---"):
                    content_start = True
                    continue
                if content_start:
                    real_content.append(line)

            doc = Document(
                page_content="\n".join(real_content).strip(),
                metadata={
                    "title": title or file_path.stem,
                    "source": source,
                    "url": url,
                    "character": character,
                    "category": category,
                    "file": file_path.name
                }
            )
            documents.append(doc)
            logger.info(f"  加载: {file_path.name}")

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
