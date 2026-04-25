"""CharacterStateTracker - get_chapter_snapshotMixin"""
from __future__ import annotations
from typing import Optional
import re


class GetChapterSnapshotMixin:
    """get_chapter_snapshot功能域"""

    def get_chapter_snapshot(self, chapter_num: int) -> Optional[ChapterSnapshot]:
        """获取指定章节的状态快照

        Args:
            chapter_num: 章节号

        Returns:
            章节快照，如果不存在返回None
        """
        return self._chapter_snapshots.get(chapter_num)


