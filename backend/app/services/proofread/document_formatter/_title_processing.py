"""DocumentFormatter - 标题标准化与重复处理Mixin"""
from __future__ import annotations
import re
from typing import Dict
from typing import Any
from typing import Tuple


class TitleProcessingMixin:
    """标题标准化与重复处理"""

    def _process_markdown_headers(self, content: str) -> str:
        """处理Markdown标题"""
        lines = content.split('\n')
        result_lines = []

        for line in lines:
            # 检测Markdown标题
            match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()

                # 一级和二级标题转换为章节格式
                if level <= 2:
                    # 检查标题是否已经包含章节编号
                    has_chapter_num = bool(
                        re.search(r'第[一二三四五六七八九十百千万零\d]+[章节回集场]', title) or
                        re.search(r'[Cc]hapter\s*\d+', title) or
                        re.search(r'[Ee]pisode\s*\d+', title) or
                        re.search(r'[Ss]cene\s*\d+', title)
                    )

                    if not has_chapter_num:
                        # 尝试从标题中提取数字
                        num_match = re.search(r'(\d+)', title)
                        if num_match:
                            num = int(num_match.group(1))
                            # 转换为标准格式
                            unit = self._get_unit_name()
                            chinese_num = self._number_to_chinese(num)
                            title = f"第{chinese_num}{unit} {title}"
                            self.stats.markdown_headers_processed += 1

                    result_lines.append(title)
                else:
                    # 三级及以下标题保留原样
                    result_lines.append(line)
            else:
                result_lines.append(line)

        return '\n'.join(result_lines)


    def _normalize_chapter_titles(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        统一章节标题格式

        Returns:
            (格式化后的内容, 章节信息列表)
        """
        lines = content.split('\n')
        result_lines = []
        chapter_info = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            normalized = False

            for pattern, num_group, title_group, norm_type in self._compiled_patterns:
                match = pattern.match(line_stripped)
                if match:
                    groups = match.groups()
                    number_str = groups[num_group -
                                        1] if num_group <= len(groups) else ''
                    title = groups[title_group -
                                   1] if title_group <= len(groups) else ''

                    # 验证是否为有效章节标题
                    if not self._is_valid_chapter_title(title, line_stripped):
                        continue

                    # 转换章节编号
                    if number_str.isdigit():
                        number = int(number_str)
                    else:
                        number = self._chinese_to_number(number_str)

                    if number <= 0:
                        continue

                    # 标准化为统一格式
                    unit = self._get_unit_name()
                    chinese_num = self._number_to_chinese(number)

                    # 清理标题
                    title = title.strip()
                    # 移除标题中可能存在的编号前缀
                    title = re.sub(
                        r'^[\d一二三四五六七八九十百千万零]+[\.、\s:：]+', '', title)
                    title = re.sub(
                        r'^第[一二三四五六七八九十百千万零\d]+[章节回集场][\s:：]*', '', title)
                    title = title.strip()

                    # 生成标准化标题
                    if title:
                        normalized_title = f"第{chinese_num}{unit} {title}"
                    else:
                        normalized_title = f"第{chinese_num}{unit}"

                    result_lines.append(normalized_title)
                    chapter_info.append({
                        'line_index': i,
                        'number': number,
                        'original_title': line_stripped,
                        'normalized_title': normalized_title,
                        'title': title
                    })

                    self.stats.titles_normalized += 1
                    normalized = True
                    break

            if not normalized:
                result_lines.append(line)

        return '\n'.join(result_lines), chapter_info


    def _is_valid_chapter_title(self, title: str, original_line: str) -> bool:
        """验证是否为有效的章节标题"""
        # 检查非章节关键词
        for keyword in self.NON_CHAPTER_KEYWORDS:
            if keyword in title or keyword in original_line:
                return False

        # 检查标题长度
        if len(original_line) > 100:
            return False

        # 检查是否以句号结尾
        if title.endswith(('。', '？', '！', '.', '?', '!')):
            return False

        # 检查是否为纯数字
        if title.isdigit():
            return False

        return True


    def _remove_duplicate_titles(self, content: str, chapter_info: List[Dict[str, Any]]) -> str:
        """移除重复的章节标题"""
        if not chapter_info:
            return content

        lines = content.split('\n')

        # 检测重复：相同编号的章节标题在很近的距离内出现
        seen_numbers = {}  # number -> (line_index, title)
        lines_to_remove = set()

        for info in chapter_info:
            number = info['number']
            line_idx = info['line_index']
            title = info.get('title', '')

            if number in seen_numbers:
                prev_line_idx, prev_title = seen_numbers[number]

                # 如果两个相同编号的章节标题距离很近（< 5行），可能是重复
                if line_idx - prev_line_idx < 5:
                    # 保留标题更完整的那个
                    if len(title) > len(prev_title):
                        lines_to_remove.add(prev_line_idx)
                        seen_numbers[number] = (line_idx, title)
                    else:
                        lines_to_remove.add(line_idx)
                    self.stats.duplicate_titles_removed += 1
                    logger.debug(
                        f"移除重复章节标题: 第{number}章 "
                        f"(行{prev_line_idx + 1} vs 行{line_idx + 1})"
                    )
                else:
                    # 距离较远，可能是分卷或其他情况，保留
                    seen_numbers[number] = (line_idx, title)
            else:
                seen_numbers[number] = (line_idx, title)

        # 构建结果
        result_lines = [
            line for i, line in enumerate(lines)
            if i not in lines_to_remove
        ]

        return '\n'.join(result_lines)


