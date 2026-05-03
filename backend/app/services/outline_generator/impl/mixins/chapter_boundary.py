"""大纲生成器 - 章节边界程序化提取与验证Mixin

核心创新：从全局大纲中程序化提取每章的内容边界，并在每章生成后
执行程序化验证，从根本上消除"跨章节内容泄漏"问题。

设计原则：
- 正向约束：告诉LLM"本章应该写什么"而非"不要写什么"
- 程序化校验：不依赖LLM自觉遵守，而是代码层面强制验证
- 多层回退：正则主解析 → 关键词辅助 → LLM兜底
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any


@dataclass
class ValidationResult:
    """单章边界验证结果"""
    passed: bool
    warnings: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    matched_future_events: List[str] = field(default_factory=list)
    score: float = 1.0  # 1.0=完全合规, 0.0=严重违规


class ChapterBoundaryMixin:
    """章节边界程序化提取与验证"""

    # ==================== 常量定义 ====================
    # 中文停用词（过滤无意义的词）
    _STOP_WORDS: Set[str] = {
        '这是', '这个', '那个', '一个', '一种', '其中', '这里', '那里',
        '此时', '然后', '之后', '之前', '期间', '当中', '已经', '正在',
        '可以', '需要', '应该', '必须', '能够', '可能', '将会', '一直',
        '非常', '十分', '特别', '比较', '更加', '最为', '及其', '以及',
        '但是', '然而', '因此', '所以', '因为', '如果', '虽然', '尽管',
        '不仅', '而且', '或者', '并且', '同时', '最终', '终于', '突然',
        '原来', '显然', '似乎', '也许', '或许', '大概', '一般', '通常',
        '开始', '结束', '进行', '发生', '出现', '变成', '成为', '感到',
        '知道', '觉得', '认为', '以为', '希望', '决定', '准备', '打算',
    }

    # 分章大纲段落定位正则
    _CHAPTER_OUTLINE_HEADER_RE = re.compile(
        r'#+\s*(?:分章大纲|章节分配|章节划分|分章规划|章节计划)',
        re.IGNORECASE
    )
    _CHAPTER_OUTLINE_SECTION_RE = re.compile(
        r'(?:【|\[)?分章大纲(?:】|\])?[\s\S]*?(?=\n#+\s|\n---|\Z)',
        re.IGNORECASE
    )

    # 章节范围匹配
    _RANGE_RE = re.compile(
        r'^第([\u4e00二三四五六七八九十百千\d]+)[-－至到]\s*'
        r'第?([\u4e00二三四五六七八九十百千\d]+)\s*'
        r'(?:章|集|场)?[：:]\s*(.+)$'
    )
    _SINGLE_CHAPTER_RE = re.compile(
        r'^[-–—•·\s]*第([\u4e00二三四五六七八九十百千\d]+)\s*'
        r'(?:章|集|场)?[：:]\s*(.+)$'
    )

    def extract_chapter_boundaries(
        self,
        global_outline: str,
        unit_count: int,
        unit_label: str = "章"
    ) -> Dict[int, str]:
        """
        从全局大纲中程序化提取每章的边界描述

        策略：
        1. 定位【分章大纲】段落
        2. 解析分章范围（如"第11-30章：江湖历练"）
        3. 解析单章分配（如"第1章：主角穿越"）
        4. 为每章生成标准化的边界描述

        Args:
            global_outline: 完整的全局大纲文本
            unit_count: 总章节数
            unit_label: 单元标签（章/集/场）

        Returns:
            {chapter_num: boundary_description} 字典
        """
        boundary_map: Dict[int, str] = {}

        # 步骤1：定位分章大纲段落
        chapter_section = self._find_chapter_outline_section(global_outline)
        if not chapter_section:
            self.logger.warning("[边界提取] 未找到【分章大纲】段落，回退到全文解析")
            chapter_section = global_outline

        # 步骤2：按行解析
        lines = chapter_section.split('\n')
        current_range_desc = ""
        current_range_start = 0
        current_range_end = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 跳过标题行
            if re.match(r'^#+', line) or line.startswith('【') or line.startswith('```'):
                continue

            # 尝试匹配范围行：第N-M章：xxx
            range_match = self._RANGE_RE.match(line)
            if range_match:
                start = self._parse_chapter_number(range_match.group(1))
                end = self._parse_chapter_number(range_match.group(2))
                desc = range_match.group(3).strip()
                current_range_desc = desc
                current_range_start = start
                current_range_end = end
                # 为范围内每章分配描述
                for ch_num in range(start, end + 1):
                    if ch_num not in boundary_map:
                        boundary_map[ch_num] = desc
                continue

            # 尝试匹配单章行：- 第N章：xxx
            single_match = self._SINGLE_CHAPTER_RE.match(line)
            if single_match:
                ch_num = self._parse_chapter_number(single_match.group(1))
                desc = single_match.group(2).strip()
                boundary_map[ch_num] = desc
                continue

            # 未匹配的行：如果当前在范围内，尝试作为补充描述
            if current_range_start > 0 and len(line) > 3:
                # 可能是续行描述，跳过
                pass

        # 步骤3：补齐缺失章节的边界（使用范围描述或相邻推断）
        for ch_num in range(1, unit_count + 1):
            if ch_num not in boundary_map:
                boundary_map[ch_num] = self._infer_boundary(
                    ch_num, boundary_map, unit_count, unit_label
                )

        self.logger.info(
            f"[边界提取] 成功提取 {len(boundary_map)} 个章节边界，"
            f"目标 {unit_count} 章"
        )
        return boundary_map

    def validate_chapter_against_boundary(
        self,
        chapter_content: str,
        chapter_num: int,
        boundary_map: Dict[int, str],
        unit_label: str = "章"
    ) -> ValidationResult:
        """
        验证生成的章节内容是否超出其边界

        核心算法：
        1. 提取本章内容中的关键事件关键词
        2. 提取所有后续章节(n+1, n+2, ...)边界中的关键事件关键词
        3. 检测是否存在跨章节事件重叠
        4. 根据重叠程度返回验证结果

        Args:
            chapter_content: 本章生成的内容
            chapter_num: 本章编号
            boundary_map: 所有章节的边界映射
            unit_label: 单元标签

        Returns:
            ValidationResult 包含通过/警告/违规信息
        """
        result = ValidationResult()

        if not chapter_content or len(chapter_content.strip()) < 20:
            result.warnings.append("章节内容过短，跳过验证")
            return result

        # 步骤1：提取本章内容的关键词
        chapter_keywords = self._extract_key_events(chapter_content)

        # 步骤2：提取所有后续章节边界的专属关键词
        max_chapter = max(boundary_map.keys()) if boundary_map else chapter_num
        future_keywords_map: Dict[int, Set[str]] = {}

        for future_ch in range(chapter_num + 1, max_chapter + 1):
            if future_ch in boundary_map:
                future_boundary = boundary_map[future_ch]
                future_kw = self._extract_key_events(future_boundary)
                if future_kw:
                    future_keywords_map[future_ch] = future_kw

        # 步骤3：检测重叠
        for future_ch, future_kw_set in future_keywords_map.items():
            # 过滤掉过于通用的词
            specific_kw = {kw for kw in future_kw_set if len(kw) >= 4}
            overlaps = chapter_keywords & specific_kw

            if overlaps:
                result.matched_future_events.extend(
                    f"第{future_ch}{unit_label}专属: {kw}"
                    for kw in overlaps
                )
                result.violations.append(
                    f"检测到第{chapter_num}{unit_label}内容中"
                    f"包含第{future_ch}{unit_label}的专属事件: {', '.join(overlaps)}"
                )

        # 步骤4：判定结果
        violation_count = len(result.violations)
        if violation_count >= 2:
            result.passed = False
            result.score = max(0.0, 1.0 - violation_count * 0.25)
        elif violation_count == 1:
            result.passed = True
            result.score = 0.7
            result.warnings.append(
                f"边界轻微警告：1处疑似越界，请人工复核"
            )
        else:
            result.passed = True
            result.score = 1.0

        if not result.passed or result.warnings:
            self.logger.info(
                f"[边界验证] 第{chapter_num}{unit_label}: "
                f"通过={result.passed}, 分数={result.score:.2f}, "
                f"违规={violation_count}处, 警告={len(result.warnings)}处"
            )
            if result.matched_future_events:
                self.logger.info(
                    f"[边界验证] 越界事件: {result.matched_future_events[:5]}"
                )

        return result

    def extract_key_events_from_boundary(
        self,
        boundary_text: str
    ) -> Set[str]:
        """从单章边界描述中提取关键事件关键词

        Args:
            boundary_text: 边界描述文本

        Returns:
            关键事件关键词集合
        """
        return self._extract_key_events(boundary_text)

    # ==================== 内部辅助方法 ====================

    def _find_chapter_outline_section(self, text: str) -> Optional[str]:
        """定位分章大纲段落"""
        # 策略1：查找【分章大纲】标记
        match = self._CHAPTER_OUTLINE_SECTION_RE.search(text)
        if match:
            section = match.group(0)
            # 截取到下一个大标题或2000字符
            if len(section) > 2000:
                section = section[:2000]
            return section

        # 策略2：查找标题行
        for pattern in [
            r'#{1,3}\s*分章大纲[\s\S]*?(?=\n#{1,3}\s|\Z)',
            r'#{1,3}\s*章节分配[\s\S]*?(?=\n#{1,3}\s|\Z)',
        ]:
            match = re.search(pattern, text)
            if match:
                return match.group(0)[:2000]

        return None

    def _parse_chapter_number(self, num_str: str) -> int:
        """解析章节编号（支持中文数字和阿拉伯数字）"""
        num_str = num_str.strip()
        # 阿拉伯数字
        try:
            return int(num_str)
        except ValueError:
            pass
        # 中文数字
        cn_num_map = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '百': 100, '千': 1000,
        }
        if num_str in cn_num_map:
            return cn_num_map[num_str]
        # 十X 或 X十X 格式
        result = 0
        if '十' in num_str:
            parts = num_str.split('十')
            if parts[0]:
                result += cn_num_map.get(parts[0], 0) * 10
            else:
                result += 10
            if len(parts) > 1 and parts[1]:
                result += cn_num_map.get(parts[1], 0)
            return result
        # 无法解析，尝试作为阿拉伯数字
        try:
            return int(num_str)
        except ValueError:
            return 0

    def _infer_boundary(
        self,
        ch_num: int,
        boundary_map: Dict[int, str],
        unit_count: int,
        unit_label: str
    ) -> str:
        """推断缺失章节的边界描述"""
        # 策略1：使用最近的前一个章节边界
        for prev in range(ch_num - 1, 0, -1):
            if prev in boundary_map:
                desc = boundary_map[prev]
                return f"（继承第{prev}{unit_label}边界）{desc}"

        # 策略2：使用最近的后一个章节边界
        for nxt in range(ch_num + 1, unit_count + 1):
            if nxt in boundary_map:
                desc = boundary_map[nxt]
                return f"（参考第{nxt}{unit_label}边界）{desc}"

        return f"第{ch_num}{unit_label}（未找到明确边界）"

    def _extract_key_events(self, text: str) -> Set[str]:
        """从文本中提取关键事件/人物/地点关键词

        使用中文分词启发式规则：
        1. 提取2-4字的连续中文字符作为候选词
        2. 过滤停用词
        3. 保留名词性短语（动词+名词、形容词+名词结构）

        Args:
            text: 待提取的文本

        Returns:
            关键词集合
        """
        if not text:
            return set()

        keywords: Set[str] = set()

        # 清理文本
        text = re.sub(r'[#*\-\s\n\r\t]+', '', text)
        text = re.sub(r'[，。！？、；：""''（）【】《》…—\u3000]', ' ', text)

        # 提取2-4字中文短语
        for length in [4, 3, 2]:
            pattern = rf'[\u4e00-\u9fff]{{{length}}}'
            matches = re.findall(pattern, text)
            for match in matches:
                if match not in self._STOP_WORDS and len(match.strip()) >= 2:
                    keywords.add(match)

        # 额外提取动词+名词结构（如"兵败自焚"、"初入江湖"）
        vn_pattern = re.findall(
            r'[\u4e00-\u9fff]{2}(?:于|在|到|了|的|得)'
            r'[\u4e00-\u9fff]{2,4}',
            text
        )
        for match in vn_pattern:
            keywords.add(match)

        return keywords

    def build_boundary_context_for_chapter(
        self,
        chapter_num: int,
        boundary_map: Dict[int, str],
        unit_label: str = "章",
        include_neighbors: bool = True
    ) -> str:
        """
        为指定章节构建边界上下文描述

        用于注入到LLM提示词中，作为正向约束。

        Args:
            chapter_num: 目标章节号
            boundary_map: 边界映射表
            unit_label: 单元标签
            include_neighbors: 是否包含相邻章节边界（用于上下文理解）

        Returns:
            格式化的边界上下文文本
        """
        lines = []

        # 本章边界（核心）
        own_boundary = boundary_map.get(
            chapter_num, f"第{chapter_num}{unit_label}内容"
        )
        lines.append(f"【第{chapter_num}{unit_label}的专属内容范围】")
        lines.append(own_boundary)

        if include_neighbors:
            # 上一章边界（衔接参考）
            if chapter_num > 1 and (chapter_num - 1) in boundary_map:
                lines.append("")
                lines.append(f"【第{chapter_num - 1}{unit_label}的结尾状态（衔接点）】")
                lines.append(boundary_map[chapter_num - 1])

            # 下一章边界（禁止跨越的边界）
            if (chapter_num + 1) in boundary_map:
                lines.append("")
                lines.append(
                    f"【第{chapter_num + 1}{unit_label}的内容范围"
                    f"（以下内容绝不出现在本章）】"
                )
                lines.append(boundary_map[chapter_num + 1])

        return '\n'.join(lines)
