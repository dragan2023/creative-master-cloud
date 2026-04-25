"""双轨知识库 GraphRAG 检索器"""
from typing import List, Dict, Any

from app.core.logger import get_logger
from app.core.vector_store import get_vector_store
from app.core.config import get_settings

from app.tools.graph_rag.graph_rag_core import GraphRAG


class DualTrackGraphRAG:
    """双轨知识库 GraphRAG 检索器

    实现通用知识库与垂直领域知识库的协同检索。

    **重要说明**: 该类仅用于公共知识库系统，不适用于正文板块（novel）。
    正文板块的知识库是完全独立的，使用 ProjectKnowledgeBase 类进行管理。
    """

    def __init__(self, persist_dir: str = None):
        self.settings = get_settings()
        self.persist_dir = persist_dir or self.settings.get_knowledge_graph_dir()
        self.logger = get_logger("dual_track_graph_rag")

        # 通用知识库（创意理论层）
        self.general_graph_rag = GraphRAG(
            persist_dir=self.persist_dir,
            kb_category="general"
        )

        # 垂直领域知识库缓存（不包括 novel，novel 是完全独立的）
        self._vertical_rags: Dict[str, GraphRAG] = {}

        self.vector_store = get_vector_store()

    def get_vertical_rag(self, category: str) -> GraphRAG:
        """获取或创建垂直领域 GraphRAG

        **注意**: novel 类别不支持，因为正文板块知识库是完全独立的。
        """
        # 正文板块使用独立的知识库系统，不应该通过 DualTrackGraphRAG 访问
        if category == "novel":
            self.logger.warning(
                "正文板块(novel)知识库是完全独立的，不应通过DualTrackGraphRAG访问。"
                "请使用 ProjectKnowledgeBase 类进行检索。"
            )
            raise ValueError(
                "正文板块知识库不支持双轨检索。请使用 ProjectKnowledgeBase 类。"
            )

        if category not in self._vertical_rags:
            self._vertical_rags[category] = GraphRAG(
                persist_dir=self.persist_dir,
                kb_category=category
            )
        return self._vertical_rags[category]

    async def retrieve_dual_track(
        self,
        query: str,
        general_kb_id: int = None,
        vertical_kb_id: int = None,
        vertical_category: str = None,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        双轨知识库检索

        Args:
            query: 查询文本
            general_kb_id: 通用知识库ID（固定调用）
            vertical_kb_id: 垂直领域知识库ID
            vertical_category: 垂直领域类别
            n_results: 返回结果数量

        Returns:
            {
                "general_results": 通用知识库结果,
                "vertical_results": 垂直领域结果,
                "connections": 理论连接,
                "enhanced_context": 增强后的上下文
            }
        """
        results = {
            "general_results": None,
            "vertical_results": None,
            "connections": [],
            "enhanced_context": ""
        }

        # 1. 检索通用知识库（创意理论）
        if general_kb_id:
            try:
                general_collection = f"kb_{general_kb_id}"
                results["general_results"] = await self.general_graph_rag.retrieve_with_graph(
                    collection_name=general_collection,
                    query=query,
                    n_results=n_results
                )
                self.logger.info(f"通用知识库检索完成: {general_kb_id}")
            except Exception as e:
                self.logger.warning(f"通用知识库检索失败: {e}")

        # 2. 检索垂直领域知识库
        if vertical_kb_id and vertical_category:
            try:
                vertical_rag = self.get_vertical_rag(vertical_category)
                vertical_collection = f"kb_{vertical_kb_id}"
                results["vertical_results"] = await vertical_rag.retrieve_with_graph(
                    collection_name=vertical_collection,
                    query=query,
                    n_results=n_results
                )
                self.logger.info(f"垂直知识库检索完成: {vertical_kb_id}")
            except Exception as e:
                self.logger.warning(f"垂直知识库检索失败: {e}")

        # 3. 分析理论连接
        results["connections"] = self._analyze_connections(results)

        # 4. 生成增强上下文
        results["enhanced_context"] = self._format_dual_track_context(results)

        return results

    def _analyze_connections(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分析垂直实体与通用理论的连接"""
        connections = []

        general_results = results.get("general_results", {})
        vertical_results = results.get("vertical_results", {})

        if not general_results or not vertical_results:
            return connections

        # 获取通用理论实体
        general_entities = set()
        for ctx in general_results.get("graph_context", []):
            general_entities.add(ctx.get("query_entity", ""))
            for rel in ctx.get("related_entities", []):
                general_entities.add(rel.get("text", ""))

        # 获取垂直领域实体并匹配理论
        for ctx in vertical_results.get("graph_context", []):
            vertical_entity = ctx.get("query_entity", "")
            for rel in ctx.get("related_entities", []):
                related_text = rel.get("text", "")
                relation_type = rel.get("relation", "")

                # 检查是否与通用理论相关
                if related_text in general_entities:
                    connections.append({
                        "vertical_entity": vertical_entity,
                        "general_theory": related_text,
                        "relation": relation_type,
                        "confidence": rel.get("weight", 0.8)
                    })

        return connections

    def _format_dual_track_context(self, results: Dict[str, Any]) -> str:
        """格式化双轨检索结果为上下文"""
        parts = []

        # 添加通用理论部分
        general_results = results.get("general_results", {})
        if general_results and general_results.get("vector_results"):
            parts.append("## 通用创意理论\n")
            for i, result in enumerate(general_results["vector_results"][:3], 1):
                content = result.get("content", "")
                parts.append(f"[理论 {i}] {content[:300]}...\n")

        # 添加垂直领域案例部分
        vertical_results = results.get("vertical_results", {})
        if vertical_results and vertical_results.get("vector_results"):
            parts.append("\n## 垂直领域案例\n")
            for i, result in enumerate(vertical_results["vector_results"][:3], 1):
                content = result.get("content", "")
                parts.append(f"[案例 {i}] {content[:300]}...\n")

        # 添加理论连接部分
        connections = results.get("connections", [])
        if connections:
            parts.append("\n## 理论-案例连接\n")
            for conn in connections[:5]:
                parts.append(
                    f"- 「{conn['vertical_entity']}」{conn['relation']}「{conn['general_theory']}」"
                    f" (置信度: {conn['confidence']:.2f})"
                )

        return "\n".join(parts) if parts else ""
