"""ProjectKnowledgeBase - get_collection_nameMixin"""
import re


class GetCollectionNameMixin:
    """get_collection_name功能域"""

    def get_collection_name(self, project_id: int) -> str:
        """获取项目知识库的集合名称"""
        return f"project_{project_id}_kb"


