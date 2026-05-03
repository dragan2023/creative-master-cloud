"""
多Agent协作文学作品生成系统 - 知识顾问Agent 适配器模块

从 knowledge_agent.py 拆分，包含上下文管理器和知识库的适配器类。

@date: 2026-04-24
@version: v2.0.0
"""

from typing import Dict, Any, List, Optional


class ContextManagerAdapter:
    """上下文管理器适配器

    包装旧的ContextWindowManager，实现松耦合引用。
    使用懒加载模式，只在需要时才导入和实例化旧模块。
    """

    def __init__(self):
        self._manager_class = None
        self._manager_instance = None

    def _get_manager_class(self):
        """获取管理器类（懒加载）"""
        if self._manager_class is None:
            try:
                from app.services.novel_writer.context_manager import ContextWindowManager
                self._manager_class = ContextWindowManager
            except ImportError as e:
                return None
        return self._manager_class

    async def get_relevant_context(
        self,
        query: str,
        project_id: int,
        top_k: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """获取相关上下文

        从向量存储中检索与查询相关的历史内容片段。

        Args:
            query: 查询文本
            project_id: 项目ID
            top_k: 返回结果数量
            **kwargs: 其他参数

        Returns:
            相关内容片段列表
        """
        manager_class = self._get_manager_class()
        if manager_class is None:
            return []

        try:
            manager = self._get_instance(project_id)
            if hasattr(manager, 'search_relevant'):
                results = await manager.search_relevant(query, top_k=top_k)
                return results
            else:
                return []
        except Exception as e:
            return []

    def _get_instance(self, project_id: int):
        """获取管理器实例"""
        if self._manager_instance is None:
            manager_class = self._get_manager_class()
            if manager_class:
                self._manager_instance = manager_class(project_id=project_id)
        return self._manager_instance


class KnowledgeBaseAdapter:
    """项目知识库适配器

    包装旧的ProjectKnowledgeBase，实现松耦合引用。
    使用懒加载模式，只在需要时才导入和实例化旧模块。
    """

    def __init__(self):
        self._kb_class = None
        self._kb_instance = None

    def _get_kb_class(self):
        """获取知识库类（懒加载）"""
        if self._kb_class is None:
            try:
                from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
                self._kb_class = ProjectKnowledgeBase
            except ImportError:
                return None
        return self._kb_class

    async def search_knowledge(
        self,
        query: str,
        project_id: int,
        knowledge_types: Optional[List[str]] = None,
        top_k: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """搜索知识

        从知识图谱和向量存储中检索相关知识。

        Args:
            query: 查询文本
            project_id: 项目ID
            knowledge_types: 知识类型过滤
            top_k: 返回结果数量
            **kwargs: 其他参数

        Returns:
            知识检索结果
        """
        kb_class = self._get_kb_class()
        if kb_class is None:
            return self._empty_result()

        try:
            kb = self._get_instance(project_id)
            if hasattr(kb, 'search'):
                results = await kb.search(
                    query=query,
                    types=knowledge_types,
                    top_k=top_k
                )
                return results
            else:
                return self._empty_result()
        except Exception as e:
            return self._empty_result()

    async def get_character_relations(
        self,
        project_id: int,
        character_names: List[str]
    ) -> List[Dict[str, Any]]:
        """获取角色关系

        Args:
            project_id: 项目ID
            character_names: 角色名称列表

        Returns:
            角色关系列表
        """
        kb_class = self._get_kb_class()
        if kb_class is None:
            return []

        try:
            kb = self._get_instance(project_id)
            if hasattr(kb, 'get_relations'):
                relations = await kb.get_relations(
                    entity_names=character_names,
                    relation_type="character"
                )
                return relations
            else:
                return []
        except Exception as e:
            return []

    async def get_plot_threads(
        self,
        project_id: int,
        current_chapter: int
    ) -> List[Dict[str, Any]]:
        """获取剧情线索

        Args:
            project_id: 项目ID
            current_chapter: 当前章节号

        Returns:
            剧情线索列表
        """
        kb_class = self._get_kb_class()
        if kb_class is None:
            return []

        try:
            kb = self._get_instance(project_id)
            if hasattr(kb, 'get_plot_threads'):
                threads = await kb.get_plot_threads(
                    up_to_chapter=current_chapter
                )
                return threads
            else:
                return []
        except Exception as e:
            return []

    def _get_instance(self, project_id: int):
        """获取知识库实例"""
        if self._kb_instance is None:
            kb_class = self._get_kb_class()
            if kb_class:
                self._kb_instance = kb_class(project_id=project_id)
        return self._kb_instance

    def _empty_result(self) -> Dict[str, Any]:
        """返回空结果结构"""
        return {
            "characters": [],
            "events": [],
            "settings": [],
            "relations": []
        }
