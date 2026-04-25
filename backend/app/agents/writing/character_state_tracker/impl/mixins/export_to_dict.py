"""CharacterStateTracker - export_to_dictMixin"""
from __future__ import annotations
from typing import Dict
from typing import Any
import re


class ExportToDictMixin:
    """export_to_dict功能域"""

    def export_to_dict(self) -> Dict[str, Any]:
        """导出追踪器状态为字典（用于持久化）

        Returns:
            包含完整追踪器状态的字典
        """
        return {
            "project_id": self.project_id,
            "initialized": self._initialized,
            "current_chapter": self._current_chapter,
            "character_states": {
                name: state.to_dict()
                for name, state in self._character_states.items()
            },
            "chapter_snapshots": {
                str(num): snapshot.to_dict()
                for num, snapshot in self._chapter_snapshots.items()
            },
            "relationship_history": [
                {
                    "chapter_num": r.chapter_num,
                    "character1": r.character1,
                    "character2": r.character2,
                    "relationship_type": r.relationship_type,
                    "previous_state": r.previous_state,
                    "new_state": r.new_state,
                    "description": r.description
                }
                for r in self._relationship_history
            ],
            "known_locations": list(self._known_locations)
        }


