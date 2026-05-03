"""知识图谱相关API

包含 get_global_knowledge_graph, get_all_general_knowledge_bases,
get_knowledge_graph, extract_entities_from_kb, _extract_entities_task
"""

from typing import Dict, Any, List

from sqlalchemy import select
from fastapi import BackgroundTasks, Depends

from app.core.logger import get_logger
from app.core.exceptions import ResourceNotFoundException, ValidationException, AuthorizationException, KnowledgeBaseException
from app.models import KnowledgeBase, KnowledgeBaseStatus, KnowledgeBaseCategory, User
from app.schemas.knowledge import KnowledgeGraphData, KnowledgeBaseResponse
from app.schemas.common import ResponseModel

logger = get_logger(__name__)


async def get_global_knowledge_graph_handler(
    max_nodes: int,
    current_user: User
):
    """获取全局知识图谱数据"""
    from app.tools.graph_rag import graph_rag
    graph_data = graph_rag.get_graph_data(max_nodes=max_nodes)
    return ResponseModel(data=graph_data)


async def get_all_general_knowledge_bases_handler(
    current_user: User,
    db
):
    """获取所有通用类型的知识库"""
    try:
        result = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.category == KnowledgeBaseCategory.GENERAL)
            .where(KnowledgeBase.status == KnowledgeBaseStatus.READY)
            .order_by(KnowledgeBase.created_at.desc())
        )
        knowledge_bases = result.scalars().all()

        return ResponseModel(data=[
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "type": kb.type,
                "category": kb.category,
                "status": kb.status,
                "file_type": kb.file_type,
                "file_size": kb.file_size,
                "document_count": kb.document_count,
                "preprocessor_metadata": kb.preprocessor_metadata,
                "created_at": kb.created_at.isoformat() if kb.created_at else None
            }
            for kb in knowledge_bases
        ])
    except Exception as e:
        logger.error(f"获取通用知识库失败: {e}")
        raise KnowledgeBaseException(f"获取失败: {str(e)}")


async def get_knowledge_graph_handler(
    kb_id: int,
    max_nodes: int,
    current_user: User,
    db
):
    """获取知识库的知识图谱数据"""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    if kb.user_id and kb.user_id != current_user.id and not current_user.is_admin:
        raise AuthorizationException("无权访问此知识库")

    try:
        from app.tools.graph_rag import GraphRAG
        graph_rag = GraphRAG(
            kb_category=kb.category.value if kb.category else "general")
        graph_data = graph_rag.get_graph_data(kb_id=kb_id, max_nodes=max_nodes)
        return ResponseModel(data=graph_data)
    except Exception as e:
        logger.error(f"获取知识图谱失败: {e}")
        raise KnowledgeBaseException(f"获取图谱失败: {str(e)}")


async def extract_entities_from_kb_handler(
    kb_id: int,
    background_tasks: BackgroundTasks,
    current_user: User,
    db
):
    """使用 LLM 从知识库文档中提取实体和关系"""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    if kb.user_id and kb.user_id != current_user.id and not current_user.is_admin:
        raise AuthorizationException("无权访问此知识库")

    if kb.status != KnowledgeBaseStatus.READY:
        raise ValidationException("知识库尚未就绪")

    background_tasks.add_task(
        _extract_entities_task,
        kb_id=kb_id,
        category=kb.category.value if kb.category else "general"
    )

    return ResponseModel(message="实体提取任务已启动，请稍后查看结果")


async def _extract_entities_task(kb_id: int, category: str):
    """后台执行实体提取任务"""
    try:
        from app.agents.llm_manager import llm_manager
        from app.tools.graph_rag import GraphRAG, LLMEntityExtractor
        from app.core.vector_store import get_vector_store

        llm_provider = llm_manager.get_default_provider()
        llm_extractor = LLMEntityExtractor(
            llm_provider=llm_provider,
            kb_category=category
        )
        vector_store = get_vector_store()

        logger.info(f"开始提取知识库 {kb_id} 的实体和关系")
    except Exception as e:
        logger.error(f"实体提取任务失败: {e}")
