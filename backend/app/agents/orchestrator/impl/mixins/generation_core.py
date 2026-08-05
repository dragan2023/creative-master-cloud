"""Agent编排器 - 生成核心流程（加载LLM、初稿、评估修正、保存）Mixin"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from typing import Optional
import re
import os
import time
import asyncio
import base64
from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory
from app.agents.orchestrator.api import get_model_friendly_name, convert_images_to_base64, GenerateStreamContext
from app.core.config import get_settings


class GenerationCoreMixin:
    """生成核心流程（加载LLM、初稿、评估修正、保存）"""

    async def _load_llm_provider(
        self,
        db: AsyncSession,
        user_id: int,
        provider: Optional[str] = None
    ) -> tuple:
        """
        加载LLM提供者

        Args:
            db: 数据库会话
            user_id: 用户ID
            provider: 指定的提供者名称

        Returns:
            (llm_provider, model_display_name) 元组
        """
        llm_provider = await self.llm_manager.get_provider_from_db(
            db=db,
            user_id=user_id,
            provider_name=provider
        )
        model_display_name = get_model_friendly_name(
            llm_provider.get_model_info()["provider"],
            llm_provider.model_name
        )
        return llm_provider, model_display_name


    async def _generate_first_draft(
        self,
        ctx: GenerateStreamContext,
        db: AsyncSession,
        user_id: int,
        module: str,
        temperature: float,
        cancel_event: Optional[asyncio.Event],
        logger
    ) -> AsyncGenerator[str, None]:
        """
        生成初稿内容

        Yields:
            SSE 格式的事件字符串
        """
        logger.info(
            f"开始流式生成 - 模块: {module}, 模型: {ctx.llm_provider.model_name}")

        # 转换图片URL为base64格式
        converted_images = convert_images_to_base64(ctx.converted_images)
        if converted_images:
            logger.info(f"已转换 {len(converted_images)} 张图片为base64格式")
        ctx.converted_images = converted_images

        # 处理视频URL
        if ctx.videos:
            logger.info(f"接收到 {len(ctx.videos)} 个视频URL: {ctx.videos}")

        yield self._format_sse("workflow", {"type": "step", "step": "generate", "status": "running", "message": "正在生成初稿内容...", "icon": "ChatDotRound"})

        # 获取模型支持的最大输出 token，并设置安全上限
        safe_output_limit = min(
            ctx.llm_provider.get_max_output_tokens(), get_settings().MAX_LLM_OUTPUT_TOKENS)
        logger.info(f"初次回答生成 - max_tokens: {safe_output_limit}")

        first_draft_content = []
        try:
            stream = ctx.llm_provider.generate_stream(
                prompt=ctx.full_prompt,
                system_prompt=ctx.system_prompt,
                temperature=temperature,
                max_tokens=safe_output_limit,
                images=converted_images,
                videos=ctx.videos
            )

            async for chunk in stream:
                if cancel_event and cancel_event.is_set():
                    logger.info(f"用户 {user_id} 取消了生成任务")
                    yield self._format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                    return

                first_draft_content.append(chunk)
                yield self._format_sse("content", {"text": chunk})

        except Exception as stream_error:
            logger.exception(f"流式生成异常: {stream_error}")
            yield self._format_sse("workflow", {"type": "error", "message": f"生成过程出错: {str(stream_error)}"})
            return

        yield self._format_sse("workflow", {"type": "step", "step": "generate", "status": "done", "message": "初稿内容生成完成"})

        # 更新上下文
        ctx.first_draft = "".join(first_draft_content)
        ctx.final_content = ctx.first_draft


    async def _evaluate_and_revise(
        self,
        ctx: GenerateStreamContext,
        db: AsyncSession,
        user_id: int,
        module: str,
        enable_knowledge: bool,
        temperature: float,
        cancel_event: Optional[asyncio.Event],
        logger,
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        评估和修正内容

        流程：
        1. 通用知识库修正（默认启用，当enable_knowledge=True时）
        2. 根据用户选择叠加垂直领域、用户专属、官方手册知识库修正
        3. 自反思机制评估和修正
        4. 自洽性检查

        Yields:
            SSE 格式的事件字符串
        """
        # 知识库评估与修正
        if enable_knowledge and (ctx.kb_contexts["theory"].strip() or ctx.kb_contexts["case"].strip() or ctx.kb_contexts["user_specific"].strip() or ctx.kb_contexts["manual"].strip()):
            yield self._format_sse("workflow", {"type": "step", "step": "evaluate", "status": "running", "message": "智能体正在评估内容质量...", "icon": "DataAnalysis"})

            if cancel_event and cancel_event.is_set():
                logger.info(f"用户 {user_id} 在评估阶段取消了生成任务")
                yield self._format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                return

            evaluation_result = await self._evaluate_with_llm(
                llm_provider=ctx.llm_provider,
                first_answer=ctx.first_draft,
                kb_contexts=ctx.kb_contexts,
                input_params=ctx.input_params
            )

            if evaluation_result.get("needs_revision"):
                issue_count = len(evaluation_result.get("theory_issues", [])) + \
                    len(evaluation_result.get("case_insights", [])) + \
                    len(evaluation_result.get("user_specific_issues", [])) + \
                    len(evaluation_result.get("compliance_issues", []))
                yield self._format_sse("workflow", {"type": "step", "step": "evaluate", "status": "done", "message": f"检测到可优化点：{issue_count}处"})

                if cancel_event and cancel_event.is_set():
                    logger.info(f"用户 {user_id} 在修正阶段取消了生成任务")
                    yield self._format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
                    return

                yield self._format_sse("workflow", {"type": "step", "step": "revise", "status": "running", "message": "正在优化内容...", "icon": "Edit"})

                revised_content = await self._generate_revised_content(
                    llm_provider=ctx.llm_provider,
                    original_content=ctx.first_draft,
                    evaluation_result=evaluation_result,
                    kb_contexts=ctx.kb_contexts,
                    system_prompt=ctx.system_prompt,
                    temperature=temperature,
                    input_params=ctx.input_params,
                    cancel_event=cancel_event
                )

                if revised_content:
                    yield self._format_sse("content", {"text": "\n\n---\n\n### 🔄 基于知识库的优化建议\n\n"})
                    yield self._format_sse("content", {"text": revised_content})
                    ctx.final_content = ctx.first_draft + \
                        "\n\n---\n\n### 🔄 基于知识库的优化建议\n\n" + revised_content

                yield self._format_sse("workflow", {"type": "step", "step": "revise", "status": "done", "message": "内容优化完成"})
            else:
                yield self._format_sse("workflow", {"type": "step", "step": "evaluate", "status": "done", "message": "知识库验证通过"})

        # 自洽性检查
        yield self._format_sse("workflow", {"type": "step", "step": "consistency", "status": "running", "message": "执行自洽性检查...", "icon": "CircleCheck"})

        if cancel_event and cancel_event.is_set():
            logger.info(f"用户 {user_id} 在自洽性检查阶段取消了生成任务")
            yield self._format_sse("workflow", {"type": "error", "message": "生成任务已被用户取消"})
            return

        consistency_result = await self._check_self_consistency(
            llm_provider=ctx.llm_provider,
            content=ctx.first_draft,
            input_params=ctx.input_params,
            module=module,
            temperature=temperature
        )

        if consistency_result.get("issues"):
            issues_count = len(consistency_result.get("issues", []))
            yield self._format_sse("workflow", {"type": "step", "step": "consistency", "status": "done", "message": f"自洽性检查完成，发现{issues_count}处问题"})

            if consistency_result.get("needs_fix"):
                fix_content = await self._auto_fix_issues(
                    llm_provider=ctx.llm_provider,
                    original_content=ctx.first_draft,
                    consistency_result=consistency_result,
                    temperature=temperature
                )
                if fix_content:
                    yield self._format_sse("content", {"text": "\n\n---\n\n### 🤖 Agent修正建议\n\n"})
                    yield self._format_sse("content", {"text": fix_content})
                    ctx.final_content = ctx.first_draft + \
                        "\n\n---\n\n### 🤖 Agent修正建议\n\n" + fix_content
        else:
            yield self._format_sse("workflow", {"type": "step", "step": "consistency", "status": "done", "message": "自洽性检查通过"})


    async def _save_and_complete(
        self,
        ctx: GenerateStreamContext,
        db: AsyncSession,
        user_id: int,
        logger,
        module: Optional[str] = None,
        generation_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        保存生成记录并发送完成事件

        [2026-08-04] 修复历史记录重复与模块类型错误：
        - 不再新建第二条生成记录，而是更新流式端点预先创建的同一条记录，
          保证"一次生成 = 一条历史记录"。
        - 模块类型显式传入（module），不再从 input_params 里取，
          避免所有模块被默认落库为 short_video。

        Args:
            ctx: 生成上下文
            db: 数据库会话
            user_id: 用户ID
            logger: 日志器
            module: 模块名称（与 GenerationModule 枚举值一致）
            generation_id: 已存在的生成记录ID（流式端点预先创建），为空时新建

        Yields:
            SSE 格式的事件字符串
        """
        # 添加专业标识
        yield self._format_sse("content", {"text": "\n\n---\n\n✨ *该方案已经过全能创意大师智能验证与优化*"})
        ctx.final_content += "\n\n---\n\n✨ *该方案已经过全能创意大师智能验证与优化*"

        # 保存生成记录到数据库（优先更新已存在的记录，避免重复）
        saved_generation_id = None
        try:
            title = None
            if ctx.input_params:
                title_keys = ['title', 'topic', 'theme', 'subject', 'name']
                for key in title_keys:
                    if key in ctx.input_params and ctx.input_params[key]:
                        title = str(ctx.input_params[key])[:200]
                        break

            module_enum = GenerationModule(module) if module else None

            if generation_id is not None:
                # 更新流式端点预先创建的记录（单记录生命周期）
                generation = await db.get(Generation, generation_id)
                if generation is None:
                    # 记录已被删除等异常情况：回退为新建
                    generation = Generation(
                        user_id=user_id,
                        module=module_enum or GenerationModule.SHORT_VIDEO,
                        status=GenerationStatus.COMPLETED,
                        input_params=ctx.input_params,
                        title=title,
                        output_content=ctx.final_content,
                        provider=ctx.llm_provider.get_model_info()["provider"],
                        model_name=ctx.llm_provider.model_name,
                        duration_ms=int((time.time() - ctx.start_time) * 1000)
                    )
                    db.add(generation)
                else:
                    if module_enum is not None:
                        generation.module = module_enum
                    generation.status = GenerationStatus.COMPLETED
                    generation.input_params = ctx.input_params
                    generation.title = title
                    generation.output_content = ctx.final_content
                    generation.provider = ctx.llm_provider.get_model_info()["provider"]
                    generation.model_name = ctx.llm_provider.model_name
                    generation.duration_ms = int((time.time() - ctx.start_time) * 1000)
                    db.add(generation)
            else:
                generation = Generation(
                    user_id=user_id,
                    module=module_enum or GenerationModule.SHORT_VIDEO,
                    status=GenerationStatus.COMPLETED,
                    input_params=ctx.input_params,
                    title=title,
                    output_content=ctx.final_content,
                    provider=ctx.llm_provider.get_model_info()["provider"],
                    model_name=ctx.llm_provider.model_name,
                    duration_ms=int((time.time() - ctx.start_time) * 1000)
                )
                db.add(generation)

            await db.commit()
            saved_generation_id = generation.id
            logger.info(
                f"生成记录已保存 - ID: {generation.id}, 模块: {generation.module}, "
                f"标题: {title}, 是否为更新: {generation_id is not None}")
        except Exception as save_error:
            logger.exception("保存生成记录失败")
            await db.rollback()

        # 发送完成事件
        duration_ms = int((time.time() - ctx.start_time) * 1000)
        logger.info(f"流式生成完成 - 耗时: {duration_ms}ms")

        yield self._format_sse("workflow", {"type": "complete", "message": "生成完成"})
        yield self._format_sse("done", {
            "model": ctx.model_display_name,
            "model_id": ctx.llm_provider.model_name,
            "provider": ctx.llm_provider.get_model_info()["provider"],
            "duration_ms": duration_ms,
            "generation_id": saved_generation_id
        })


