"""ProjectKnowledgeBase包 - 替代原单文件，保持向后兼容"""
from app.services.novel_writer.project_knowledge_base.impl import ProjectKnowledgeBase
from app.services.novel_writer.project_knowledge_base.impl.generator import get_project_knowledge_base

__all__ = ['ProjectKnowledgeBase', 'get_project_knowledge_base']
