"""NovelKnowledgeGraph - format_character_state_for_promptMixin"""
import re


class FormatCharacterStateForPromptMixin:
    """format_character_state_for_prompt功能域"""

    def format_character_state_for_prompt(self, character_name: str, chapter_num: int = None) -> str:
        """格式化人物状态为提示词格式

        将人物状态追踪实体格式化为可读的文本，供写作Agent使用。

        Args:
            character_name: 人物名称
            chapter_num: 章节号（可选，只显示到该章节为止的状态）

        Returns:
            格式化的人物状态文本
        """
        state_entities = self.get_character_state_entities(
            character_name=character_name,
            chapter_num=chapter_num
        )

        lines = [f"## {character_name} 状态追踪", ""]

        if state_entities["identity_changes"]:
            lines.append("### 身份变化")
            for entity in state_entities["identity_changes"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
                if entity.get("description"):
                    lines.append(f"  {entity.get('description')}")
            lines.append("")

        if state_entities["location_changes"]:
            lines.append("### 位置变化")
            for entity in state_entities["location_changes"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
            lines.append("")

        if state_entities["relationship_changes"]:
            lines.append("### 关系变化")
            for entity in state_entities["relationship_changes"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
                if entity.get("description"):
                    lines.append(f"  {entity.get('description')}")
            lines.append("")
        if state_entities["ability_growth"]:
            lines.append("### 能力成长")
            for entity in state_entities["ability_growth"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
            lines.append("")
        if state_entities["mental_states"]:
            lines.append("### 心理状态")
            for entity in state_entities["mental_states"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
            lines.append("")
        if state_entities["character_development"]:
            lines.append("### 性格发展")
            for entity in state_entities["character_development"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
                if entity.get("description"):
                    lines.append(f"  {entity.get('description')}")
            lines.append("")
        return "\n".join(lines)


