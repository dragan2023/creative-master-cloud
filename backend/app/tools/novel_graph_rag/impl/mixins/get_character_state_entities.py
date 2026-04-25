"""NovelKnowledgeGraph - get_character_state_entitiesMixin"""
from typing import Dict
from typing import List
from typing import Any
import re


class GetCharacterStateEntitiesMixin:
    """get_character_state_entities功能域"""

    def get_character_state_entities(self, character_name: str = None, chapter_num: int = None) -> Dict[str, List[Dict[str, Any]]]:
        """获取人物状态追踪实体

        从知识图谱中提取人物状态相关的实体，用于支持人物状态追踪器。

        Args:
            character_name: 人物名称（可选，筛选特定人物的实体）
            chapter_num: 章节号（可选，筛选特定章节的实体）

        Returns:
            按类型分组的人物状态实体字典
        """
        # 人物状态相关的实体类型
        state_entity_types = {
            "身份变化", "位置变化", "关系变化", "性格发展",
            "能力成长", "心理状态", "行为模式"
        }

        result = {
            "identity_changes": [],    # 身份变化
            "location_changes": [],    # 位置变化
            "relationship_changes": [],  # 关系变化
            "character_development": [],  # 性格发展
            "ability_growth": [],       # 能力成长
            "mental_states": [],        # 心理状态
            "behavior_patterns": []     # 行为模式
        }

        # 类型映射
        type_mapping = {
            "身份变化": "identity_changes",
            "位置变化": "location_changes",
            "关系变化": "relationship_changes",
            "性格发展": "character_development",
            "能力成长": "ability_growth",
            "心理状态": "mental_states",
            "行为模式": "behavior_patterns"
        }

        for node_id, data in self.graph.nodes(data=True):
            entity_type = data.get("type", "")
            if entity_type not in state_entity_types:
                continue

            # 筛选特定人物
            if character_name:
                entity_character = data.get("character", "")
                if entity_character and entity_character != character_name:
                    continue
                # 也检查实体文本中是否包含人物名称
                if not entity_character and character_name not in data.get("text", ""):
                    continue

            # 筛选特定章节
            if chapter_num is not None:
                entity_chapter = data.get("chapter")
                if entity_chapter is not None and entity_chapter != chapter_num:
                    continue

            # 添加到对应的分类
            result_key = type_mapping.get(entity_type)
            if result_key:
                result[result_key].append({
                    "id": node_id,
                    "text": data.get("text", ""),
                    "type": entity_type,
                    "character": data.get("character", ""),
                    "chapter": data.get("chapter"),
                    "description": data.get("description", ""),
                    "attributes": data.get("attributes", {})
                })

        return result


