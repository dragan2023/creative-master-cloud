"""NovelKnowledgeGraph - add_relationMixin"""
from typing import Dict
from typing import Any
import re

from app.tools.novel_graph_rag.constants import FORBIDDEN_RELATION_TYPES


class AddRelationMixin:
    """add_relation功能域"""

    def add_relation(self, relation_data: Dict[str, Any], doc_id: str = "") -> bool:
        """
        添加关系到图谱

        Args:
            relation_data: 关系数据，包含 source, target, relation 等
            doc_id: 文档ID

        Returns:
            是否成功
        """
        source_text = relation_data.get("source", "")
        target_text = relation_data.get("target", "")
        relation_type = relation_data.get("relation", "关联")

        # 过滤禁止的关系类型
        if relation_type in FORBIDDEN_RELATION_TYPES:
            self.logger.warning(f"过滤禁止的关系类型: {relation_type}")
            return False

        # 查找或创建节点
        if source_text not in self.entity_index:
            self.add_entity({"text": source_text, "type": "未知"}, doc_id)
        if target_text not in self.entity_index:
            self.add_entity({"text": target_text, "type": "未知"}, doc_id)

        source_id = self.entity_index[source_text]
        target_id = self.entity_index[target_text]

        # 添加边
        edge_data = {
            "relation": relation_type,
            "context": relation_data.get("context", ""),
            "doc_ids": [doc_id] if doc_id else []
        }

        # 如果边已存在，更新doc_ids
        if self.graph.has_edge(source_id, target_id):
            existing_data = self.graph.edges[source_id, target_id]
            edge_data["doc_ids"] = list(
                set(existing_data.get("doc_ids", []) + edge_data["doc_ids"]))

        self.graph.add_edge(source_id, target_id, **edge_data)
        return True


