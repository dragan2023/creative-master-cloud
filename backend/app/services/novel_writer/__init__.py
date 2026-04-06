"""
小说/剧本正文生成服务模块

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from app.services.novel_writer.context_manager import ContextWindowManager
from app.services.novel_writer.consistency import ConsistencyManager
from app.services.novel_writer.vector_store import ProjectVectorStore
from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
from app.services.novel_writer.prompt_templates import (
    NOVEL_CHAPTER_PROMPT,
    SERIES_SCRIPT_SCENE_PROMPT,
    MOVIE_SCRIPT_SCENE_PROMPT,
    SCRIPT_SCENE_PROMPT,
    DIRECTORY_GENERATE_PROMPT,
    SUMMARY_UPDATE_PROMPT,
    CHARACTER_UPDATE_PROMPT,
    CONSISTENCY_CHECK_PROMPT,
    KNOWLEDGE_FILTER_PROMPT
)
from app.services.novel_writer.exporter import NovelExporter

__all__ = [
    "ContextWindowManager",
    "ConsistencyManager",
    "ProjectVectorStore",
    "ProjectKnowledgeBase",
    "NovelExporter",
    "NOVEL_CHAPTER_PROMPT",
    "SERIES_SCRIPT_SCENE_PROMPT",
    "MOVIE_SCRIPT_SCENE_PROMPT",
    "SCRIPT_SCENE_PROMPT",
    "DIRECTORY_GENERATE_PROMPT",
    "SUMMARY_UPDATE_PROMPT",
    "CHARACTER_UPDATE_PROMPT",
    "CONSISTENCY_CHECK_PROMPT",
    "KNOWLEDGE_FILTER_PROMPT",
]
