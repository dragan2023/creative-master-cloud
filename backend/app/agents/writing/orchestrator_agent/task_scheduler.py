"""
多Agent协作文学作品生成系统 - 任务调度和并发管理模块

模块: agents.writing.orchestrator_agent
文件: task_scheduler.py
功能: 任务续传、调度控制、任务数据库操作

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import asyncio
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, func

from app.agents.writing.base_agent import AgentContext, AgentResult, AgentRole
from app.models.writing_task import WritingTask, TaskStatus
from app.models.writing_unit import WritingUnit, UnitStatus
from app.models.novel_project import NovelProject, ProjectStatus


class TaskSchedulerMixin:
    """任务调度和并发管理 Mixin
    
    提供：
    - 任务续传 (resume)
    - 继续生成 (continue_from)
    - 续传起点检测
    - 任务数据库操作
    """
    
    # 这些属性由主类提供，类型提示
    db: Any  # AsyncSession
    _interrupt_event: Any  # asyncio.Event
    _semaphore: Optional[asyncio.Semaphore]
    _current_task: Optional[WritingTask]
    _max_concurrent_writers: int
    _character_tracker: Any
    _stats_interceptor: Any
    logger: Any
    
    # 从 MonitoringMixin 继承的方法
    _check_interrupted: callable
    _send_ws_message: callable
    _initialize_character_tracker: callable
    _build_error_result: callable
    _build_success_result: callable
    
    # 从 ContentPipelineMixin 继承的方法
    _process_unit_direct: callable
    
    async def resume(self, context: AgentContext) -> AgentResult:
        """从检查点续传任务
            
        Args:
            context: Agent执行上下文
                
        Returns:
            AgentResult: 执行结果
        """
        self.logger.info(f"尝试续传任务: {context.task_id}")
        self._interrupt_event.set()  # 清除中断状态

        # 加载任务
        task = await self._load_task(context.task_id)
        if not task:
            return self._build_error_result(f"任务不存在: {context.task_id}")

        # 多重检测机制确定续传起点
        start_unit = await self._determine_resume_start(task)

        if start_unit > task.total_units:
            self.logger.info(f"所有单元已完成，无需续传: start_unit={start_unit}, total={task.total_units}")
            return self._build_success_result(
                content="",
                duration_ms=0,
                unit_index=start_unit - 1,
                scene_count=0
            )

        self.logger.info(f"续传任务从单元 {start_unit} 开始")

        # 更新任务状态
        task.status = TaskStatus.RUNNING
        await self.db.commit()

        # 从确定的位置继续执行
        return await self._execute_from_unit(context, task, start_unit)

    async def continue_from(self, context: AgentContext, start_from: int, unit_count: int) -> AgentResult:
        """从指定位置继续生成新单元

        与resume不同，continue_from是在任务完成后追加新单元。

        Args:
            context: Agent执行上下文
            start_from: 起始单元索引
            unit_count: 要生成的单元数

        Returns:
            AgentResult: 执行结果
        """
        self.logger.info(f"继续生成任务: task_id={context.task_id}, start_from={start_from}, unit_count={unit_count}")
        self._interrupt_event.set()  # 清除中断状态

        # 加载任务
        task = await self._load_task(context.task_id)
        if not task:
            return self._build_error_result(f"任务不存在: {context.task_id}")

        self._current_task = task

        # 🔴 防御：安全提取 config（defense-in-depth，__post_init__ 已标准化但保留二次守卫）
        _cfg = context.config if isinstance(context.config, dict) else {}

        # 初始化并发控制
        self._max_concurrent_writers = _cfg.get("max_concurrent_writers", 3)
        self._semaphore = asyncio.Semaphore(self._max_concurrent_writers)

        # 初始化人物状态追踪器（根据叙事模式差异化初始化）
        _narrative_mode = _cfg.get("narrative_mode", "serialized")
        _is_pure_episodic = _narrative_mode == "episodic"
        _is_episodic_with_arc = _narrative_mode == "episodic_with_arc"
        _skip_previous_accumulation = _is_pure_episodic or _is_episodic_with_arc

        await self._initialize_character_tracker(
            project_id=context.project_id,
            character_profiles=context.character_profiles,
            world_settings=context.world_settings,
            persist_dir=_cfg.get("persist_dir"),
            narrative_mode=_narrative_mode
        )

        # [修复] 继续生成时：从 DB 加载上一单元的结尾内容
        # 确保后续单元的 previous_content 不为空
        # 单元剧模式跳过：每集独立故事，不应加载上集内容
        if start_from > 1 and not context.previous_content and not _skip_previous_accumulation:
            try:
                from app.models.writing_unit import WritingUnit as _WritingUnit
                prev_unit_query = select(_WritingUnit).where(
                    _WritingUnit.task_id == task.id,
                    _WritingUnit.unit_index == start_from - 1
                )
                prev_result = await self.db.execute(prev_unit_query)
                prev_unit = prev_result.scalar_one_or_none()
                if prev_unit and prev_unit.final_content:
                    prev_content = prev_unit.final_content
                    if len(prev_content) > 3000:
                        prev_content = prev_content[-3000:]
                    context.previous_content = prev_content
                    self.logger.info(
                        f"[上下文初始化] 从单元 {start_from - 1} 加载前文结尾，"
                        f"长度: {len(context.previous_content)} 字符"
                    )
            except Exception as init_error:
                self.logger.warning(
                    f"[上下文初始化] 加载前文内容失败: {init_error}"
                )

        # 计算结束单元
        end_unit = start_from + unit_count - 1

        # [防护] 硬性边界校验：end_unit 不得超过单元概述的实际数量
        unit_summaries = _cfg.get("unit_summaries", {})
        if unit_summaries and isinstance(unit_summaries, dict) and len(unit_summaries) > 0:
            max_unit_in_summaries = max(int(k) for k in unit_summaries.keys() if str(k).isdigit())
            if end_unit > max_unit_in_summaries:
                original_end = end_unit
                end_unit = max_unit_in_summaries
                unit_count = end_unit - start_from + 1
                task.total_units = task.completed_units + unit_count
                self.logger.warning(
                    f"[continue_from] 硬性边界保护: end_unit 从 {original_end} 截断为 "
                    f"{end_unit}（单元概述最大编号={max_unit_in_summaries}）")

        # 更新任务状态
        task.status = TaskStatus.RUNNING
        await self.db.commit()

        # 发送状态变更通知
        await self._send_ws_message("status_change", {
            "old_status": "completed",
            "new_status": "running",
            "message": f"继续生成 {unit_count} 个单元"
        })

        completed_in_this_run = 0

        for unit_index in range(start_from, end_unit + 1):
            # 发送任务进度推送
            await self._send_ws_message("task_progress", {
                "completed_units": task.completed_units,
                "total_units": task.total_units,
                "current_unit": unit_index,
                "current_scene": None
            })

            # 检查中断信号
            if self._check_interrupted():
                self.logger.warning(f"继续生成任务被中断于单元 {unit_index}")
                task.status = TaskStatus.INTERRUPTED
                await self.db.commit()
                return self._build_error_result(
                    f"任务被中断于单元 {unit_index}",
                    completed_units=task.completed_units,
                    total_units=task.total_units
                )

            # 处理单个单元 - 使用与初始生成一致的 direct 模式
            self.logger.info(f"[继续生成] 处理单元 {unit_index} (direct 模式)")
            unit_result = await self._process_unit_direct(context, unit_index)

            if unit_result.success:
                task.completed_units += 1
                completed_in_this_run += 1
                await self.db.commit()

                # [修复] 累积前文结尾内容到 context.previous_content
                # 单元剧模式跳过：清空 previous_content，不累积跨集上下文
                if _skip_previous_accumulation:
                    context.previous_content = ""
                    mode_label = "纯单元剧" if _is_pure_episodic else "主线串联单元剧"
                    self.logger.info(
                        f"[上下文累积] {mode_label}模式：单元 {unit_index} 完成，清空 previous_content"
                    )
                else:
                    try:
                        from app.models.writing_unit import WritingUnit as _WritingUnit
                        unit_query = select(_WritingUnit).where(
                            _WritingUnit.task_id == task.id,
                            _WritingUnit.unit_index == unit_index
                        )
                        db_unit_result = await self.db.execute(unit_query)
                        db_unit = db_unit_result.scalar_one_or_none()
                        if db_unit and db_unit.final_content:
                            unit_content = db_unit.final_content
                            if context.previous_content:
                                context.previous_content += "\n\n" + unit_content
                            else:
                                context.previous_content = unit_content
                            if len(context.previous_content) > 5000:
                                context.previous_content = context.previous_content[-5000:]
                            self.logger.info(
                                f"[上下文累积] 单元 {unit_index} 完成，"
                                f"previous_content 长度: {len(context.previous_content)} 字符"
                            )
                    except Exception as accumulate_error:
                        self.logger.warning(
                            f"[上下文累积] 更新 previous_content 失败: {accumulate_error}"
                        )
            else:
                self.logger.error(f"单元 {unit_index} 处理失败: {unit_result.errors}")
                if _cfg.get("stop_on_error", True):
                    task.status = TaskStatus.FAILED
                    task.error_message = f"单元 {unit_index} 失败: {unit_result.errors[0] if unit_result.errors else '未知错误'}"
                    await self.db.commit()
                    return self._build_error_result(
                        task.error_message,
                        completed_units=task.completed_units,
                        total_units=task.total_units
                    )

        # 完成
        if self._stats_interceptor:
            stats = self._stats_interceptor.get_summary()
            task.total_tokens = stats["total_tokens"]
            task.total_cost = stats["total_cost"]
        task.status = TaskStatus.COMPLETED
        task.end_time = datetime.now()
        await self.db.commit()

        # 更新项目状态和完成章节数
        try:
            project_result = await self.db.execute(
                select(NovelProject).where(NovelProject.id == context.project_id)
            )
            project = project_result.scalar_one_or_none()
            if project:
                project.status = ProjectStatus.COMPLETED
                project.completed_chapters = task.completed_units
                project.current_chapter = task.total_units
                await self.db.commit()
                self.logger.info(f"项目状态已更新: project_id={context.project_id}, status=completed, completed_chapters={task.completed_units}")
        except Exception as e:
            self.logger.warning(f"更新项目状态失败: {e}")

        self.logger.info(f"继续生成完成: {completed_in_this_run} 个单元")

        return self._build_success_result(
            content=f"继续生成完成，共生成 {completed_in_this_run} 个单元",
            duration_ms=0,
            completed_units=task.completed_units,
            total_units=task.total_units,
            task_id=context.task_id
        )

    async def _determine_resume_start(self, task: WritingTask) -> int:
        """确定续传起始单元
            
        使用多重检测机制：
        1. 首先检查检查点
        2. 然后检查已完成的单元记录
        3. 最后检查任务的 completed_units 字段

        Args:
            task: 写作任务

        Returns:
            续传起始单元序号（1-based）
        """
        # 方案1：检查检查点
        checkpoint = await self._load_checkpoint(task.id)
        if checkpoint and checkpoint.last_completed_unit >= 0:
            self.logger.info(f"从检查点恢复: 最后完成单元 {checkpoint.last_completed_unit}")
            return checkpoint.last_completed_unit + 1

        # 方案2：查询实际已完成的单元
        result = await self.db.execute(
            select(func.max(WritingUnit.unit_index)).where(
                WritingUnit.task_id == task.id,
                WritingUnit.status == UnitStatus.COMPLETED
            )
        )
        max_completed_unit = result.scalar()
        if max_completed_unit is not None and max_completed_unit >= 0:
            self.logger.info(f"从已完成单元记录恢复: 最大完成单元 {max_completed_unit}")
            return max_completed_unit + 1

        # 方案3：使用任务的 completed_units 字段
        if task.completed_units > 0:
            # 需要结合 start_from 计算
            start_from = task.start_from or 1
            last_completed = start_from + task.completed_units - 1
            self.logger.info(f"从任务进度恢复: completed_units={task.completed_units}, 最后完成单元 {last_completed}")
            return last_completed + 1

        # 没有任何进度记录，从头开始
        self.logger.info("没有找到任何进度记录，从头开始执行")
        return task.start_from or 1

    # ==================== 任务数据库操作 ====================
    
    async def _load_task(self, task_uuid: str) -> Optional[WritingTask]:
        """通过UUID加载任务"""
        result = await self.db.execute(
            select(WritingTask).where(WritingTask.uuid == task_uuid).limit(1)
        )
        return result.scalar_one_or_none()

    async def _load_or_create_task(self, context: AgentContext) -> WritingTask:
        """加载或创建任务记录"""
        task = await self._load_task(context.task_id)

        if task:
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.start_time = datetime.now()
            await self.db.commit()
            return task

        # 创建新任务
        task = WritingTask(
            uuid=context.task_id,
            project_id=context.project_id,
            user_id=context.user_id,
            status=TaskStatus.RUNNING,
            total_units=context.config.get("total_units", 1),
            completed_units=0,
            config=context.config,
            start_from=context.config.get("start_from", 1),
            unit_count=context.config.get("unit_count"),
            start_time=datetime.now()
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        return task

    async def _execute_from_unit(
        self, 
        context: AgentContext, 
        task: WritingTask, 
        start_unit: int
    ) -> AgentResult:
        """从指定单元开始执行"""
        # 更新上下文配置
        context.config["start_from"] = start_unit

        # 继续执行
        return await self.execute(context)
    
    async def _get_chapter_detailed_outline(self, project_id: int, chapter_num: int) -> Optional[dict]:
        """获取章节详细大纲

        从项目的 chapter_outlines 字段获取指定章节的详细大纲。
        如果不存在，返回 None（跳过策略）。

        Args:
            project_id: 项目ID
            chapter_num: 章节号

        Returns:
            章节详细大纲字典，或 None
        """
        try:
            from app.models.novel_project import NovelProject

            result = await self.db.execute(
                select(NovelProject).where(NovelProject.id == project_id).limit(1)
            )
            project = result.scalar_one_or_none()

            if not project:
                self.logger.warning(f"项目不存在: {project_id}")
                return None

            # 获取章节详细大纲
            chapter_outlines = project.chapter_outlines or {}
            chapter_outline = chapter_outlines.get(str(chapter_num))

            if chapter_outline:
                self.logger.info(
                    f"[章节大纲] 获取章节 {chapter_num} 详细大纲成功: "
                    f"title={chapter_outline.get('chapter_title')}, "
                    f"detailed_outline_len={len(chapter_outline.get('detailed_outline', ''))}"
                )
                return chapter_outline

            self.logger.info(f"[章节大纲] 章节 {chapter_num} 详细大纲不存在，将使用基础大纲")
            return None

        except Exception as e:
            self.logger.error(f"获取章节详细大纲失败: {str(e)}")
            return None
