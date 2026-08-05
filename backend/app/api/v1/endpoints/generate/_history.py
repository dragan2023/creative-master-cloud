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
from app.models import User, Generation, GenerationStatus, UserAction
from app.schemas.generation import (
    UserActionCreate, UserActionResponse, ActionStatsResponse,
    ExperienceEventCreate, ExperienceEventResponse,
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
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        获取用户的生成历史

        Args:
            module: 模块筛选
            status: 状态筛选（completed/processing/failed/cancelled）
            keyword: 标题关键词搜索
            start_date: 创建时间起始（YYYY-MM-DD 或 ISO 时间）
            end_date: 创建时间截止（YYYY-MM-DD 或 ISO 时间）
            limit: 每页数量
            offset: 偏移量

        Returns:
            生成历史列表
        """
        from sqlalchemy import select, desc, func, and_, or_

        # 构建基础查询条件
        base_query = select(Generation).where(
            Generation.user_id == current_user.id
        )

        # [2026-08-04] 过滤旧版遗留的"状态已完成但无正文"记录
        # （此前流式端点会额外创建一条空状态记录，造成历史列表重复）
        base_query = base_query.where(
            or_(
                and_(
                    Generation.output_content.isnot(None),
                    Generation.output_content != "",
                ),
                Generation.status != GenerationStatus.COMPLETED,
            )
        )

        if module:
            base_query = base_query.where(Generation.module == module)

        if status:
            try:
                status_enum = GenerationStatus(status)
                base_query = base_query.where(Generation.status == status_enum)
            except ValueError:
                raise ValidationException(message=f"无效的状态值: {status}")

        if keyword:
            base_query = base_query.where(
                Generation.title.ilike(f"%{keyword}%")
            )

        if start_date or end_date:
            from datetime import datetime

            def _parse_date(value: str, end_of_day: bool):
                try:
                    dt = datetime.fromisoformat(value)
                except ValueError:
                    try:
                        dt = datetime.strptime(value, "%Y-%m-%d")
                    except ValueError:
                        raise ValidationException(
                            message=f"无效的日期格式: {value}，请使用 YYYY-MM-DD 或 ISO 时间")
                if end_of_day:
                    dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                return dt

            if start_date:
                base_query = base_query.where(
                    Generation.created_at >= _parse_date(start_date, end_of_day=False)
                )
            if end_date:
                base_query = base_query.where(
                    Generation.created_at <= _parse_date(end_date, end_of_day=True)
                )

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
                    "preview": (g.output_content or "")[:200],
                    "content_length": len(g.output_content or ""),
                    "provider": g.provider,
                    "model_name": g.model_name,
                    "token_count": g.token_count,
                    "duration_ms": g.duration_ms,
                    "is_finalized": g.is_finalized,
                    "revision_count": g.revision_count or 0,
                    "created_at": g.created_at.isoformat() if g.created_at else None,
                    "updated_at": g.updated_at.isoformat() if g.updated_at else None
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
            "is_finalized": generation.is_finalized,
            "revision_count": generation.revision_count or 0,
            "created_at": generation.created_at.isoformat() if generation.created_at else None,
            "updated_at": generation.updated_at.isoformat() if generation.updated_at else None
        }

    @router.delete("/history/{generation_id}")
    async def delete_generation(
        generation_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """删除生成记录"""
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

        # 使用 ORM 删除，级联清理修订历史（generation_revision_history）
        await db.delete(generation)
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

    # ==================== 体验事件追踪（阶段04新增） ====================

    @router.post("/experience-event", response_model=ExperienceEventResponse)
    async def track_experience_event(
        data: ExperienceEventCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """记录体验事件（creation_started/completed/cancelled 等）
        
        事件数据仅包含：模块、阶段、时长桶、错误类别、是否重试、是否首次使用。
        不包含正文、提示词、API Key 或任何用户内容。
        """
        action_service = UserActionService(db)
        action = await action_service.track_experience_event(
            user_id=current_user.id,
            module=data.module,
            event_type=data.event_type,
            generation_id=data.generation_id,
            phase=data.phase,
            duration_bucket=data.duration_bucket,
            error_category=data.error_category,
            is_retry=data.is_retry,
            is_first_use=data.is_first_use,
        )

        if action is None:
            raise ValidationException(message=f"无效的事件类型: {data.event_type}")

        return ExperienceEventResponse(
            id=action.id,
            user_id=action.user_id,
            event_type=action.action.value,
            module=action.module,
            generation_id=action.generation_id,
            phase=action.phase,
            duration_bucket=action.duration_bucket,
            error_category=action.error_category,
            is_retry=action.is_retry or False,
            is_first_use=action.is_first_use or False,
            created_at=action.created_at.isoformat() if action.created_at else None,
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
