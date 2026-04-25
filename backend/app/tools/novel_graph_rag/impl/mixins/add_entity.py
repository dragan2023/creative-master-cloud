"""NovelKnowledgeGraph - add_entityMixin"""
from typing import Dict
from typing import Any
import re


class AddEntityMixin:
    """add_entity功能域"""

    def add_entity(self, entity_data: Dict[str, Any], doc_id: str = "") -> str:
        """
        添加实体到图谱

        Args:
            entity_data: 实体数据，包含 text, type, level, description 等
            doc_id: 文档ID

        Returns:
            节点ID
        """
        import uuid

        text = entity_data.get("text", "")

        # 检查是否已存在相同文本的实体
        if text in self.entity_index:
            # 更新现有节点
            node_id = self.entity_index[text]
            # 合并属性
            existing_data = dict(self.graph.nodes[node_id])
            existing_data.update(entity_data)
            existing_data["doc_ids"] = existing_data.get("doc_ids", [])
            if doc_id and doc_id not in existing_data["doc_ids"]:
                existing_data["doc_ids"].append(doc_id)
            self.graph.nodes[node_id].update(existing_data)
            return node_id

        # 创建新节点
        node_id = str(uuid.uuid4())
        node_data = {
            **entity_data,
            "doc_ids": [doc_id] if doc_id else []
        }
        self.graph.add_node(node_id, **node_data)
        self.entity_index[text] = node_id

        return node_id


