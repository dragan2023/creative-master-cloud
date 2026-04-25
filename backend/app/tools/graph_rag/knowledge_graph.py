"""知识图谱存储和查询"""
from typing import List, Dict, Any
import json
import os
import networkx as nx
from collections import defaultdict

from app.core.logger import get_logger


class KnowledgeGraph:
    """知识图谱存储和查询"""

    def __init__(self, persist_path: str = None):
        self.graph = nx.DiGraph()
        self.entity_index = defaultdict(list)  # 实体名 -> 节点ID列表
        self._node_counter = 0
        self.persist_path = persist_path
        self.logger = get_logger("knowledge_graph")

        # 初始化时尝试加载已保存的图谱
        if persist_path:
            self.load()

    def add_entity(self, entity: Dict[str, Any], doc_id: str = None) -> str:
        """
        添加实体节点

        Args:
            entity: 实体信息，包含 text, type, level, description, attributes 等
            doc_id: 文档ID

        Returns:
            节点ID
        """
        node_id = f"entity_{self._node_counter}"
        self._node_counter += 1

        # 构建节点属性，支持分层结构和额外属性
        node_attrs = {
            "text": entity["text"],
            "type": entity["type"],
            "level": entity.get("level", "macro"),  # 宏观层或微观层
            "description": entity.get("description", ""),
            "doc_id": doc_id
        }

        # 添加额外属性（如果有）
        if "attributes" in entity and entity["attributes"]:
            node_attrs["attributes"] = entity["attributes"]

        self.graph.add_node(node_id, **node_attrs)

        self.entity_index[entity["text"]].append(node_id)
        return node_id

    def add_relation(self, relation: Dict[str, Any], doc_id: str = None):
        """
        添加关系边

        Args:
            relation: 关系信息
            doc_id: 文档ID
        """
        source_nodes = self.entity_index.get(relation["source"], [])
        target_nodes = self.entity_index.get(relation["target"], [])

        # 如果节点不存在，创建新节点
        if not source_nodes:
            source_id = self.add_entity(
                {"text": relation["source"], "type": "未知"}, doc_id)
        else:
            source_id = source_nodes[0]

        if not target_nodes:
            target_id = self.add_entity(
                {"text": relation["target"], "type": "未知"}, doc_id)
        else:
            target_id = target_nodes[0]

        self.graph.add_edge(
            source_id,
            target_id,
            relation=relation["relation"],
            context=relation.get("context", ""),
            doc_id=doc_id
        )

    def get_related_entities(self, entity_text: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        获取相关实体

        Args:
            entity_text: 实体文本
            max_depth: 最大搜索深度

        Returns:
            相关实体列表
        """
        results = []
        node_ids = self.entity_index.get(entity_text, [])

        for node_id in node_ids:
            # BFS 遍历相关节点
            visited = set()
            queue = [(node_id, 0)]

            while queue:
                current_id, depth = queue.pop(0)

                if current_id in visited or depth > max_depth:
                    continue

                visited.add(current_id)
                node_data = self.graph.nodes.get(current_id, {})

                if depth > 0:  # 不包括起始节点
                    results.append({
                        "text": node_data.get("text"),
                        "type": node_data.get("type"),
                        "depth": depth
                    })

                # 遍历邻居
                for neighbor in self.graph.successors(current_id):
                    edge_data = self.graph.edges.get(
                        (current_id, neighbor), {})
                    results.append({
                        "text": self.graph.nodes[neighbor].get("text"),
                        "type": self.graph.nodes[neighbor].get("type"),
                        "relation": edge_data.get("relation"),
                        "depth": depth + 1
                    })
                    queue.append((neighbor, depth + 1))

                for neighbor in self.graph.predecessors(current_id):
                    edge_data = self.graph.edges.get(
                        (neighbor, current_id), {})
                    queue.append((neighbor, depth + 1))

        return results

    def get_entity_paths(self, entity1: str, entity2: str) -> List[List[str]]:
        """
        获取两个实体之间的路径

        Args:
            entity1: 实体1
            entity2: 实体2

        Returns:
            路径列表
        """
        paths = []
        nodes1 = self.entity_index.get(entity1, [])
        nodes2 = self.entity_index.get(entity2, [])

        for n1 in nodes1:
            for n2 in nodes2:
                try:
                    path = nx.shortest_path(self.graph, n1, n2)
                    path_texts = [
                        self.graph.nodes[n].get("text", "")
                        for n in path
                    ]
                    paths.append(path_texts)
                except nx.NetworkXNoPath:
                    continue

        return paths

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                **data
            })

        edges = []
        for source, target, data in self.graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                **data
            })

        return {
            "nodes": nodes,
            "edges": edges
        }

    def from_dict(self, data: Dict[str, Any]):
        """从字典导入"""
        self.graph.clear()
        self.entity_index.clear()
        self._node_counter = 0

        for node in data.get("nodes", []):
            node_id = node.pop("id")
            self.graph.add_node(node_id, **node)
            self.entity_index[node.get("text", "")].append(node_id)
            self._node_counter = max(
                self._node_counter, int(node_id.split("_")[-1]) + 1)

        for edge in data.get("edges", []):
            source = edge.pop("source")
            target = edge.pop("target")
            self.graph.add_edge(source, target, **edge)

    def save(self, path: str = None) -> bool:
        """
        保存知识图谱到文件

        Args:
            path: 保存路径（可选，默认使用初始化时的路径）

        Returns:
            是否保存成功
        """
        save_path = path or self.persist_path
        if not save_path:
            return False

        try:
            # 确保目录存在
            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)

            # 导出为字典并保存
            data = self.to_dict()
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info(
                f"知识图谱已保存: {save_path}, 节点数: {len(data['nodes'])}, 边数: {len(data['edges'])}")
            return True
        except Exception as e:
            self.logger.error(f"保存知识图谱失败: {str(e)}")
            return False

    def load(self, path: str = None) -> bool:
        """
        从文件加载知识图谱

        Args:
            path: 加载路径（可选，默认使用初始化时的路径）

        Returns:
            是否加载成功
        """
        load_path = path or self.persist_path
        if not load_path or not os.path.exists(load_path):
            return False

        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.from_dict(data)
            self.logger.info(
                f"知识图谱已加载: {load_path}, 节点数: {len(data.get('nodes', []))}, 边数: {len(data.get('edges', []))}")
            return True
        except Exception as e:
            self.logger.error(f"加载知识图谱失败: {str(e)}")
            return False

    def save_for_knowledge_base(self, kb_id: int, base_dir: str):
        """
        为特定知识库保存图谱

        Args:
            kb_id: 知识库ID
            base_dir: 基础目录
        """
        kb_graph_path = os.path.join(base_dir, f"kb_{kb_id}_graph.json")
        self.save(kb_graph_path)

    def load_for_knowledge_base(self, kb_id: int, base_dir: str) -> bool:
        """
        加载特定知识库的图谱

        Args:
            kb_id: 知识库ID
            base_dir: 基础目录

        Returns:
            是否加载成功
        """
        kb_graph_path = os.path.join(base_dir, f"kb_{kb_id}_graph.json")
        return self.load(kb_graph_path)

    def get_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "entity_types": self._count_entity_types()
        }

    def _count_entity_types(self) -> Dict[str, int]:
        """统计各类型实体数量"""
        type_counts = defaultdict(int)
        for _, data in self.graph.nodes(data=True):
            entity_type = data.get("type", "未知")
            type_counts[entity_type] += 1
        return dict(type_counts)
