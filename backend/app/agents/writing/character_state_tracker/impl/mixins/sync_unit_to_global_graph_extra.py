"""CharacterStateTracker - sync_unit_to_global_graph_extraMixin"""
from __future__ import annotations
from typing import Dict
from typing import Any
import re


class SyncUnitToGlobalGraphExtraMixin:
    """sync_unit_to_global_graph_extra功能域"""

    def _update_character_profile_in_graph(
        self,
        knowledge_graph,
        char_name: str,
        updates: Dict[str, Any],
        chapter_num: int
    ) -> bool:
        """更新全局知识图谱中的人物设定

        以正文内容为准，动态更新人物设定属性。

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            char_name: 人物名称
            updates: 要更新的属性字典
            chapter_num: 章节号

        Returns:
            是否更新成功
        """
        try:
            graph = knowledge_graph.graph

            # 查找人物设定节点
            for node_id, node_data in graph.nodes(data=True):
                if node_data.get("type") == "人物设定" and node_data.get("text") == char_name:
                    # 更新属性
                    attributes = node_data.get("attributes", {})
                    for key, value in updates.items():
                        old_value = attributes.get(key, "")
                        attributes[key] = value

                        # 记录变更历史
                        history_key = f"{key}_变更历史"
                        history = attributes.get(history_key, [])
                        if not isinstance(history, list):
                            history = []
                        history.append({
                            "chapter": chapter_num,
                            "old_value": old_value,
                            "new_value": value
                        })
                        attributes[history_key] = history

                    node_data["attributes"] = attributes

                    # 更新描述
                    node_data["description"] = self._build_profile_description_from_attrs(
                        attributes)
                    node_data["last_updated_chapter"] = chapter_num

                    self.logger.info(
                        f"更新人物设定: {char_name}, 属性={list(updates.keys())}, 章节={chapter_num}")
                    return True

            # 如果没找到现有节点，创建新的
            self._create_character_profile_in_graph(
                knowledge_graph, char_name, updates, chapter_num)
            return True

        except Exception as e:
            self.logger.error(f"更新人物设定失败: {char_name}, {e}")
            return False


    def _create_character_profile_in_graph(
        self,
        knowledge_graph,
        char_name: str,
        attributes: Dict[str, Any],
        chapter_num: int
    ) -> None:
        """在全局图谱中创建新的人物设定节点

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            char_name: 人物名称
            attributes: 属性字典
            chapter_num: 章节号
        """
        try:
            profile_entity = {
                "text": char_name,
                "type": "人物设定",
                "level": "macro",
                "description": self._build_profile_description_from_attrs(attributes),
                "attributes": attributes,
                "first_appearance_chapter": chapter_num,
                "last_updated_chapter": chapter_num
            }

            knowledge_graph.add_entity(
                profile_entity, doc_id="character_profiles")

            self.logger.info(
                f"创建人物设定节点: {char_name}, 章节={chapter_num}")

        except Exception as e:
            self.logger.error(f"创建人物设定节点失败: {char_name}, {e}")


    def _append_character_attribute_in_graph(
        self,
        knowledge_graph,
        char_name: str,
        attr_name: str,
        value: str
    ) -> None:
        """追加人物属性记录（用于性格发展等累积性属性）

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            char_name: 人物名称
            attr_name: 属性名称
            value: 要追加的值
        """
        try:
            graph = knowledge_graph.graph

            for node_id, node_data in graph.nodes(data=True):
                if node_data.get("type") == "人物设定" and node_data.get("text") == char_name:
                    attributes = node_data.get("attributes", {})

                    # 获取或创建列表
                    existing = attributes.get(attr_name, [])
                    if not isinstance(existing, list):
                        existing = [existing] if existing else []

                    existing.append(value)
                    attributes[attr_name] = existing
                    node_data["attributes"] = attributes

                    self.logger.debug(
                        f"追加人物属性: {char_name}.{attr_name} += {value}")
                    return

        except Exception as e:
            self.logger.error(f"追加人物属性失败: {char_name}, {e}")


    def _build_profile_description_from_attrs(self, attributes: Dict[str, Any]) -> str:
        """从属性字典构建人物设定描述

        Args:
            attributes: 属性字典

        Returns:
            格式化的描述文本
        """
        parts = []

        # 主要属性
        main_attrs = [
            ("角色定位", "角色"),
            ("身份", "身份"),
            ("性格特点", "性格"),
            ("年龄", "年龄"),
            ("性别", "性别"),
            ("当前位置", "位置")
        ]

        for attr_key, display_name in main_attrs:
            if attributes.get(attr_key):
                parts.append(f"{display_name}: {attributes[attr_key]}")

        # 背景故事（截取前50字）
        if attributes.get("背景故事"):
            bg = attributes["背景故事"]
            if len(bg) > 50:
                bg = bg[:50] + "..."
            parts.append(f"背景: {bg}")

        return " | ".join(parts) if parts else "人物设定"


    def _build_profile_description(self, profile: Dict[str, Any]) -> str:
        """构建人物设定描述文本

        Args:
            profile: 人物设定字典

        Returns:
            格式化的描述文本
        """
        parts = []

        if profile.get("role"):
            parts.append(f"角色: {profile['role']}")
        if profile.get("identity"):
            parts.append(f"身份: {profile['identity']}")
        if profile.get("personality"):
            parts.append(f"性格: {profile['personality']}")
        if profile.get("background"):
            # 背景可能较长，截取前100字
            bg = profile['background']
            if len(bg) > 100:
                bg = bg[:100] + "..."
            parts.append(f"背景: {bg}")
        if profile.get("age"):
            parts.append(f"年龄: {profile['age']}")
        if profile.get("gender"):
            parts.append(f"性别: {profile['gender']}")

        return " | ".join(parts) if parts else "人物设定"


