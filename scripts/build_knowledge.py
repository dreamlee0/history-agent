"""
构建知识库脚本
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from langchain_core.documents import Document

from src.retrievers import VectorStoreManager


def load_knowledge_files(knowledge_dir: str = "./data/knowledge") -> list[Document]:
    """加载知识库文件"""
    documents = []
    knowledge_path = Path(knowledge_dir)

    if not knowledge_path.exists():
        print(f"知识库目录不存在: {knowledge_dir}")
        return documents

    for file_path in knowledge_path.glob("*.txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        doc = Document(
            page_content=content,
            metadata={"source": file_path.name}
        )
        documents.append(doc)
        print(f"加载文件: {file_path.name}")

    return documents


def main():
    """主函数"""
    print("=" * 50)
    print("构建历史知识库")
    print("=" * 50)

    # 加载文档
    print("\n1. 加载知识文件...")
    documents = load_knowledge_files()
    print(f"共加载 {len(documents)} 个文档")

    if not documents:
        print("没有文档，请先运行 crawl_history.py 爬取数据")
        return

    # 构建向量库
    print("\n2. 构建向量数据库...")
    vector_store = VectorStoreManager()
    count = vector_store.add_documents(documents)
    print(f"已添加 {count} 个文本块到向量库")

    # 验证
    print("\n3. 验证知识库...")
    total = vector_store.get_document_count()
    print(f"向量库中共有 {total} 个文档")

    # 测试检索
    print("\n4. 测试检索...")
    test_queries = [
        "秦始皇统一六国",
        "诸葛亮的北伐",
        "李白的诗歌风格",
    ]
    for query in test_queries:
        results = vector_store.similarity_search(query, k=2)
        print(f"\n查询: {query}")
        for i, doc in enumerate(results, 1):
            print(f"  [{i}] {doc.metadata.get('source', '未知')}: {doc.page_content[:100]}...")

    print("\n知识库构建完成！")


if __name__ == "__main__":
    main()
