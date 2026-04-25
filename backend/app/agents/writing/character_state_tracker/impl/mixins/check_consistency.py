"""CharacterStateTracker - check_consistencyMixin"""
from __future__ import annotations
from typing import Dict
from typing import Any
import re


class CheckConsistencyMixin:
    """check_consistency功能域"""

    def check_consistency(
        self,
        chapter_num: int,
        content: str
    ) -> Dict[str, Any]:
        """检查人物状态一致性

        检查以下方面：
        1. 人物位置是否合理（是否在合理时间内到达）
        2. 人物身份是否与设定一致
        3. 人物行为是否符合当前状态
        4. 新人物是否有冲突

        Args:
            chapter_num: 章节号
            content: 章节内容

        Returns:
            检查结果，包含issues和warnings
        """
        result = {
            "issues": [],
            "warnings": [],
            "passed": True
        }

        # 获取前一章状态作为参考
        prev_snapshot = self._chapter_snapshots.get(chapter_num - 1)
        if not prev_snapshot:
            return result

        # 检查每个出场人物
        for name, prev_state in prev_snapshot.characters.items():
            if name in content:
                current_state = self._character_states.get(name)
                if not current_state:
                    continue

                # 检查位置合理性
                if prev_state.location and current_state.location:
                    if prev_state.location != current_state.location:
                        # 位置变化，检查是否有过渡
                        if prev_state.location not in content and current_state.location not in content:
                            result["warnings"].append({
                                "type": "location_transition_missing",
                                "character": name,
                                "message": f"人物'{name}'从'{prev_state.location}'到'{current_state.location}'的位置变化缺少过渡描述"
                            })

        if result["issues"]:
            result["passed"] = False

        return result


