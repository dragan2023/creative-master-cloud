"""ProjectKnowledgeBase - 主类（组合所有Mixin）"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.vector_store import get_vector_store
from app.tools.novel_graph_rag.impl.generator import NovelKnowledgeGraph
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
    InheritKnowledgeGraphMixin,
    RepairKbVectorStoreMixin,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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
    InheritKnowledgeGraphMixin,
    RepairKbVectorStoreMixin,
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
        self.logger = get_logger("project_knowledge_base")
        
        # 延迟加载向量库（避免初始化时阻塞）
        self._vector_store = None

        # GraphRAG实例缓存（使用正文板块专属类型）
        self._graph_instances: Dict[int, NovelKnowledgeGraph] = {}
    
    @property
    def vector_store(self):
        """延迟加载向量库（避免初始化时阻塞）"""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store


# 全局实例
_instance = None


def get_project_knowledge_base() -> "ProjectKnowledgeBase":
    """获取ProjectKnowledgeBase实例"""
    global _instance
    if _instance is None:
        _instance = ProjectKnowledgeBase()
    return _instance
