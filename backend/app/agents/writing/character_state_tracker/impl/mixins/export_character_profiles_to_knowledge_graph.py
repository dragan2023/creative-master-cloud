"""CharacterStateTracker - export_character_profiles_to_knowledge_graphMixin"""
from __future__ import annotations
from typing import Dict
from typing import List
from typing import Any
import re


class ExportCharacterProfilesToKnowledgeGraphMixin:
    """export_character_profiles_to_knowledge_graph功能域"""

    def export_character_profiles_to_knowledge_graph(
        self,
        knowledge_graph,
        character_profiles: List[Dict[str, Any]] = None
    ) -> None:
        """导出人物设定到全局知识图谱

        将人物的基础设定（性格、背景、关系等）作为持久化实体存入全局知识图谱。
        这些设定不会随章节变化，是人物的常态属性。

        Args:
            knowledge_graph: NovelKnowledgeGraph实例（全局图谱）
            character_profiles: 人物设定列表（可选，默认使用追踪器中的状态）
        """
        try:
            entity_count = 0

            # 使用传入的设定或追踪器中的状态
            profiles_to_export = character_profiles or []

            # 如果没有传入设定，从追踪器状态构建
            if not profiles_to_export:
                for char_name, state in self._character_states.items():
                    profile = {
                        "name": char_name,
                        "identity": state.identity,
                        "location": state.location,
                        **state.attributes
                    }
                    profiles_to_export.append(profile)

            for profile in profiles_to_export:
                # 添加类型检查：确保profile是字典而不是字符串
                if isinstance(profile, str):
                    self.logger.warning(f"跳过无效的人物设定（字符串类型）: {profile[:50]}...")
                    continue
                
                if not isinstance(profile, dict):
                    self.logger.warning(f"跳过无效的人物设定（类型={type(profile).__name__}）")
                    continue
                    
                char_name = profile.get("name", "")
                if not char_name:
                    continue

                # 创建人物设定实体
                profile_entity = {
                    "text": char_name,
                    "type": "人物设定",
                    "level": "macro",
                    "description": self._build_profile_description(profile)
                }

                # 添加详细属性
                attributes = {}
                if profile.get("identity"):
                    attributes["身份"] = profile.get("identity")
                if profile.get("role"):
                    attributes["角色定位"] = profile.get("role")
                if profile.get("personality"):
                    attributes["性格特点"] = profile.get("personality")
                if profile.get("background"):
                    attributes["背景故事"] = profile.get("background")
                if profile.get("age"):
                    attributes["年龄"] = profile.get("age")
                if profile.get("gender"):
                    attributes["性别"] = profile.get("gender")
                if profile.get("location") or profile.get("initial_location"):
                    attributes["初始位置"] = profile.get(
                        "location") or profile.get("initial_location")
                if profile.get("goals"):
                    attributes["目标动机"] = profile.get("goals")

                if attributes:
                    profile_entity["attributes"] = attributes

                knowledge_graph.add_entity(
                    profile_entity, doc_id="character_profiles")
                entity_count += 1

                # 导出人物关系作为图谱边
                relationships = profile.get("relationships", {})
                for related_char, relation_desc in relationships.items():
                    knowledge_graph.add_relation({
                        "source": char_name,
                        "target": related_char,
                        "relation": "人物关系",
                        "context": relation_desc
                    }, doc_id="character_profiles")

            # 保存图谱
            knowledge_graph.save()

            self.logger.info(
                f"导出人物设定到全局图谱完成: {entity_count}个人物设定")

        except Exception as e:
            self.logger.error(f"导出人物设定到全局图谱失败: {e}")


