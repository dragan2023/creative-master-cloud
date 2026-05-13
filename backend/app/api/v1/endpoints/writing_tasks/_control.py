"""
写作任务 API - 任务控制端点（中断/续传/继续生成）

@date: 2026-04-24
@version: v3.1.0 (从writing_tasks.py拆分)
"""
import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.core.database import get_db
from app.core.logger import get_logger
from app.api.deps import get_current_user
from app.models import User
from app.models.writing_task import WritingTask, TaskStatus
from app.models.writing_unit import WritingUnit
from app.schemas.common import ResponseModel
from app.schemas.writing_task import WritingTaskResponse, WritingTaskContinue
from app.services.writing_engine.pipeline import WritingPipeline

from ._common import _build_task_response
from ._pipeline import _resume_pipeline, _continue_pipeline

logger = get_logger("writing_tasks")


def register_control_routes(router: APIRouter):
    """注册任务控制路由"""

    @router.post("/{task_id}/interrupt", response_model=ResponseModel[WritingTaskResponse])
    async def interrupt_task(
        task_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        中断写作任务

        向正在运行的任务发送中断信号，Pipeline会在下一个检查点停止。
        状态更新由Orchestrator在检测到中断后自动完成。
        可通过 `/resume` 端点续传。
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

            # 检查任务状态
            current_status = task.status.value if isinstance(
                task.status, TaskStatus) else task.status
            if current_status not in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"任务当前状态为 {current_status}，无法中断"
                )

            # 获取活跃的Pipeline实例并发送中断信号
            pipeline = WritingPipeline.get_active_pipeline(task_id)
            interrupt_sent = False

            if pipeline:
                try:
                    await pipeline.interrupt()
                    interrupt_sent = True
                    logger.info(f"已向Pipeline发送中断信号: task_id={task_id}")
                except Exception as e:
                    logger.warning(
                        f"向Pipeline发送中断信号失败: task_id={task_id}, error={e}")

            # 如果没有活跃的Pipeline，直接更新状态
            if not interrupt_sent:
                logger.info(f"没有活跃的Pipeline，直接更新任务状态: task_id={task_id}")
                task.status = TaskStatus.INTERRUPTED
                task.end_time = datetime.now()
                await db.commit()
                await db.refresh(task)
            else:
                # 等待一小段时间让Pipeline处理中断，然后刷新任务状态
                import asyncio
                await asyncio.sleep(0.5)  # 给Pipeline一些时间处理中断
                await db.refresh(task)

            logger.info(f"中断写作任务: task_id={task_id}, 最终状态={task.status}")

            return ResponseModel(
                success=True,
                code=200,
                message="中断信号已发送" if interrupt_sent else "任务已中断",
                data=_build_task_response(task)
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"中断任务失败: task_id={task_id}, error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"中断任务失败: {str(e)}"
            )

    @router.post("/{task_id}/resume", response_model=ResponseModel[WritingTaskResponse])
    async def resume_task(
        task_id: int,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        续传写作任务

        从中断点继续执行写作Pipeline。只有状态为 interrupted 的任务可以续传。
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

            # 检查任务状态
            current_status = task.status.value if isinstance(
                task.status, TaskStatus) else task.status
            resumable_statuses = (TaskStatus.INTERRUPTED.value, TaskStatus.FAILED.value)
            if current_status not in resumable_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"任务当前状态为 {current_status}，无法续传。只有已中断或失败的任务才能续传。"
                )

            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.end_time = None
            task.error_message = None
            await db.commit()
            await db.refresh(task)

            # 启动续传Pipeline
            asyncio.create_task(
                _resume_pipeline(task_id=task_id)
            )

            logger.info(f"续传写作任务: task_id={task_id}")

            return ResponseModel(
                success=True,
                code=200,
                message="任务已续传",
                data=_build_task_response(task)
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"续传任务失败: task_id={task_id}, error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"续传任务失败: {str(e)}"
            )

    @router.post("/{task_id}/continue", response_model=ResponseModel[WritingTaskResponse])
    async def continue_task(
        task_id: int,
        request: WritingTaskContinue,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        继续生成写作任务

        任务完成后继续生成更多单元。从当前已完成单元的下一单元开始。

        参数:
        - unit_count: 要继续生成的单元数量（必需）

        注意：只有已完成的任务才能继续生成。
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

            # 检查任务状态 - 只有completed状态可以继续生成
            current_status = task.status.value if isinstance(
                task.status, TaskStatus) else task.status
            if current_status != TaskStatus.COMPLETED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"任务当前状态为 {current_status}，无法继续生成。只有已完成的任务才能继续生成。"
                )

            # 获取项目信息
            from app.models.novel_project import NovelProject
            project_result = await db.execute(
                select(NovelProject).where(NovelProject.id == task.project_id)
            )
            project = project_result.scalar_one_or_none()
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="项目不存在"
                )

            # 计算新的起始位置
            start_from = task.completed_units + 1
            unit_count = request.unit_count

            # 计算项目的实际单元数
            actual_unit_count = 0
            if project.unit_summaries and isinstance(project.unit_summaries, dict):
                actual_unit_count = len(project.unit_summaries)
            if actual_unit_count == 0:
                from app.models.novel_chapter import NovelChapter
                chapter_count_result = await db.execute(
                    select(func.count(NovelChapter.id)).where(
                        NovelChapter.project_id == task.project_id
                    )
                )
                actual_unit_count = chapter_count_result.scalar() or 0

            # 验证是否还有单元可生成
            if actual_unit_count > 0 and start_from > actual_unit_count:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"已到达项目最后单元（{actual_unit_count}），无法继续生成"
                )

            # 计算实际可生成的单元数
            if actual_unit_count > 0:
                available_units = actual_unit_count - start_from + 1
                if unit_count > available_units:
                    unit_count = available_units

            if unit_count <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="没有可生成的单元"
                )

            logger.info(
                f"继续生成任务: task_id={task_id}, start_from={start_from}, unit_count={unit_count}")

            # 更新任务配置和状态
            task_config = task.config or {}
            task_config["continue_from"] = start_from
            task_config["continue_unit_count"] = unit_count
            task.config = task_config

            # 更新任务参数
            task.total_units = task.total_units + unit_count
            task.status = TaskStatus.PENDING  # 重置为pending，让Pipeline启动
            task.end_time = None
            task.error_message = None

            # 预创建WritingUnit记录
            from app.models.writing_unit import WritingUnit, UnitStatus
            if project.unit_summaries and isinstance(project.unit_summaries, dict):
                unit_summaries = project.unit_summaries
                for i in range(start_from, start_from + unit_count):
                    unit_key = str(i)
                    unit_summary_data = unit_summaries.get(unit_key, {})

                    # 检查是否已存在该单元
                    existing_unit = await db.execute(
                        select(WritingUnit).where(
                            and_(WritingUnit.task_id == task_id,
                                 WritingUnit.unit_index == i)
                        )
                    )
                    if existing_unit.scalar_one_or_none():
                        continue  # 跳过已存在的单元

                    unit = WritingUnit(
                        task_id=task.id,
                        unit_index=i,
                        unit_title=unit_summary_data.get("title") if isinstance(
                            unit_summary_data, dict) else None,
                        unit_summary=unit_summary_data.get("summary") if isinstance(
                            unit_summary_data, dict) else str(unit_summary_data),
                        status=UnitStatus.PENDING,
                        scenes_data=[]
                    )
                    db.add(unit)

            await db.commit()
            await db.refresh(task)

            # 启动Pipeline
            asyncio.create_task(
                _continue_pipeline(
                    task_id=task.id,
                    start_from=start_from,
                    unit_count=unit_count
                )
            )

            logger.info(f"继续生成任务已启动: task_id={task_id}")

            return ResponseModel(
                success=True,
                code=200,
                message=f"已从第{start_from}单元继续生成{unit_count}个单元",
                data=_build_task_response(task)
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"继续生成任务失败: task_id={task_id}, error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"继续生成任务失败: {str(e)}"
            )

    @router.post("/{task_id}/reset_stale_status", response_model=ResponseModel[WritingTaskResponse])
    async def reset_stale_task_status(
        task_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        重置幽灵状态任务
        
        当任务卡在RUNNING状态但实际上已停止运行时（如进程崩溃、网络中断），
        使用此接口手动将状态重置为INTERRUPTED，然后可以调用 /resume 续传。
        """
        from datetime import timedelta
        from sqlalchemy import update
        
        STALE_THRESHOLD = timedelta(minutes=30)
        
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
            
            # 只允许重置RUNNING状态的任务
            if task.status != TaskStatus.RUNNING:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"任务当前状态为 {task.status.value}，只能重置RUNNING状态的任务"
                )
            
            # 检查是否确实是幽灵状态（超过阈值）
            last_update = task.updated_at or task.start_time
            if last_update:
                time_elapsed = datetime.now() - last_update
                if time_elapsed < STALE_THRESHOLD:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"任务仍在活跃运行中（上次更新: {time_elapsed.seconds//60}分钟前），请稍后再试或使用中断接口"
                    )
            
            # 更新状态为INTERRUPTED
            await db.execute(
                update(WritingTask)
                .where(WritingTask.id == task_id)
                .values(status=TaskStatus.INTERRUPTED, end_time=datetime.now())
            )
            await db.commit()
            
            await db.refresh(task)
            logger.info(f"已重置幽灵状态任务: task_id={task_id}, 新状态={task.status}")
            
            return ResponseModel(
                success=True,
                code=200,
                message="已将任务状态从RUNNING重置为INTERRUPTED，可以调用 /resume 续传",
                data=_build_task_response(task)
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"重置任务状态失败: task_id={task_id}, error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"重置任务状态失败: {str(e)}"
            )
