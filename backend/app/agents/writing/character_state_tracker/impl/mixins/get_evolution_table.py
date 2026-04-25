"""CharacterStateTracker - get_evolution_tableMixin"""
from __future__ import annotations
import re


class GetEvolutionTableMixin:
    """get_evolution_table功能域"""

    def get_evolution_table(self, character_name: str) -> str:
        """获取单个人物的状态演变表（用于提示词）

        Args:
            character_name: 人物名称

        Returns:
            格式化的状态演变表格
        """
        evolution = self.get_state_evolution(character_name)

        if not evolution:
            return f"人物 '{character_name}' 暂无状态演变记录"

        lines = [
            f"# {character_name} 状态演变",
            "",
            "| 章节 | 身份/官职 | 所在位置 | 状态变化 |",
            "|------|-----------|----------|----------|"
        ]

        for entry in evolution:
            state = entry["state"]
            lines.append(
                f"| 第{entry['chapter']}章 | "
                f"{state.get('identity', '-') or '-'} | "
                f"{state.get('location', '-') or '-'} | "
                f"{state.get('status_change', '-') or '-'} |"
            )

        return "\n".join(lines)


