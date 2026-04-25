"""NovelKnowledgeGraph包 - 替代原单文件，保持向后兼容"""
from app.tools.novel_graph_rag.impl import NovelKnowledgeGraph, NovelEntityExtractor
from app.tools.novel_graph_rag.impl.generator import get_novel_knowledge_graph
from app.tools.novel_graph_rag.constants import (
    NOVEL_ENTITY_TYPES,
    NOVEL_RELATION_TYPES,
    FORBIDDEN_RELATION_TYPES,
    NOVEL_CHUNK_SIZE,
    NOVEL_MAX_ENTITIES_PER_CHUNK,
    NOVEL_MAX_RELATIONS_PER_CHUNK,
    CHARACTER_STATE_MAX_ENTITIES,
    CHARACTER_STATE_MAX_RELATIONS,
)
from app.tools.novel_graph_rag.prompts import (
    CHARACTER_STATE_EXTRACTION_PROMPT,
    EXTENDED_STATE_EXTRACTION_PROMPT,
    NOVEL_EXTRACTION_PROMPT,
)

__all__ = [
    'NovelKnowledgeGraph',
    'NovelEntityExtractor',
    'get_novel_knowledge_graph',
    'NOVEL_ENTITY_TYPES',
    'NOVEL_RELATION_TYPES',
    'FORBIDDEN_RELATION_TYPES',
    'NOVEL_CHUNK_SIZE',
    'NOVEL_MAX_ENTITIES_PER_CHUNK',
    'NOVEL_MAX_RELATIONS_PER_CHUNK',
    'CHARACTER_STATE_MAX_ENTITIES',
    'CHARACTER_STATE_MAX_RELATIONS',
    'CHARACTER_STATE_EXTRACTION_PROMPT',
    'EXTENDED_STATE_EXTRACTION_PROMPT',
    'NOVEL_EXTRACTION_PROMPT',
]
