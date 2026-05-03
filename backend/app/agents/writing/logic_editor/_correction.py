"""
逻辑编辑Agent - 逻辑修正 Mixin

@date: 2026-04-24
@version: v1.0.0
"""
from typing import Any, Dict, List, Optional

from app.agents.writing.base_agent import AgentContext
from app.agents.writing.prompts.character_state_prompts import get_logic_correction_prompt


class LogicCorrectionMixin:
    """逻辑修正 Mixin"""

    async def _correct_logic_issues(
        self,
        original_content: str,
        content_type: str,
        detected_issues: List[Dict],
        character_profiles: List[Dict],
        global_outline: Dict,
        previous_summary: str,
        character_state_snapshot: str,
        context: AgentContext
    ) -> Optional[Dict[str, Any]]:
        """修正逻辑问题"""
        try:
            correction_prompt = get_logic_correction_prompt(content_type)

            issues_text = self._format_detected_issues(detected_issues)

            formatted_prompt = correction_prompt.format(
                detected_issues=issues_text,
                original_content=original_content,
                global_outline=self._format_global_outline(global_outline),
                character_profiles=self._format_character_profiles(character_profiles),
                previous_summary=previous_summary or "暂无前文摘要",
                character_state_snapshot=character_state_snapshot,
                series_type=context.extra.get("series_type", "电视剧"),
                script_mode=context.extra.get("script_mode", "real")
            )

            messages = [{"role": "user", "content": formatted_prompt}]

            self.logger.info(f"逻辑修正LLM调用开始 - Task: {context.task_id}")

            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(context.scene_index) if context.scene_index else None
            )

            if not llm_result:
                self.logger.error(f"逻辑修正LLM返回结果为空 - Task: {context.task_id}")
                return None

            llm_content = llm_result.get("content")
            if llm_content is None:
                self.logger.error(f"逻辑修正LLM返回内容为None - Task: {context.task_id}")
                return None

            result = self._parse_correction_response(llm_content)
            return result

        except Exception as e:
            self.logger.error(f"逻辑修正执行失败: {type(e).__name__}: {str(e)}")
            return None

    def _parse_correction_response(self, content: str) -> Optional[Dict[str, Any]]:
        """解析逻辑修正响应"""
        if content is None:
            return None
        if not isinstance(content, str):
            try:
                content = str(content)
            except Exception as e:
                self.logger.debug(f"内容转换字符串失败: {e!r}")
                return None
        content = content.strip()
        if not content:
            return None

        from app.utils.json_parser import parse_json
        result = parse_json(content, default=None)

        if result is not None and isinstance(result, dict):
            self.logger.debug("逻辑修正JSON解析成功")
            return result

        self.logger.warning("无法解析逻辑修正响应，返回原始内容")
        return {
            "corrected_content": content,
            "corrections": [],
            "preservation_notes": "响应解析失败，返回原始内容"
        }
