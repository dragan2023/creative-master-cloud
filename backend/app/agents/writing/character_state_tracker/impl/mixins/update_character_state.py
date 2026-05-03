"""CharacterStateTracker - update_character_stateMixin"""
from __future__ import annotations
from typing import Dict
from typing import Optional
from typing import Any
import re

from app.agents.writing.character_state_tracker.api import CharacterState, CharacterStatus


class UpdateCharacterStateMixin:
    """update_character_state功能域"""

    def update_character_state(
        self,
        name: str,
        updates: Dict[str, Any],
        chapter_num: Optional[int] = None
    ) -> bool:
        """更新人物状态

        Args:
            name: 人物名称
            updates: 更新内容，可包含identity, location, status_change, relationships等
            chapter_num: 当前章节号

        Returns:
            是否更新成功
        """
        if name not in self._character_states:
            # 创建新人物状态
            self._character_states[name] = CharacterState(
                name=name,
                first_appearance=chapter_num,
                last_appearance=chapter_num
            )
            self._character_names.add(name)
            self.logger.info(f"创建新人物状态记录: {name}")

        state = self._character_states[name]

        # 更新各字段
        if "identity" in updates:
            state.identity = updates["identity"]
        if "location" in updates:
            old_location = state.location
            state.location = updates["location"]
            # 记录新地点
            if updates["location"]:
                self._known_locations.add(updates["location"])
        if "status_change" in updates:
            state.status_change = updates["status_change"]
        if "status" in updates:
            if isinstance(updates["status"], str):
                state.status = CharacterStatus(updates["status"])
            else:
                state.status = updates["status"]
        if "relationships" in updates:
            state.relationships.update(updates["relationships"])
        if "attributes" in updates:
            state.attributes.update(updates["attributes"])
        if "speech_style" in updates:
            # 更新台词风格
            state.speech_style.update(updates["speech_style"])

        # 更新出场章节
        if chapter_num is not None:
            if state.first_appearance is None:
                state.first_appearance = chapter_num
            state.last_appearance = chapter_num

        self.logger.debug(f"更新人物状态: {name} -> {updates}")
        return True


