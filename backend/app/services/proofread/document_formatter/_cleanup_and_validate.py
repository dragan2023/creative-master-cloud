"""DocumentFormatter - 空白清理与验证Mixin"""
from __future__ import annotations
import re
from typing import Tuple
from app.services.proofread.document_formatter._schemas import FormattingStats


class CleanupAndValidateMixin:
    """空白清理与验证"""

    def _cleanup_whitespace(self, content: str) -> str:
        """清理多余空白"""
        # 移除行尾空白
        content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)

        # 限制连续空行为最多2个
        content = re.sub(r'\n{3,}', '\n\n', content)

        # 移除行首多余空格（保留缩进）
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            # 保留最多4个空格的缩进
            stripped = line.lstrip()
            indent_len = min(len(line) - len(stripped), 4)
            cleaned_lines.append(' ' * indent_len + stripped)

        return '\n'.join(cleaned_lines)


    def _validate_and_fix(self, content: str) -> str:
        """验证格式化结果并修复问题"""
        lines = content.split('\n')

        # 检测章节编号连续性
        chapter_numbers = []
        for line in lines:
            for pattern, _, _, _ in self._compiled_patterns:
                match = pattern.match(line.strip())
                if match:
                    number_str = match.groups()[0]
                    if number_str.isdigit():
                        chapter_numbers.append(int(number_str))
                    else:
                        chapter_numbers.append(
                            self._chinese_to_number(number_str))
                    break

        if chapter_numbers:
            sorted_numbers = sorted(chapter_numbers)
            expected = list(range(1, max(sorted_numbers) + 1))
            missing = set(expected) - set(sorted_numbers)

            if missing:
                logger.warning(f"检测到章节编号不连续，缺失: {sorted(missing)[:10]}...")

        return content


    def _count_chapters(self, content: str) -> int:
        """统计章节数量"""
        count = 0
        for pattern, _, _, _ in self._compiled_patterns:
            matches = pattern.findall(content)
            count = max(count, len(matches))
        return count


def format_document(content: str, content_type: str = "novel") -> Tuple[str, FormattingStats]:
    """
    格式化文档的便捷函数

    Args:
        content: 文档内容
        content_type: 内容类型

    Returns:
        (格式化后的内容, 格式化统计信息)
    """
    formatter = DocumentFormatter(content_type=content_type)
    return formatter.format(content)


