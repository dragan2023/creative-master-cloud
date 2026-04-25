"""CharacterStateTracker - add_relationship_changeMixin"""
from __future__ import annotations
import re


class AddRelationshipChangeMixin:
    """add_relationship_change功能域"""

    def add_relationship_change(
        self,
        chapter_num: int,
        char1: str,
        char2: str,
        relationship_type: str,
        previous_state: str,
        new_state: str,
        description: str = ""
    ) -> None:
        """记录人物关系变化

        Args:
            chapter_num: 发生章节
            char1: 人物1
            char2: 人物2
            relationship_type: 关系类型
            previous_state: 之前的关系状态
            new_state: 新的关系状态
            description: 变化描述
        """
        change = RelationshipChange(
            chapter_num=chapter_num,
            character1=char1,
            character2=char2,
            relationship_type=relationship_type,
            previous_state=previous_state,
            new_state=new_state,
            description=description
        )

        self._relationship_history.append(change)

        # 更新到章节快照
        if chapter_num in self._chapter_snapshots:
            snapshot = self._chapter_snapshots[chapter_num]
            snapshot.relationship_changes.append({
                "characters": [char1, char2],
                "type": relationship_type,
                "previous": previous_state,
                "new": new_state,
                "description": description
            })

        self.logger.info(
            f"记录关系变化: {char1} ↔ {char2} ({relationship_type}): "
            f"{previous_state} -> {new_state}"
        )


