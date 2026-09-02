"""
多格式文档摄取脚本：把指定文件/目录解析入库。

格式：txt / md / html / pdf / docx / xml / json / csv / tsv / xlsx
（解析见 src/retrievers/document_loader.py）。

模式：
  append  把 --src 下的文档追加进现有向量库（幂等：已入库的同名文件跳过，
          不会重复写入；见 dedup 说明）；
  rebuild 用 data/knowledge 全量重建向量库（先清空再重建，幂等）。

用法：
  python scripts/ingest_documents.py --src data/documents_sample --mode append
  python scripts/ingest_documents.py --src data/documents_sample/sample.pdf --mode append
  python scripts/ingest_documents.py --mode rebuild
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger import get_logger
from src.retrievers.document_loader import load_documents
from src.retrievers.vector_store import VectorStoreManager, load_knowledge_files

logger = get_logger("ingest")


def _collect_docs(src: Path):
    """收集 --src 下的所有文档（文件或目录递归）。"""
    if src.is_file():
        return load_documents(src)
    docs = []
    for p in sorted(src.rglob("*")):
        if p.is_file():
            docs.extend(load_documents(p))
    return docs


def main():
    ap = argparse.ArgumentParser(description="多格式文档摄取")
    ap.add_argument("--src", default="data/documents_sample",
                    help="源文件或目录（默认 data/documents_sample）")
    ap.add_argument("--mode", choices=["append", "rebuild"], default="append",
                    help="append=追加现有向量库；rebuild=用 data/knowledge 全量重建")
    ap.add_argument("--chunk-size", type=int, default=500)
    ap.add_argument("--chunk-overlap", type=int, default=100)
    args = ap.parse_args()

    vs = VectorStoreManager()

    if args.mode == "rebuild":
        logger.info("模式=rebuild：用 data/knowledge 全量重建向量库（将清空现有库）")
        docs = load_knowledge_files()
        if not docs:
            logger.error("data/knowledge 无有效文档，中止重建")
            sys.exit(1)
        count = vs.rebuild(docs, args.chunk_size, args.chunk_overlap)
        logger.info("重建完成：入库 %d 个文本块，现有总数 %d", count, vs.get_document_count())
        return

    # append：追加现有向量库，按 file 元数据去重（幂等，重复运行不翻倍）
    src = Path(args.src)
    if not src.exists():
        logger.error("--src 不存在: %s", src)
        sys.exit(1)
    docs = _collect_docs(src)
    if not docs:
        logger.error("--src 未解析出任何文档: %s", src)
        sys.exit(1)

    existing_files = {d.metadata.get("file") for d in vs.get_all_chunks()}
    new_docs = [d for d in docs if d.metadata.get("file") not in existing_files]
    logger.info("解析到 %d 篇，其中 %d 篇为新文件（已按 file 元数据去重）",
                len(docs), len(new_docs))
    if not new_docs:
        logger.info("全部文件已在向量库中，无需追加")
        return

    count = vs.add_documents(new_docs, args.chunk_size, args.chunk_overlap)
    logger.info("追加完成：新增 %d 个文本块，现有总数 %d", count, vs.get_document_count())


if __name__ == "__main__":
    main()
