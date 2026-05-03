"""知识库处理进度与状态管理

包含 get_processing_progress, get_all_processing_progress_endpoint, stop_knowledge_processing
"""

from sqlalchemy import select
from fastapi import Depends

from app.core.logger import get_logger
from app.core.exceptions import ResourceNotFoundException, ValidationException, AuthorizationException
from app.models import KnowledgeBase, KnowledgeBaseStatus, UserRole, User
from app.schemas.common import ResponseModel

from ._state import _async_get_kb_progress, _async_get_all_kb_progress, stop_kb_processing

logger = get_logger(__name__)


async def get_processing_progress_handler(
    kb_id: int,
    current_user: User
):
    """获取知识库处理进度"""
    progress = await _async_get_kb_progress(kb_id)
    return ResponseModel(data=progress)


async def get_all_processing_progress_endpoint_handler(
    current_user: User,
    db
):
    """获取所有正在处理的知识库进度"""
    from app.models import UserRole

    all_progress = await _async_get_all_kb_progress()

    if current_user.role != UserRole.ADMIN:
        result = await db.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.user_id == current_user.id)
        )
        user_kb_ids = {row[0] for row in result.all()}
        all_progress = [p for p in all_progress if p.get(
            "kb_id") in user_kb_ids]

    return ResponseModel(data=all_progress)


async def stop_knowledge_processing_handler(
    kb_id: int,
    current_user: User,
    db
):
    """终止知识库处理进程"""
    from app.models import UserRole

    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    if current_user.role != UserRole.ADMIN and kb.user_id != current_user.id:
        raise AuthorizationException("无权终止此知识库的处理")

    if kb.status != KnowledgeBaseStatus.PROCESSING:
        raise ValidationException("知识库未在处理中")

    success = stop_kb_processing(kb_id)

    if success:
        kb.status = KnowledgeBaseStatus.FAILED
        await db.commit()
        return ResponseModel(message="处理已终止")
    else:
        return ResponseModel(code=400, message="无法终止处理，任务可能已完成或不存在")
