"""
风格润色Agent - 文风分析 Mixin

包含 style_editor_agent.py 中的文风文档分析和风格指导相关方法。

@date: 2026-04-24
@version: v1.0.0
"""
import json
import re
from typing import Any, Dict, Optional

from app.agents.writing.base_agent import AgentContext
from app.agents.writing.prompts.style_prompts import STYLE_PROMPTS
from app.utils.json_parser import parse_json, RobustJSONParser


class StyleEditorAnalysisMixin:
    """文风分析 Mixin"""

    async def analyze_style_document(
        self,
        style_document: str,
        context: AgentContext
    ) -> Optional[Dict[str, Any]]:
        """分析文风文档，提取风格特征"""
        try:
            analysis_prompt = STYLE_PROMPTS["analyze_style_document"].format(
                style_document=style_document
            )

            messages = [{"role": "user", "content": analysis_prompt}]

            self.logger.info(f"文风文档分析开始 - Task: {context.task_id}")

            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(
                    context.scene_index) if context.scene_index else None,
                user_id=context.user_id
            )

            if not llm_result:
                self.logger.error(f"文风文档分析LLM返回结果为空 - Task: {context.task_id}")
                return None

            result = self._parse_style_analysis_response(
                llm_result.get("content", ""))

            if result:
                self.logger.info(
                    f"文风文档分析完成 - Task: {context.task_id}, "
                    f"Style: {result.get('style_profile', {}).get('name', 'Unknown')}"
                )

            return result

        except Exception as e:
            self.logger.error(f"文风文档分析失败: {e}")
            return None

    async def get_real_time_style_guide(
        self,
        content_type: str,
        scene_title: str,
        target_words: int,
        project_style_params: Dict[str, Any],
        style_document_features: str,
        context: AgentContext
    ) -> Optional[Dict[str, Any]]:
        """获取实时风格指导"""
        try:
            guide_prompt = STYLE_PROMPTS["real_time_style_guide"].format(
                content_type=content_type,
                scene_title=scene_title,
                target_words=target_words,
                project_style_params=self._format_style_guide(
                    project_style_params),
                style_document_features=style_document_features or "未上传文风文档"
            )

            messages = [{"role": "user", "content": guide_prompt}]

            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(
                    context.scene_index) if context.scene_index else None,
                user_id=context.user_id
            )

            if not llm_result:
                return None

            return self._parse_llm_response(llm_result.get("content", ""))

        except Exception as e:
            self.logger.error(f"获取实时风格指导失败: {e}")
            return None

    def _parse_style_analysis_response(self, content: str) -> Dict[str, Any]:
        """解析风格文档分析的LLM响应"""
        if not content:
            self.logger.error("LLM返回内容为空")
            return self._extract_style_from_text("")

        self.logger.info(f"风格分析 - LLM返回长度: {len(content)} 字符")
        self.logger.debug(f"风格分析 - LLM返回前200字符: {content[:200]}")

        # 使用健壮的JSON解析器
        result, parse_logs = RobustJSONParser.parse(
            content,
            default=None,
            repair_truncated=True
        )

        # 记录解析日志
        for log in parse_logs:
            self.logger.debug(f"JSON解析: {log}")

        if result is not None and isinstance(result, dict):
            if self._validate_style_analysis_result(result):
                style_name = result.get('style_profile', {}).get(
                    'name', 'Unknown') if isinstance(result.get('style_profile'), dict) else 'N/A'
                self.logger.info(f"风格分析JSON解析成功: Style={style_name}")
                return result
            else:
                self.logger.warning(
                    f"JSON验证失败: 缺少必要字段 "
                    f"(style_profile: {'style_profile' in result}, "
                    f"style_guide_for_writing: {'style_guide_for_writing' in result})"
                )
                if result.get('style_profile') or result.get('style_guide_for_writing'):
                    self.logger.info("返回部分有效的风格分析结果")
                    return result

        self.logger.warning("所有JSON解析方法均失败，尝试从文本提取关键信息")
        return self._extract_style_from_text(content)

    def _validate_style_analysis_result(self, result: Dict[str, Any]) -> bool:
        """验证风格分析结果是否包含必要的字段"""
        if not isinstance(result, dict):
            return False

        has_style_profile = "style_profile" in result and isinstance(
            result["style_profile"], dict)
        has_style_guide = "style_guide_for_writing" in result

        return has_style_profile or has_style_guide

    def _try_fix_truncated_json(self, response: str) -> Optional[str]:
        """尝试修复被截断的JSON"""
        style_profile_start = response.find('"style_profile"')
        style_guide_start = response.find('"style_guide_for_writing"')

        if style_profile_start == -1 and style_guide_start == -1:
            return None

        style_profile_obj = None
        if style_profile_start != -1:
            brace_start = response.find('{', style_profile_start)
            if brace_start != -1:
                style_profile_obj = self._extract_complete_object(
                    response, brace_start)

        style_guide_value = None
        if style_guide_start != -1:
            colon_pos = response.find(':', style_guide_start)
            if colon_pos != -1:
                value_start = colon_pos + 1
                while value_start < len(response) and (response[value_start] in [' ', '\t', '\n']):
                    value_start += 1

                if value_start < len(response):
                    if response[value_start] == '"':
                        end_quote = self._find_closing_quote(
                            response, value_start)
                        if end_quote != -1:
                            style_guide_value = response[value_start+1:end_quote]
                    else:
                        next_comma = response.find(',', value_start)
                        next_brace = response.find('}', value_start)
                        end_pos = min(
                            next_comma if next_comma != -1 else len(response),
                            next_brace if next_brace != -1 else len(response)
                        )
                        style_guide_value = response[value_start:end_pos].strip().strip('"')

        if style_profile_obj or style_guide_value:
            parts = []
            if style_profile_obj:
                parts.append(f'"style_profile": {style_profile_obj}')
            if style_guide_value:
                escaped_guide = style_guide_value.replace(
                    '\\', '\\\\').replace('"', '\\"')
                parts.append(f'"style_guide_for_writing": "{escaped_guide}"')

            return '{' + ', '.join(parts) + '}'

        return None

    def _extract_complete_object(self, json_str: str, start: int) -> Optional[str]:
        """从JSON字符串中提取完整的对象"""
        depth = 0
        in_string = False
        escape_next = False
        last_complete_pos = start

        for i in range(start, len(json_str)):
            char = json_str[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\' and in_string:
                escape_next = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return json_str[start:i+1]
                    elif depth == 1:
                        last_complete_pos = i
                elif char == ']' and depth == 1:
                    last_complete_pos = i

        if last_complete_pos > start:
            truncated = json_str[start:last_complete_pos+1]
            truncated = truncated.rstrip()
            while truncated.endswith(',') or truncated.endswith(':'):
                truncated = truncated[:-1]
            return truncated + '}'

        return None

    def _find_closing_quote(self, s: str, start: int) -> int:
        """查找匹配的结束引号"""
        escape = False
        for i in range(start + 1, len(s)):
            if escape:
                escape = False
                continue
            if s[i] == '\\':
                escape = True
                continue
            if s[i] == '"':
                return i
        return -1

    def _extract_style_from_text(self, content: str) -> Dict[str, Any]:
        """从非结构化文本中提取风格信息"""
        style_name = "未知风格"
        style_guide = content  # 不再截断风格文档内容

        name_patterns = [
            r'风格名称[：:]\s*["\']?([^"\'\n，,]+)["\']?',
            r'name[：:]\s*["\']?([^"\'\n，,]+)["\']?',
            r'风格[：:]\s*["\']?([^"\'\n，,]+)["\']?'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, content)
            if match:
                style_name = match.group(1).strip()
                break

        return {
            "style_profile": {
                "name": style_name,
                "vocabulary": {
                    "word_preference": "从文档中自动提取",
                    "signature_words": []
                },
                "sentence_structure": {
                    "average_length": "未知",
                    "preferred_patterns": []
                },
                "narrative_style": {
                    "perspective": "未知",
                    "pacing": "未知"
                }
            },
            "style_guide_for_writing": style_guide,
            "key_imitation_points": [
                "请参考上传的文风文档进行写作",
                "注意保持原文的语言风格特点"
            ],
            "avoid_patterns": [
                "避免与原文风格差异过大的表达"
            ],
            "_raw_content": content,  # 不再截断原始内容
            "_parse_warning": "LLM返回格式非标准JSON，已自动提取关键信息"
        }
