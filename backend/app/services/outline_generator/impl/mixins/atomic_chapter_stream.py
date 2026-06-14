"""大纲生成器 - 原子化逐章流式生成Mixin

逐章流式生成：每生成一章立即通过SSE发送给前端，支持逐章实时展示。
"""
from __future__ import annotations

import asyncio
from typing import Dict, Any, AsyncGenerator
from datetime import datetime

from app.services.outline_generator.impl.mixins.chapter_boundary import (
    ChapterBoundaryMixin
)


class AtomicChapterStreamMixin:
    """原子化逐章流式生成器"""

    MAX_BOUNDARY_RETRIES = 2
    BOUNDARY_VIOLATION_TEMPERATURE_DELTA = 0.1
    # [2026-05-05] 从 LLM_429_* 重命名为 LLM_RETRY_*，扩展覆盖 RemoteProtocolError 等网络断联错误
    LLM_RETRY_MAX_ATTEMPTS = 3
    LLM_RETRY_BASE_DELAY = 5

    async def generate_all_chapters_atomic_stream(
        self,
        global_outline: str,
        unit_count: int,
        content_type: str,
        user_id: int,
        llm_provider=None,
        temperature: float = 0.5,
        series_type: str = None,
        episode_duration_range: str = None,
        title_style: str = None,
        title_style_name: str = None,
        start_from_unit: int = 1,
        existing_parsed: Dict[str, Dict[str, Any]] = None,
        cancel_event=None,
        # GraphRAG知识库增强（v4.1新增）
        project_id: int = None,
        # 叙事模式（serialized=连续剧，episodic=单元剧）
        narrative_mode: str = "serialized",
    ) -> AsyncGenerator[str, None]:
        """逐章流式生成，每章完成后立即发送SSE事件给前端

        Yields: SSE事件字符串
        """
        boundary_mixin: ChapterBoundaryMixin = self  # type: ignore

        try:
            unit_label_key = {"novel": "章", "series_script": "集",
                              "movie_script": "场", "movie_outline": "场",
                              "series_outline": "集"}
            unit_label = unit_label_key.get(content_type, "章")

            # 步骤1：边界提取
            yield self._format_sse("workflow", {
                "type": "step", "step": "boundary_extraction",
                "status": "running", "message": "正在解析章节边界...",
                "icon": "Search"})

            boundary_map = boundary_mixin.extract_chapter_boundaries(
                global_outline, unit_count, unit_label)

            yield self._format_sse("workflow", {
                "type": "step", "step": "boundary_extraction",
                "status": "done",
                "message": f"章节边界解析完成，覆盖{len(boundary_map)}/{unit_count}章",
                "icon": "Search"})

            # 步骤2：初始化
            locked_chapters: Dict[str, Dict[str, Any]] = {}
            if existing_parsed:
                locked_chapters = dict(existing_parsed)

            boundary_violations = 0

            # 步骤3：逐章流式生成
            self.logger.info(
                f"[原子化流式] 开始逐集生成: start_from_unit={start_from_unit}, "
                f"unit_count={unit_count}, 将生成 {unit_count - start_from_unit + 1} 集"
            )
            for chapter_num in range(start_from_unit, unit_count + 1):
                if cancel_event and cancel_event.is_set():
                    yield self._format_sse("workflow", {
                        "type": "cancelled", "message": "生成已取消"})
                    return

                yield self._format_sse("workflow", {
                    "type": "step", "step": "chapter_generate",
                    "status": "running",
                    "message": f"正在生成第{chapter_num}/{unit_count}{unit_label}...",
                    "icon": "MagicStick", "chapter_num": chapter_num,
                    "total": unit_count})

                prompt = await self._build_atomic_chapter_prompt(
                    chapter_num=chapter_num, boundary_map=boundary_map,
                    locked_chapters=locked_chapters,
                    global_outline=global_outline, content_type=content_type,
                    unit_label=unit_label, unit_count=unit_count,
                    series_type=series_type,
                    episode_duration_range=episode_duration_range,
                    title_style=title_style, title_style_name=title_style_name,
                    project_id=project_id)

                chapter_data = None
                current_temp = temperature

                for retry in range(self.MAX_BOUNDARY_RETRIES + 1):
                    if retry > 0:
                        current_temp = max(
                            0.1, temperature -
                            retry * self.BOUNDARY_VIOLATION_TEMPERATURE_DELTA)

                    # 流式生成单章（带429重试）
                    chunk_parts = []
                    retry_prompt = prompt if retry == 0 else (
                        self._add_boundary_retry_instruction(
                            prompt, chapter_num, unit_label))
                    async for chunk in self._call_llm_stream_with_retry(
                        llm_provider=llm_provider,
                        prompt=retry_prompt,
                        temperature=current_temp,
                        context=f"第{chapter_num}{unit_label}"
                    ):
                        if cancel_event and cancel_event.is_set():
                            return
                        text = chunk.content if hasattr(
                            chunk, 'content') else str(chunk)
                        chunk_parts.append(text)
                        # 实时流式推送每个chunk，实现打字机效果
                        yield self._format_sse("content", {
                            "text": text,
                            "chapter_num": chapter_num,
                            "total": unit_count,
                        })

                    chapter_content = ''.join(chunk_parts)

                    # 解析
                    parsed = self.parse_unit_summaries(
                        chapter_content, unit_count, content_type)
                    chapter_key = str(chapter_num)

                    if chapter_key not in parsed:
                        if retry < self.MAX_BOUNDARY_RETRIES:
                            continue
                        chapter_data = {
                            "unit_id": f"unit-{chapter_num}-fallback",
                            "unit_number": chapter_num,
                            "title": f"第{chapter_num}{unit_label}",
                            "summary": chapter_content[:200],
                            "full_content": chapter_content,
                            "status": "draft",
                            "created_at": datetime.now().isoformat()}
                        break

                    chapter_data = parsed[chapter_key]
                    chapter_data["is_atomic_locked"] = True

                    # 边界验证（v4.0升级）：关键词预筛 + LLM语义验证
                    semantic_validation = await self.validate_boundary_semantic(
                        chapter_content=chapter_data.get(
                            "full_content", "") or chapter_data.get("summary", ""),
                        chapter_num=chapter_num, boundary_map=boundary_map,
                        llm_provider=llm_provider, unit_label=unit_label)
                    chapter_data["boundary_validation"] = {
                        "passed": semantic_validation.passed,
                        "confidence": semantic_validation.confidence,
                        "method": "semantic" if semantic_validation.llm_validated else "keyword",
                    }

                    if semantic_validation.passed:
                        break
                    boundary_violations += 1
                    self.logger.warning(
                        f"[原子化流式] 第{chapter_num}{unit_label}"
                        f"边界违规，第{retry+1}次重试")

                # 锁定本章
                if chapter_data:
                    chapter_data["is_atomic_locked"] = True
                    locked_chapters[chapter_key] = chapter_data
                    self.logger.info(
                        f"[原子化流式] 第{chapter_num}{unit_label}已锁定，"
                        f"locked_chapters现在有{len(locked_chapters)}个章节"
                    )

                    # [2026-05-05] 修复：每生成一集立即保存，支持两种保存方式
                    # 1. 如果有project_id，保存到NovelProject.unit_summaries
                    # 2. 如果没有project_id，保存到Generation.stage_data（单元概述生成阶段）
                    if project_id:
                        # 方式1：保存到NovelProject
                        self.logger.info(
                            f"[原子化流式] 尝试保存第{chapter_num}{unit_label}到项目，project_id={project_id}"
                        )
                        try:
                            from app.models.novel_project import NovelProject
                            from sqlalchemy import select
                            stmt = select(NovelProject).where(NovelProject.id == project_id)
                            result = await self.db.execute(stmt)
                            project = result.scalar_one_or_none()
                            self.logger.info(
                                f"[原子化流式] 查询到项目: {project is not None}, "
                                f"locked_chapters数量: {len(locked_chapters)}"
                            )
                            if project:
                                project.unit_summaries = dict(locked_chapters)
                                await self.db.commit()
                                self.logger.info(
                                    f"[原子化流式] ✅ 第{chapter_num}{unit_label}已保存到项目数据库，"
                                    f"累计{len(locked_chapters)}集"
                                )
                            else:
                                self.logger.warning(
                                    f"[原子化流式] ⚠️ 未找到项目 {project_id}"
                                )
                        except Exception as save_err:
                            import traceback
                            self.logger.error(
                                f"[原子化流式] ❌ 保存到项目失败: {save_err}"
                            )
                            self.logger.error(
                                f"[原子化流式] 异常堆栈:\n{traceback.format_exc()}"
                            )
                    else:
                        # 方式2：保存到Generation.stage_data（单元概述生成阶段）
                        # 这个逻辑需要上层API端点配合，在流式生成时定期保存
                        self.logger.info(
                            f"[原子化流式] ️ project_id为空（单元概述生成阶段），"
                            f"locked_chapters将在生成完成后由API端点保存"
                        )
                else:
                    self.logger.error(
                        f"[原子化流式] ❌ 第{chapter_num}{unit_label}的chapter_data为None，无法保存"
                    )

                # 构建截止当前的全部累积内容（而非仅本章内容）
                accumulated = self._build_revised_content(
                    locked_chapters, content_type)

                # 发送截止当前的累积内容事件（确保前端始终显示全部已生成章节）
                yield self._format_sse("replace_content", {
                    "content": accumulated,
                    "chapter_num": chapter_num, "unit_label": unit_label,
                    "message": f"第{chapter_num}{unit_label}生成完成（共{len(locked_chapters)}章）",
                    "boundary_passed": chapter_data.get(
                        "boundary_validation", {}).get("passed", True)
                    if chapter_data else True,
                    "boundary_method": chapter_data.get(
                        "boundary_validation", {}).get("method", "keyword")
                    if chapter_data else "keyword"})

                yield self._format_sse("workflow", {
                    "type": "step", "step": "chapter_generate",
                    "status": "done",
                    "message": f"第{chapter_num}{unit_label}已完成",
                    "icon": "Check", "chapter_num": chapter_num})

            # 步骤4：编译最终内容并发送完成事件
            final_content = self._build_revised_content(
                locked_chapters, content_type)

            yield self._format_sse("replace_content", {
                "content": final_content,
                "message": f"全部{len(locked_chapters)}章生成完成"})

            # ==================== 保存解析结果到 project.unit_summaries ====================
            # [2026-05-05] 修复续生成检测bug：原子化流式生成完成后必须将locked_chapters
            # 保存到NovelProject.unit_summaries，否则get_unit_summaries_resume_info
            # 端点读取到的数据永远是空的，导致续生成从第1集开始而非从已生成N集后开始
            if project_id and locked_chapters:
                try:
                    from app.models.novel_project import NovelProject
                    from sqlalchemy import select
                    stmt = select(NovelProject).where(NovelProject.id == project_id)
                    result = await self.db.execute(stmt)
                    project = result.scalar_one_or_none()
                    if project:
                        project.unit_summaries = dict(locked_chapters)
                        await self.db.commit()
                        self.logger.info(
                            f"[原子化流式] ✅ 已保存 {len(locked_chapters)} 个单元概述到项目 {project_id}"
                        )
                except Exception as save_err:
                    self.logger.error(
                        f"[原子化流式] ❌ 保存单元概述到项目失败: {save_err}"
                    )

            # [修复] 在complete事件中携带locked_chapters结构化数据，
            # 使API端点可直接保存到 Generation.stage_data，无需前端重新上传
            yield self._format_sse("workflow", {
                "type": "complete",
                "chapters_generated": len(locked_chapters) -
                (start_from_unit - 1),
                "boundary_violations": boundary_violations,
                "locked_chapters_parsed": dict(locked_chapters),
            })

        except Exception as e:
            self.logger.error(f"[原子化流式] 失败: {e!r}", exc_info=True)
            yield self._format_sse("workflow", {
                "type": "error", "message": f"生成失败: {str(e)}"})

    async def _call_llm_stream_with_retry(
        self,
        llm_provider,
        prompt: str,
        temperature: float,
        context: str = "",
    ) -> AsyncGenerator:
        """流式调用LLM生成并自动处理限流和网络断联错误（指数退避重试）

        遇到以下错误时自动重试：
        - 429 限流错误
        - httpx.RemoteProtocolError / 网络断联错误

        Args:
            llm_provider: LLM提供商实例
            prompt: 提示词
            temperature: 温度参数
            context: 上下文标识（如"第5章"）用于日志

        Yields:
            LLM流式响应chunk

        Raises:
            Exception: 非可重试错误直接抛出；重试耗尽后抛出最后一次异常
        """
        from app.utils.llm_retry import is_network_error, is_rate_limit_error

        ctx_suffix = f" | {context}" if context else ""
        for attempt in range(self.LLM_RETRY_MAX_ATTEMPTS):
            try:
                async for chunk in llm_provider.generate_stream(
                    prompt=prompt, temperature=temperature):
                    yield chunk
                return  # 流式完成，正常退出
            except Exception as e:
                should_retry = is_rate_limit_error(e) or is_network_error(e)
                if not should_retry:
                    raise
                if attempt < self.LLM_RETRY_MAX_ATTEMPTS - 1:
                    wait_time = self.LLM_RETRY_BASE_DELAY * (2 ** attempt)
                    error_type = "限流" if is_rate_limit_error(e) else "网络断联"
                    self.logger.warning(
                        f"[原子化流式] LLM{error_type}错误{ctx_suffix}，"
                        f"第{attempt + 1}次重试，等待{wait_time}秒..."
                        f"{type(e).__name__}: {str(e)[:200]}")
                    yield self._format_sse("workflow", {
                        "type": "step", "step": "retry",
                        "status": "running",
                        "message": f"LLM{error_type}，正在重试（{attempt + 1}/{self.LLM_RETRY_MAX_ATTEMPTS}）...",
                        "icon": "RefreshRight"})
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(
                        f"[原子化流式] LLM重试耗尽{ctx_suffix}，"
                        f"已重试{self.LLM_RETRY_MAX_ATTEMPTS}次仍失败: "
                        f"{type(e).__name__}: {str(e)[:200]}")
                    raise
