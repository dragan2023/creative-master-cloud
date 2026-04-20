"""
电影剧本策略 - 上下文构建策略的具体实现

处理电影剧本类型的上下文构建差异。

@date: 2026-04-19
@version: v1.0.0
"""
from typing import Dict, Any, Optional

from app.models import NovelChapter
from app.services.novel_writer.strategies.base import ContextBuildStrategy


class MovieScriptStrategy(ContextBuildStrategy):
    """电影剧本上下文构建策略

    电影剧本使用场(scene)作为生成单位，数据源为scene_outlines。
    """

    def get_unit_label(self) -> str:
        return "场"

    def get_unit_number_field(self) -> str:
        return "scene_number"

    def get_outlines_source(self, project) -> Optional[dict]:
        return getattr(project, 'scene_outlines', None)

    def get_outline_extract_pattern(self, unit_number: int) -> str:
        # 支持两种命名模式："第N场" 和 "场景N"
        return rf"(第{unit_number}场|场景{unit_number}).*?(?=(第\d+场|场景\d+)|$)"

    def get_chapter_query_filter(self, project_id: int, current_unit: int, start_unit: int) -> list:
        return [
            NovelChapter.project_id == project_id,
            NovelChapter.scene_number < current_unit,
            NovelChapter.scene_number >= start_unit,
        ]

    def get_metadata_from_chapter(self, chapter) -> dict:
        sc_num = chapter.scene_number or chapter.chapter_number
        return {
            "unit_number": sc_num,
            "scene_number": sc_num,
            "title": getattr(chapter, 'chapter_title', None) or getattr(chapter, 'title', ''),
        }

    def format_ending_header(self, unit_number: int) -> str:
        return f"第{unit_number}场结尾："

    def format_summary_header(self, unit_number: int) -> str:
        return f"第{unit_number}场: "

    def get_content_type(self) -> str:
        return "movie_script"
