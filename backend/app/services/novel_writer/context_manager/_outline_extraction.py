"""
上下文窗口管理器 - 大纲提取与剧本/电影上下文Mixin

提供大纲片段提取、连续剧/电影上下文构建功能。

@date: 2026-04-24
@version: v3.1.0 (从context_manager.py拆分)
"""
import re
import asyncio
from typing import Dict, Any, List

from app.models import NovelChapter
from app.services.proofread.document_formatter import DocumentFormatter


class OutlineExtractionMixin:
    """大纲提取与剧本/电影上下文Mixin"""

    async def _get_current_unit_outline(
        self,
        project,
        chapter_num: int,
        chapter_metadata: Dict[str, Any]
    ) -> str:
        """获取当前章节/分集/场景对应的大纲片段

        支持两阶段大纲生成机制：
        - 优先使用 unit_summaries（新版两阶段大纲的第二阶段）
        - 回退使用 outline_content（旧版兼容）
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
            return self._extract_chapter_outline(outline, chapter_num)
        elif content_type == "series_script":
            episode_num = chapter_metadata.get('episode_number', 1)
            return self._extract_episode_outline(outline, episode_num)
        elif content_type == "movie_script":
            return self._extract_scene_outline(outline, chapter_num)
        else:
            if project.project_type and project.project_type.value == "script":
                episode_num = chapter_metadata.get('episode_number', 1)
                return self._extract_episode_outline(outline, episode_num)
            return self._extract_chapter_outline(outline, chapter_num)

    def _extract_chapter_outline(self, outline: str, chapter_num: int) -> str:
        """从大纲中提取指定章节的内容"""
        lines = outline.split('\n')
        result_lines = []
        capturing = False
        capture_count = 0

        chapter_patterns = [
            rf'^第[{self._chinese_numbers()}\d]+章',
            rf'^Chapter\s*\d+',
            rf'^\d+[、．.\s]',
        ]

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            for pattern in chapter_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
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
                            capturing = False
                            break
                    elif capturing:
                        capturing = False
                        break

            if capturing:
                result_lines.append(line)
                capture_count += 1
                if capture_count > 50:
                    break

        result = '\n'.join(result_lines).strip()

        if result:
            return f"【第{chapter_num}章大纲】\n{result}\n【以上是第{chapter_num}章的大纲内容，请严格按照此大纲进行创作】"
        return ""

    def _extract_episode_outline(self, outline: str, episode_num: int) -> str:
        """从大纲中提取指定分集的内容"""
        lines = outline.split('\n')
        result_lines = []
        capturing = False
        capture_count = 0

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

        episode_patterns = [
            rf'^#+\s*第{episode_num}集',
            rf'^#+\s*第{chinese_episode}集',
            rf'^\*\*第{episode_num}集',
            rf'^\*\*第{chinese_episode}集',
            rf'^【第{episode_num}集】',
            rf'^【第{chinese_episode}集】',
            rf'^第{episode_num}集',
            rf'^第{chinese_episode}集',
            rf'^第\s*{episode_num}\s*集',
            rf'^[Ee]pisode\s*{episode_num}',
            rf'^EP\s*{episode_num}',
            rf'^Ep\.?\s*{episode_num}',
            rf'^#+\s*第[{self._chinese_numbers()}\d]+集',
            rf'^第[{self._chinese_numbers()}\d]+集',
            rf'^[Ee]pisode\s*\d+',
            rf'^EP\s*\d+',
        ]

        for line in lines:
            line_stripped = line.strip()

            for pattern in episode_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
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
                if capture_count > 80:
                    break

        result = '\n'.join(result_lines).strip()

        if result:
            return f"【第{episode_num}集大纲】\n{result}\n【以上是第{episode_num}集的大纲内容，请严格按照此大纲进行创作】"
        return ""

    def _extract_scene_outline(self, outline: str, scene_num: int) -> str:
        """从大纲中提取指定场景的内容"""
        lines = outline.split('\n')
        result_lines = []
        capturing = False
        capture_count = 0

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

        scene_patterns = [
            rf'^#+\s*第{scene_num}场',
            rf'^#+\s*第{chinese_scene}场',
            rf'^\*\*第{scene_num}场',
            rf'^\*\*第{chinese_scene}场',
            rf'^【第{scene_num}场】',
            rf'^【第{chinese_scene}场】',
            rf'^第{scene_num}场',
            rf'^第{chinese_scene}场',
            rf'^第\s*{scene_num}\s*场',
            rf'^[Ss]cene\s*{scene_num}',
            rf'^SCENE\s*{scene_num}',
            rf'^{scene_num}\.\s*[内外]景',
            rf'^{scene_num}[\.、]\s*[^\d]',
            rf'^[Ii][Nn][Tt]\.?\s*.*{scene_num}',
            rf'^[Ee][Xx][Tt]\.?\s*.*{scene_num}',
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

        if result:
            return f"【第{scene_num}场大纲】\n{result}\n【以上是第{scene_num}场的大纲内容，请严格按照此大纲进行创作】"
        return ""

    async def _get_episode_outline(self, project, episode_num: int) -> str:
        """获取剧集剧本的分集大纲（用于场景生成时参考）"""
        # 1. 优先从 episode_outlines 获取详细大纲
        episode_outlines = project.episode_outlines or {}
        detailed_outline = episode_outlines.get(str(episode_num), {})

        if detailed_outline and detailed_outline.get("detailed_outline"):
            self.logger.info(
                f"[分集大纲] 使用第{episode_num}集详细大纲（来自episode_outlines）")

            scenes_info = ""
            if detailed_outline.get("scenes"):
                scenes_list = detailed_outline["scenes"]
                if scenes_list:
                    scenes_info = "\n\n【场景规划】\n"
                    for scene in scenes_list:
                        scenes_info += f"- {scene.get('scene_number', '')}: {scene.get('location', '')}（{scene.get('interior_exterior', '')}景/{scene.get('time_of_day', '')}）- {scene.get('core_content', '')}\n"

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
        project,
        current_episode: int,
        max_previous: int = 3
    ) -> str:
        """获取前序集数的大纲摘要（用于保证剧情一致性）"""
        summaries = []
        episode_outlines = project.episode_outlines or {}

        start_ep = max(1, current_episode - max_previous)

        for ep in range(start_ep, current_episode):
            ep_outline = episode_outlines.get(str(ep), {})

            if ep_outline.get("detailed_outline"):
                title = ep_outline.get("episode_title", f"第{ep}集")
                summary = ep_outline.get("episode_summary", "")
                core_conflict = ep_outline.get("core_conflict", "")
                emotional_curve = ep_outline.get("emotional_curve", "")

                ep_summary = f"""【第{ep}集《{title}》摘要】
