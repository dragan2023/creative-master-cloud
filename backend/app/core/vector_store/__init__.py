# -*- coding: utf-8 -*-
"""
向量数据库配置
使用 ChromaDB 存储和检索向量数据

重要说明：
- ChromaDB 1.5.0 使用 PersistentClient 进行持久化
- HNSW 索引在内存中缓存，可能导致多进程/多实例数据不一致
- 需要在写入后验证数据完整性，确保数据正确持久化
"""
# [2026-03-27] 多Agent重构: Embedding模型从 all-MiniLM-L6-v2 升级为 BAAI/bge-small-zh-v1.5（中文优化）
# 使用pysqlite3替代系统sqlite（解决ChromaDB版本要求）- 必须在导入chromadb之前执行
import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass  # 如果pysqlite3不可用，使用系统sqlite

# 在导入 chromadb 之前设置环境变量
from app.core.vector_store._embedding import setup_chroma_environment
setup_chroma_environment()

# 导入核心类
from app.core.vector_store._store import VectorStore

# 全局向量存储实例
vector_store = VectorStore()


def get_vector_store() -> VectorStore:
    """获取向量存储实例"""
    return vector_store


__all__ = ["VectorStore", "vector_store", "get_vector_store"]
