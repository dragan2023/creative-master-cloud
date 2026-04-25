"""GraphRAG 检索增强核心"""
from typing import List, Dict, Any
import os

from app.core.logger import get_logger
from app.core.vector_store import get_vector_store
from app.core.config import get_settings

from app.tools.graph_rag.entity_extractor import EntityExtractor
from app.tools.graph_rag.knowledge_graph import KnowledgeGraph
from app.tools.graph_rag.llm_entity_extractor import LLMEntityExtractor


class GraphRAG:
    """GraphRAG 检索增强

    支持双轨知识库架构：
    - 通用知识库（general）: 创意理论，固定调用
    - 垂直领域知识库: 应用案例，按需调用
    - 主动建立垂直实体与通用理论的连接
    """

    def __init__(self, persist_dir: str = None, kb_category: str = "general"):
        """
        初始化 GraphRAG

        Args:
            persist_dir: 持久化目录
            kb_category: 知识库类别 (general/short-video/script/novel/print-ad/tvc)
        """
        self.extractor = EntityExtractor()
        self.settings = get_settings()
        self.kb_category = kb_category

        # 设置持久化目录
        self.persist_dir = persist_dir or self.settings.get_knowledge_graph_dir()

        # 初始化知识图谱（全局图谱）
        global_graph_path = os.path.join(self.persist_dir, "global_graph.json")
        self.knowledge_graph = KnowledgeGraph(persist_path=global_graph_path)

        # 知识库图谱缓存
        self._kb_graphs: Dict[int, KnowledgeGraph] = {}

        self.vector_store = get_vector_store()
        self.logger = get_logger("graph_rag")

        # LLM提取器（延迟初始化）
        self._llm_extractor = None

    def get_llm_extractor(self, llm_provider=None):
        """获取或创建LLM提取器"""
        if self._llm_extractor is None:
            if llm_provider is None:
                # 尝试获取默认LLM提供者
                from app.agents.llm_manager import llm_manager
                llm_provider = llm_manager.get_default_provider()
            self._llm_extractor = LLMEntityExtractor(
                llm_provider=llm_provider,
                kb_category=self.kb_category
            )
        return self._llm_extractor

    def get_kb_graph(self, kb_id: int) -> KnowledgeGraph:
        """
        获取特定知识库的知识图谱

        Args:
            kb_id: 知识库ID

        Returns:
            知识图谱实例
        """
        if kb_id not in self._kb_graphs:
            kb_graph_path = os.path.join(
                self.persist_dir, f"kb_{kb_id}_graph.json")
            self._kb_graphs[kb_id] = KnowledgeGraph(persist_path=kb_graph_path)
            # 尝试加载已存在的图谱
            if os.path.exists(kb_graph_path):
                self._kb_graphs[kb_id].load()
        return self._kb_graphs[kb_id]

    async def index_document(self, collection_name: str, doc_id: str, content: str, kb_id: int = None):
        """
        索引文档，提取实体和关系

        Args:
            collection_name: 集合名称
            doc_id: 文档ID
            content: 文档内容
            kb_id: 知识库ID（用于持久化）
        """
        # 提取实体和关系
        entities = self.extractor.extract_entities(content)
        relations = self.extractor.extract_relations(content, entities)

        # 添加到全局知识图谱
        entity_map = {}
        for entity in entities:
            node_id = self.knowledge_graph.add_entity(entity, doc_id)
            entity_map[entity["text"]] = node_id

        for relation in relations:
            self.knowledge_graph.add_relation(relation, doc_id)

        # 如果指定了知识库ID，同时添加到知识库专属图谱
        if kb_id:
            kb_graph = self.get_kb_graph(kb_id)
            for entity in entities:
                kb_graph.add_entity(entity, doc_id)
            for relation in relations:
                kb_graph.add_relation(relation, doc_id)
            # 保存知识库图谱
            kb_graph.save()

        # 保存全局图谱
        self.knowledge_graph.save()

        self.logger.info(
            f"索引文档 {doc_id}: 提取 {len(entities)} 个实体, {len(relations)} 个关系")

        # 更新向量存储的元数据
        metadata = {
            "entities": [e["text"] for e in entities],
            "entity_types": list(set(e["type"] for e in entities)),
            "doc_id": doc_id
        }

        return metadata

    async def retrieve_with_graph(
        self,
        collection_name: str,
        query: str,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        结合知识图谱的检索

        Args:
            collection_name: 集合名称
            query: 查询文本
            n_results: 返回结果数量

        Returns:
            检索结果，包含向量检索和图谱增强信息
        """
        # 1. 向量检索
        try:
            vector_results = self.vector_store.query(
                collection_name=collection_name,
                query_texts=[query],
                n_results=n_results
            )
        except Exception as e:
            self.logger.warning(f"向量检索失败: {str(e)}")
            vector_results = {"documents": [[]], "metadatas": [[]]}

        # 2. 提取查询中的实体
        query_entities = self.extractor.extract_entities(query)
        query_entity_texts = [e["text"] for e in query_entities]

        # 3. 知识图谱增强
        graph_context = []
        for entity_text in query_entity_texts:
            related = self.knowledge_graph.get_related_entities(entity_text)
            if related:
                graph_context.append({
                    "query_entity": entity_text,
                    "related_entities": related[:5]  # 限制数量
                })

        # 4. 格式化结果
        results = []
        if vector_results["documents"] and vector_results["documents"][0]:
            for i, doc in enumerate(vector_results["documents"][0]):
                result = {
                    "content": doc,
                    "metadata": {}
                }

                if vector_results.get("metadatas") and vector_results["metadatas"][0]:
                    result["metadata"] = vector_results["metadatas"][0][i]

                if vector_results.get("distances") and vector_results["distances"][0]:
                    result["distance"] = vector_results["distances"][0][i]

                results.append(result)

        return {
            "vector_results": results,
            "graph_context": graph_context,
            "query_entities": query_entity_texts
        }

    def format_for_context(self, retrieval_result: Dict[str, Any]) -> str:
        """
        格式化检索结果用于 LLM 上下文

        Args:
            retrieval_result: 检索结果

        Returns:
            格式化的上下文文本
        """
        parts = ["以下是知识库中检索到的相关内容：\n"]

        # 向量检索结果
        for i, result in enumerate(retrieval_result.get("vector_results", [])[:3], 1):
            content = result.get("content", "")
            entities = result.get("metadata", {}).get("entities", [])

            parts.append(f"[参考文档 {i}]")
            if entities:
                parts.append(f"关键实体: {', '.join(entities[:5])}")
            parts.append(f"内容:\n{content}\n")

        # 知识图谱上下文
        graph_context = retrieval_result.get("graph_context", [])
        if graph_context:
            parts.append("\n## 相关实体关系")
            for ctx in graph_context:
                parts.append(f"\n「{ctx['query_entity']}」的相关信息:")
                for rel in ctx.get("related_entities", [])[:3]:
                    if rel.get("relation"):
                        parts.append(f"  - {rel['text']} ({rel['relation']})")
                    else:
                        parts.append(f"  - {rel['text']}")

        return "\n".join(parts)

    def get_graph_data(self, kb_id: int = None, max_nodes: int = 100) -> Dict[str, Any]:
        """
        获取知识图谱数据（用于可视化）

        Args:
            kb_id: 知识库ID（可选，不指定则返回全局图谱）
            max_nodes: 最大返回节点数

        Returns:
            图谱数据 {"nodes": [...], "edges": [...]}
        """
        graph = self.get_kb_graph(kb_id) if kb_id else self.knowledge_graph

        # 获取所有节点和边
        all_nodes = []
        for node_id, data in graph.graph.nodes(data=True):
            all_nodes.append({
                "id": node_id,
                "label": data.get("text", ""),
                "type": data.get("type", "未知"),
                "doc_id": data.get("doc_id")
            })

        all_edges = []
        for source, target, data in graph.graph.edges(data=True):
            all_edges.append({
                "source": source,
                "target": target,
                "relation": data.get("relation", "相关"),
                "context": data.get("context", "")
            })

        # 如果节点太多，进行裁剪（优先保留有更多连接的节点）
        if len(all_nodes) > max_nodes:
            # 计算节点度数
            node_degrees = {}
            for edge in all_edges:
                node_degrees[edge["source"]] = node_degrees.get(
                    edge["source"], 0) + 1
                node_degrees[edge["target"]] = node_degrees.get(
                    edge["target"], 0) + 1

            # 按度数排序，保留度数高的节点
            sorted_nodes = sorted(
                all_nodes, key=lambda n: node_degrees.get(n["id"], 0), reverse=True)
            kept_node_ids = set(n["id"] for n in sorted_nodes[:max_nodes])

            # 过滤节点和边
            all_nodes = [n for n in all_nodes if n["id"] in kept_node_ids]
            all_edges = [e for e in all_edges if e["source"]
                         in kept_node_ids and e["target"] in kept_node_ids]

        return {
            "nodes": all_nodes,
            "edges": all_edges,
            "stats": graph.get_stats()
        }

    def add_llm_entities_to_graph(self, entities: List[Dict], relations: List[Dict], kb_id: int = None, doc_id: str = None):
        """
        将LLM提取的实体和关系添加到图谱

        Args:
            entities: 实体列表
            relations: 关系列表
            kb_id: 知识库ID
            doc_id: 文档ID
        """
        # 添加到全局图谱
        for entity in entities:
            # 兼容两种字段名：LLM返回的是 "text"，旧代码可能使用 "name"
            entity_text = entity.get("text") or entity.get("name", "")
            entity_type = entity.get("type", "未知")

            # 跳过空实体
            if not entity_text or not entity_text.strip():
                self.logger.warning(f"跳过空实体: type={entity_type}")
                continue

            entity_data = {
                "text": entity_text,
                "type": entity_type
            }
            self.knowledge_graph.add_entity(entity_data, doc_id)

        for relation in relations:
            relation_data = {
                "source": relation.get("source", ""),
                "target": relation.get("target", ""),
                "relation": relation.get("relation", "相关关系"),
                "context": relation.get("context", "")
            }
            self.knowledge_graph.add_relation(relation_data, doc_id)

        # 添加到知识库专属图谱
        if kb_id:
            kb_graph = self.get_kb_graph(kb_id)
            for entity in entities:
                # 兼容两种字段名：LLM返回的是 "text"，旧代码可能使用 "name"
                entity_text = entity.get("text") or entity.get("name", "")
                entity_type = entity.get("type", "未知")

                # 跳过空实体
                if not entity_text or not entity_text.strip():
                    self.logger.warning(f"跳过空实体: type={entity_type}")
                    continue

                entity_data = {
                    "text": entity_text,
                    "type": entity_type
                }
                kb_graph.add_entity(entity_data, doc_id)

            for relation in relations:
                relation_data = {
                    "source": relation.get("source", ""),
                    "target": relation.get("target", ""),
                    "relation": relation.get("relation", "相关关系"),
                    "context": relation.get("context", "")
                }
                kb_graph.add_relation(relation_data, doc_id)

            # 保存知识库图谱
            kb_graph.save()

        # 保存全局图谱
        self.knowledge_graph.save()


# 全局 GraphRAG 实例
graph_rag = GraphRAG()


def get_graph_rag() -> GraphRAG:
    """获取 GraphRAG 实例"""
    return graph_rag
