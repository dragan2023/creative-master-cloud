"""NovelKnowledgeGraph - get_entity_by_textMixin"""
from typing import Dict
from typing import Optional
from typing import Any
import re


class GetEntityByTextMixin:
    """get_entity_by_text功能域"""

    def get_entity_by_text(self, text: str) -> Optional[Dict[str, Any]]:
        """根据文本获取实体"""
        if text in self.entity_index:
            node_id = self.entity_index[text]
            return {"id": node_id, **self.graph.nodes[node_id]}
        return None


