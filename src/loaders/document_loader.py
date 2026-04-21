"""
文档加载器 - 支持PDF、Word、TXT、网页等多种格式
"""
from typing import List, Optional
from pathlib import Path
from abc import ABC, abstractmethod

from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    WebBaseLoader,
    UnstructuredHTMLLoader,
)
from langchain_core.documents import Document


class BaseLoader(ABC):
    """文档加载器基类"""

    @abstractmethod
    def load(self, source: str) -> List[Document]:
        """加载文档"""
        pass


class PDFLoader(BaseLoader):
    """PDF文档加载器"""

    def load(self, source: str) -> List[Document]:
        loader = PyPDFLoader(source)
        return loader.load()


class DocxLoader(BaseLoader):
    """Word文档加载器"""

    def load(self, source: str) -> List[Document]:
        loader = Docx2txtLoader(source)
        return loader.load()


class TextFileLoader(BaseLoader):
    """文本文件加载器"""

    def load(self, source: str) -> List[Document]:
        loader = TextLoader(source, encoding="utf-8")
        return loader.load()


class WebLoader(BaseLoader):
    """网页加载器"""

    def load(self, source: str) -> List[Document]:
        loader = WebBaseLoader(source)
        return loader.load()


class DocumentLoaderManager:
    """文档加载管理器"""

    def __init__(self):
        self.loaders = {
            ".pdf": PDFLoader(),
            ".docx": DocxLoader(),
            ".doc": DocxLoader(),
            ".txt": TextFileLoader(),
            ".md": TextFileLoader(),
            ".html": WebLoader(),
        }

    def load_file(self, file_path: str) -> List[Document]:
        """加载单个文件"""
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix not in self.loaders:
            raise ValueError(f"不支持的文件格式: {suffix}")

        return self.loaders[suffix].load(file_path)

    def load_directory(self, dir_path: str) -> List[Document]:
        """加载目录下所有文档"""
        documents = []
        dir_path = Path(dir_path)

        for file_path in dir_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in self.loaders:
                try:
                    docs = self.load_file(str(file_path))
                    # 添加元数据
                    for doc in docs:
                        doc.metadata["source_file"] = str(file_path)
                    documents.extend(docs)
                except Exception as e:
                    print(f"加载文件失败 {file_path}: {e}")

        return documents

    def load_url(self, url: str) -> List[Document]:
        """加载网页内容"""
        loader = WebLoader()
        return loader.load(url)

    def load_urls(self, urls: List[str]) -> List[Document]:
        """批量加载网页"""
        documents = []
        for url in urls:
            try:
                docs = self.load_url(url)
                for doc in docs:
                    doc.metadata["source_url"] = url
                documents.extend(docs)
            except Exception as e:
                print(f"加载网页失败 {url}: {e}")
        return documents
