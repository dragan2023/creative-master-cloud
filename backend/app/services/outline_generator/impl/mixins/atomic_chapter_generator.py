"""大纲生成器 - 原子化逐章生成器Mixin

核心创新：将一次性全量生成改为逐章迭代生成，每章生成后程序化验证并锁定。

设计原则：
- 原子化：每章独立生成，不受其他章节干扰
- 正向约束：告诉LLM"本章应该写什么"而非"不要写什么"
- 滚动上下文：提供前5章摘要+上一章结尾+下一章边界，保持叙事连贯
- 程序化锁定：每章验证通过后锁定为不可变上下文
- 失败重试：边界验证失败时自动重试（最多2次）
"""
from __future__ import annotations

import asyncio
from typing import Dict, Optional, Any
from datetime import datetime

from app.services.outline_generator.impl.mixins.chapter_boundary import (
    ChapterBoundaryMixin, ValidationResult
)


class AtomicChapterGeneratorMixin:
    """原子化逐章生成器（非流式）"""

    # ==================== 配置常量 ====================
    MAX_BOUNDARY_RETRIES = 2
    LOCKED_CONTEXT_WINDOW = 5
    BOUNDARY_VIOLATION_TEMPERATURE_DELTA = 0.1
    LLM_429_MAX_RETRIES = 3
    LLM_429_BASE_DELAY = 5

    async def generate_all_chapters_atomic(
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
        # GraphRAG知识库增强（v4.1新增）
        project_id: int = None,
    ) -> Dict[str, Any]:
        """逐章生成全部单元概述（原子化模式 v4.0）

        流程：程序化提取边界 -> 章节大纲隔离 -> 逐章LLM生成
            -> 关键词预筛 -> LLM语义验证 -> 锁定 -> 合并返回
        """
        start_time = datetime.now()
        result = {
            "success": False, "content": None, "parsed": None,
            "boundary_report": {}, "duration_ms": 0,
            "chapters_generated": 0, "boundary_violations": 0, "error": None,
        }

        boundary_mixin: ChapterBoundaryMixin = self  # type: ignore

        try:
            unit_label_key = {"novel": "章", "series_script": "集",
                              "movie_script": "场", "movie_outline": "场",
                              "series_outline": "集"}
            unit_label = unit_label_key.get(content_type, "章")

            # 步骤1：程序化提取所有章节边界
            self.logger.info(f"[原子化生成] 提取{unit_count}个章节边界...")
            boundary_map = boundary_mixin.extract_chapter_boundaries(
                global_outline, unit_count, unit_label)
            self.logger.info(
                f"[原子化生成] 边界覆盖{len(boundary_map)}/{unit_count}章")

            # 步骤2：初始化锁定上下文
            locked_chapters: Dict[str, Dict[str, Any]] = {}
            if existing_parsed:
                locked_chapters = dict(existing_parsed)
                self.logger.info(
                    f"[原子化生成] 续生成模式，已有{len(locked_chapters)}章锁定")

            boundary_violations = 0

            # 步骤3：逐章生成
            for chapter_num in range(start_from_unit, unit_count + 1):
                self.logger.info(
                    f"[原子化生成] 第{chapter_num}/{unit_count}{unit_label}...")

                prompt = await self._build_atomic_chapter_prompt(
                    chapter_num=chapter_num, boundary_map=boundary_map,
                    locked_chapters=locked_chapters,
                    global_outline=global_outline, content_type=content_type,
                    unit_label=unit_label, unit_count=unit_count,
                    series_type=series_type,
                    episode_duration_range=episode_duration_range,
                    title_style=title_style, title_style_name=title_style_name,
                    project_id=project_id,
                )

                chapter_data = None
                current_temp = temperature

                for retry in range(self.MAX_BOUNDARY_RETRIES + 1):
                    if retry > 0:
                        self.logger.warning(
                            f"[原子化生成] 第{chapter_num}{unit_label}"
                            f"边界违规，第{retry}次重试...")
                        current_temp = max(
                            0.1, temperature -
                            retry * self.BOUNDARY_VIOLATION_TEMPERATURE_DELTA)

                    llm_response = await self._call_llm_with_429_retry(
                        llm_provider=llm_provider,
                        prompt=prompt if retry == 0 else
                        self._add_boundary_retry_instruction(
                            prompt, chapter_num, unit_label),
                        temperature=current_temp,
                        context=f"第{chapter_num}{unit_label}"
                    )

                    chapter_content = (
                        llm_response.content if hasattr(
                            llm_response, 'content')
                        else str(llm_response))

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
                            "created_at": datetime.now().isoformat(),
                        }
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

                if chapter_data:
                    chapter_data["is_atomic_locked"] = True
                    locked_chapters[chapter_key] = chapter_data
                else:
                    locked_chapters[chapter_key] = {
                        "unit_id": f"unit-{chapter_num}-error",
                        "unit_number": chapter_num,
                        "title": f"第{chapter_num}{unit_label}",
                        "summary": "", "full_content": "",
                        "status": "error",
                        "created_at": datetime.now().isoformat(),
                    }

            # 步骤4：构建最终内容
            final_content = self._build_revised_content(
                locked_chapters, content_type)

            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            result["success"] = True
            result["content"] = final_content
            result["parsed"] = locked_chapters
            result["boundary_report"] = {
                "total_chapters": unit_count,
                "chapters_with_boundaries": len(boundary_map),
                "boundary_violations_detected": boundary_violations,
            }
            result["duration_ms"] = duration_ms
            result["chapters_generated"] = unit_count - start_from_unit + 1
            result["boundary_violations"] = boundary_violations

            self.logger.info(
                f"[原子化生成] 完成！{result['chapters_generated']}章，"
                f"边界违规{boundary_violations}次，{duration_ms}ms")

        except Exception as e:
            self.logger.error(f"[原子化生成] 失败: {e!r}", exc_info=True)
            result["error"] = str(e)

        return result

    # ==================== 提示词构建 ====================

    async def _build_atomic_chapter_prompt(
        self,
        chapter_num: int,
        boundary_map: Dict[int, str],
        locked_chapters: Dict[str, Dict[str, Any]],
        global_outline: str,
        content_type: str,
        unit_label: str,
        unit_count: int,
        series_type: str = None,
        episode_duration_range: str = None,
        title_style: str = None,
        title_style_name: str = None,
        # v5.0废弃：保留签名向后兼容，不再用于GraphRAG检索
        project_id: int = None,
    ) -> str:
        """构建单章专属提示词（v5.0 直接传入完整全局大纲）

        核心原则：
        - 正向约束：只告诉LLM本章应该写什么，完全不说不要写什么
        - 内容隔离：仅提供当前章节的大纲段落，不暴露其他章节内容
        - 最小上下文：只提供必要信息（本章边界+前文摘要+上一章结尾）
        - 完整大纲：直接传入完整的全局大纲内容，确保AI获取全部角色设定、时间线和情节安排

        注意：project_id 参数已废弃（v5.0），不再用于GraphRAG检索，仅保留签名向后兼容。
        """
        boundary_mixin: ChapterBoundaryMixin = self  # type: ignore

        # 构建本章边界上下文
        boundary_context = boundary_mixin.build_boundary_context_for_chapter(
            chapter_num=chapter_num, boundary_map=boundary_map,
            unit_label=unit_label, include_neighbors=True)

        # 构建锁定摘要（前5章摘要）
        locked_context = self._build_locked_summary(
            locked_chapters, chapter_num, unit_label, unit_count)

        # 获取上一章结尾
        last_ending = self._get_last_chapter_ending(
            locked_chapters, chapter_num, unit_label)

        # ===== 内容隔离：仅提取当前章节的大纲段落 =====
        chapter_outline_segment = self._extract_chapter_outline_segment(
            global_outline, chapter_num, content_type, unit_label)

        if not chapter_outline_segment:
            # 回退：无法精确提取时，使用边界描述作为本章大纲
            own_boundary = boundary_map.get(chapter_num, "")
            chapter_outline_segment = (
                f"第{chapter_num}{unit_label}的核心内容：{own_boundary}"
                if own_boundary else
                f"（参考全局大纲中第{chapter_num}{unit_label}的内容）"
            )
            self.logger.info(
                f"[原子化提示词] 第{chapter_num}{unit_label}无法精确提取大纲段落，"
                f"使用边界描述回退")

        # ===== v5.0：直接传入完整全局大纲，不再使用GraphRAG检索 =====
        # GraphRAG检索会丢失角色年龄、关系、时间线等细粒度信息，
        # 导致AI在生成时出现人物关系混淆（张冠李戴）。
        # 改为始终传入完整global_outline，确保AI获取全部设定。
        global_reference = global_outline

        # 标题风格指导
        title_guidance = ""
        if content_type == "novel" and title_style:
            from app.agents.writing.prompts.title_style_guidance import (
                get_title_style_guidance)
            title_guidance = get_title_style_guidance(
                title_style, title_style_name or "")

        return f"""# 任务：创作第{chapter_num}{unit_label}的详细单元概述

# 全局大纲参考
{global_reference}

# 本章专属大纲（仅本章内容，严格据此创作）
{chapter_outline_segment}

# 本章边界说明
{boundary_context}

# 前文摘要（已生成完毕，仅供参考衔接）
{locked_context}

# 上一章结尾衔接点
{last_ending}

# 本章创作指引
1. 本章应专注于上述「本章专属大纲」和「本章边界说明」中描述的内容
2. 从上一章结尾状态自然过渡，保持叙事连贯
3. 在内容范围内尽情发挥创造力，细化场景描写、对话设计和情感渲染
4. 结尾自然为下一章做好铺垫和过渡
5. 在完成梗概后，列出本章专属的核心事件清单，便于后续质量核查
6. ⚠️ 请严格核对全局大纲中的角色姓名、地点名称等关键信息，确保完全一致
{title_guidance}

# 输出格式
请按以下格式输出第{chapter_num}{unit_label}的完整概述：

### 第{chapter_num}{unit_label}：[标题]

**本章梗概**：[200-500字的本章情节概要]

- **情节要点**：
  1. [情节要点1]
  2. [情节要点2]
  ...（列出3-5个关键情节节点）

- **人物状态标注**：
  - [角色名]：[本章的状态变化/情感发展]

- **核心冲突**：[本章的核心矛盾或冲突]

- **关键转折**：[本章的关键情节点或转折]

- **【本章专属事件清单】**：
  1. [本章发生的核心事件1]
  2. [本章发生的核心事件2]
  ...（列出本章覆盖的所有关键事件，用于后续边界验证）

请确保输出格式完整且可被程序解析。
"""

    def _format_graphrag_context(
        self,
        retrieval_result: dict,
        chapter_num: int,
        unit_label: str,
    ) -> str:
        """将GraphRAG检索结果格式化为提示词段落（v4.1新增）

        纯格式化方法，无副作用。从 _build_graphrag_enhanced_outline_context
        中提取以控制主方法长度不超过50行。
        """
        combined = retrieval_result.get("combined_context", "")
        entity_count = len(retrieval_result.get("entities", []))
        relation_count = len(retrieval_result.get("relations", []))

        self.logger.info(
            f"[GraphRAG] 第{chapter_num}{unit_label}："
            f"检索到{entity_count}个实体、{relation_count}个关系，"
            f"上下文长度={len(combined)}字符")

        return f"""【知识图谱约束 - 必须遵守】
以下是从全局知识图谱中检索到的核心设定，请严格遵守：

{combined}

⚠️ 上述内容来自已建立的知识图谱，是故事的基石设定，不得随意更改或违背。
（检索到{entity_count}个实体、{relation_count}个关系）"""

    # [v5.0 已废弃] 内部直接返回空字符串，不再检索知识图谱。
    # 保留方法签名仅向后兼容。
    async def _build_graphrag_enhanced_outline_context(
        self,
        chapter_num: int,
        unit_label: str,
        boundary_map: Dict[int, str],
        locked_chapters: Dict[str, Dict[str, Any]],
        global_outline: str,
        project_id: int = None,
    ) -> str:
        """[v5.0 已废弃] 直接返回空字符串。"""
        return ""

    def _build_graphrag_query(
        self,
        chapter_num: int,
        unit_label: str,
        boundary_map: Dict[int, str],
        locked_chapters: Dict[str, Dict[str, Any]],
    ) -> str:
        """构建GraphRAG检索查询：章节边界+前文摘要（v4.1）"""
        boundary_text = boundary_map.get(chapter_num, "")
        recent_entities = []
        for ch_key in list(locked_chapters.keys())[-5:]:
            ch = locked_chapters.get(ch_key, {})
            summary = ch.get("summary", "")
            if summary:
                recent_entities.append(summary[:80])

        query_parts = [f"第{chapter_num}{unit_label}"]
        if boundary_text:
            query_parts.append(boundary_text[:200])
        if recent_entities:
            query_parts.append("前文摘要：" + " | ".join(recent_entities[-3:]))
        return " ".join(query_parts)

    async def _call_llm_with_429_retry(
        self,
        llm_provider,
        prompt: str,
        temperature: float,
        context: str = "",
    ):
        """调用LLM生成并自动处理429限流错误（指数退避重试）

        Args:
            llm_provider: LLM提供商实例
            prompt: 提示词
            temperature: 温度参数
            context: 上下文标识（如"第5章"）用于日志

        Returns:
            LLM响应对象

        Raises:
            Exception: 非429错误直接抛出；429错误重试耗尽后抛出
        """
        ctx_suffix = f" | {context}" if context else ""
        for attempt in range(self.LLM_429_MAX_RETRIES):
            try:
                return await llm_provider.generate(
                    prompt=prompt, temperature=temperature)
            except Exception as e:
                error_str = str(e)
                is_429 = any(kw in error_str for kw in (
                    '429', 'TooManyRequests', 'ServerOverloaded', 'rate_limit'))
                if not is_429:
                    raise
                if attempt < self.LLM_429_MAX_RETRIES - 1:
                    wait_time = self.LLM_429_BASE_DELAY * (2 ** attempt)
                    self.logger.warning(
                        f"[原子化生成] LLM返回429限流错误{ctx_suffix}，"
                        f"第{attempt + 1}次重试，等待{wait_time}秒...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(
                        f"[原子化生成] LLM 429限流错误{ctx_suffix}，"
                        f"已重试{self.LLM_429_MAX_RETRIES}次仍失败")
                    raise

    def _add_boundary_retry_instruction(
        self, original_prompt: str, chapter_num: int, unit_label: str
    ) -> str:
        """边界验证失败后追加的重试指令"""
        return (
            f"# ⚠️ 重试指令（第{chapter_num}{unit_label}）\n\n"
            f"上一版内容超出了本章范围，包含后续章节剧情。\n"
            f"请严格限定在「本章专属内容范围」内，不要提前引入后续章节的事件。\n\n"
            f"---\n\n" + original_prompt
        )

    # ==================== 上下文构建 ====================

    def _extract_chapter_outline_segment(
        self,
        global_outline: str,
        chapter_num: int,
        content_type: str,
        unit_label: str,
    ) -> str:
        """从全局大纲中提取当前章节的专属大纲段落（内容隔离）

        核心原则：禁止对global_outline做字符串切片[:N]，
        而是通过正则/结构化提取当前章节对应的大纲段落。

        Args:
            global_outline: 全局大纲完整文本
            chapter_num: 当前章节号
            content_type: 内容类型
            unit_label: 单元标签

        Returns:
            当前章节对应的大纲段落，提取失败返回空字符串
        """
        if not global_outline:
            return ""

        import re

        # 构造中文数字章节号（如 7 → 七）
        def _num_to_chinese(n):
            if n <= 10:
                return "零一二三四五六七八九十"[n]
            elif n < 20:
                return "十" + ("一二三四五六七八九"[n - 11] if n > 10 else "")
            elif n < 100:
                tens, ones = divmod(n, 10)
                result = ("" if tens == 1 else "一二三四五六七八九"[tens - 1]) + "十"
                if ones:
                    result += "一二三四五六七八九"[ones - 1]
                return result
            return str(n)

        chinese_chapter = _num_to_chinese(chapter_num)
        chinese_nums = "一二三四五六七八九十百千"
        unit_class = f"[章节集场]"
        # 负向前瞻：匹配所有中文+阿拉伯数字章节标题
        next_chapter_lookahead = rf"(?=第[{chinese_nums}\d]+{unit_class})"

        # 根据内容类型选择匹配模式（兼容中文与阿拉伯数字章节编号）
        if content_type == "novel":
            patterns = [
                rf"第[{chinese_nums}\d]*{chinese_chapter}[{chinese_nums}\d]*章[^\n]*\n(?:(?!第[{chinese_nums}\d]+章).)*",
                rf"第[{chinese_nums}\d]*{chapter_num}[{chinese_nums}\d]*章[^\n]*\n(?:(?!第[{chinese_nums}\d]+章).)*",
                rf"第[{chinese_nums}\d]*{chinese_chapter}[{chinese_nums}\d]*章.*?{next_chapter_lookahead}",
                rf"第[{chinese_nums}\d]*{chapter_num}[{chinese_nums}\d]*章.*?{next_chapter_lookahead}",
                rf"第[{chinese_nums}\d]*{chinese_chapter}[{chinese_nums}\d]*章.*?$",
                rf"第[{chinese_nums}\d]*{chapter_num}[{chinese_nums}\d]*章.*?$",
            ]
        elif content_type in ("series_script", "script"):
            patterns = [
                rf"第[{chinese_nums}\d]*{chinese_chapter}[{chinese_nums}\d]*集[^\n]*\n(?:(?!第[{chinese_nums}\d]+集).)*",
                rf"第[{chinese_nums}\d]*{chapter_num}[{chinese_nums}\d]*集[^\n]*\n(?:(?!第[{chinese_nums}\d]+集).)*",
            ]
        elif content_type == "movie_script":
            patterns = [
                rf"第[{chinese_nums}\d]*{chinese_chapter}[{chinese_nums}\d]*场[^\n]*\n(?:(?!第[{chinese_nums}\d]+场).)*",
                rf"第[{chinese_nums}\d]*{chapter_num}[{chinese_nums}\d]*场[^\n]*\n(?:(?!第[{chinese_nums}\d]+场).)*",
            ]
        else:
            patterns = [
                rf"第[{chinese_nums}\d]*{chinese_chapter}[{chinese_nums}\d]*{unit_class}[^\n]*\n(?:(?!第[{chinese_nums}\d]+{unit_class}).)*",
                rf"第[{chinese_nums}\d]*{chapter_num}[{chinese_nums}\d]*{unit_class}[^\n]*\n(?:(?!第[{chinese_nums}\d]+{unit_class}).)*",
            ]

        for pattern in patterns:
            try:
                match = re.search(pattern, global_outline, re.DOTALL)
                if match:
                    return match.group(0).strip()
            except re.error:
                continue

        # 无法精确提取
        self.logger.info(
            f"[大纲隔离] 第{chapter_num}{unit_label}：无法精确提取大纲段落，"
            f"content_type={content_type}")
        return ""

    def _build_locked_summary(
        self, locked_chapters: Dict[str, Dict[str, Any]],
        current_chapter: int, unit_label: str, unit_count: int
    ) -> str:
        """构建前文锁定章节的滚动摘要（最近5章）"""
        if not locked_chapters:
            return "（无前文，这是第一章）"

        window_start = max(1, current_chapter - self.LOCKED_CONTEXT_WINDOW)
        parts = []
        for ch_num in range(window_start, current_chapter):
            ch_key = str(ch_num)
            if ch_key not in locked_chapters:
                continue
            ch = locked_chapters[ch_key]
            title = ch.get("title", "")
            summary = ch.get("summary", "")
            if len(summary) > 300:
                summary = summary[:300] + "..."
            parts.append(
                f"第{ch_num}{unit_label}《{title}》\n  摘要：{summary}")

        return '\n'.join(parts) if parts else "（无前文）"

    def _get_last_chapter_ending(
        self, locked_chapters: Dict[str, Dict[str, Any]],
        current_chapter: int, unit_label: str
    ) -> str:
        """获取上一章的结尾状态"""
        if current_chapter <= 1:
            return "（故事开始，无上一章）"

        prev_key = str(current_chapter - 1)
        if prev_key not in locked_chapters:
            return "（上一章数据不可用）"

        prev = locked_chapters[prev_key]
        prev_title = prev.get("title", "")
        prev_full = prev.get("full_content", "") or prev.get("summary", "")
        ending = prev_full[-200:] if len(prev_full) > 200 else prev_full

        return (f"第{current_chapter - 1}{unit_label}《{prev_title}》\n"
                f"结尾状态：{ending.strip()}")
