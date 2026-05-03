"""CharacterStateTracker - initializeMixin"""
from __future__ import annotations
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
import re
import os

from app.agents.writing.character_state_tracker.api import CharacterState, CharacterStatus


class InitializeMixin:
    """initialize功能域"""

    async def initialize(
        self,
        character_profiles: List[Dict[str, Any]],
        world_settings: Optional[Dict[str, Any]] = None
    ) -> None:
        """初始化人物状态追踪器

        从初始人物设定加载人物状态，构建追踪基线。

        Args:
            character_profiles: 初始人物设定列表
            world_settings: 世界观设定（包含地点等）
        """
        self.logger.info(f"初始化人物状态追踪器，项目ID: {self.project_id}")

        # 加载初始人物设定
        for profile in character_profiles:
            name = profile.get("name", "")
            if not name:
                continue

            state = CharacterState(
                name=name,
                identity=profile.get("identity", profile.get("position", "")),
                location=profile.get(
                    "location", profile.get("initial_location", "")),
                status=CharacterStatus.ACTIVE,
                relationships=profile.get("relationships", {}),
                attributes={
                    "personality": profile.get("personality", ""),
                    "background": profile.get("background", ""),
                    "traits": profile.get("traits", []),
                    "age": profile.get("age", ""),
                    "gender": profile.get("gender", "")
                },
                first_appearance=0,  # 初始设定，视为第0章
                last_appearance=0,
                speech_style=profile.get("speech_style", {})  # 新增：台词风格
            )

            # 如果没有预设speech_style,根据性格和背景自动生成
            if not state.speech_style:
                state.speech_style = self._infer_speech_style_from_profile(
                    profile)

            self._character_states[name] = state
            self._character_names.add(name)

            # 记录初始位置
            if state.location:
                self._known_locations.add(state.location)

        # 加载世界观中的地点
        if world_settings:
            locations = world_settings.get("locations", [])
            for loc in locations:
                loc_name = loc.get("name", "")
                if loc_name:
                    self._known_locations.add(loc_name)

        self._initialized = True
        self.logger.info(
            f"人物状态追踪器初始化完成，已加载 {len(self._character_states)} 个人物，"
            f"{len(self._known_locations)} 个地点"
        )


