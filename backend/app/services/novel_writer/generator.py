"""
章节生成器
核心章节生成逻辑
"""
import os
import json
import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.logger import get_logger
from app.core.config import get_settings
from app.models import NovelProject, NovelChapter, ProjectStatus, ChapterStatus
from app.agents.llm_manager import llm_manager

from app.services.novel_writer.context_manager import ContextWindowManager
from app.services.novel_writer.consistency import ConsistencyManager
from app.services.novel_writer.vector_store import ProjectVectorStore
from app.services.novel_writer.prompt_templates import get_chapter_prompt, get_episode_prompt
from app.services.novel_writer.content_reviser import ContentReviser
from app.services.proofread.document_formatter import DocumentFormatter
from app.services.task_manager import (
    task_manager, TASK_STATUS_CANCELLED,
    TASK_TYPE_EPISODE_OUTLINE, TASK_TYPE_CHAPTER_OUTLINE, TASK_TYPE_SCENE_OUTLINE,
    TASK_TYPE_EPISODE_CONTENT, TASK_TYPE_CHAPTER_CONTENT, TASK_TYPE_SCENE_CONTENT
)


class NovelChapterGenerator:
    """小说/剧本章节生成器"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.logger = get_logger("chapter_generator")

        # 初始化各管理器
        self.context_manager = ContextWindowManager(db)
        self.consistency_manager = ConsistencyManager()
        self.vector_store = ProjectVectorStore()
        self.content_reviser = ContentReviser(db)

    def _format_outline(self, outline: str, content_type: str = "novel") -> str:
        """
        格式化大纲内容

        在提取章节/分集概要之前，先对大纲进行格式化处理：
        - 标准化章节标题格式
        - 移除干扰内容（版权声明、广告等）
        - 删除重复章节标题

        Args:
            outline: 原始大纲内容
            content_type: 内容类型 (novel/series_script/movie_script)

        Returns:
            格式化后的大纲内容
        """
        if not outline:
            return outline

        try:
            formatter = DocumentFormatter(content_type=content_type)
            formatted_outline, stats = formatter.format(outline)
            if stats.titles_normalized > 0 or stats.noise_content_removed > 0:
                self.logger.info(
                    f"[大纲格式化] 标准化{stats.titles_normalized}个标题, "
                    f"移除{stats.noise_content_removed}处干扰内容, "
                    f"移除{stats.duplicate_titles_removed}个重复标题"
                )
            return formatted_outline
        except Exception as e:
            self.logger.warning(f"[大纲格式化] 格式化处理失败: {e}")
            return outline

    def _smart_outline_truncate(
        self,
        outline: str,
        max_length: int = 30000,
        target_unit: int = None,
        content_type: str = "novel"
    ) -> str:
        """
        智能截断大纲内容

        与简单截断不同，此方法会：
        1. 优先保留目标单元附近的内容
        2. 保留全局设定部分（人物、世界观等）
        3. 在章节边界处截断，避免截断到一半
        4. 对于超长大纲，保留关键信息摘要

        Args:
            outline: 大纲内容
            max_length: 最大长度限制
            target_unit: 目标单元号（章节/集/场景）
            content_type: 内容类型

        Returns:
            处理后的大纲内容
        """
        if not outline or len(outline) <= max_length:
            return outline or ""

        # 单位标签映射
        unit_label = {"novel": "章", "series_script": "集",
                      "movie_script": "场"}.get(content_type, "章")

        # 1. 提取全局设定部分（通常在开头）
        global_section = ""
        global_keywords = ["人物", "角色", "设定", "世界观", "背景", "简介", "概述", "大纲说明"]
        lines = outline.split('\n')
        global_lines = []
        content_start_idx = 0

        for i, line in enumerate(lines):
            # 检测全局设定区域
            line_stripped = line.strip()
            is_global_header = any(
                kw in line_stripped for kw in global_keywords)
            is_chapter_header = (
                line_stripped.startswith(
                    '#') and f'第' in line_stripped and unit_label in line_stripped
            ) or re.match(rf'^#+\s*第\d+{unit_label}', line_stripped)

            if is_chapter_header and not is_global_header:
                content_start_idx = i
                break
            elif i < 50:  # 只在前50行查找全局设定
                global_lines.append(line)

        if global_lines:
            global_section = '\n'.join(global_lines[:30])  # 最多保留30行全局设定

        # 2. 如果指定了目标单元，优先保留该单元附近的内容
        target_section = ""
        if target_unit:
            # 查找目标单元的位置
            target_patterns = [
                rf'^#+\s*第{target_unit}{unit_label}',
                rf'^第{target_unit}{unit_label}',
                rf'^\*\*第{target_unit}{unit_label}',
            ]

            target_start_idx = -1
            target_end_idx = len(lines)

            for i, line in enumerate(lines):
                for pattern in target_patterns:
                    if re.match(pattern, line.strip()):
                        target_start_idx = i
                        break
                if target_start_idx >= 0 and i > target_start_idx:
                    # 查找下一单元的开始位置
                    next_unit = target_unit + 1
                    next_patterns = [
                        rf'^#+\s*第{next_unit}{unit_label}',
                        rf'^第{next_unit}{unit_label}',
                    ]
                    for pattern in next_patterns:
                        if re.match(pattern, line.strip()):
                            target_end_idx = i
                            break

            if target_start_idx >= 0:
                target_section = '\n'.join(
                    lines[target_start_idx:target_end_idx])

        # 3. 构建最终内容
        result_parts = []

        # 添加全局设定
        if global_section:
            result_parts.append(global_section)

        # 添加目标单元内容
        if target_section:
            result_parts.append(
                f"\n---\n\n【当前{unit_label}详细大纲】\n{target_section}")

        # 4. 如果仍有空间，添加其他单元的摘要
        current_length = sum(len(p) for p in result_parts)
        remaining_space = max_length - current_length - 500  # 预留500字符

        if remaining_space > 1000:
            # 提取其他单元的标题和简短摘要
            other_sections = []
            for i, line in enumerate(lines):
                if re.match(rf'^#+\s*第\d+{unit_label}', line.strip()):
                    # 获取标题行和下一行摘要
                    section_preview = line
                    if i + 1 < len(lines) and lines[i + 1].strip():
                        section_preview += '\n' + \
                            lines[i + 1][:100]  # 最多100字符摘要
                    other_sections.append(section_preview)

            if other_sections:
                other_content = '\n\n'.join(other_sections[:20])  # 最多20个单元预览
                if len(other_content) <= remaining_space:
                    result_parts.append(
                        f"\n---\n\n【其他{unit_label}概览】\n{other_content}")
                else:
                    result_parts.append(
                        f"\n---\n\n【其他{unit_label}概览】\n{other_content[:remaining_space]}")

        result = '\n'.join(result_parts)

        # 5. 最终检查长度
        if len(result) > max_length:
            result = result[:max_length]
            # 在最后一个完整的句子或行处截断
            last_newline = result.rfind('\n')
            if last_newline > max_length * 0.8:
                result = result[:last_newline]

        self.logger.debug(
            f"[智能截断] 原始长度: {len(outline)}, 截断后: {len(result)}, "
            f"目标{unit_label}: {target_unit}, 全局设定: {len(global_section)}字"
        )

        return result

    async def _ensure_fresh_project_data(
        self,
        project: NovelProject,
        required_fields: List[str] = None
    ) -> bool:
        """
        确保项目数据是最新的（解决会话隔离问题）

        在长时间运行的任务中，SQLAlchemy会话可能会过期或隔离，
        导致项目对象的某些字段（如outline_content）为None。
        此方法会检查并从数据库重新获取缺失的数据。

        Args:
            project: 项目对象
            required_fields: 需要检查的字段列表，默认为['outline_content']

        Returns:
            是否成功刷新数据
        """
        if required_fields is None:
            required_fields = ['outline_content']

        # JSON 字段列表（需要检查是否为空字典）
        json_fields = {'unit_summaries', 'chapter_outlines',
                       'episode_outlines', 'scene_outlines'}

        def is_field_missing(obj, field):
            """检查字段是否缺失（None 或空字典）"""
            value = getattr(obj, field, None)
            if value is None:
                return True
            # 对于 JSON 字段，空字典也算缺失
            if field in json_fields and isinstance(value, dict) and len(value) == 0:
                return True
            return False

        # 检查是否需要刷新
        needs_refresh = False
        missing_fields = []

        for field in required_fields:
            if is_field_missing(project, field):
                missing_fields.append(field)
                needs_refresh = True

        if not needs_refresh:
            return True

        if not project.id:
            self.logger.warning("[会话刷新] 项目ID为空，无法刷新")
            return False

        try:
            # 方法1: 尝试使用refresh刷新整个对象
            try:
                await self.db.refresh(project)
                self.logger.debug(f"[会话刷新] refresh成功")
            except Exception as refresh_error:
                self.logger.debug(f"[会话刷新] refresh失败: {refresh_error}")

            # 方法2: 如果refresh后仍有缺失字段，执行独立查询
            still_missing = []
            for field in required_fields:
                if is_field_missing(project, field):
                    still_missing.append(field)

            if still_missing:
                self.logger.info(
                    f"[会话刷新] refresh后仍有缺失字段: {still_missing}，执行独立查询")

                from sqlalchemy import select
                fresh_query = select(NovelProject).where(
                    NovelProject.id == project.id)
                fresh_result = await self.db.execute(fresh_query)
                fresh_project = fresh_result.scalar_one_or_none()

                if fresh_project:
                    for field in still_missing:
                        fresh_value = getattr(fresh_project, field, None)
                        # 对于 JSON 字段，检查是否有内容
                        if fresh_value is not None:
                            if field in json_fields:
                                if isinstance(fresh_value, dict) and len(fresh_value) > 0:
                                    setattr(project, field, fresh_value)
                                    self.logger.info(
                                        f"[会话刷新] 从数据库重新获取{field}成功，共{len(fresh_value)}项")
                            else:
                                setattr(project, field, fresh_value)
                                self.logger.info(
                                    f"[会话刷新] 从数据库重新获取{field}成功")
                    return True
                else:
                    self.logger.warning("[会话刷新] 独立查询未找到项目")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"[会话刷新] 刷新失败: {e}")
            return False

    async def _call_with_retry(
        self,
        coro_factory,
        item_name: str = "项目",
        max_retries: int = None,
        base_delay: float = None
    ) -> Dict[str, Any]:
        """
        带重试机制的 API 调用包装器

        Args:
            coro_factory: 返回协程的可调用对象（每次调用返回新的协程实例）
            item_name: 当前生成项的名称（用于日志）
            max_retries: 最大重试次数，None则使用配置值
            base_delay: 基础延迟时间，None则使用配置值

        Returns:
            生成结果字典

        Note:
            使用协程工厂函数而非协程对象，因为协程只能被 await 一次。
            每次重试时需要创建新的协程实例。
        """
        if max_retries is None:
            max_retries = self.settings.BATCH_MAX_RETRIES
        if base_delay is None:
            base_delay = self.settings.BATCH_RETRY_BASE_DELAY

        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # 每次重试都创建新的协程实例
                coro = coro_factory() if callable(coro_factory) else coro_factory
                result = await coro
                return result
            except asyncio.CancelledError:
                # 取消异常直接抛出，不重试
                raise
            except Exception as e:
                error_str = str(e).lower()
                # 检查是否为速率限制错误（429 或 rate limit 相关）
                is_rate_limit = (
                    "429" in error_str or
                    "rate" in error_str or
                    "limit" in error_str or
                    "too many requests" in error_str
                )

                if is_rate_limit and attempt < max_retries and self.settings.BATCH_RETRY_ON_RATE_LIMIT:
                    # 指数退避：base_delay * (2 ^ attempt)
                    wait_time = base_delay * (2 ** attempt)
                    self.logger.warning(
                        f"[速率限制] {item_name} 触发API限流，"
                        f"等待 {wait_time:.1f} 秒后重试 (尝试 {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    last_error = e
                else:
                    # 非速率限制错误或重试次数用尽，直接抛出
                    raise

        # 重试次数用尽
        raise last_error or Exception(f"{item_name} 生成失败：重试次数已用尽")

    async def generate_chapter(
        self,
        project: NovelProject,
        chapter_num: int,
        llm_provider=None
    ) -> Dict[str, Any]:
        """
        生成单个章节

        Args:
            project: 项目对象
            chapter_num: 章节号
            llm_provider: LLM提供者（可选）

        Returns:
            生成结果
        """
        result = {
            "success": False,
            "chapter_number": chapter_num,
            "content": None,
            "word_count": 0,
            "token_count": 0,
            "duration_ms": 0,
            "error_message": None
        }

        start_time = time.time()

        try:
            # 1. 获取章节对象
            chapter = await self._get_or_create_chapter(project, chapter_num)

            if chapter.status == ChapterStatus.COMPLETED:
                result["success"] = True
                result["content"] = chapter.final_content
                result["word_count"] = chapter.word_count
                self.logger.info(f"章节已完成，跳过生成: 第{chapter_num}章")
                return result

            # 记录大纲状态（调试用）
            outline_status = {
                "has_outline_content": bool(project.outline_content),
                "outline_content_len": len(project.outline_content) if project.outline_content else 0,
                "outline_file_path": project.outline_file_path
            }
            self.logger.debug(f"[大纲状态] 第{chapter_num}章生成前: {outline_status}")

            # 确保项目数据是最新的（解决会话隔离问题）
            await self._ensure_fresh_project_data(
                project, required_fields=['outline_content', 'outline_file_path'])

            # 2. 更新状态为生成中
            chapter.status = ChapterStatus.DRAFTING
            await self.db.commit()

            # 3. 获取LLM提供者
            if not llm_provider:
                llm_provider = await self._get_llm_provider(project)

            if not llm_provider:
                raise Exception("无法获取LLM提供者，请检查API配置")

            # 设置一致性管理器的LLM
            self.consistency_manager.set_llm_provider(llm_provider)

            # 4. 构建上下文
            chapter_metadata = chapter.chapter_metadata or {}

            # 关键修复：将数据库列字段中的episode_number和scene_number加入元数据字典
            # 这些值存储在chapter对象的独立列字段中，而非JSON字段chapter_metadata中
            if chapter.episode_number is not None:
                chapter_metadata['episode_number'] = chapter.episode_number
            if chapter.scene_number is not None:
                chapter_metadata['scene_number'] = chapter.scene_number

            # 日志记录分集信息
            if chapter.episode_number:
                self.logger.info(
                    f"[分集信息] 当前生成: 第{chapter.episode_number}集 第{chapter.scene_number}场")

            context = await self.context_manager.build_chapter_context(
                project, chapter_num, chapter_metadata
            )

            # 5. 构建提示词
            generation_config = project.generation_config or {}

            # 获取内容类型（优先使用新版content_type，兼容旧版project_type）
            content_type = getattr(project, 'content_type', None)
            if not content_type:
                content_type = project.project_type.value if hasattr(
                    project, 'project_type') else 'novel'

            # 获取类型配置
            type_config = None
            if content_type == 'novel':
                type_config = getattr(project, 'novel_config', None)
            elif content_type == 'series_script':
                type_config = getattr(project, 'series_script_config', None)
            elif content_type == 'movie_script':
                type_config = getattr(project, 'movie_script_config', None)

            # 兼容旧版script_config
            if not type_config and content_type == 'script':
                type_config = getattr(project, 'script_config', None)

            prompt = get_chapter_prompt(
                content_type=content_type,
                chapter_number=chapter_num,
                chapter_title=chapter.chapter_title or f"第{chapter_num}章",
                chapter_metadata=chapter_metadata,
                context=context,
                generation_config=generation_config,
                type_config=type_config
            )

            # 调试日志：检查提示词中的大纲内容
            outline_in_context = context.get("outline_content", "")
            current_unit_outline = context.get("current_unit_outline", "")
            chapter_detailed_outline = context.get(
                "chapter_detailed_outline", "")
            self.logger.debug(
                f"[提示词检查] outline_content长度: {len(outline_in_context)}字")
            self.logger.debug(
                f"[提示词检查] current_unit_outline长度: {len(current_unit_outline)}字")
            self.logger.debug(
                f"[提示词检查] chapter_detailed_outline长度: {len(chapter_detailed_outline)}字")
            self.logger.debug(f"[提示词检查] 最终提示词总长度: {len(prompt)}字")

            # 检查提示词是否包含大纲关键字
            if "大纲" in prompt:
                self.logger.debug("[提示词检查] 提示词中包含'大纲'关键字 ✓")
            else:
                self.logger.warning("[提示词检查] 提示词中未找到'大纲'关键字 ✗")

            # 6. 调用LLM生成（带重试机制）
            self.logger.info(f"开始生成章节: 第{chapter_num}章")

            temperature = generation_config.get("temperature", 0.8)
            # 不再限制max_tokens，让LLM根据提示词中的字数要求自由生成

            # 使用带重试的调用方式处理 429 速率限制
            llm_response = await self._call_with_retry(
                lambda: llm_provider.generate(
                    prompt, temperature=temperature),
                item_name=f"第{chapter_num}章生成"
            )

            # 提取响应内容（LLMResponse是Pydantic模型，需要获取content属性）
            if hasattr(llm_response, 'content'):
                chapter_content = llm_response.content
            else:
                # 兼容直接返回字符串的情况
                chapter_content = str(llm_response)

            # 提取Token使用量（关键修复：正确统计Token消耗）
            token_count = 0
            if hasattr(llm_response, 'usage') and llm_response.usage:
                usage = llm_response.usage
                if isinstance(usage, dict):
                    token_count = usage.get('total_tokens', 0)
                else:
                    token_count = getattr(usage, 'total_tokens', 0)

                # 更新项目总Token消耗
                if token_count > 0:
                    project.total_tokens = (
                        project.total_tokens or 0) + token_count
                    self.logger.info(
                        f"章节生成Token消耗: {token_count}, 项目累计: {project.total_tokens}")

            # 7. 基于知识库自动修正（如果启用）
            # 保存原始草稿内容（用于修正历史对比）
            original_draft = chapter_content
            revision_applied = False
            revision_info = None

            if project.kb_graphrag_enabled and project.kb_status == "ready":
                self.logger.info(f"开始知识库修正: 第{chapter_num}章")
                revision_result = await self.content_reviser.revise_content(
                    project=project,
                    unit_number=chapter_num,
                    draft_content=chapter_content,
                    llm_provider=llm_provider,
                    content_type=content_type
                )
                if revision_result["success"] and revision_result.get("revised_content"):
                    original_len = len(chapter_content)
                    chapter_content = revision_result["revised_content"]
                    revision_applied = True
                    revision_info = {
                        "applied": True,
                        "original_length": original_len,
                        "revised_length": len(chapter_content),
                        "knowledge_used": revision_result.get("knowledge_used", {}),
                        "revised_at": datetime.now().isoformat()
                    }
                    self.logger.info(
                        f"知识库修正完成: 第{chapter_num}章, "
                        f"原文{original_len}字 -> 修正后{len(chapter_content)}字, "
                        f"知识库引用: {revision_result.get('knowledge_used', {})}"
                    )
                else:
                    self.logger.info(
                        f"知识库修正跳过: 第{chapter_num}章, 原因: {revision_result.get('error', '未知')}"
                    )

            # 8. 后处理
            chapter_content = self._post_process(chapter_content)

            # 8.5 合规审核标记（非阻塞）
            compliance_result = await self._mark_compliance(project, chapter_content)

            # 记录字数信息（用于日志）
            words_per_chapter = 3000  # 默认值
            if type_config:
                words_per_chapter = type_config.get("words_per_chapter", 3000)
            actual_words = len(chapter_content)
            self.logger.info(
                f"第{chapter_num}章生成完成: 目标{words_per_chapter}字, 实际{actual_words}字, "
                f"偏差{((actual_words - words_per_chapter) / words_per_chapter * 100):.1f}%"
            )

            # 9. 定稿处理
            await self._finalize_chapter(project, chapter, chapter_content, llm_provider)

            # 10. 更新结果
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)

            result["success"] = True
            result["content"] = chapter_content
            result["word_count"] = len(chapter_content)
            result["token_count"] = token_count
            result["duration_ms"] = duration_ms

            # 更新章节记录
            chapter.status = ChapterStatus.COMPLETED
            chapter.draft_content = original_draft  # 保存原始草稿
            chapter.final_content = chapter_content
            chapter.word_count = len(chapter_content)
            chapter.token_count = token_count
            chapter.duration_ms = duration_ms

            # 保存修正信息到元数据
            if revision_applied and revision_info:
                chapter_metadata = chapter.chapter_metadata or {}
                chapter_metadata["revision_info"] = revision_info
                chapter.chapter_metadata = chapter_metadata

            # 保存合规审核标记到元数据
            if compliance_result:
                chapter_metadata = chapter.chapter_metadata or {}
                chapter_metadata["compliance_marking"] = compliance_result
                chapter.chapter_metadata = chapter_metadata
                if compliance_result.get("has_issues"):
                    self.logger.info(
                        f"合规审核标记: 第{chapter_num}章, "
                        f"发现{compliance_result.get('issue_count', 0)}处潜在问题"
                    )

            # 更新项目进度
            await self._update_project_progress(project, chapter_num)

            # 同步正文生成状态到大纲记录
            await self._sync_content_status(
                project, chapter_num, content_type, len(chapter_content))

            await self.db.commit()

            self.logger.info(
                f"章节生成完成: 第{chapter_num}章, 字数: {len(chapter_content)}")
            return result

        except Exception as e:
            self.logger.error(f"生成章节失败: 第{chapter_num}章, 错误: {str(e)}")
            result["error_message"] = str(e)

            # 更新错误状态
            try:
                chapter = await self._get_or_create_chapter(project, chapter_num)
                chapter.status = ChapterStatus.FAILED
                chapter.error_message = str(e)
                await self.db.commit()
            except Exception as update_error:
                self.logger.warning(f"更新章节错误状态失败: {str(update_error)}")

            return result

    async def generate_all_chapters(
        self,
        project: NovelProject,
        start_chapter: int = 1,
        stop_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        批量生成所有章节

        Args:
            project: 项目对象
            start_chapter: 起始章节
            stop_on_error: 出错时是否停止

        Returns:
            批量生成结果
        """
        result = {
            "project_id": project.id,
            "start_chapter": start_chapter,
            "end_chapter": project.total_chapters,
            "completed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,  # 新增：跳过的章节计数
            "total_tokens": 0,
            "total_duration_ms": 0,
            "errors": [],
            "skipped": []  # 新增：跳过的章节详情
        }

        # 更新项目状态
        project.status = ProjectStatus.GENERATING
        await self.db.commit()

        try:
            # 获取LLM提供者（只获取一次）
            llm_provider = await self._get_llm_provider(project)

            # 获取内容类型
            content_type = getattr(project, 'content_type', None)
            if not content_type:
                content_type = project.project_type.value if hasattr(
                    project, 'project_type') else 'novel'

            for chapter_num in range(start_chapter, project.total_chapters + 1):
                # 检查项目是否已暂停
                await self.db.refresh(project)
                if project.status == ProjectStatus.PAUSED:
                    self.logger.info(f"项目已暂停，停止生成: {project.title}")
                    break

                # 对于连续剧类型，检查是否有详细大纲
                if content_type in ('series_script', 'script'):
                    episode_outlines = project.episode_outlines or {}
                    episode_outline = episode_outlines.get(str(chapter_num))

                    if not episode_outline:
                        self.logger.warning(
                            f"[批量生成] 第{chapter_num}集缺少详细大纲，跳过生成")
                        result["skipped_count"] += 1
                        result["skipped"].append({
                            "chapter_number": chapter_num,
                            "reason": "缺少详细大纲"
                        })
                        continue

                # 生成章节
                chapter_result = await self.generate_chapter(
                    project, chapter_num, llm_provider
                )

                if chapter_result["success"]:
                    result["completed_count"] += 1
                    # 累计Token消耗
                    result["total_tokens"] += chapter_result.get(
                        "token_count", 0)
                else:
                    result["failed_count"] += 1
                    result["errors"].append({
                        "chapter_number": chapter_num,
                        "error": chapter_result.get("error_message")
                    })

                    if stop_on_error:
                        self.logger.warning(f"生成失败，停止批量生成: 第{chapter_num}章")
                        break

                result["total_duration_ms"] += chapter_result.get(
                    "duration_ms", 0)

                # 更新当前章节
                project.current_chapter = chapter_num
                await self.db.commit()

            # 更新项目状态
            if result["completed_count"] == project.total_chapters:
                project.status = ProjectStatus.COMPLETED
            elif result["failed_count"] > 0 and stop_on_error:
                project.status = ProjectStatus.FAILED
                project.error_message = f"生成失败于第{result['errors'][-1]['chapter_number']}章"

            await self.db.commit()

            return result

        except Exception as e:
            self.logger.error(f"批量生成失败: {str(e)}")
            project.status = ProjectStatus.FAILED
            project.error_message = str(e)
            await self.db.commit()

            return result

    async def _get_or_create_chapter(
        self,
        project: NovelProject,
        chapter_num: int
    ) -> NovelChapter:
        """获取或创建章节"""
        query = select(NovelChapter).where(
            NovelChapter.project_id == project.id,
            NovelChapter.chapter_number == chapter_num
        )
        result = await self.db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            # 关键修复：获取内容类型
            content_type = getattr(project, 'content_type', None)
            if not content_type:
                content_type = project.project_type.value if hasattr(
                    project, 'project_type') else 'novel'

            # 根据内容类型确定标题
            chapter_title = f"第{chapter_num}章"  # 默认标题

            # 如果是剧本类型，尝试从 episode_outlines 获取标题
            if content_type in ('series_script', 'script'):
                episode_outlines = project.episode_outlines or {}
                # 对于剧本，章节号对应集数
                # 先查找是否有对应的大纲记录
                ep_outline = episode_outlines.get(str(chapter_num), {})
                episode_title = ep_outline.get('episode_title', '')

                if episode_title:
                    chapter_title = f"第{chapter_num}集 {episode_title}"
                    self.logger.info(
                        f"[章节标题] 从分集大纲获取标题: 第{chapter_num}集《{episode_title}》")
                else:
                    chapter_title = f"第{chapter_num}集"

            chapter = NovelChapter(
                project_id=project.id,
                chapter_number=chapter_num,
                chapter_title=chapter_title,
                status=ChapterStatus.PENDING
            )
            self.db.add(chapter)
            await self.db.commit()
            await self.db.refresh(chapter)

        return chapter

    async def _get_llm_provider(self, project: NovelProject):
        """获取LLM提供者"""
        generation_config = project.generation_config or {}

        provider_name = generation_config.get("provider")
        model_name = generation_config.get("model_name")

        if provider_name:
            try:
                provider = await llm_manager.get_provider_from_db(
                    self.db,
                    project.user_id,
                    provider_name
                )
                return provider
            except Exception as e:
                self.logger.warning(f"从数据库获取提供者失败: {str(e)}")

        # 使用默认提供者
        try:
            provider = await llm_manager.get_provider_from_db(
                self.db,
                project.user_id
            )
            return provider
        except Exception as e:
            self.logger.error(f"获取默认提供者失败: {str(e)}")
            return None

    async def _finalize_chapter(
        self,
        project: NovelProject,
        chapter: NovelChapter,
        content: str,
        llm_provider
    ):
        """章节定稿处理"""
        # 1. 保存章节文件
        if project.chapters_dir:
            os.makedirs(project.chapters_dir, exist_ok=True)
            chapter_file = os.path.join(
                project.chapters_dir,
                f"{project.project_code}_chapter_{chapter.chapter_number:03d}.txt"
            )
            with open(chapter_file, 'w', encoding='utf-8') as f:
                f.write(content)
            chapter.content_file = chapter_file

        # 2. 一致性更新
        await self.consistency_manager.finalize_chapter(project, chapter, content)

        # 3. 存入向量库
        await self.vector_store.add_chapter(
            project.id,
            chapter.chapter_number,
            chapter.chapter_title,
            content
        )

    async def _update_project_progress(
        self,
        project: NovelProject,
        completed_chapter: int
    ):
        """更新项目进度"""
        if completed_chapter > project.completed_chapters:
            project.completed_chapters = completed_chapter
            project.current_chapter = completed_chapter

    async def _sync_content_status(
        self,
        project: NovelProject,
        unit_number: int,
        content_type: str,
        word_count: int,
        status: str = "generated"
    ) -> bool:
        """
        同步正文生成状态到大纲记录

        在正文生成完成后，需要同步更新对应的 xxx_outlines 字段中的状态信息，
        确保前端能正确显示生成状态。

        Args:
            project: 项目对象
            unit_number: 单元号（章节/集/场景）
            content_type: 内容类型 (novel/series_script/movie_script)
            word_count: 正文字数
            status: 状态 (generated/failed)

        Returns:
            是否成功同步
        """
        try:
            from sqlalchemy.orm.attributes import flag_modified
            from datetime import datetime

            unit_key = str(unit_number)
            updated = False

            if content_type == "novel":
                outlines = project.chapter_outlines or {}
                if unit_key in outlines:
                    outlines[unit_key]["content_status"] = status
                    outlines[unit_key]["content_generated_at"] = datetime.now(
                    ).isoformat()
                    outlines[unit_key]["content_word_count"] = word_count
                    project.chapter_outlines = outlines
                    flag_modified(project, 'chapter_outlines')
                    updated = True

            elif content_type in ("series_script", "script"):
                outlines = project.episode_outlines or {}
                if unit_key in outlines:
                    outlines[unit_key]["content_status"] = status
                    outlines[unit_key]["content_generated_at"] = datetime.now(
                    ).isoformat()
                    outlines[unit_key]["content_word_count"] = word_count
                    project.episode_outlines = outlines
                    flag_modified(project, 'episode_outlines')
                    updated = True

            elif content_type == "movie_script":
                outlines = project.scene_outlines or {}
                if unit_key in outlines:
                    outlines[unit_key]["content_status"] = status
                    outlines[unit_key]["content_generated_at"] = datetime.now(
                    ).isoformat()
                    outlines[unit_key]["content_word_count"] = word_count
                    project.scene_outlines = outlines
                    flag_modified(project, 'scene_outlines')
                    updated = True

            if updated:
                self.logger.debug(
                    f"[状态同步] {content_type} 单元{unit_number}状态已同步: {status}, {word_count}字")
            else:
                self.logger.warning(
                    f"[状态同步] 未找到{content_type} 单元{unit_number}的大纲记录")

            return updated

        except Exception as e:
            self.logger.error(f"[状态同步] 同步状态失败: {e}")
            return False

    def _post_process(self, content: str) -> str:
        """后处理生成内容"""
        # 移除可能的markdown代码块标记
        if content.startswith("```"):
            lines = content.split("\n")
            if len(lines) > 2:
                content = "\n".join(
                    lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        # 移除开头/结尾的空白
        content = content.strip()

        return content

    async def _mark_compliance(
        self,
        project: NovelProject,
        content: str
    ) -> Optional[Dict[str, Any]]:
        """
        合规审核标记（非阻塞）

        检查内容合规性，标记潜在问题，不中断生成流程

        Args:
            project: 项目对象
            content: 章节内容

        Returns:
            合规标记结果字典，包含问题列表
        """
        try:
            # 获取合规配置
            compliance_config = project.compliance_config or {}

            # 检查是否启用合规审核
            if not compliance_config.get("enabled", True):
                self.logger.info("[合规审核] 合规审核已禁用，跳过检查")
                return None

            self.logger.info("[合规审核] 开始检查内容合规性...")

            # 导入合规审核器
            from app.services.compliance.auditor import check_content_compliance

            # 执行合规检查
            result = check_content_compliance(content, compliance_config)

            # 输出明确的审核结果
            if result and result.get("has_issues"):
                issue_count = result.get("issue_count", 0)
                summary = result.get("issue_summary", {})
                self.logger.warning(
                    f"[合规审核] 发现 {issue_count} 处潜在问题 "
                    f"(高危:{summary.get('high', 0)} "
                    f"中等:{summary.get('medium', 0)} "
                    f"低危:{summary.get('low', 0)})"
                )
            else:
                self.logger.info("[合规审核] 内容合规，未发现问题")

            return result

        except Exception as e:
            # 合规审核失败不影响生成流程，仅记录日志
            self.logger.warning(f"[合规审核] 检查失败: {e}")
            return None

    # ==================== 分集详细大纲生成 ====================

    async def generate_episode_outline(
        self,
        project: NovelProject,
        episode_number: int,
        user_guidance: str = None
    ) -> Dict[str, Any]:
        """
        生成单集详细大纲

        Args:
            project: 项目对象
            episode_number: 集数
            user_guidance: 用户提供的概要或参考信息（可选）

        Returns:
            生成结果
        """
        result = {
            "success": False,
            "episode_number": episode_number,
            "content": None,
            "parsed": None,
            "error_message": None
        }

        start_time = time.time()

        try:
            # 检查任务是否被取消
            if await task_manager.is_task_cancelled(project.id):
                result["error_message"] = "生成任务被取消"
                result["cancelled"] = True
                return result

            # 1. 检查基础大纲
            # 记录大纲状态（调试用）
            outline_status = {
                "has_outline_content": bool(project.outline_content),
                "outline_content_len": len(project.outline_content) if project.outline_content else 0,
                "outline_file_path": project.outline_file_path
            }
            self.logger.info(
                f"[分集大纲] 第{episode_number}集生成前大纲状态: {outline_status}")

            # 确保项目数据是最新的（解决会话隔离和Redis问题）
            await self._ensure_fresh_project_data(
                project, required_fields=['outline_content', 'outline_file_path'])

            # 再次检查大纲是否存在
            if not project.outline_content:
                raise Exception("请先上传基础大纲")

            # 调试日志：记录大纲内容状态
            self.logger.info(
                f"[分集大纲] 第{episode_number}集生成前: outline_content长度={len(project.outline_content) if project.outline_content else 0}")

            # 2. 从基础大纲中提取当前分集概要
            # 先对大纲进行格式化处理
            formatted_outline = self._format_outline(
                project.outline_content, "series_script")
            episode_summary = self._extract_episode_summary_from_outline(
                formatted_outline, episode_number
            )

            # 3. 获取LLM提供者
            llm_provider = await self._get_llm_provider(project)
            if not llm_provider:
                raise Exception("无法获取LLM提供者")

            # 4. 获取前序集数的大纲摘要
            previous_summaries = self._get_previous_episodes_summary(
                project, episode_number
            )

            # 5. 构建提示词
            prompt = self._build_episode_outline_prompt(
                project, episode_number, episode_summary, previous_summaries
            )

            self.logger.info(f"开始生成第{episode_number}集详细大纲")

            # 6. 调用LLM生成（带重试机制）
            llm_response = await self._call_with_retry(
                lambda: llm_provider.generate(
                    prompt, temperature=0.7, max_tokens=30000),
                item_name=f"第{episode_number}集详细大纲"
            )

            content = llm_response.content if hasattr(
                llm_response, 'content') else str(llm_response)

            # 7. 解析结构化数据
            parsed_outline = self._parse_episode_outline_content(
                content, episode_number)

            # 8. 保存到项目配置
            await self._save_episode_outline(project, episode_number, parsed_outline)

            # 9. 一致性校验（与小说大纲生成保持一致）
            consistency_result = await self._validate_outline_consistency(
                project, episode_number, parsed_outline, "series_script"
            )
            if consistency_result.get("issues"):
                self.logger.warning(
                    f"[一致性校验] 第{episode_number}集发现{len(consistency_result['issues'])}个问题")
            else:
                self.logger.info(f"[一致性校验] 第{episode_number}集校验通过")

            end_time = time.time()

            result["success"] = True
            result["content"] = content
            result["parsed"] = parsed_outline
            result["duration_ms"] = int((end_time - start_time) * 1000)
            result["consistency"] = consistency_result

            # 10. 触发单元知识图谱构建（如果启用GraphRAG）
            # 注意：kb_graphrag_enabled 可能为 None（旧记录），默认视为启用
            graphrag_enabled = project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True
            self.logger.info(
                f"单元知识图谱触发检查: kb_graphrag_enabled={project.kb_graphrag_enabled}(实际={graphrag_enabled}), "
                f"kb_status={project.kb_status}"
            )

            if graphrag_enabled and project.kb_status == "ready":
                try:
                    # 构建单元大纲内容文本
                    unit_outline_text = parsed_outline.get(
                        "detailed_outline", "")
                    if not unit_outline_text:
                        unit_outline_text = content  # 使用原始生成内容

                    # 异步构建单元图谱（不阻塞主流程）
                    build_result = await self.content_reviser.knowledge_base.build_unit_outline_graph(
                        project_id=project.id,
                        unit_number=episode_number,
                        unit_outline_content=unit_outline_text,
                        llm_provider=llm_provider
                    )

                    if build_result["success"]:
                        self.logger.info(
                            f"单元知识图谱构建完成: 第{episode_number}集, "
                            f"entities={build_result['entity_count']}, relations={build_result['relation_count']}"
                        )
                    else:
                        self.logger.warning(
                            f"单元知识图谱构建失败: 第{episode_number}集, error={build_result.get('error')}"
                        )
                except Exception as kb_error:
                    # 知识图谱构建失败不影响主流程
                    self.logger.warning(
                        f"单元知识图谱构建异常: 第{episode_number}集, error={str(kb_error)}")

            self.logger.info(f"第{episode_number}集详细大纲生成完成")
            return result

        except asyncio.CancelledError:
            self.logger.warning(f"生成分集大纲被取消: 第{episode_number}集")
            result["error_message"] = "生成任务被取消"
            result["cancelled"] = True
            # 确保数据库会话处于干净状态
            await self.db.rollback()
            raise  # 重新抛出以便上层处理
        except Exception as e:
            self.logger.error(f"生成分集大纲失败: 第{episode_number}集, 错误: {str(e)}")
            result["error_message"] = str(e)
            return result

    async def generate_all_episode_outlines(
        self,
        project: NovelProject,
        episode_numbers: Optional[List[int]] = None,
        stop_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        批量生成多集详细大纲

        Args:
            project: 项目对象
            episode_numbers: 要生成的集数列表，None表示生成全部
            stop_on_error: 出错时是否停止

        Returns:
            批量生成结果
        """
        # 确定要生成的集数
        script_config = project.series_script_config or project.script_config or {}
        total_episodes = script_config.get("episode_count", 0)

        if episode_numbers is None:
            episode_numbers = list(range(1, total_episodes + 1))

        result = {
            "project_id": project.id,
            "total_episodes": len(episode_numbers),
            "completed_count": 0,
            "failed_count": 0,
            "episodes": [],
            "errors": []
        }

        # 创建任务状态追踪
        await task_manager.create_task(
            project.id, TASK_TYPE_EPISODE_OUTLINE,
            total_count=len(episode_numbers)
        )

        try:
            for episode_num in episode_numbers:
                # 刷新项目对象以确保获取最新数据（关键：解决断点续传时 outline_content 丢失问题）
                await self.db.refresh(project)

                # 检查任务是否被取消
                if await task_manager.is_task_cancelled(project.id):
                    self.logger.info(f"任务已取消，停止生成: project_id={project.id}")
                    result["cancelled"] = True
                    break

                # 使用带重试的调用方式
                try:
                    gen_result = await self._call_with_retry(
                        lambda: self.generate_episode_outline(
                            project, episode_num),
                        item_name=f"第{episode_num}集大纲"
                    )
                except Exception as e:
                    # 重试失败后，构造失败结果
                    gen_result = {
                        "success": False,
                        "error_message": str(e)
                    }

                result["episodes"].append({
                    "episode_number": episode_num,
                    "success": gen_result["success"],
                    "error": gen_result.get("error_message")
                })

                if gen_result["success"]:
                    result["completed_count"] += 1
                else:
                    result["failed_count"] += 1
                    result["errors"].append({
                        "episode_number": episode_num,
                        "error": gen_result.get("error_message")
                    })
                    if stop_on_error:
                        self.logger.warning(f"生成失败，停止批量生成: 第{episode_num}集")
                        break

                # 更新任务进度
                await task_manager.update_task(
                    project.id,
                    completed_count=result["completed_count"],
                    current_item=episode_num
                )

                # 添加请求间隔，避免触发API速率限制
                if episode_num != episode_numbers[-1]:  # 最后一个不需要等待
                    await asyncio.sleep(self.settings.BATCH_REQUEST_INTERVAL)

            # 标记任务完成
            await task_manager.complete_task(project.id, success=result["failed_count"] == 0)
            return result

        except asyncio.CancelledError:
            self.logger.warning("批量生成分集大纲被取消")
            result["cancelled"] = True
            result["error_message"] = "生成任务被取消"
            await task_manager.cancel_task(project.id)
            await self.db.rollback()
            raise

    # ==================== 批量正文生成方法 ====================

    async def generate_all_episode_content(
        self,
        project: NovelProject,
        episode_numbers: Optional[List[int]] = None,
        stop_on_error: bool = True,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """批量生成多集正文（剧集专用）"""
        script_config = project.series_script_config or project.script_config or {}
        total_episodes = script_config.get("episode_count", 0)

        if episode_numbers is None:
            episode_numbers = list(range(1, total_episodes + 1))

        result = {
            "project_id": project.id,
            "total_episodes": len(episode_numbers),
            "completed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "episodes": [],
            "errors": [],
            "skipped": []
        }

        # 创建任务状态追踪
        await task_manager.create_task(
            project.id, TASK_TYPE_EPISODE_CONTENT,
            total_count=len(episode_numbers)
        )

        try:
            llm_provider = await self._get_llm_provider(project)

            for episode_num in episode_numbers:
                # 刷新项目对象以确保获取最新数据（解决会话隔离问题）
                await self.db.refresh(project)

                # 检查任务是否被取消
                if await task_manager.is_task_cancelled(project.id):
                    self.logger.info(f"任务已取消，停止生成: project_id={project.id}")
                    result["cancelled"] = True
                    break

                episode_outlines = project.episode_outlines or {}
                episode_outline = episode_outlines.get(str(episode_num))

                if not episode_outline:
                    self.logger.warning(f"[批量正文] 第{episode_num}集缺少详细大纲，跳过")
                    result["skipped_count"] += 1
                    result["skipped"].append(
                        {"episode_number": episode_num, "reason": "缺少详细大纲"})
                    continue

                # 使用带重试的调用方式
                try:
                    gen_result = await self._call_with_retry(
                        lambda: self.generate_episode_content(
                            project, episode_num, llm_provider),
                        item_name=f"第{episode_num}集正文"
                    )
                except asyncio.CancelledError:
                    result["cancelled"] = True
                    raise
                except Exception as e:
                    # 重试失败后，构造失败结果
                    gen_result = {
                        "success": False,
                        "error_message": str(e)
                    }

                result["episodes"].append({
                    "episode_number": episode_num,
                    "success": gen_result["success"],
                    "word_count": gen_result.get("word_count", 0),
                    "error": gen_result.get("error_message")
                })

                if gen_result["success"]:
                    result["completed_count"] += 1
                    if progress_callback:
                        await progress_callback(episode_num, "completed", gen_result)
                else:
                    result["failed_count"] += 1
                    result["errors"].append(
                        {"episode_number": episode_num, "error": gen_result.get("error_message")})
                    if stop_on_error:
                        break

                # 更新任务进度
                await task_manager.update_task(
                    project.id,
                    completed_count=result["completed_count"],
                    skipped_count=result["skipped_count"],
                    current_item=episode_num
                )

                # 添加请求间隔，避免触发API速率限制
                if episode_num != episode_numbers[-1]:  # 最后一个不需要等待
                    await asyncio.sleep(self.settings.BATCH_REQUEST_INTERVAL)

            # 标记任务完成
            await task_manager.complete_task(project.id, success=result["failed_count"] == 0)
            return result
        except asyncio.CancelledError:
            self.logger.warning("批量生成正文被取消")
            result["cancelled"] = True
            await task_manager.cancel_task(project.id)
            await self.db.rollback()
            raise

    async def generate_all_chapter_content(
        self,
        project: NovelProject,
        chapter_numbers: Optional[List[int]] = None,
        stop_on_error: bool = True,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """批量生成多章正文（小说专用）"""
        total_chapters = project.total_chapters or 0
        if chapter_numbers is None:
            chapter_numbers = list(range(1, total_chapters + 1))

        result = {
            "project_id": project.id,
            "total_chapters": len(chapter_numbers),
            "completed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "chapters": [],
            "errors": [],
            "skipped": []
        }

        # 创建任务状态追踪
        await task_manager.create_task(
            project.id, TASK_TYPE_CHAPTER_CONTENT,
            total_count=len(chapter_numbers)
        )

        try:
            llm_provider = await self._get_llm_provider(project)

            for chapter_num in chapter_numbers:
                # 刷新项目对象以确保获取最新数据（解决会话隔离问题）
                await self.db.refresh(project)

                # 检查任务是否被取消
                if await task_manager.is_task_cancelled(project.id):
                    self.logger.info(f"任务已取消，停止生成: project_id={project.id}")
                    result["cancelled"] = True
                    break

                chapter_outlines = project.chapter_outlines or {}
                if not chapter_outlines.get(str(chapter_num)):
                    result["skipped_count"] += 1
                    result["skipped"].append(
                        {"chapter_number": chapter_num, "reason": "缺少详细大纲"})
                    continue

                # 使用带重试的调用方式
                try:
                    gen_result = await self._call_with_retry(
                        lambda: self.generate_chapter(
                            project, chapter_num, llm_provider),
                        item_name=f"第{chapter_num}章正文"
                    )
                except asyncio.CancelledError:
                    result["cancelled"] = True
                    raise
                except Exception as e:
                    # 重试失败后，构造失败结果
                    gen_result = {
                        "success": False,
                        "error_message": str(e)
                    }

                result["chapters"].append({
                    "chapter_number": chapter_num,
                    "success": gen_result["success"],
                    "word_count": gen_result.get("word_count", 0),
                    "error": gen_result.get("error_message")
                })

                if gen_result["success"]:
                    result["completed_count"] += 1
                    if progress_callback:
                        await progress_callback(chapter_num, "completed", gen_result)
                else:
                    result["failed_count"] += 1
                    result["errors"].append(
                        {"chapter_number": chapter_num, "error": gen_result.get("error_message")})
                    if stop_on_error:
                        break

                # 更新任务进度
                await task_manager.update_task(
                    project.id,
                    completed_count=result["completed_count"],
                    skipped_count=result["skipped_count"],
                    current_item=chapter_num
                )

                # 添加请求间隔，避免触发API速率限制
                if chapter_num != chapter_numbers[-1]:  # 最后一个不需要等待
                    await asyncio.sleep(self.settings.BATCH_REQUEST_INTERVAL)

            # 标记任务完成
            await task_manager.complete_task(project.id, success=result["failed_count"] == 0)
            return result
        except asyncio.CancelledError:
            self.logger.warning("批量生成正文被取消")
            result["cancelled"] = True
            await task_manager.cancel_task(project.id)
            await self.db.rollback()
            raise

    async def generate_all_scene_content(
        self,
        project: NovelProject,
        scene_numbers: Optional[List[int]] = None,
        stop_on_error: bool = True,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """批量生成多场景正文（电影剧本专用）"""
        total_scenes = project.total_chapters or 0
        if scene_numbers is None:
            scene_numbers = list(range(1, total_scenes + 1))

        result = {
            "project_id": project.id,
            "total_scenes": len(scene_numbers),
            "completed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "scenes": [],
            "errors": [],
            "skipped": []
        }

        # 创建任务状态追踪
        await task_manager.create_task(
            project.id, TASK_TYPE_SCENE_CONTENT,
            total_count=len(scene_numbers)
        )

        try:
            llm_provider = await self._get_llm_provider(project)

            for scene_num in scene_numbers:
                # 刷新项目对象以确保获取最新数据（解决会话隔离问题）
                await self.db.refresh(project)

                # 检查任务是否被取消
                if await task_manager.is_task_cancelled(project.id):
                    self.logger.info(f"任务已取消，停止生成: project_id={project.id}")
                    result["cancelled"] = True
                    break

                scene_outlines = project.scene_outlines or {}
                if not scene_outlines.get(str(scene_num)):
                    result["skipped_count"] += 1
                    result["skipped"].append(
                        {"scene_number": scene_num, "reason": "缺少详细大纲"})
                    continue

                # 使用带重试的调用方式
                try:
                    gen_result = await self._call_with_retry(
                        lambda: self.generate_scene_content(
                            project, scene_num, llm_provider),
                        item_name=f"第{scene_num}场正文"
                    )
                except asyncio.CancelledError:
                    result["cancelled"] = True
                    raise
                except Exception as e:
                    # 重试失败后，构造失败结果
                    gen_result = {
                        "success": False,
                        "error_message": str(e)
                    }

                result["scenes"].append({
                    "scene_number": scene_num,
                    "success": gen_result["success"],
                    "word_count": gen_result.get("word_count", 0),
                    "error": gen_result.get("error_message")
                })

                if gen_result["success"]:
                    result["completed_count"] += 1
                    if progress_callback:
                        await progress_callback(scene_num, "completed", gen_result)
                else:
                    result["failed_count"] += 1
                    result["errors"].append(
                        {"scene_number": scene_num, "error": gen_result.get("error_message")})
                    if stop_on_error:
                        break

                # 更新任务进度
                await task_manager.update_task(
                    project.id,
                    completed_count=result["completed_count"],
                    skipped_count=result["skipped_count"],
                    current_item=scene_num
                )

                # 添加请求间隔，避免触发API速率限制
                if scene_num != scene_numbers[-1]:  # 最后一个不需要等待
                    await asyncio.sleep(self.settings.BATCH_REQUEST_INTERVAL)

            # 标记任务完成
            await task_manager.complete_task(project.id, success=result["failed_count"] == 0)
            return result
        except asyncio.CancelledError:
            self.logger.warning("批量生成正文被取消")
            result["cancelled"] = True
            await task_manager.cancel_task(project.id)
            await self.db.rollback()
            raise

    def _extract_episode_summary_from_outline(
        self,
        outline: str,
        episode_num: int
    ) -> Dict[str, str]:
        """从基础大纲中提取分集概要（参考小说章节提取的成功模式）"""
        import re

        result = {
            "episode_title": f"第{episode_num}集",
            "episode_summary": ""
        }

        if not outline:
            return result

        lines = outline.split('\n')
        capturing = False
        summary_lines = []

        # 中文数字映射
        chinese_nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

        def num_to_chinese(n):
            if n <= 10:
                return chinese_nums[n]
            elif n < 20:
                return '十' + (chinese_nums[n - 10] if n > 10 else '')
            elif n < 100:
                tens = n // 10
                ones = n % 10
                result = chinese_nums[tens] + '十'
                if ones > 0:
                    result += chinese_nums[ones]
                return result
            return str(n)

        chinese_episode = num_to_chinese(episode_num)

        # 匹配当前分集的模式 - 支持多种格式（参考小说章节提取的成功模式，按优先级排序）
        patterns = [
            # 1. Markdown标题格式（带 # 前缀）- 最常用
            rf'^#+\s*第{episode_num}集\s*#*\s*$',  # ### 第1集 ###
            rf'^#+\s*第{episode_num}集[:：\s]',    # ### 第1集：标题
            rf'^#+\s*第{chinese_episode}集\s*#*\s*$',  # ### 第一集 ###
            rf'^#+\s*第{chinese_episode}集[:：\s]',    # ### 第一集：标题
            # 2. 粗体格式
            rf'^\*\*第{episode_num}集\*\*',
            rf'^\*\*第{chinese_episode}集\*\*',
            rf'^\*\*第{episode_num}集[:：\s]',
            rf'^\*\*第{chinese_episode}集[:：\s]',
            # 3. 括号格式
            rf'^【第{episode_num}集】',
            rf'^【第{chinese_episode}集】',
            # 4. 纯文本格式（阿拉伯数字）
            rf'^第{episode_num}集[:：\s]',
            rf'^第{episode_num}集$',
            # 5. 纯文本格式（中文数字）
            rf'^第{chinese_episode}集[:：\s]',
            rf'^第{chinese_episode}集$',
            # 6. 带空格格式
            rf'^第\s*{episode_num}\s*集[:：\s]?',
            rf'^第\s*{chinese_episode}\s*集[:：\s]?',
            # 7. Episode 格式
            rf'^[Ee]pisode\s*{episode_num}[:：\s]?',
            rf'^[Ee]pisode\s*{chinese_episode}[:：\s]?',
            rf'^EP\s*{episode_num}[:：\s]?',
            rf'^Ep\.?\s*{episode_num}[:：\s]?',
            # 8. 纯数字格式
            rf'^{episode_num}[\.、:：\s]+.*集',
            rf'^{episode_num}[\.、]\s*[^\d]',  # "1. 标题" 格式
        ]

        compiled_patterns = [re.compile(p) for p in patterns]

        matched_line_idx = -1
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # 检查是否匹配当前分集标题
            for pattern in compiled_patterns:
                if pattern.match(line_stripped):
                    matched_line_idx = i
                    self.logger.debug(
                        f"[分集概要提取] 第{episode_num}集标题匹配成功: 行{i}, 内容: {line_stripped[:60]}")
                    # 尝试多种标题提取模式（按优先级排序）
                    title_patterns = [
                        # 1. Markdown标题格式
                        rf'^#+\s*第{episode_num}集[:：\s]*(.*?)\s*#*\s*$',
                        rf'^#+\s*第{chinese_episode}集[:：\s]*(.*?)\s*#*\s*$',
                        # 2. 粗体格式
                        rf'^\*\*第{episode_num}集\*\*[:：\s]*(.*)',
                        rf'^\*\*第{chinese_episode}集\*\*[:：\s]*(.*)',
                        rf'^\*\*第{episode_num}集[:：\s]*(.*?)\*\*',
                        rf'^\*\*第{chinese_episode}集[:：\s]*(.*?)\*\*',
                        # 3. 括号格式
                        rf'^【第{episode_num}集】[:：\s]*(.*)',
                        rf'^【第{chinese_episode}集】[:：\s]*(.*)',
                        # 4. 普通格式
                        rf'第{episode_num}集[:：\s]*(.*)',
                        rf'第{chinese_episode}集[:：\s]*(.*)',
                        rf'第\s*{episode_num}\s*集[:：\s]*(.*)',
                        rf'第\s*{chinese_episode}\s*集[:：\s]*(.*)',
                        # 5. Episode格式
                        rf'^[Ee]pisode\s*{episode_num}[:：\s]*(.*)',
                        rf'^EP\s*{episode_num}[:：\s]*(.*)',
                    ]
                    for title_pattern in title_patterns:
                        title_match = re.search(title_pattern, line_stripped)
                        if title_match:
                            title = title_match.group(1).strip()
                            # 移除可能的markdown标记
                            title = re.sub(r'\*+', '', title).strip()
                            title = re.sub(r'#+', '', title).strip()
                            title = re.sub(r'【.*?】', '', title).strip()
                            if title:
                                result["episode_title"] = title
                                break

                    capturing = True
                    continue

            # 检查是否进入下一集
            if capturing:
                # 构建下一集的匹配模式
                next_episode_num = episode_num + 1
                next_chinese_episode = num_to_chinese(next_episode_num)

                # 下一集匹配模式 - 按优先级排序
                next_episode_patterns = [
                    # 1. 优先匹配带 # 前缀的具体下一集
                    rf'^#+\s*第{next_episode_num}集',
                    rf'^#+\s*第{next_chinese_episode}集',
                    # 2. 匹配带 # 前缀的任意集数
                    rf'^#+\s*第\d+集',
                    rf'^#+\s*第[{chinese_nums}]+集',
                    # 3. 不带 # 前缀的具体下一集
                    rf'^第{next_episode_num}集',
                    rf'^第{next_chinese_episode}集',
                    # 4. 括号格式
                    rf'^【第{next_episode_num}集】',
                    rf'^【第{next_chinese_episode}集】',
                    rf'^【第\d+集】',
                    # 5. 其他格式
                    rf'^\*\*第\d+集',
                    rf'^[Ee]pisode\s*{next_episode_num}',
                    rf'^[Ee]pisode\s*\d+',
                    rf'^EP\s*{next_episode_num}',
                    rf'^EP\s*\d+',
                    r'^---+$',
                    r'^___+$',
                    r'^##\s+第',
                ]

                matched_pattern = None
                for pattern in next_episode_patterns:
                    if re.match(pattern, line_stripped):
                        matched_pattern = pattern
                        capturing = False
                        break

                if not capturing:
                    self.logger.debug(
                        f"[分集概要提取] 第{episode_num}集边界检测: 匹配到下一集模式 '{matched_pattern}', 行内容: {line_stripped[:50]}")
                    break

                # 跳过当前集数的标题行
                if line_stripped.startswith('**') and '集' in line_stripped and len(line_stripped) < 50:
                    current_title_patterns = [
                        rf'^\*\*第{episode_num}集',
                        rf'^\*\*第{chinese_episode}集',
                    ]
                    for tp in current_title_patterns:
                        if re.match(tp, line_stripped):
                            continue
                # 跳过纯分隔符行
                if line_stripped in ['---', '***', '___', '']:
                    continue

                # 捕获概要内容
                skip_patterns = [
                    r'^###\s+\d',
                    r'^##\s+创作',
                    r'^##\s+检查',
                ]
                should_skip = False
                for pattern in skip_patterns:
                    if re.match(pattern, line_stripped):
                        should_skip = True
                        break

                if not should_skip:
                    summary_lines.append(line_stripped)

        result["episode_summary"] = '\n'.join(summary_lines).strip()

        # 如果没有提取到概要，使用默认提示
        if not result["episode_summary"]:
            result["episode_summary"] = f"（请根据基础大纲中的人物设定和故事结构，为第{episode_num}集创作详细剧情）"
            self.logger.warning(
                f"[分集概要提取] 第{episode_num}集未提取到概要，使用默认提示。标题匹配行: {matched_line_idx}, 捕获行数: {len(summary_lines)}")
        else:
            self.logger.info(
                f"[分集概要提取] 第{episode_num}集提取成功，标题='{result['episode_title']}', 概要长度={len(result['episode_summary'])}, 标题匹配行: {matched_line_idx}, 捕获行数: {len(summary_lines)}")

        return result

    def _get_previous_episodes_summary(
        self,
        project: NovelProject,
        current_episode: int,
        max_previous: int = 3
    ) -> str:
        """
        获取前序集数的大纲摘要（增强版）

        增强功能：
        1. 获取已生成的详细大纲摘要
        2. 当缺少详细大纲时，从基础大纲中提取概要
        3. 添加全局上下文信息（人物设定、世界观等）

        Args:
            project: 项目对象
            current_episode: 当前集数
            max_previous: 最多获取前几集

        Returns:
            前序集数大纲摘要文本
        """
        summaries = []
        episode_outlines = project.episode_outlines or {}

        start_ep = max(1, current_episode - max_previous)

        for ep in range(start_ep, current_episode):
            ep_outline = episode_outlines.get(str(ep), {})

            # 优先使用已生成的详细大纲
            if ep_outline.get("detailed_outline"):
                summary = ep_outline.get("episode_summary", "")
                title = ep_outline.get("episode_title", f"第{ep}集")
                core_conflict = ep_outline.get("core_conflict", "")

                summary_text = f"第{ep}集《{title}》：{summary[:300]}{'...' if len(summary) > 300 else ''}"
                if core_conflict:
                    summary_text += f"\n  核心冲突：{core_conflict[:100]}"
                summaries.append(summary_text)

            # 如果没有详细大纲，尝试从基础大纲中提取概要
            elif project.outline_content:
                # 先对大纲进行格式化处理
                formatted_outline = self._format_outline(
                    project.outline_content, "series_script")
                basic_summary = self._extract_episode_summary_from_outline(
                    formatted_outline, ep
                )
                if basic_summary.get("episode_summary") and \
                   not basic_summary["episode_summary"].startswith("（请根据"):
                    summaries.append(
                        f"第{ep}集《{basic_summary['episode_title']}》（基础大纲概要）：\n  {basic_summary['episode_summary'][:300]}"
                    )

        # 添加全局上下文信息
        global_context = ""
        if project.outline_content:
            context = self._extract_global_context_from_outline(
                project.outline_content, "series_script"
            )

            context_parts = []
            if context.get("characters"):
                context_parts.append(
                    f"【人物设定摘要】\n{context['characters'][:400]}")
            if context.get("world_setting"):
                context_parts.append(
                    f"【世界观设定】\n{context['world_setting'][:200]}")
            if context.get("main_plot"):
                context_parts.append(f"【故事主线】\n{context['main_plot'][:200]}")

            if context_parts:
                global_context = "\n\n**全局上下文参考：**\n" + \
                    "\n".join(context_parts)

        if summaries:
            return "\n\n".join(summaries) + global_context

        # 如果是第一集，返回全局上下文
        if global_context:
            return f"（无前序集数，这是第一集）\n{global_context}"
        return "（无前序集数，这是第一集）"

    def _build_episode_outline_prompt(
        self,
        project: NovelProject,
        episode_number: int,
        episode_summary: Dict[str, str],
        previous_summaries: str
    ) -> str:
        """
        构建分集详细大纲生成提示词（增强版）

        增强功能：
        1. 检测是否缺少简略大纲
        2. 为缺失大纲的情况提供推断性上下文
        3. 确保与前文内容的一致性

        Args:
            project: 项目对象
            episode_number: 集数
            episode_summary: 当前分集概要
            previous_summaries: 前序集数摘要

        Returns:
            格式化后的提示词
        """
        from app.services.novel_writer.prompt_templates import EPISODE_DETAILED_OUTLINE_PROMPT

        # 获取剧本配置
        script_config = project.series_script_config or project.script_config or {}

        # 格式化时长区间
        duration_range = script_config.get("episode_duration_range", [30, 45])
        if isinstance(duration_range, list) and len(duration_range) == 2:
            duration_str = f"{duration_range[0]}-{duration_range[1]}分钟"
        else:
            duration_str = "30-45分钟"

        # 检测是否缺少简略大纲
        raw_summary = episode_summary.get("episode_summary", "")
        is_missing_outline = not raw_summary or raw_summary.startswith("（请根据")

        # 如果缺少大纲，构建推断性上下文
        enhanced_summary = raw_summary
        if is_missing_outline and project.outline_content:
            # 构建缺失单元的上下文提示
            missing_context = self._build_missing_unit_context(
                outline=project.outline_content,
                unit_number=episode_number,
                content_type="series_script",
                existing_outlines=project.episode_outlines or {}
            )
            enhanced_summary = missing_context
            self.logger.info(f"[详细大纲] 第{episode_number}集缺少简略大纲，已构建推断性上下文")

        # 提取全局上下文用于提示词
        global_context_section = ""
        if project.outline_content:
            context = self._extract_global_context_from_outline(
                project.outline_content, "series_script"
            )
            context_parts = []
            if context.get("core_conflict"):
                context_parts.append(f"【核心冲突】{context['core_conflict']}")
            if context.get("theme"):
                context_parts.append(f"【主题思想】{context['theme']}")
            if context_parts:
                global_context_section = "\n\n**创作参考：**\n" + \
                    "\n".join(context_parts)

        return EPISODE_DETAILED_OUTLINE_PROMPT.format(
            outline_content=project.outline_content[
                :30000] if project.outline_content else "",  # 提高到30000字符，保留更多大纲信息
            episode_number=episode_number,
            episode_title=episode_summary.get(
                "episode_title", f"第{episode_number}集"),
            episode_summary=enhanced_summary,
            previous_episodes_summary=previous_summaries + global_context_section,
            series_type=script_config.get("series_type", "电视剧"),
            episode_duration_range=duration_str,
            format_standard=script_config.get("format_standard", "标准格式"),
            dialogue_narration_ratio=script_config.get(
                "dialogue_narration_ratio", "均衡"),
            target_broadcast=script_config.get("target_broadcast", "未指定")
        )

    def _parse_episode_outline_content(
        self,
        content: str,
        episode_number: int
    ) -> Dict[str, Any]:
        """解析LLM生成的分集大纲内容"""
        import re
        from datetime import datetime

        parsed = {
            "episode_number": episode_number,
            "episode_title": "",
            "episode_summary": "",
            "detailed_outline": content,
            "estimated_duration": None,
            "scenes": [],
            "core_conflict": "",
            "emotional_curve": "",
            "key_dialogues": [],
            "visual_highlights": "",
            "status": "generated",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # 尝试提取集标题（支持多种格式）
        # 格式1: - **集标题**：xxx 或 **集标题**：xxx（Markdown加粗格式）
        title_match = re.search(
            r'\*{0,2}集标题\*{0,2}[：:]\s*(.+?)(?:\n|$)', content)
        if title_match:
            title = title_match.group(1).strip()
            # 移除可能的markdown标记
            title = re.sub(r'\*+', '', title).strip()
            parsed["episode_title"] = title

        # 格式2: # 第X集 标题名 或 ## 第X集：标题名
        if not parsed["episode_title"]:
            title_match = re.search(
                r'^#+\s*第' + str(episode_number) + r'集[：:：]?\s*(.+?)(?:\n|$)', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
                # 移除可能的markdown标记
                title = re.sub(r'\*+', '', title).strip()
                parsed["episode_title"] = title

        # 格式3: **第X集 标题名** 或 第X集《标题名》
        if not parsed["episode_title"]:
            title_match = re.search(r'(?:\*\*)?第' + str(episode_number) +
                                    r'集[《【:：]?\s*([^》】\n]+?)[》】]?(?:\*\*)?(?:\n|$)', content)
            if title_match:
                title = title_match.group(1).strip()
                title = re.sub(r'\*+', '', title).strip()
                if title and title != str(episode_number):
                    parsed["episode_title"] = title

        # 格式4: 列表项中的标题（如 "- 集标题：xxx" 或 "- **集标题**：xxx"）
        if not parsed["episode_title"]:
            title_match = re.search(
                r'[\-\*]\s*\*{0,2}集标题\*{0,2}[：:]\s*(.+?)(?:\n|$)', content)
            if title_match:
                title = title_match.group(1).strip()
                title = re.sub(r'\*+', '', title).strip()
                parsed["episode_title"] = title

        # 尝试提取核心冲突
        conflict_match = re.search(r'核心冲突[：:]\s*(.+?)(?:\n|$)', content)
        if conflict_match:
            parsed["core_conflict"] = conflict_match.group(1).strip()

        # 尝试提取情感曲线
        emotion_match = re.search(r'情感曲线[：:]\s*(.+?)(?:\n|$)', content)
        if emotion_match:
            parsed["emotional_curve"] = emotion_match.group(1).strip()

        # 尝试提取预计时长
        duration_match = re.search(r'预计时长[：:]\s*(\d+)\s*分钟', content)
        if duration_match:
            parsed["estimated_duration"] = int(duration_match.group(1))

        # 尝试提取场景列表
        scene_pattern = r'\|\s*(\d+-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*(\d+)\s*\|'
        scene_matches = re.findall(scene_pattern, content)
        for match in scene_matches:
            parsed["scenes"].append({
                "scene_number": match[0],
                "location": match[1].strip(),
                "interior_exterior": match[2].strip(),
                "time_of_day": match[3].strip(),
                "core_content": match[4].strip(),
                "main_characters": match[5].strip(),
                "estimated_duration": int(match[6])
            })

        return parsed

    async def _save_episode_outline(
        self,
        project: NovelProject,
        episode_number: int,
        parsed_outline: Dict[str, Any]
    ):
        """保存分集详细大纲到项目配置"""
        # 获取现有大纲（确保从数据库获取最新状态）
        existing_outlines = project.episode_outlines or {}

        # 创建新的字典（触发 SQLAlchemy 变更检测）
        updated_outlines = dict(existing_outlines)
        updated_outlines[str(episode_number)] = parsed_outline

        # 重新赋值整个字段，确保 SQLAlchemy 检测到 JSON 字段的变化
        project.episode_outlines = updated_outlines

        # 标记字段已修改（对于某些 SQLAlchemy 版本是必要的）
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(project, 'episode_outlines')

        await self.db.commit()
        await self.db.refresh(project)

        self.logger.info(
            f"第{episode_number}集详细大纲已保存到项目配置，当前共{len(project.episode_outlines)}集大纲")

    # ==================== 连续剧单集正文生成（新版） ====================

    async def generate_episode_content(
        self,
        project: NovelProject,
        episode_number: int,
        llm_provider=None
    ) -> Dict[str, Any]:
        """
        生成连续剧单集正文（完整单集，包含所有场景）

        这是新版生成方法，用于替代旧版的场景拆分生成模式。
        一集生成一条完整的剧本正文，场景作为正文内部结构。

        Args:
            project: 项目对象
            episode_number: 集数
            llm_provider: LLM提供者（可选）

        Returns:
            生成结果
        """
        result = {
            "success": False,
            "episode_number": episode_number,
            "content": None,
            "word_count": 0,
            "token_count": 0,
            "duration_ms": 0,
            "error_message": None
        }

        start_time = time.time()

        try:
            # 1. 检查分集详细大纲是否存在
            episode_outlines = project.episode_outlines or {}
            episode_outline = episode_outlines.get(str(episode_number))

            if not episode_outline:
                raise Exception(f"第{episode_number}集的详细大纲未生成，请先生成分集详细大纲")

            # 2. 获取或创建章节记录（一集对应一章）
            chapter = await self._get_or_create_episode_chapter(project, episode_number)

            if chapter.status == ChapterStatus.COMPLETED:
                result["success"] = True
                result["content"] = chapter.final_content
                result["word_count"] = chapter.word_count
                self.logger.info(f"第{episode_number}集已完成，跳过生成")
                return result

            # 3. 更新状态为生成中
            chapter.status = ChapterStatus.DRAFTING
            await self.db.commit()

            # 4. 获取LLM提供者
            if not llm_provider:
                llm_provider = await self._get_llm_provider(project)

            if not llm_provider:
                raise Exception("无法获取LLM提供者，请检查API配置")

            # 5. 构建上下文
            context = await self.context_manager.build_episode_context(
                project, episode_number
            )

            # 6. 获取集标题
            episode_title = episode_outline.get(
                "episode_title", f"第{episode_number}集")

            # 7. 获取类型配置
            type_config = getattr(project, 'series_script_config', None)
            if not type_config:
                type_config = getattr(project, 'script_config', None)
            generation_config = project.generation_config or {}

            # 8. 构建提示词（使用新的单集正文提示词）
            prompt = get_episode_prompt(
                episode_number=episode_number,
                episode_title=episode_title,
                episode_outline=episode_outline,
                context=context,
                type_config=type_config,
                generation_config=generation_config
            )

            # 调试日志：检查提示词中的大纲内容
            outline_in_context = context.get("outline_content", "")
            episode_outline_text = episode_outline.get("detailed_outline", "")
            previous_episodes_summary = context.get(
                "previous_episodes_summary", "")
            self.logger.info(
                f"[提示词检查] 第{episode_number}集: outline_content长度={len(outline_in_context)}字")
            self.logger.info(
                f"[提示词检查] 第{episode_number}集: episode_outline长度={len(episode_outline_text)}字")
            self.logger.info(
                f"[提示词检查] 第{episode_number}集: previous_episodes_summary长度={len(previous_episodes_summary)}字")
            self.logger.info(
                f"[提示词检查] 第{episode_number}集: 提示词总长度={len(prompt)}字")

            # 检查提示词是否包含大纲关键字
            if "大纲" in prompt:
                self.logger.info(
                    f"[提示词检查] 第{episode_number}集: 提示词中包含'大纲'关键字 ✓")
            else:
                self.logger.warning(
                    f"[提示词检查] 第{episode_number}集: 提示词中未找到'大纲'关键字 ✗")

            self.logger.info(f"开始生成第{episode_number}集正文")

            # 9. 调用LLM生成（带重试机制）
            temperature = generation_config.get("temperature", 0.8)
            # 不再限制max_tokens，让LLM根据提示词中的字数要求自由生成

            llm_response = await self._call_with_retry(
                lambda: llm_provider.generate(
                    prompt, temperature=temperature),
                item_name=f"第{episode_number}集正文"
            )

            # 提取响应内容
            if hasattr(llm_response, 'content'):
                content = llm_response.content
            else:
                content = str(llm_response)

            # 提取Token使用量
            token_count = 0
            if hasattr(llm_response, 'usage') and llm_response.usage:
                usage = llm_response.usage
                if isinstance(usage, dict):
                    token_count = usage.get('total_tokens', 0)
                else:
                    token_count = getattr(usage, 'total_tokens', 0)

                if token_count > 0:
                    project.total_tokens = (
                        project.total_tokens or 0) + token_count

            # 10. 基于知识库自动修正（如果启用）
            if project.kb_graphrag_enabled and project.kb_status == "ready":
                self.logger.info(f"开始知识库修正: 第{episode_number}集")
                revision_result = await self.content_reviser.revise_content(
                    project=project,
                    unit_number=episode_number,
                    draft_content=content,
                    llm_provider=llm_provider,
                    content_type="series_script"
                )
                if revision_result["success"] and revision_result.get("revised_content"):
                    original_len = len(content)
                    content = revision_result["revised_content"]
                    self.logger.info(
                        f"知识库修正完成: 第{episode_number}集, "
                        f"原文{original_len}字 -> 修正后{len(content)}字, "
                        f"知识库引用: {revision_result.get('knowledge_used', {})}"
                    )
                else:
                    self.logger.info(
                        f"知识库修正跳过: 第{episode_number}集, 原因: {revision_result.get('error', '未知')}"
                    )

            # 11. 后处理
            content = self._post_process(content)

            # 记录字数信息（用于日志）
            words_per_episode = 5000  # 默认值
            if type_config:
                words_per_episode = type_config.get("words_per_episode", 5000)
            actual_words = len(content)
            self.logger.info(
                f"第{episode_number}集生成完成: 目标{words_per_episode}字, 实际{actual_words}字, "
                f"偏差{((actual_words - words_per_episode) / words_per_episode * 100):.1f}%"
            )

            # 12. 定稿处理
            await self._finalize_chapter(project, chapter, content, llm_provider)

            # 13. 更新结果
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)

            result["success"] = True
            result["content"] = content
            result["word_count"] = len(content)
            result["token_count"] = token_count
            result["duration_ms"] = duration_ms

            # 更新章节记录
            chapter.status = ChapterStatus.COMPLETED
            chapter.final_content = content
            chapter.word_count = len(content)
            chapter.token_count = token_count
            chapter.duration_ms = duration_ms
            chapter.chapter_title = f"第{episode_number}集 {episode_title}"

            # 更新项目进度
            await self._update_project_progress(project, episode_number)

            # 14. 更新 episode_outlines 中的正文生成状态
            episode_outline["content_status"] = "generated"
            episode_outline["content_generated_at"] = datetime.now(
            ).isoformat()
            episode_outline["content_word_count"] = len(content)
            episode_outlines[str(episode_number)] = episode_outline
            project.episode_outlines = episode_outlines
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(project, 'episode_outlines')

            await self.db.commit()

            self.logger.info(
                f"第{episode_number}集正文生成完成, 字数: {len(content)}")
            return result

        except Exception as e:
            self.logger.error(f"生成第{episode_number}集正文失败: {str(e)}")
            result["error_message"] = str(e)

            # 更新错误状态
            try:
                chapter = await self._get_or_create_episode_chapter(project, episode_number)
                chapter.status = ChapterStatus.FAILED
                chapter.error_message = str(e)
                await self.db.commit()
            except Exception as update_error:
                self.logger.warning(f"更新章节错误状态失败: {str(update_error)}")

            return result

    async def _get_or_create_episode_chapter(
        self,
        project: NovelProject,
        episode_number: int
    ) -> NovelChapter:
        """获取或创建单集章节（一集对应一章）"""
        # 查找现有章节（按episode_number查找）
        query = select(NovelChapter).where(
            NovelChapter.project_id == project.id,
            NovelChapter.episode_number == episode_number
        )
        result = await self.db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            # 获取集标题
            episode_outlines = project.episode_outlines or {}
            ep_outline = episode_outlines.get(str(episode_number), {})
            episode_title = ep_outline.get('episode_title', '')

            if episode_title:
                chapter_title = f"第{episode_number}集 {episode_title}"
            else:
                chapter_title = f"第{episode_number}集"

            chapter = NovelChapter(
                project_id=project.id,
                chapter_number=episode_number,
                chapter_title=chapter_title,
                episode_number=episode_number,
                scene_number=None,  # 不再使用场景号
                status=ChapterStatus.PENDING
            )
            self.db.add(chapter)
            await self.db.commit()
            await self.db.refresh(chapter)

        return chapter

    # ==================== 小说章节详细大纲生成 ====================

    async def generate_chapter_outline(
        self,
        project: NovelProject,
        chapter_number: int,
        force_regenerate: bool = False,
        user_guidance: str = None
    ) -> Dict[str, Any]:
        """
        生成单章详细大纲（小说专用）

        Args:
            project: 项目对象
            chapter_number: 章节号
            force_regenerate: 是否强制重新生成（即使已存在详细大纲）
            user_guidance: 用户提供的概要或参考信息（可选）

        Returns:
            生成结果
        """
        result = {
            "success": False,
            "chapter_number": chapter_number,
            "content": None,
            "parsed": None,
            "error_message": None
        }

        start_time = time.time()
        item_name = f"第{chapter_number}章"

        try:
            # 检查任务是否被取消
            if await task_manager.is_task_cancelled(project.id):
                result["error_message"] = "生成任务被取消"
                result["cancelled"] = True
                return result

            # 步骤1：检查是否已存在详细大纲
            await task_manager.update_task_step(
                project.id, "outline_check", f"正在检查详细大纲状态...", "running", "Document", item_name
            )

            chapter_outlines = project.chapter_outlines or {}
            existing_outline = chapter_outlines.get(str(chapter_number), {})

            if existing_outline.get("detailed_outline") and not force_regenerate:
                # 已存在详细大纲且不强制重新生成
                self.logger.info(f"[章节大纲] 第{chapter_number}章已存在详细大纲，跳过生成")
                await task_manager.update_task_step(
                    project.id, "outline_check", "已存在详细大纲，跳过生成", "done", "Document", item_name
                )
                result["success"] = True
                result["content"] = existing_outline.get("detailed_outline")
                result["parsed"] = existing_outline
                result["skipped"] = True
                result["message"] = "已存在详细大纲，跳过生成"
                return result

            # 步骤2：检查基础大纲（支持两阶段大纲机制）
            await task_manager.update_task_step(
                project.id, "outline_check", f"正在检查基础大纲...", "running", "Document", item_name
            )

            # 记录大纲状态（调试用）
            outline_status = {
                "has_outline_content": bool(project.outline_content),
                "outline_content_len": len(project.outline_content) if project.outline_content else 0,
                "outline_file_path": project.outline_file_path,
                "has_global_outline": bool(getattr(project, 'global_outline_content', None)),
                "global_outline_len": len(project.global_outline_content) if hasattr(project, 'global_outline_content') and project.global_outline_content else 0,
                "has_unit_summaries": bool(getattr(project, 'unit_summaries', None)),
                "unit_summaries_count": len(getattr(project, 'unit_summaries', {}) or {})
            }
            self.logger.info(
                f"[章节大纲] 第{chapter_number}章生成前大纲状态: {outline_status}")

            # 确保项目数据是最新的（解决会话隔离和Redis问题）
            await self._ensure_fresh_project_data(
                project, required_fields=['outline_content', 'outline_file_path', 'global_outline_content', 'unit_summaries'])

            # 再次检查大纲是否存在（支持两阶段大纲）
            has_outline = bool(project.outline_content)
            has_global_outline = bool(
                getattr(project, 'global_outline_content', None))
            has_unit_summaries = bool(getattr(project, 'unit_summaries', None))

            # 至少需要一种大纲数据（基础大纲、全局大纲或单元概述）
            if not has_outline and not has_global_outline and not has_unit_summaries:
                await task_manager.update_task_step(
                    project.id, "outline_check", "大纲数据检查失败", "error", "Document", item_name
                )
                raise Exception("请先上传基础大纲、生成全局大纲或上传单元概述")

            await task_manager.update_task_step(
                project.id, "outline_check", "基础大纲检查完成", "done", "Document", item_name
            )

            # 调试日志：记录大纲内容状态
            self.logger.info(
                f"[章节大纲] 第{chapter_number}章生成前: outline_content长度={len(project.outline_content) if project.outline_content else 0}, "
                f"global_outline长度={len(project.global_outline_content) if hasattr(project, 'global_outline_content') and project.global_outline_content else 0}")

            # 步骤2：提取章节概要（支持两阶段大纲）
            await task_manager.update_task_step(
                project.id, "extract_summary", "正在提取章节概要...", "running", "Reading", item_name
            )

            # 优先使用两阶段大纲的单元概述
            chapter_summary = None
            unit_summaries = getattr(project, 'unit_summaries', None) or {}
            unit_key = str(chapter_number)

            # 如果 unit_summaries 为空但项目有 total_chapters，尝试从数据库重新加载
            if not unit_summaries and project.total_chapters and project.total_chapters > 0:
                self.logger.warning(
                    f"[章节大纲] unit_summaries 为空，尝试从数据库重新加载: project_id={project.id}")
                try:
                    from sqlalchemy import select
                    fresh_query = select(NovelProject).where(
                        NovelProject.id == project.id)
                    fresh_result = await self.db.execute(fresh_query)
                    fresh_project = fresh_result.scalar_one_or_none()
                    if fresh_project:
                        fresh_summaries = getattr(
                            fresh_project, 'unit_summaries', None)
                        if fresh_summaries:
                            unit_summaries = fresh_summaries
                            # 同步更新 project 对象
                            project.unit_summaries = fresh_summaries
                            self.logger.info(
                                f"[章节大纲] 从数据库重新加载 unit_summaries 成功: {len(unit_summaries)} 个单元")
                except Exception as e:
                    self.logger.error(f"[章节大纲] 重新加载 unit_summaries 失败: {e}")

            if unit_key in unit_summaries:
                unit_data = unit_summaries[unit_key]
                # 确保chapter_summary是字典格式，与后续代码保持一致
                if isinstance(unit_data, dict):
                    summary_text = unit_data.get('summary', '')
                    chapter_summary = {
                        "chapter_summary": summary_text,
                        "chapter_title": unit_data.get('title', f'第{chapter_number}章')
                    }
                    self.logger.info(
                        f"[章节大纲] 使用两阶段单元概述: 第{chapter_number}章, "
                        f"title={unit_data.get('title', 'N/A')}, summary_len={len(summary_text)}")
                else:
                    # 兼容旧数据格式（unit_data可能是字符串）
                    chapter_summary = {
                        "chapter_summary": str(unit_data) if unit_data else '',
                        "chapter_title": f'第{chapter_number}章'
                    }
                    self.logger.info(
                        f"[章节大纲] 使用两阶段单元概述(旧格式): 第{chapter_number}章, summary_len={len(str(unit_data) if unit_data else '')}")
            else:
                self.logger.warning(
                    f"[章节大纲] unit_summaries 中未找到第{chapter_number}章, "
                    f"可用keys: {list(unit_summaries.keys())[:5]}... (共{len(unit_summaries)}个)")

            # 回退：从基础大纲中提取当前章节概要
            if not chapter_summary or not chapter_summary.get('chapter_summary'):
                if project.outline_content:
                    self.logger.info(
                        f"[章节大纲] 从基础大纲提取章节概要: 第{chapter_number}章")
                    formatted_outline = self._format_outline(
                        project.outline_content, "novel")
                    extracted_summary = self._extract_chapter_summary_from_outline(
                        formatted_outline, chapter_number
                    )
                    # 确保返回的是字典格式
                    if isinstance(extracted_summary, dict):
                        chapter_summary = extracted_summary
                    else:
                        chapter_summary = {
                            "chapter_summary": str(extracted_summary) if extracted_summary else '',
                            "chapter_title": f'第{chapter_number}章'
                        }
                    self.logger.info(
                        f"[章节大纲] 从基础大纲提取章节概要完成: 第{chapter_number}章, summary_len={len(chapter_summary.get('chapter_summary', ''))}")
                else:
                    self.logger.warning(
                        f"[章节大纲] 第{chapter_number}章无法获取章节概要（无两阶段单元概述，也无基础大纲）")

            await task_manager.update_task_step(
                project.id, "extract_summary", "章节概要提取完成", "done", "Reading", item_name
            )

            # 步骤3：获取LLM提供者
            await task_manager.update_task_step(
                project.id, "load_model", "正在加载AI模型...", "running", "Cpu", item_name
            )
            llm_provider = await self._get_llm_provider(project)
            if not llm_provider:
                await task_manager.update_task_step(
                    project.id, "load_model", "AI模型加载失败", "error", "Cpu", item_name
                )
                raise Exception("无法获取LLM提供者")
            await task_manager.update_task_step(
                project.id, "load_model", f"已加载模型: {llm_provider.model_name}", "done", "Cpu", item_name
            )

            # 步骤4：获取前序章节摘要
            await task_manager.update_task_step(
                project.id, "context_build", "正在构建上下文...", "running", "DataAnalysis", item_name
            )
            # 获取前序章节的大纲摘要
            previous_summaries = self._get_previous_chapters_summary(
                project, chapter_number
            )
            await task_manager.update_task_step(
                project.id, "context_build", "上下文构建完成", "done", "DataAnalysis", item_name
            )

            # 步骤5：构建提示词
            await task_manager.update_task_step(
                project.id, "prompt_build", "正在构建提示词...", "running", "Document", item_name
            )
            prompt = self._build_chapter_outline_prompt(
                project, chapter_number, chapter_summary, previous_summaries,
                user_guidance=user_guidance
            )
            await task_manager.update_task_step(
                project.id, "prompt_build", "提示词构建完成", "done", "Document", item_name
            )

            self.logger.info(f"开始生成第{chapter_number}章详细大纲")

            # 步骤6：调用LLM生成
            await task_manager.update_task_step(
                project.id, "llm_generate", "正在调用AI生成内容...", "running", "ChatDotRound", item_name
            )
            # 调用LLM生成（带重试机制）
            llm_response = await self._call_with_retry(
                lambda: llm_provider.generate(
                    prompt, temperature=0.7, max_tokens=30000),
                item_name=f"第{chapter_number}章详细大纲"
            )

            content = llm_response.content if hasattr(
                llm_response, 'content') else str(llm_response)
            await task_manager.update_task_step(
                project.id, "llm_generate", "AI内容生成完成", "done", "ChatDotRound", item_name
            )

            # 步骤7：解析结构化数据
            await task_manager.update_task_step(
                project.id, "parse_content", "正在解析生成内容...", "running", "Edit", item_name
            )
            parsed_outline = self._parse_chapter_outline_content(
                content, chapter_number)
            await task_manager.update_task_step(
                project.id, "parse_content", "内容解析完成", "done", "Edit", item_name
            )

            # 步骤7.5：逻辑一致性修正
            original_outline_content = content  # 保存原始内容
            outline_revision_info = None

            # 获取全局大纲设定
            global_context = project.global_outline_content or project.outline_content or ""

            # 获取前序章节摘要
            previous_context = self._get_previous_chapters_summary(
                project, chapter_number)

            if global_context or previous_context:
                await task_manager.update_task_step(
                    project.id, "logic_revision", "正在进行逻辑一致性修正...", "running", "Edit", item_name
                )

                revision_result = await self.content_reviser.revise_outline_content(
                    project=project,
                    unit_number=chapter_number,
                    outline_content=content,
                    global_context=global_context,
                    previous_context=previous_context,
                    llm_provider=llm_provider,
                    content_type="novel"
                )

                if revision_result["success"] and revision_result.get("has_changes"):
                    # 有实际修改
                    original_len = len(content)
                    content = revision_result["revised_content"]
                    # 重新解析修正后的内容
                    parsed_outline = self._parse_chapter_outline_content(
                        content, chapter_number)

                    outline_revision_info = {
                        "applied": True,
                        "original_length": original_len,
                        "revised_length": len(content),
                        "revised_at": datetime.now().isoformat()
                    }

                    self.logger.info(
                        f"章节大纲逻辑修正完成: 第{chapter_number}章, "
                        f"原文{original_len}字 -> 修正后{len(content)}字"
                    )
                    await task_manager.update_task_step(
                        project.id, "logic_revision",
                        f"逻辑修正完成，原文{original_len}字 → 修正后{len(content)}字",
                        "done", "Edit", item_name
                    )
                else:
                    # 无修改或修正失败
                    self.logger.info(
                        f"章节大纲逻辑修正跳过: 第{chapter_number}章, 原因: {revision_result.get('error', '无修改')}"
                    )
                    await task_manager.update_task_step(
                        project.id, "logic_revision", "逻辑检查完成，无需修正", "done", "CircleCheck", item_name
                    )
            else:
                self.logger.info(f"缺少上下文，跳过章节大纲逻辑修正: 第{chapter_number}章")

            # 步骤8：保存结果
            await task_manager.update_task_step(
                project.id, "save_result", "正在保存结果...", "running", "Folder", item_name
            )
            await self._save_chapter_outline(
                project, chapter_number, parsed_outline,
                original_content=original_outline_content,
                revision_info=outline_revision_info
            )
            await task_manager.update_task_step(
                project.id, "save_result", "结果保存完成", "done", "Folder", item_name
            )

            # 步骤9：一致性校验
            await task_manager.update_task_step(
                project.id, "consistency_check", "正在进行一致性校验...", "running", "CircleCheck", item_name
            )
            consistency_result = await self._validate_outline_consistency(
                project, chapter_number, parsed_outline, "novel"
            )
            if consistency_result.get("issues"):
                self.logger.warning(
                    f"[一致性校验] 第{chapter_number}章发现{len(consistency_result['issues'])}个问题")
                await task_manager.update_task_step(
                    project.id, "consistency_check",
                    f"一致性校验完成，发现{len(consistency_result['issues'])}个问题",
                    "warning", "Warning", item_name
                )
            else:
                await task_manager.update_task_step(
                    project.id, "consistency_check", "一致性校验通过", "done", "CircleCheck", item_name
                )

            end_time = time.time()

            result["success"] = True
            result["content"] = content
            result["parsed"] = parsed_outline
            result["duration_ms"] = int((end_time - start_time) * 1000)
            result["consistency"] = consistency_result

            # 10. 触发单元知识图谱构建（如果启用GraphRAG）
            # 注意：kb_graphrag_enabled 可能为 None（旧记录），默认视为启用
            graphrag_enabled = project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True
            self.logger.info(
                f"单元知识图谱触发检查: kb_graphrag_enabled={project.kb_graphrag_enabled}(实际={graphrag_enabled}), "
                f"kb_status={project.kb_status}"
            )

            if graphrag_enabled and project.kb_status == "ready":
                try:
                    # 构建单元大纲内容文本
                    unit_outline_text = parsed_outline.get(
                        "detailed_outline", "")
                    if not unit_outline_text:
                        unit_outline_text = content  # 使用原始生成内容

                    # 异步构建单元图谱（不阻塞主流程）
                    build_result = await self.content_reviser.knowledge_base.build_unit_outline_graph(
                        project_id=project.id,
                        unit_number=chapter_number,
                        unit_outline_content=unit_outline_text,
                        llm_provider=llm_provider
                    )

                    if build_result["success"]:
                        self.logger.info(
                            f"单元知识图谱构建完成: 第{chapter_number}章, "
                            f"entities={build_result['entity_count']}, relations={build_result['relation_count']}"
                        )
                    else:
                        self.logger.warning(
                            f"单元知识图谱构建失败: 第{chapter_number}章, error={build_result.get('error')}"
                        )
                except Exception as kb_error:
                    # 知识图谱构建失败不影响主流程
                    self.logger.warning(
                        f"单元知识图谱构建异常: 第{chapter_number}章, error={str(kb_error)}")

            self.logger.info(f"第{chapter_number}章详细大纲生成完成")
            return result

        except asyncio.CancelledError:
            self.logger.warning(f"生成章节大纲被取消: 第{chapter_number}章")
            result["error_message"] = "生成任务被取消"
            result["cancelled"] = True
            await self.db.rollback()
            raise
        except Exception as e:
            self.logger.error(f"生成章节大纲失败: 第{chapter_number}章, 错误: {str(e)}")
            result["error_message"] = str(e)
            return result

    async def generate_all_chapter_outlines(
        self,
        project: NovelProject,
        chapter_numbers: Optional[List[int]] = None,
        stop_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        批量生成多章详细大纲（小说专用，自动接受推断内容）

        Args:
            project: 项目对象
            chapter_numbers: 要生成的章节号列表
            stop_on_error: 出错时是否停止

        Returns:
            生成结果
        """
        # 确定要生成的章节数
        total_chapters = project.total_chapters or 0

        if chapter_numbers is None:
            chapter_numbers = list(range(1, total_chapters + 1))

        result = {
            "project_id": project.id,
            "total_chapters": len(chapter_numbers),
            "completed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "chapters": [],
            "errors": []
        }

        # 创建任务状态追踪
        await task_manager.create_task(
            project.id, TASK_TYPE_CHAPTER_OUTLINE,
            total_count=len(chapter_numbers)
        )

        try:
            for chapter_num in chapter_numbers:
                # 刷新项目对象以确保获取最新数据
                await self.db.refresh(project)

                # 检查任务是否被取消
                if await task_manager.is_task_cancelled(project.id):
                    self.logger.info(f"任务已取消，停止生成: project_id={project.id}")
                    result["cancelled"] = True
                    break

                # 直接调用生成方法，自动接受推断内容
                try:
                    gen_result = await self._call_with_retry(
                        lambda: self.generate_chapter_outline(
                            project, chapter_num),
                        item_name=f"第{chapter_num}章大纲"
                    )
                except Exception as e:
                    gen_result = {
                        "success": False,
                        "error_message": str(e)
                    }

                # 处理生成结果
                if gen_result.get("success"):
                    if gen_result.get("skipped"):
                        result["skipped_count"] += 1
                        result["chapters"].append({
                            "chapter_number": chapter_num,
                            "success": True,
                            "status": "skipped_exists"
                        })
                        self.logger.info(f"[批量生成] 第{chapter_num}章已存在详细大纲，跳过")
                    else:
                        result["completed_count"] += 1
                        result["chapters"].append({
                            "chapter_number": chapter_num,
                            "success": True,
                            "status": "generated"
                        })
                        self.logger.info(f"[批量生成] 第{chapter_num}章详细大纲生成成功")
                else:
                    # 生成失败
                    result["failed_count"] += 1
                    result["errors"].append({
                        "chapter_number": chapter_num,
                        "error": gen_result.get("error_message", "未知错误")
                    })
                    result["chapters"].append({
                        "chapter_number": chapter_num,
                        "success": False,
                        "status": "failed",
                        "error": gen_result.get("error_message")
                    })
                    if stop_on_error:
                        self.logger.warning(f"生成失败，停止批量生成: 第{chapter_num}章")
                        break

                # 更新任务进度
                await task_manager.update_task(
                    project.id,
                    completed_count=result["completed_count"],
                    current_item=chapter_num
                )

                # 添加请求间隔，避免触发API速率限制
                if chapter_num != chapter_numbers[-1]:
                    await asyncio.sleep(self.settings.BATCH_REQUEST_INTERVAL)

            # 标记任务完成
            await task_manager.complete_task(project.id, success=result["failed_count"] == 0)
            return result

        except asyncio.CancelledError:
            self.logger.warning("批量生成章节大纲被取消")
            result["cancelled"] = True
            result["error_message"] = "生成任务被取消"
            await task_manager.cancel_task(project.id)
            await self.db.rollback()
            raise

    def _extract_chapter_summary_from_outline(
        self,
        outline: str,
        chapter_num: int
    ) -> Dict[str, str]:
        """从基础大纲中提取章节概要"""
        import re

        result = {
            "chapter_title": f"第{chapter_num}章",
            "chapter_summary": ""
        }

        if not outline:
            return result

        lines = outline.split('\n')
        capturing = False
        summary_lines = []

        # 中文数字映射
        chinese_nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

        def num_to_chinese(n):
            if n <= 10:
                return chinese_nums[n]
            elif n < 20:
                return '十' + (chinese_nums[n - 10] if n > 10 else '')
            elif n < 100:
                tens = n // 10
                ones = n % 10
                result = chinese_nums[tens] + '十'
                if ones > 0:
                    result += chinese_nums[ones]
                return result
            return str(n)

        chinese_chapter = num_to_chinese(chapter_num)

        # 匹配当前章节的模式 - 支持多种格式（按优先级排序）
        patterns = [
            # 1. Markdown标题格式（带 # 前缀）- 最常用
            rf'^#+\s*第{chapter_num}章\s*#*\s*$',  # ### 第1章 ### 或 ### 第1章
            rf'^#+\s*第{chapter_num}章[:：\s]',    # ### 第1章：标题
            rf'^#+\s*第{chinese_chapter}章\s*#*\s*$',  # ### 第一章 ###
            rf'^#+\s*第{chinese_chapter}章[:：\s]',    # ### 第一章：标题
            # 2. 粗体格式
            rf'^\*\*第{chapter_num}章\*\*',
            rf'^\*\*第{chinese_chapter}章\*\*',
            rf'^\*\*第{chapter_num}章[:：\s]',
            rf'^\*\*第{chinese_chapter}章[:：\s]',
            # 3. 纯文本格式（阿拉伯数字）
            rf'^第{chapter_num}章[:：\s]',
            rf'^第{chapter_num}章$',
            # 4. 纯文本格式（中文数字）
            rf'^第{chinese_chapter}章[:：\s]',
            rf'^第{chinese_chapter}章$',
            # 5. 带空格格式
            rf'^第\s*{chapter_num}\s*章[:：\s]?',
            rf'^第\s*{chinese_chapter}\s*章[:：\s]?',
            # 6. Chapter 格式
            rf'^[Cc]hapter\s*{chapter_num}[:：\s]?',
            rf'^[Cc]hapter\s*{chinese_chapter}[:：\s]?',
            # 7. 纯数字格式
            rf'^{chapter_num}[\.、:：\s]+[^\d]',  # "1. 标题" 或 "1、标题"
        ]

        compiled_patterns = [re.compile(p) for p in patterns]

        matched_line_idx = -1
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # 检查是否匹配当前章节标题
            for pattern in compiled_patterns:
                if pattern.match(line_stripped):
                    matched_line_idx = i
                    self.logger.debug(
                        f"[章节概要提取] 第{chapter_num}章标题匹配成功: 行{i}, 内容: {line_stripped[:60]}")
                    # 尝试多种标题提取模式（按优先级排序）
                    title_patterns = [
                        # 1. Markdown标题格式（带 # 前缀和可能的尾部 #）
                        rf'^#+\s*第{chapter_num}章[:：\s]*(.*?)\s*#*\s*$',
                        rf'^#+\s*第{chinese_chapter}章[:：\s]*(.*?)\s*#*\s*$',
                        # 2. 粗体格式
                        rf'^\*\*第{chapter_num}章\*\*[:：\s]*(.*)',
                        rf'^\*\*第{chinese_chapter}章\*\*[:：\s]*(.*)',
                        rf'^\*\*第{chapter_num}章[:：\s]*(.*?)\*\*',
                        rf'^\*\*第{chinese_chapter}章[:：\s]*(.*?)\*\*',
                        # 3. 普通格式
                        rf'第{chapter_num}章[:：\s]*(.*)',
                        rf'第{chinese_chapter}章[:：\s]*(.*)',
                        rf'第\s*{chapter_num}\s*章[:：\s]*(.*)',
                        rf'第\s*{chinese_chapter}\s*章[:：\s]*(.*)',
                    ]
                    for title_pattern in title_patterns:
                        title_match = re.search(title_pattern, line_stripped)
                        if title_match:
                            title = title_match.group(1).strip()
                            # 移除可能的markdown标记
                            title = re.sub(r'\*+', '', title).strip()
                            title = re.sub(r'#+', '', title).strip()
                            if title:
                                result["chapter_title"] = title
                                break

                    capturing = True
                    continue

            # 检查是否进入下一章
            if capturing:
                # 构建下一章的匹配模式
                next_chapter_num = chapter_num + 1
                next_chinese_chapter = num_to_chinese(next_chapter_num)

                # 下一章匹配模式 - 按优先级排序（先匹配具体的，再匹配通用的）
                next_chapter_patterns = [
                    # 1. 优先匹配带 # 前缀的具体下一章（阿拉伯数字）
                    rf'^#+\s*第{next_chapter_num}章',
                    # 2. 优先匹配带 # 前缀的具体下一章（中文数字）
                    rf'^#+\s*第{next_chinese_chapter}章',
                    # 3. 匹配带 # 前缀的任意章节
                    rf'^#+\s*第\d+章',
                    rf'^#+\s*第[{chinese_nums}]+章',
                    # 4. 不带 # 前缀的具体下一章
                    rf'^第{next_chapter_num}章',
                    rf'^第{next_chinese_chapter}章',
                    # 5. 其他格式
                    rf'^\*\*第\d+章',
                    rf'^[Cc]hapter\s*{next_chapter_num}',
                    rf'^[Cc]hapter\s*\d+',
                    r'^---+$',
                    r'^##\s+第',
                ]

                matched_pattern = None
                for pattern in next_chapter_patterns:
                    if re.match(pattern, line_stripped):
                        matched_pattern = pattern
                        capturing = False
                        break

                if not capturing:
                    self.logger.debug(
                        f"[章节概要提取] 第{chapter_num}章边界检测: 匹配到下一章模式 '{matched_pattern}', 行内容: {line_stripped[:50]}")
                    break

                # 跳过当前章节的标题行（只跳过标题行本身，不是下一章的标题）
                # 注意：这里只跳过当前章节的标题行，不跳过内容
                if line_stripped.startswith('**') and '章' in line_stripped and len(line_stripped) < 30:
                    # 检查是否是当前章节的标题
                    current_title_patterns = [
                        rf'^\*\*第{chapter_num}章',
                        rf'^\*\*第{chinese_chapter}章',
                    ]
                    for tp in current_title_patterns:
                        if re.match(tp, line_stripped):
                            continue
                # 跳过纯分隔符行
                if line_stripped in ['---', '***', '___', '']:
                    continue

                # 捕获概要内容
                skip_patterns = [
                    r'^###\s+\d',
                    r'^##\s+创作',
                    r'^##\s+检查',
                ]
                should_skip = False
                for pattern in skip_patterns:
                    if re.match(pattern, line_stripped):
                        should_skip = True
                        break

                if not should_skip:
                    summary_lines.append(line_stripped)

        result["chapter_summary"] = '\n'.join(summary_lines).strip()

        if not result["chapter_summary"]:
            result["chapter_summary"] = f"（请根据基础大纲中的人物设定和故事结构，为第{chapter_num}章创作详细内容）"
            self.logger.warning(
                f"[章节概要提取] 第{chapter_num}章未提取到概要，使用默认提示。标题匹配行: {matched_line_idx}, 捕获行数: {len(summary_lines)}")
        else:
            self.logger.info(
                f"[章节概要提取] 第{chapter_num}章提取成功，标题='{result['chapter_title']}', 概要长度={len(result['chapter_summary'])}, 标题匹配行: {matched_line_idx}, 捕获行数: {len(summary_lines)}")

        return result

    def _get_previous_chapters_summary(
        self,
        project: NovelProject,
        current_chapter: int,
        max_previous: int = 3
    ) -> str:
        """
        获取前序章节的大纲摘要（增强版）

        增强功能：
        1. 获取已生成的详细大纲摘要
        2. 当缺少详细大纲时，从基础大纲中提取概要
        3. 添加全局上下文信息（人物设定、世界观等）

        Args:
            project: 项目对象
            current_chapter: 当前章节号
            max_previous: 最多获取前几章

        Returns:
            前序章节大纲摘要文本
        """
        summaries = []
        chapter_outlines = project.chapter_outlines or {}

        start_ch = max(1, current_chapter - max_previous)

        for ch in range(start_ch, current_chapter):
            ch_outline = chapter_outlines.get(str(ch), {})

            # 优先使用已生成的详细大纲
            if ch_outline.get("detailed_outline"):
                summary = ch_outline.get("chapter_summary", "")
                title = ch_outline.get("chapter_title", f"第{ch}章")
                key_events = ch_outline.get("key_events", [])

                summary_text = f"第{ch}章《{title}》：{summary[:300]}{'...' if len(summary) > 300 else ''}"
                if key_events and isinstance(key_events, list) and len(key_events) > 0:
                    events_str = "；".join(key_events[:3]) if len(
                        key_events) > 3 else "；".join(key_events)
                    summary_text += f"\n  关键事件：{events_str[:100]}"
                summaries.append(summary_text)

            # 如果没有详细大纲，尝试从基础大纲中提取概要
            elif project.outline_content:
                # 先对大纲进行格式化处理
                formatted_outline = self._format_outline(
                    project.outline_content, "novel")
                basic_summary = self._extract_chapter_summary_from_outline(
                    formatted_outline, ch
                )
                if basic_summary.get("chapter_summary") and \
                   not basic_summary["chapter_summary"].startswith("（请根据"):
                    summaries.append(
                        f"第{ch}章《{basic_summary['chapter_title']}》（基础大纲概要）：\n  {basic_summary['chapter_summary'][:300]}"
                    )

        # 添加全局上下文信息
        global_context = ""
        if project.outline_content:
            context = self._extract_global_context_from_outline(
                project.outline_content, "novel"
            )

            context_parts = []
            if context.get("characters"):
                context_parts.append(
                    f"【人物设定摘要】\n{context['characters'][:400]}")
            if context.get("world_setting"):
                context_parts.append(
                    f"【世界观设定】\n{context['world_setting'][:200]}")
            if context.get("main_plot"):
                context_parts.append(f"【故事主线】\n{context['main_plot'][:200]}")

            if context_parts:
                global_context = "\n\n**全局上下文参考：**\n" + \
                    "\n".join(context_parts)

        if summaries:
            return "\n\n".join(summaries) + global_context

        # 如果是第一章，返回全局上下文
        if global_context:
            return f"（无前序章节，这是第一章）\n{global_context}"
        return "（无前序章节，这是第一章）"

    def _build_chapter_outline_prompt(
        self,
        project: NovelProject,
        chapter_number: int,
        chapter_summary: Dict[str, str],
        previous_summaries: str,
        user_guidance: str = None
    ) -> str:
        """
        构建章节详细大纲生成提示词（增强版）

        增强功能：
        1. 检测是否缺少简略大纲
        2. 为缺失大纲的情况提供推断性上下文
        3. 确保与前文内容的一致性
        4. 支持用户提供的概要或参考信息
        5. 支持两阶段大纲生成机制

        Args:
            project: 项目对象
            chapter_number: 章节号
            chapter_summary: 当前章节概要
            previous_summaries: 前序章节摘要
            user_guidance: 用户提供的概要或参考信息（可选）

        Returns:
            格式化后的提示词
        """
        from app.services.novel_writer.prompt_templates import CHAPTER_DETAILED_OUTLINE_PROMPT

        # 获取小说配置
        novel_config = project.novel_config or {}

        # ==================== 两阶段大纲机制 ====================
        # 获取全局大纲内容（优先使用两阶段大纲）
        global_outline = getattr(
            project, 'global_outline_content', None) or project.outline_content or ""

        # 如果用户提供了概要，优先使用
        if user_guidance:
            enhanced_summary = user_guidance
            self.logger.info(f"[详细大纲] 第{chapter_number}章使用用户提供的概要")
        else:
            # 检测是否缺少简略大纲
            raw_summary = chapter_summary.get("chapter_summary", "")
            is_missing_outline = not raw_summary or raw_summary.startswith(
                "（请根据")

            # 如果缺少大纲，构建推断性上下文
            enhanced_summary = raw_summary
            if is_missing_outline and global_outline:
                # 构建缺失单元的上下文提示
                missing_context = self._build_missing_unit_context(
                    outline=global_outline,
                    unit_number=chapter_number,
                    content_type="novel",
                    existing_outlines=project.chapter_outlines or {}
                )
                enhanced_summary = missing_context
                self.logger.info(f"[详细大纲] 第{chapter_number}章缺少简略大纲，已构建推断性上下文")

        # 提取全局上下文用于提示词（优先使用两阶段全局大纲）
        global_context_section = ""
        if global_outline:
            context = self._extract_global_context_from_outline(
                global_outline, "novel"
            )
            context_parts = []
            if context.get("core_conflict"):
                context_parts.append(f"【核心冲突】{context['core_conflict']}")
            if context.get("theme"):
                context_parts.append(f"【主题思想】{context['theme']}")
            if context_parts:
                global_context_section = "\n\n**创作参考：**\n" + \
                    "\n".join(context_parts)

        return CHAPTER_DETAILED_OUTLINE_PROMPT.format(
            outline_content=self._smart_outline_truncate(
                global_outline, max_length=30000,
                target_unit=chapter_number, content_type="novel"
            ),
            chapter_number=chapter_number,
            chapter_title=chapter_summary.get(
                "chapter_title", f"第{chapter_number}章"),
            chapter_summary=enhanced_summary,
            previous_chapters_summary=previous_summaries + global_context_section,
            words_per_chapter=novel_config.get("words_per_chapter", 3000),
            narrative_perspective=novel_config.get(
                "narrative_perspective", "第三人称"),
            tone=novel_config.get("tone", "正剧"),
            target_platform=novel_config.get("target_platform", "未指定")
        )

    def _parse_chapter_outline_content(
        self,
        content: str,
        chapter_number: int
    ) -> Dict[str, Any]:
        """解析LLM生成的章节大纲内容"""
        import re
        from datetime import datetime

        parsed = {
            "chapter_number": chapter_number,
            "chapter_title": "",
            "chapter_summary": "",
            "detailed_outline": content,
            "key_events": [],
            "character_arcs": "",
            "suspense_points": [],
            "emotional_tone": "",
            "status": "generated",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # 尝试提取章节标题
        title_match = re.search(
            r'\*{0,2}章节标题\*{0,2}[：:]\s*(.+?)(?:\n|$)', content)
        if title_match:
            title = title_match.group(1).strip()
            title = re.sub(r'\*+', '', title).strip()
            parsed["chapter_title"] = title

        # 格式2: # 第X章 标题名
        if not parsed["chapter_title"]:
            title_match = re.search(
                r'^#+\s*第' + str(chapter_number) + r'章[：:：]?\s*(.+?)(?:\n|$)', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
                title = re.sub(r'\*+', '', title).strip()
                parsed["chapter_title"] = title

        # 尝试提取关键事件
        events_match = re.search(
            r'关键事件[：:]\s*([\s\S]*?)(?=\n\n|\n(?:核心|情感|悬念|$))', content)
        if events_match:
            events_text = events_match.group(1).strip()
            events = re.findall(r'[-\*]\s*(.+?)(?:\n|$)', events_text)
            if events:
                parsed["key_events"] = [e.strip() for e in events if e.strip()]

        # 尝试提取角色发展
        arcs_match = re.search(r'角色发展[：:]\s*(.+?)(?:\n|$)', content)
        if arcs_match:
            parsed["character_arcs"] = arcs_match.group(1).strip()

        # 尝试提取悬念设置
        suspense_match = re.search(
            r'悬念设置[：:]\s*([\s\S]*?)(?=\n\n|\n(?:核心|情感|关键|$))', content)
        if suspense_match:
            suspense_text = suspense_match.group(1).strip()
            suspense = re.findall(r'[-\*]\s*(.+?)(?:\n|$)', suspense_text)
            if suspense:
                parsed["suspense_points"] = [s.strip()
                                             for s in suspense if s.strip()]

        # 尝试提取情感基调
        tone_match = re.search(r'情感基调[：:]\s*(.+?)(?:\n|$)', content)
        if tone_match:
            parsed["emotional_tone"] = tone_match.group(1).strip()

        return parsed

    async def _save_chapter_outline(
        self,
        project: NovelProject,
        chapter_number: int,
        parsed_outline: Dict[str, Any],
        original_content: str = None,
        revision_info: Dict[str, Any] = None
    ):
        """保存章节详细大纲到项目配置

        Args:
            project: 项目对象
            chapter_number: 章节号
            parsed_outline: 解析后的大纲数据
            original_content: 原始大纲内容（用于修正对比）
            revision_info: 修正信息
        """
        existing_outlines = project.chapter_outlines or {}

        updated_outlines = dict(existing_outlines)

        # 保存原始内容和修正信息
        if original_content:
            parsed_outline["original_content"] = original_content
        if revision_info:
            parsed_outline["revision_info"] = revision_info

        updated_outlines[str(chapter_number)] = parsed_outline

        project.chapter_outlines = updated_outlines

        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(project, 'chapter_outlines')

        await self.db.commit()
        await self.db.refresh(project)

        self.logger.info(
            f"第{chapter_number}章详细大纲已保存到项目配置，当前共{len(project.chapter_outlines)}章大纲" +
            (f"，已应用逻辑修正" if revision_info else "")
        )

    # ==================== 电影场景详细大纲生成 ====================

    async def generate_scene_outline(
        self,
        project: NovelProject,
        scene_number: int,
        user_guidance: str = None
    ) -> Dict[str, Any]:
        """
        生成单场景详细大纲（电影剧本专用）

        Args:
            project: 项目对象
            scene_number: 场景号
            user_guidance: 用户提供的概要或参考信息（可选）

        Returns:
            生成结果
        """
        result = {
            "success": False,
            "scene_number": scene_number,
            "content": None,
            "parsed": None,
            "error_message": None
        }

        start_time = time.time()

        try:
            # 检查任务是否被取消
            if await task_manager.is_task_cancelled(project.id):
                result["error_message"] = "生成任务被取消"
                result["cancelled"] = True
                return result

            # 1. 检查基础大纲
            # 记录大纲状态（调试用）
            outline_status = {
                "has_outline_content": bool(project.outline_content),
                "outline_content_len": len(project.outline_content) if project.outline_content else 0,
                "outline_file_path": project.outline_file_path
            }
            self.logger.info(
                f"[场景大纲] 第{scene_number}场生成前大纲状态: {outline_status}")

            # 确保项目数据是最新的（解决会话隔离和Redis问题）
            await self._ensure_fresh_project_data(
                project, required_fields=['outline_content', 'outline_file_path'])

            # 再次检查大纲是否存在
            if not project.outline_content:
                raise Exception("请先上传基础大纲")

            # 调试日志：记录大纲内容状态
            self.logger.info(
                f"[场景大纲] 第{scene_number}场生成前: outline_content长度={len(project.outline_content) if project.outline_content else 0}")

            # 2. 从基础大纲中提取当前场景概要
            scene_summary = self._extract_scene_summary_from_outline(
                project.outline_content, scene_number
            )

            # 3. 获取LLM提供者
            llm_provider = await self._get_llm_provider(project)
            if not llm_provider:
                raise Exception("无法获取LLM提供者")

            # 4. 获取前序场景的大纲摘要
            previous_summaries = self._get_previous_scenes_summary(
                project, scene_number
            )

            # 5. 构建提示词
            prompt = self._build_scene_outline_prompt(
                project, scene_number, scene_summary, previous_summaries
            )

            self.logger.info(f"开始生成第{scene_number}场详细大纲")

            # 6. 调用LLM生成（带重试机制）
            llm_response = await self._call_with_retry(
                lambda: llm_provider.generate(
                    prompt, temperature=0.7, max_tokens=30000),
                item_name=f"第{scene_number}场详细大纲"
            )

            content = llm_response.content if hasattr(
                llm_response, 'content') else str(llm_response)

            # 7. 解析结构化数据
            parsed_outline = self._parse_scene_outline_content(
                content, scene_number)

            # 8. 保存到项目配置
            await self._save_scene_outline(project, scene_number, parsed_outline)

            # 9. 一致性校验（与小说大纲生成保持一致）
            consistency_result = await self._validate_outline_consistency(
                project, scene_number, parsed_outline, "movie_script"
            )
            if consistency_result.get("issues"):
                self.logger.warning(
                    f"[一致性校验] 第{scene_number}场发现{len(consistency_result['issues'])}个问题")
            else:
                self.logger.info(f"[一致性校验] 第{scene_number}场校验通过")

            end_time = time.time()

            result["success"] = True
            result["content"] = content
            result["parsed"] = parsed_outline
            result["duration_ms"] = int((end_time - start_time) * 1000)
            result["consistency"] = consistency_result

            # 10. 触发单元知识图谱构建（如果启用GraphRAG）
            # 注意：kb_graphrag_enabled 可能为 None（旧记录），默认视为启用
            graphrag_enabled = project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True
            self.logger.info(
                f"单元知识图谱触发检查: kb_graphrag_enabled={project.kb_graphrag_enabled}(实际={graphrag_enabled}), "
                f"kb_status={project.kb_status}"
            )

            if graphrag_enabled and project.kb_status == "ready":
                try:
                    # 构建单元大纲内容文本
                    unit_outline_text = parsed_outline.get(
                        "detailed_outline", "")
                    if not unit_outline_text:
                        unit_outline_text = content  # 使用原始生成内容

                    # 异步构建单元图谱（不阻塞主流程）
                    build_result = await self.content_reviser.knowledge_base.build_unit_outline_graph(
                        project_id=project.id,
                        unit_number=scene_number,
                        unit_outline_content=unit_outline_text,
                        llm_provider=llm_provider
                    )

                    if build_result["success"]:
                        self.logger.info(
                            f"单元知识图谱构建完成: 第{scene_number}场, "
                            f"entities={build_result['entity_count']}, relations={build_result['relation_count']}"
                        )
                    else:
                        self.logger.warning(
                            f"单元知识图谱构建失败: 第{scene_number}场, error={build_result.get('error')}"
                        )
                except Exception as kb_error:
                    # 知识图谱构建失败不影响主流程
                    self.logger.warning(
                        f"单元知识图谱构建异常: 第{scene_number}场, error={str(kb_error)}")

            self.logger.info(f"第{scene_number}场详细大纲生成完成")
            return result

        except asyncio.CancelledError:
            self.logger.warning(f"生成场景大纲被取消: 第{scene_number}场")
            result["error_message"] = "生成任务被取消"
            result["cancelled"] = True
            await self.db.rollback()
            raise
        except Exception as e:
            self.logger.error(f"生成场景大纲失败: 第{scene_number}场, 错误: {str(e)}")
            result["error_message"] = str(e)
            return result

    async def generate_all_scene_outlines(
        self,
        project: NovelProject,
        scene_numbers: Optional[List[int]] = None,
        stop_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        批量生成多场景详细大纲（电影剧本专用）
        """
        # 确定要生成的场景数
        total_scenes = project.total_chapters or 0

        if scene_numbers is None:
            scene_numbers = list(range(1, total_scenes + 1))

        result = {
            "project_id": project.id,
            "total_scenes": len(scene_numbers),
            "completed_count": 0,
            "failed_count": 0,
            "scenes": [],
            "errors": []
        }

        # 创建任务状态追踪
        await task_manager.create_task(
            project.id, TASK_TYPE_SCENE_OUTLINE,
            total_count=len(scene_numbers)
        )

        try:
            for scene_num in scene_numbers:
                # 刷新项目对象以确保获取最新数据（关键：解决断点续传时 outline_content 丢失问题）
                await self.db.refresh(project)

                # 检查任务是否被取消
                if await task_manager.is_task_cancelled(project.id):
                    self.logger.info(f"任务已取消，停止生成: project_id={project.id}")
                    result["cancelled"] = True
                    break

                # 使用带重试的调用方式
                try:
                    gen_result = await self._call_with_retry(
                        lambda: self.generate_scene_outline(
                            project, scene_num),
                        item_name=f"第{scene_num}场大纲"
                    )
                except Exception as e:
                    # 重试失败后，构造失败结果
                    gen_result = {
                        "success": False,
                        "error_message": str(e)
                    }

                result["scenes"].append({
                    "scene_number": scene_num,
                    "success": gen_result["success"],
                    "error": gen_result.get("error_message")
                })

                if gen_result["success"]:
                    result["completed_count"] += 1
                else:
                    result["failed_count"] += 1
                    result["errors"].append({
                        "scene_number": scene_num,
                        "error": gen_result.get("error_message")
                    })
                    if stop_on_error:
                        self.logger.warning(f"生成失败，停止批量生成: 第{scene_num}场")
                        break

                # 更新任务进度
                await task_manager.update_task(
                    project.id,
                    completed_count=result["completed_count"],
                    current_item=scene_num
                )

                # 添加请求间隔，避免触发API速率限制
                if scene_num != scene_numbers[-1]:  # 最后一个不需要等待
                    await asyncio.sleep(self.settings.BATCH_REQUEST_INTERVAL)

            # 标记任务完成
            await task_manager.complete_task(project.id, success=result["failed_count"] == 0)
            return result

        except asyncio.CancelledError:
            self.logger.warning("批量生成场景大纲被取消")
            result["cancelled"] = True
            result["error_message"] = "生成任务被取消"
            await task_manager.cancel_task(project.id)
            await self.db.rollback()
            raise

    def _extract_scene_summary_from_outline(
        self,
        outline: str,
        scene_num: int
    ) -> Dict[str, str]:
        """从基础大纲中提取场景概要（参考小说章节提取的成功模式）"""
        import re

        result = {
            "scene_title": f"第{scene_num}场",
            "location": None,
            "scene_summary": ""
        }

        if not outline:
            return result

        lines = outline.split('\n')
        capturing = False
        summary_lines = []

        # 中文数字映射
        chinese_nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

        def num_to_chinese(n):
            if n <= 10:
                return chinese_nums[n]
            elif n < 20:
                return '十' + (chinese_nums[n - 10] if n > 10 else '')
            elif n < 100:
                tens = n // 10
                ones = n % 10
                result = chinese_nums[tens] + '十'
                if ones > 0:
                    result += chinese_nums[ones]
                return result
            return str(n)

        chinese_scene = num_to_chinese(scene_num)

        # 匹配当前场景的模式 - 支持多种格式（参考小说章节提取的成功模式，按优先级排序）
        patterns = [
            # 1. Markdown标题格式（带 # 前缀）- 最常用
            rf'^#+\s*第{scene_num}场\s*#*\s*$',  # ### 第1场 ###
            rf'^#+\s*第{scene_num}场[:：\s]',    # ### 第1场：标题
            rf'^#+\s*第{chinese_scene}场\s*#*\s*$',  # ### 第一场 ###
            rf'^#+\s*第{chinese_scene}场[:：\s]',    # ### 第一场：标题
            # 2. 粗体格式
            rf'^\*\*第{scene_num}场\*\*',
            rf'^\*\*第{chinese_scene}场\*\*',
            rf'^\*\*第{scene_num}场[:：\s]',
            rf'^\*\*第{chinese_scene}场[:：\s]',
            # 3. 括号格式
            rf'^【第{scene_num}场】',
            rf'^【第{chinese_scene}场】',
            # 4. 纯文本格式（阿拉伯数字）
            rf'^第{scene_num}场[:：\s]',
            rf'^第{scene_num}场$',
            # 5. 纯文本格式（中文数字）
            rf'^第{chinese_scene}场[:：\s]',
            rf'^第{chinese_scene}场$',
            # 6. 带空格格式
            rf'^第\s*{scene_num}\s*场[:：\s]?',
            rf'^第\s*{chinese_scene}\s*场[:：\s]?',
            # 7. Scene 格式
            rf'^[Ss]cene\s*{scene_num}[:：\s]?',
            rf'^[Ss]cene\s*{chinese_scene}[:：\s]?',
            rf'^SCENE\s*{scene_num}[:：\s]?',
            # 8. 内景/外景格式（剧本常用）
            rf'^{scene_num}\.\s*[内外]景',
            rf'^{scene_num}[\.、]\s*[^\d]',  # "1. 标题" 格式
            # 9. INT./EXT. 格式（国际剧本标准）
            rf'^[Ii][Nn][Tt]\.?\s*[-–]?\s*.*{scene_num}',
            rf'^[Ee][Xx][Tt]\.?\s*[-–]?\s*.*{scene_num}',
            # 10. 内外景带编号格式
            rf'^[内外]景\s*[-–·•]\s*.*第{scene_num}场',
            rf'^[内外]景\s*[-–·•]\s*.*第{chinese_scene}场',
        ]

        compiled_patterns = [re.compile(p) for p in patterns]

        matched_line_idx = -1
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # 检查是否匹配当前场景标题
            for pattern in compiled_patterns:
                if pattern.match(line_stripped):
                    matched_line_idx = i
                    self.logger.debug(
                        f"[场景概要提取] 第{scene_num}场标题匹配成功: 行{i}, 内容: {line_stripped[:60]}")
                    # 尝试多种标题提取模式（按优先级排序）
                    title_patterns = [
                        # 1. Markdown标题格式
                        rf'^#+\s*第{scene_num}场[:：\s]*(.*?)\s*#*\s*$',
                        rf'^#+\s*第{chinese_scene}场[:：\s]*(.*?)\s*#*\s*$',
                        # 2. 粗体格式
                        rf'^\*\*第{scene_num}场\*\*[:：\s]*(.*)',
                        rf'^\*\*第{chinese_scene}场\*\*[:：\s]*(.*)',
                        rf'^\*\*第{scene_num}场[:：\s]*(.*?)\*\*',
                        rf'^\*\*第{chinese_scene}场[:：\s]*(.*?)\*\*',
                        # 3. 括号格式
                        rf'^【第{scene_num}场】[:：\s]*(.*)',
                        rf'^【第{chinese_scene}场】[:：\s]*(.*)',
                        # 4. 普通格式
                        rf'第{scene_num}场[:：\s]*(.*)',
                        rf'第{chinese_scene}场[:：\s]*(.*)',
                        rf'第\s*{scene_num}\s*场[:：\s]*(.*)',
                        rf'第\s*{chinese_scene}\s*场[:：\s]*(.*)',
                        # 5. Scene格式
                        rf'^[Ss]cene\s*{scene_num}[:：\s]*(.*)',
                    ]
                    for title_pattern in title_patterns:
                        title_match = re.search(title_pattern, line_stripped)
                        if title_match:
                            title = title_match.group(1).strip()
                            # 移除可能的markdown标记
                            title = re.sub(r'\*+', '', title).strip()
                            title = re.sub(r'#+', '', title).strip()
                            title = re.sub(r'【.*?】', '', title).strip()
                            if title:
                                result["scene_title"] = title
                                break

                    # 尝试提取地点
                    location_match = re.search(
                        r'([内外]景[^\.·•\-–]+)', line_stripped)
                    if location_match:
                        result["location"] = location_match.group(1).strip()
                    # 尝试 INT./EXT. 格式
                    if not result["location"]:
                        int_ext_match = re.search(
                            r'^([Ii][Nn][Tt]\.?|[Ee][Xx][Tt]\.?)\s*[-–]?\s*(.+?)(?:\s*[-–]|$)', line_stripped)
                        if int_ext_match:
                            result["location"] = int_ext_match.group(2).strip()

                    capturing = True
                    continue

            # 检查是否进入下一场景
            if capturing:
                # 构建下一场景的匹配模式
                next_scene_num = scene_num + 1
                next_chinese_scene = num_to_chinese(next_scene_num)

                # 下一场景匹配模式 - 按优先级排序
                next_scene_patterns = [
                    # 1. 优先匹配带 # 前缀的具体下一场景
                    rf'^#+\s*第{next_scene_num}场',
                    rf'^#+\s*第{next_chinese_scene}场',
                    # 2. 匹配带 # 前缀的任意场景
                    rf'^#+\s*第\d+场',
                    rf'^#+\s*第[{chinese_nums}]+场',
                    # 3. 不带 # 前缀的具体下一场景
                    rf'^第{next_scene_num}场',
                    rf'^第{next_chinese_scene}场',
                    # 4. 括号格式
                    rf'^【第{next_scene_num}场】',
                    rf'^【第{next_chinese_scene}场】',
                    rf'^【第\d+场】',
                    # 5. 其他格式
                    rf'^\*\*第\d+场',
                    rf'^[Ss]cene\s*{next_scene_num}',
                    rf'^[Ss]cene\s*\d+',
                    rf'^SCENE\s*\d+',
                    rf'^\d+\.\s*[内外]景',
                    rf'^[Ii][Nn][Tt]\.\s*',
                    rf'^[Ee][Xx][Tt]\.\s*',
                    r'^---+$',
                    r'^___+$',
                ]

                matched_pattern = None
                for pattern in next_scene_patterns:
                    if re.match(pattern, line_stripped):
                        matched_pattern = pattern
                        capturing = False
                        break

                if not capturing:
                    self.logger.debug(
                        f"[场景概要提取] 第{scene_num}场边界检测: 匹配到下一场模式 '{matched_pattern}', 行内容: {line_stripped[:50]}")
                    break

                # 跳过当前场景的标题行
                if line_stripped.startswith('**') and '场' in line_stripped and len(line_stripped) < 50:
                    current_title_patterns = [
                        rf'^\*\*第{scene_num}场',
                        rf'^\*\*第{chinese_scene}场',
                    ]
                    for tp in current_title_patterns:
                        if re.match(tp, line_stripped):
                            continue
                # 跳过纯分隔符行
                if line_stripped in ['---', '***', '___', '']:
                    continue

                # 捕获概要内容
                skip_patterns = [
                    r'^###\s+\d',
                    r'^##\s+创作',
                    r'^##\s+检查',
                ]
                should_skip = False
                for pattern in skip_patterns:
                    if re.match(pattern, line_stripped):
                        should_skip = True
                        break

                if not should_skip:
                    summary_lines.append(line_stripped)

        result["scene_summary"] = '\n'.join(summary_lines).strip()

        if not result["scene_summary"]:
            result["scene_summary"] = f"（请根据基础大纲中的故事结构，为第{scene_num}场创作详细内容）"
            self.logger.warning(
                f"[场景概要提取] 第{scene_num}场未提取到概要，使用默认提示。标题匹配行: {matched_line_idx}, 捕获行数: {len(summary_lines)}")
        else:
            self.logger.info(
                f"[场景概要提取] 第{scene_num}场提取成功，标题='{result['scene_title']}', 概要长度={len(result['scene_summary'])}, 标题匹配行: {matched_line_idx}, 捕获行数: {len(summary_lines)}")

        return result

    def _get_previous_scenes_summary(
        self,
        project: NovelProject,
        current_scene: int,
        max_previous: int = 5
    ) -> str:
        """
        获取前序场景的大纲摘要（增强版）

        增强功能：
        1. 获取已生成的详细大纲摘要
        2. 当缺少详细大纲时，从基础大纲中提取概要
        3. 添加全局上下文信息（人物设定、世界观等）

        Args:
            project: 项目对象
            current_scene: 当前场景号
            max_previous: 最多获取前几场

        Returns:
            前序场景大纲摘要文本
        """
        summaries = []
        scene_outlines = project.scene_outlines or {}

        start_sc = max(1, current_scene - max_previous)

        for sc in range(start_sc, current_scene):
            sc_outline = scene_outlines.get(str(sc), {})

            # 优先使用已生成的详细大纲
            if sc_outline.get("detailed_outline"):
                summary = sc_outline.get("scene_summary", "")
                title = sc_outline.get("scene_title", f"第{sc}场")
                location = sc_outline.get("location", "")
                key_action = sc_outline.get("key_action", "")

                summary_text = f"第{sc}场《{title}》({location})：{summary[:200]}{'...' if len(summary) > 200 else ''}"
                if key_action:
                    summary_text += f"\n  关键动作：{key_action[:80]}"
                summaries.append(summary_text)

            # 如果没有详细大纲，尝试从基础大纲中提取概要
            elif project.outline_content:
                basic_summary = self._extract_scene_summary_from_outline(
                    project.outline_content, sc
                )
                if basic_summary.get("scene_summary") and \
                   not basic_summary["scene_summary"].startswith("（请根据"):
                    location = basic_summary.get("location", "未知地点")
                    summaries.append(
                        f"第{sc}场《{basic_summary['scene_title']}》({location})（基础大纲概要）：\n  {basic_summary['scene_summary'][:200]}"
                    )

        # 添加全局上下文信息
        global_context = ""
        if project.outline_content:
            context = self._extract_global_context_from_outline(
                project.outline_content, "movie_script"
            )

            context_parts = []
            if context.get("characters"):
                context_parts.append(
                    f"【人物设定摘要】\n{context['characters'][:400]}")
            if context.get("world_setting"):
                context_parts.append(
                    f"【世界观设定】\n{context['world_setting'][:200]}")
            if context.get("main_plot"):
                context_parts.append(f"【故事主线】\n{context['main_plot'][:200]}")

            if context_parts:
                global_context = "\n\n**全局上下文参考：**\n" + \
                    "\n".join(context_parts)

        if summaries:
            return "\n\n".join(summaries) + global_context

        # 如果是第一场，返回全局上下文
        if global_context:
            return f"（无前序场景，这是第一场）\n{global_context}"
        return "（无前序场景，这是第一场）"

    def _build_scene_outline_prompt(
        self,
        project: NovelProject,
        scene_number: int,
        scene_summary: Dict[str, str],
        previous_summaries: str
    ) -> str:
        """
        构建场景详细大纲生成提示词（增强版）

        增强功能：
        1. 检测是否缺少简略大纲
        2. 为缺失大纲的情况提供推断性上下文
        3. 确保与前文内容的一致性

        Args:
            project: 项目对象
            scene_number: 场景号
            scene_summary: 当前场景概要
            previous_summaries: 前序场景摘要

        Returns:
            格式化后的提示词
        """
        from app.services.novel_writer.prompt_templates import SCENE_DETAILED_OUTLINE_PROMPT

        # 获取电影配置
        movie_config = project.movie_script_config or {}

        # 检测是否缺少简略大纲
        raw_summary = scene_summary.get("scene_summary", "")
        is_missing_outline = not raw_summary or raw_summary.startswith("（请根据")

        # 如果缺少大纲，构建推断性上下文
        enhanced_summary = raw_summary
        if is_missing_outline and project.outline_content:
            # 构建缺失单元的上下文提示
            missing_context = self._build_missing_unit_context(
                outline=project.outline_content,
                unit_number=scene_number,
                content_type="movie_script",
                existing_outlines=project.scene_outlines or {}
            )
            enhanced_summary = missing_context
            self.logger.info(f"[详细大纲] 第{scene_number}场缺少简略大纲，已构建推断性上下文")

        # 提取全局上下文用于提示词
        global_context_section = ""
        if project.outline_content:
            context = self._extract_global_context_from_outline(
                project.outline_content, "movie_script"
            )
            context_parts = []
            if context.get("core_conflict"):
                context_parts.append(f"【核心冲突】{context['core_conflict']}")
            if context.get("theme"):
                context_parts.append(f"【主题思想】{context['theme']}")
            if context_parts:
                global_context_section = "\n\n**创作参考：**\n" + \
                    "\n".join(context_parts)

        return SCENE_DETAILED_OUTLINE_PROMPT.format(
            outline_content=self._smart_outline_truncate(
                project.outline_content, max_length=30000,
                target_unit=scene_number, content_type="movie_script"
            ),
            scene_number=scene_number,
            scene_title=scene_summary.get("scene_title", f"第{scene_number}场"),
            location=scene_summary.get("location", "待确定"),
            scene_summary=enhanced_summary,
            previous_scenes_summary=previous_summaries + global_context_section,
            movie_type=movie_config.get("movie_type", "院线电影"),
            total_duration=movie_config.get("total_duration", 90),
            format_standard=movie_config.get("format_standard", "标准格式"),
            dialogue_narration_ratio=movie_config.get(
                "dialogue_narration_ratio", "均衡")
        )

    def _parse_scene_outline_content(
        self,
        content: str,
        scene_number: int
    ) -> Dict[str, Any]:
        """解析LLM生成的场景大纲内容"""
        import re
        from datetime import datetime

        parsed = {
            "scene_number": scene_number,
            "scene_title": "",
            "location": None,
            "scene_summary": "",
            "detailed_outline": content,
            "characters": [],
            "estimated_duration": None,
            "key_action": "",
            "dialogue_focus": "",
            "status": "generated",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # 尝试提取场景标题
        title_match = re.search(
            r'\*{0,2}场景标题\*{0,2}[：:]\s*(.+?)(?:\n|$)', content)
        if title_match:
            title = title_match.group(1).strip()
            title = re.sub(r'\*+', '', title).strip()
            parsed["scene_title"] = title

        # 格式2: # 第X场 标题名
        if not parsed["scene_title"]:
            title_match = re.search(
                r'^#+\s*第' + str(scene_number) + r'场[：:：]?\s*(.+?)(?:\n|$)', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
                title = re.sub(r'\*+', '', title).strip()
                parsed["scene_title"] = title

        # 尝试提取地点
        location_match = re.search(r'地点[：:]\s*(.+?)(?:\n|$)', content)
        if location_match:
            parsed["location"] = location_match.group(1).strip()

        # 尝试提取出场人物
        characters_match = re.search(r'出场人物[：:]\s*(.+?)(?:\n|$)', content)
        if characters_match:
            characters_text = characters_match.group(1).strip()
            # 尝试分割人物列表
            characters = re.split(r'[,，、\s]+', characters_text)
            parsed["characters"] = [c.strip() for c in characters if c.strip()]

        # 尝试提取预计时长
        duration_match = re.search(r'预计时长[：:]\s*(\d+)\s*分钟', content)
        if duration_match:
            parsed["estimated_duration"] = int(duration_match.group(1))

        # 尝试提取关键动作
        action_match = re.search(r'关键动作[：:]\s*(.+?)(?:\n|$)', content)
        if action_match:
            parsed["key_action"] = action_match.group(1).strip()

        # 尝试提取对话重点
        dialogue_match = re.search(r'对话重点[：:]\s*(.+?)(?:\n|$)', content)
        if dialogue_match:
            parsed["dialogue_focus"] = dialogue_match.group(1).strip()

        return parsed

    async def _save_scene_outline(
        self,
        project: NovelProject,
        scene_number: int,
        parsed_outline: Dict[str, Any]
    ):
        """保存场景详细大纲到项目配置"""
        existing_outlines = project.scene_outlines or {}

        updated_outlines = dict(existing_outlines)
        updated_outlines[str(scene_number)] = parsed_outline

        project.scene_outlines = updated_outlines

        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(project, 'scene_outlines')

        await self.db.commit()
        await self.db.refresh(project)

        self.logger.info(
            f"第{scene_number}场详细大纲已保存到项目配置，当前共{len(project.scene_outlines)}场大纲")

    # ==================== 电影场景正文生成 ====================

    async def generate_scene_content(
        self,
        project: NovelProject,
        scene_number: int,
        llm_provider=None
    ) -> Dict[str, Any]:
        """
        生成电影场景正文（电影剧本专用）

        Args:
            project: 项目对象
            scene_number: 场景号
            llm_provider: LLM提供者（可选）

        Returns:
            生成结果
        """
        result = {
            "success": False,
            "scene_number": scene_number,
            "content": None,
            "word_count": 0,
            "token_count": 0,
            "duration_ms": 0,
            "error_message": None
        }

        start_time = time.time()

        try:
            # 1. 检查场景详细大纲是否存在
            scene_outlines = project.scene_outlines or {}
            scene_outline = scene_outlines.get(str(scene_number))

            if not scene_outline:
                raise Exception(f"第{scene_number}场的详细大纲未生成，请先生成场景详细大纲")

            # 2. 获取或创建章节记录（一场对应一章）
            chapter = await self._get_or_create_scene_chapter(project, scene_number)

            if chapter.status == ChapterStatus.COMPLETED:
                result["success"] = True
                result["content"] = chapter.final_content
                result["word_count"] = chapter.word_count
                self.logger.info(f"第{scene_number}场已完成，跳过生成")
                return result

            # 3. 更新状态为生成中
            chapter.status = ChapterStatus.DRAFTING
            await self.db.commit()

            # 4. 获取LLM提供者
            if not llm_provider:
                llm_provider = await self._get_llm_provider(project)

            if not llm_provider:
                raise Exception("无法获取LLM提供者，请检查API配置")

            # 5. 构建上下文
            context = await self.context_manager.build_scene_context(
                project, scene_number
            )

            # 6. 获取场景标题
            scene_title = scene_outline.get(
                "scene_title", f"第{scene_number}场")

            # 7. 获取类型配置
            type_config = getattr(project, 'movie_script_config', None)
            generation_config = project.generation_config or {}

            # 8. 构建提示词
            from app.services.novel_writer.prompt_templates import get_scene_script_prompt
            prompt = get_scene_script_prompt(
                scene_number=scene_number,
                scene_title=scene_title,
                scene_outline=scene_outline,
                context=context,
                type_config=type_config,
                generation_config=generation_config
            )

            # 调试日志：检查提示词中的大纲内容
            outline_in_context = context.get("outline_content", "")
            scene_outline_text = context.get("scene_outline", "")
            previous_scenes_summary = context.get(
                "previous_scenes_summary", "")
            self.logger.info(
                f"[提示词检查] 第{scene_number}场: outline_content长度={len(outline_in_context)}字")
            self.logger.info(
                f"[提示词检查] 第{scene_number}场: scene_outline长度={len(scene_outline_text)}字")
            self.logger.info(
                f"[提示词检查] 第{scene_number}场: previous_scenes_summary长度={len(previous_scenes_summary)}字")
            self.logger.info(
                f"[提示词检查] 第{scene_number}场: 提示词总长度={len(prompt)}字")

            # 检查提示词是否包含大纲关键字
            if "大纲" in prompt:
                self.logger.info(f"[提示词检查] 第{scene_number}场: 提示词中包含'大纲'关键字 ✓")
            else:
                self.logger.warning(
                    f"[提示词检查] 第{scene_number}场: 提示词中未找到'大纲'关键字 ✗")

            self.logger.info(f"开始生成第{scene_number}场正文")

            # 9. 调用LLM生成（带重试机制）
            temperature = generation_config.get("temperature", 0.8)
            # 不再限制max_tokens，让LLM根据提示词中的字数要求自由生成

            llm_response = await self._call_with_retry(
                lambda: llm_provider.generate(
                    prompt, temperature=temperature),
                item_name=f"第{scene_number}场正文"
            )

            # 提取响应内容
            if hasattr(llm_response, 'content'):
                content = llm_response.content
            else:
                content = str(llm_response)

            # 提取Token使用量
            token_count = 0
            if hasattr(llm_response, 'usage') and llm_response.usage:
                usage = llm_response.usage
                if isinstance(usage, dict):
                    token_count = usage.get('total_tokens', 0)
                else:
                    token_count = getattr(usage, 'total_tokens', 0)

                if token_count > 0:
                    project.total_tokens = (
                        project.total_tokens or 0) + token_count

            # 10. 后处理
            content = self._post_process(content)

            # 记录字数信息（用于日志）
            # 获取时长，确保不为 None（防止 None * int 报错）
            duration_minutes = scene_outline.get(
                "estimated_duration") or scene_outline.get("duration_minutes") or 3
            estimated_words = int(duration_minutes * 250)  # 每分钟约250字
            actual_words = len(content)
            self.logger.info(
                f"第{scene_number}场生成完成: 目标{estimated_words}字(时长{duration_minutes}分钟), "
                f"实际{actual_words}字, 偏差{((actual_words - estimated_words) / estimated_words * 100):.1f}%"
            )

            # 11. 定稿处理
            await self._finalize_chapter(project, chapter, content, llm_provider)

            # 12. 更新结果
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)

            result["success"] = True
            result["content"] = content
            result["word_count"] = len(content)
            result["token_count"] = token_count
            result["duration_ms"] = duration_ms

            # 更新章节记录
            chapter.status = ChapterStatus.COMPLETED
            chapter.final_content = content
            chapter.word_count = len(content)
            chapter.token_count = token_count
            chapter.duration_ms = duration_ms
            chapter.chapter_title = f"第{scene_number}场 {scene_title}"

            # 更新项目进度
            await self._update_project_progress(project, scene_number)

            # 更新 scene_outlines 中的正文生成状态
            scene_outlines = project.scene_outlines or {}
            if str(scene_number) in scene_outlines:
                scene_outlines[str(scene_number)
                               ]["content_status"] = "generated"
                scene_outlines[str(
                    scene_number)]["content_generated_at"] = datetime.now().isoformat()
                scene_outlines[str(scene_number)
                               ]["content_word_count"] = len(content)
                project.scene_outlines = scene_outlines
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(project, 'scene_outlines')

            await self.db.commit()

            self.logger.info(
                f"第{scene_number}场正文生成完成, 字数: {len(content)}")
            return result

        except Exception as e:
            self.logger.error(f"生成第{scene_number}场正文失败: {str(e)}")
            result["error_message"] = str(e)

            # 更新错误状态
            try:
                chapter = await self._get_or_create_scene_chapter(project, scene_number)
                chapter.status = ChapterStatus.FAILED
                chapter.error_message = str(e)
                await self.db.commit()
            except Exception as update_error:
                self.logger.warning(f"更新章节错误状态失败: {str(update_error)}")

            return result

    async def _get_or_create_scene_chapter(
        self,
        project: NovelProject,
        scene_number: int
    ) -> NovelChapter:
        """获取或创建场景章节（一场对应一章）"""
        # 查找现有章节（按chapter_number查找，对应场景号）
        query = select(NovelChapter).where(
            NovelChapter.project_id == project.id,
            NovelChapter.chapter_number == scene_number
        )
        result = await self.db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            # 获取场景标题
            scene_outlines = project.scene_outlines or {}
            sc_outline = scene_outlines.get(str(scene_number), {})
            scene_title = sc_outline.get('scene_title', '')
            location = sc_outline.get('location', '')

            if scene_title:
                chapter_title = f"第{scene_number}场 {scene_title}"
            elif location:
                chapter_title = f"第{scene_number}场 {location}"
            else:
                chapter_title = f"第{scene_number}场"

            chapter = NovelChapter(
                project_id=project.id,
                chapter_number=scene_number,
                chapter_title=chapter_title,
                status=ChapterStatus.PENDING
            )
            self.db.add(chapter)
            await self.db.commit()
            await self.db.refresh(chapter)

        return chapter

    # ==================== 一致性参考辅助方法（详细大纲生成专用） ====================

    def _extract_global_context_from_outline(
        self,
        outline: str,
        content_type: str = "novel"
    ) -> Dict[str, str]:
        """
        从基础大纲中提取全局上下文信息

        用于详细大纲生成时提供一致性参考，包括：
        1. 人物设定
        2. 世界观设定
        3. 故事主线
        4. 核心冲突

        Args:
            outline: 基础大纲内容
            content_type: 内容类型（novel/series_script/movie_script）

        Returns:
            全局上下文字典
        """
        import re

        context = {
            "characters": "",
            "world_setting": "",
            "main_plot": "",
            "core_conflict": "",
            "theme": "",
            "style_notes": ""
        }

        if not outline:
            return context

        lines = outline.split('\n')

        # 定义要提取的章节标题模式
        section_patterns = {
            "characters": [
                r'^#+\s*人物',
                r'^#+\s*角色',
                r'^#+\s*主要人物',
                r'^#+\s*人物设定',
                r'^#+\s*角色介绍',
                r'^人物设定',
                r'^角色介绍',
            ],
            "world_setting": [
                r'^#+\s*世界观',
                r'^#+\s*世界设定',
                r'^#+\s*背景设定',
                r'^世界观',
                r'^背景设定',
            ],
            "main_plot": [
                r'^#+\s*故事主线',
                r'^#+\s*剧情概要',
                r'^#+\s*故事梗概',
                r'^#+\s*主要内容',
                r'^故事梗概',
                r'^剧情概要',
            ],
            "core_conflict": [
                r'^#+\s*核心冲突',
                r'^#+\s*主要矛盾',
                r'^核心冲突',
            ],
            "theme": [
                r'^#+\s*主题',
                r'^#+\s*核心主题',
                r'^主题思想',
            ],
            "style_notes": [
                r'^#+\s*风格',
                r'^#+\s*创作风格',
                r'^#+\s*写作风格',
                r'^风格说明',
            ]
        }

        current_section = None
        section_content = []

        def is_new_section(line_stripped):
            """检查是否是新章节的开始"""
            for section_key, patterns in section_patterns.items():
                for pattern in patterns:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        return section_key
            # 检查是否是新的markdown标题（可能是新章节）
            if re.match(r'^#+\s', line_stripped):
                return "other"
            return None

        for line in lines:
            line_stripped = line.strip()

            # 检查是否进入新章节
            new_section = is_new_section(line_stripped)

            if new_section and new_section != "other":
                # 保存之前章节的内容
                if current_section and current_section in context and section_content:
                    context[current_section] = '\n'.join(
                        section_content).strip()

                # 开始新章节
                current_section = new_section
                section_content = []
                continue
            elif new_section == "other":
                # 进入其他章节，保存当前内容
                if current_section and current_section in context and section_content:
                    context[current_section] = '\n'.join(
                        section_content).strip()
                current_section = None
                section_content = []
                continue

            # 收集当前章节内容
            if current_section and current_section in context:
                section_content.append(line_stripped)

        # 保存最后一个章节
        if current_section and current_section in context and section_content:
            context[current_section] = '\n'.join(section_content).strip()

        # 清理和格式化结果
        for key in context:
            if context[key]:
                # 限制长度
                max_len = 1500 if key == "characters" else 800
                if len(context[key]) > max_len:
                    context[key] = context[key][:max_len] + "..."

        return context

    def _extract_story_structure_from_outline(
        self,
        outline: str,
        content_type: str = "novel"
    ) -> Dict[str, Any]:
        """
        从基础大纲中提取故事结构信息

        用于推断缺失章节的内容方向，包括：
        1. 已有章节/分集/场景的概要列表
        2. 故事起承转合的结构
        3. 关键转折点

        Args:
            outline: 基础大纲内容
            content_type: 内容类型

        Returns:
            故事结构信息
        """
        import re

        structure = {
            "existing_units": [],  # 已有单元概要列表
            "story_phases": [],    # 故事阶段（起承转合）
            "key_turning_points": [],  # 关键转折点
            "total_units": 0
        }

        if not outline:
            return structure

        lines = outline.split('\n')

        # 根据内容类型选择匹配模式
        if content_type == "series_script":
            unit_patterns = [
                r'^第(\d+)集[:：\s]*(.*)$',
                r'^\*\*第(\d+)集[:：\s]*([^*]*)\*\*',
            ]
            unit_label = "集"
        elif content_type == "movie_script":
            unit_patterns = [
                r'^第(\d+)场[:：\s]*(.*)$',
                r'^\*\*第(\d+)场[:：\s]*([^*]*)\*\*',
                r'^(\d+)\.\s*[内外]景[:：\s]*(.*)$',
            ]
            unit_label = "场"
        else:  # novel
            unit_patterns = [
                r'^第(\d+)章[:：\s]*(.*)$',
                r'^\*\*第(\d+)章[:：\s]*([^*]*)\*\*',
            ]
            unit_label = "章"

        # 提取所有单元概要
        for line in lines:
            line_stripped = line.strip()

            for pattern in unit_patterns:
                match = re.match(pattern, line_stripped)
                if match:
                    unit_num = int(match.group(1))
                    unit_title = match.group(
                        2).strip() if match.group(2) else ""
                    # 清理标题
                    unit_title = re.sub(r'[《》【】\*]', '', unit_title).strip()

                    structure["existing_units"].append({
                        "number": unit_num,
                        "title": unit_title,
                        "raw_line": line_stripped
                    })
                    break

        # 计算总单元数
        if structure["existing_units"]:
            structure["total_units"] = max(u["number"]
                                           for u in structure["existing_units"])

        # 识别故事阶段（基于单元位置）
        if structure["total_units"] > 0:
            total = structure["total_units"]
            # 四幕式结构
            structure["story_phases"] = [
                {"phase": "开端", "range": f"第1{unit_label}-第{total//4}{unit_label}",
                    "purpose": "建立世界观、人物关系、初始冲突"},
                {"phase": "发展", "range": f"第{total//4+1}{unit_label}-第{total//2}{unit_label}",
                    "purpose": "冲突升级、人物发展"},
                {"phase": "高潮", "range": f"第{total//2+1}{unit_label}-第{total*3//4}{unit_label}",
                    "purpose": "核心冲突爆发、情感顶点"},
                {"phase": "结局", "range": f"第{total*3//4+1}{unit_label}-第{total}{unit_label}",
                    "purpose": "冲突解决、收尾"}
            ]

        return structure

    def _build_missing_unit_context(
        self,
        outline: str,
        unit_number: int,
        content_type: str,
        existing_outlines: Dict[str, Any]
    ) -> str:
        """
        为缺失简略大纲的单元构建上下文提示

        当基础大纲中缺少某个单元的简略大纲时，基于：
        1. 全局上下文（人物、世界观、主题）
        2. 故事结构阶段
        3. 滑动窗口内的前序单元摘要
        4. 已生成的详细大纲内容

        Args:
            outline: 基础大纲内容
            unit_number: 当前单元编号
            content_type: 内容类型
            existing_outlines: 已生成的详细大纲字典

        Returns:
            推断性上下文提示
        """
        # 获取全局上下文
        global_context = self._extract_global_context_from_outline(
            outline, content_type)

        # 获取故事结构
        story_structure = self._extract_story_structure_from_outline(
            outline, content_type)

        # 确定单元标签
        unit_label = self._get_unit_label(content_type)

        # 构建上下文提示
        context_parts = []

        # 1. 故事阶段定位
        phase_info = ""
        for phase in story_structure.get("story_phases", []):
            if phase["range"].startswith(f"第{unit_number}{unit_label}") or \
               f"第{unit_number}{unit_label}" in phase["range"]:
                phase_info = f"【故事阶段】本{unit_label}处于故事{phase['phase']}阶段（{phase['range']}），应侧重：{phase['purpose']}"
                break

        if phase_info:
            context_parts.append(phase_info)

        # 2. 人物设定参考
        if global_context.get("characters"):
            context_parts.append(
                f"【人物设定参考】\n{global_context['characters'][:500]}")

        # 3. 世界观参考
        if global_context.get("world_setting"):
            context_parts.append(
                f"【世界观设定】\n{global_context['world_setting'][:300]}")

        # 4. 核心冲突参考
        if global_context.get("core_conflict"):
            context_parts.append(
                f"【核心冲突】{global_context['core_conflict'][:200]}")

        # 5. 故事主线参考
        if global_context.get("main_plot"):
            context_parts.append(
                f"【故事主线】\n{global_context['main_plot'][:300]}")

        # 6. 滑动窗口摘要（增强：查看多个前序单元）
        sliding_summary = self._get_sliding_window_summary(
            existing_outlines, unit_number, content_type
        )
        if sliding_summary:
            context_parts.append(
                f"【前序{unit_label}摘要（滑动窗口）】\n{sliding_summary}")

        # 7. 前后单元衔接提示
        next_unit_info = None
        for unit in story_structure.get("existing_units", []):
            if unit["number"] == unit_number + 1:
                next_unit_info = unit
                break

        connection_hints = []
        if next_unit_info:
            connection_hints.append(
                f"后{unit_label}概要：{next_unit_info.get('title', '')}（需要为后续剧情做好铺垫）")

        if connection_hints:
            context_parts.append(
                f"【后续{unit_label}衔接】\n" + "\n".join(connection_hints))

        # 8. 最近单元的关键事件（增强）
        prev_unit = existing_outlines.get(str(unit_number - 1), {})
        if prev_unit and prev_unit.get("detailed_outline"):
            key_events = self._extract_key_events_from_outline(
                prev_unit.get("detailed_outline", ""))
            if key_events:
                context_parts.append(f"【前{unit_label}关键事件】{key_events[:200]}")

        # 组合最终提示
        final_prompt = f"""
**注意：基础大纲中缺少第{unit_number}{unit_label}的详细概要，请基于以下信息进行创作推断：**

{chr(10).join(context_parts)}

**创作要求：**
1. 确保与前文剧情逻辑连贯
2. 人物性格与设定保持一致
3. 情节发展符合故事整体走向
4. 为后续剧情预留合理的发展空间
5. 保持故事的张力和节奏感
6. 避免引入与前文矛盾的新设定
"""
        return final_prompt

    def _extract_key_events_from_outline(self, outline_content: str) -> str:
        """从详细大纲中提取关键事件"""
        import re

        if not outline_content:
            return ""

        # 尝试匹配关键事件部分
        patterns = [
            r'关键事件[：:]\s*([\s\S]*?)(?=\n\n|\n(?:核心|情感|悬念|###|$))',
            r'核心事件[：:]\s*([\s\S]*?)(?=\n\n|\n(?:核心|情感|悬念|###|$))',
            r'主要事件[：:]\s*([\s\S]*?)(?=\n\n|\n(?:核心|情感|悬念|###|$))',
        ]

        for pattern in patterns:
            match = re.search(pattern, outline_content, re.IGNORECASE)
            if match:
                events_text = match.group(1).strip()
                # 提取列表项
                events = re.findall(r'[-\*\d\.]+\s*(.+?)(?:\n|$)', events_text)
                if events:
                    return "；".join([e.strip() for e in events if e.strip()])

        return ""

    # ==================== 一致性增强：滑动窗口与置信度机制 ====================

    def _get_sliding_window_summary(
        self,
        existing_outlines: Dict[str, Any],
        current_unit: int,
        content_type: str = "novel",
        window_size: int = 5
    ) -> str:
        """
        获取滑动窗口内的摘要（替代只看前一个单元）

        滑动窗口随单元位置动态调整：
        - 早期单元：窗口小，关注近邻细节
        - 后期单元：窗口大，关注整体趋势

        Args:
            existing_outlines: 已生成的详细大纲字典
            current_unit: 当前单元编号
            content_type: 内容类型
            window_size: 基础窗口大小

        Returns:
            滑动窗口内的压缩摘要
        """
        total_units = len(existing_outlines)

        # 动态调整窗口大小
        if total_units > 50:
            # 长篇作品，后期增大窗口
            position_ratio = current_unit / max(1, total_units)
            if position_ratio > 0.7:
                window_size = min(10, window_size + 3)

        summaries = []
        start = max(1, current_unit - window_size)

        for u in range(start, current_unit):
            unit_data = existing_outlines.get(str(u), {})
            if not unit_data:
                continue

            # 提取核心摘要（压缩到100字以内）
            summary = self._compress_unit_summary(unit_data, content_type)
            if summary:
                unit_label = self._get_unit_label(content_type)
                summaries.append(f"第{u}{unit_label}: {summary}")

        if summaries:
            return "\n".join(summaries)
        return ""

    def _compress_unit_summary(
        self,
        unit_data: Dict[str, Any],
        content_type: str
    ) -> str:
        """
        将单元详细大纲压缩为核心摘要

        Args:
            unit_data: 单元数据字典
            content_type: 内容类型

        Returns:
            压缩后的摘要（100字以内）
        """
        # 优先使用简短概要
        summary = (
            unit_data.get("chapter_summary", "") or
            unit_data.get("episode_summary", "") or
            unit_data.get("scene_summary", "")
        )

        if summary and len(summary) <= 100:
            return summary

        # 如果概要过长，提取关键事件
        key_events = unit_data.get("key_events", [])
        if key_events:
            events_str = "；".join(key_events[:2])  # 只取前两个事件
            if len(events_str) <= 100:
                return events_str

        # 从详细大纲中提取
        detailed = unit_data.get("detailed_outline", "")
        if detailed:
            # 提取第一段或核心内容
            first_para = detailed.split("\n\n")[0][:100]
            return first_para.strip() + "..."

        return ""

    def _get_unit_label(self, content_type: str) -> str:
        """获取内容类型对应的单元标签"""
        if content_type == "series_script":
            return "集"
        elif content_type == "movie_script":
            return "场"
        return "章"

    # ==================== 动态上下文窗口：位置感知的内容分配策略 ====================

    def _build_position_aware_context(
        self,
        project: NovelProject,
        unit_number: int,
        content_type: str,
        max_tokens: int = 30000
    ) -> Dict[str, str]:
        """
        构建位置感知的上下文内容

        根据当前单元在整体故事中的位置，动态调整上下文内容的分配：
        - 开端阶段（前25%）：优先传递完整的世界观和人物设定
        - 发展阶段（25-50%）：平衡传递前文摘要和设定参考
        - 高潮阶段（50-75%）：优先传递冲突升级和情感曲线
        - 结局阶段（后25%）：优先传递伏笔回收和未解决冲突

        Args:
            project: 项目对象
            unit_number: 当前单元编号
            content_type: 内容类型
            max_tokens: 最大token预算（估算）

        Returns:
            位置感知的上下文字典
        """
        total_units = project.total_chapters or len(
            project.chapter_outlines or {})
        if total_units == 0:
            total_units = unit_number

        position_ratio = unit_number / max(1, total_units)

        # 获取基础内容
        global_context = self._extract_global_context_from_outline(
            project.outline_content or "", content_type
        )

        existing_outlines = project.chapter_outlines or project.episode_outlines or project.scene_outlines or {}

        result = {
            "position_phase": "",
            "characters": "",
            "world_setting": "",
            "main_plot": "",
            "core_conflict": "",
            "foreshadowing": "",
            "recent_events": "",
            "position_hint": ""
        }

        # 根据位置阶段分配内容
        if position_ratio <= 0.25:
            # 开端阶段：优先传递世界观和人物设定
            result["position_phase"] = "开端"
            result["position_hint"] = "处于故事开端阶段，重点在于建立世界观、介绍人物关系、设置初始冲突"

            # 分配更多空间给设定
            result["characters"] = global_context.get("characters", "")[:800]
            result["world_setting"] = global_context.get(
                "world_setting", "")[:600]
            result["main_plot"] = global_context.get("main_plot", "")[:400]

        elif position_ratio <= 0.5:
            # 发展阶段：平衡传递
            result["position_phase"] = "发展"
            result["position_hint"] = "处于故事发展阶段，重点在于冲突升级、人物发展、剧情推进"

            # 平衡分配
            result["characters"] = global_context.get("characters", "")[:500]
            result["world_setting"] = global_context.get(
                "world_setting", "")[:300]
            result["main_plot"] = global_context.get("main_plot", "")[:400]
            result["core_conflict"] = global_context.get(
                "core_conflict", "")[:300]

            # 获取前文关键事件
            recent = self._get_sliding_window_summary(
                existing_outlines, unit_number, content_type, 3)
            result["recent_events"] = recent

        elif position_ratio <= 0.75:
            # 高潮阶段：优先传递冲突和情感
            result["position_phase"] = "高潮"
            result["position_hint"] = "处于故事高潮阶段，重点在于核心冲突爆发、情感顶点、关键转折"

            # 减少设定，增加冲突
            result["characters"] = global_context.get("characters", "")[:300]
            result["core_conflict"] = global_context.get(
                "core_conflict", "")[:500]

            # 获取更多前文事件
            recent = self._get_sliding_window_summary(
                existing_outlines, unit_number, content_type, 5)
            result["recent_events"] = recent

            # 提取伏笔信息
            foreshadowing = self._extract_foreshadowing_from_outlines(
                existing_outlines, unit_number)
            result["foreshadowing"] = foreshadowing

        else:
            # 结局阶段：优先传递伏笔回收和未解决冲突
            result["position_phase"] = "结局"
            result["position_hint"] = "处于故事结局阶段，重点在于冲突解决、伏笔回收、收尾"

            # 最少设定，最多收尾信息
            result["core_conflict"] = global_context.get(
                "core_conflict", "")[:300]

            # 获取更多前文事件
            recent = self._get_sliding_window_summary(
                existing_outlines, unit_number, content_type, 7)
            result["recent_events"] = recent

            # 提取所有未回收的伏笔
            foreshadowing = self._extract_foreshadowing_from_outlines(
                existing_outlines, unit_number)
            result["foreshadowing"] = foreshadowing

        return result

    def _extract_foreshadowing_from_outlines(
        self,
        existing_outlines: Dict[str, Any],
        current_unit: int
    ) -> str:
        """
        从已有详细大纲中提取伏笔信息

        Args:
            existing_outlines: 已生成的详细大纲字典
            current_unit: 当前单元编号

        Returns:
            伏笔信息字符串
        """
        import re

        foreshadowing_items = []

        # 遍历前序单元，提取伏笔
        for unit_num in range(1, current_unit):
            unit_data = existing_outlines.get(str(unit_num), {})
            if not unit_data:
                continue

            # 尝试提取伏笔相关内容
            detailed = unit_data.get("detailed_outline", "")
            if not detailed:
                continue

            # 搜索伏笔标记
            patterns = [
                r'伏笔[：:][\s]*([^\n]+)',
                r'埋设[：:][\s]*([^\n]+)',
                r'预留[：:][\s]*([^\n]+)',
                r'悬念[：:][\s]*([^\n]+)',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, detailed)
                for match in matches:
                    item = match.strip()
                    if item and len(item) > 5:
                        foreshadowing_items.append(
                            f"第{unit_num}章: {item[:100]}")

        if foreshadowing_items:
            # 只返回最近5个伏笔
            return "\n".join(foreshadowing_items[-5:])
        return ""

    # ==================== 一致性校验机制 ====================

    async def _validate_outline_consistency(
        self,
        project: NovelProject,
        unit_number: int,
        generated_outline: Dict[str, Any],
        content_type: str = "novel"
    ) -> Dict[str, Any]:
        """
        校验生成的详细大纲与已有内容的一致性

        检查维度：
        1. 人物行为是否符合设定
        2. 剧情发展是否与前文矛盾
        3. 世界观设定是否被违反
        4. 时间线是否连贯

        Args:
            project: 项目对象
            unit_number: 当前单元编号
            generated_outline: 生成的详细大纲
            content_type: 内容类型

        Returns:
            校验结果字典
        """
        issues = []
        warnings = []

        # 获取全局上下文
        global_context = self._extract_global_context_from_outline(
            project.outline_content or "", content_type
        )

        # 获取已有大纲
        existing_outlines = (
            project.chapter_outlines or
            project.episode_outlines or
            project.scene_outlines or
            {}
        )

        # 1. 人物一致性检查
        character_issues = self._check_character_consistency(
            generated_outline,
            global_context.get("characters", ""),
            existing_outlines,
            unit_number
        )
        issues.extend(character_issues)

        # 2. 剧情连贯性检查
        plot_issues = self._check_plot_consistency(
            generated_outline,
            existing_outlines,
            unit_number
        )
        issues.extend(plot_issues)

        # 3. 世界观一致性检查
        world_issues = self._check_world_setting_consistency(
            generated_outline,
            global_context.get("world_setting", "")
        )
        warnings.extend(world_issues)

        # 4. 时间线检查
        timeline_issues = self._check_timeline_consistency(
            generated_outline,
            existing_outlines,
            unit_number
        )
        warnings.extend(timeline_issues)

        # 计算整体一致性分数
        total_checks = 4
        passed_checks = total_checks
        if issues:
            passed_checks -= len(issues) * 0.5
        if warnings:
            passed_checks -= len(warnings) * 0.2

        consistency_score = max(0, min(1, passed_checks / total_checks))

        return {
            "is_consistent": len(issues) == 0,
            "consistency_score": consistency_score,
            "issues": issues,
            "warnings": warnings,
            "unit_number": unit_number,
            "recommendation": self._get_consistency_recommendation(issues, warnings)
        }

    def _check_character_consistency(
        self,
        generated_outline: Dict[str, Any],
        character_setting: str,
        existing_outlines: Dict[str, Any],
        current_unit: int
    ) -> List[str]:
        """
        检查人物行为一致性

        Args:
            generated_outline: 生成的详细大纲
            character_setting: 人物设定文本
            existing_outlines: 已有详细大纲
            current_unit: 当前单元编号

        Returns:
            问题列表
        """
        issues = []
        import re

        if not character_setting:
            return issues

        detailed = generated_outline.get("detailed_outline", "")
        if not detailed:
            return issues

        # 提取人物设定中的关键信息
        # 简化检查：查找可能的人物矛盾描述词
        contradiction_patterns = [
            r'突然改变[，,]与之前.*矛盾',
            r'性格突变',
            r'人设崩塌',
            r'前后矛盾',
        ]

        for pattern in contradiction_patterns:
            if re.search(pattern, detailed):
                issues.append(f"检测到可能的人物性格矛盾: {pattern}")

        # 检查是否引入了设定中不存在的重要角色
        # 提取设定中的人物名
        setting_names = set(re.findall(
            r'[\u4e00-\u9fa5]{2,4}(?=[，,：:或])', character_setting))
        outline_names = set(re.findall(
            r'[\u4e00-\u9fa5]{2,4}(?=[说想做去来])', detailed))

        # 检查新出现的角色
        new_characters = outline_names - setting_names
        if new_characters and len(new_characters) > 2:
            issues.append(
                f"引入了多个新角色，请确认是否符合设定: {', '.join(list(new_characters)[:3])}")

        return issues

    def _check_plot_consistency(
        self,
        generated_outline: Dict[str, Any],
        existing_outlines: Dict[str, Any],
        current_unit: int
    ) -> List[str]:
        """
        检查剧情连贯性

        Args:
            generated_outline: 生成的详细大纲
            existing_outlines: 已有详细大纲
            current_unit: 当前单元编号

        Returns:
            问题列表
        """
        issues = []

        # 获取前一个单元的信息
        prev_unit = existing_outlines.get(str(current_unit - 1), {})
        if not prev_unit:
            return issues

        prev_detailed = prev_unit.get("detailed_outline", "")
        curr_detailed = generated_outline.get("detailed_outline", "")

        if not prev_detailed or not curr_detailed:
            return issues

        # 检查关键事件连续性
        prev_events = self._extract_key_events_from_outline(prev_detailed)
        curr_events = generated_outline.get("key_events", [])

        # 如果前章有未解决的悬念，检查当前章节是否有回应
        suspense_patterns = [
            r'悬念[：:][\s]*([^\n]+)',
            r'未解决[：:][\s]*([^\n]+)',
            r'待续[。！]?$',
        ]

        import re
        for pattern in suspense_patterns:
            matches = re.findall(pattern, prev_detailed)
            for match in matches:
                # 检查当前章节是否回应了这个悬念
                suspense_topic = match.strip()[:20]
                if suspense_topic and suspense_topic not in curr_detailed:
                    issues.append(f"前章悬念未得到回应: {suspense_topic}...")

        return issues

    def _check_world_setting_consistency(
        self,
        generated_outline: Dict[str, Any],
        world_setting: str
    ) -> List[str]:
        """
        检查世界观一致性

        Args:
            generated_outline: 生成的详细大纲
            world_setting: 世界观设定文本

        Returns:
            警告列表
        """
        warnings = []

        if not world_setting:
            return warnings

        detailed = generated_outline.get("detailed_outline", "")
        if not detailed:
            return warnings

        # 检查是否有可能违反世界观的描述
        # 这是一个简化检查，实际可以更复杂
        violation_keywords = ['违反', '违背', '不可能', '矛盾']
        for keyword in violation_keywords:
            if keyword in detailed:
                warnings.append(f"检测到可能的世界观冲突关键词: '{keyword}'")
                break

        return warnings

    def _check_timeline_consistency(
        self,
        generated_outline: Dict[str, Any],
        existing_outlines: Dict[str, Any],
        current_unit: int
    ) -> List[str]:
        """
        检查时间线一致性

        Args:
            generated_outline: 生成的详细大纲
            existing_outlines: 已有详细大纲
            current_unit: 当前单元编号

        Returns:
            警告列表
        """
        warnings = []
        import re

        # 简化检查：查找时间跳跃描述
        detailed = generated_outline.get("detailed_outline", "")
        if not detailed:
            return warnings

        # 检查是否有不合理的时间跳跃
        time_jump_patterns = [
            r'([一二三四五六七八九十百]+年)后',
            r'([一二三四五六七八九十百]+个月)后',
            r'转眼([一二三四五六七八九十百]+年)',
        ]

        for pattern in time_jump_patterns:
            match = re.search(pattern, detailed)
            if match:
                warnings.append(f"检测到时间跳跃: {match.group(0)}，请确认是否合理")

        return warnings

    def _get_consistency_recommendation(
        self,
        issues: List[str],
        warnings: List[str]
    ) -> str:
        """
        根据校验结果生成建议

        Args:
            issues: 问题列表
            warnings: 警告列表

        Returns:
            建议文本
        """
        if not issues and not warnings:
            return "生成内容与已有内容高度一致，可以直接采用。"

        if issues:
            return f"发现{len(issues)}个一致性问题，建议检查并修改后再采用。"

        return f"发现{len(warnings)}个潜在风险，建议确认后采用。"

    # ==================== 用户干预机制 ====================

    async def generate_outline_with_intervention(
        self,
        project: NovelProject,
        unit_number: int,
        content_type: str = "novel",
        user_choice: Optional[str] = None,
        user_guidance: Optional[str] = None,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        带用户干预选项的详细大纲生成

        当推断置信度过低时，提供用户干预选项：
        1. 接受推断生成
        2. 提供章节概要
        3. 参考相邻章节
        4. 跳过此章节

        Args:
            project: 项目对象
            unit_number: 单元编号
            content_type: 内容类型
            user_choice: 用户选择 ("accept"/"provide"/"reference"/"skip")
            user_guidance: 用户提供的指导文本
            force_regenerate: 是否强制重新生成（即使已存在详细大纲）

        Returns:
            生成结果或干预请求
        """
        # 清理之前可能残留的取消状态（单个生成不受批量取消影响）
        from app.services.task_manager import clear_memory_cancel_token, TaskManager
        clear_memory_cancel_token(project.id)
        # 同时清理 Redis 中的任务状态
        await TaskManager.delete_task(project.id)
        self.logger.info(f"[详细大纲] 已清理残留取消状态: project_id={project.id}")

        # 确保 unit_summaries 数据已加载
        unit_summaries = getattr(project, 'unit_summaries', None) or {}
        if not unit_summaries and project.total_chapters and project.total_chapters > 0:
            self.logger.warning(
                f"[详细大纲] unit_summaries 为空，尝试从数据库重新加载: project_id={project.id}"
            )
            try:
                from sqlalchemy import select
                fresh_query = select(NovelProject).where(
                    NovelProject.id == project.id)
                fresh_result = await self.db.execute(fresh_query)
                fresh_project = fresh_result.scalar_one_or_none()
                if fresh_project:
                    fresh_summaries = getattr(
                        fresh_project, 'unit_summaries', None)
                    if fresh_summaries:
                        project.unit_summaries = fresh_summaries
                        self.logger.info(
                            f"[详细大纲] 从数据库重新加载 unit_summaries 成功: {len(fresh_summaries)} 个单元"
                        )
            except Exception as e:
                self.logger.error(f"[详细大纲] 重新加载 unit_summaries 失败: {e}")

        # 获取现有大纲
        existing_outlines = (
            project.chapter_outlines or
            project.episode_outlines or
            project.scene_outlines or
            {}
        )

        # 检查是否已存在详细大纲
        existing_unit = existing_outlines.get(str(unit_number), {})
        if existing_unit.get("detailed_outline") and not force_regenerate and user_choice is None:
            # 已存在详细大纲，返回跳过状态
            self.logger.info(f"[详细大纲] 第{unit_number}单元已存在详细大纲，跳过生成")
            return {
                "status": "already_exists",
                "message": f"第{unit_number}单元已存在详细大纲",
                "existing_outline": existing_unit
            }

        # 检查是否有原始概要（优先从 unit_summaries 获取）
        unit_summary = self._get_unit_summary_from_project(
            project, unit_number, content_type)
        has_original_summary = bool(
            unit_summary and not unit_summary.startswith("（请根据"))

        # 如果有原始概要，直接生成
        if has_original_summary:
            self.logger.info(
                f"[详细大纲] 第{unit_number}单元有原始概要，直接生成"
            )
            return await self._generate_outline_directly(
                project, unit_number, content_type, unit_summary
            )

        # 没有原始概要，需要用户干预
        if user_choice is None:
            # 构建推断概要
            inferred_summary = self._build_missing_unit_context(
                project.outline_content or "",
                unit_number,
                content_type,
                existing_outlines
            )

            # 返回干预请求
            return {
                "status": "need_intervention",
                "message": f"第{unit_number}单元缺少原始概要，请选择处理方式",
                "inferred_summary": inferred_summary,
                "options": [
                    {
                        "key": "accept",
                        "label": "接受推断生成",
                        "description": "基于推断上下文生成，可能需要后续调整"
                    },
                    {
                        "key": "provide",
                        "label": "提供章节概要",
                        "description": "输入您的概要内容，提高生成质量"
                    },
                    {
                        "key": "reference",
                        "label": "参考相邻章节",
                        "description": "查看前后章节，手动补充概要"
                    },
                    {
                        "key": "skip",
                        "label": "跳过此章节",
                        "description": "暂不生成此章节详细大纲"
                    }
                ]
            }

        # 处理用户选择
        if user_choice == "accept":
            self.logger.info(f"[详细大纲] 用户选择接受推断生成，第{unit_number}单元")
            return await self._generate_outline_directly(
                project, unit_number, content_type,
                user_guidance=self._build_missing_unit_context(
                    project.outline_content or "",
                    unit_number,
                    content_type,
                    existing_outlines
                )
            )

        elif user_choice == "provide":
            if not user_guidance:
                return {
                    "status": "need_guidance",
                    "message": "请提供章节概要内容"
                }
            self.logger.info(f"[详细大纲] 用户提供了概要，第{unit_number}单元")
            return await self._generate_outline_directly(
                project, unit_number, content_type, user_guidance=user_guidance
            )

        elif user_choice == "reference":
            # 参考相邻章节重新生成大纲
            prev_unit = existing_outlines.get(str(unit_number - 1), {})
            next_unit = existing_outlines.get(str(unit_number + 1), {})

            # 构建参考上下文
            reference_context = ""
            if prev_unit:
                prev_summary = prev_unit.get("chapter_summary", "") or (prev_unit.get(
                    "detailed_outline", "")[:500] if prev_unit.get("detailed_outline") else "")
                if prev_summary:
                    reference_context += f"【前一章概要】\n{prev_summary}\n\n"
            if next_unit:
                next_summary = next_unit.get("chapter_summary", "") or (next_unit.get(
                    "detailed_outline", "")[:500] if next_unit.get("detailed_outline") else "")
                if next_summary:
                    reference_context += f"【后一章概要】\n{next_summary}\n\n"

            if reference_context:
                self.logger.info(f"[详细大纲] 参考相邻章节重新生成，第{unit_number}单元")
                # 使用参考上下文重新生成
                return await self._generate_outline_directly(
                    project, unit_number, content_type,
                    user_guidance=f"请参考以下相邻章节信息来生成本章详细大纲：\n{reference_context}"
                )
            else:
                # 没有相邻章节信息，直接重新生成
                self.logger.info(f"[详细大纲] 无相邻章节信息，直接重新生成，第{unit_number}单元")
                return await self._generate_outline_directly(
                    project, unit_number, content_type
                )

        elif user_choice == "skip":
            return {
                "status": "skipped",
                "message": f"已跳过第{unit_number}单元的详细大纲生成"
            }

        return {"status": "error", "message": "无效的用户选择"}

    def _get_unit_summary_from_project(
        self,
        project: NovelProject,
        unit_number: int,
        content_type: str
    ) -> str:
        """
        从项目数据中获取单元概要

        优先级：
        1. unit_summaries（两阶段大纲的单元概述）
        2. chapter_outlines/episode_outlines/scene_outlines（已生成的详细大纲）

        Args:
            project: 项目对象
            unit_number: 单元编号
            content_type: 内容类型

        Returns:
            单元概要文本
        """
        unit_key = str(unit_number)

        # 优先从 unit_summaries 获取（两阶段大纲）
        unit_summaries = getattr(project, 'unit_summaries', None) or {}
        if unit_key in unit_summaries:
            unit_data = unit_summaries[unit_key]
            if isinstance(unit_data, dict):
                summary = unit_data.get('summary', '')
                if summary:
                    self.logger.debug(
                        f"[单元概要] 从 unit_summaries 获取第{unit_number}单元概要成功，长度={len(summary)}"
                    )
                    return summary

        # 回退到已生成的详细大纲
        if content_type == "novel":
            outlines = project.chapter_outlines or {}
            unit_data = outlines.get(unit_key, {})
            return unit_data.get("chapter_summary", "")
        elif content_type == "series_script":
            outlines = project.episode_outlines or {}
            unit_data = outlines.get(unit_key, {})
            return unit_data.get("episode_summary", "")
        elif content_type == "movie_script":
            outlines = project.scene_outlines or {}
            unit_data = outlines.get(unit_key, {})
            return unit_data.get("scene_summary", "")
        return ""

    async def _generate_outline_directly(
        self,
        project: NovelProject,
        unit_number: int,
        content_type: str,
        user_guidance: str = None,
        force_regenerate: bool = True  # 默认强制重新生成
    ) -> Dict[str, Any]:
        """
        直接生成详细大纲

        Args:
            project: 项目对象
            unit_number: 单元编号
            content_type: 内容类型
            user_guidance: 用户提供的概要或参考信息（可选）
            force_regenerate: 是否强制重新生成（默认True）

        Returns:
            生成结果（统一格式：status/message/data）
        """
        # 调用相应的生成方法
        if content_type == "novel":
            result = await self.generate_chapter_outline(project, unit_number, force_regenerate=force_regenerate, user_guidance=user_guidance)
        elif content_type == "series_script":
            result = await self.generate_episode_outline(project, unit_number, user_guidance=user_guidance)
        elif content_type == "movie_script":
            result = await self.generate_scene_outline(project, unit_number, user_guidance=user_guidance)
        else:
            return {"status": "error", "message": f"不支持的内容类型: {content_type}"}

        # 转换返回格式：generate_chapter_outline 返回 success/content/parsed
        # 需要转换为 status/message/data 格式
        if result.get("success"):
            return {
                "status": "success",
                "message": f"第{unit_number}单元详细大纲生成成功",
                "data": {
                    "unit_number": unit_number,
                    "content": result.get("content"),
                    "parsed": result.get("parsed"),
                    "duration_ms": result.get("duration_ms", 0)
                }
            }
        else:
            return {
                "status": "error",
                "message": result.get("error_message", "生成失败"),
                "data": result
            }
