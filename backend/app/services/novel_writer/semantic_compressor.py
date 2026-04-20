"""
语义压缩器
基于分级策略对超长上下文进行语义压缩，替代粗暴截断

核心原则：
1. 禁止对正文生成结果做截断处理（字数控制依赖LLM自主遵循）
2. 禁止对global_outline和unit_summaries使用字符串切片（[:N]）
3. 压缩仅针对前文摘要和向量检索结果等"参考性"上下文
4. 对大纲/概述内容通过"选择性传入"控制规模，而非截断

@date: 2026-04-19
@version: v1.0.0
"""
import hashlib
from enum import Enum
from typing import Dict, Any, List, Optional

from app.core.logger import get_logger


class CompressionLevel(Enum):
    """压缩级别"""
    DETAILED = "detailed"      # 相邻1-2单元：保留完整结尾+关键情节，约800字
    MODERATE = "moderate"      # 近距离3-5单元：保留事件摘要+角色变化，约400字
    BRIEF = "brief"            # 远距离5+单元：仅保留核心事件和伏笔，约150字


# 每个级别的目标字数
LEVEL_TARGET_CHARS = {
    CompressionLevel.DETAILED: 800,
    CompressionLevel.MODERATE: 400,
    CompressionLevel.BRIEF: 150,
}

# 每个级别的LLM压缩提示词模板
COMPRESSION_PROMPTS = {
    CompressionLevel.DETAILED: (
        "请将以下小说章节内容压缩为{target}字以内的详细摘要。"
        "要求：保留所有关键情节发展、角色变化和伏笔线索，仅去掉冗余描写和过渡段落。"
        "直接输出摘要内容，不要添加任何前缀说明。\n\n"
        "章节内容：\n{content}"
    ),
    CompressionLevel.MODERATE: (
        "请将以下小说章节内容压缩为{target}字以内的摘要。"
        "要求：保留主要事件和角色发展，省略细节描写。"
        "直接输出摘要内容，不要添加任何前缀说明。\n\n"
        "章节内容：\n{content}"
    ),
    CompressionLevel.BRIEF: (
        "请将以下小说章节内容压缩为{target}字以内的极简摘要。"
        "要求：仅保留核心事件（谁做了什么、关键转折），用精炼语言概括。"
        "直接输出摘要内容，不要添加任何前缀说明。\n\n"
        "章节内容：\n{content}"
    ),
}


