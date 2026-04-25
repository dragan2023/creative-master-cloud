"""NovelKnowledgeGraph - 主类（组合所有Mixin）"""
import networkx as nx
from app.core.logger import get_logger
from app.tools.novel_graph_rag.impl.mixins import (
    LoadMixin,
    SaveMixin,
    AddEntityMixin,
    AddRelationMixin,
    GetEntityByTextMixin,
    GetEntitiesByTypeMixin,
    GetCharacterProfilesMixin,
    GetWorldSettingsMixin,
    GetRelatedEntitiesMixin,
    GetCharacterStateEntitiesMixin,
    GetCharacterEvolutionMixin,
    FormatCharacterStateForPromptMixin,
    GetExtendedStateEntitiesMixin,
    GetConsistencyReportMixin,
    FormatConsistencyReportForPromptMixin,
)

class NovelKnowledgeGraph(
    LoadMixin,
    SaveMixin,
    AddEntityMixin,
    AddRelationMixin,
    GetEntityByTextMixin,
    GetEntitiesByTypeMixin,
    GetCharacterProfilesMixin,
    GetWorldSettingsMixin,
    GetRelatedEntitiesMixin,
    GetCharacterStateEntitiesMixin,
    GetCharacterEvolutionMixin,
    FormatCharacterStateForPromptMixin,
    GetExtendedStateEntitiesMixin,
    GetConsistencyReportMixin,
    FormatConsistencyReportForPromptMixin,
):
    """NovelKnowledgeGraph - 组合Mixin实现"""

    def __init__(self, persist_path: str = None):
        """
        初始化知识图谱

        Args:
            persist_path: 持久化文件路径
        """
        self.graph = nx.DiGraph()
        self.persist_path = persist_path
        self.logger = get_logger("novel_knowledge_graph")
        self.entity_index = {}  # 实体文本到节点ID的映射


# 全局实例
_instance = None


def get_novel_knowledge_graph() -> "NovelKnowledgeGraph":
    """获取NovelKnowledgeGraph实例"""
    global _instance
    if _instance is None:
        _instance = NovelKnowledgeGraph()
    return _instance
