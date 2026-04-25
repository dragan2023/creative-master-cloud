"""CharacterStateTracker - get_state_evolutionMixin"""
from __future__ import annotations
from typing import Dict
from typing import List
from typing import Any
import re


class GetStateEvolutionMixin:
    """get_state_evolution功能域"""

    def get_state_evolution(self, character_name: str) -> List[Dict[str, Any]]:
        """获取指定人物的状态演变历史

        Args:
            character_name: 人物名称

        Returns:
            状态演变列表，每项包含章节号和该章节的状态
        """
        evolution = []

        for chapter_num in sorted(self._chapter_snapshots.keys()):
            snapshot = self._chapter_snapshots[chapter_num]
            if character_name in snapshot.characters:
                state = snapshot.characters[character_name]
                evolution.append({
                    "chapter": chapter_num,
                    "chapter_title": snapshot.chapter_title,
                    "state": state.to_dict()
                })

        return evolution


