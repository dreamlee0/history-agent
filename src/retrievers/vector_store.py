"""
向量数据库管理器 - RAG知识库核心
支持历史人物资料的存储、检索和溯源
使用智谱AI Embedding
"""
import os
import sys
from typing import List, Optional, Dict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings


class ZhipuEmbeddings:
    """智谱AI Embedding封装"""

    def __init__(self, api_key: str, model: str = "embedding-3"):
        self.api_key = api_key
        self.model = model
        try:
            from zhipuai import ZhipuAI
            self.client = ZhipuAI(api_key=api_key)
        except ImportError:
            raise ImportError("请安装智谱AI SDK: pip install zhipuai")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文档"""
        embeddings = []
        for text in texts:
            result = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            embeddings.append(result.data[0].embedding)
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """嵌入查询"""
        result = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return result.data[0].embedding


class VectorStoreManager:
    """向量数据库管理器"""

    def __init__(self, collection_name: str = "history_knowledge"):
        self.settings = get_settings()
        self.collection_name = collection_name

        self._embeddings = None
        self._vectorstore = None

    @property
    def embeddings(self):
        """延迟加载embeddings"""
        if self._embeddings is None:
            self._embeddings = ZhipuEmbeddings(
                api_key=self.settings.zhipu_api_key,
                model=self.settings.embedding_model
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
        """添加文档到向量库"""
        if not documents:
            return 0

        split_docs = self.split_documents(documents, chunk_size, chunk_overlap)
        self.vectorstore.add_documents(split_docs)
        return len(split_docs)

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
    ) -> List[tuple]:
        """带分数的相似度搜索"""
        return self.vectorstore.similarity_search_with_score(query, k=k)

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

    def search_by_category(
        self,
        query: str,
        category: str,
        k: int = 3,
    ) -> List[Document]:
        """按分类搜索"""
        return self.vectorstore.similarity_search(
            query,
            k=k,
            filter={"category": category}
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
        except:
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
        print(f"知识库目录不存在: {knowledge_dir}")
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
                    character = line[5:].strip()
                elif line.startswith("【分类】"):
                    category = line[5:].strip()

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
            print(f"  加载: {file_path.name}")

        except Exception as e:
            print(f"  加载失败 {file_path}: {e}")

    return documents


def build_vector_store():
    """构建向量数据库"""
    print("=" * 60)
    print("构建历史知识向量数据库")
    print("=" * 60)

    print("\n[1] 加载知识文件...")
    documents = load_knowledge_files()
    print(f"共加载 {len(documents)} 个文档")

    if not documents:
        print("没有文档，请先添加知识文件到 data/knowledge/ 目录")
        return

    print("\n[2] 构建向量数据库...")
    vs_manager = VectorStoreManager()
    count = vs_manager.add_documents(documents)
    print(f"已添加 {count} 个文本块到向量库")

    print("\n[3] 验证知识库...")
    total = vs_manager.get_document_count()
    print(f"向量库中共有 {total} 个文档")

    print("\n[4] 测试检索...")
    test_queries = [
        "秦始皇统一六国",
        "李白的诗歌",
        "赤壁之战",
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        results = vs_manager.similarity_search(query, k=2)
        for i, doc in enumerate(results, 1):
            print(f"  [{i}] {doc.metadata.get('title', '未知')}: {doc.page_content[:60]}...")

    print("\n" + "=" * 60)
    print("知识库构建完成！")
    print("=" * 60)


if __name__ == "__main__":
    build_vector_store()
