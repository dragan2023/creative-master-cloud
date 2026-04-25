"""CharacterStateTracker - get_state_summaryMixin"""
from __future__ import annotations
from typing import Optional
import re


class GetStateSummaryMixin:
    """get_state_summary功能域"""

    def get_state_summary(self, chapter_num: Optional[int] = None) -> str:
        """获取人物状态摘要（用于提示词）

        Args:
            chapter_num: 章节号（可选，默认使用最新章节）

        Returns:
            格式化的状态摘要文本
        """
        if chapter_num is None:
            chapter_num = self._current_chapter

        if chapter_num and chapter_num in self._chapter_snapshots:
            snapshot = self._chapter_snapshots[chapter_num]
            return snapshot.format_as_table()

        # 返回当前状态总表
        lines = ["# 人物状态总表", ""]

        for name, state in self._character_states.items():
            lines.append(f"## {name}")
            lines.append(f"- 身份/官职: {state.identity or '未设定'}")
            lines.append(f"- 所在位置: {state.location or '未知'}")
            lines.append(f"- 当前状态: {state.status.value}")
            if state.status_change:
                lines.append(f"- 最近变化: {state.status_change}")
            lines.append("")

        return "\n".join(lines)


