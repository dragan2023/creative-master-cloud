"""
小说策略 - 上下文构建策略的具体实现

处理小说类型的上下文构建差异。

@date: 2026-04-19
@version: v1.0.0
"""
from typing import Dict, Any, Optional

from app.models import NovelChapter
from app.services.novel_writer.strategies.base import ContextBuildStrategy


class NovelStrategy(ContextBuildStrategy):
    """小说上下文构建策略

    小说使用章节(chapter)作为生成单位，数据源为chapter_outlines。
    """

    def get_unit_label(self) -> str:
        return "章节"

    def get_unit_number_field(self) -> str:
        return "chapter_number"

    def get_outlines_source(self, project) -> Optional[dict]:
        return getattr(project, 'chapter_outlines', None)

    def get_outline_extract_pattern(self, unit_number: int) -> str:
        return rf"第{unit_number}章.*?(?=第\d+章|$)"

    def get_chapter_query_filter(self, project_id: int, current_unit: int, start_unit: int) -> list:
        return [
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number < current_unit,
            NovelChapter.chapter_number >= start_unit,
        ]

    def get_metadata_from_chapter(self, chapter) -> dict:
        return {
            "unit_number": chapter.chapter_number,
            "chapter_number": chapter.chapter_number,
            "title": getattr(chapter, 'chapter_title', None) or getattr(chapter, 'title', ''),
        }

    def format_ending_header(self, unit_number: int) -> str:
        return f"第{unit_number}章结尾："

    def format_summary_header(self, unit_number: int) -> str:
        return f"第{unit_number}章: "

    def get_content_type(self) -> str:
        return "novel"
