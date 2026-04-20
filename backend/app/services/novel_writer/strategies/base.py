"""
上下文构建策略基类

定义统一接口，三种内容类型（小说/剧集剧本/电影剧本）各自实现差异部分。
ContextWindowManager通过策略接口调用，消除三套build_*_context的代码冗余。

@date: 2026-04-19
@version: v1.0.0
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from sqlalchemy import select


class ContextBuildStrategy(ABC):
    """上下文构建策略基类

    定义内容类型差异化的接口，包括：
    - 单元标签和编号字段
    - 大纲数据源选择
    - 章节查询过滤条件
    - 大纲提取正则模式
    - 元数据提取
    - 近章内容获取
    """

    @abstractmethod
    def get_unit_label(self) -> str:
        """单元标签：章节/集/场"""
        ...

    @abstractmethod
    def get_unit_number_field(self) -> str:
        """数据库中单元编号字段名（NovelChapter模型属性名）"""
        ...

    @abstractmethod
    def get_outlines_source(self, project) -> Optional[dict]:
        """获取详细大纲数据源

        Args:
            project: NovelProject对象

        Returns:
            详细大纲字典（chapter_outlines/episode_outlines/scene_outlines）
        """
        ...

    @abstractmethod
    def get_outline_extract_pattern(self, unit_number: int) -> str:
        """大纲提取正则模式

        Args:
            unit_number: 当前单元号

        Returns:
            用于从基础大纲中提取当前单元段落的正则表达式
        """
        ...

    @abstractmethod
    def get_chapter_query_filter(self, project_id: int, current_unit: int, start_unit: int) -> list:
        """构建章节查询过滤条件

        Args:
            project_id: 项目ID
            current_unit: 当前单元号
            start_unit: 滑动窗口起始单元号

        Returns:
            SQLAlchemy过滤条件列表
        """
        ...

    @abstractmethod
    def get_metadata_from_chapter(self, chapter) -> dict:
        """从NovelChapter提取元数据

        Args:
            chapter: NovelChapter对象

        Returns:
            元数据字典，包含unit_number/title等
        """
        ...

    @abstractmethod
    def format_ending_header(self, unit_number: int) -> str:
        """格式化章节结尾的标题

        Args:
            unit_number: 单元号

        Returns:
            格式化的标题字符串，如"第3章结尾："
        """
        ...

    @abstractmethod
    def format_summary_header(self, unit_number: int) -> str:
        """格式化摘要的标题

        Args:
            unit_number: 单元号

        Returns:
            格式化的标题字符串，如"第3章: "
        """
        ...

    def get_unit_number_from_chapter(self, chapter) -> int:
        """从章节对象获取单元编号（通用实现，子类可覆盖）

        Args:
            chapter: NovelChapter对象

        Returns:
            单元编号
        """
        field = self.get_unit_number_field()
        return getattr(chapter, field, None) or getattr(chapter, 'chapter_number', 0)

    def get_content_type(self) -> str:
        """获取内容类型标识符"""
        return "novel"  # 默认值，子类覆盖
