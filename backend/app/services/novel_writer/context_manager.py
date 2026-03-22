"""
上下文窗口管理器
管理章节生成时的上下文构建，包括滑动窗口、摘要压缩等
支持知识库三层检索、GraphRAG增强、内容规则应用
"""
import os
import json
import aiofiles
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models import NovelProject, NovelChapter
from app.services.novel_writer.vector_store import ProjectVectorStore
from app.services.novel_writer.knowledge_integration import NovelKnowledgeIntegration
from app.services.proofread.document_formatter import DocumentFormatter


class ContextWindowManager:
    """上下文窗口管理器

    负责构建章节生成时的上下文，包括：
    1. 前文摘要（压缩后）
    2. 角色状态
    3. 最近N章内容（滑动窗口）
    4. 当前章节元数据
    5. 向量检索相关内容
    6. 知识库内容
    """

    def __init__(
        self,
        db: AsyncSession,
        max_context_tokens: int = 4096,
        recent_chapters_count: int = 3,
        summary_max_chars: int = 2000,
        vector_retrieve_k: int = 2
    ):
        self.db = db
        self.max_context_tokens = max_context_tokens
        self.recent_chapters_count = recent_chapters_count
        self.summary_max_chars = summary_max_chars
        self.vector_retrieve_k = vector_retrieve_k
        self.logger = get_logger("context_manager")
        self.vector_store = ProjectVectorStore()
        # 初始化文档格式化器
        self.formatter = DocumentFormatter(content_type="novel")
        # 上下文压缩配置
        self.compression_threshold = 6000  # 超过此长度触发压缩
        self.target_compressed_length = 4000  # 压缩后目标长度

    def _compress_context(
        self,
        context: Dict[str, Any],
        max_length: int = None
    ) -> Dict[str, Any]:
        """
        智能压缩上下文内容

        当上下文总长度超过阈值时，按优先级压缩各部分内容：
        1. 低优先级：历史参考、向量检索结果
        2. 中优先级：前序章节摘要、角色状态
        3. 高优先级：当前章节大纲、知识库上下文

        Args:
            context: 原始上下文字典
            max_length: 最大允许长度

        Returns:
            压缩后的上下文字典
        """
        if max_length is None:
            max_length = self.target_compressed_length

        # 计算当前总长度
        total_length = sum(
            len(str(v)) for v in context.values() if isinstance(v, str)
        )

        if total_length <= max_length:
            return context

        self.logger.info(
            f"[上下文压缩] 开始压缩: 原始长度={total_length}, 目标={max_length}")

        compressed = dict(context)
        current_length = total_length

        # 定义压缩优先级（从低到高）
        compression_order = [
            # 低优先级 - 可以大幅压缩
            ("vector_context", 0.3),  # 保留30%
            ("previous_scene_ending", 0.4),  # 保留40%
            ("short_summary", 0.5),  # 保留50%
            # 中优先级
            ("previous_content_summaries", 0.6),  # 保留60%
            ("previous_outline_summaries", 0.6),
            ("previous_episodes_summary", 0.6),
            ("character_state", 0.7),
            # 高优先级 - 尽量保留
            ("global_summary", 0.8),
            ("knowledge_context", 0.8),
            ("unit_outline_summary", 0.9),
            ("chapter_detailed_outline", 0.9),
            ("current_unit_outline", 0.9),
        ]

        for field, keep_ratio in compression_order:
            if current_length <= max_length:
                break

            original_value = compressed.get(field, "")
            if not original_value or not isinstance(original_value, str):
                continue

            original_len = len(original_value)
            target_len = int(original_len * keep_ratio)

            if target_len < original_len:
                # 智能截断：在句子边界处截断
                truncated = self._smart_truncate(original_value, target_len)
                compressed[field] = truncated
                reduction = original_len - len(truncated)
                current_length -= reduction
                self.logger.debug(
                    f"[上下文压缩] {field}: {original_len} -> {len(truncated)} (-{reduction})"
                )

        # 最终检查
        final_length = sum(
            len(str(v)) for v in compressed.values() if isinstance(v, str)
        )
        self.logger.info(
            f"[上下文压缩] 压缩完成: {total_length} -> {final_length}")

        return compressed

    def _smart_truncate(self, text: str, max_len: int) -> str:
        """
        智能截断文本

        在句子边界处截断，保持语义完整性。

        Args:
            text: 原始文本
            max_len: 最大长度

        Returns:
            截断后的文本
        """
        if len(text) <= max_len:
            return text

        # 在max_len附近寻找句子边界
        # 优先在句号、感叹号、问号后截断
        search_start = max(0, max_len - 100)
        search_end = min(len(text), max_len + 50)
        search_text = text[search_start:search_end]

        # 查找句子结束标记
        sentence_enders = ['。', '！', '？', '."',
                           '!”', '？”', '.\n', '!\n', '?\n']
        best_pos = -1

        for ender in sentence_enders:
            pos = search_text.rfind(ender)
            if pos > best_pos:
                best_pos = pos + len(ender)

        if best_pos > 0:
            # 在句子边界处截断
            truncate_pos = search_start + best_pos
            if truncate_pos <= max_len + 50:
                return text[:truncate_pos].strip()

        # 没找到句子边界，在词边界处截断
        # 查找最后一个空格或换行
        last_space = text[:max_len].rfind(' ')
        last_newline = text[:max_len].rfind('\n')
        truncate_pos = max(last_space, last_newline)

        if truncate_pos > max_len * 0.8:
            return text[:truncate_pos].strip()

        # 最后手段：直接截断
        return text[:max_len].strip()

    async def build_chapter_context(
        self,
        project: NovelProject,
        chapter_num: int,
        chapter_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建章节生成上下文

        Args:
            project: 项目对象
            chapter_num: 当前章节号
            chapter_metadata: 章节元数据

        Returns:
            上下文字典
        """
        context = {
            "global_summary": "",
            "character_state": "",
            "short_summary": "",
            "previous_scene_ending": "",
            "knowledge_context": "",
            "vector_context": "",
            # 新增：大纲元信息（不再嵌入完整大纲内容）
            "outline_metadata": "",
            "current_unit_outline": "",
            "episode_outline": "",  # 剧集分集大纲
            "previous_episodes_summary": "",  # 前序集数大纲摘要
            # 新增：单元摘要上下文（重构后新增）
            "previous_content_summaries": "",  # 前三单元正文摘要
            "previous_outline_summaries": "",  # 前序单元大纲摘要
            "unit_outline_summary": "",  # 当前单元大纲摘要（精简版）
            "chapter_detailed_outline": ""
        }

        try:
            # 1. 获取前文摘要
            context["global_summary"] = await self._get_summary(project)

            # 2. 获取角色状态
            context["character_state"] = await self._get_character_state(project)

            # 3. 获取最近章节内容（滑动窗口）
            recent_context = await self._get_recent_chapters(project, chapter_num)
            context["previous_scene_ending"] = recent_context.get(
                "endings", "")
            context["short_summary"] = recent_context.get("summary", "")

            # 4. 获取向量检索相关内容
            context["vector_context"] = await self._get_vector_context(
                project, chapter_metadata, chapter_num
            )

            # 5. 获取知识库内容（如果配置了）
            context["knowledge_context"] = await self._get_knowledge_context(
                project, chapter_metadata
            )

            # 6. 获取大纲元信息（不再嵌入完整大纲）
            context["outline_metadata"] = await self._get_outline_metadata(project)

            # 7. 构建单元摘要上下文（重构核心：替代完整大纲嵌入）
            content_type = getattr(project, 'content_type', 'novel')
            unit_summaries = await self._build_unit_summaries(project, chapter_num, content_type, chapter_metadata)
            context["previous_content_summaries"] = unit_summaries.get(
                "previous_content_summaries", "")
            context["previous_outline_summaries"] = unit_summaries.get(
                "previous_outline_summaries", "")
            context["unit_outline_summary"] = unit_summaries.get(
                "unit_outline_summary", "")

            # 8. 获取当前章节/分集对应的大纲片段（从基础大纲提取）
            context["current_unit_outline"] = await self._get_current_unit_outline(
                project, chapter_num, chapter_metadata
            )

            # 9. 获取单章详细大纲（从 chapter_outlines 数据库字段）
            context["chapter_detailed_outline"] = await self._get_chapter_detailed_outline(
                project, chapter_num
            )

            # 10. 剧集剧本专用：获取当前分集的大纲
            if content_type in ('series_script', 'script'):
                episode_num = chapter_metadata.get('episode_number', 1)
                context["episode_outline"] = await self._get_episode_outline(
                    project, episode_num
                )
                # 11. 获取前序集数的大纲摘要
                context["previous_episodes_summary"] = await self._get_previous_episodes_summary(
                    project, episode_num
                )

            return context

        except Exception as e:
            self.logger.error(f"构建章节上下文失败: {str(e)}")
            return context

    async def _get_summary(self, project: NovelProject) -> str:
        """获取前文摘要"""
        if not project.summary_file or not os.path.exists(project.summary_file):
            return ""

        try:
            async with aiofiles.open(project.summary_file, 'r', encoding='utf-8') as f:
                summary = await f.read()
                # 限制长度
                if len(summary) > self.summary_max_chars:
                    summary = summary[:self.summary_max_chars] + "..."
                return summary
        except Exception as e:
            self.logger.warning(f"读取摘要文件失败: {str(e)}")
            return ""

    async def _get_character_state(self, project: NovelProject) -> str:
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
        project: NovelProject,
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

    async def _get_vector_context(
        self,
        project: NovelProject,
        chapter_metadata: Dict[str, Any],
        current_chapter_num: int = 1
    ) -> str:
        """从项目向量库检索相关内容"""
        if not project.vectorstore_path:
            return ""

        try:
            # 构建检索查询
            query = self._build_vector_query(chapter_metadata)

            # 检索
            results = await self.vector_store.retrieve(
                collection_name=f"project_{project.id}",
                query=query,
                n_results=self.vector_retrieve_k
            )

            if results:
                return self._format_vector_results(results, current_chapter_num)
            return ""

        except Exception as e:
            self.logger.warning(f"向量检索失败: {str(e)}")
            return ""

    def _build_vector_query(self, chapter_metadata: Dict[str, Any]) -> str:
        """构建向量检索查询"""
        parts = []

        # 章节摘要
        if chapter_metadata.get("chapter_summary"):
            parts.append(chapter_metadata["chapter_summary"])

        # 伏笔信息
        if chapter_metadata.get("foreshadowing"):
            parts.append(chapter_metadata["foreshadowing"])

        # 章节定位
        if chapter_metadata.get("chapter_role"):
            parts.append(chapter_metadata["chapter_role"])

        return " ".join(parts)

    def _format_vector_results(self, results: List[Dict[str, Any]], current_chapter: int = 1) -> str:
        """格式化向量检索结果（应用时间距离规则）"""
        formatted = []
        for i, result in enumerate(results[:2], 1):
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            ref_chapter = metadata.get("chapter_number", 0)

            # 应用时间距离规则
            if isinstance(ref_chapter, int) and ref_chapter > 0:
                distance = current_chapter - ref_chapter
                if distance <= 2:
                    rule_tag = f"[SKIP] 跳过近{distance}章内容"
                    content_excerpt = content[:300]  # 截短
                elif 3 <= distance <= 5:
                    rule_tag = "[MOD40%] 需修改≥40%"
                    content_excerpt = content[:500]
                else:
                    rule_tag = "[OK] 可引用核心"
                    content_excerpt = content[:500]
                formatted.append(
                    f"[历史参考 {i}] {rule_tag} - 第{ref_chapter}章:\n{content_excerpt}")
            else:
                formatted.append(
                    f"[历史参考 {i}] 第{ref_chapter}章相关内容:\n{content[:500]}")
        return "\n\n".join(formatted)

    async def _get_knowledge_context(
        self,
        project: NovelProject,
        chapter_metadata: Dict[str, Any]
    ) -> str:
        """获取知识库内容（支持项目专属知识库 + 公共知识库）"""
        kb_config = project.knowledge_base_config or {}

        # 构建结果容器
        context_parts = []

        # 1. 检索项目专属知识库（如果已构建）
        if project.kb_status == 'ready':
            try:
                from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
                project_kb = ProjectKnowledgeBase(db=self.db)

                # 获取当前单元号
                unit_number = chapter_metadata.get(
                    'unit_number', chapter_metadata.get('chapter_number', 1))

                # 构建查询文本（使用章节摘要）
                query_text = chapter_metadata.get(
                    'chapter_summary', '') or chapter_metadata.get('chapter_title', '')

                # 检索项目专属知识库
                kb_result = await project_kb.retrieve_for_revision(
                    project_id=project.id,
                    current_unit=unit_number,
                    query_text=query_text,
                    n_results=5
                )

                if kb_result.get('combined_context'):
                    context_parts.append("【项目专属知识库】")
                    context_parts.append(kb_result['combined_context'])
                    self.logger.info(f"项目专属知识库检索成功: project_id={project.id}")
            except Exception as e:
                self.logger.warning(f"项目专属知识库检索失败: {str(e)}")

        # 2. 检索公共知识库（如果配置了）
        if any([
            kb_config.get("kb_vertical_enabled"),
            kb_config.get("kb_user_specific_enabled"),
            kb_config.get("kb_manual_enabled")
        ]):
            try:
                # 使用知识库集成服务
                kb_integration = NovelKnowledgeIntegration(
                    self.db, project.user_id)

                # 构建章节信息
                chapter_info = self._build_chapter_info(chapter_metadata)

                # 验证并规范化配置
                kb_config_validated = kb_integration.validate_kb_config(
                    kb_config)

                # 检索知识库
                kb_result = await kb_integration.retrieve_knowledge_for_chapter(
                    project=project,
                    chapter_info=chapter_info,
                    kb_config=kb_config_validated
                )

                # 格式化知识库内容
                formatted = kb_integration.format_knowledge_for_prompt(
                    kb_result)
                if formatted:
                    context_parts.append("\n【公共知识库参考】")
                    context_parts.append(formatted)

            except Exception as e:
                self.logger.warning(f"公共知识库检索失败: {str(e)}")

        return "\n".join(context_parts) if context_parts else ""

    def _build_chapter_info(self, chapter_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """构建用于知识库检索的章节信息"""
        return {
            "chapter_summary": chapter_metadata.get("chapter_summary", ""),
            "chapter_role": chapter_metadata.get("chapter_role", ""),
            "chapter_purpose": chapter_metadata.get("chapter_purpose", ""),
            "foreshadowing": chapter_metadata.get("foreshadowing", ""),
            "scene_metadata": chapter_metadata.get("scene_metadata", {})
        }

    def _build_knowledge_query(self, chapter_metadata: Dict[str, Any]) -> str:
        """构建知识库检索查询"""
        parts = []

        if chapter_metadata.get("chapter_summary"):
            parts.append(chapter_metadata["chapter_summary"])
        if chapter_metadata.get("chapter_role"):
            parts.append(f"章节类型: {chapter_metadata['chapter_role']}")
        if chapter_metadata.get("chapter_purpose"):
            parts.append(f"叙事目的: {chapter_metadata['chapter_purpose']}")

        return " ".join(parts)

    def _format_knowledge_contexts(self, kb_contexts: Dict[str, str]) -> str:
        """格式化知识库内容"""
        formatted = []

        if kb_contexts.get("theory"):
            formatted.append(f"【理论知识】\n{kb_contexts['theory']}")
        if kb_contexts.get("case"):
            formatted.append(f"【案例参考】\n{kb_contexts['case']}")
        if kb_contexts.get("user_specific"):
            formatted.append(f"【用户知识】\n{kb_contexts['user_specific']}")
        if kb_contexts.get("manual"):
            formatted.append(f"【官方手册】\n{kb_contexts['manual']}")

        return "\n\n".join(formatted)

    async def _get_outline_metadata(self, project: NovelProject) -> str:
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
        project: NovelProject,
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

        Args:
            project: 项目对象
            current_unit: 当前单元号
            content_type: 内容类型
            chapter_metadata: 章节元数据

        Returns:
            摘要字典
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
        project: NovelProject,
        current_unit: int,
        content_type: str,
        max_units: int = 3
    ) -> str:
        """
        获取前三单元的正文摘要

        Args:
            project: 项目对象
            current_unit: 当前单元号
            content_type: 内容类型
            max_units: 最多获取前几个单元

        Returns:
            正文摘要字符串
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
                if content:
                    # 提取摘要（取前500字）
                    summary = content[:500] + \
                        "..." if len(content) > 500 else content
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
        project: NovelProject,
        current_unit: int,
        content_type: str,
        max_summaries: int = 10
    ) -> str:
        """
        获取当前单元之前所有单元的大纲摘要

        Args:
            project: 项目对象
            current_unit: 当前单元号
            content_type: 内容类型
            max_summaries: 最多包含多少个单元的摘要

        Returns:
            大纲摘要字符串
        """
        summaries = []

        try:
            # 根据内容类型获取大纲数据
            if content_type == "novel":
                outlines = project.chapter_outlines or {}
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

                    # 提取摘要信息
                    if content_type == "novel":
                        title = outline.get("chapter_title", f"第{unit_num}章")
                        summary = outline.get("chapter_summary", "") or outline.get(
                            "detailed_outline", "")[:300]
                    elif content_type in ("series_script", "script"):
                        title = outline.get("episode_title", f"第{unit_num}集")
                        summary = outline.get("episode_summary", "") or outline.get(
                            "detailed_outline", "")[:300]
                    else:
                        title = outline.get("scene_title", f"第{unit_num}场")
                        summary = outline.get("scene_summary", "") or outline.get(
                            "detailed_outline", "")[:200]

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
        project: NovelProject,
        current_unit: int,
        content_type: str,
        chapter_metadata: Dict[str, Any]
    ) -> str:
        """
        获取当前单元的大纲摘要（精简版）

        Args:
            project: 项目对象
            current_unit: 当前单元号
            content_type: 内容类型
            chapter_metadata: 章节元数据

        Returns:
            当前单元大纲摘要
        """
        try:
            # 根据内容类型获取大纲数据
            if content_type == "novel":
                outlines = project.chapter_outlines or {}
                unit_key = str(current_unit)
                unit_label = "章"

                if unit_key in outlines:
                    outline = outlines[unit_key]
                    title = outline.get("chapter_title", f"第{current_unit}章")
                    summary = outline.get("chapter_summary", "")
                    detailed = outline.get("detailed_outline", "")
                    key_events = outline.get("key_events", [])

                    result = f"【第{current_unit}{unit_label}《{title}》大纲】\n"
                    if summary:
                        result += f"章节概要：{summary}\n"
                    if key_events:
                        result += f"关键事件：{'；'.join(key_events[:3])}\n"
                    if detailed and not summary:
                        result += f"详细大纲：{detailed[:500]}...\n"

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

    async def _get_outline_content(self, project: NovelProject) -> str:
        """
        获取完整大纲内容（已废弃，保留向后兼容）

        注意：此方法已被 _get_outline_metadata() 替代
        保留此方法是为了向后兼容旧版代码
        """
        self.logger.warning(
            "[已废弃] _get_outline_content 方法已废弃，请使用 _get_outline_metadata")
        return await self._get_outline_metadata(project)

    async def _get_current_unit_outline(
        self,
        project: NovelProject,
        chapter_num: int,
        chapter_metadata: Dict[str, Any]
    ) -> str:
        """获取当前章节/分集/场景对应的大纲片段

        支持两阶段大纲生成机制：
        - 优先使用 unit_summaries（新版两阶段大纲的第二阶段）
        - 回退使用 outline_content（旧版兼容）

        根据内容类型提取相关的大纲部分，让LLM能够精准参考当前单元的情节设定

        格式化处理：
        - 在提取章节之前先对大纲进行格式化
        - 确保章节标题格式统一，便于准确提取
        """
        content_type = getattr(project, 'content_type', 'novel')

        # ==================== 两阶段大纲机制：优先使用 unit_summaries ====================
        unit_summaries = getattr(project, 'unit_summaries', None) or {}
        unit_key = str(chapter_num)

        if unit_key in unit_summaries:
            unit_data = unit_summaries[unit_key]
            summary = unit_data.get('summary', '')
            title = unit_data.get('title', '')

            if summary:
                self.logger.info(
                    f"[两阶段大纲] 使用 unit_summaries: unit={chapter_num}, "
                    f"title={title}, summary_len={len(summary)}")

                # 根据内容类型格式化输出
                if content_type == "novel":
                    unit_label = "章"
                elif content_type in ("series_script", "script"):
                    unit_label = "集"
                else:
                    unit_label = "场"

                result = f"【第{chapter_num}{unit_label}"
                if title:
                    result += f"《{title}》"
                result += f"大纲】\n{summary}\n"
                result += f"【以上是第{chapter_num}{unit_label}的大纲内容，请严格按照此大纲进行创作】"
                return result

        # ==================== 回退：使用旧版 outline_content ====================
        outline = project.outline_content or ""
        if not outline:
            return ""

        # 对大纲内容进行格式化处理
        # 确保章节标题格式统一，便于准确提取
        try:
            unit_formatter = DocumentFormatter(content_type=content_type)
            formatted_outline, stats = unit_formatter.format(outline)
            if stats.titles_normalized > 0 or stats.noise_content_removed > 0:
                self.logger.debug(
                    f"[单元大纲提取] 格式化处理: 标准化{stats.titles_normalized}个标题, "
                    f"移除{stats.noise_content_removed}处干扰内容"
                )
            outline = formatted_outline
        except Exception as e:
            self.logger.warning(f"[单元大纲提取] 格式化处理失败: {e}")

        # 根据内容类型选择不同的提取策略
        if content_type == "novel":
            # 小说：提取当前章节相关的大纲内容
            return self._extract_chapter_outline(outline, chapter_num)
        elif content_type == "series_script":
            # 剧集：提取当前场景所属分集的大纲
            episode_num = chapter_metadata.get('episode_number', 1)
            return self._extract_episode_outline(outline, episode_num)
        elif content_type == "movie_script":
            # 电影：提取当前场景的大纲描述
            return self._extract_scene_outline(outline, chapter_num)
        else:
            # 兼容旧版
            if project.project_type and project.project_type.value == "script":
                episode_num = chapter_metadata.get('episode_number', 1)
                return self._extract_episode_outline(outline, episode_num)
            return self._extract_chapter_outline(outline, chapter_num)

    def _extract_chapter_outline(self, outline: str, chapter_num: int) -> str:
        """从大纲中提取指定章节的内容"""
        import re

        lines = outline.split('\n')
        result_lines = []
        capturing = False
        capture_count = 0

        # 匹配章节标题的正则表达式
        chapter_patterns = [
            rf'^第[{self._chinese_numbers()}\d]+章',
            rf'^Chapter\s*\d+',
            rf'^\d+[、．.\s]',
        ]

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # 检查是否匹配当前章节
            for pattern in chapter_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    # 提取章节号
                    match = re.search(
                        r'第?([一二三四五六七八九十百千万\d]+)章', line_stripped)
                    if match:
                        num_str = match.group(1)
                        num = self._chinese_to_number(
                            num_str) if not num_str.isdigit() else int(num_str)
                        if num == chapter_num:
                            capturing = True
                            result_lines = [line]
                            continue
                        elif capturing:
                            # 已经捕获到下一章，停止
                            capturing = False
                            break
                    elif capturing:
                        capturing = False
                        break

            if capturing:
                result_lines.append(line)
                capture_count += 1
                # 限制捕获长度
                if capture_count > 50:
                    break

        result = '\n'.join(result_lines).strip()

        # 添加格式化包装（参考创意生成模块的成功模式）
        if result:
            return f"【第{chapter_num}章大纲】\n{result}\n【以上是第{chapter_num}章的大纲内容，请严格按照此大纲进行创作】"
        return ""

    def _extract_episode_outline(self, outline: str, episode_num: int) -> str:
        """从大纲中提取指定分集的内容（参考小说章节提取的成功模式）"""
        import re

        lines = outline.split('\n')
        result_lines = []
        capturing = False
        capture_count = 0

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

        # 匹配分集标题的正则表达式（参考小说章节提取的成功模式，按优先级排序）
        episode_patterns = [
            # 1. Markdown标题格式（带 # 前缀）
            rf'^#+\s*第{episode_num}集',
            rf'^#+\s*第{chinese_episode}集',
            # 2. 粗体格式
            rf'^\*\*第{episode_num}集',
            rf'^\*\*第{chinese_episode}集',
            # 3. 括号格式
            rf'^【第{episode_num}集】',
            rf'^【第{chinese_episode}集】',
            # 4. 纯文本格式
            rf'^第{episode_num}集',
            rf'^第{chinese_episode}集',
            rf'^第\s*{episode_num}\s*集',
            # 5. Episode 格式
            rf'^[Ee]pisode\s*{episode_num}',
            rf'^EP\s*{episode_num}',
            rf'^Ep\.?\s*{episode_num}',
            # 6. 通用格式（匹配任意集数）
            rf'^#+\s*第[{self._chinese_numbers()}\d]+集',
            rf'^第[{self._chinese_numbers()}\d]+集',
            rf'^[Ee]pisode\s*\d+',
            rf'^EP\s*\d+',
        ]

        for line in lines:
            line_stripped = line.strip()

            for pattern in episode_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    # 提取集数
                    match = re.search(
                        r'第?([一二三四五六七八九十百千万\d]+)集', line_stripped)
                    if match:
                        num_str = match.group(1)
                        num = self._chinese_to_number(
                            num_str) if not num_str.isdigit() else int(num_str)
                        if num == episode_num:
                            capturing = True
                            result_lines = [line]
                            continue
                        elif capturing:
                            capturing = False
                            break
                    # 检查 Episode 格式
                    ep_match = re.search(
                        r'[Ee]pisode\s*(\d+)|EP\s*(\d+)', line_stripped)
                    if ep_match:
                        num = int(ep_match.group(1) or ep_match.group(2))
                        if num == episode_num:
                            capturing = True
                            result_lines = [line]
                            continue
                        elif capturing:
                            capturing = False
                            break
                    elif capturing:
                        capturing = False
                        break

            if capturing:
                result_lines.append(line)
                capture_count += 1
                if capture_count > 80:  # 分集内容通常更长
                    break

        result = '\n'.join(result_lines).strip()

        # 添加格式化包装（参考创意生成模块的成功模式）
        if result:
            return f"【第{episode_num}集大纲】\n{result}\n【以上是第{episode_num}集的大纲内容，请严格按照此大纲进行创作】"
        return ""

    def _extract_scene_outline(self, outline: str, scene_num: int) -> str:
        """从大纲中提取指定场景的内容（参考小说章节提取的成功模式）"""
        import re

        lines = outline.split('\n')
        result_lines = []
        capturing = False
        capture_count = 0

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

        # 匹配场景标题的正则表达式（参考小说章节提取的成功模式，按优先级排序）
        scene_patterns = [
            # 1. Markdown标题格式（带 # 前缀）
            rf'^#+\s*第{scene_num}场',
            rf'^#+\s*第{chinese_scene}场',
            # 2. 粗体格式
            rf'^\*\*第{scene_num}场',
            rf'^\*\*第{chinese_scene}场',
            # 3. 括号格式
            rf'^【第{scene_num}场】',
            rf'^【第{chinese_scene}场】',
            # 4. 纯文本格式
            rf'^第{scene_num}场',
            rf'^第{chinese_scene}场',
            rf'^第\s*{scene_num}\s*场',
            # 5. Scene 格式
            rf'^[Ss]cene\s*{scene_num}',
            rf'^SCENE\s*{scene_num}',
            # 6. 内景/外景格式（带编号）
            rf'^{scene_num}\.\s*[内外]景',
            rf'^{scene_num}[\.、]\s*[^\d]',
            # 7. INT./EXT. 格式
            rf'^[Ii][Nn][Tt]\.?\s*.*{scene_num}',
            rf'^[Ee][Xx][Tt]\.?\s*.*{scene_num}',
            # 8. 通用格式（匹配任意场景）
            rf'^#+\s*第[{self._chinese_numbers()}\d]+场',
            rf'^第[{self._chinese_numbers()}\d]+场',
            rf'^[Ss]cene\s*\d+',
            rf'^SCENE\s*\d+',
            rf'^[内外]景[·•．.:：]',
        ]

        for line in lines:
            line_stripped = line.strip()

            for pattern in scene_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    # 提取场景号
                    match = re.search(
                        r'第?([一二三四五六七八九十百千万\d]+)场', line_stripped)
                    if match:
                        num_str = match.group(1)
                        num = self._chinese_to_number(
                            num_str) if not num_str.isdigit() else int(num_str)
                        if num == scene_num:
                            capturing = True
                            result_lines = [line]
                            continue
                        elif capturing:
                            capturing = False
                            break
                    # 检查 Scene 格式
                    sc_match = re.search(
                        r'[Ss]cene\s*(\d+)|SCENE\s*(\d+)', line_stripped)
                    if sc_match:
                        num = int(sc_match.group(1) or sc_match.group(2))
                        if num == scene_num:
                            capturing = True
                            result_lines = [line]
                            continue
                        elif capturing:
                            capturing = False
                            break
                    # 检查数字编号格式 (如 "1. 内景" 或 "1、外景")
                    num_match = re.match(r'^(\d+)[\.、]\s*', line_stripped)
                    if num_match:
                        num = int(num_match.group(1))
                        if num == scene_num:
                            capturing = True
                            result_lines = [line]
                            continue
                        elif capturing:
                            capturing = False
                            break
                    # 检查 INT./EXT. 格式中的编号
                    int_ext_match = re.search(
                        r'[Ii][Nn][Tt]\.?\s*.*?(\d+)|[Ee][Xx][Tt]\.?\s*.*?(\d+)', line_stripped)
                    if int_ext_match:
                        num = int(int_ext_match.group(
                            1) or int_ext_match.group(2))
                        if num == scene_num:
                            capturing = True
                            result_lines = [line]
                            continue
                        elif capturing:
                            capturing = False
                            break
                    elif capturing:
                        capturing = False
                        break

            if capturing:
                result_lines.append(line)
                capture_count += 1
                if capture_count > 30:
                    break

        result = '\n'.join(result_lines).strip()

        # 添加格式化包装（参考创意生成模块的成功模式）
        if result:
            return f"【第{scene_num}场大纲】\n{result}\n【以上是第{scene_num}场的大纲内容，请严格按照此大纲进行创作】"
        return ""

    async def _get_episode_outline(self, project: NovelProject, episode_num: int) -> str:
        """
        获取剧集剧本的分集大纲（用于场景生成时参考）

        优先级：
        1. 分集详细大纲（episode_outlines）
        2. 基础大纲中的分集概要（outline_content）
        """
        # 1. 优先从 episode_outlines 获取详细大纲
        episode_outlines = project.episode_outlines or {}
        detailed_outline = episode_outlines.get(str(episode_num), {})

        if detailed_outline and detailed_outline.get("detailed_outline"):
            self.logger.info(
                f"[分集大纲] 使用第{episode_num}集详细大纲（来自episode_outlines）")

            # 格式化场景信息
            scenes_info = ""
            if detailed_outline.get("scenes"):
                scenes_list = detailed_outline["scenes"]
                if scenes_list:
                    scenes_info = "\n\n【场景规划】\n"
                    for scene in scenes_list:
                        scenes_info += f"- {scene.get('scene_number', '')}: {scene.get('location', '')}（{scene.get('interior_exterior', '')}景/{scene.get('time_of_day', '')}）- {scene.get('core_content', '')}\n"

            # 格式化核心信息
            core_info = ""
            if detailed_outline.get("core_conflict"):
                core_info += f"\n**核心冲突**：{detailed_outline['core_conflict']}"
            if detailed_outline.get("emotional_curve"):
                core_info += f"\n**情感曲线**：{detailed_outline['emotional_curve']}"

            return f"""【第{episode_num}集详细大纲】

**集标题**：{detailed_outline.get('episode_title', f'第{episode_num}集')}

**本集梗概**：
{detailed_outline.get('episode_summary', '未提供概要')}
{core_info}

**详细剧情**：
{detailed_outline.get('detailed_outline', '未提供详细大纲')}
{scenes_info}
【以上是第{episode_num}集的详细大纲，请严格按照此大纲进行场景创作】
"""

        # 2. 回退到基础大纲中的分集概要
        outline = self._extract_episode_outline(
            project.outline_content or "", episode_num
        )
        if outline:
            self.logger.info(f"[分集大纲] 使用基础大纲中第{episode_num}集概要（回退方案）")
        else:
            self.logger.warning(f"[分集大纲] 未找到第{episode_num}集的大纲信息")

        return outline

    async def _get_previous_episodes_summary(
        self,
        project: NovelProject,
        current_episode: int,
        max_previous: int = 3
    ) -> str:
        """
        获取前序集数的大纲摘要（用于保证剧情一致性）

        当生成当前分集的场景时，获取前几集的大纲摘要，确保：
        1. 剧情连贯性
        2. 人物状态一致性
        3. 伏笔呼应
        4. 场景过渡自然

        Args:
            project: 项目对象
            current_episode: 当前集数
            max_previous: 最多获取前几集的摘要

        Returns:
            前序集数大纲摘要文本
        """
        summaries = []
        episode_outlines = project.episode_outlines or {}

        # 计算需要获取的集数范围
        start_ep = max(1, current_episode - max_previous)

        for ep in range(start_ep, current_episode):
            ep_outline = episode_outlines.get(str(ep), {})

            # 如果有详细大纲，优先使用
            if ep_outline.get("detailed_outline"):
                title = ep_outline.get("episode_title", f"第{ep}集")
                summary = ep_outline.get("episode_summary", "")
                core_conflict = ep_outline.get("core_conflict", "")
                emotional_curve = ep_outline.get("emotional_curve", "")

                # 构建摘要（控制在合理长度）
                ep_summary = f"""【第{ep}集《{title}》摘要】
剧情概要：{summary[:400]}{'...' if len(summary) > 400 else ''}"""
                if core_conflict:
                    ep_summary += f"\n核心冲突：{core_conflict[:200]}"
                if emotional_curve:
                    ep_summary += f"\n情感曲线：{emotional_curve[:100]}"

                summaries.append(ep_summary)
                self.logger.info(f"[前序大纲] 获取第{ep}集详细大纲摘要成功")

            # 如果没有详细大纲，尝试从基础大纲中提取概要
            elif project.outline_content:
                ep_summary_in_outline = self._extract_episode_outline(
                    project.outline_content, ep
                )
                if ep_summary_in_outline:
                    # 简化格式，只保留核心内容
                    ep_summary_in_outline = ep_summary_in_outline.replace(
                        f"【第{ep}集大纲】\n", f"【第{ep}集概要（来自基础大纲）】\n"
                    ).replace(f"\n【以上是第{ep}集的大纲内容，请严格按照此大纲进行创作】", "")
                    # 截断过长的内容
                    if len(ep_summary_in_outline) > 500:
                        ep_summary_in_outline = ep_summary_in_outline[:500] + "..."
                    summaries.append(ep_summary_in_outline)
                    self.logger.info(f"[前序大纲] 从基础大纲提取第{ep}集概要成功")

        if summaries:
            result = "\n\n".join(summaries)
            self.logger.info(f"[前序大纲] 共获取{len(summaries)}集大纲摘要")
            return result

        self.logger.info("[前序大纲] 无前序集数，这是第一集")
        return "（无前序集数，这是第一集）"

    async def _get_chapter_detailed_outline(
        self,
        project: NovelProject,
        chapter_num: int
    ) -> str:
        """
        获取单章详细大纲（从 chapter_outlines 数据库字段）

        当基础大纲（outline_content）中没有章节概述时，
        使用单章详细大纲作为补充，确保LLM有足够的参考信息生成正文。

        Args:
            project: 项目对象
            chapter_num: 章节号

        Returns:
            格式化的单章详细大纲文本
        """
        chapter_outlines = project.chapter_outlines or {}
        chapter_outline = chapter_outlines.get(str(chapter_num), {})

        if not chapter_outline:
            self.logger.debug(f"[单章详细大纲] 第{chapter_num}章无详细大纲数据")
            return ""

        # 提取详细大纲的各个字段
        chapter_title = chapter_outline.get(
            "chapter_title", f"第{chapter_num}章")
        chapter_summary = chapter_outline.get("chapter_summary", "")
        detailed_outline = chapter_outline.get("detailed_outline", "")
        key_events = chapter_outline.get("key_events", [])
        character_arcs = chapter_outline.get("character_arcs", "")

        # 如果没有详细大纲内容，返回空
        if not detailed_outline and not chapter_summary:
            self.logger.debug(f"[单章详细大纲] 第{chapter_num}章详细大纲内容为空")
            return ""

        self.logger.info(
            f"[单章详细大纲] 使用第{chapter_num}章详细大纲（来自chapter_outlines）"
        )

        # 对详细大纲内容进行格式化处理
        if detailed_outline:
            try:
                formatted_outline, stats = self.formatter.format(
                    detailed_outline)
                if stats.titles_normalized > 0 or stats.noise_content_removed > 0:
                    self.logger.info(
                        f"[单章详细大纲] 格式化处理: 标准化{stats.titles_normalized}个标题, "
                        f"移除{stats.noise_content_removed}处干扰内容"
                    )
                detailed_outline = formatted_outline
            except Exception as e:
                self.logger.warning(f"[单章详细大纲] 格式化处理失败: {e}")

        # 构建格式化的大纲文本
        sections = []

        # 章节标题
        sections.append(f"【第{chapter_num}章《{chapter_title}》详细大纲】")

        # 章节梗概
        if chapter_summary:
            sections.append(f"\n**章节梗概**：\n{chapter_summary}")

        # 详细剧情
        if detailed_outline:
            sections.append(f"\n**详细剧情**：\n{detailed_outline}")

        # 关键事件
        if key_events:
            events_text = "\n".join([f"- {event}" for event in key_events])
            sections.append(f"\n**关键事件**：\n{events_text}")

        # 角色发展
        if character_arcs:
            sections.append(f"\n**角色发展**：\n{character_arcs}")

        # 添加结尾提示
        sections.append(f"\n【以上是第{chapter_num}章的详细大纲，请严格按照此大纲进行正文创作】")

        return "\n".join(sections)

    def _chinese_numbers(self) -> str:
        """返回中文数字字符串"""
        return "一二三四五六七八九十百千万"

    def _chinese_to_number(self, chinese: str) -> int:
        """将中文数字转换为阿拉伯数字"""
        chinese_nums = {
            '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
            '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
            '十': 10, '百': 100, '千': 1000, '万': 10000
        }

        if len(chinese) == 1:
            return chinese_nums.get(chinese, 1)

        result = 0
        temp = 0
        for char in chinese:
            if char in chinese_nums:
                num = chinese_nums[char]
                if num >= 10:
                    if temp == 0:
                        temp = 1
                    result += temp * num
                    temp = 0
                else:
                    temp = num
        result += temp

        return result if result > 0 else 1

    # ==================== 连续剧单集上下文构建（新版） ====================

    async def build_episode_context(
        self,
        project: NovelProject,
        episode_number: int
    ) -> Dict[str, Any]:
        """
        构建连续剧单集正文生成上下文

        专门用于新版单集正文生成，一集对应完整上下文。
        包含与小说章节生成相同的完整机制。

        Args:
            project: 项目对象
            episode_number: 当前集数

        Returns:
            上下文字典
        """
        context = {
            # 基础大纲相关
            "outline_content": "",
            "episode_outline": "",
            "previous_episodes_summary": "",
            # 全局上下文（与小说生成保持一致）
            "global_summary": "",
            "character_states": "",
            "short_summary": "",
            "previous_scene_ending": "",
            "knowledge_context": "",
            "vector_context": ""
        }

        try:
            # 1. 获取前文摘要（全局摘要）
            context["global_summary"] = await self._get_summary(project)

            # 2. 获取角色状态
            context["character_states"] = await self._get_character_state(project)

            # 3. 获取最近集数内容（滑动窗口，适配剧集）
            recent_context = await self._get_recent_episodes(project, episode_number)
            context["previous_scene_ending"] = recent_context.get(
                "endings", "")
            context["short_summary"] = recent_context.get("summary", "")

            # 4. 获取向量检索相关内容
            context["vector_context"] = await self._get_vector_context(
                project, {"episode_number": episode_number}, episode_number
            )

            # 5. 获取知识库内容
            context["knowledge_context"] = await self._get_knowledge_context(
                project, {"episode_number": episode_number}
            )

            # 6. 获取故事大纲
            context["outline_content"] = await self._get_outline_content(project)

            # 7. 获取当前分集详细大纲
            context["episode_outline"] = await self._get_episode_outline(project, episode_number)

            # 8. 获取前序集数大纲摘要
            context["previous_episodes_summary"] = await self._get_previous_episodes_summary(
                project, episode_number
            )

            return context

        except Exception as e:
            self.logger.error(f"构建单集上下文失败: {str(e)}")
            return context

    async def _get_recent_episodes(
        self,
        project: NovelProject,
        current_episode: int
    ) -> Dict[str, str]:
        """
        获取最近N集内容（滑动窗口，剧集专用）

        Args:
            project: 项目对象
            current_episode: 当前集数

        Returns:
            包含结尾内容和摘要的字典
        """
        result = {
            "endings": "",
            "summary": ""
        }

        start = max(1, current_episode - self.recent_chapters_count)
        endings = []

        # 从数据库获取最近集数（通过 episode_number 字段查询）
        from sqlalchemy import select
        query = select(NovelChapter).where(
            NovelChapter.project_id == project.id,
            NovelChapter.episode_number < current_episode,
            NovelChapter.episode_number >= start
        ).order_by(NovelChapter.episode_number)

        episodes_result = await self.db.execute(query)
        episodes = episodes_result.scalars().all()

        for episode in episodes:
            content = episode.final_content or episode.draft_content or ""
            if content:
                # 只取集尾部分（约800字）
                excerpt = content[-800:] if len(content) > 800 else content
                ep_num = episode.episode_number or episode.chapter_number
                endings.append(f"第{ep_num}集结尾：\n{excerpt}")

        result["endings"] = "\n\n".join(endings)

        # 生成简短摘要（如果有多个前集）
        if len(episodes) > 1:
            result["summary"] = self._generate_episodes_summary(episodes)

        return result

    def _generate_episodes_summary(self, episodes: List[NovelChapter]) -> str:
        """生成最近集数的简短摘要"""
        summaries = []
        for episode in episodes[-3:]:  # 最近3集
            metadata = episode.chapter_metadata or {}
            summary = metadata.get(
                "episode_summary", metadata.get("chapter_summary", ""))
            if summary:
                ep_num = episode.episode_number or episode.chapter_number
                summaries.append(f"第{ep_num}集: {summary}")
        return " | ".join(summaries)

    async def _get_recent_scenes(
        self,
        project: NovelProject,
        current_scene: int
    ) -> Dict[str, str]:
        """
        获取最近N场内容（滑动窗口，电影专用）

        Args:
            project: 项目对象
            current_scene: 当前场景号

        Returns:
            包含结尾内容和摘要的字典
        """
        result = {
            "endings": "",
            "summary": ""
        }

        start = max(1, current_scene - self.recent_chapters_count)
        endings = []

        # 从数据库获取最近场景（通过 scene_number 字段查询）
        from sqlalchemy import select
        query = select(NovelChapter).where(
            NovelChapter.project_id == project.id,
            NovelChapter.scene_number < current_scene,
            NovelChapter.scene_number >= start
        ).order_by(NovelChapter.scene_number)

        scenes_result = await self.db.execute(query)
        scenes = scenes_result.scalars().all()

        for scene in scenes:
            content = scene.final_content or scene.draft_content or ""
            if content:
                # 只取场尾部分（约600字，电影场景通常较短）
                excerpt = content[-600:] if len(content) > 600 else content
                sc_num = scene.scene_number or scene.chapter_number
                endings.append(f"第{sc_num}场结尾：\n{excerpt}")

        result["endings"] = "\n\n".join(endings)

        # 生成简短摘要（如果有多个前场）
        if len(scenes) > 1:
            result["summary"] = self._generate_scenes_summary(scenes)

        return result

    def _generate_scenes_summary(self, scenes: List[NovelChapter]) -> str:
        """生成最近场景的简短摘要"""
        summaries = []
        for scene in scenes[-3:]:  # 最近3场
            metadata = scene.chapter_metadata or {}
            summary = metadata.get(
                "scene_summary", metadata.get("chapter_summary", ""))
            if summary:
                sc_num = scene.scene_number or scene.chapter_number
                summaries.append(f"第{sc_num}场: {summary}")
        return " | ".join(summaries)

    async def build_scene_context(
        self,
        project: NovelProject,
        scene_number: int
    ) -> Dict[str, Any]:
        """
        构建电影单场景正文生成上下文

        专门用于电影剧本单场景正文生成，一场对应完整上下文。
        包含与小说章节生成相同的完整机制。

        Args:
            project: 项目对象
            scene_number: 当前场景号

        Returns:
            上下文字典
        """
        context = {
            # 基础大纲相关
            "outline_content": "",
            "scene_outline": "",
            "previous_scenes_summary": "",
            # 全局上下文（与小说生成保持一致）
            "global_summary": "",
            "character_states": "",
            "short_summary": "",
            "previous_scene_ending": "",
            "knowledge_context": "",
            "vector_context": ""
        }

        try:
            # 1. 获取前文摘要（全局摘要）
            context["global_summary"] = await self._get_summary(project)

            # 2. 获取角色状态
            context["character_states"] = await self._get_character_state(project)

            # 3. 获取最近场景内容（滑动窗口，适配电影）
            recent_context = await self._get_recent_scenes(project, scene_number)
            context["previous_scene_ending"] = recent_context.get(
                "endings", "")
            context["short_summary"] = recent_context.get("summary", "")

            # 4. 获取向量检索相关内容
            context["vector_context"] = await self._get_vector_context(
                project, {"scene_number": scene_number}, scene_number
            )

            # 5. 获取知识库内容
            context["knowledge_context"] = await self._get_knowledge_context(
                project, {"scene_number": scene_number}
            )

            # 6. 获取故事大纲
            context["outline_content"] = await self._get_outline_content(project)

            # 7. 获取当前场景详细大纲
            context["scene_outline"] = await self._get_scene_outline(project, scene_number)

            # 8. 获取前序场景大纲摘要
            context["previous_scenes_summary"] = await self._get_previous_scenes_summary(
                project, scene_number
            )

            return context

        except Exception as e:
            self.logger.error(f"构建单场景上下文失败: {str(e)}")
            return context

    async def _get_scene_outline(
        self,
        project: NovelProject,
        scene_number: int
    ) -> str:
        """
        获取指定场景的详细大纲（格式化文本）

        参考 _get_chapter_detailed_outline 的成功模式，
        返回格式化的文本字符串，便于LLM理解和遵循。

        Args:
            project: 项目对象
            scene_number: 场景号

        Returns:
            格式化的场景大纲文本
        """
        try:
            scene_outlines = project.scene_outlines or {}
            scene_outline = scene_outlines.get(str(scene_number), {})

            if not scene_outline:
                self.logger.debug(f"[场景详细大纲] 第{scene_number}场无详细大纲数据")
                return ""

            # 提取场景大纲的各个字段
            scene_title = scene_outline.get("scene_title", f"第{scene_number}场")
            location = scene_outline.get("location", "未指定")
            interior_exterior = scene_outline.get(
                "interior_exterior", scene_outline.get("int_ext", "内"))
            time_of_day = scene_outline.get(
                "time_of_day", scene_outline.get("time", "日"))
            characters_present = scene_outline.get(
                "characters_present", scene_outline.get("main_characters", "未指定"))
            scene_purpose = scene_outline.get(
                "scene_purpose", scene_outline.get("core_content", ""))
            scene_summary = scene_outline.get(
                "scene_summary", scene_outline.get("summary", ""))
            detailed_outline = scene_outline.get("detailed_outline", "")
            key_action = scene_outline.get("key_action", "")
            dialogue_focus = scene_outline.get("dialogue_focus", "")
            estimated_duration = scene_outline.get(
                "estimated_duration") or scene_outline.get("duration_minutes") or 3

            # 如果没有任何大纲内容，返回空
            if not detailed_outline and not scene_summary and not scene_purpose:
                self.logger.debug(f"[场景详细大纲] 第{scene_number}场详细大纲内容为空")
                return ""

            self.logger.info(
                f"[场景详细大纲] 使用第{scene_number}场详细大纲（来自scene_outlines）"
            )

            # 对详细大纲内容进行格式化处理
            if detailed_outline:
                try:
                    # 使用电影剧本类型的格式化器
                    movie_formatter = DocumentFormatter(
                        content_type="movie_script")
                    formatted_outline, stats = movie_formatter.format(
                        detailed_outline)
                    if stats.titles_normalized > 0 or stats.noise_content_removed > 0:
                        self.logger.info(
                            f"[场景详细大纲] 格式化处理: 标准化{stats.titles_normalized}个标题, "
                            f"移除{stats.noise_content_removed}处干扰内容"
                        )
                    detailed_outline = formatted_outline
                except Exception as e:
                    self.logger.warning(f"[场景详细大纲] 格式化处理失败: {e}")

            # 构建格式化的大纲文本（参考小说章节的成功模式）
            sections = []

            # 场景标题
            sections.append(f"【第{scene_number}场《{scene_title}》详细大纲】")

            # 场景基本信息
            sections.append(f"\n**场景信息**：")
            sections.append(f"- 地点：{location}（{interior_exterior}景）")
            sections.append(f"- 时间：{time_of_day}")
            sections.append(f"- 在场角色：{characters_present}")
            sections.append(f"- 预计时长：{estimated_duration}分钟")

            # 场景目的/核心内容
            if scene_purpose:
                sections.append(f"\n**本场任务**：\n{scene_purpose}")

            # 场景概要
            if scene_summary:
                sections.append(f"\n**场景概要**：\n{scene_summary}")

            # 详细剧情
            if detailed_outline:
                sections.append(f"\n**详细剧情**：\n{detailed_outline}")

            # 关键动作
            if key_action:
                sections.append(f"\n**关键动作**：{key_action}")

            # 对话重点
            if dialogue_focus:
                sections.append(f"\n**对话重点**：{dialogue_focus}")

            # 添加结尾提示
            sections.append(f"\n【以上是第{scene_number}场的详细大纲，请严格按照此大纲进行剧本创作】")

            return "\n".join(sections)

        except Exception as e:
            self.logger.error(f"获取场景大纲失败: {str(e)}")
            return ""

    async def _get_previous_scenes_summary(
        self,
        project: NovelProject,
        scene_number: int,
        max_scenes: int = 5
    ) -> str:
        """
        获取前序场景的大纲摘要

        Args:
            project: 项目对象
            scene_number: 当前场景号
            max_scenes: 最多包含的前序场景数

        Returns:
            前序场景摘要字符串
        """
        try:
            scene_outlines = project.scene_outlines or {}
            summaries = []

            # 获取前 max_scenes 个场景的摘要
            for sn in range(max(1, scene_number - max_scenes), scene_number):
                outline = scene_outlines.get(str(sn), {})
                if outline:
                    title = outline.get('scene_title', f'第{sn}场')
                    summary = outline.get(
                        'scene_summary', outline.get('summary', ''))
                    if summary:
                        summaries.append(f"【{title}】{summary[:200]}")

            return "\n".join(summaries) if summaries else ""
        except Exception as e:
            self.logger.error(f"获取前序场景摘要失败: {str(e)}")
            return ""
