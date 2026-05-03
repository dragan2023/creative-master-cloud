"""知识库搜索与双轨检索

包含 search_knowledge_base 和 dual_track_retrieve
"""

from sqlalchemy import select
from fastapi import Depends

from app.core.logger import get_logger
from app.core.exceptions import (
    ResourceNotFoundException, ValidationException,
    KnowledgeBaseException, AuthorizationException
)
from app.models import (
    KnowledgeBase, KnowledgeBaseStatus, KnowledgeBaseCategory,
    KnowledgeBaseType, User
)
from app.tools import get_knowledge_retrieval_tool
from app.tools.graph_rag import DualTrackGraphRAG
from app.schemas.knowledge import DualTrackRetrieveRequest
from app.schemas.common import ResponseModel
from app.api.deps import get_current_user
from app.core.database import get_db

logger = get_logger(__name__)

# 全局双轨 GraphRAG 实例
dual_track_graph_rag = DualTrackGraphRAG()


async def search_knowledge_base_handler(
    kb_id: int,
    query: str,
    n_results: int,
    current_user: User,
    db
):
    """搜索知识库"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    if kb.status != KnowledgeBaseStatus.READY:
        raise ValidationException("知识库未就绪")

    retrieval_tool = get_knowledge_retrieval_tool()
    results = await retrieval_tool.retrieve(
        collection_name=kb.collection_name,
        query=query,
        n_results=n_results
    )

    return ResponseModel(data=results)


async def dual_track_retrieve_handler(
    request: DualTrackRetrieveRequest,
    current_user: User,
    db
):
    """三层知识库检索策略"""
    try:
        # 第一层：通用知识库检索
        general_kb_ids = []
        if request.general_kb_id:
            general_kb_ids = [request.general_kb_id]
        else:
            result = await db.execute(
                select(KnowledgeBase)
                .where(KnowledgeBase.category == KnowledgeBaseCategory.GENERAL)
                .where(KnowledgeBase.status == KnowledgeBaseStatus.READY)
            )
            general_kbs = result.scalars().all()
            general_kb_ids = [kb.id for kb in general_kbs]
            logger.info(f"[第一层] 自动检索 {len(general_kb_ids)} 个通用知识库")

        all_general_results = []
        for general_kb_id in general_kb_ids[:3]:
            try:
                result = await dual_track_graph_rag.retrieve_dual_track(
                    query=request.query,
                    general_kb_id=general_kb_id,
                    vertical_kb_id=None,
                    vertical_category=None,
                    n_results=request.n_results
                )
                if result.get("general_results"):
                    all_general_results.append(result["general_results"])
            except Exception as e:
                logger.warning(f"检索通用知识库 {general_kb_id} 失败: {e}")
                continue

        # 第二层：垂直领域知识库检索
        vertical_results = None
        if request.vertical_kb_id and request.vertical_category:
            try:
                logger.info(f"[第二层] 检索垂直领域知识库: {request.vertical_category}")
                result = await dual_track_graph_rag.retrieve_dual_track(
                    query=request.query,
                    general_kb_id=None,
                    vertical_kb_id=request.vertical_kb_id,
                    vertical_category=request.vertical_category.value,
                    n_results=request.n_results
                )
                vertical_results = result.get("vertical_results")
            except Exception as e:
                logger.warning(f"检索垂直知识库失败: {e}")

        # 第三层：官方手册检索
        manual_results = None
        should_query_manual = False
        if all_general_results or vertical_results:
            total_results = len(all_general_results) + \
                (1 if vertical_results else 0)
            if total_results < 2:
                should_query_manual = True

        manual_keywords = ["api", "配置", "使用", "教程", "文档", "说明", "指南", "手册"]
        if any(keyword in request.query.lower() for keyword in manual_keywords):
            should_query_manual = True

        if should_query_manual:
            try:
                logger.info(f"[第三层] 查询官方手册知识库")
                manual_result = await db.execute(
                    select(KnowledgeBase)
                    .where(KnowledgeBase.category == KnowledgeBaseCategory.MANUAL)
                    .where(KnowledgeBase.status == KnowledgeBaseStatus.READY)
                )
                manual_kbs = manual_result.scalars().all()

                if manual_kbs:
                    retrieval_tool = get_knowledge_retrieval_tool()
                    manual_chunks = []
                    for manual_kb in manual_kbs[:2]:
                        try:
                            kb_results = await retrieval_tool.retrieve(
                                collection_name=manual_kb.collection_name,
                                query=request.query,
                                n_results=request.n_results
                            )
                            if kb_results:
                                manual_chunks.extend(kb_results)
                        except Exception as e:
                            logger.warning(f"查询官方手册 {manual_kb.id} 失败: {e}")

                    if manual_chunks:
                        manual_results = {
                            "chunks": manual_chunks[:request.n_results],
                            "kb_count": len(manual_kbs),
                            "source": "manual"
                        }
            except Exception as e:
                logger.warning(f"官方手册检索失败: {e}")

        # 分析理论连接
        connections = []
        if all_general_results and vertical_results:
            connections = dual_track_graph_rag._analyze_connections({
                "general_results": all_general_results[0] if all_general_results else None,
                "vertical_results": vertical_results
            })

        context_data = {
            "general_results": all_general_results[0] if all_general_results else None,
            "vertical_results": vertical_results,
            "connections": connections
        }
        enhanced_context = dual_track_graph_rag._format_dual_track_context(context_data)

        if manual_results:
            manual_context = "\n\n## 官方手册参考：\n"
            for i, chunk in enumerate(manual_results["chunks"][:3], 1):
                manual_context += f"\n{i}. {chunk}\n"
            enhanced_context += manual_context

        return ResponseModel(
            data={
                "query": request.query,
                "general_results": all_general_results[0] if all_general_results else None,
                "vertical_results": vertical_results,
                "manual_results": manual_results,
                "connections": connections,
                "enhanced_context": enhanced_context
            }
        )
    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        raise KnowledgeBaseException(f"检索失败: {str(e)}")
