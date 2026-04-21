"""文档加载模块"""
from .document_loader import (
    DocumentLoaderManager,
    PDFLoader,
    DocxLoader,
    TextFileLoader,
    WebLoader,
)

__all__ = [
    "DocumentLoaderManager",
    "PDFLoader",
    "DocxLoader",
    "TextFileLoader",
    "WebLoader",
]
