"""CharacterStateTracker - sync_from_knowledge_graphMixin"""
from __future__ import annotations
import re


class SyncFromKnowledgeGraphMixin:
    """sync_from_knowledge_graph功能域"""

    def sync_from_knowledge_graph(self, knowledge_graph) -> None:
        """从知识图谱同步人物状态

        将知识图谱中的人物状态追踪实体同步到追踪器中。
        这个方法用于在追踪器初始化后，从已有的知识图谱中恢复人物状态。

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
        """
        try:
            # 获取所有人物的状态实体
            for char_name in self._character_names:
                state_entities = knowledge_graph.get_character_state_entities(
                    character_name=char_name
                )

                # 处理身份变化
                for entity in state_entities.get("identity_changes", []):
                    self.update_character_state(
                        char_name,
                        {
                            "identity": entity.get("text", ""),
                            "status_change": entity.get("description", "")
                        },
                        chapter_num=entity.get("chapter")
                    )

                # 处理位置变化
                location_entities = state_entities.get("location_changes", [])
                if location_entities:
                    # 取最新的位置
                    latest_location = location_entities[-1]
                    self.update_character_state(
                        char_name,
                        {"location": latest_location.get("text", "")},
                        chapter_num=latest_location.get("chapter")
                    )

                # 处理关系变化
                for entity in state_entities.get("relationship_changes", []):
                    desc = entity.get("description", "")
                    text = entity.get("text", "")
                    # 尝试解析关系变化描述
                    self._parse_relationship_change(char_name, text, desc)

            self.logger.info(
                f"从知识图谱同步人物状态完成: {len(self._character_states)}个人物")

        except Exception as e:
            self.logger.error(f"从知识图谱同步人物状态失败: {e}")


    def _parse_relationship_change(self, char_name: str, text: str, description: str) -> None:
        """解析关系变化描述并更新人物关系"""
        # 简单的关系解析逻辑
        # 格式通常是 "与XXX的关系变为YYY" 或 "XXX成为XXX"
        import re

        # 尝试提取目标人物
        patterns = [
            r"与([\\u4e00-\\u9fa5]{2,4})的?关系",
            r"([\\u4e00-\\u9fa5]{2,4})成为",
            r"([\\u4e00-\\u9fa5]{2,4})与([\\u4e00-\\u9fa5]{2,4})"
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                target_char = match.group(1)
                if target_char in self._character_names:
                    # 更新关系
                    if char_name in self._character_states:
                        state = self._character_states[char_name]
                        state.relationships[target_char] = description or text
                break


