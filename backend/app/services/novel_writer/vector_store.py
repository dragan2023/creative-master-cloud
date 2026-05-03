"""
项目向量存储服务
管理项目自有向量库，存储历史章节用于检索

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
from typing import List, Dict, Any, Optional

from app.core.logger import get_logger
from app.core.vector_store import get_vector_store


class ProjectVectorStore:
    """项目向量存储服务

    每个项目有独立的向量库，存储：
    1. 已完成章节的分段内容
    2. 用于后续章节的上下文检索
    """

    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or "./data/novel_vectorstores"
        self.logger = get_logger("project_vector_store")
        # 延迟加载向量库（避免初始化时阻塞）
        self._vector_store = None
    
    @property
    def vector_store(self):
        """延迟加载向量库（避免初始化时阻塞）"""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    def get_collection_name(self, project_id: int) -> str:
        """获取项目的集合名称（统一命名规则）"""
        return f"project_{project_id}"

    async def initialize_project_store(self, project_id: int) -> bool:
        """
        初始化项目向量库

        Args:
            project_id: 项目ID

        Returns:
            是否成功
        """
        try:
            collection_name = self.get_collection_name(project_id)

            # 创建集合（如果不存在）
            self.vector_store.get_or_create_collection(collection_name)

            self.logger.info(f"项目向量库初始化完成")
            return True

        except Exception as e:
            self.logger.error(f"初始化项目向量库失败: {str(e)}")
            return False

    async def add_chapter(
        self,
        project_id: int,
        chapter_number: int,
        chapter_title: str,
        chapter_content: str
    ) -> bool:
        """
        添加章节到向量库

        Args:
            project_id: 项目ID
            chapter_number: 章节号
            chapter_title: 章节标题
            chapter_content: 章节内容

        Returns:
            是否成功
        """
        try:
            collection_name = self.get_collection_name(project_id)

            # 分段
            chunks = self._split_content(chapter_content)

            # 准备文档和元数据
            documents = []
            metadatas = []
            ids = []

            for i, chunk in enumerate(chunks):
                doc_id = f"chapter_{chapter_number}_chunk_{i}"
                documents.append(chunk)
                metadatas.append({
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "chunk_index": i,
                    "source": f"第{chapter_number}章"
                })
                ids.append(doc_id)

            # 添加到向量库
            self.vector_store.add_documents(
                collection_name=collection_name,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

            self.logger.info(f"章节添加到向量库: 第{chapter_number}章, {len(chunks)}个分段")
            return True

        except Exception as e:
            self.logger.error(f"添加章节到向量库失败: {str(e)}")
            return False

    async def retrieve(
        self,
        collection_name: str,
        query: str,
        n_results: int = 2
    ) -> List[Dict[str, Any]]:
        """
        从向量库检索相关内容

        Args:
            collection_name: 集合名称
            query: 查询文本
            n_results: 返回结果数量

        Returns:
            检索结果列表
        """
        try:
            results = self.vector_store.query(
                collection_name=collection_name,
                query_texts=[query],
                n_results=n_results
            )

            formatted_results = []

            if results and results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results.get("metadatas", [[]])[
                        0][i] if results.get("metadatas") else {}
                    formatted_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "distance": results.get("distances", [[]])[0][i] if results.get("distances") else None
                    })

            return formatted_results

        except Exception as e:
            self.logger.error(f"向量检索失败: {str(e)}")
            return []

    async def delete_project_store(self, project_id: int) -> bool:
        """
        删除项目向量库

        Args:
            project_id: 项目ID

        Returns:
            是否成功
        """
        try:
            collection_name = self.get_collection_name(project_id)
            self.vector_store.delete_collection(collection_name)

            self.logger.info(f"项目向量库已删除")
            return True

        except Exception as e:
            self.logger.error(f"删除项目向量库失败: {str(e)}")
            return False

    def _split_content(
        self,
        content: str,
        max_chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """
        分段内容

        Args:
            content: 原始内容
            max_chunk_size: 最大分段大小（字符）
            overlap: 重叠大小

        Returns:
            分段列表
        """
        if len(content) <= max_chunk_size:
            return [content]

        chunks = []

        # 按段落分割
        paragraphs = content.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) <= max_chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        # 合并过小的分段
        merged_chunks = []
        for chunk in chunks:
            if merged_chunks and len(chunk) < 100:
                merged_chunks[-1] += "\n\n" + chunk
            else:
                merged_chunks.append(chunk)

        return merged_chunks

    def get_collection_stats(self, project_id: int) -> Dict[str, Any]:
        """
        获取项目向量库统计信息

        Args:
            project_id: 项目ID

        Returns:
            统计信息
        """
        try:
            collection_name = self.get_collection_name(project_id)
            count = self.vector_store.count_documents(collection_name)

            return {
                "collection_name": collection_name,
                "document_count": count,
                "status": "ready"
            }

        except Exception as e:
            return {
                "collection_name": self.get_collection_name(project_id),
                "document_count": 0,
                "status": "error",
                "error": str(e)
            }
