"""CharacterStateTracker - get_state_for_promptMixin"""
from __future__ import annotations
import re

from app.agents.writing.character_state_tracker.api import CharacterStatus


class GetStateForPromptMixin:
    """get_state_for_prompt功能域"""

    def get_state_for_prompt(self, chapter_num: int = None) -> str:
        """获取人物状态摘要用于写作提示词

        返回格式化的人物状态信息，供写作Agent在生成下一章时使用。

        Args:
            chapter_num: 章节号（可选，只显示到该章节为止的状态）

        Returns:
            格式化的人物状态文本
        """
        lines = ["# 人物状态追踪摘要", ""]
        lines.append("以下是各主要人物到当前为止的状态，请在写作时保持一致性：")
        lines.append("")

        for char_name, state in self._character_states.items():
            # 只显示活跃或最近出场的人物
            if state.status == CharacterStatus.ABSENT and state.last_appearance:
                if chapter_num and (chapter_num - state.last_appearance) > 3:
                    continue  # 超过3章未出场，跳过

            lines.append(f"## {char_name}")

            if state.identity:
                lines.append(f"- 身份/官职: {state.identity}")
            if state.location:
                lines.append(f"- 所在位置: {state.location}")
            if state.status_change:
                lines.append(f"- 最近变化: {state.status_change}")
            if state.relationships:
                lines.append("- 人物关系:")
                for related, relation in state.relationships.items():
                    lines.append(f"  - 与{related}: {relation}")

            attrs = state.attributes
            if attrs:
                personality = attrs.get("personality", attrs.get("性格", ""))
                if personality:
                    lines.append(f"- 性格特点: {personality}")

            lines.append("")

        # 添加关系变化历史
        if self._relationship_history:
            lines.append("## 人物关系变化历史")
            lines.append(self.get_relationship_summary())
            lines.append("")

        return "\n".join(lines)


