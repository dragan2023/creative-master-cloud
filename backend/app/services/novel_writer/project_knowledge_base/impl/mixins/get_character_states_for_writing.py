"""ProjectKnowledgeBase - get_character_states_for_writingMixin"""
import re
import os


class GetCharacterStatesForWritingMixin:
    """get_character_states_for_writing功能域"""

    def get_character_states_for_writing(
        self,
        project_id: int,
        character_name: str,
        current_unit: int = None
    ) -> str:
        """
        获取人物状态信息用于写作提示词

        整合全局图谱和当前章节之前所有单元图谱中的人物状态信息。

        Args:
            project_id: 项目ID
            character_name: 人物名称
            current_unit: 当前章节号（只获取此章节之前的状态）

        Returns:
            格式化的人物状态文本
        """
        try:
            context_parts = [f"## {character_name} 人物状态追踪", ""]

            # 1. 从全局图谱获取人物基础信息
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            if os.path.exists(global_graph_path):
                global_graph = NovelKnowledgeGraph(
                    persist_path=global_graph_path)
                if global_graph.load():
                    # 获取人物基础信息
                    character = global_graph.get_entity_by_text(character_name)
                    if character:
                        context_parts.append("### 基础设定")
                        context_parts.append(
                            f"- 类型: {character.get('type', '人物')}")
                        if character.get("description"):
                            context_parts.append(
                                f"- 描述: {character.get('description')}")
                        attrs = character.get("attributes", {})
                        if attrs:
                            for key, value in attrs.items():
                                if value:
                                    context_parts.append(f"- {key}: {value}")
                        context_parts.append("")

            # 2. 遍历所有已完成的单元图谱，收集人物状态
            all_state_entities = {
                "identity_changes": [],
                "location_changes": [],
                "relationship_changes": [],
                "character_development": [],
                "ability_growth": [],
                "mental_states": [],
                "behavior_patterns": []
            }

            # 确定要遍历的单元范围
            max_unit = current_unit - 1 if current_unit else 1000

            for unit in range(1, max_unit + 1):
                unit_graph_path = self.get_graph_path(project_id, unit)
                if not os.path.exists(unit_graph_path):
                    continue

                unit_graph = NovelKnowledgeGraph(persist_path=unit_graph_path)
                if not unit_graph.load():
                    continue

                # 获取该单元的人物状态实体
                unit_states = unit_graph.get_character_state_entities(
                    character_name=character_name,
                    chapter_num=unit
                )

                # 合并到总状态中
                for key in all_state_entities:
                    all_state_entities[key].extend(unit_states.get(key, []))

            # 3. 格式化输出
            if all_state_entities["identity_changes"]:
                context_parts.append("### 身份变化轨迹")
                for entity in all_state_entities["identity_changes"]:
                    chapter = entity.get("chapter", "")
                    context_parts.append(
                        f"- 第{chapter}章: {entity.get('text')}")
                    if entity.get("description"):
                        context_parts.append(f"  {entity.get('description')}")
                context_parts.append("")

            if all_state_entities["location_changes"]:
                context_parts.append("### 位置变化轨迹")
                locations = []
                for entity in all_state_entities["location_changes"]:
                    locations.append(entity.get("text", ""))
                context_parts.append(" → ".join(locations))
                context_parts.append("")

            if all_state_entities["relationship_changes"]:
                context_parts.append("### 关系变化")
                for entity in all_state_entities["relationship_changes"]:
                    chapter = entity.get("chapter", "")
                    context_parts.append(
                        f"- 第{chapter}章: {entity.get('text')}")
                context_parts.append("")

            if all_state_entities["ability_growth"]:
                context_parts.append("### 能力成长")
                for entity in all_state_entities["ability_growth"]:
                    chapter = entity.get("chapter", "")
                    context_parts.append(
                        f"- 第{chapter}章: {entity.get('text')}")
                context_parts.append("")

            if all_state_entities["mental_states"]:
                context_parts.append("### 心理状态演变")
                for entity in all_state_entities["mental_states"][-5:]:  # 只显示最近5条
                    chapter = entity.get("chapter", "")
                    context_parts.append(
                        f"- 第{chapter}章: {entity.get('text')}")
                context_parts.append("")

            return "\n".join(context_parts)

        except Exception as e:
            self.logger.error(
                f"获取人物状态失败: character={character_name}, error={str(e)}")
            return f"人物 {character_name} 暂无状态追踪信息"


