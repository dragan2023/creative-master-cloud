"""CharacterStateTracker - 主类（组合所有Mixin）"""
from __future__ import annotations
from typing import Dict, List, Set, Optional

from app.core.logger import get_logger
from app.agents.writing.character_state_tracker.api import CharacterState, ChapterSnapshot, RelationshipChange
from app.agents.writing.character_state_tracker.impl.mixins import (
    InitializeMixin,
    GetCharacterStateMixin,
    GetAllCharactersMixin,
    GetChapterSnapshotMixin,
    GetStateEvolutionMixin,
    DetectNewCharactersMixin,
    DetectNewEntitiesMixin,
    MergeNewEntitiesToGlobalMixin,
    UpdateCharacterStateMixin,
    RecordChapterSnapshotMixin,
    AddRelationshipChangeMixin,
    GetRelationshipSummaryMixin,
    GetStateSummaryMixin,
    GetEvolutionTableMixin,
    CheckConsistencyMixin,
    ExportToDictMixin,
    ImportFromDictMixin,
    SaveMixin,
    LoadMixin,
    SyncFromKnowledgeGraphMixin,
    ExportToKnowledgeGraphMixin,
    ExportCharacterProfilesToKnowledgeGraphMixin,
    SyncUnitToGlobalGraphMixin,
    SyncUnitToGlobalGraphExtraMixin,
    GetStateForPromptMixin,
    ExtractKnowledgeGraphFromContentMixin,
    GetKnowledgeGraphContextForWritingMixin,
    GenerateCharacterProfilesFromOutlineMixin,
    GenerateProfileForNewCharacterMixin,
    VerifyNewCharactersWithLlmMixin,
)

class CharacterStateTracker(
    InitializeMixin,
    GetCharacterStateMixin,
    GetAllCharactersMixin,
    GetChapterSnapshotMixin,
    GetStateEvolutionMixin,
    DetectNewCharactersMixin,
    DetectNewEntitiesMixin,
    MergeNewEntitiesToGlobalMixin,
    UpdateCharacterStateMixin,
    RecordChapterSnapshotMixin,
    AddRelationshipChangeMixin,
    GetRelationshipSummaryMixin,
    GetStateSummaryMixin,
    GetEvolutionTableMixin,
    CheckConsistencyMixin,
    ExportToDictMixin,
    ImportFromDictMixin,
    SaveMixin,
    LoadMixin,
    SyncFromKnowledgeGraphMixin,
    ExportToKnowledgeGraphMixin,
    ExportCharacterProfilesToKnowledgeGraphMixin,
    SyncUnitToGlobalGraphMixin,
    SyncUnitToGlobalGraphExtraMixin,
    GetStateForPromptMixin,
    ExtractKnowledgeGraphFromContentMixin,
    GetKnowledgeGraphContextForWritingMixin,
    GenerateCharacterProfilesFromOutlineMixin,
    GenerateProfileForNewCharacterMixin,
    VerifyNewCharactersWithLlmMixin,
):
    """CharacterStateTracker - 组合Mixin实现"""

    def __init__(
        self,
        project_id: int,
        persist_dir: Optional[str] = None
    ):
        """初始化追踪器

        Args:
            project_id: 项目ID
            persist_dir: 持久化目录（可选，默认使用项目数据目录）
        """
        self.project_id = project_id
        self.persist_dir = persist_dir

        # 内存中的状态存储
        self._character_states: Dict[str, CharacterState] = {}  # 人物名 -> 最新状态
        self._chapter_snapshots: Dict[int, ChapterSnapshot] = {}  # 章节号 -> 快照
        self._relationship_history: List[RelationshipChange] = []  # 关系变化历史
        self._character_names: Set[str] = set()  # 已知人物名称集合

        # 已知地点集合（用于位置一致性检查）
        self._known_locations: Set[str] = set()

        # 追踪器状态
        self._initialized = False
        self._current_chapter = 0

        # 延迟导入logger
        from app.core.logger import get_logger
        self.logger = get_logger("character_state_tracker")


# 全局实例
_instance = None


def get_character_state_tracker() -> "CharacterStateTracker":
    """获取CharacterStateTracker实例"""
    global _instance
    if _instance is None:
        _instance = CharacterStateTracker()
    return _instance
