"""
多Agent协作文学作品生成系统 - 内容生成流水线模块

模块: agents.writing.orchestrator_agent
文件: content_pipeline.py
功能: 核心执行流程、单元处理、并发写作、审阅流水线、单元/场景数据库操作

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.writing.base_agent import AgentContext, AgentResult, AgentRole
from app.core.database import async_session_maker
from app.models.writing_task import WritingTask, TaskStatus
from app.models.writing_unit import WritingUnit, UnitStatus
from app.models.writing_scene import WritingScene, SceneStatus
from app.models.novel_project import NovelProject, ProjectStatus


class ContentPipelineMixin:
    """内容生成流水线 Mixin

    提供：
    - 核心执行流程 (execute)
    - 单元处理 (_process_unit, _process_unit_direct)
    - 并发写作 (_concurrent_write_scenes)
    - 审阅流水线 (_run_review_pipeline_for_unit)
    - 单元/场景数据库操作
    """

    # 这些属性由主类提供，类型提示
    db: AsyncSession
    _interrupt_event: Any  # asyncio.Event
    _semaphore: Optional[asyncio.Semaphore]
    _current_task: Optional[WritingTask]
    _max_concurrent_writers: int
    _character_tracker: Any  # CharacterStateTracker
    _project_knowledge_base: Any  # ProjectKnowledgeBase
    _stats_interceptor: Any  # StatsInterceptor
    logger: Any

    # 从 MonitoringMixin 继承的方法
    _check_interrupted: callable
    _send_ws_message: callable
    _initialize_character_tracker: callable
    _save_checkpoint: callable
    _update_character_states: callable

    # 从 AgentCommunicationMixin 继承的方法
    _get_agent: callable
    _call_structural_agent: callable
    _call_logic_editor: callable
    _call_style_editor: callable
    _call_compliance_agent: callable
    _call_assembler_agent: callable

    # 从 TaskSchedulerMixin 继承的方法
    _load_or_create_task: callable
    _get_chapter_detailed_outline: callable
    _build_error_result: callable
    _build_success_result: callable

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

            # 2.5 初始化人物状态追踪器（新增）
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
            # 架构优化后：只使用 direct 模式（基于全局大纲+单元概述的直接生成模式）
            # 移除了详细大纲依赖和场景拆解模式，简化写作流程
            generation_mode = "direct"  # 固定使用直接生成模式
            self.logger.info(f"生成模式: {generation_mode} (架构优化版)")

            # 4. 遍历处理每个Unit
            total_units = task.total_units
            # 续传时，从任务已完成的单元数开始计数
            completed_units = task.completed_units or 0

            for unit_index in range(start_unit, total_units + 1):
                # 发送任务进度推送（单元开始）
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

                # 架构优化：固定使用 direct 模式，基于全局大纲+单元概述直接生成
                # 不再检测详细大纲，不再使用场景拆解模式
                chapter_detailed_outline = None  # 不再使用详细大纲

                # 发送模式决策日志
                await self._send_ws_message("mode_decision", {
                    "unit_index": unit_index,
                    "has_detailed_outline": False,
                    "selected_mode": "direct",
                    "reason": "架构优化：基于全局大纲+单元概述的直接生成模式"
                })

                # 处理单个单元 - 直接生成模式
                self.logger.info(f"处理单元 {unit_index}/{total_units} (direct模式)")

                # 直接调用 _process_unit_direct 方法
                unit_result = await self._process_unit_direct(
                    context, unit_index, chapter_detailed_outline
                )

                if unit_result.success:
                    completed_units += 1
                    task.completed_units = completed_units
                    await self.db.commit()

                    # 发送任务进度推送（单元完成）
                    await self._send_ws_message("task_progress", {
                        "completed_units": completed_units,
                        "total_units": total_units,
                        "current_unit": unit_index,
                        "current_scene": None
                    })
                else:
                    # 单个单元失败，记录错误但继续（根据配置决定是否停止）
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
            # 最终统计同步
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
                    project.completed_chapters = completed_units
                    project.current_chapter = total_units
                    await self.db.commit()
                    self.logger.info(f"项目状态已更新: project_id={context.project_id}, status=completed, completed_chapters={completed_units}")
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

    async def _process_unit(self, context: AgentContext, unit_index: int) -> AgentResult:
        """处理单个写作单元

        执行完整的Unit流水线：
        1. 调用结构师Agent拆解场景
        2. 并发调用写手Agent（受Semaphore限制）
        3. 并行审阅：逻辑编辑 + 风格润色 + 合规审查
        4. 调用合成Agent合并结果
        5. 保存检查点

        Args:
            context: Agent执行上下文
            unit_index: 单元序号

        Returns:
            AgentResult: 单元处理结果
        """
        unit_start_time = time.time()
        self.logger.info(f"开始处理单元 {unit_index}")
        unit = None

        try:
            # 1. 获取或创建Unit记录
            unit = await self._get_or_create_unit(context, unit_index)
            unit.status = UnitStatus.STRUCTURING
            await self.db.commit()

            # 检查中断信号（在调用结构师之前）
            if self._check_interrupted():
                self.logger.warning(f"任务在结构拆解前被中断: 单元 {unit_index}")
                unit.status = UnitStatus.PENDING
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            # 发送工作流步骤消息：开始结构拆解
            await self._send_ws_message("workflow_step", {
                "step": "structuring",
                "status": "running",
                "message": f"单元 {unit_index}: 正在拆解场景结构...",
                "agent_name": "结构师Agent",
                "unit_index": unit_index,
                "icon": "OfficeBuilding"
            })

            # 发送单元进度推送（开始结构化）
            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "structuring",
                "progress": 0.0
            })

            # 2. 调用结构师Agent拆解场景
            self.logger.info(f"单元 {unit_index}: 调用结构师Agent拆解场景")
            structural_result = await self._call_structural_agent(context, unit)

            # 检查中断信号（结构师完成后）
            if self._check_interrupted():
                self.logger.warning(f"任务在结构拆解后被中断: 单元 {unit_index}")
                unit.status = UnitStatus.PENDING
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            if not structural_result.success:
                # 发送工作流步骤消息：结构拆解失败
                await self._send_ws_message("workflow_step", {
                    "step": "structuring",
                    "status": "error",
                    "message": f"单元 {unit_index}: 场景拆解失败",
                    "agent_name": "结构师Agent",
                    "unit_index": unit_index,
                    "icon": "OfficeBuilding"
                })
                unit.status = UnitStatus.PENDING
                await self.db.commit()
                return self._build_error_result(f"结构分析失败: {structural_result.errors}")

            # 发送工作流步骤消息：结构拆解完成
            await self._send_ws_message("workflow_step", {
                "step": "structuring",
                "status": "done",
                "message": f"单元 {unit_index}: 场景拆解完成，共 {len(structural_result.data.get('scenes', []))} 个场景",
                "agent_name": "结构师Agent",
                "unit_index": unit_index,
                "icon": "OfficeBuilding"
            })

            # 保存场景结构
            scenes_data = structural_result.data.get("scenes", [])
            unit.scenes_data = scenes_data
            unit.status = UnitStatus.PROCESSING
            await self.db.commit()

            # 发送工作流步骤消息：开始内容生成
            await self._send_ws_message("workflow_step", {
                "step": "writing",
                "status": "running",
                "message": f"单元 {unit_index}: 正在生成 {len(scenes_data)} 个场景内容...",
                "agent_name": "写手Agent",
                "unit_index": unit_index,
                "icon": "EditPen"
            })

            # 发送单元进度推送（开始写作）
            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "writing",
                "progress": 25.0
            })

            # 3. 并发调用写手Agent生成场景内容
            self.logger.info(
                f"单元 {unit_index}: 并发调用写手Agent生成 {len(scenes_data)} 个场景")
            scene_results = await self._concurrent_write_scenes(context, unit, scenes_data)

            # 检查中断信号（写作完成后）
            if self._check_interrupted():
                self.logger.warning(f"任务在内容生成后被中断: 单元 {unit_index}")
                unit.status = UnitStatus.INTERRUPTED
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            # 发送工作流步骤消息：内容生成完成
            successful_scenes = [r for r in scene_results if r.get("success")]
            await self._send_ws_message("workflow_step", {
                "step": "writing",
                "status": "done",
                "message": f"单元 {unit_index}: 内容生成完成，成功 {len(successful_scenes)}/{len(scenes_data)} 个场景",
                "agent_name": "写手Agent",
                "unit_index": unit_index,
                "icon": "EditPen"
            })

            # 发送单元进度推送（开始审阅）
            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "reviewing",
                "progress": 60.0
            })

            # 发送工作流步骤消息：开始审阅
            await self._send_ws_message("workflow_step", {
                "step": "reviewing",
                "status": "running",
                "message": f"单元 {unit_index}: 正在审阅润色内容...",
                "agent_name": "编辑Agent",
                "unit_index": unit_index,
                "icon": "View"
            })

            # 4. 并行审阅流水线
            self.logger.info(f"单元 {unit_index}: 启动并行审阅流水线")
            await self._run_review_pipeline_for_unit(context, unit, scene_results)

            # 检查中断信号（审阅完成后）
            if self._check_interrupted():
                self.logger.warning(f"任务在审阅后被中断: 单元 {unit_index}")
                unit.status = UnitStatus.INTERRUPTED
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            # 发送工作流步骤消息：审阅完成
            await self._send_ws_message("workflow_step", {
                "step": "reviewing",
                "status": "done",
                "message": f"单元 {unit_index}: 审阅润色完成",
                "agent_name": "编辑Agent",
                "unit_index": unit_index,
                "icon": "View"
            })

            # 发送单元进度推送（开始组装）
            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "assembling",
                "progress": 80.0
            })

            # 发送工作流步骤消息：开始组装
            await self._send_ws_message("workflow_step", {
                "step": "assembling",
                "status": "running",
                "message": f"单元 {unit_index}: 正在组装最终内容...",
                "agent_name": "合成Agent",
                "unit_index": unit_index,
                "icon": "SetUp"
            })

            # 5. 调用合成Agent合并结果
            self.logger.info(f"单元 {unit_index}: 调用合成Agent合并场景")
            final_content = await self._call_assembler_agent(context, unit)

            # 发送工作流步骤消息：组装完成
            await self._send_ws_message("workflow_step", {
                "step": "assembling",
                "status": "done",
                "message": f"单元 {unit_index}: 内容组装完成，共 {len(final_content)} 字",
                "agent_name": "合成Agent",
                "unit_index": unit_index,
                "icon": "SetUp"
            })

            # 6. 更新Unit状态
            unit.final_content = final_content
            unit.word_count = len(final_content)
            unit.status = UnitStatus.COMPLETED
            unit.duration_ms = int((time.time() - unit_start_time) * 1000)
            await self.db.commit()

            # 发送单元进度推送（完成）
            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "completed",
                "progress": 100.0,
                "word_count": unit.word_count or 0
            })

            # 发送统计数据推送（单元完成后）
            if self._stats_interceptor:
                stats_summary = self._stats_interceptor.get_summary()
                if stats_summary["total_tokens"] > 0:
                    await self._send_ws_message("statistics", {
                        "total_tokens": stats_summary["total_tokens"],
                        "total_cost": stats_summary["total_cost"],
                        "call_count": stats_summary["call_count"],
                        "by_agent": stats_summary["by_agent"]
                    })
                    # 同步更新数据库
                    if self._current_task:
                        self._current_task.total_tokens = stats_summary["total_tokens"]
                        self._current_task.total_cost = stats_summary["total_cost"]
                        try:
                            await self.db.commit()
                        except Exception as e:
                            self.logger.warning(f"更新统计数据失败: {e}")

            # 7. 保存检查点
            await self._save_checkpoint(context.task_id, unit_index, None, "unit_completed")

            # 8. 更新人物状态追踪（集成知识图谱）
            if self._character_tracker and final_content:
                try:
                    # 获取LLM提供者用于提取人物状态实体
                    llm_provider = None
                    if hasattr(context, 'extra') and context.extra:
                        llm_provider = context.extra.get('llm_provider')

                    await self._update_character_states(
                        chapter_num=unit_index,
                        chapter_title=unit.unit_title,
                        content=final_content,
                        project_id=context.project_id,
                        llm_provider=llm_provider
                    )
                except Exception as e:
                    self.logger.warning(f"更新人物状态失败: {e}")

            duration_ms = int((time.time() - unit_start_time) * 1000)
            self.logger.info(f"单元 {unit_index} 处理完成，耗时 {duration_ms}ms")

            return self._build_success_result(
                content=final_content,
                duration_ms=duration_ms,
                unit_index=unit_index,
                scene_count=len(scenes_data)
            )

        except Exception as e:
            self.logger.exception(f"处理单元 {unit_index} 时发生异常: {str(e)}")
            if unit:
                unit.status = UnitStatus.INTERRUPTED
                await self.db.commit()
            return self._build_error_result(f"单元处理异常: {str(e)}")

    async def _process_unit_direct(
        self,
        context: AgentContext,
        unit_index: int,
        chapter_detailed_outline: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """直接生成整章内容（跳过场景拆解）

        适用于短篇小说和简单项目，直接调用WriterAgent生成整章内容。
        支持智能模式传入预检测的详细大纲，避免重复查询。

        Args:
            context: Agent执行上下文
            unit_index: 单元序号
            chapter_detailed_outline: 预检测的章节详细大纲（可选，由智能模式传入）

        Returns:
            AgentResult: 单元处理结果
        """
        unit_start_time = time.time()
        self.logger.info(f"[整章生成] 开始处理单元 {unit_index}")
        unit = None

        try:
            # 1. 获取或创建Unit记录
            unit = await self._get_or_create_unit(context, unit_index)
            unit.status = UnitStatus.PROCESSING
            await self.db.commit()

            # 检查中断信号
            if self._check_interrupted():
                self.logger.warning(f"[整章生成] 任务被中断: 单元 {unit_index}")
                unit.status = UnitStatus.PENDING
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            # 发送单元进度推送
            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "writing",
                "progress": 0.0
            })

            # 发送工作流步骤消息
            await self._send_ws_message("workflow_step", {
                "step": "direct_writing",
                "status": "running",
                "message": f"单元 {unit_index}: 正在生成整章内容...",
                "agent_name": "写手Agent",
                "unit_index": unit_index,
                "icon": "EditPen"
            })

            # 2. 直接调用WriterAgent生成整章内容
            from app.agents.writing.writer_agent import WriterAgent

            writer_agent = self._get_agent(AgentRole.WRITER, WriterAgent)

            # 获取字数配置
            words_per_unit = context.config.get("words_per_unit", 3000)

            # 架构优化：获取人物状态追踪信息和前文知识图谱参考
            character_state_snapshot = ""
            knowledge_graph_context = ""
            extended_consistency_context = ""  # v3.0.0: 扩展实体一致性上下文
            if self._character_tracker:
                # 获取人物状态快照
                character_state_snapshot = self._character_tracker.get_state_for_prompt(
                    chapter_num=unit_index
                )
                # 获取前文知识图谱参考（架构优化新增）
                knowledge_graph_context = self._character_tracker.get_knowledge_graph_context_for_writing(
                    chapter_num=unit_index,
                    max_entities=30
                )
                self.logger.info(f"[整章生成] 已获取前文知识图谱参考: 单元 {unit_index}")

            # v3.0.0: 获取扩展实体一致性上下文
            if self._project_knowledge_base and context.project_id:
                try:
                    from app.tools.novel_graph_rag import NovelKnowledgeGraph
                    graph_path = self._project_knowledge_base.get_graph_path(
                        context.project_id, unit_index)
                    import os
                    if graph_path and os.path.exists(graph_path):
                        knowledge_graph = NovelKnowledgeGraph(
                            persist_path=graph_path)
                        if knowledge_graph.load():
                            consistency_report = knowledge_graph.get_consistency_report(
                                unit_index)
                            extended_consistency_context = knowledge_graph.format_consistency_report_for_prompt(
                                unit_index)
                            self.logger.info(
                                f"[整章生成] 已获取扩展实体一致性上下文: 单元 {unit_index}")
                except Exception as e:
                    self.logger.warning(f"获取扩展实体上下文失败: {e}")

            # 架构优化：不再获取详细大纲，直接基于全局大纲+单元概述生成
            # chapter_detailed_outline 固定为 None
            self.logger.info(f"[整章生成] 使用全局大纲+单元概述模式: 单元 {unit_index}")

            # 获取风格文档特征（用于传递给写手）
            style_document_features = context.config.get(
                "style_document_features", "")
            if style_document_features:
                self.logger.info(
                    f"[整章生成] 风格文档特征已加载，长度: {len(style_document_features)}")

            # 构建写手上下文
            writer_context = AgentContext(
                task_id=context.task_id,
                unit_index=unit_index,
                scene_index=0,  # 整章生成时场景索引为0
                project_id=context.project_id,
                user_id=context.user_id,
                outline=context.outline,
                global_context=context.global_context,
                character_profiles=context.character_profiles,
                world_settings=context.world_settings,
                style_guide=context.style_guide,
                previous_content=context.previous_content,
                character_state_snapshot=character_state_snapshot,
                extra={
                    "unit_title": unit.unit_title,
                    "unit_summary": unit.unit_summary,
                    "direct_mode": True,  # 标记为整章生成模式
                    "knowledge_graph_context": knowledge_graph_context,  # 架构优化：前文知识图谱参考
                    "extended_consistency_context": extended_consistency_context,  # v3.0.0: 扩展实体一致性
                    "style_document_features": style_document_features  # 风格文档特征
                },
                config={
                    "words_per_scene": words_per_unit,  # 整章字数
                    "style_document_features": style_document_features,  # 显式传递风格文档特征
                    **context.config
                }
            )

            result = await writer_agent.execute(writer_context)

            # 检查中断信号
            if self._check_interrupted():
                self.logger.warning(f"[整章生成] 任务在写作后被中断: 单元 {unit_index}")
                unit.status = UnitStatus.INTERRUPTED
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            if not result.success:
                self.logger.error(f"[整章生成] 写作失败: {result.errors}")
                unit.status = UnitStatus.PENDING
                await self.db.commit()
                return self._build_error_result(f"写作失败: {result.errors}")

            # 3. 更新Unit状态
            final_content = result.content
            unit.final_content = final_content
            unit.word_count = len(final_content)
            unit.status = UnitStatus.COMPLETED
            unit.duration_ms = int((time.time() - unit_start_time) * 1000)

            # 创建单个场景记录（用于兼容）
            scene = WritingScene(
                unit_id=unit.id,
                scene_index=1,
                scene_title=unit.unit_title or f"场景1",
                scene_outline={"direct_mode": True},
                status=SceneStatus.COMPLETED,
                final_content=final_content,
                word_count=len(final_content)
            )
            self.db.add(scene)
            await self.db.commit()

            # 发送单元进度推送（完成）
            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "completed",
                "progress": 100.0,
                "word_count": unit.word_count or 0
            })

            # 发送工作流步骤消息：完成
            await self._send_ws_message("workflow_step", {
                "step": "direct_writing",
                "status": "done",
                "message": f"单元 {unit_index}: 整章内容生成完成，共 {len(final_content)} 字",
                "agent_name": "写手Agent",
                "unit_index": unit_index,
                "icon": "EditPen"
            })

            # 发送统计数据推送
            if self._stats_interceptor:
                stats_summary = self._stats_interceptor.get_summary()
                if stats_summary["total_tokens"] > 0:
                    await self._send_ws_message("statistics", {
                        "total_tokens": stats_summary["total_tokens"],
                        "total_cost": stats_summary["total_cost"],
                        "call_count": stats_summary["call_count"],
                        "by_agent": stats_summary["by_agent"]
                    })
                    if self._current_task:
                        self._current_task.total_tokens = stats_summary["total_tokens"]
                        self._current_task.total_cost = stats_summary["total_cost"]
                        try:
                            await self.db.commit()
                        except Exception as e:
                            self.logger.warning(f"更新统计数据失败: {e}")

            # 4. 保存检查点
            await self._save_checkpoint(context.task_id, unit_index, None, "unit_completed")

            # 5. 更新人物状态追踪
            if self._character_tracker and final_content:
                try:
                    llm_provider = None
                    if hasattr(context, 'extra') and context.extra:
                        llm_provider = context.extra.get('llm_provider')

                    await self._update_character_states(
                        chapter_num=unit_index,
                        chapter_title=unit.unit_title,
                        content=final_content,
                        project_id=context.project_id,
                        llm_provider=llm_provider
                    )
                except Exception as e:
                    self.logger.warning(f"更新人物状态失败: {e}")

            duration_ms = int((time.time() - unit_start_time) * 1000)
            self.logger.info(f"[整章生成] 单元 {unit_index} 处理完成，耗时 {duration_ms}ms")

            return self._build_success_result(
                content=final_content,
                duration_ms=duration_ms,
                unit_index=unit_index,
                scene_count=1
            )

        except Exception as e:
            self.logger.exception(f"[整章生成] 处理单元 {unit_index} 时发生异常: {str(e)}")
            if unit:
                unit.status = UnitStatus.INTERRUPTED
                await self.db.commit()
            return self._build_error_result(f"单元处理异常: {str(e)}")

    async def _concurrent_write_scenes(
        self,
        context: AgentContext,
        unit: WritingUnit,
        scenes_data: List[Dict]
    ) -> List[Dict[str, Any]]:
        """并发调用写手Agent生成场景内容

        使用asyncio.Semaphore控制并发数量

        Args:
            context: Agent执行上下文
            unit: 写作单元
            scenes_data: 场景数据列表

        Returns:
            List[Dict]: 场景结果列表
        """
        # 计算精确的每场景字数
        words_per_unit = context.config.get("words_per_unit", 3000)
        scene_count = len(scenes_data)
        words_per_scene = words_per_unit // scene_count if scene_count > 0 else words_per_unit

        async def write_single_scene(scene_data: Dict, scene_index: int) -> Dict[str, Any]:
            """单个场景的写入任务 - 每个任务使用独立的数据库会话"""
            async with self._semaphore:
                # 检查中断信号
                if self._check_interrupted():
                    return {
                        "scene_index": scene_index,
                        "success": False,
                        "error": "任务被中断"
                    }

                scene_title = scene_data.get("scene_title", f"场景{scene_index}")

                # 发送场景进度推送（开始写作）
                await self._send_ws_message("scene_progress", {
                    "unit_index": unit.unit_index,
                    "scene_index": scene_index,
                    "scene_title": scene_title,
                    "status": "writing"
                })

                # 为每个并发场景创建独立的数据库会话
                async with async_session_maker() as scene_db:
                    try:
                        # 延迟导入避免循环依赖
                        from app.agents.writing.writer_agent import WriterAgent

                        writer_agent = self._get_agent(
                            AgentRole.WRITER, WriterAgent)

                        # 获取或创建Scene记录（使用独立会话）
                        scene = await self._get_or_create_scene_with_db(scene_db, unit.id, scene_index, scene_data)
                        scene.status = SceneStatus.WRITING
                        await scene_db.commit()

                        character_state_snapshot = ""
                        relationship_summary = ""
                        character_states = {}
                        character_location_map = {}
                        character_identity_map = {}
                        active_characters = []

                        if self._character_tracker:
                            character_state_snapshot = self._character_tracker.get_state_for_prompt(
                                chapter_num=unit.unit_index
                            )
                            relationship_summary = self._character_tracker.get_relationship_summary()

                            all_states = self._character_tracker.get_all_characters()
                            character_states = {name: state.to_dict(
                            ) for name, state in all_states.items()}
                            character_location_map = {
                                name: state.location for name, state in all_states.items() if state.location}
                            character_identity_map = {
                                name: state.identity for name, state in all_states.items() if state.identity}
                            active_characters = [name for name, state in all_states.items()
                                                 if state.status.value in ["active", "mentioned"]]

                        knowledge_graph_states = ""
                        if self._project_knowledge_base and context.project_id:
                            try:
                                knowledge_graph_states = self._project_knowledge_base.get_all_character_states_for_chapter(
                                    context.project_id, unit.unit_index
                                )
                            except Exception as kg_error:
                                self.logger.warning(
                                    f"获取知识图谱人物状态失败: {kg_error}")

                        writer_context = AgentContext(
                            task_id=context.task_id,
                            unit_index=unit.unit_index,
                            scene_index=scene_index,
                            project_id=context.project_id,
                            user_id=context.user_id,
                            outline=context.outline,
                            global_context=context.global_context,
                            character_profiles=context.character_profiles,
                            world_settings=context.world_settings,
                            style_guide=context.style_guide,
                            previous_content=context.previous_content,
                            character_state_snapshot=character_state_snapshot,
                            relationship_summary=relationship_summary,
                            character_states=character_states,
                            character_location_map=character_location_map,
                            character_identity_map=character_identity_map,
                            active_characters=active_characters,
                            extra={
                                "scene_outline": scene_data,
                                "unit_title": unit.unit_title,
                                "knowledge_graph_states": knowledge_graph_states
                            },
                            config={
                                "words_per_scene": words_per_scene,
                                **context.config
                            }
                        )

                        result = await writer_agent.execute(writer_context)

                        # 更新Scene记录（使用独立会话）
                        if result.success:
                            scene.writer_result = {
                                "content": result.content,
                                "token_usage": result.token_usage
                            }
                            scene.final_content = result.content
                            scene.word_count = len(result.content)
                            scene.status = SceneStatus.REVIEWING
                        else:
                            scene.status = SceneStatus.FAILED

                        await scene_db.commit()

                        # 发送场景进度推送（完成）
                        scene_status = "completed" if result.success else "failed"
                        await self._send_ws_message("scene_progress", {
                            "unit_index": unit.unit_index,
                            "scene_index": scene_index,
                            "scene_title": scene_title,
                            "status": scene_status
                        })

                        return {
                            "scene_index": scene_index,
                            "scene_id": scene.id,
                            "success": result.success,
                            "content": result.content if result.success else "",
                            "error": result.errors[0] if result.errors else None
                        }

                    except Exception as e:
                        self.logger.exception(
                            f"场景 {scene_index} 写入失败: {str(e)}")
                        # 发送场景进度推送（失败）
                        await self._send_ws_message("scene_progress", {
                            "unit_index": unit.unit_index,
                            "scene_index": scene_index,
                            "scene_title": scene_title,
                            "status": "failed"
                        })
                        return {
                            "scene_index": scene_index,
                            "success": False,
                            "error": str(e)
                        }

        # 创建所有场景的写入任务
        tasks = [
            write_single_scene(scene_data, idx + 1)
            for idx, scene_data in enumerate(scenes_data)
        ]

        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        return processed_results

    async def _run_review_pipeline_for_unit(
        self,
        context: AgentContext,
        unit: WritingUnit,
        scene_results: List[Dict[str, Any]]
    ) -> None:
        """为单元的所有场景运行并行审阅流水线

        并行执行：逻辑编辑 + 风格润色 + 合规审查

        Args:
            context: Agent执行上下文
            unit: 写作单元
            scene_results: 场景结果列表
        """
        # 筛选成功的场景
        successful_scenes = [r for r in scene_results if r.get("success")]

        async def review_single_scene(scene_result: Dict) -> None:
            """单个场景的审阅任务 - 每个任务使用独立的数据库会话"""
            scene_index = scene_result["scene_index"]
            scene_id = scene_result.get("scene_id")
            content = scene_result.get("content", "")

            if not scene_id:
                return

            # 为每个并发审阅任务创建独立的数据库会话
            async with async_session_maker() as review_db:
                try:
                    # 并行执行三个审阅Agent
                    logic_result, style_result, compliance_result = await asyncio.gather(
                        self._call_logic_editor(
                            context, unit, scene_index, content),
                        self._call_style_editor(
                            context, unit, scene_index, content),
                        self._call_compliance_agent(
                            context, unit, scene_index, content),
                        return_exceptions=True
                    )

                    # 获取Scene记录并更新（使用独立会话）
                    scene = await self._get_scene_by_id_with_db(review_db, scene_id)
                    if scene:
                        # 记录审阅结果
                        if isinstance(logic_result, AgentResult):
                            scene.editor_result = {
                                "content": logic_result.content,
                                "issues": logic_result.data.get("issues", [])
                            }

                        if isinstance(style_result, AgentResult):
                            scene.stylist_result = {
                                "content": style_result.content,
                                "suggestions": style_result.data.get("suggestions", [])
                            }

                        if isinstance(compliance_result, AgentResult):
                            scene.compliance_result = {
                                "passed": compliance_result.success,
                                "violations": compliance_result.data.get("violations", [])
                            }

                        # 应用审阅结果（简化版本：直接使用风格润色结果）
                        if isinstance(style_result, AgentResult) and style_result.success:
                            scene.final_content = style_result.content

                        scene.status = SceneStatus.COMPLETED
                        await review_db.commit()

                except Exception as e:
                    self.logger.exception(f"场景 {scene_index} 审阅失败: {str(e)}")

        # 并发执行所有场景的审阅
        review_tasks = [review_single_scene(sr) for sr in successful_scenes]
        await asyncio.gather(*review_tasks, return_exceptions=True)

    # ==================== 单元/场景数据库操作 ====================

    async def _get_or_create_unit(self, context: AgentContext, unit_index: int) -> WritingUnit:
        """获取或创建单元记录"""
        if not self._current_task:
            raise ValueError("当前任务未设置")

        # 尝试查找现有单元
        result = await self.db.execute(
            select(WritingUnit).where(
                WritingUnit.task_id == self._current_task.id,
                WritingUnit.unit_index == unit_index
            ).limit(1)
        )
        unit = result.scalar_one_or_none()

        if unit:
            return unit

        # 从多个来源获取单元信息（按优先级）
        unit_title = ""
        unit_summary = ""

        # 优先级1：从 context.config.unit_summaries 获取（这是数据库加载的单元概述）
        unit_summaries = context.config.get("unit_summaries", {})
        self.logger.info(
            f"[_get_or_create_unit] 单元 {unit_index}: 尝试从 unit_summaries 获取，可用单元数: {len(unit_summaries)}")
        if unit_summaries and isinstance(unit_summaries, dict):
            # unit_summaries 的 key 可能是字符串形式的数字
            unit_data = unit_summaries.get(
                str(unit_index)) or unit_summaries.get(unit_index)
            if unit_data:
                unit_title = unit_data.get("title", "")
                unit_summary = unit_data.get("summary", "")
                self.logger.info(
                    f"[_get_or_create_unit] 从 unit_summaries 获取单元 {unit_index} 成功: title={unit_title}, summary_len={len(unit_summary)}")
            else:
                self.logger.warning(
                    f"[_get_or_create_unit] 单元 {unit_index} 在 unit_summaries 中未找到，可用keys: {list(unit_summaries.keys())[:5]}...")

        # 优先级2：从 context.outline.chapters 获取（这是大纲结构中的章节列表）
        if (not unit_title or not unit_summary) and context.outline:
            chapters = context.outline.get("chapters", [])
            if 0 <= unit_index - 1 < len(chapters):
                chapter = chapters[unit_index - 1]
                if not unit_title:
                    unit_title = chapter.get("title", "")
                if not unit_summary:
                    unit_summary = chapter.get("summary", "")
                self.logger.info(
                    f"[_get_or_create_unit] 从 outline.chapters 获取单元 {unit_index}: title={unit_title}")

        # 创建新单元
        unit = WritingUnit(
            task_id=self._current_task.id,
            unit_index=unit_index,
            unit_title=unit_title or f"第{unit_index}章",
            unit_summary=unit_summary,
            status=UnitStatus.PENDING
        )
        self.db.add(unit)
        await self.db.commit()
        await self.db.refresh(unit)

        self.logger.info(
            f"[_get_or_create_unit] 创建单元 {unit_index}: title={unit_title}, summary_len={len(unit_summary)}")

        return unit

    async def _get_or_create_scene(
        self,
        unit_id: int,
        scene_index: int,
        scene_data: Dict
    ) -> WritingScene:
        """获取或创建场景记录"""
        result = await self.db.execute(
            select(WritingScene).where(
                WritingScene.unit_id == unit_id,
                WritingScene.scene_index == scene_index
            ).limit(1)
        )
        scene = result.scalar_one_or_none()

        if scene:
            return scene

        # 创建新场景
        scene = WritingScene(
            unit_id=unit_id,
            scene_index=scene_index,
            scene_title=scene_data.get("scene_title", f"场景{scene_index}"),
            scene_outline=scene_data,
            status=SceneStatus.PENDING
        )
        self.db.add(scene)
        await self.db.commit()
        await self.db.refresh(scene)

        return scene

    async def _get_or_create_scene_with_db(
        self,
        db: AsyncSession,
        unit_id: int,
        scene_index: int,
        scene_data: Dict
    ) -> WritingScene:
        """获取或创建场景记录（使用指定数据库会话）

        Args:
            db: 数据库会话
            unit_id: 单元ID
            scene_index: 场景序号
            scene_data: 场景数据

        Returns:
            WritingScene: 场景记录
        """
        result = await db.execute(
            select(WritingScene).where(
                WritingScene.unit_id == unit_id,
                WritingScene.scene_index == scene_index
            ).limit(1)
        )
        scene = result.scalar_one_or_none()

        if scene:
            return scene

        # 创建新场景
        scene = WritingScene(
            unit_id=unit_id,
            scene_index=scene_index,
            scene_title=scene_data.get("scene_title", f"场景{scene_index}"),
            scene_outline=scene_data,
            status=SceneStatus.PENDING
        )
        db.add(scene)
        await db.commit()
        await db.refresh(scene)

        return scene

    async def _get_scene_by_id(self, scene_id: int) -> Optional[WritingScene]:
        """通过ID获取场景"""
        result = await self.db.execute(
            select(WritingScene).where(WritingScene.id == scene_id).limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_scene_by_id_with_db(self, db: AsyncSession, scene_id: int) -> Optional[WritingScene]:
        """通过ID获取场景（使用指定数据库会话）

        Args:
            db: 数据库会话
            scene_id: 场景ID

        Returns:
            Optional[WritingScene]: 场景记录或None
        """
        result = await db.execute(
            select(WritingScene).where(WritingScene.id == scene_id).limit(1)
        )
        return result.scalar_one_or_none()
