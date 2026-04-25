"""NovelKnowledgeGraph - get_entities_by_typeMixin"""
from typing import Dict
from typing import List
from typing import Any
import re


class GetEntitiesByTypeMixin:
    """get_entities_by_type功能域"""

    def get_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """根据类型获取所有实体

        Args:
            entity_type: 实体类型（如"人物"、"地点"、"世界观规则"等）

        Returns:
            该类型的所有实体列表
        """
        entities = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") == entity_type:
                entities.append({
                    "id": node_id,
                    "name": data.get("text", ""),
                    "type": data.get("type", ""),
                    "description": data.get("description", ""),
                    "attributes": data.get("attributes", {}),
                    "level": data.get("level", "")
                })
        return entities


