"""CharacterStateTracker - import_from_dictMixin"""
from __future__ import annotations
from typing import Dict
from typing import Any
import re
import time

from app.agents.writing.character_state_tracker.api import CharacterState, ChapterSnapshot, RelationshipChange


class ImportFromDictMixin:
    """import_from_dict功能域"""

    def import_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典导入追踪器状态

        Args:
            data: 包含追踪器状态的字典
        """
        # 导入人物状态
        self._character_states = {
            name: CharacterState.from_dict(state_data)
            for name, state_data in data.get("character_states", {}).items()
        }

        # 导入章节快照
        self._chapter_snapshots = {}
        for num_str, snapshot_data in data.get("chapter_snapshots", {}).items():
            num = int(num_str)
            characters = {
                name: CharacterState.from_dict(state_data)
                for name, state_data in snapshot_data.get("characters", {}).items()
            }
            self._chapter_snapshots[num] = ChapterSnapshot(
                chapter_num=snapshot_data.get("chapter_num", num),
                chapter_title=snapshot_data.get("chapter_title", ""),
                timestamp=snapshot_data.get("timestamp", ""),
                characters=characters,
                new_characters=snapshot_data.get("new_characters", []),
                relationship_changes=snapshot_data.get(
                    "relationship_changes", [])
            )

        # 导入关系历史
        self._relationship_history = []
        for r_data in data.get("relationship_history", []):
            self._relationship_history.append(RelationshipChange(
                chapter_num=r_data.get("chapter_num", 0),
                character1=r_data.get("character1", ""),
                character2=r_data.get("character2", ""),
                relationship_type=r_data.get("relationship_type", ""),
                previous_state=r_data.get("previous_state", ""),
                new_state=r_data.get("new_state", ""),
                description=r_data.get("description", "")
            ))

        # 导入已知地点
        self._known_locations = set(data.get("known_locations", []))

        # 重建人物名称集合
        self._character_names = set(self._character_states.keys())

        # 更新状态
        self._initialized = data.get("initialized", False)
        self._current_chapter = data.get("current_chapter", 0)

        self.logger.info(
            f"导入追踪器状态完成: {len(self._character_states)}个人物，"
            f"{len(self._chapter_snapshots)}个章节快照"
        )


