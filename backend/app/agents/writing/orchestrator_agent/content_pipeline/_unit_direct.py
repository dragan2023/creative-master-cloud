"""
content_pipeline - 直接生成模式模块

包含 ContentPipelineMixin._process_unit_direct() 方法。
直接生成整章内容（跳过场景拆解）。

@date: 2026-04-24
@version: v3.0.0
"""
import os as _os
import time
from typing import Any, Dict, Optional

from sqlalchemy import select as _select

from app.agents.writing.base_agent import AgentContext, AgentResult, AgentRole
from app.models.writing_scene import WritingScene, SceneStatus
from app.models.writing_unit import UnitStatus


class UnitDirectMixin:
    """直接生成模式 Mixin

    提供 _process_unit_direct() 方法 - 直接生成整章内容。
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
    _build_error_result: callable
    _build_success_result: callable

    # 从本模块子模块继承的方法
    _get_or_create_unit: callable

    async def _process_unit_direct(
        self,
        context: AgentContext,
        unit_index: int,
        chapter_detailed_outline: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """直接生成整章内容（跳过场景拆解）

        适用于短篇小说和简单项目，直接调用WriterAgent生成整章内容。

        Args:
            context: Agent执行上下文
            unit_index: 单元序号
            chapter_detailed_outline: 预检测的章节详细大纲（可选）

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

            if self._check_interrupted():
                self.logger.warning(f"[整章生成] 任务被中断: 单元 {unit_index}")
                unit.status = UnitStatus.PENDING
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "writing",
                "progress": 0.0
            })

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
            words_per_unit = context.config.get("words_per_unit", 3000)

            character_state_snapshot = ""
            knowledge_graph_context = ""
            extended_consistency_context = ""
            if self._character_tracker:
                character_state_snapshot = self._character_tracker.get_state_for_prompt(
                    chapter_num=unit_index
                )
                knowledge_graph_context = self._character_tracker.get_knowledge_graph_context_for_writing(
                    chapter_num=unit_index,
                    max_entities=30
                )
                self.logger.info(f"[整章生成] 已获取前文知识图谱参考: 单元 {unit_index}")

            if self._project_knowledge_base and context.project_id:
                try:
                    from app.tools.novel_graph_rag import NovelKnowledgeGraph
                    graph_path = self._project_knowledge_base.get_graph_path(
                        context.project_id, unit_index)
                    if graph_path and _os.path.exists(graph_path):
                        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
                        if knowledge_graph.load():
                            extended_consistency_context = knowledge_graph.format_consistency_report_for_prompt(unit_index)
                            self.logger.info(f"[整章生成] 已获取扩展实体一致性上下文: 单元 {unit_index}")
                except Exception as e:
                    self.logger.warning(f"获取扩展实体上下文失败: {e}")

            self.logger.info(f"[整章生成] 使用全局大纲+单元概述模式: 单元 {unit_index}")

            style_document_features = context.config.get("style_document_features", "")
            if style_document_features:
                self.logger.info(f"[整章生成] 风格文档特征已加载，长度: {len(style_document_features)}")

            writer_context = AgentContext(
                task_id=context.task_id,
                unit_index=unit_index,
                scene_index=0,
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
                    "direct_mode": True,
                    "knowledge_graph_context": knowledge_graph_context,
                    "extended_consistency_context": extended_consistency_context,
                    "style_document_features": style_document_features
                },
                config={
                    "words_per_scene": words_per_unit,
                    "style_document_features": style_document_features,
                    **context.config
                }
            )

            result = await writer_agent.execute(writer_context)

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

            # 同步触发实时质控
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
                        self.logger.info(f"[整章生成-质控] 开始质控: unit={unit_index}, 等待完成后再提取知识图谱")
                        await trigger_unit_quality_control(
                            project_id=project_id,
                            unit_index=unit_index,
                            content=final_content,
                            user_id=user_id,
                            ws_send_func=self._send_ws_message
                        )
                        qc_completed = True
                        self.logger.info(f"[整章生成-质控] 质控完成: unit={unit_index}")
                except Exception as qc_error:
                    self.logger.warning(f"[整章生成-质控] 质控失败: unit={unit_index}, error={qc_error}，继续执行知识图谱提取")
                    qc_completed = False

            await self._send_ws_message("unit_progress", {
                "unit_index": unit_index,
                "unit_title": unit.unit_title,
                "status": "completed",
                "progress": 100.0,
                "word_count": unit.word_count or 0
            })

            await self._send_ws_message("workflow_step", {
                "step": "direct_writing",
                "status": "done",
                "message": f"单元 {unit_index}: 整章内容生成完成，共 {len(final_content)} 字",
                "agent_name": "写手Agent",
                "unit_index": unit_index,
                "icon": "EditPen"
            })

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
                    content_for_kg = final_content
                    if qc_completed:
                        try:
                            from app.models.writing_unit import WritingUnit
                            await self.db.flush()
                            unit_query = _select(WritingUnit).where(
                                WritingUnit.id == unit.id
                            )
                            unit_result = await self.db.execute(unit_query)
                            refreshed_unit = unit_result.scalar_one_or_none()

                            if refreshed_unit and refreshed_unit.quality_control_status == 'completed' and refreshed_unit.final_content:
                                content_for_kg = refreshed_unit.final_content
                                self.logger.info(f"[整章生成-知识图谱] 使用质控修正后的内容: unit={unit_index}, 原文{len(final_content)}字符 -> 修正后{len(content_for_kg)}字符")
                            else:
                                self.logger.info(f"[整章生成-知识图谱] 质控状态: {refreshed_unit.quality_control_status if refreshed_unit else 'None'}")
                                self.logger.info(f"[整章生成-知识图谱] 质控未完成或无修正，使用原始内容: unit={unit_index}")
                        except Exception as db_error:
                            self.logger.warning(f"[整章生成-知识图谱] 读取修正后内容失败: {db_error}，使用原始内容")

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
