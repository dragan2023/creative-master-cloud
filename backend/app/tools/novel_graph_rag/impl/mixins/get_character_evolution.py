"""NovelKnowledgeGraph - get_character_evolutionMixin"""
from typing import Dict
from typing import Any
import re


class GetCharacterEvolutionMixin:
    """get_character_evolution功能域"""

    def get_character_evolution(self, character_name: str) -> Dict[str, Any]:
        """获取人物完整演变轨迹

        综合获取指定人物的所有状态变化实体，构建演变轨迹。

        Args:
            character_name: 人物名称

        Returns:
            人物演变轨迹字典，包含各类型的状态变化按章节排序
        """
        state_entities = self.get_character_state_entities(
            character_name=character_name)

        evolution = {
            "character_name": character_name,
            "identity_evolution": [],  # 身份演变轨迹
            "location_evolution": [],   # 位置演变轨迹
            "relationship_evolution": [],  # 关系演变轨迹
            "ability_evolution": [],    # 能力演变轨迹
            "psychological_evolution": [],  # 心理演变轨迹
            "total_changes": 0
        }

        # 按章节排序整理身份变化
        for entity in sorted(state_entities["identity_changes"],
                             key=lambda x: x.get("chapter") or 0):
            evolution["identity_evolution"].append({
                "chapter": entity.get("chapter"),
                "change": entity.get("text"),
                "description": entity.get("description")
            })

        # 按章节排序整理位置变化
        for entity in sorted(state_entities["location_changes"],
                             key=lambda x: x.get("chapter") or 0):
            evolution["location_evolution"].append({
                "chapter": entity.get("chapter"),
                "location": entity.get("text"),
                "description": entity.get("description")
            })

        # 按章节排序整理关系变化
        for entity in sorted(state_entities["relationship_changes"],
                             key=lambda x: x.get("chapter") or 0):
            evolution["relationship_evolution"].append({
                "chapter": entity.get("chapter"),
                "change": entity.get("text"),
                "description": entity.get("description")
            })

        # 按章节排序整理能力成长
        for entity in sorted(state_entities["ability_growth"],
                             key=lambda x: x.get("chapter") or 0):
            evolution["ability_evolution"].append({
                "chapter": entity.get("chapter"),
                "ability": entity.get("text"),
                "description": entity.get("description")
            })
        # 按章节排序整理心理状态
        for entity in sorted(state_entities["mental_states"],
                             key=lambda x: x.get("chapter") or 0):
            evolution["psychological_evolution"].append({
                "chapter": entity.get("chapter"),
                "state": entity.get("text"),
                "description": entity.get("description")
            })

        # 计算总变化数
        evolution["total_changes"] = (
            len(evolution["identity_evolution"]) +
            len(evolution["location_evolution"]) +
            len(evolution["relationship_evolution"]) +
            len(evolution["ability_evolution"]) +
            len(evolution["psychological_evolution"])
        )

        return evolution


