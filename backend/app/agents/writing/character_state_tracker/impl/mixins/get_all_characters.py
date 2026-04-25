"""CharacterStateTracker - get_all_charactersMixin"""
from __future__ import annotations
from typing import Dict
import re
import copy


class GetAllCharactersMixin:
    """get_all_characters功能域"""

    def get_all_characters(self) -> Dict[str, CharacterState]:
        """获取所有人物状态"""
        return self._character_states.copy()


