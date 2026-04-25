"""
写作流水线 - 执行方法 Mixin

@date: 2026-04-24
@version: v1.0.0
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.writing_task import WritingTask, TaskStatus
from app.agents.writing.orchestrator_agent import OrchestratorAgent
from app.agents.writing.base_agent import AgentContext
from ._context_builder import ContextBuilderMixin

logger = get_logger("writing_engine.pipeline")


class PipelineExecuteMixin(ContextBuilderMixin):
    """执行方法 Mixin"""

    def __init__(self, *args, db: Optional[AsyncSession] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = db

    async def _get_or_create_db(self) -> AsyncSession:
        """获取数据库会话，优先使用注入的会话，不存在则创建新会话"""
        if hasattr(self, 'db') and self.db is not None:
            return self.db
        from app.core.database import async_session_maker
        return async_session_maker()

    async def start(self) -> None:
        """启动流水线执行（异步，非阻塞）

        创建OrchestratorAgent实例并启动后台执行任务。
        执行结果通过WebSocket推送或存储在任务记录中。

        注意：此方法只负责启动后台任务，数据库会话在_execute中创建和管理
        """
        # 注册到活跃列表（使用task_id）
        type(self)._active_pipelines[self.task_id] = self

        # 如果没有注入WebSocket管理器，尝试获取全局实例
        if not self._ws_manager:
            try:
                from app.services.writing_engine.websocket_manager import get_websocket_manager
                self._ws_manager = get_websocket_manager()
                logger.debug(f"WebSocket管理器已自动获取: task_id={self.task_id}")
            except Exception as e:
                logger.warning(
                    f"获取WebSocket管理器失败: task_id={self.task_id}, error={e}")

        # 启动后台执行任务（数据库会话在_execute中创建）
        self._execution_task = asyncio.create_task(self._execute())

        logger.info(f"写作流水线已启动: task_id={self.task_id}")

    async def _execute(self) -> None:
        """执行写作任务（内部方法）

        在自己的数据库会话中调用OrchestratorAgent.execute，
        处理执行结果和异常，更新任务状态并通过WebSocket推送进度。
        """
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            self.db = db
            try:
                # 加载任务对象
                from sqlalchemy import select
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                self.task = result.scalar_one_or_none()

                if not self.task:
                    logger.error(f"任务不存在: task_id={self.task_id}")
                    return

                # 安全检查：如果 total_units 为 0 或 None，尝试从数据库查询实际单元数并更新
                if not self.task.total_units or self.task.total_units == 0:
                    logger.warning(f"任务 total_units 为 0 或 None，尝试从数据库查询实际单元数")

                    from app.models.novel_project import NovelProject
                    from app.models.novel_chapter import NovelChapter

                    # 获取项目信息
                    project_result = await db.execute(
                        select(NovelProject).where(
                            NovelProject.id == self.task.project_id).limit(1)
                    )
                    project = project_result.scalar_one_or_none()

                    actual_unit_count = 0
                    if project:
                        # 优先从 unit_summaries (JSON字段) 获取
                        if project.unit_summaries and isinstance(project.unit_summaries, dict):
                            actual_unit_count = len(project.unit_summaries)

                        if actual_unit_count == 0:
                            # 从 NovelChapter 表查询章节数
                            chapter_count_result = await db.execute(
                                select(func.count(NovelChapter.id)).where(
                                    NovelChapter.project_id == self.task.project_id
                                )
                            )
                            actual_unit_count = chapter_count_result.scalar() or 0

                        if actual_unit_count == 0:
                            # 兜底：使用项目的 total_chapters 字段
                            actual_unit_count = project.total_chapters or 0

                    # 根据 start_from 和 unit_count 计算实际要生成的单元数
                    start_from = self.task.start_from or 1
                    unit_count = self.task.unit_count
                    available_units = max(
                        0, actual_unit_count - start_from + 1)

                    if unit_count is not None:
                        total_units = min(unit_count, available_units)
                    else:
                        total_units = available_units

                    if total_units > 0:
                        self.task.total_units = total_units
                        await db.commit()
                        logger.info(
                            f"已更新任务 total_units: task_id={self.task_id}, total_units={total_units}")
                    else:
                        logger.error(
                            f"无法获取有效的 total_units: task_id={self.task_id}, project_id={self.task.project_id}")
                        self.task.status = TaskStatus.FAILED
                        self.task.error_message = "项目没有可生成的单元"
                        await db.commit()
                        return

                # 检查任务状态
                if self.task.status == TaskStatus.RUNNING:
                    logger.warning(f"任务已在运行中: task_id={self.task_id}")
                    return

                # 创建OrchestratorAgent
                self._orchestrator = OrchestratorAgent(
                    db=db, config=self.config)

                # 设置统计拦截器
                if self._stats_interceptor:
                    self._orchestrator.set_stats_interceptor(
                        self._stats_interceptor)

                # 设置WebSocket管理器
                if self._ws_manager:
                    self._orchestrator.set_ws_manager(self._ws_manager)

                # 更新任务状态为运行中
                self.task.status = TaskStatus.RUNNING
                self.task.start_time = datetime.now()
                await db.commit()

                # 通知状态变更
                await self._notify_status_change(TaskStatus.PENDING, TaskStatus.RUNNING)

                # 构建执行上下文
                context = await self._build_context()

                # 执行Orchestrator
                self._result = await self._orchestrator.execute(context)

                # 处理执行结果
                if self._result.success:
                    self.task.status = TaskStatus.COMPLETED
                    self.task.end_time = datetime.now()
                    logger.info(f"写作任务完成: task_id={self.task.id}")
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.COMPLETED)
                else:
                    self.task.status = TaskStatus.FAILED
                    self.task.error_message = self._result.errors[0] if self._result.errors else "未知错误"
                    self.task.end_time = datetime.now()
                    logger.error(
                        f"写作任务失败: task_id={self.task.id}, error={self.task.error_message}")
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.FAILED)

                await db.commit()

            except asyncio.CancelledError:
                # 任务被取消（中断）
                if self.task:
                    logger.info(f"写作任务被中断: task_id={self.task.id}")
                    self.task.status = TaskStatus.INTERRUPTED
                    self.task.end_time = datetime.now()
                    await db.commit()
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.INTERRUPTED)
                else:
                    logger.info(f"写作任务被中断: task_id={self.task_id}")

            except Exception as e:
                # 执行异常
                logger.exception(
                    f"写作任务执行异常: task_id={self.task_id}, error={str(e)}")
                if self.task:
                    self.task.status = TaskStatus.FAILED
                    self.task.error_message = str(e)
                    self.task.end_time = datetime.now()
                    await db.commit()
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.FAILED)

            finally:
                # 从活跃列表移除
                type(self).remove_active_pipeline(self.task_id)
                self.db = None




