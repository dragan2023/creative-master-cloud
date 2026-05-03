"""DocumentFormatter - 小节标题处理Mixin"""
from __future__ import annotations
import re


class SectionTitlesMixin:
    """小节标题处理"""

    NON_CHAPTER_KEYWORDS = {
        '首先', '其次', '再次', '然后', '最后',
        '注意', '提示', '说明', '备注', '附录', '目录', '前言', '序言',
        '简介', '概述', '摘要', '引言', '后记', '结语', '尾声',
        '步骤', '方法', '技巧', '要点', '重点', '总结',
        # 列表项指示词（需要更严格的上下文验证）
        '第一步', '第二步', '第三步', '第四步', '第五步',
        '第一种', '第二种', '第三种', '第四种', '第五种',
    }

    SECTION_TITLE_PATTERNS = [
        # 中文数字小节：一、二、三、等（单独一行，后面跟标点）
        r'^([一二三四五六七八九十]+)[、．.]\s*(.*)$',
        # 带括号的小节：（一）、（二）、等
        r'^[（(]([一二三四五六七八九十]+)[）)]\s*(.*)$',
        # 数字小节：1. 2. 3. 等（需要验证上下文）
        r'^(\d+)[、．.]\s*(.*)$',
    ]

    EXTENDED_SECTION_PATTERNS = [
        # 第X部分、第X节（非章节单位）
        r'^第([一二三四五六七八九十百千万零\d]+)[部分节](?![章回集场])\s*[:：]?\s*(.*)$',
        # 带圈数字：①②③等
        r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*(.*)$',
        # 罗马数字：I. II. III.等
        r'^([IVXLCDM]+)[\.．]\s*(.*)$',
    ]

    def _process_section_titles(self, content: str) -> str:
        """
        处理章节内部的小节标题

        小节标题（如"一、"、"二、"、"三、"、"1."、"2."等）经常被误识别为章节标题。
        这个方法将这些小节标题转换为特殊格式，避免干扰章节识别。

        处理策略：
        1. 识别小节标题模式（中文数字+顿号、括号数字、阿拉伯数字等）
        2. 通过上下文验证确认是否为小节标题
        3. 将小节标题转换为【小节】标记格式
        4. 保留原始内容，但避免被章节识别器误识别
        """
        lines = content.split('\n')
        result_lines = []
        section_count = 0

        # 编译小节标题模式
        section_patterns = [
            # 中文数字小节：一、二、三、等（高优先级）
            (re.compile(r'^([一二三四五六七八九十]+)[、．.]\s*(.+)$'),
             'chinese_num', 'high'),
            # 带括号的小节：（一）、（二）、等（高优先级）
            (re.compile(r'^[（(]([一二三四五六七八九十]+)[）)]\s*(.+)$'),
             'bracket_num', 'high'),
            # 数字小节：1. 2. 3. 等（需要更严格的验证）
            (re.compile(r'^(\d{1,2})[、．.]\s*(.+)$'), 'digit_num', 'medium'),
            # 带括号的数字：（1）、（2）、等
            (re.compile(r'^[（(](\d{1,2})[）)]\s*(.+)$'),
             'bracket_digit', 'medium'),
            # 带圈数字：①②③等
            (re.compile(r'^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮])\s*(.*)$'),
             'circle_num', 'medium'),
        ]

        # 扩展模式（需要更严格的上下文验证）
        extended_patterns = [
            # 第X部分、第X节（非章节单位）
            (re.compile(
                r'^第([一二三四五六七八九十百千万零\d]+)[部分节]\s*[:：]?\s*(.*)$'), 'part_section', 'low'),
        ]

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            converted = False

            # 跳过空行和已经是章节标题的行
            if not line_stripped or self._is_chapter_title(line_stripped):
                result_lines.append(line)
                continue

            # 检查基本小节模式
            for pattern, pattern_type, priority in section_patterns:
                match = pattern.match(line_stripped)
                if match:
                    section_num = match.group(1)
                    section_title = match.group(2).strip() if len(
                        match.groups()) > 1 else ""

                    # 根据优先级进行不同的验证
                    if priority == 'high':
                        # 高优先级模式：基本验证即可
                        if self._is_section_title(section_num, section_title, line_stripped):
                            converted_line = f"【小节】{section_num}、{section_title}" if section_title else f"【小节】{section_num}"
                            result_lines.append(converted_line)
                            section_count += 1
                            converted = True
                            logger.debug(
                                f"转换小节标题(高优先级): {line_stripped} -> {converted_line}")
                            break
                    elif priority == 'medium':
                        # 中优先级模式：需要更严格的上下文验证
                        if self._is_section_title_with_context(section_num, section_title, line_stripped, lines, i):
                            converted_line = f"【小节】{section_num}、{section_title}" if section_title else f"【小节】{section_num}"
                            result_lines.append(converted_line)
                            section_count += 1
                            converted = True
                            logger.debug(
                                f"转换小节标题(中优先级): {line_stripped} -> {converted_line}")
                            break

            # 如果基本模式没有匹配，检查扩展模式
            if not converted:
                for pattern, pattern_type, priority in extended_patterns:
                    match = pattern.match(line_stripped)
                    if match:
                        section_num = match.group(1)
                        section_title = match.group(2).strip() if len(
                            match.groups()) > 1 else ""

                        # 扩展模式需要严格的上下文验证
                        if self._is_section_title_with_context(section_num, section_title, line_stripped, lines, i):
                            converted_line = f"【小节】{section_num}、{section_title}" if section_title else f"【小节】{section_num}"
                            result_lines.append(converted_line)
                            section_count += 1
                            converted = True
                            logger.debug(
                                f"转换小节标题(扩展模式): {line_stripped} -> {converted_line}")
                            break

            if not converted:
                result_lines.append(line)

        if section_count > 0:
            logger.info(f"处理了 {section_count} 个小节标题")

        return '\n'.join(result_lines)


    def _is_chapter_title(self, line: str) -> bool:
        """
        检查是否为章节标题

        Args:
            line: 行内容

        Returns:
            是否为章节标题
        """
        # 检查是否匹配章节标题模式
        for pattern, _, _, _ in self._compiled_patterns:
            if pattern.match(line):
                return True
        return False


    def _is_section_title_with_context(
        self,
        section_num: str,
        section_title: str,
        original_line: str,
        lines: List[str],
        current_index: int
    ) -> bool:
        """
        带上下文验证的小节标题判断

        用于数字小节等需要更严格验证的模式。

        Args:
            section_num: 小节编号
            section_title: 小节标题
            original_line: 原始行内容
            lines: 所有行
            current_index: 当前行索引

        Returns:
            是否为小节标题
        """
        # 首先进行基本验证
        if not self._is_section_title(section_num, section_title, original_line):
            return False

        # 上下文验证：检查是否在章节标题之后
        # 小节标题通常出现在章节标题之后，而不是文档开头
        found_chapter_before = False
        check_range = min(30, current_index)  # 检查前30行

        for j in range(current_index - 1, max(-1, current_index - check_range - 1), -1):
            if j < 0 or j >= len(lines):
                continue
            check_line = lines[j].strip()
            if not check_line:
                continue
            if self._is_chapter_title(check_line):
                found_chapter_before = True
                break
            # 如果遇到另一个【小节】标记，也说明在章节内
            if check_line.startswith('【小节】'):
                found_chapter_before = True
                break

        # 如果在章节标题之后出现，更可能是小节
        if not found_chapter_before:
            # 如果没有找到前置章节标题，检查是否在文档开头
            # 文档开头的数字列表更可能是目录或列表项
            if current_index < 10:  # 前10行
                return False

        # 检查编号是否连续（可选的额外验证）
        # 如果前后有其他数字小节，更可能是真正的小节

        return True


    def _is_section_title(self, section_num: str, section_title: str, original_line: str) -> bool:
        """
        验证是否为章节内部的小节标题

        Args:
            section_num: 小节编号（中文数字或阿拉伯数字）
            section_title: 小节标题
            original_line: 原始行内容

        Returns:
            是否为小节标题（True=是小节标题，应该被转换）
        """
        # 1. 如果标题包含"章"、"集"、"场"等章节关键词，可能是章节标题，不转换
        chapter_keywords = ['章', '集', '场', 'Chapter', 'Episode', 'Scene']
        for keyword in chapter_keywords:
            if keyword in original_line:
                return False

        # 2. 如果标题长度过长（超过30字），可能是正文，不转换
        if len(original_line) > 30:
            return False

        # 3. 如果标题以句号结尾，可能是正文句子，不转换
        if section_title.endswith(('。', '？', '！', '.', '?', '!')):
            return False

        # 4. 检查是否为非章节关键词
        for keyword in self.NON_CHAPTER_KEYWORDS:
            if keyword in section_title or keyword in original_line:
                return False

        # 5. 新增：检查标题是否过短（只有编号没有标题）
        # 如果只有编号没有标题内容，可能是列表项而非小节标题
        if not section_title.strip():
            # 只有编号的情况需要更严格的验证
            # 中文数字编号单独出现时，通常是小节标题
            # 但需要确保不是章节标题的一部分
            if section_num in ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']:
                return True  # 中文数字单独出现，可能是小节
            return False

        # 6. 新增：检查标题内容是否像正文
        # 如果标题包含多个句子（有多个句号），可能是正文
        if section_title.count('。') > 1:
            return False

        # 7. 新增：检查编号是否合理
        # 如果编号超过20，可能不是小节标题
        try:
            num = int(section_num) if section_num.isdigit(
            ) else self._chinese_to_number(section_num)
            if num > 20:  # 小节编号通常不会超过20
                return False
        except (ValueError, IndexError) as e:
            logger.warning(f"解析小节编号失败: {e}")
            pass

        return True


