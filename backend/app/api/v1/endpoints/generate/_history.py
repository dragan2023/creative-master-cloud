"""
创意生成 API - 生成历史、用户行为追踪、提示词优化

@date: 2026-04-24
@version: v3.1.0 (从generate.py拆分)
"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    GenerationException,
)
from app.core.logger import get_logger
from app.models import User, Generation, UserAction
from app.schemas.generation import (
    UserActionCreate, UserActionResponse, ActionStatsResponse,
    OptimizeRequest, OptimizeResponse,
)
from app.schemas.common import ResponseModel
from app.services.user_action_service import UserActionService

logger = get_logger(__name__)


def register_history_routes(router: APIRouter):
    """注册生成历史、行为追踪、提示词优化路由"""

    # ==================== 生成历史 ====================

    @router.get("/history")
    async def get_generation_history(
        module: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        获取用户的生成历史

        Args:
            module: 模块筛选
            limit: 每页数量
            offset: 偏移量

        Returns:
            生成历史列表
        """
        from sqlalchemy import select, desc, func

        # 构建基础查询条件
        base_query = select(Generation).where(
            Generation.user_id == current_user.id
        )

        if module:
            base_query = base_query.where(Generation.module == module)

        # 获取总数
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 获取分页数据
        query = base_query.order_by(desc(Generation.created_at))
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        generations = result.scalars().all()

        return ResponseModel(data={
            "items": [
                {
                    "id": g.id,
                    "module": g.module,
                    "status": g.status,
                    "title": g.title,
                    "input_params": g.input_params,
                    "output_content": g.output_content,
                    "provider": g.provider,
                    "model_name": g.model_name,
                    "token_count": g.token_count,
                    "duration_ms": g.duration_ms,
                    "created_at": g.created_at.isoformat() if g.created_at else None
                }
                for g in generations
            ],
            "total": total
        })

    @router.get("/history/{generation_id}")
    async def get_generation_detail(
        generation_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """获取生成记录详情"""
        from sqlalchemy import select

        result = await db.execute(
            select(Generation).where(
                Generation.id == generation_id,
                Generation.user_id == current_user.id
            )
        )
        generation = result.scalar_one_or_none()

        if not generation:
            raise ResourceNotFoundException("生成记录不存在")

        return {
            "id": generation.id,
            "module": generation.module,
            "status": generation.status,
            "title": generation.title,
            "input_params": generation.input_params,
            "output_content": generation.output_content,
            "provider": generation.provider,
            "model_name": generation.model_name,
            "token_count": generation.token_count,
            "duration_ms": generation.duration_ms,
            "created_at": generation.created_at.isoformat() if generation.created_at else None
        }

    @router.delete("/history/{generation_id}")
    async def delete_generation(
        generation_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """删除生成记录"""
        from sqlalchemy import select, delete

        result = await db.execute(
            select(Generation).where(
                Generation.id == generation_id,
                Generation.user_id == current_user.id
            )
        )
        generation = result.scalar_one_or_none()

        if not generation:
            raise ResourceNotFoundException("生成记录不存在")

        await db.execute(
            delete(Generation).where(Generation.id == generation_id)
        )
        await db.commit()

        logger.info(f"用户 {current_user.id} 删除了生成记录 {generation_id}")

        return ResponseModel(success=True, message="删除成功")

    # ==================== 用户行为追踪 ====================

    @router.post("/action", response_model=UserActionResponse)
    async def track_user_action(
        data: UserActionCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """记录用户行为（复制、下载、重新生成等）"""
        action_service = UserActionService(db)
        action = await action_service.track_action(
            user_id=current_user.id,
            generation_id=data.generation_id,
            module=data.module,
            action=data.action,
            content_snippet=data.content_snippet
        )

        return UserActionResponse(
            id=action.id,
            user_id=action.user_id,
            generation_id=action.generation_id,
            module=action.module,
            action=action.action,
            content_snippet=action.content_snippet,
            created_at=action.created_at.isoformat() if action.created_at else None
        )

    @router.get("/action/stats")
    async def get_action_stats(
        module: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """获取用户行为统计"""
        from sqlalchemy import select, func

        query = select(UserAction).where(UserAction.user_id == current_user.id)

        if module:
            query = query.where(UserAction.module == module)

        result = await db.execute(query)
        actions = result.scalars().all()

        # 统计各类行为
        copy_count = sum(1 for a in actions if a.action == "copy")
        download_count = sum(1 for a in actions if a.action == "download")
        regenerate_count = sum(1 for a in actions if a.action == "regenerate")
        total = len(actions)

        # 获取总生成数
        gen_query = select(func.count(Generation.id)).where(
            Generation.user_id == current_user.id
        )
        if module:
            gen_query = gen_query.where(Generation.module == module)

        gen_result = await db.execute(gen_query)
        total_generations = gen_result.scalar() or 1  # 避免除以0

        return ActionStatsResponse(
            total_actions=total,
            copy_count=copy_count,
            download_count=download_count,
            regenerate_count=regenerate_count,
            copy_rate=round(copy_count / total_generations, 2),
            download_rate=round(download_count / total_generations, 2)
        )

    # ==================== 提示词优化 ====================

    @router.post("/optimize")
    async def optimize_prompt(
        data: OptimizeRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        提示词优化

        将用户笼统的创意描述优化为结构化的提示词，帮助AI更好地理解用户意图。

        支持的模块：
        - short_video: 短视频脚本
        - script: 剧本大纲
        - novel: 小说大纲
        - print_ad: 平面广告
        - tvc: TVC广告
        - original_ip: 原创IP计划
        """
        from app.agents.prompt_optimizer import get_prompt_optimizer

        try:
            optimizer = get_prompt_optimizer()
            result = await optimizer.optimize(
                db=db,
                user_id=current_user.id,
                module=data.module,
                original_text=data.original_text
            )

            logger.info(
                f"用户 {current_user.id} 优化提示词成功 - "
                f"模块: {data.module}, "
                f"原文长度: {result['original_length']}, "
                f"优化后长度: {result['optimized_length']}"
            )

            return ResponseModel(
                success=True,
                data=result
            )

        except ValueError as e:
            logger.warning(f"优化参数错误: {str(e)}")
            raise ValidationException(str(e))
        except Exception as e:
            logger.error(f"优化失败: {str(e)}")
            raise GenerationException(f"优化失败: {str(e)}")

    @router.get("/optimize/modules")
    async def get_optimize_modules():
        """获取支持的优化模块列表"""
        from app.agents.prompt_optimizer import get_prompt_optimizer

        optimizer = get_prompt_optimizer()
        modules = optimizer.get_supported_modules()

        return ResponseModel(
            success=True,
            data={
                "modules": [
                    {"id": k, "name": v}
                    for k, v in modules.items()
                ]
            }
        )
