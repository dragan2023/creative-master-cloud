"""
content_pipeline - 单元处理方法模块

包含 ContentPipelineMixin._process_unit() 方法。
处理完整单元流水线：拆解场景、并发写作、并行审阅、合成、质控。

@date: 2026-04-24
@version: v3.0.0
"""
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.agents.writing.base_agent import AgentContext, AgentResult, AgentRole
from app.models.writing_unit import WritingUnit, UnitStatus
from app.models.writing_scene import SceneStatus


class ProcessUnitMixin:
    """单元处理 Mixin

    提供 _process_unit() 方法 - 执行完整的Unit流水线。
    """

    # 由主类提供的属性
    db: Any
    _interrupt_event: Any
    logger: Any
    _semaphore: Optional[Any]
    _current_task: Optional[Any]
    _character_tracker: Any
    _project_knowledge_base: Any
    _stats_interceptor: Any

    # 从其他 Mixin 继承的方法
    _check_interrupted: callable
    _send_ws_message: callable
    _save_checkpoint: callable
    _update_character_states: callable
    _get_agent: callable
    _call_structural_agent: callable
    _call_logic_editor: callable
    _call_style_editor: callable
    _call_compliance_agent: callable
    _call_assembler_agent: callable
    _build_error_result: callable
    _build_success_result: callable

    # 从本模块子模块继承的方法
    _get_or_create_unit: callable
    _concurrent_write_scenes: callable
    _run_review_pipeline_for_unit: callable

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

            # 检查中断信号
            if self._check_interrupted():
                self.logger.warning(f"任务在结构拆解前被中断: 单元 {unit_index}")
                unit.status = UnitStatus.PENDING
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            # 发送工作流步骤消息
            await self._send_ws_message("workflow_step", {
                "step": "structuring",
                "status": "running",
                "message": f"单元 {unit_index}: 正在拆解场景结构...",
                "agent_name": "结构师Agent",
                "unit_index": unit_index,
                "icon": "OfficeBuilding"
            })

            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "structuring",
                "progress": 0.0
            })

            # 2. 调用结构师Agent拆解场景
            self.logger.info(f"单元 {unit_index}: 调用结构师Agent拆解场景")
            structural_result = await self._call_structural_agent(context, unit)

            if self._check_interrupted():
                self.logger.warning(f"任务在结构拆解后被中断: 单元 {unit_index}")
                unit.status = UnitStatus.PENDING
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            if not structural_result.success:
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

            await self._send_ws_message("workflow_step", {
                "step": "structuring",
                "status": "done",
                "message": f"单元 {unit_index}: 场景拆解完成，共 {len(structural_result.data.get('scenes', []))} 个场景",
                "agent_name": "结构师Agent",
                "unit_index": unit_index,
                "icon": "OfficeBuilding"
            })

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

            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "writing",
                "progress": 25.0
            })

            # 3. 并发调用写手Agent
            self.logger.info(f"单元 {unit_index}: 并发调用写手Agent生成 {len(scenes_data)} 个场景")
            scene_results = await self._concurrent_write_scenes(context, unit, scenes_data)

            if self._check_interrupted():
                self.logger.warning(f"任务在内容生成后被中断: 单元 {unit_index}")
                unit.status = UnitStatus.INTERRUPTED
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            successful_scenes = [r for r in scene_results if r.get("success")]
            await self._send_ws_message("workflow_step", {
                "step": "writing",
                "status": "done",
                "message": f"单元 {unit_index}: 内容生成完成，成功 {len(successful_scenes)}/{len(scenes_data)} 个场景",
                "agent_name": "写手Agent",
                "unit_index": unit_index,
                "icon": "EditPen"
            })

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

            if self._check_interrupted():
                self.logger.warning(f"任务在审阅后被中断: 单元 {unit_index}")
                unit.status = UnitStatus.INTERRUPTED
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            await self._send_ws_message("workflow_step", {
                "step": "reviewing",
                "status": "done",
                "message": f"单元 {unit_index}: 审阅润色完成",
                "agent_name": "编辑Agent",
                "unit_index": unit_index,
                "icon": "View"
            })

            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "assembling",
                "progress": 80.0
            })

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

            # 7. 同步触发实时质控
            import asyncio as _asyncio
            from app.agents.writing.orchestrator_agent.quality_control_trigger import trigger_unit_quality_control

            project_id = None
            user_id = None
            if self._current_task:
                project_id = self._current_task.project_id
                user_id = self._current_task.user_id

            qc_completed = False
            if project_id and final_content:
                try:
                    if not hasattr(self, '_qc_semaphore'):
                        self._qc_semaphore = _asyncio.Semaphore(2)

                    async with self._qc_semaphore:
                        self.logger.info(f"[质控] 开始质控: unit={unit_index}, 等待完成后再提取知识图谱")
                        await trigger_unit_quality_control(
                            project_id=project_id,
                            unit_index=unit_index,
                            content=final_content,
                            user_id=user_id,
                            ws_send_func=self._send_ws_message
                        )
                        qc_completed = True
                        self.logger.info(f"[质控] 质控完成: unit={unit_index}")
                except Exception as qc_error:
                    self.logger.warning(f"[质控] 质控失败: unit={unit_index}, error={qc_error}，继续执行知识图谱提取")
                    qc_completed = False

            # 发送单元进度推送（完成）
            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "completed",
                "progress": 100.0,
                "word_count": unit.word_count or 0
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

            # 8. 保存检查点
            await self._save_checkpoint(context.task_id, unit_index, None, "unit_completed")

            # 9. 更新人物状态追踪
            if self._character_tracker and final_content:
                try:
                    content_for_kg = final_content
                    if qc_completed:
                        try:
                            from sqlalchemy import select as _select
                            from app.models.writing_unit import WritingUnit

                            await self.db.flush()
                            unit_query = _select(WritingUnit).where(
                                WritingUnit.id == unit.id
                            )
                            unit_result = await self.db.execute(unit_query)
                            refreshed_unit = unit_result.scalar_one_or_none()

                            if refreshed_unit and refreshed_unit.quality_control_status == 'completed' and refreshed_unit.final_content:
                                content_for_kg = refreshed_unit.final_content
                                self.logger.info(f"[知识图谱] 使用质控修正后的内容: unit={unit_index}, 原文{len(final_content)}字符 -> 修正后{len(content_for_kg)}字符")
                            else:
                                self.logger.info(f"[知识图谱] 质控状态: {refreshed_unit.quality_control_status if refreshed_unit else 'None'}, final_content长度: {len(refreshed_unit.final_content) if refreshed_unit and refreshed_unit.final_content else 0}")
                                self.logger.info(f"[知识图谱] 质控未完成或无修正，使用原始内容: unit={unit_index}")
                        except Exception as db_error:
                            self.logger.warning(f"[知识图谱] 读取修正后内容失败: {db_error}，使用原始内容")

                    llm_provider = None
                    if hasattr(context, 'extra') and context.extra:
                        llm_provider = context.extra.get('llm_provider')

                    await self._update_character_states(
                        chapter_num=unit_index,
                        chapter_title=unit.unit_title,
                        content=content_for_kg,
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
