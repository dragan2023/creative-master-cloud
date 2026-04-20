"""
剧集剧本策略 - 上下文构建策略的具体实现

处理剧集剧本类型的上下文构建差异。

@date: 2026-04-19
@version: v1.0.0
"""
from typing import Dict, Any, Optional

from app.models import NovelChapter
from app.services.novel_writer.strategies.base import ContextBuildStrategy


class SeriesScriptStrategy(ContextBuildStrategy):
    """剧集剧本上下文构建策略

    剧集使用集(episode)作为生成单位，数据源为episode_outlines。
    """

    def get_unit_label(self) -> str:
        return "集"

    def get_unit_number_field(self) -> str:
        return "episode_number"

    def get_outlines_source(self, project) -> Optional[dict]:
        return getattr(project, 'episode_outlines', None)

    def get_outline_extract_pattern(self, unit_number: int) -> str:
        return rf"第{unit_number}集.*?(?=第\d+集|$)"

    def get_chapter_query_filter(self, project_id: int, current_unit: int, start_unit: int) -> list:
        return [
            NovelChapter.project_id == project_id,
            NovelChapter.episode_number < current_unit,
            NovelChapter.episode_number >= start_unit,
        ]

    def get_metadata_from_chapter(self, chapter) -> dict:
        ep_num = chapter.episode_number or chapter.chapter_number
        return {
            "unit_number": ep_num,
            "episode_number": ep_num,
            "title": getattr(chapter, 'chapter_title', None) or getattr(chapter, 'title', ''),
        }

    def format_ending_header(self, unit_number: int) -> str:
        return f"第{unit_number}集结尾："

    def format_summary_header(self, unit_number: int) -> str:
        return f"第{unit_number}集: "

    def get_content_type(self) -> str:
        return "series_script"
