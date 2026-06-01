"""
上下文窗口管理器 - 章节数据获取Mixin

提供前文摘要、角色状态、近章内容、大纲元信息等数据获取功能。

@date: 2026-04-24
@version: v3.1.0 (从context_manager.py拆分)
"""
import os
import json
import aiofiles
from typing import Dict, Any, List

from app.models import NovelChapter


class ChapterDataMixin:
    """章节数据获取Mixin"""

    async def _get_summary(self, project) -> str:
        """获取前文摘要"""
        if not project.summary_file or not os.path.exists(project.summary_file):
            return ""

        try:
            async with aiofiles.open(project.summary_file, 'r', encoding='utf-8') as f:
                summary = await f.read()
                # 不再限制长度，直接返回完整内容
                return summary
        except Exception as e:
            self.logger.warning(f"读取摘要文件失败: {str(e)}")
            return ""

    async def _get_character_state(self, project) -> str:
        """获取角色状态"""
        if not project.characters_file or not os.path.exists(project.characters_file):
            return ""

        try:
            async with aiofiles.open(project.characters_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                characters = json.loads(content)
                # 格式化为文本
                return self._format_character_state(characters)
        except Exception as e:
            self.logger.warning(f"读取角色状态文件失败: {str(e)}")
            return ""

    def _format_character_state(self, characters: Dict[str, Any]) -> str:
        """格式化角色状态为文本"""
        lines = []
        for name, state in characters.items():
            lines.append(f"【{name}】")
            if isinstance(state, dict):
                for key, value in state.items():
                    if isinstance(value, dict):
                        lines.append(f"  {key}:")
                        for k, v in value.items():
                            lines.append(f"    - {k}: {v}")
                    elif isinstance(value, list):
                        lines.append(f"  {key}: {', '.join(value)}")
                    else:
                        lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    async def _get_recent_chapters(
        self,
        project,
        current_num: int
    ) -> Dict[str, str]:
        """获取最近N章内容（滑动窗口）"""
        result = {
            "endings": "",
            "summary": ""
        }

        start = max(1, current_num - self.recent_chapters_count)
        endings = []

        # 从数据库获取最近章节
        from sqlalchemy import select
        query = select(NovelChapter).where(
            NovelChapter.project_id == project.id,
            NovelChapter.chapter_number < current_num,
            NovelChapter.chapter_number >= start
        ).order_by(NovelChapter.chapter_number)

        chapters_result = await self.db.execute(query)
        chapters = chapters_result.scalars().all()

        for chapter in chapters:
            content = chapter.final_content or chapter.draft_content or ""
            if content:
                # 只取章节结尾部分（约800字）
                excerpt = content[-800:] if len(content) > 800 else content
                endings.append(f"第{chapter.chapter_number}章结尾：\n{excerpt}")

        result["endings"] = "\n\n".join(endings)

        # 生成简短摘要（如果有多个前章）
        if len(chapters) > 1:
            result["summary"] = self._generate_short_summary(chapters)

        return result

    def _generate_short_summary(self, chapters: List[NovelChapter]) -> str:
        """生成最近章节的简短摘要"""
        summaries = []
        for chapter in chapters[-3:]:  # 最近3章
            metadata = chapter.chapter_metadata or {}
            summary = metadata.get("chapter_summary", "")
            if summary:
                summaries.append(f"第{chapter.chapter_number}章: {summary}")
        return " | ".join(summaries)

    async def _get_outline_metadata(self, project) -> str:
        """
        获取大纲元信息（不再嵌入完整大纲内容）

        重构说明：
        - 不再将完整大纲嵌入提示词，避免上下文冗余
        - 仅返回大纲的基本元信息，供LLM了解项目概况
        - 完整的大纲信息通过GraphRAG知识图谱在修正阶段使用
        - 支持两阶段大纲生成机制

        Returns:
            大纲元信息字符串
        """
        # 检查是否有大纲（支持两阶段大纲）
        has_global_outline = bool(
            getattr(project, 'global_outline_content', None))
        has_unit_summaries = bool(getattr(project, 'unit_summaries', None))
        has_outline = bool(project.outline_content) or bool(
            project.outline_file_path)

        if not has_outline and not has_global_outline:
            self.logger.warning(f"[大纲元信息] 项目无大纲内容: project_id={project.id}")
            return "（未上传大纲）"

        # 获取大纲长度信息（支持两阶段大纲）
        global_outline_len = len(project.global_outline_content) if hasattr(
            project, 'global_outline_content') and project.global_outline_content else 0
        outline_len = len(
            project.outline_content) if project.outline_content else 0

        # 获取单元概述数量
        unit_summaries = getattr(project, 'unit_summaries', None) or {}
        unit_summaries_count = len(unit_summaries)

        # 获取内容类型
        content_type = getattr(project, 'content_type', 'novel')
        type_name = {
            'novel': '小说',
            'series_script': '剧集剧本',
            'movie_script': '电影剧本'
        }.get(content_type, '未知类型')

        # 获取总单元数
        total_units = project.total_chapters or 0

        # 获取两阶段大纲状态
        global_outline_status = getattr(
            project, 'global_outline_status', 'pending')
        unit_summaries_status = getattr(
            project, 'unit_summaries_status', 'pending')

        # 构建元信息
        if has_global_outline:
            # 两阶段大纲模式
            metadata = f"""【项目大纲信息】
- 类型：{type_name}
- 大纲模式：两阶段大纲
- 全局大纲长度：{global_outline_len}字
- 全局大纲状态：{global_outline_status}
- 单元概述数量：{unit_summaries_count}个
- 单元概述状态：{unit_summaries_status}
- 总单元数：{total_units}
- 知识库状态：{project.kb_status or 'pending'}

注意：全局大纲内容已存入项目专属知识库，单元概述将用于指导正文生成。"""
        else:
            # 旧版大纲模式
            metadata = f"""【项目大纲信息】
- 类型：{type_name}
- 大纲长度：{outline_len}字
- 总单元数：{total_units}
- 知识库状态：{project.kb_status or 'pending'}

注意：完整大纲内容已存入项目专属知识库，通过知识图谱检索使用。"""

        self.logger.info(
            f"[大纲元信息] 返回大纲元信息: type={type_name}, global_outline={global_outline_len}, outline={outline_len}")
        return metadata

    async def _build_unit_summaries(
        self,
        project,
        current_unit: int,
        content_type: str,
        chapter_metadata: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        构建单元摘要上下文（重构核心方法）

        替代原有的完整大纲嵌入，提供精简的摘要信息：
        1. previous_content_summaries: 前三单元的正文摘要
        2. previous_outline_summaries: 当前单元之前所有单元的大纲摘要
        3. unit_outline_summary: 当前单元的大纲摘要（精简版）
        """
        result = {
            "previous_content_summaries": "",
            "previous_outline_summaries": "",
            "unit_outline_summary": ""
        }

        try:
            # 1. 获取前三单元正文摘要
            result["previous_content_summaries"] = await self._get_previous_content_summaries(
                project, current_unit, content_type
            )

            # 2. 获取前序单元大纲摘要
            result["previous_outline_summaries"] = await self._get_previous_outline_summaries(
                project, current_unit, content_type
            )

            # 3. 获取当前单元大纲摘要
            result["unit_outline_summary"] = await self._get_current_unit_outline_summary(
                project, current_unit, content_type, chapter_metadata
            )

            self.logger.info(
                f"[单元摘要] 构建完成: unit={current_unit}, "
                f"content_summaries_len={len(result['previous_content_summaries'])}, "
                f"outline_summaries_len={len(result['previous_outline_summaries'])}"
            )

            return result

        except Exception as e:
            self.logger.error(f"构建单元摘要失败: {str(e)}")
            return result

    async def _get_previous_content_summaries(
        self,
        project,
        current_unit: int,
        content_type: str,
        max_units: int = 5  # 架构优化：从3增加到5，增强前文参考
    ) -> str:
        """
        获取前N单元的正文摘要（架构优化版：增强滑动窗口）
        """
        summaries = []

        try:
            # 计算需要获取的单元范围
            start_unit = max(1, current_unit - max_units)

            # 从数据库获取已完成的章节
            from sqlalchemy import select

            if content_type == "novel":
                query = select(NovelChapter).where(
                    NovelChapter.project_id == project.id,
                    NovelChapter.chapter_number < current_unit,
                    NovelChapter.chapter_number >= start_unit,
                    NovelChapter.final_content != None
                ).order_by(NovelChapter.chapter_number.desc()).limit(max_units)
            elif content_type in ("series_script", "script"):
                query = select(NovelChapter).where(
                    NovelChapter.project_id == project.id,
                    NovelChapter.episode_number < current_unit,
                    NovelChapter.episode_number >= start_unit,
                    NovelChapter.final_content != None
                ).order_by(NovelChapter.episode_number.desc()).limit(max_units)
            elif content_type == "movie_script":
                query = select(NovelChapter).where(
                    NovelChapter.project_id == project.id,
                    NovelChapter.scene_number < current_unit,
                    NovelChapter.scene_number >= start_unit,
                    NovelChapter.final_content != None
                ).order_by(NovelChapter.scene_number.desc()).limit(max_units)
            else:
                return ""

            chapters_result = await self.db.execute(query)
            chapters = chapters_result.scalars().all()

            for chapter in chapters:
                content = chapter.final_content or ""

                # v3.1: 优先使用QC修正稿内容（增强上下文质量）
                # 尝试从 WritingUnit 获取 content_after_qc_fix
                if content:
                    chapter_num = chapter.chapter_number or chapter.episode_number or chapter.scene_number or 0
                    try:
                        from app.models.writing_unit import WritingUnit
                        from app.models.writing_task import WritingTask
                        task_query = select(WritingTask).where(
                            WritingTask.project_id == project.id
                        )
                        task_result = await self.db.execute(task_query)
                        tasks = task_result.scalars().all()
                        if tasks:
                            task_ids = [t.id for t in tasks]
                            unit_q = select(WritingUnit).where(
                                WritingUnit.unit_index == chapter_num,
                                WritingUnit.task_id.in_(task_ids),
                                WritingUnit.content_after_qc_fix.isnot(None),
                                WritingUnit.content_after_qc_fix != ''
                            ).order_by(WritingUnit.id.desc()).limit(1)
                            unit_r = await self.db.execute(unit_q)
                            matched_unit = unit_r.scalars().first()
                            if matched_unit and matched_unit.content_after_qc_fix:
                                content = matched_unit.content_after_qc_fix
                                self.logger.debug(
                                    f"[前文摘要] 单元{chapter_num}使用修正稿: "
                                    f"{len(content)}字符"
                                )
                    except Exception as lookup_err:
                        self.logger.debug(
                            f"[前文摘要] 查询修正稿跳过: unit={chapter_num}, "
                            f"err={lookup_err}"
                        )

                if content:
                    # 不再截断，直接使用完整内容
                    summary = content
                    unit_num = chapter.chapter_number or chapter.episode_number or chapter.scene_number or 0

                    if content_type == "novel":
                        label = f"第{unit_num}章正文摘要"
                    elif content_type in ("series_script", "script"):
                        label = f"第{unit_num}集正文摘要"
                    else:
                        label = f"第{unit_num}场正文摘要"

                    summaries.append(f"【{label}】\n{summary}")

            if summaries:
                return "\n\n".join(summaries)

            return "（无前序正文内容）"

        except Exception as e:
            self.logger.error(f"获取前序正文摘要失败: {str(e)}")
            return ""

    async def _get_previous_outline_summaries(
        self,
        project,
        current_unit: int,
        content_type: str,
        max_summaries: int = 10
    ) -> str:
        """获取当前单元之前所有单元的大纲摘要"""
        summaries = []

        try:
            # 根据内容类型获取大纲数据
            if content_type == "novel":
                outlines = project.unit_summaries or {}
                unit_label = "章"
            elif content_type in ("series_script", "script"):
                outlines = project.episode_outlines or {}
                unit_label = "集"
            elif content_type == "movie_script":
                outlines = project.scene_outlines or {}
                unit_label = "场"
            else:
                return ""

            # 计算需要获取的单元范围
            start_unit = max(1, current_unit - max_summaries)

            for unit_num in range(start_unit, current_unit):
                unit_key = str(unit_num)
                if unit_key in outlines:
                    outline = outlines[unit_key]

                    # 提取摘要信息 - 不再截断
                    if content_type == "novel":
                        title = outline.get("title", f"第{unit_num}章")
                        summary = outline.get("summary", "")
                    elif content_type in ("series_script", "script"):
                        title = outline.get("episode_title", f"第{unit_num}集")
                        summary = outline.get("episode_summary", "") or outline.get(
                            "detailed_outline", "")
                    else:
                        title = outline.get("scene_title", f"第{unit_num}场")
                        summary = outline.get("scene_summary", "") or outline.get(
                            "detailed_outline", "")

                    if summary:
                        summaries.append(
                            f"【第{unit_num}{unit_label}《{title}》大纲摘要】\n{summary}")

            if summaries:
                return "\n\n".join(summaries)

            return "（无前序单元大纲）"

        except Exception as e:
            self.logger.error(f"获取前序大纲摘要失败: {str(e)}")
            return ""

    async def _get_current_unit_outline_summary(
        self,
        project,
        current_unit: int,
        content_type: str,
        chapter_metadata: Dict[str, Any]
    ) -> str:
        """获取当前单元的大纲摘要（精简版）"""
        try:
            # 根据内容类型获取大纲数据
            if content_type == "novel":
                outlines = project.unit_summaries or {}
                unit_key = str(current_unit)
                unit_label = "章"

                if unit_key in outlines:
                    outline = outlines[unit_key]
                    title = outline.get("title", f"第{current_unit}章")
                    summary = outline.get("summary", "")

                    result = f"【第{current_unit}{unit_label}《{title}》大纲】\n"
                    if summary:
                        result += f"章节概要：{summary}\n"

                    return result

            elif content_type in ("series_script", "script"):
                outlines = project.episode_outlines or {}
                unit_key = str(current_unit)

                if unit_key in outlines:
                    outline = outlines[unit_key]
                    title = outline.get("episode_title", f"第{current_unit}集")
                    summary = outline.get("episode_summary", "")
                    core_conflict = outline.get("core_conflict", "")
                    scenes = outline.get("scenes", [])

                    result = f"【第{current_unit}集《{title}》大纲】\n"
                    if summary:
                        result += f"本集概要：{summary}\n"
                    if core_conflict:
                        result += f"核心冲突：{core_conflict}\n"
                    if scenes:
                        result += f"场景数：{len(scenes)}场\n"

                    return result

            elif content_type == "movie_script":
                outlines = project.scene_outlines or {}
                unit_key = str(current_unit)

                if unit_key in outlines:
                    outline = outlines[unit_key]
                    title = outline.get("scene_title", f"第{current_unit}场")
                    location = outline.get("location", "")
                    summary = outline.get("scene_summary", "")
                    purpose = outline.get("scene_purpose", "")

                    result = f"【第{current_unit}场《{title}》大纲】\n"
                    if location:
                        result += f"场景地点：{location}\n"
                    if summary:
                        result += f"场景概要：{summary}\n"
                    if purpose:
                        result += f"本场任务：{purpose}\n"

                    return result

            # 回退：尝试从基础大纲提取
            return await self._get_current_unit_outline(
                project, current_unit, chapter_metadata
            )

        except Exception as e:
            self.logger.error(f"获取当前单元大纲摘要失败: {str(e)}")
            return ""

    async def _get_outline_content(self, project) -> str:
        """
        获取完整大纲内容（已废弃，保留向后兼容）

        注意：此方法已被 _get_outline_metadata() 替代
        """
        self.logger.warning(
            "[已废弃] _get_outline_content 方法已废弃，请使用 _get_outline_metadata")
        return await self._get_outline_metadata(project)
