"""
风格润色Agent - LLM响应解析工具 Mixin

包含 style_editor_agent.py 中的LLM响应解析和文本清理相关方法。

@date: 2026-04-24
@version: v1.0.0
"""
import re
import time
from typing import Any, Dict

from app.utils.json_parser import parse_json


class StyleEditorUtilsMixin:
    """LLM工具方法 Mixin"""

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """解析LLM返回的JSON响应

        使用健壮的JSON解析器，支持多种格式的LLM返回
        """
        if not content:
            return {
                "polished_content": "",
                "changes_summary": "LLM返回内容为空",
                "word_count": 0
            }

        result = parse_json(content, default=None)

        if result is not None and isinstance(result, dict):
            self.logger.debug("润色JSON解析成功")
            return result

        self.logger.warning("无法解析润色JSON，使用默认结构")
        return {
            "polished_content": content,
            "changes_summary": "直接返回润色内容",
            "word_count": len(content)
        }

    def _clean_control_characters(self, text: str) -> str:
        """清理JSON字符串中的非法控制字符和未转义引号"""
        if not text:
            return text

        original_len = len(text)
        result = []
        i = 0
        text_len = len(text)

        while i < text_len:
            char = text[i]

            if char == '\\':
                result.append(char)
                if i + 1 < text_len:
                    result.append(text[i + 1])
                    i += 2
                    continue
                else:
                    i += 1
                    continue

            if char != '"':
                code = ord(char)
                if len(result) >= 2 and result[-2] == '"' and result[-1] != '\\' and code < 0x20 and code not in (0x09, 0x0A, 0x0D):
                    pass
                elif code == 0x0A or code == 0x09:
                    result.append(' ')
                elif code == 0x0D:
                    pass
                else:
                    result.append(char)
                i += 1
                continue

            is_likely_end_quote = False
            j = i + 1
            while j < text_len and text[j] in ' \t\n\r':
                j += 1

            if j < text_len:
                next_char = text[j]
                if next_char in ':,]}])':
                    is_likely_end_quote = True
                elif j > i + 1:
                    k = i - 1
                    while k >= 0 and text[k] in ' \t\n\r':
                        k -= 1
                    if k >= 0 and text[k] in '([{,:':
                        is_likely_end_quote = True
            else:
                is_likely_end_quote = True

            if is_likely_end_quote:
                result.append(char)
            else:
                result.append('\\"')

            i += 1

        cleaned = ''.join(result)
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', cleaned)

        if len(cleaned) != original_len:
            removed_count = original_len - len(cleaned)
            self.logger.info(
                f"JSON文本清理完成: 原始{original_len}字符 -> 清理后{len(cleaned)}字符 (差异{removed_count})")

        return cleaned

    def _get_timestamp(self) -> int:
        """获取当前时间戳（毫秒）"""
        return int(time.time() * 1000)
