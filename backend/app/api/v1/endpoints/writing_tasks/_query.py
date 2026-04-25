"""
写作任务 API - 查询与统计端点

@date: 2026-04-24
@version: v3.1.0 (从writing_tasks.py拆分)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import get_db
from app.core.logger import get_logger
from app.api.deps import get_current_user
from app.models import User
from app.models.writing_task import WritingTask
from app.models.writing_unit import WritingUnit
from app.models.writing_scene import WritingScene
from app.schemas.common import ResponseModel
from app.schemas.writing_task import (
    WritingUnitResponse, WritingSceneResponse,
    WritingTaskStatsDetailResponse, AgentStatItem,
)

from ._common import _build_unit_response, _build_scene_response

logger = get_logger("writing_tasks")


def register_query_routes(router: APIRouter):
    """注册查询统计路由"""

    @router.get("/{task_id}/stats", response_model=ResponseModel[WritingTaskStatsDetailResponse])
    async def get_task_stats(
        task_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        获取写作任务统计详情

        包含总token消耗、总费用、按Agent统计等详细信息。
        """
        try:
            # 查询任务
            result = await db.execute(
                select(WritingTask).where(
                    and_(WritingTask.id == task_id,
                         WritingTask.user_id == current_user.id)
                )
            )
            task = result.scalar_one_or_none()

            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="任务不存在"
                )

            # 查询Agent统计
            from app.models.writing_stat import WritingStat
            stats_result = await db.execute(
                select(WritingStat).where(WritingStat.task_id == task_id)
            )
            stats = stats_result.scalars().all()

            # 构建按Agent统计
            by_agent = []
            for stat in stats:
                by_agent.append(AgentStatItem(
                    agent_name=stat.agent_name,
                    model_id=stat.model_id,
                    call_count=stat.call_count,
                    total_input_tokens=stat.total_input_tokens,
                    total_output_tokens=stat.total_output_tokens,
                    total_tokens=stat.total_tokens,
                    total_duration_sec=stat.total_duration_ms /
                    1000.0 if stat.total_duration_ms else 0.0,
                    total_cost=stat.total_cost
                ))

            # 构建响应
            stats_data = WritingTaskStatsDetailResponse(
                task_id=task_id,
                total_tokens=task.total_tokens,
                total_cost=task.total_cost,
                by_agent=by_agent,
                by_scene={}  # TODO: 按场景统计
            )

            return ResponseModel(
                success=True,
                code=200,
                message="获取任务统计成功",
                data=stats_data
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取任务统计失败: task_id={task_id}, error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取任务统计失败: {str(e)}"
            )

    @router.get("/{task_id}/units", response_model=ResponseModel[list[WritingUnitResponse]])
    async def get_task_units(
        task_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        获取写作任务的单元列表
        """
        try:
            # 验证任务存在且属于当前用户
            result = await db.execute(
                select(WritingTask).where(
                    and_(WritingTask.id == task_id,
                         WritingTask.user_id == current_user.id)
                )
            )
            task = result.scalar_one_or_none()

            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="任务不存在"
                )

            # 查询单元列表
            units_result = await db.execute(
                select(WritingUnit).where(WritingUnit.task_id ==
                                          task_id).order_by(WritingUnit.unit_index)
            )
            units = units_result.scalars().all()

            return ResponseModel(
                success=True,
                code=200,
                message="获取单元列表成功",
                data=[_build_unit_response(unit) for unit in units]
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取单元列表失败: task_id={task_id}, error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取单元列表失败: {str(e)}"
            )

    @router.get("/{task_id}/units/{unit_index}/scenes", response_model=ResponseModel[list[WritingSceneResponse]])
    async def get_unit_scenes(
        task_id: int,
        unit_index: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        获取指定单元的场景列表
        """
        try:
            # 验证任务存在且属于当前用户
            task_result = await db.execute(
                select(WritingTask).where(
                    and_(WritingTask.id == task_id,
                         WritingTask.user_id == current_user.id)
                )
            )
            task = task_result.scalar_one_or_none()

            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="任务不存在"
                )

            # 查询单元
            unit_result = await db.execute(
                select(WritingUnit).where(
                    and_(WritingUnit.task_id == task_id,
                         WritingUnit.unit_index == unit_index)
                )
            )
            unit = unit_result.scalar_one_or_none()

            if not unit:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="单元不存在"
                )

            # 查询场景列表
            scenes_result = await db.execute(
                select(WritingScene).where(WritingScene.unit_id ==
                                           unit.id).order_by(WritingScene.scene_index)
            )
            scenes = scenes_result.scalars().all()

            return ResponseModel(
                success=True,
                code=200,
                message="获取场景列表成功",
                data=[_build_scene_response(scene) for scene in scenes]
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"获取场景列表失败: task_id={task_id}, unit_index={unit_index}, error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取场景列表失败: {str(e)}"
            )
