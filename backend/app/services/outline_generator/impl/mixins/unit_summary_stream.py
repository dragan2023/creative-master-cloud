"""大纲生成器 - 单元概述流式生成Mixin"""
from typing import AsyncGenerator
from typing import Dict
from typing import Any
import re
from app.services.outline_generator.api.constants import ENABLE_QUALITY_CONTROL


class UnitSummaryStreamMixin:
    """单元概述流式生成"""

    async def generate_unit_summaries_stream(
        self,
        global_outline: str,
        unit_count: int,
        content_type: str,
        series_type: str = None,
        episode_duration_range: str = None,
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_quality_control: bool = True,
        qc_mode: str = "manual",  # 新增: 质控模式 (manual/auto)
        cancel_event=None,
        # 续生成参数
        existing_content: str = "",
        existing_parsed: Dict[str, Dict[str, Any]] = None,
        start_from_unit: int = 1,
        # 标题风格参数（新增）
        title_style: str = None,
        title_style_name: str = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成单元简要概述（第二阶段）

        支持续生成模式和后置分层质量管控：
        - workflow 事件：通知前端当前执行步骤
        - content 事件：流式输出内容
        - replace_content 事件：质量修正后替换内容

        Args:
            global_outline: 全局大纲内容
            unit_count: 单元数量
            content_type: 内容类型
            series_type: 剧本类型
            episode_duration_range: 每集时长区间
            provider: LLM提供商
            model: 模型名称
            temperature: 温度参数
            user_id: 用户ID
            enable_quality_control: 是否启用质量管控
            cancel_event: 取消事件对象（用于中断生成）
            existing_content: 已生成的内容（续生成时使用）
            existing_parsed: 已解析的单元数据（续生成时使用）
            start_from_unit: 从第几章开始续生成（默认1表示全新生成）
            title_style: 标题风格ID
            title_style_name: 标题风格名称

        Yields:
            SSE 事件字符串
        """
        try:
            # 检测是否为续生成模式
            is_resume = bool(
                existing_content and existing_parsed and start_from_unit > 1)

            if is_resume:
                self.logger.info(
                    f"[单元概述续生成] 检测到续生成模式: "
                    f"已有{len(existing_parsed)}章, 从第{start_from_unit}章开始, "
                    f"目标{unit_count}章"
                )
                yield self._format_sse("workflow", {
                    "type": "step", "step": "resume_detection", "status": "done",
                    "message": f"检测到续生成模式，从第{start_from_unit}章继续生成至第{unit_count}章",
                    "icon": "RefreshRight"
                })

            # 确定模块名称
            module_name = f"{content_type}_unit_summaries"

            # 构建输入参数（区分续生成和全新生成）
            if is_resume:
                # 续生成模式：构建续生成上下文
                context_prefix = self._build_resume_context(
                    existing_parsed=existing_parsed,
                    start_from_unit=start_from_unit,
                    content_type=content_type
                )

                filled_prompt = self._build_resume_prompt(
                    module_name=module_name,
                    global_outline=global_outline,
                    context_prefix=context_prefix,
                    start_from_unit=start_from_unit,
                    unit_count=unit_count,
                    content_type=content_type,
                    series_type=series_type,
                    episode_duration_range=episode_duration_range,
                    title_style=title_style,  # 传递标题风格参数
                    title_style_name=title_style_name  # 传递标题风格名称
                )

                units_to_generate = unit_count - start_from_unit + 1
                self.logger.info(
                    f"[单元概述流式] 续生成模式，将生成第{start_from_unit}-{unit_count}章，"
                    f"共{units_to_generate}章"
                )
            else:
                # 全新生成模式
                input_params = {
                    "global_outline": global_outline,
                    "chapter_count": str(unit_count),
                    "episode_count": str(unit_count),
                    "series_type": series_type or "网剧",
                    "episode_duration_range": episode_duration_range or "30-45分钟"
                }

                # 生成标题风格指导文本（新增）
                if content_type == "novel" and title_style:
                    from app.agents.writing.prompts.title_style_guidance import get_title_style_guidance
                    title_style_guidance = get_title_style_guidance(
                        title_style, title_style_name or "")
                    input_params["title_style_guidance"] = title_style_guidance
                    self.logger.info(
                        f"[单元概述流式] 使用标题风格: {title_style_name} ({title_style})")
                else:
                    input_params["title_style_guidance"] = ""

                # 获取提示词模板（使用默认模板，不需要数据库）
                prompt_template = self.prompt_manager.get_default_prompt(
                    module_name)
                if not prompt_template:
                    raise ValueError(f"未找到提示词模板: {module_name}")

                # 渲染提示词（填充变量）
                filled_prompt = self.prompt_manager.render_prompt(
                    prompt_template, input_params, module_name
                )
                units_to_generate = unit_count

            self.logger.info(
                f"[单元概述流式] 开始生成，模块: {module_name}，单元数: {units_to_generate}")

            # 发送开始生成的工作流事件
            yield self._format_sse("workflow", {
                "type": "step", "step": "generate", "status": "running",
                "message": f"正在生成第{start_from_unit}-{unit_count}章概述..." if is_resume else f"正在生成{unit_count}个单元概述...",
                "icon": "MagicStick"
            })

            # 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(
                self.db, user_id, provider
            )
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            self.logger.info(
                f"[单元概述流式] 使用LLM提供商: {llm_provider.get_model_info()['provider']}")

            self.logger.info(
                f"[单元概述流式] 开始生成 {units_to_generate} 个单元概述，不设置token上限")

            # 流式调用LLM生成（不传递max_tokens，让LLM自主控制输出长度）
            # 提示词中已包含完整性保障指令：LLM接近token上限时必须提前结束并确保最后单元完整
            new_content_chunks = []
            async for chunk in llm_provider.generate_stream(
                prompt=filled_prompt,
                temperature=temperature
            ):
                # 检查是否被取消
                if cancel_event and cancel_event.is_set():
                    self.logger.info("[单元概述流式] 生成被取消")
                    # 发送取消事件
                    yield self._format_sse("workflow", {
                        "type": "cancelled", "message": "生成已取消"
                    })
                    break

                # 使用 SSE 格式包装内容
                if hasattr(chunk, 'content'):
                    new_content_chunks.append(chunk.content)
                    yield self._format_sse("content", {"text": chunk.content})
                elif isinstance(chunk, str):
                    new_content_chunks.append(chunk)
                    yield self._format_sse("content", {"text": chunk})

            # 发送生成完成的工作流事件
            yield self._format_sse("workflow", {
                "type": "step", "step": "generate", "status": "done",
                "message": f"第{start_from_unit}-{unit_count}章概述生成完成" if is_resume else "单元概述生成完成",
                "icon": "MagicStick"
            })

            # ==================== 合并内容 ====================
            new_content = ''.join(new_content_chunks)

            if is_resume:
                # 续生成模式：合并已有内容和新生成内容
                unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
                    content_type, "章"
                )
                full_content = existing_content + "\n\n" + new_content

                # 解析新生成的章节
                # 注意：expected_count 必须使用 unit_count（总目标章节数），而非 units_to_generate
                # 因为 _parse_novel_chapters 使用 expected_count 判断是否为最后一章（end_marker=None），
                # 如果传入 units_to_generate（如25），而章节号从26开始（都>25），
                # 则所有章节都会被当作最后一章处理，导致 full_content 越界截取
                new_parsed = self.parse_unit_summaries(
                    new_content,
                    unit_count,
                    content_type
                )

                # 为新生成的章节添加续生成标记
                # 注意：LLM已经生成了正确的绝对章节号（第51-100章），不需要调整
                adjusted_new_parsed = {}
                skipped_duplicates = []
                out_of_range = []

                for unit_num, data in new_parsed.items():
                    unit_num_int = int(unit_num)

                    # 防御性检查1：跳过已存在的章节号（LLM意外重复生成）
                    if unit_num_int < start_from_unit:
                        skipped_duplicates.append(unit_num_int)
                        self.logger.warning(
                            f"[单元概述续生成] 跳过重复章节: 第{unit_num_int}{unit_label}"
                        )
                        continue

                    # 防御性检查2：跳过超出目标范围的章节号
                    if unit_num_int > unit_count:
                        out_of_range.append(unit_num_int)
                        self.logger.warning(
                            f"[单元概述续生成] 跳过超范围章节: 第{unit_num_int}{unit_label}（目标上限{unit_count}）"
                        )
                        continue

                    adjusted_new_parsed[unit_num] = {
                        **data,
                        "is_resumed": True  # 标记为续生成
                    }

                # 合并已解析的和新生成的（已有章节不会被覆盖）
                full_parsed = {**existing_parsed, **adjusted_new_parsed}

                # 合并后完整性验证日志
                if skipped_duplicates:
                    self.logger.warning(
                        f"[单元概述续生成] 跳过了{len(skipped_duplicates)}个重复章节: "
                        f"{skipped_duplicates[:5]}{'...' if len(skipped_duplicates) > 5 else ''}"
                    )
                if out_of_range:
                    self.logger.warning(
                        f"[单元概述续生成] 跳过了{len(out_of_range)}个超范围章节: "
                        f"{out_of_range[:5]}{'...' if len(out_of_range) > 5 else ''}"
                    )

                self.logger.info(
                    f"[单元概述续生成] 合并完成: 已有{len(existing_parsed)}章 + "
                    f"新生成{len(adjusted_new_parsed)}章 = 总计{len(full_parsed)}章"
                )

                # 验证合并后章节连续性
                expected_total = unit_count
                if len(full_parsed) < expected_total:
                    self.logger.warning(
                        f"[单元概述续生成] 合并后章节数({len(full_parsed)})"
                        f"少于预期({expected_total})，可能需要再次续生成"
                    )
            else:
                # 全新生成模式
                full_content = new_content
                full_parsed = self.parse_unit_summaries(
                    full_content, unit_count, content_type
                )

            # ==================== 截断检测(已禁用) ====================
            # 注意: 截断检测已禁用,现在使用分段生成机制替代
            # expected_count = self.get_expected_unit_count(...)
            # truncation_info = self.detect_truncated_units(...)

            # 记录截断信息为空(保持兼容性)
            # 不再发送truncation_detected事件

            # self.logger.info(
            #     f"[单元概述流式] 截断检测已禁用,使用分段生成机制"
            # )

            # ==================== 后置分层质量管控 ====================
            # 根据qc_mode参数决定是否执行质控
            if ENABLE_QUALITY_CONTROL and enable_quality_control and full_parsed:
                if qc_mode == "auto":
                    # 自动模式: 执行质控检测与修正
                    self.logger.info("[单元概述流式] 自动模式: 开始自动质控检测与修正...")
                    # 注意：_perform_layered_quality_control 是异步生成器，需要使用 async for 迭代
                    async for qc_event in self._perform_layered_quality_control(
                        full_parsed=full_parsed,
                        global_outline=global_outline,
                        content_type=content_type,
                        is_resume=is_resume,
                        new_units_start=start_from_unit if is_resume else None,
                        llm_provider=llm_provider,
                        temperature=temperature,
                        workflow_yield=lambda event: event,
                        replace_content_yield=lambda content, msg: (
                            content, msg),
                        user_id=user_id
                    ):
                        # 处理质量管控产生的事件
                        if isinstance(qc_event, tuple):
                            # replace_content 事件
                            content, msg = qc_event
                            yield self._format_sse("replace_content", {
                                "content": content,
                                "message": msg
                            })
                        else:
                            # workflow 事件
                            yield self._format_sse("workflow", qc_event)

                elif qc_mode == "manual":
                    # 手动模式: 跳过自动质控,等待用户手动触发
                    self.logger.info("[单元概述流式] 手动模式: 跳过自动质控,等待用户手动触发")

            # 发送质控提示信息
            yield self._format_sse("workflow", {
                "type": "qc_hint",
                "message": "质控检测已改为手动触发，请在生成完成后点击'质量检测'按钮"
            })

            # 发送完成事件
            yield self._format_sse("workflow", {"type": "complete"})

        except Exception as e:
            self.logger.error(f"[单元概述流式] 生成失败: {str(e)}")
            yield self._format_sse("workflow", {
                "type": "error", "message": f"生成失败: {str(e)}"
            })


