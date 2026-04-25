"""CharacterStateTracker - get_relationship_summaryMixin"""
from __future__ import annotations
import re


class GetRelationshipSummaryMixin:
    """get_relationship_summary功能域"""

    def get_relationship_summary(self) -> str:
        """获取人物关系摘要（用于提示词）

        Returns:
            格式化的关系摘要文本
        """
        if not self._relationship_history:
            return "暂无人物关系变化记录"

        lines = ["# 人物关系链追踪表", ""]
        lines.append("| 关系类型 | 涉及人物 | 初始关系 | 最新状态 | 变化章节 |")
        lines.append(
            "|----------|----------|----------|----------|----------|")

        # 按人物对分组
        seen_pairs = set()
        for change in reversed(self._relationship_history):
            pair = tuple(sorted([change.character1, change.character2]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            lines.append(
                f"| {change.relationship_type} | "
                f"{change.character1}↔{change.character2} | "
                f"{change.previous_state or '无'} | "
                f"{change.new_state} | "
                f"第{change.chapter_num}章 |"
            )

        return "\n".join(lines)


