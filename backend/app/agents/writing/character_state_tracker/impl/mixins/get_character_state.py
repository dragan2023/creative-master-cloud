"""CharacterStateTracker - get_character_stateMixin"""
from __future__ import annotations
from typing import Optional
import re


class GetCharacterStateMixin:
    """get_character_state功能域"""

    def get_character_state(self, name: str) -> Optional[CharacterState]:
        """获取人物当前状态

        Args:
            name: 人物名称

        Returns:
            人物状态对象，如果不存在返回None
        """
        return self._character_states.get(name)