剧情概要：{summary[:400]}{'...' if len(summary) > 400 else ''}"""
                if core_conflict:
                    ep_summary += f"\n核心冲突：{core_conflict[:200]}"
                if emotional_curve:
                    ep_summary += f"\n情感曲线：{emotional_curve[:100]}"

                summaries.append(ep_summary)
                self.logger.info(f"[前序大纲] 获取第{ep}集详细大纲摘要成功")

            elif project.outline_content:
                ep_summary_in_outline = self._extract_episode_outline(
                    project.outline_content, ep
                )
                if ep_summary_in_outline:
                    ep_summary_in_outline = ep_summary_in_outline.replace(
                        f"【第{ep}集大纲】\n", f"【第{ep}集概要（来自基础大纲）】\n"
                    ).replace(f"\n【以上是第{ep}集的大纲内容，请严格按照此大纲进行创作】", "")
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

    # ==================== 连续剧单集上下文构建 ====================

    async def build_episode_context(
        self,
        project,
        episode_number: int
    ) -> Dict[str, Any]:
        """构建连续剧单集正文生成上下文"""
        context = {
            "outline_content": "",
            "outline_metadata": "",
            "episode_outline": "",
            "previous_episodes_summary": "",
            "previous_content_summaries": "",
            "global_summary": "",
            "character_states": "",
            "short_summary": "",
            "previous_scene_ending": "",
            "knowledge_context": "",
            "vector_context": "",
            "current_unit_outline": "",
            "unit_outline_summary": ""
        }

        try:
            episode_metadata = {"episode_number": episode_number}
            results = await asyncio.gather(
                self._get_summary(project),
                self._get_character_state(project),
                self._get_recent_episodes(project, episode_number),
                self._get_vector_context(project, episode_metadata, episode_number),
                self._get_knowledge_context(project, episode_metadata),
                self._get_outline_metadata(project),
                return_exceptions=True
            )

            context["global_summary"] = results[0] if not isinstance(results[0], Exception) else ""
            context["character_states"] = results[1] if not isinstance(results[1], Exception) else ""
            recent_context = results[2] if not isinstance(results[2], Exception) else {"endings": "", "summary": ""}
            context["previous_scene_ending"] = recent_context.get("endings", "")
            context["short_summary"] = recent_context.get("summary", "")
            context["vector_context"] = results[3] if not isinstance(results[3], Exception) else ""
            context["knowledge_context"] = results[4] if not isinstance(results[4], Exception) else ""
            outline_meta = results[5] if not isinstance(results[5], Exception) else ""
            context["outline_metadata"] = outline_meta
            context["outline_content"] = outline_meta

            ep_names = ["前文摘要", "角色状态", "近集内容", "向量检索", "知识库", "大纲元信息"]
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.warning(
                        f"并行获取{ep_names[i] if i < len(ep_names) else '未知'}失败: {result}"
                    )

            context["episode_outline"] = await self._get_episode_outline(project, episode_number)
            context["previous_episodes_summary"] = await self._get_previous_episodes_summary(project, episode_number)
            context["previous_content_summaries"] = await self._get_previous_content_summaries(project, episode_number, "series_script")
            context["current_unit_outline"] = await self._get_current_unit_outline(project, episode_number, episode_metadata)
            context["unit_outline_summary"] = await self._get_current_unit_outline_summary(project, episode_number, "series_script", episode_metadata)

            context = await self._compress_context(context)

            return context

        except Exception as e:
            self.logger.error(f"构建单集上下文失败: {str(e)}")
            return context

    async def _get_recent_episodes(
        self,
        project,
        current_episode: int
    ) -> Dict[str, str]:
        """获取最近N集内容（滑动窗口，剧集专用）"""
        result = {"endings": "", "summary": ""}

        start = max(1, current_episode - self.recent_chapters_count)
        endings = []

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
                excerpt = content[-800:] if len(content) > 800 else content
                ep_num = episode.episode_number or episode.chapter_number
                endings.append(f"第{ep_num}集结尾：\n{excerpt}")

        result["endings"] = "\n\n".join(endings)

        if len(episodes) > 1:
            result["summary"] = self._generate_episodes_summary(episodes)

        return result

    def _generate_episodes_summary(self, episodes: List[NovelChapter]) -> str:
        """生成最近集数的简短摘要"""
        summaries = []
        for episode in episodes[-3:]:
            metadata = episode.chapter_metadata or {}
            summary = metadata.get("episode_summary", metadata.get("chapter_summary", ""))
            if summary:
                ep_num = episode.episode_number or episode.chapter_number
                summaries.append(f"第{ep_num}集: {summary}")
        return " | ".join(summaries)

    async def _get_recent_scenes(
        self,
        project,
        current_scene: int
    ) -> Dict[str, str]:
        """获取最近N场内容（滑动窗口，电影专用）"""
        result = {"endings": "", "summary": ""}

        start = max(1, current_scene - self.recent_chapters_count)
        endings = []

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
                excerpt = content[-600:] if len(content) > 600 else content
                sc_num = scene.scene_number or scene.chapter_number
                endings.append(f"第{sc_num}场结尾：\n{excerpt}")

        result["endings"] = "\n\n".join(endings)

        if len(scenes) > 1:
            result["summary"] = self._generate_scenes_summary(scenes)

        return result

    def _generate_scenes_summary(self, scenes: List[NovelChapter]) -> str:
        """生成最近场景的简短摘要"""
        summaries = []
        for scene in scenes[-3:]:
            metadata = scene.chapter_metadata or {}
            summary = metadata.get("scene_summary", metadata.get("chapter_summary", ""))
            if summary:
                sc_num = scene.scene_number or scene.chapter_number
                summaries.append(f"第{sc_num}场: {summary}")
        return " | ".join(summaries)

    # ==================== 电影单场景上下文构建 ====================

    async def build_scene_context(
        self,
        project,
        scene_number: int
    ) -> Dict[str, Any]:
        """构建电影单场景正文生成上下文"""
        movie_config = project.movie_script_config or {}
        script_mode = movie_config.get("script_mode", "real")

        context = {
            "outline_content": "",
            "scene_outline": "",
            "previous_scenes_summary": "",
            "global_summary": "",
            "character_states": "",
            "short_summary": "",
            "previous_scene_ending": "",
            "knowledge_context": "",
            "vector_context": "",
            "current_unit_outline": "",
            "unit_outline_summary": "",
            "script_mode": script_mode,
            "feasibility_check_enabled": script_mode == "real"
        }

        try:
            scene_metadata = {"scene_number": scene_number}
            results = await asyncio.gather(
                self._get_summary(project),
                self._get_character_state(project),
                self._get_recent_scenes(project, scene_number),
                self._get_vector_context(project, scene_metadata, scene_number),
                self._get_knowledge_context(project, scene_metadata),
                self._get_outline_content(project),
                return_exceptions=True
            )

            context["global_summary"] = results[0] if not isinstance(results[0], Exception) else ""
            context["character_states"] = results[1] if not isinstance(results[1], Exception) else ""
            recent_context = results[2] if not isinstance(results[2], Exception) else {"endings": "", "summary": ""}
            context["previous_scene_ending"] = recent_context.get("endings", "")
            context["short_summary"] = recent_context.get("summary", "")
            context["vector_context"] = results[3] if not isinstance(results[3], Exception) else ""
            context["knowledge_context"] = results[4] if not isinstance(results[4], Exception) else ""
            context["outline_content"] = results[5] if not isinstance(results[5], Exception) else ""

            sc_names = ["前文摘要", "角色状态", "近场景内容", "向量检索", "知识库", "故事大纲"]
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.warning(
                        f"并行获取{sc_names[i] if i < len(sc_names) else '未知'}失败: {result}"
                    )

            context["scene_outline"] = await self._get_scene_outline(project, scene_number)
            context["previous_scenes_summary"] = await self._get_previous_scenes_summary(project, scene_number)
            context["current_unit_outline"] = await self._get_current_unit_outline(project, scene_number, scene_metadata)
            context["unit_outline_summary"] = await self._get_current_unit_outline_summary(project, scene_number, "movie_script", scene_metadata)

            context = await self._compress_context(context)

            return context

        except Exception as e:
            self.logger.error(f"构建单场景上下文失败: {str(e)}")
            return context

    async def _get_scene_outline(
        self,
        project,
        scene_number: int
    ) -> str:
        """获取指定场景的详细大纲（格式化文本）"""
        try:
            scene_outlines = project.scene_outlines or {}
            scene_outline = scene_outlines.get(str(scene_number), {})

            if not scene_outline:
                self.logger.debug(f"[场景详细大纲] 第{scene_number}场无详细大纲数据")
                return ""

            scene_title = scene_outline.get("scene_title", f"第{scene_number}场")
            location = scene_outline.get("location", "未指定")
            interior_exterior = scene_outline.get("interior_exterior", scene_outline.get("int_ext", "内"))
            time_of_day = scene_outline.get("time_of_day", scene_outline.get("time", "日"))
            characters_present = scene_outline.get("characters_present", scene_outline.get("main_characters", "未指定"))
            scene_purpose = scene_outline.get("scene_purpose", scene_outline.get("core_content", ""))
            scene_summary = scene_outline.get("scene_summary", scene_outline.get("summary", ""))
            detailed_outline = scene_outline.get("detailed_outline", "")
            key_action = scene_outline.get("key_action", "")
            dialogue_focus = scene_outline.get("dialogue_focus", "")
            estimated_duration = scene_outline.get("estimated_duration") or scene_outline.get("duration_minutes") or 3

            if not detailed_outline and not scene_summary and not scene_purpose:
                self.logger.debug(f"[场景详细大纲] 第{scene_number}场详细大纲内容为空")
                return ""

            self.logger.info(f"[场景详细大纲] 使用第{scene_number}场详细大纲（来自scene_outlines）")

            if detailed_outline:
                try:
                    movie_formatter = DocumentFormatter(content_type="movie_script")
                    formatted_outline, stats = movie_formatter.format(detailed_outline)
                    if stats.titles_normalized > 0 or stats.noise_content_removed > 0:
                        self.logger.info(
                            f"[场景详细大纲] 格式化处理: 标准化{stats.titles_normalized}个标题, "
                            f"移除{stats.noise_content_removed}处干扰内容"
                        )
                    detailed_outline = formatted_outline
                except Exception as e:
                    self.logger.warning(f"[场景详细大纲] 格式化处理失败: {e}")

            sections = []
            sections.append(f"【第{scene_number}场《{scene_title}》详细大纲】")
            sections.append(f"\n**场景信息**：")
            sections.append(f"- 地点：{location}（{interior_exterior}景）")
            sections.append(f"- 时间：{time_of_day}")
            sections.append(f"- 在场角色：{characters_present}")
            sections.append(f"- 预计时长：{estimated_duration}分钟")

            if scene_purpose:
                sections.append(f"\n**本场任务**：\n{scene_purpose}")
            if scene_summary:
                sections.append(f"\n**场景概要**：\n{scene_summary}")
            if detailed_outline:
                sections.append(f"\n**详细剧情**：\n{detailed_outline}")
            if key_action:
                sections.append(f"\n**关键动作**：{key_action}")
            if dialogue_focus:
                sections.append(f"\n**对话重点**：{dialogue_focus}")

            sections.append(f"\n【以上是第{scene_number}场的详细大纲，请严格按照此大纲进行剧本创作】")

            return "\n".join(sections)

        except Exception as e:
            self.logger.error(f"获取场景大纲失败: {str(e)}")
            return ""

    async def _get_previous_scenes_summary(
        self,
        project,
        scene_number: int,
        max_scenes: int = 5
    ) -> str:
        """获取前序场景的大纲摘要"""
        try:
            scene_outlines = project.scene_outlines or {}
            summaries = []

            for sn in range(max(1, scene_number - max_scenes), scene_number):
                outline = scene_outlines.get(str(sn), {})
                if outline:
                    title = outline.get('scene_title', f'第{sn}场')
                    summary = outline.get('scene_summary', outline.get('summary', ''))
                    if summary:
                        summaries.append(f"【{title}】{summary[:200]}")

            return "\n".join(summaries) if summaries else ""
        except Exception as e:
            self.logger.error(f"获取前序场景摘要失败: {str(e)}")
            return ""
