"""
知识库检索工具
从向量数据库中检索相关知识，集成 GraphRAG 增强

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import List, Dict, Any, Optional

from app.core.vector_store import vector_store, get_vector_store
from app.tools.graph_rag import get_graph_rag, GraphRAG
from app.core.logger import get_logger

logger = get_logger(__name__)


class KnowledgeRetrievalTool:
    """知识库检索工具"""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.graph_rag = get_graph_rag()

    async def retrieve(
        self,
        collection_name: str,
        query: str,
        n_results: int = 5,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        检索知识库

        Args:
            collection_name: 集合名称
            query: 查询文本
            n_results: 返回结果数量
            where_filter: 过滤条件

        Returns:
            检索结果列表
        """
        try:
            results = self.vector_store.query(
                collection_name=collection_name,
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )

            formatted_results = []

            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    result = {
                        "content": doc,
                        "metadata": {}
                    }

                    if results.get("metadatas") and results["metadatas"][0]:
                        result["metadata"] = results["metadatas"][0][i]

                    if results.get("distances") and results["distances"][0]:
                        result["distance"] = results["distances"][0][i]

                    formatted_results.append(result)

            return formatted_results

        except ConnectionError as e:
            logger.error(f"向量数据库连接失败: {e}")
            return [{"error": f"向量数据库连接失败，请检查ChromaDB服务状态"}]
        except ValueError as e:
            logger.error(f"检索参数错误: {e}")
            return [{"error": f"检索参数错误: {str(e)}"}]
        except Exception as e:
            logger.error(f"知识库检索异常: {e}", exc_info=True)
            return [{"error": f"检索失败: {str(e)}"}]

    async def retrieve_with_context(
        self,
        collection_name: str,
        query: str,
        n_results: int = 3
    ) -> str:
        """
        检索并格式化为上下文文本

        Args:
            collection_name: 集合名称
            query: 查询文本
            n_results: 返回结果数量

        Returns:
            格式化的上下文文本
        """
        results = await self.retrieve(collection_name, query, n_results)

        if not results:
            return "知识库中未找到相关内容。"

        if results and "error" in results[0]:
            return f"知识库检索出错: {results[0]['error']}"

        context_parts = ["以下是知识库中检索到的相关内容：\n"]

        for i, result in enumerate(results, 1):
            content = result.get("content", "")
            source = result.get("metadata", {}).get("source", "未知来源")
            context_parts.append(f"[参考文档 {i}] (来源: {source})\n{content}\n")

        return "\n".join(context_parts)

    async def retrieve_with_graph_rag(
        self,
        collection_name: str,
        query: str,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        使用 GraphRAG 增强检索

        Args:
            collection_name: 集合名称
            query: 查询文本
            n_results: 返回结果数量

        Returns:
            增强检索结果
        """
        return await self.graph_rag.retrieve_with_graph(
            collection_name=collection_name,
            query=query,
            n_results=n_results
        )

    async def retrieve_with_graph_context(
        self,
        collection_name: str,
        query: str,
        n_results: int = 3
    ) -> str:
        """
        使用 GraphRAG 增强检索并格式化为上下文

        Args:
            collection_name: 集合名称
            query: 查询文本
            n_results: 返回结果数量

        Returns:
            格式化的上下文文本
        """
        result = await self.retrieve_with_graph_rag(collection_name, query, n_results)
        return self.graph_rag.format_for_context(result)

    async def add_document(
        self,
        collection_name: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        添加文档到知识库

        Args:
            collection_name: 集合名称
            content: 文档内容
            metadata: 元数据

        Returns:
            文档ID
        """
        import uuid
        doc_id = str(uuid.uuid4())

        # 索引到 GraphRAG
        graph_metadata = await self.graph_rag.index_document(
            collection_name, doc_id, content
        )

        # 合并元数据
        merged_metadata = {**(metadata or {}), **graph_metadata}

        self.vector_store.add_documents(
            collection_name=collection_name,
            documents=[content],
            metadatas=[merged_metadata],
            ids=[doc_id]
        )

        return doc_id

    async def add_documents_batch(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        批量添加文档

        Args:
            collection_name: 集合名称
            documents: 文档列表
            metadatas: 元数据列表

        Returns:
            文档ID列表
        """
        import uuid
        try:
            ids = [str(uuid.uuid4()) for _ in documents]

            self.vector_store.add_documents(
                collection_name=collection_name,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

            return ids
        except ConnectionError as e:
            logger.error(f"批量添加文档时向量数据库连接失败: {e}")
            raise
        except ValueError as e:
            logger.error(f"批量添加文档参数错误: {e}")
            raise
        except Exception as e:
            logger.error(f"批量添加文档异常: {e}", exc_info=True)
            raise

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        获取集合统计信息

        Args:
            collection_name: 集合名称

        Returns:
            统计信息
        """
        try:
            count = self.vector_store.count_documents(collection_name)
            return {
                "collection_name": collection_name,
                "document_count": count
            }
        except Exception:
            return {
                "collection_name": collection_name,
                "document_count": 0,
                "error": "集合不存在"
            }


# 全局知识库检索工具实例
knowledge_retrieval_tool = KnowledgeRetrievalTool()


def get_knowledge_retrieval_tool() -> KnowledgeRetrievalTool:
    """获取知识库检索工具实例"""
    return knowledge_retrieval_tool
