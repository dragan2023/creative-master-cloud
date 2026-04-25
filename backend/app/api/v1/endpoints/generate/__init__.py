"""
创意生成 API 端点包

提供短视频脚本、剧本大纲、小说大纲、平面广告、TVC广告脚本的生成功能
支持流式和非流式生成
支持多模态文件上传

从原始 generate.py (2984行) 拆分为以下模块：
- _common.py: 公共常量、工具函数、流式端点工厂
- _upload.py: 文件上传端点
- _streaming.py: 各模块流式/非流式生成端点
- _history.py: 生成历史、行为追踪、提示词优化
- _outline.py: 两阶段大纲生成API
- _revision.py: 原创IP计划生成、修订相关API

@date: 2026-04-24
@version: v3.1.0 (从generate.py拆分)
"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.core.exceptions import (
    ValidationException,
    GenerationException,
)
from app.core.logger import get_logger
from app.core.redis_client import redis_manager
from app.models import User
from app.schemas.generation import SessionCreateResponse
from app.schemas.common import ResponseModel
from app.utils.generation_state_manager import GenerationStateManager

from ._common import CANCEL_KEY_PREFIX, CANCEL_EXPIRE_SECONDS, parse_kb_ids, is_cancelled
from ._upload import register_upload_routes
from ._streaming import register_streaming_routes
from ._history import register_history_routes
from ._outline import register_outline_routes
from ._revision import register_original_ip_routes, register_revision_routes

logger = get_logger(__name__)

# 创建主路由器
router = APIRouter(prefix="/generate", tags=["创意生成"])

# 注册各子模块路由
register_upload_routes(router)
register_streaming_routes(router)
register_history_routes(router)
register_outline_routes(router)
register_original_ip_routes(router)
register_revision_routes(router)


# ==================== 通用端点（直接定义在__init__.py中）====================

@router.get("/latest/{module}")
async def get_latest_generation(
    module: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户最近的生成记录(通用API,适用于所有模块)

    用于在前端页面加载时恢复上次的生成状态。
    """
    try:
        state = await GenerationStateManager.get_latest_generation(
            db, current_user.id, module, days=7
        )

        return ResponseModel(success=True, data=state)

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"获取最近生成记录失败: {str(e)}")
        raise GenerationException(f"获取失败: {str(e)}")


@router.get("/{generation_id}/restore")
async def restore_generation(
    generation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    恢复指定的生成记录

    返回完整的生成状态,包括修订历史等。
    """
    from app.models.generation import Generation
    from sqlalchemy import select

    try:
        stmt = select(Generation).where(
            Generation.id == generation_id,
            Generation.user_id == current_user.id
        )

        result = await db.execute(stmt)
        generation = result.scalar_one_or_none()

        if not generation:
            raise ValidationException("生成记录不存在")

        return ResponseModel(
            success=True,
            data={
                "id": generation.id,
                "title": generation.title,
                "module": generation.module.value,
                "status": generation.status.value,
                "outline_stage": generation.outline_stage,
                "global_outline_content": generation.global_outline_content,
                "unit_summaries_content": generation.unit_summaries_content,
                "revision_messages": generation.revision_messages,
                "revision_count": generation.revision_count,
                "is_finalized": generation.is_finalized,
                "output_content": generation.output_content,
                "created_at": generation.created_at.isoformat(),
                "updated_at": generation.updated_at.isoformat(),
                "input_params": generation.input_params
            }
        )

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"恢复生成记录失败: {str(e)}")
        raise GenerationException(f"恢复失败: {str(e)}")


@router.post("/cancel/{session_id}")
async def cancel_generation(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    取消生成任务
    使用 Redis 存储取消状态，支持多 worker 环境
    同时设置内存中的 Event 实现立即中断
    """
    from ._common import cancel_tokens

    cancel_key = f"{CANCEL_KEY_PREFIX}{session_id}"

    try:
        # 1. 设置 Redis 取消标记（支持多 worker 环境）
        await redis_manager.set(cancel_key, "1", expire=CANCEL_EXPIRE_SECONDS)

        # 2. 设置内存中的 Event（实现立即中断）
        if session_id in cancel_tokens:
            cancel_tokens[session_id].set()
            logger.info(f"已设置内存取消事件: {session_id}")

        logger.info(
            f"用户 {current_user.id} 请求取消生成任务: {session_id}, Redis key: {cancel_key}")
        return ResponseModel(success=True, message="取消请求已发送")
    except Exception as e:
        logger.error(f"设置取消标记失败: {e}")
        return ResponseModel(success=False, message=f"取消请求失败: {str(e)}")


# ==================== 会话管理 ====================

@router.post("/session", response_model=SessionCreateResponse)
async def create_session(
    module: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新的生成会话

    Args:
        module: 生成模块名称

    Returns:
        会话ID
    """
    from app.agents.orchestrator import get_agent_orchestrator

    orchestrator = get_agent_orchestrator()
    user_id = current_user.id if current_user else 0
    session_id = await orchestrator.create_session(user_id, module)
    return SessionCreateResponse(session_id=session_id)


@router.get("/session/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = 20,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    获取会话历史消息

    Args:
        session_id: 会话ID
        limit: 最大消息数

    Returns:
        消息列表
    """
    from app.agents.orchestrator import get_agent_orchestrator

    orchestrator = get_agent_orchestrator()
    messages = await orchestrator.get_session_messages(session_id, limit)
    return {"messages": messages}
