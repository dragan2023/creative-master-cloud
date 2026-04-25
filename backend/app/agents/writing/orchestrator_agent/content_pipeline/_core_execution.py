"""
content_pipeline - 核心执行流程模块

包含 ContentPipelineMixin.execute() 核心方法。

@date: 2026-04-24
@version: v3.0.0
"""
import asyncio
import time
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select

from app.agents.writing.base_agent import AgentContext, AgentResult
from app.models.writing_task import WritingTask, TaskStatus
from app.models.novel_project import NovelProject, ProjectStatus
from app.models.writing_unit import UnitStatus


class CoreExecutionMixin:
    """核心执行流程 Mixin

    提供 execute() 方法 - 驱动完整写作任务执行。
    """

    # 由主类提供的属性（类型提示）
    db: Any
    _interrupt_event: Any
    _semaphore: Optional[Any]
    _current_task: Optional[WritingTask]
    _max_concurrent_writers: int
    _character_tracker: Any
    _project_knowledge_base: Any
    _stats_interceptor: Any
    logger: Any

    # 从 MonitoringMixin 继承的方法
    _check_interrupted: callable
    _send_ws_message: callable
    _initialize_character_tracker: callable
    _save_checkpoint: callable
    _update_character_states: callable

    # 从 AgentCommunicationMixin 继承的方法
    _get_agent: callable

    # 从 TaskSchedulerMixin 继承的方法
    _load_or_create_task: callable
    _build_error_result: callable
    _build_success_result: callable

    # 从子模块继承的方法
    _process_unit_direct: callable

    async def execute(self, context: AgentContext) -> AgentResult:
        """执行完整写作任务

        这是总线Agent的核心方法，驱动整个写作流程：
        1. 加载或创建WritingTask记录
        2. 遍历每个Unit，调用_process_unit
        3. 汇总结果并返回

        Args:
            context: Agent执行上下文，包含task_id、project_id等信息

        Returns:
            AgentResult: 包含最终生成内容和执行统计
        """
        start_time = time.time()
        self.logger.info(f"开始执行写作任务: {context.task_id}")

        try:
            # 1. 加载或创建任务记录
            task = await self._load_or_create_task(context)
            self._current_task = task

            # 2. 初始化并发控制
            self._max_concurrent_writers = context.config.get(
                "max_concurrent_writers", 3)
            self._semaphore = asyncio.Semaphore(self._max_concurrent_writers)

            # 2.5 初始化人物状态追踪器
            await self._initialize_character_tracker(
                project_id=context.project_id,
                character_profiles=context.character_profiles,
                world_settings=context.world_settings,
                persist_dir=context.config.get("persist_dir")
            )

            # 3. 确定要处理的单元范围
            start_unit = context.config.get("start_from", 1)
            unit_count = context.config.get("unit_count")

            # 获取生成模式
            generation_mode = "direct"
            self.logger.info(f"生成模式: {generation_mode} (架构优化版)")

            # 4. 遍历处理每个Unit
            total_units = task.total_units
            completed_units = task.completed_units or 0

            for unit_index in range(start_unit, total_units + 1):
                # 发送任务进度推送
                await self._send_ws_message("task_progress", {
                    "completed_units": completed_units,
                    "total_units": total_units,
                    "current_unit": unit_index,
                    "current_scene": None
                })

                # 检查中断信号
                if self._check_interrupted():
                    self.logger.warning(f"任务被中断于单元 {unit_index}")
                    await self._save_checkpoint(task.id, unit_index - 1, None, "interrupted")
                    task.status = TaskStatus.INTERRUPTED
                    await self.db.commit()
                    return self._build_error_result(
                        f"任务被中断于单元 {unit_index}",
                        completed_units=completed_units,
                        total_units=total_units
                    )

                # 架构优化：固定使用 direct 模式
                chapter_detailed_outline = None

                # 发送模式决策日志
                await self._send_ws_message("mode_decision", {
                    "unit_index": unit_index,
                    "has_detailed_outline": False,
                    "selected_mode": "direct",
                    "reason": "架构优化：基于全局大纲+单元概述的直接生成模式"
                })

                # 处理单个单元 - 直接生成模式
                self.logger.info(f"处理单元 {unit_index}/{total_units} (direct模式)")
                unit_result = await self._process_unit_direct(
                    context, unit_index, chapter_detailed_outline
                )

                if unit_result.success:
                    completed_units += 1
                    task.completed_units = completed_units
                    await self.db.commit()

                    await self._send_ws_message("task_progress", {
                        "completed_units": completed_units,
                        "total_units": total_units,
                        "current_unit": unit_index,
                        "current_scene": None
                    })
                else:
                    self.logger.error(
                        f"单元 {unit_index} 处理失败: {unit_result.errors}")
                    if context.config.get("stop_on_error", True):
                        task.status = TaskStatus.FAILED
                        task.error_message = f"单元 {unit_index} 失败: {unit_result.errors[0] if unit_result.errors else '未知错误'}"
                        await self.db.commit()
                        return self._build_error_result(
                            task.error_message,
                            completed_units=completed_units,
                            total_units=total_units
                        )

            # 5. 任务完成
            if self._stats_interceptor:
                stats = self._stats_interceptor.get_summary()
                task.total_tokens = stats["total_tokens"]
                task.total_cost = stats["total_cost"]
            task.status = TaskStatus.COMPLETED
            task.end_time = datetime.now()
            await self.db.commit()

            # 更新项目状态
            try:
                project_result = await self.db.execute(
                    select(NovelProject).where(
                        NovelProject.id == context.project_id)
                )
                project = project_result.scalar_one_or_none()
                if project:
                    project.status = ProjectStatus.COMPLETED
                    project.completed_chapters = completed_units
                    project.current_chapter = total_units
                    await self.db.commit()
                    self.logger.info(
                        f"项目状态已更新: project_id={context.project_id}, status=completed, completed_chapters={completed_units}")
            except Exception as e:
                self.logger.warning(f"更新项目状态失败: {e}")

            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.info(
                f"写作任务完成: {completed_units}/{total_units} 单元, 耗时 {duration_ms}ms")

            return self._build_success_result(
                content=f"任务完成，共生成 {completed_units} 个单元",
                duration_ms=duration_ms,
                completed_units=completed_units,
                total_units=total_units,
                task_id=context.task_id
            )

        except Exception as e:
            self.logger.exception(f"执行任务时发生异常: {str(e)}")
            if self._current_task:
                self._current_task.status = TaskStatus.FAILED
                self._current_task.error_message = str(e)
                await self.db.commit()
            return self._build_error_result(f"执行异常: {str(e)}")
