#!/usr/bin/env python
"""
构建向量数据库脚本
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrievers.vector_store import build_vector_store

if __name__ == "__main__":
    build_vector_store()
