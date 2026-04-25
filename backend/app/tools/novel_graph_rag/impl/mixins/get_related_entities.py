"""NovelKnowledgeGraph - get_related_entitiesMixin"""
from typing import Dict
from typing import List
from typing import Any
import re


class GetRelatedEntitiesMixin:
    """get_related_entities功能域"""

    def get_related_entities(self, entity_text: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """获取相关实体"""
        if entity_text not in self.entity_index:
            return []

        node_id = self.entity_index[entity_text]
        related = []
        visited = {node_id}

        # BFS遍历
        current_level = [node_id]
        for depth in range(max_depth):
            next_level = []
            for current_id in current_level:
                # 出边
                for _, target, edge_data in self.graph.edges(current_id, data=True):
                    if target not in visited:
                        visited.add(target)
                        target_data = self.graph.nodes[target]
                        related.append({
                            "id": target,
                            "text": target_data.get("text", ""),
                            "type": target_data.get("type", ""),
                            "relation": edge_data.get("relation", ""),
                            "depth": depth + 1
                        })
                        next_level.append(target)

                # 入边
                for source, _, edge_data in self.graph.edges(data=True):
                    if source == current_id and source not in visited:
                        continue
                    # 简化处理，只查出边

            current_level = next_level

        return related


