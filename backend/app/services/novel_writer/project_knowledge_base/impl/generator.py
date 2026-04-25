"""ProjectKnowledgeBase - 主类（组合所有Mixin）"""
from __future__ import annotations

from app.core.logger import get_logger
from app.services.novel_writer.project_knowledge_base.impl.mixins import (
    GetCollectionNameMixin,
    GetGraphPathMixin,
    InitializeProjectKbMixin,
    BuildGlobalOutlineGraphMixin,
    BuildUnitOutlineGraphMixin,
    RetrieveForRevisionMixin,
    RetrieveGlobalOnlyMixin,
    GetKnowledgeGraphDataMixin,
    DeleteProjectKbMixin,
    GetKbStatsMixin,
    ExtractAndStoreCharacterStatesMixin,
    GetCharacterStatesForWritingMixin,
    GetAllCharacterStatesForChapterMixin,
    SyncUnitEntitiesToGlobalMixin,
    DetectAndMergeNewEntitiesMixin,
)

class ProjectKnowledgeBase(
    GetCollectionNameMixin,
    GetGraphPathMixin,
    InitializeProjectKbMixin,
    BuildGlobalOutlineGraphMixin,
    BuildUnitOutlineGraphMixin,
    RetrieveForRevisionMixin,
    RetrieveGlobalOnlyMixin,
    GetKnowledgeGraphDataMixin,
    DeleteProjectKbMixin,
    GetKbStatsMixin,
    ExtractAndStoreCharacterStatesMixin,
    GetCharacterStatesForWritingMixin,
    GetAllCharacterStatesForChapterMixin,
    SyncUnitEntitiesToGlobalMixin,
    DetectAndMergeNewEntitiesMixin,
):
    """ProjectKnowledgeBase - 组合Mixin实现"""

    def __init__(self, db: AsyncSession = None, persist_dir: str = None):
        """
        初始化项目知识库管理器

        Args:
            db: 数据库会话
            persist_dir: 持久化目录
        """
        self.db = db
        self.settings = get_settings()
        self.persist_dir = persist_dir or self.settings.get_knowledge_graph_dir()
        self.vector_store = get_vector_store()
        self.logger = get_logger("project_knowledge_base")

        # GraphRAG实例缓存（使用正文板块专属类型）
        self._graph_instances: Dict[int, NovelKnowledgeGraph] = {}


# 全局实例
_instance = None


def get_project_knowledge_base() -> "ProjectKnowledgeBase":
    """获取ProjectKnowledgeBase实例"""
    global _instance
    if _instance is None:
        _instance = ProjectKnowledgeBase()
    return _instance
