"""Agent编排器 - 流式生成入口Mixin"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
import re
import os
import time
import asyncio
from app.core.logger import get_logger, LoggerAdapter
from app.agents.orchestrator.api import GenerateStreamContext


class GenerateStreamMixinMixin:
    """流式生成入口"""

    async def generate_stream(
        self,
        db: AsyncSession,
        module: str,
        user_id: int,
        input_params: Dict[str, Any],
        session_id: Optional[str] = None,
        enable_search: bool = False,  # 向后兼容，映射到 enable_creative_search
        enable_knowledge: bool = False,
        enable_mcp: bool = False,  # 向后兼容，映射到 enable_trending
        reference_urls: Optional[List[str]] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None,
        cancel_event: Optional[asyncio.Event] = None,
        # 知识库类别选择参数
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[List[int]] = None,
        kb_user_specific_ids: Optional[List[int]] = None,
        kb_manual_ids: Optional[List[int]] = None,
        # 创作辅助搜索参数（新）
        enable_creative_search: bool = False,
        search_keywords: Optional[List[str]] = None,
        search_depth: str = "normal",
        # 实时热点参数（新）
        enable_trending: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        执行创意生成（流式输出）- 重构后的编排器方法

        此方法现在作为编排器，调用各个私有方法完成生成流程：
        1. _load_llm_provider() - LLM加载
        2. _prepare_input_params() - 参数准备
        3. _gather_context() - 上下文收集
        4. _generate_first_draft() - 初稿生成
        5. _evaluate_and_revise() - 评估和修正
        6. _save_and_complete() - 保存和完成

        Args:
            db: 数据库会话
            module: 模块名称
            user_id: 用户ID
            input_params: 输入参数
            session_id: 会话ID
            enable_search: 是否启用联网搜索（向后兼容，映射到 enable_creative_search）
            enable_knowledge: 是否启用知识库增强
            enable_mcp: 是否启用 MCP 实时热点数据（向后兼容，映射到 enable_trending）
            reference_urls: 参考网页URL列表
            provider: 指定LLM提供者
            temperature: 温度参数
            images: 图片URL列表（多模态支持）
            videos: 视频URL列表（多模态支持，仅部分LLM支持）
            kb_vertical: 是否启用垂直领域知识库
            kb_user_specific: 是否启用用户专属知识库
            kb_manual: 是否启用官方手册知识库
            kb_vertical_ids: 指定的垂直领域知识库ID列表
            kb_user_specific_ids: 指定的用户专属知识库ID列表
            kb_manual_ids: 指定的官方手册知识库ID列表
            enable_creative_search: 是否启用创作辅助搜索（智能搜索创作素材和背景信息）
            search_keywords: 用户指定的搜索关键词列表
            search_depth: 搜索深度 (quick/normal/deep)
            enable_trending: 是否启用实时热点聚合

        Yields:
            SSE 格式的数据块
        """
        logger = get_logger(str(user_id))
        start_time = time.time()

        # 参数兼容处理：旧参数映射到新参数
        actual_enable_creative_search = enable_creative_search or enable_search
        actual_enable_trending = enable_trending or enable_mcp

        try:
            # 发送开始事件
            yield self._format_sse("workflow", {"type": "start", "steps": []})

            # 1. 加载 LLM 提供者
            yield self._format_sse("workflow", {"type": "step", "step": "model", "status": "running", "message": "正在加载AI模型...", "icon": "Cpu"})
            llm_provider, model_display_name = await self._load_llm_provider(db, user_id, provider)
            yield self._format_sse("workflow", {"type": "step", "step": "model", "status": "done", "message": f"已加载模型: {model_display_name}"})

            # 2. 准备输入参数和系统提示词
            yield self._format_sse("workflow", {"type": "step", "step": "prompt", "status": "running", "message": "正在准备提示词...", "icon": "Document"})
            processed_input_params, system_prompt = await self._prepare_input_params(db, module, input_params, logger)
            yield self._format_sse("workflow", {"type": "step", "step": "prompt", "status": "done", "message": "提示词准备完成"})

            # 3. 初始化上下文对象
            ctx = GenerateStreamContext(
                llm_provider=llm_provider,
                model_display_name=model_display_name,
                system_prompt=system_prompt,
                input_params=processed_input_params,
                start_time=start_time,
                converted_images=images,
                videos=videos
            )

            # 4. 收集上下文信息
            async for sse_event in self._gather_context(
                ctx=ctx,
                db=db,
                user_id=user_id,
                module=module,
                enable_knowledge=enable_knowledge,
                kb_vertical=kb_vertical,
                kb_user_specific=kb_user_specific,
                kb_manual=kb_manual,
                kb_vertical_ids=kb_vertical_ids,
                kb_user_specific_ids=kb_user_specific_ids,
                kb_manual_ids=kb_manual_ids,
                actual_enable_creative_search=actual_enable_creative_search,
                search_keywords=search_keywords,
                search_depth=search_depth,
                actual_enable_trending=actual_enable_trending,
                reference_urls=reference_urls,
                logger=logger
            ):
                yield sse_event

            # 5. 生成初稿
            async for sse_event in self._generate_first_draft(
                ctx=ctx,
                db=db,
                user_id=user_id,
                module=module,
                temperature=temperature,
                cancel_event=cancel_event,
                logger=logger
            ):
                yield sse_event

            # 6. 评估和修正
            async for sse_event in self._evaluate_and_revise(
                ctx=ctx,
                db=db,
                user_id=user_id,
                module=module,
                enable_knowledge=enable_knowledge,
                temperature=temperature,
                cancel_event=cancel_event,
                logger=logger,
                kb_vertical=kb_vertical,
                kb_user_specific=kb_user_specific,
                kb_manual=kb_manual
            ):
                yield sse_event

            # 7. 保存和完成
            async for sse_event in self._save_and_complete(
                ctx=ctx,
                db=db,
                user_id=user_id,
                logger=logger
            ):
                yield sse_event

        except Exception as e:
            logger.exception("流式生成失败")
            yield self._format_sse("workflow", {"type": "error", "message": str(e)})
            yield self._format_sse("error", {"message": str(e)})


