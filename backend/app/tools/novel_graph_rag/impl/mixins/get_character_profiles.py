"""NovelKnowledgeGraph - get_character_profilesMixin"""
from typing import Dict
from typing import List
from typing import Any
import re


class GetCharacterProfilesMixin:
    """get_character_profiles功能域"""

    def get_character_profiles(self) -> List[Dict[str, Any]]:
        """获取所有人物档案

        将知识图谱中的"人物"类型实体转换为角色设定格式，
        供写手Agent使用。

        Returns:
            角色设定列表，每个元素包含 name, role, personality, background 等
        """
        characters = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") == "人物":
                attrs = data.get("attributes", {})
                character = {
                    "name": data.get("text", ""),
                    "role": attrs.get("role", attrs.get("身份", "")),
                    "personality": attrs.get("personality", attrs.get("性格", "")),
                    "background": attrs.get("background", attrs.get("背景", "")),
                    "description": data.get("description", ""),
                    "age": attrs.get("age", attrs.get("年龄", "")),
                    "gender": attrs.get("gender", attrs.get("性别", "")),
                    "appearance": attrs.get("appearance", attrs.get("外貌", "")),
                    "goals": attrs.get("goals", attrs.get("目标", "")),
                    "relationships": []
                }
                # 过滤空值
                character = {k: v for k, v in character.items() if v}
                characters.append(character)
        return characters


