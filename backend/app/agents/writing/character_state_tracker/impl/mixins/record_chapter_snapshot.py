"""CharacterStateTracker - record_chapter_snapshotMixin"""
from __future__ import annotations
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
from datetime import datetime
import re
import time
import copy

from app.agents.writing.character_state_tracker.api import CharacterState, CharacterStatus, ChapterSnapshot


class RecordChapterSnapshotMixin:
    """record_chapter_snapshot功能域"""

    def record_chapter_snapshot(
        self,
        chapter_num: int,
        chapter_title: str,
        content: str,
        characters_present: Optional[List[str]] = None,
        character_updates: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> ChapterSnapshot:
        """记录章节人物状态快照

        这是追踪器的核心方法，在每章完成后调用：
        1. 更新出场人物的状态
        2. 检测并记录新人物
        3. 生成状态快照
        4. 更新关系变化

        Args:
            chapter_num: 章节号
            chapter_title: 章节标题
            content: 章节内容
            characters_present: 出场人物列表（可选，不提供则自动检测）
            character_updates: 人物状态更新（可选，由LLM提取）

        Returns:
            生成的章节快照
        """
        self.logger.info(f"记录第{chapter_num}章人物状态快照")

        # 自动检测出场人物（如果未提供）
        if characters_present is None:
            characters_present = self._detect_present_characters(content)

        # 检测新人物
        new_characters = self.detect_new_characters(content)

        # 构建快照
        snapshot_characters: Dict[str, CharacterState] = {}
        new_char_names = []

        for name in characters_present:
            # 获取或创建状态
            if name in self._character_states:
                state = self._character_states[name]
            else:
                # 新人物
                state = CharacterState(
                    name=name,
                    first_appearance=chapter_num,
                    last_appearance=chapter_num
                )
                self._character_states[name] = state
                self._character_names.add(name)
                new_char_names.append(name)

            # 应用外部提供的更新
            if character_updates and name in character_updates:
                updates = character_updates[name]
                if "identity" in updates:
                    state.identity = updates["identity"]
                if "location" in updates:
                    state.location = updates["location"]
                    if updates["location"]:
                        self._known_locations.add(updates["location"])
                if "status_change" in updates:
                    state.status_change = updates["status_change"]
                if "relationships" in updates:
                    state.relationships.update(updates["relationships"])

            state.last_appearance = chapter_num
            state.status = CharacterStatus.ACTIVE

            # 添加到快照
            snapshot_characters[name] = CharacterState(
                name=state.name,
                identity=state.identity,
                location=state.location,
                status=CharacterStatus.ACTIVE,
                status_change=state.status_change,
                relationships=state.relationships.copy(),
                attributes=state.attributes.copy(),
                first_appearance=state.first_appearance,
                last_appearance=state.last_appearance
            )

        # 标记未出场人物状态
        for name, state in self._character_states.items():
            if name not in characters_present:
                # 检查是否被提及
                if name in content:
                    state.status = CharacterStatus.MENTIONED
                else:
                    state.status = CharacterStatus.ABSENT

        # 创建快照
        snapshot = ChapterSnapshot(
            chapter_num=chapter_num,
            chapter_title=chapter_title,
            timestamp=datetime.now().isoformat(),
            characters=snapshot_characters,
            new_characters=new_char_names,
            relationship_changes=[]  # 关系变化由外部检测后添加
        )

        self._chapter_snapshots[chapter_num] = snapshot
        self._current_chapter = chapter_num

        self.logger.info(
            f"第{chapter_num}章快照记录完成: {len(snapshot_characters)}个出场人物，"
            f"{len(new_char_names)}个新人物"
        )

        return snapshot


    def _detect_present_characters(self, content: str) -> List[str]:
        """从内容中检测实际出场人物

        区分“被提及”和“实际出场”：
        - 实际出场：有对话、动作、心理描写等
        - 被提及：仅被他人提到名字

        Args:
            content: 章节内容

        Returns:
            实际出场人物名称列表
        """
        present = []
        mentioned_only = []  # 仅被提及的人物

        for name in self._character_names:
            # 统计名称出现次数
            count = content.count(name)

            if count == 0:
                continue

            # 检查是否有实际出场迹象（对话、动作、心理描写）
            has_dialogue = self._check_character_dialogue(name, content)
            has_action = self._check_character_action(name, content)
            has_mental = self._check_character_mental(name, content)

            if has_dialogue or has_action or has_mental:
                # 有对话/动作/心理描写，认为实际出场
                present.append(name)
            elif count >= 2:
                # 仅被提及，出现2次以上才记录
                mentioned_only.append(name)

        # 记录日志区分出场和提及
        if mentioned_only:
            self.logger.debug(
                f"仅被提及的人物: {mentioned_only}")

        return present


    def _check_character_dialogue(self, name: str, content: str) -> bool:
        """检查人物是否有对话

        Args:
            name: 人物名称
            content: 章节内容

        Returns:
            是否有对话
        """
        # 模式：引号后跟人物名+对话动词
        patterns = [
            rf'"[^"]*"[，。]?\s*{re.escape(name)}(说道|问道|答道|笑道|怒道|叹道|喊道|叫道|低声道|高声道|沉声道)',
            rf'{re.escape(name)}(说道|问道|答道|笑道|怒道|叹道|喊道|叫道)[：:"“]',
            rf'{re.escape(name)}[，。]\s*"',  # 人物名后跟引号
        ]

        for pattern in patterns:
            if re.search(pattern, content):
                return True
        return False


    def _check_character_action(self, name: str, content: str) -> bool:
        """检查人物是否有动作描写

        Args:
            name: 人物名称
            content: 章节内容

        Returns:
            是否有动作描写
        """
        # 模式：句首或句号后跟人物名+动作动词
        action_verbs = [
            '走上前', '转过身', '抬起头', '低下头', '站起身', '坐下来',
            '迈步', '走进', '离开', '来到', '看向', '望向', '伸手', '握住',
            '拱手', '作揖', '行礼', '点头', '摇头', '皱眉', '微笑', '叹气'
        ]

        for verb in action_verbs:
            # 检查是否是主语位置（句首或句号后）
            pattern = rf'(?:^|[。！？\n])\s*{re.escape(name)}{verb}'
            if re.search(pattern, content):
                return True

        return False


    def _check_character_mental(self, name: str, content: str) -> bool:
        """检查人物是否有心理描写

        Args:
            name: 人物名称
            content: 章节内容

        Returns:
            是否有心理描写
        """
        # 模式：人物名+心理动词/形容词
        mental_patterns = [
            rf'{re.escape(name)}(心中|心里|暗自|不禁|不由得)',
            rf'{re.escape(name)}(感到|觉得|想到|想起|意识到)',
            rf'{re.escape(name)}(心中[一二三四五六七八九十]+惊|喜|忧|怒)',
        ]

        for pattern in mental_patterns:
            if re.search(pattern, content):
                return True
        return False


