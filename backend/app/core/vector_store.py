"""
向量数据库配置
使用 ChromaDB 存储和检索向量数据
"""
import chromadb
from typing import Optional, List
import os

from app.core.config import get_settings


def _setup_chroma_environment():
    """设置 ChromaDB 环境变量（模型缓存目录等）"""
    settings = get_settings()

    # 设置模型缓存目录到项目文件夹
    model_cache_dir = settings.get_chroma_model_cache_dir()
    os.environ["CHROMA_MODEL_CACHE_DIR"] = model_cache_dir

    # 设置代理（如果配置了）
    if settings.HTTPS_PROXY:
        os.environ["HTTPS_PROXY"] = settings.HTTPS_PROXY
    if settings.HTTP_PROXY:
        os.environ["HTTP_PROXY"] = settings.HTTP_PROXY


# 在模块加载时设置环境
_setup_chroma_environment()


class VectorStore:
    """向量数据库管理类"""

    def __init__(self):
        self._client: Optional[chromadb.Client] = None
        self._collections: dict = {}

    @property
    def client(self) -> chromadb.Client:
        """获取 ChromaDB 客户端（延迟初始化）"""
        if self._client is None:
            settings = get_settings()
            persist_dir = settings.get_chroma_dir()

            # 确保目录存在
            os.makedirs(persist_dir, exist_ok=True)

            # 使用新的 PersistentClient API (ChromaDB 1.0+)
            self._client = chromadb.PersistentClient(path=persist_dir)
        return self._client

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """
        获取或创建集合

        Args:
            name: 集合名称

        Returns:
            Collection 实例
        """
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}
            )
        return self._collections[name]

    def delete_collection(self, name: str) -> None:
        """
        删除集合

        Args:
            name: 集合名称
        """
        try:
            self.client.delete_collection(name=name)
            if name in self._collections:
                del self._collections[name]
        except Exception:
            pass

    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None
    ) -> None:
        """
        添加文档到向量数据库

        Args:
            collection_name: 集合名称
            documents: 文档列表
            metadatas: 元数据列表
            ids: 文档ID列表
        """
        import uuid

        collection = self.get_or_create_collection(collection_name)

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]

        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def query(
        self,
        collection_name: str,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[dict] = None
    ) -> dict:
        """
        查询相似文档

        Args:
            collection_name: 集合名称
            query_texts: 查询文本列表
            n_results: 返回结果数量
            where: 过滤条件

        Returns:
            查询结果
        """
        collection = self.get_or_create_collection(collection_name)

        return collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where
        )

    def count_documents(self, collection_name: str) -> int:
        """
        获取文档数量

        Args:
            collection_name: 集合名称

        Returns:
            文档数量
        """
        collection = self.get_or_create_collection(collection_name)
        return collection.count()


# 全局向量存储实例
vector_store = VectorStore()


def get_vector_store() -> VectorStore:
    """获取向量存储实例"""
    return vector_store
