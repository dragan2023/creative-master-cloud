"""
content_pipeline - 直接生成模式模块

包含 ContentPipelineMixin._process_unit_direct() 方法。
直接生成整章内容（跳过场景拆解）。

@date: 2026-04-24
@version: v3.0.0
"""
import os as _os
import re
import time
from collections import Counter
from typing import Any, Dict, Optional

from sqlalchemy import select as _select

from app.agents.writing.base_agent import AgentContext, AgentResult, AgentRole
from app.models.writing_scene import WritingScene, SceneStatus
from app.models.writing_unit import UnitStatus
from app.agents.writing.orchestrator_agent.content_pipeline._outline_alignment import check_outline_alignment
from app.utils.type_adapter import safe_json_dict, safe_json_list


def _rule_based_hints(content: str, unit_index: int, content_type: str) -> list:
    """轻量级规则引擎实时提示（v4.0新增）

    替代传统自动质控，为剧本类型提供非阻塞的写作提示。
    仅检测客观格式问题，不涉及内容质量判断。

    Args:
        content: 生成的内容
        unit_index: 单元序号
        content_type: 内容类型 (series_script / movie_script)

    Returns:
        list: 提示列表，每个元素为 {"type": "warning"|"info", "message": str}
    """
    hints = []

    if not content:
        return hints

    word_count = len(content)

    # 1. 字数范围检测
    if word_count < 500:
        hints.append({
            "type": "warning",
            "message": f"单元{unit_index}字数较少（{word_count}字），可能内容不完整，建议检查或使用对话修正补充"
        })
    elif word_count > 20000:
        hints.append({
            "type": "info",
            "message": f"单元{unit_index}字数较多（{word_count}字），如需精简可使用对话修正"
        })

    # 2. 场景分隔标记检测（剧本类型特有）
    if content_type in ("series_script", "movie_script", "script"):
        has_scene_markers = False
        # 常见的场景分隔标记
        scene_patterns = [
            r'场景\s*[\d一二三四五六七八九十]+',  # 场景一、场景1
            r'第[\d一二三四五六七八九十]+\s*场',  # 第1场
            r'\[场景[\d一二三四五六七八九十]*\]',  # [场景1]
            r'\*\*场景',  # **场景
            r'Scene\s+\d+',  # Scene 1
            r'INT\.|EXT\.',  # INT./EXT. (影视剧本格式)
        ]
        for pattern in scene_patterns:
            if re.search(pattern, content):
                has_scene_markers = True
                break

        if not has_scene_markers and word_count > 1000:
            hints.append({
                "type": "info",
                "message": f"单元{unit_index}未检测到明显的场景分隔标记，建议使用场景标记使内容结构更清晰"
            })

    # 3. 格式异常检测
    # 检测连续重复段落（可能是LLM生成异常）
    paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
    if len(paragraphs) > 10:
        para_counts = Counter(paragraphs)
        for para, count in para_counts.items():
            if count > 3 and len(para) > 50:
                hints.append({
                    "type": "warning",
                    "message": f"单元{unit_index}检测到重复段落（重复{count}次），可能存在生成异常，建议检查"
                })
                break

    return hints


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

        # 🔴 防御：确保 orchestrator context 的 config/extra 是 dict
        _ocfg = context.config if isinstance(context.config, dict) else {}
        _oext = context.extra if isinstance(context.extra, dict) else {}

        # 根据内容类型确定单元标签（novel→章, series_script→集, movie_script→场）
        content_type = _ocfg.get("content_type", "novel")
        _unit_label_map = {"novel": "章", "series_script": "集", "movie_script": "场", "script": "场"}
        unit_label = _unit_label_map.get(content_type, "章")
        # 叙事模式检测：三态判断
        _narrative_mode = _ocfg.get("narrative_mode", "serialized")
        _is_pure_episodic = _narrative_mode == "episodic"  # 纯单元剧
        _is_episodic_with_arc = _narrative_mode == "episodic_with_arc"  # 主线串联单元剧
        # 向后兼容：_is_episodic 对两种单元剧模式均返回 True（用于禁用跨集连续性）
        _is_episodic = _is_pure_episodic or _is_episodic_with_arc

        self.logger.info(f"[整{unit_label}生成] 开始处理单元 {unit_index}")
        unit = None

        try:
            # 1. 获取或创建Unit记录
            unit = await self._get_or_create_unit(context, unit_index)
            self.logger.info(f"[整{unit_label}生成] unit_index={unit_index}, unit_title={unit.unit_title}, unit_id={unit.id}")
            unit.status = UnitStatus.PROCESSING
            await self.db.commit()

            if self._check_interrupted():
                self.logger.warning(f"[整{unit_label}生成] 任务被中断: 单元 {unit_index}")
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
                "message": f"单元 {unit_index}: 正在生成整{unit_label}内容...",
                "agent_name": "写手Agent",
                "unit_index": unit_index,
                "icon": "EditPen"
            })

            # 2. 直接调用WriterAgent生成整章内容
            from app.agents.writing.writer_agent import WriterAgent

            writer_agent = self._get_agent(AgentRole.WRITER, WriterAgent)
            words_per_unit = _ocfg.get("words_per_unit", 3000)

            character_state_snapshot = ""
            knowledge_graph_context = ""
            extended_consistency_context = ""
            
            if self._character_tracker:
                # 🆕 [知识图谱优化 v3.1] 分离人物状态和扩展实体配额
                # 人物状态通过 get_state_for_prompt() 获取,无数量限制
                character_state_snapshot = self._character_tracker.get_state_for_prompt(
                    chapter_num=unit_index
                )
                
                # 扩展实体通过 get_knowledge_graph_context_for_writing() 获取,独立配额
                knowledge_graph_context = self._character_tracker.get_knowledge_graph_context_for_writing(
                    chapter_num=unit_index,
                    max_entities=20  # 仅用于扩展实体,人物状态不受此限制
                )
                self.logger.info(f"[整{unit_label}生成] 已获取前文知识图谱参考: 单元 {unit_index}")

            # v2.6: 提取结构化的人物位置和身份映射，供写手提示词使用
            character_location_map = {}
            character_identity_map = {}
            if self._character_tracker:
                try:
                    all_chars = self._character_tracker.get_all_characters()
                    for name, state in all_chars.items():
                        if state.location:
                            character_location_map[name] = state.location
                        if state.identity:
                            character_identity_map[name] = state.identity
                    self.logger.info(
                        f"[整{unit_label}生成] 已提取人物状态映射: "
                        f"location_map={len(character_location_map)}人, "
                        f"identity_map={len(character_identity_map)}人"
                    )
                except Exception as e:
                    self.logger.warning(f"提取人物状态映射失败: {e}")

            # 🆕 [知识图谱优化 v3.1] 获取单元图谱的完整一致性报告
            # 纯单元剧模式：跳过扩展实体一致性上下文获取（各单元独立，无需跨集一致性）
            structured_consistency = {}
            if not _is_pure_episodic and self._project_knowledge_base and context.project_id:
                try:
                    from app.tools.novel_graph_rag import NovelKnowledgeGraph
                    graph_path = self._project_knowledge_base.get_graph_path(
                        context.project_id, unit_index)
                    if graph_path and _os.path.exists(graph_path):
                        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
                        if knowledge_graph.load():
                            extended_consistency_context = knowledge_graph.format_consistency_report_for_prompt(unit_index)
                            # 🆕 同时获取结构化一致性数据，供 writer prompt 步骤6.8-6.14使用
                            raw_report = knowledge_graph.get_consistency_report(unit_index)
                            structured_consistency = {
                                "facilities": safe_json_dict(raw_report.get("facility_states", {}), "facility_states"),
                                "events": safe_json_list(raw_report.get("unfinished_events", []), "unfinished_events"),
                                "groups": safe_json_dict(raw_report.get("group_states", {}), "group_states"),
                                "items": safe_json_dict(raw_report.get("item_ownership", {}), "item_ownership"),
                                "rules": safe_json_list(raw_report.get("active_rules", []), "active_rules"),
                                "time": safe_json_dict(raw_report.get("time_context", {}), "time_context"),
                                "cross_consistency_issues": safe_json_list(raw_report.get("consistency_warnings", []), "consistency_warnings"),
                            }
                            self.logger.info(f"[整{unit_label}生成] 已获取扩展实体一致性上下文: 单元 {unit_index}")
                except Exception as e:
                    self.logger.warning(f"获取扩展实体上下文失败: {e}")
            
            # 🆕 [知识图谱优化 v3.1] 合并知识图谱上下文到单一入口
            # 将 character_state_snapshot, knowledge_graph_context, extended_consistency_context
            # 合并为一个完整的上下文,避免提示词结构混乱
            full_kg_context_parts = []
            
            if character_state_snapshot:
                full_kg_context_parts.append(character_state_snapshot)
            
            if knowledge_graph_context:
                full_kg_context_parts.append(knowledge_graph_context)
            
            if extended_consistency_context:
                full_kg_context_parts.append(extended_consistency_context)
            
            full_kg_context = "\n\n---\n\n".join(full_kg_context_parts) if full_kg_context_parts else ""

            self.logger.info(f"[整{unit_label}生成] 使用全局大纲+单元概述模式: 单元 {unit_index}")

            style_document_features = _ocfg.get("style_document_features", "")
            if style_document_features:
                self.logger.info(f"[整{unit_label}生成] 风格文档特征已加载，长度: {len(style_document_features)}")

            # 🔴 防御：标准化上下文字段，确保 writer 收到的 config/extra/style_guide 永远是 dict
            _safe_writer_config = safe_json_dict(
                {
                    "words_per_scene": words_per_unit,
                    "content_type": _ocfg.get("content_type", "novel"),
                    "style_document_features": style_document_features,
                    "total_units": self._current_task.total_units if self._current_task else 1,
                    **(_ocfg if isinstance(context.config, dict) else {}),
                },
                "writer_context.config"
            )
            _safe_writer_style_guide = safe_json_dict(context.style_guide, "writer_context.style_guide")

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
                style_guide=_safe_writer_style_guide,
                previous_content=context.previous_content,
                character_state_snapshot=character_state_snapshot,
                character_location_map=character_location_map,
                character_identity_map=character_identity_map,
                config=_safe_writer_config,
                extra={
                    "unit_title": unit.unit_title,
                    "unit_summary": unit.unit_summary,
                    "direct_mode": True,
                    # 🆕 [知识图谱优化 v3.1] 使用合并后的完整上下文
                    "knowledge_graph_context": full_kg_context,
                    # 移除 extended_consistency_context (已合并到 knowledge_graph_context)
                    "style_document_features": style_document_features,
                    # 🆕 累积式情节摘要（前文所有单元的关键剧情概览）
                    # 纯单元剧模式下传空字符串；主线串联模式下正常传递
                    "cumulative_summary": "" if _is_pure_episodic else (
                        "\n".join(getattr(self, '_cumulative_summary_parts', [])) if hasattr(self, '_cumulative_summary_parts') and len(self._cumulative_summary_parts) > 1 else ""
                    ),
                    # 🆕 全局大纲对齐报告（每5单元更新一次，注入后续单元写作上下文）
                    # 纯单元剧模式下传空字符串，主线串联和连续剧模式正常传递
                    "alignment_report": "" if _is_pure_episodic else getattr(self, '_alignment_report', ""),
                    # 🆕 待回收伏笔清单（从追踪器获取，注入写手提词）
                    # 纯单元剧模式下传空字符串；主线串联模式下正常传递
                    "pending_foreshadowing": "" if _is_pure_episodic else (
                        self._character_tracker.get_pending_foreshadowing_for_prompt() if self._character_tracker and hasattr(self._character_tracker, 'get_pending_foreshadowing_for_prompt') else ""
                    ),
                    # 🆕 全维度扩展一致性上下文（设施/事件/群体/道具/规则/时间线，供prompt步骤6.8-6.14使用）
                    "extended_consistency": structured_consistency,
                },
            )

            result = await writer_agent.execute(writer_context)

            if self._check_interrupted():
                self.logger.warning(f"[整{unit_label}生成] 任务在写作后被中断: 单元 {unit_index}")
                unit.status = UnitStatus.INTERRUPTED
                await self.db.commit()
                return self._build_error_result(f"任务被中断", completed_units=0, total_units=0)

            if not result.success:
                self.logger.error(f"[整{unit_label}生成] 写作失败: {result.errors}")
                unit.status = UnitStatus.PENDING
                await self.db.commit()
                return self._build_error_result(f"写作失败: {result.errors}")

            # 3. 更新Unit状态
            final_content = result.content
            unit.final_content = final_content
            unit.word_count = len(final_content)
            unit.status = UnitStatus.COMPLETED
            unit.duration_ms = int((time.time() - unit_start_time) * 1000)

            # [v3.0] 保存 LLM 初稿（永不覆盖，供下载对比使用）
            unit.content_after_generation = final_content

            # 创建单个场景记录（用于兼容）
            # [修复] 使用 _get_or_create_scene 避免重复键错误，并更新已有场景内容
            scene = await self._get_or_create_scene(
                unit_id=unit.id,
                scene_index=1,
                scene_data={
                    "scene_title": unit.unit_title or f"场景1",
                    "direct_mode": True
                }
            )
            # 更新场景内容（无论新建还是已存在）
            scene.scene_title = unit.unit_title or f"场景1"
            scene.scene_outline = {"direct_mode": True}
            scene.status = SceneStatus.COMPLETED
            scene.final_content = final_content
            scene.word_count = len(final_content)
            await self.db.commit()
            
            # 同步更新 NovelChapter 表（正文表单显示依赖此表）
            # 使用共享同步函数，确保 NovelChapter 永远存在
            from app.services.novel_writer.chapter_sync import sync_writing_unit_to_novel_chapter
            try:
                await sync_writing_unit_to_novel_chapter(
                    db=self.db,
                    project_id=context.project_id,
                    unit_index=unit_index,
                    final_content=final_content,
                    unit_title=getattr(unit, 'unit_title', '') or "",
                    logger=self.logger,
                    content_type=_ocfg.get("content_type", "novel")
                )
            except Exception as sync_error:
                self.logger.error(
                    f"[整{unit_label}生成-单元{unit_index}] NovelChapter 同步失败（内容已保存到WritingUnit，但正文表单可能无法显示）: {sync_error}",
                    exc_info=True
                )

            # 🆕 自动生成章节摘要（供质控分析 ±N章上下文机制使用）
            # 非阻塞：失败不影响主流程
            try:
                from sqlalchemy import select
                from app.models.novel_chapter import NovelChapter
                chapter_query = select(NovelChapter).where(
                    NovelChapter.project_id == context.project_id,
                    NovelChapter.chapter_number == unit_index
                )
                chapter_result = await self.db.execute(chapter_query)
                chapter = chapter_result.scalar_one_or_none()
                if chapter and chapter.id:
                    from app.services.quality_control.summary_generator import generate_and_store_chapter_summary
                    import asyncio as _asyncio_summary
                    _summary_user_id = context.user_id if context.user_id else (
                        self._current_task.user_id if self._current_task else None
                    )
                    _asyncio_summary.ensure_future(
                        generate_and_store_chapter_summary(
                            db=self.db,
                            chapter_id=chapter.id,
                            chapter_content=final_content,
                            user_id=_summary_user_id
                        )
                    )
            except Exception as summary_error:
                self.logger.warning(
                    f"[整{unit_label}生成-单元{unit_index}] 摘要生成调度失败（不影响主流程）: {summary_error}"
                )

            # v4.0优化：实时质控仅对小说类型生效，剧集/电影类型跳过
            # 剧集/电影类型的质量反馈由用户通过对话修正功能完成
            qc_completed = False
            if _ocfg.get("content_type", "novel") == "novel":
                import asyncio as _asyncio
                from app.agents.writing.orchestrator_agent.quality_control_trigger import trigger_unit_quality_control

                project_id = None
                user_id = None
                if self._current_task:
                    project_id = self._current_task.project_id
                    user_id = self._current_task.user_id

                if project_id and final_content:
                    try:
                        if not hasattr(self, '_qc_semaphore'):
                            self._qc_semaphore = _asyncio.Semaphore(2)

                        async with self._qc_semaphore:
                            self.logger.info(f"[整{unit_label}生成-质控] 开始质控: unit={unit_index}, 等待完成后再提取知识图谱")
                            await trigger_unit_quality_control(
                                project_id=project_id,
                                unit_index=unit_index,
                                content=final_content,
                                user_id=user_id,
                                ws_send_func=self._send_ws_message,
                                content_type=_ocfg.get("content_type", "novel")
                            )
                            qc_completed = True
                            self.logger.info(f"[整{unit_label}生成-质控] 质控完成: unit={unit_index}")
                    except Exception as qc_error:
                        self.logger.warning(f"[整{unit_label}生成-质控] 质控失败: unit={unit_index}, error={qc_error}，继续执行知识图谱提取")
                        qc_completed = False
            else:
                self.logger.info(
                    f"[整{unit_label}生成] 剧本类型({_ocfg.get('content_type')})跳过实时质控，"
                    f"unit={unit_index}，由用户对话修正功能替代")

                # v4.0新增: 轻量级规则引擎实时提示（替代传统自动质控）
                try:
                    hints = _rule_based_hints(
                        content=final_content,
                        unit_index=unit_index,
                        content_type=content_type
                    )
                    if hints:
                        self.logger.info(
                            f"[整{unit_label}生成-规则提示] unit={unit_index}, "
                            f"发现{len(hints)}条提示"
                        )
                        await self._send_ws_message("writing_hints", {
                            "unit_index": unit_index,
                            "hints": hints
                        })
                except Exception as hint_error:
                    self.logger.warning(
                        f"[整{unit_label}生成-规则提示] 规则引擎检测失败（不影响主流程）: {hint_error}"
                    )

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
                "message": f"单元 {unit_index}: 整{unit_label}内容生成完成，共 {len(final_content)} 字",
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

            # 4.5 🆕 累积式情节摘要更新
            # 在人物状态追踪之前更新，用于后续单元的前文参考
            if not hasattr(self, '_cumulative_summary_parts'):
                self._cumulative_summary_parts = []
            unit_title_text = unit.unit_title or f"第{unit_index}单元"
            unit_summary_text = unit.unit_summary or ""
            summary_entry = f"第{unit_index}{unit_label}《{unit_title_text}》：{unit_summary_text[:300]}"
            self._cumulative_summary_parts.append(summary_entry)
            # 最多保留最近50个单元的摘要，避免token膨胀
            if len(self._cumulative_summary_parts) > 50:
                self._cumulative_summary_parts = self._cumulative_summary_parts[-50:]
            self.logger.debug(f"[整{unit_label}生成] 累积摘要已更新，当前{len(self._cumulative_summary_parts)}个单元")

            # 4.6 🆕 全局大纲对齐验证
            # 纯单元剧模式：跳过大纲对齐检查
            if not _is_pure_episodic and unit_index % 5 == 0 and self._cumulative_summary_parts:
                try:
                    # 尝试获取LLM provider（优先从context.extra，回退到提取专用provider）
                    alignment_llm = None
                    if _oext:
                        alignment_llm = _oext.get('llm_provider')
                    if alignment_llm is None and hasattr(self, '_get_llm_provider_for_extraction'):
                        alignment_llm = await self._get_llm_provider_for_extraction()

                    if alignment_llm and context.global_context:
                        global_outline_text = context.global_context
                        if isinstance(global_outline_text, dict):
                            global_outline_text = global_outline_text.get("outline", str(global_outline_text))

                        alignment_report = await check_outline_alignment(
                            global_outline=str(global_outline_text),
                            generated_summaries=list(self._cumulative_summary_parts),
                            llm_provider=alignment_llm,
                            interval=5,
                            logger=self.logger
                        )

                        if alignment_report:
                            if not hasattr(self, '_alignment_report'):
                                self._alignment_report = ""
                            self._alignment_report = alignment_report
                            self.logger.info(f"[整{unit_label}生成] 大纲对齐报告已更新: 单元{unit_index}")
                except Exception as e:
                    self.logger.warning(f"[整{unit_label}生成] 大纲对齐检查失败: {e}")

            # 5. 更新人物状态追踪
            # 纯单元剧模式：跳过人物状态追踪（各单元完全独立）
            if not _is_pure_episodic and self._character_tracker and final_content:
                try:
                    content_for_kg = final_content
                    if qc_completed:
                        try:
                            from app.models.writing_unit import WritingUnit
                            # 质控在独立session中commit了status/final_content更新，
                            # 当前session的identity map中仍缓存着旧对象，
                            # 先保存PK再expire，避免expire后访问unit.id触发greenlet懒加载
                            _saved_unit_id = unit.id
                            self.db.expire(unit)
                            unit_query = _select(WritingUnit).where(
                                WritingUnit.id == _saved_unit_id
                            )
                            unit_result = await self.db.execute(unit_query)
                            refreshed_unit = unit_result.scalar_one_or_none()

                            if refreshed_unit and refreshed_unit.quality_control_status == 'completed' and refreshed_unit.final_content:
                                content_for_kg = refreshed_unit.final_content
                                self.logger.info(f"[整{unit_label}生成-知识图谱] 使用质控修正后的内容: unit={unit_index}, 原文{len(final_content)}字符 -> 修正后{len(content_for_kg)}字符")
                            else:
                                self.logger.info(f"[整{unit_label}生成-知识图谱] 质控状态: {refreshed_unit.quality_control_status if refreshed_unit else 'None'}")
                                self.logger.info(f"[整{unit_label}生成-知识图谱] 质控未完成或无修正，使用原始内容: unit={unit_index}")
                        except Exception as db_error:
                            self.logger.warning(f"[整{unit_label}生成-知识图谱] 读取修正后内容失败: {db_error}，使用原始内容")

                    llm_provider = None
                    if _oext:
                        llm_provider = _oext.get('llm_provider')

                    await self._update_character_states(
                        chapter_num=unit_index,
                        chapter_title=unit.unit_title,
                        content=content_for_kg,
                        project_id=context.project_id,
                        llm_provider=llm_provider,
                        narrative_mode=_narrative_mode
                    )
                except Exception as e:
                    self.logger.warning(f"更新人物状态失败: {e}")

            # 5.5 🆕 伏笔追踪同步
            # 纯单元剧模式：跳过伏笔追踪（各单元独立，无跨集伏笔）
            if not _is_pure_episodic and self._character_tracker and final_content and hasattr(self._character_tracker, 'sync_foreshadowing_from_knowledge_graph'):
                try:
                    # 尝试获取知识图谱实例
                    knowledge_graph = None
                    if self._project_knowledge_base and context.project_id:
                        graph_path = self._project_knowledge_base.get_graph_path(
                            context.project_id, unit_index)
                        if graph_path and _os.path.exists(graph_path):
                            from app.tools.novel_graph_rag import NovelKnowledgeGraph
                            knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
                            if knowledge_graph.load():
                                self.logger.debug(f"[伏笔追踪] 加载知识图谱: 单元{unit_index}")

                    # 同步伏笔数据
                    self._character_tracker.sync_foreshadowing_from_knowledge_graph(
                        knowledge_graph=knowledge_graph,
                        chapter_num=unit_index
                    )

                    # 检测当前章节是否回收了pending伏笔
                    self._character_tracker.detect_foreshadowing_resolution(
                        content=final_content,
                        chapter_num=unit_index
                    )
                except Exception as e:
                    self.logger.warning(f"[伏笔追踪] 同步失败: {e}")

            # 5.6 🆕 扩展实体交叉一致性检查
            # 纯单元剧模式：跳过交叉一致性检查（各单元独立）
            if not _is_pure_episodic and self._character_tracker and final_content and hasattr(self._character_tracker, 'check_extended_consistency'):
                try:
                    # 加载一致性状态（consistency_state.json）
                    consistency_state = {}
                    if self._project_knowledge_base and context.project_id:
                        graph_path = self._project_knowledge_base.get_graph_path(
                            context.project_id, unit_index)
                        if graph_path:
                            graph_dir = _os.path.dirname(graph_path)
                            from app.agents.writing.orchestrator_agent.monitoring._knowledge_graph import MonitoringKnowledgeGraphMixin
                            consistency_state = MonitoringKnowledgeGraphMixin.load_unified_state(graph_dir, context.project_id)

                    cross_result = self._character_tracker.check_extended_consistency(
                        chapter_num=unit_index,
                        content=final_content,
                        consistency_state=consistency_state,
                        context_accumulator=getattr(self, '_context_accumulator', None)
                    )

                    if cross_result:
                        cross_issues = cross_result.get("issues", [])
                        cross_warnings = cross_result.get("warnings", [])
                        all_cross = cross_issues + cross_warnings
                        if all_cross:
                            # 将交叉一致性问题合并到 writer context 的 extended_consistency 中
                            structured_consistency["cross_consistency_issues"] = (
                                structured_consistency.get("cross_consistency_issues", []) + all_cross
                            )
                            self.logger.info(
                                f"[交叉一致性] 单元{unit_index}: "
                                f"发现{len(cross_issues)}个冲突, {len(cross_warnings)}个警告"
                            )

                            # 发送交叉一致性通知到前端
                            await self._send_websocket_message(context.task_id, {
                                "type": "cross_consistency_check",
                                "status": "completed",
                                "message": f"交叉一致性检查完成: {len(cross_issues)}个冲突, {len(cross_warnings)}个警告",
                                "unit_index": unit_index,
                                "issues": [{"type": i.get("type", ""), "message": i.get("message", "")} for i in cross_issues],
                                "warnings": [{"type": w.get("type", ""), "message": w.get("message", "")} for w in cross_warnings],
                                "icon": "WarningFilled"
                            })
                except Exception as e:
                    self.logger.warning(f"[交叉一致性] 检查失败: {e}")

            duration_ms = int((time.time() - unit_start_time) * 1000)
            self.logger.info(f"[整{unit_label}生成] 单元 {unit_index} 处理完成，耗时 {duration_ms}ms")

            return self._build_success_result(
                content=final_content,
                duration_ms=duration_ms,
                unit_index=unit_index,
                scene_count=1
            )

        except Exception as e:
            self.logger.exception(f"[整{unit_label}生成] 处理单元 {unit_index} 时发生异常: {str(e)}")
            if unit:
                unit.status = UnitStatus.INTERRUPTED
                await self.db.commit()
            return self._build_error_result(f"单元处理异常: {str(e)}")
