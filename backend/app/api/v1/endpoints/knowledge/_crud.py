"""知识库CRUD操作

包含 list_knowledge_bases, get_knowledge_base, delete_knowledge_base, update_knowledge_base
"""

import os

from sqlalchemy import select
from fastapi import Depends

from app.core.logger import get_logger
from app.core.exceptions import ResourceNotFoundException
from app.models import KnowledgeBase, KnowledgeBaseCategory, KnowledgeBaseStatus, User
from app.schemas.knowledge import KnowledgeBaseResponse, KnowledgeBaseUpdate
from app.schemas.common import ResponseModel

logger = get_logger(__name__)


async def list_knowledge_bases_handler(
    category: str,
    current_user: User,
    db
):
    """获取用户的知识库列表"""
    query = select(KnowledgeBase).where(
        KnowledgeBase.user_id == current_user.id)

    if category and category != "all":
        try:
            cat_enum = KnowledgeBaseCategory(category)
            query = query.where(KnowledgeBase.category == cat_enum)
        except ValueError:
            pass

    query = query.order_by(KnowledgeBase.created_at.desc())
    result = await db.execute(query)
    kbs = result.scalars().all()

    data = [
        KnowledgeBaseResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            type=kb.type,
            category=kb.category,
            status=kb.status,
            file_type=kb.file_type,
            file_size=kb.file_size,
            document_count=kb.document_count,
            preprocessor_metadata=kb.preprocessor_metadata,
            created_at=kb.created_at.isoformat()
        )
        for kb in kbs
    ]
    return ResponseModel(data=data)


async def get_knowledge_base_handler(
    kb_id: int,
    current_user: User,
    db
):
    """获取知识库详情"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    return ResponseModel(data=KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        type=kb.type,
        category=kb.category,
        status=kb.status,
        file_type=kb.file_type,
        file_size=kb.file_size,
        document_count=kb.document_count,
        preprocessor_metadata=kb.preprocessor_metadata,
        created_at=kb.created_at.isoformat()
    ))


async def delete_knowledge_base_handler(
    kb_id: int,
    current_user: User,
    db
):
    """删除知识库"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    from app.core.vector_store import vector_store
    try:
        vector_store.delete_collection(kb.collection_name)
    except Exception as e:
        logger.warning(f"删除向量集合失败 {kb.collection_name}: {e}")

    if kb.file_path and os.path.exists(kb.file_path):
        os.remove(kb.file_path)

    await db.delete(kb)
    await db.commit()

    return ResponseModel(message="删除成功")


async def update_knowledge_base_handler(
    kb_id: int,
    update_data: KnowledgeBaseUpdate,
    current_user: User,
    db
):
    """更新知识库信息"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    if update_data.name is not None:
        kb.name = update_data.name
    if update_data.description is not None:
        kb.description = update_data.description
    if update_data.category is not None:
        kb.category = update_data.category

    await db.commit()
    await db.refresh(kb)

    return ResponseModel(data=KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        type=kb.type,
        category=kb.category,
        status=kb.status,
        file_type=kb.file_type,
        file_size=kb.file_size,
        document_count=kb.document_count,
        created_at=kb.created_at.isoformat()
    ))
