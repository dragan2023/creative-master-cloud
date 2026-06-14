"""
风格润色Agent - AI文风检测与消除 Mixin

包含 style_editor_agent.py 中的AI文风检测和人性化改写相关方法。

@date: 2026-04-24
@version: v1.0.0
"""
from typing import Any, Dict, List, Optional

from app.agents.writing.base_agent import AgentContext
from app.agents.writing.prompts.style_prompts import STYLE_PROMPTS


class StyleEditorDetectionMixin:
    """AI文风检测与消除 Mixin"""

    async def _detect_ai_writing(
        self,
        content: str,
        context: AgentContext
    ) -> Optional[Dict[str, Any]]:
        """检测AI写作特征"""
        try:
            detection_prompt = STYLE_PROMPTS["detect_ai_writing"].format(
                content=content
            )

            messages = [{"role": "user", "content": detection_prompt}]

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
            self.logger.error(f"AI文风检测失败: {e}")
            return None

    async def _humanize_content(
        self,
        content: str,
        detected_issues: List[Dict],
        style_guide: Dict,
        context: AgentContext
    ) -> Optional[Dict[str, Any]]:
        """人性化改写内容"""
        try:
            issues_text = self._format_ai_issues(detected_issues)

            humanization_prompt = STYLE_PROMPTS["eliminate_ai_style"].format(
                detected_issues=issues_text,
                original_content=content,
                style_guide=self._format_style_guide(style_guide)
            )

            messages = [{"role": "user", "content": humanization_prompt}]

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
            self.logger.error(f"人性化改写失败: {e}")
            return None

    def _format_ai_issues(self, issues: List[Dict]) -> str:
        """格式化AI检测问题"""
        if not issues:
            return "未检测到AI写作特征"

        formatted = []
        for i, issue in enumerate(issues, 1):
            category = issue.get("category", "未知类别")
            issue_type = issue.get("type", "未知类型")
            severity = issue.get("severity", "medium")
            location = issue.get("location", "")
            description = issue.get("description", "")
            ai_pattern = issue.get("ai_pattern", "")
            human_alternative = issue.get("human_alternative", "")

            formatted.append(
                f"【问题{i}】\n"
                f"类别: {category}\n"
                f"类型: {issue_type}\n"
                f"严重程度: {severity}\n"
                f"位置: {location}\n"
                f"描述: {description}\n"
                f"AI模式: {ai_pattern}\n"
                f"人类写法: {human_alternative}"
            )

        return "\n\n".join(formatted)
