"""
小说/剧本正文生成服务模块
"""
from app.services.novel_writer.generator import NovelChapterGenerator
from app.services.novel_writer.context_manager import ContextWindowManager
from app.services.novel_writer.consistency import ConsistencyManager
from app.services.novel_writer.vector_store import ProjectVectorStore
from app.services.novel_writer.knowledge_integration import NovelKnowledgeIntegration
from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
from app.services.novel_writer.content_reviser import ContentReviser, revise_content_with_knowledge_base
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
    "NovelChapterGenerator",
    "ContextWindowManager",
    "ConsistencyManager",
    "ProjectVectorStore",
    "NovelKnowledgeIntegration",
    "ProjectKnowledgeBase",
    "ContentReviser",
    "revise_content_with_knowledge_base",
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