class SemanticCompressor:
    """语义压缩器 — 用LLM生成摘要替代截断

    设计理念：
    - 对前文摘要/向量检索结果等"参考性"上下文，使用LLM生成语义摘要
    - 对global_outline/unit_summaries等"指导性"上下文，不做截断，
      而是通过选择性传入（仅传当前单元+邻近单元的完整概述）控制规模
    - 压缩结果带缓存，同一单元同一级别只压缩一次

    使用约束：
    - 绝不压缩正文生成结果
    - 绝不对大纲/概述做字符串切片
    - 仅当上下文总长度超过阈值时才触发压缩
    """

    def __init__(
        self,
        llm_provider=None,
        max_context_chars: int = 12000,
        compression_threshold: int = 10000,
    ):
        """
        Args:
            llm_provider: LLM提供者，用于语义压缩。为None时降级为规则压缩
            max_context_chars: 上下文最大字符数（软限制）
            compression_threshold: 触发压缩的阈值字符数
        """
        self.llm_provider = llm_provider
        self.max_context_chars = max_context_chars
        self.compression_threshold = compression_threshold
        self._cache: Dict[str, str] = {}  # 缓存已压缩内容
        self.logger = get_logger("semantic_compressor")

    def _cache_key(self, content: str, level: CompressionLevel) -> str:
        """生成缓存键"""
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
        return f"{content_hash}_{level.value}"

    def get_compression_level(self, distance: int) -> CompressionLevel:
        """根据与当前单元的距离获取压缩级别

        Args:
            distance: 与当前单元的距离（章节数差）

        Returns:
            压缩级别
        """
        if distance <= 2:
            return CompressionLevel.DETAILED
        elif distance <= 5:
            return CompressionLevel.MODERATE
        else:
            return CompressionLevel.BRIEF

    async def compress_text(
        self,
        text: str,
        target_length: int = 1500,
        level: Optional[CompressionLevel] = None,
    ) -> str:
        """压缩单段文本

        Args:
            text: 待压缩文本
            target_length: 目标长度（字符数）
            level: 指定压缩级别，None时根据文本长度自动选择

        Returns:
            压缩后的文本
        """
        if not text or len(text) <= target_length:
            return text

        if level is None:
            # 根据文本与目标的差距自动选择级别
            ratio = len(text) / target_length
            if ratio <= 2:
                level = CompressionLevel.DETAILED
            elif ratio <= 4:
                level = CompressionLevel.MODERATE
            else:
                level = CompressionLevel.BRIEF

        # 检查缓存
        cache_key = self._cache_key(text, level)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 尝试LLM压缩
        if self.llm_provider:
            try:
                result = await self._llm_compress(text, level)
                if result and len(result) < len(text):
                    self._cache[cache_key] = result
                    return result
            except Exception as e:
                self.logger.warning(f"LLM压缩失败，降级为规则压缩: {e}")

        # 降级：规则压缩（按段落边界截取，避免截断句子）
        result = self._rule_compress(text, target_length)
        self._cache[cache_key] = result
        return result

    async def compress_previous_summaries(
        self,
        summaries: List[Dict[str, Any]],
        current_unit: int,
    ) -> str:
        """分级压缩前文摘要

        对不同距离的前文单元使用不同压缩级别，生成精炼的前文摘要。

        Args:
            summaries: 前文单元摘要列表，每个元素含unit_number和content字段
            current_unit: 当前单元号

        Returns:
            分级压缩后的前文摘要
        """
        if not summaries:
            return ""

        compressed_parts = []
        for summary in summaries:
            unit_number = summary.get("unit_number", 0)
            content = summary.get("content", "")
            if not content:
                continue

            distance = current_unit - unit_number
            if distance <= 0:
                continue

            level = self.get_compression_level(distance)
            target_chars = LEVEL_TARGET_CHARS[level]

            # 如果内容已短于目标，直接使用
            if len(content) <= target_chars:
                header = f"第{unit_number}章摘要："
                compressed_parts.append(f"{header}{content}")
                continue

            # 执行压缩
            compressed = await self.compress_text(content, target_length=target_chars, level=level)
            header = f"第{unit_number}章摘要："
            compressed_parts.append(f"{header}{compressed}")

        return "\n\n".join(compressed_parts)

    async def compress_context_dict(
        self,
        context: Dict[str, Any],
        compressible_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """对上下文字典中的可压缩字段进行压缩

        核心原则：
        - 仅压缩compressible_keys中指定的"参考性"字段
        - 绝不压缩大纲、概述等"指导性"字段
        - 每个字段独立判断是否需要压缩

        Args:
            context: 原始上下文字典
            compressible_keys: 可压缩的字段名列表

        Returns:
            压缩后的上下文字典
        """
        if compressible_keys is None:
            # 默认可压缩字段：前文摘要和向量检索结果
            compressible_keys = [
                "previous_content_summaries",
                "short_summary",
                "vector_context",
                "global_summary",
            ]

        # 计算上下文总长度
        total_chars = sum(len(str(v)) for v in context.values() if v)

        if total_chars < self.compression_threshold:
            self.logger.info(
                f"上下文总长度{total_chars}字符，未达阈值{self.compression_threshold}，跳过压缩"
            )
            return context

        self.logger.info(
            f"上下文总长度{total_chars}字符，超过阈值{self.compression_threshold}，开始压缩"
        )

        # 按字段长度降序排列，优先压缩最长的字段
        compressible_items = []
        for key in compressible_keys:
            content = context.get(key, "")
            if content and len(str(content)) > 1500:
                compressible_items.append(
                    (key, str(content), len(str(content))))

        # 按长度降序排列
        compressible_items.sort(key=lambda x: x[2], reverse=True)

        compressed_total = 0
        for key, content, original_len in compressible_items:
            # 目标：将该字段压缩到1500字符以内
            target = min(1500, original_len)
            if original_len <= target:
                continue

            compressed = await self.compress_text(content, target_length=target)
            context[key] = compressed
            saved = original_len - len(compressed)
            compressed_total += saved
            self.logger.info(
                f"压缩字段'{key}': {original_len}→{len(compressed)}字符，节省{saved}字符"
            )

        self.logger.info(f"压缩完成，总共节省{compressed_total}字符")
        return context

    def select_unit_summaries(
        self,
        unit_summaries: Dict[str, Any],
        current_unit: int,
        adjacent_range: int = 1,
    ) -> Dict[str, Any]:
        """选择性传入单元概述，替代截断

        核心原则：禁止对unit_summaries做字符串切片[:N]，
        而是通过"选择性传入"控制规模：
        - 当前单元 + 前后各adjacent_range个单元：完整传入概述
        - 其余单元：仅传入标题和一句话摘要

        Args:
            unit_summaries: 完整的unit_summaries字典
            current_unit: 当前单元号
            adjacent_range: 邻近范围（前后各N个单元完整传入）

        Returns:
            精简后的单元概述字典
        """
        if not unit_summaries or not isinstance(unit_summaries, dict):
            return unit_summaries

        selected = {}
        for key, value in unit_summaries.items():
            if not isinstance(value, dict):
                selected[key] = value
                continue

            unit_num = value.get("unit_number", 0)
            try:
                unit_num = int(unit_num) if unit_num else int(key)
            except (ValueError, TypeError):
                unit_num = 0

            distance = abs(unit_num - current_unit)

            if distance <= adjacent_range:
                # 邻近单元：完整传入
                selected[key] = value
            else:
                # 远距离单元：仅保留标题和精简摘要
                selected[key] = {
                    "unit_number": unit_num,
                    "title": value.get("title", ""),
                    "summary": value.get("summary", "")[:80] + "..."
                    if len(value.get("summary", "")) > 80
                    else value.get("summary", ""),
                    "status": value.get("status", ""),
                    "_compressed": True,  # 标记为精简版
                }

        return selected

    def extract_current_outline_segment(
        self,
        global_outline: str,
        current_unit: int,
        content_type: str = "novel",
    ) -> str:
        """从全局大纲中提取当前单元对应的段落

        核心原则：禁止对global_outline做字符串切片[:N]，
        而是通过正则/结构化提取当前单元对应的大纲段落。

        Args:
            global_outline: 全局大纲完整文本
            current_unit: 当前单元号
            content_type: 内容类型

        Returns:
            当前单元对应的大纲段落
        """
        if not global_outline:
            return ""

        import re

        # 根据内容类型选择匹配模式
        if content_type == "novel":
            patterns = [
                rf"第{current_unit}章[^\n]*\n(?:(?!第\d+章).)*",
                rf"第{current_unit}章.*?(?=第\d+章|$)",
            ]
        elif content_type in ("series_script", "script"):
            patterns = [
                rf"第{current_unit}集[^\n]*\n(?:(?!第\d+集).)*",
                rf"第{current_unit}集.*?(?=第\d+集|$)",
            ]
        elif content_type == "movie_script":
            patterns = [
                rf"第{current_unit}场[^\n]*\n(?:(?!第\d+场).)*",
                rf"场景{current_unit}[^\n]*\n(?:(?!场景\d+).)*",
            ]
        else:
            patterns = [
                rf"第{current_unit}[章节集场][^\n]*\n(?:(?!第\d+[章节集场]).)*",
            ]

        for pattern in patterns:
            try:
                match = re.search(pattern, global_outline, re.DOTALL)
                if match:
                    return match.group(0).strip()
            except re.error:
                continue

        # 无法精确提取时，返回空字符串而非截断整个大纲
        self.logger.warning(
            f"无法从全局大纲提取第{current_unit}单元段落，content_type={content_type}"
        )
        return ""

    async def _llm_compress(self, text: str, level: CompressionLevel) -> Optional[str]:
        """使用LLM进行语义压缩

        Args:
            text: 待压缩文本
            level: 压缩级别

        Returns:
            压缩后的文本，失败返回None
        """
        if not self.llm_provider:
            return None

        target_chars = LEVEL_TARGET_CHARS[level]
        prompt_template = COMPRESSION_PROMPTS[level]
        prompt = prompt_template.format(target=target_chars, content=text)

        try:
            response = await self.llm_provider.generate(prompt)
            result = response.content if hasattr(
                response, 'content') else str(response)

            # 清理可能的markdown标记
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(
                    lines[1:-1] if lines[-1] == "```" else lines[1:]
                )

            return result.strip()
        except Exception as e:
            self.logger.warning(f"LLM语义压缩失败: {e}")
            return None

    def _rule_compress(self, text: str, target_length: int) -> str:
        """规则压缩（降级方案）

        当LLM不可用时的降级压缩策略：
        1. 按段落边界截取
        2. 保留首尾段落
        3. 中间段落仅保留首句

        Args:
            text: 待压缩文本
            target_length: 目标长度

        Returns:
            压缩后的文本
        """
        if len(text) <= target_length:
            return text

        paragraphs = text.split("\n\n")
        if len(paragraphs) <= 2:
            # 段落太少，按句子截取
            sentences = re.split(r'[。！？\n]', text)
            result = ""
            for sentence in sentences:
                if len(result) + len(sentence) + 1 > target_length:
                    break
                if sentence.strip():
                    result += sentence + "。"
            return result.strip() if result else text[:target_length]

        # 保留首段和末段，中间段仅保留首句
        result_parts = [paragraphs[0]]

        # 计算剩余可用长度
        remaining = target_length - \
            len(paragraphs[0]) - len(paragraphs[-1]) - 4

        for para in paragraphs[1:-1]:
            if remaining <= 0:
                break
            # 取段落首句
            import re
            first_sentence = re.split(r'[。！？]', para, maxsplit=1)[0]
            if first_sentence.strip():
                snippet = first_sentence.strip() + "..."
                if len(snippet) <= remaining:
                    result_parts.append(snippet)
                    remaining -= len(snippet)
                else:
                    break

        result_parts.append(paragraphs[-1])
        return "\n\n".join(result_parts)
