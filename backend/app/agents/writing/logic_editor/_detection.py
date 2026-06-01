"""
逻辑编辑Agent - 逻辑检测 Mixin

@date: 2026-04-24
@version: v1.0.0
"""
from typing import Any, Dict, List, Optional

from app.agents.writing.base_agent import AgentContext
from app.agents.writing.prompts.character_state_prompts import get_logic_detection_prompt


class LogicDetectionMixin:
    """逻辑检测 Mixin"""

    def _should_correct(self, issues: List[Dict]) -> bool:
        """判断是否需要进行修正"""
        severity_order = {"high": 3, "medium": 2, "low": 1}
        min_level = severity_order.get(self.min_severity_for_correction, 2)

        for issue in issues:
            issue_severity = issue.get("severity", "low")
            issue_level = severity_order.get(issue_severity, 1)
            if issue_level >= min_level:
                return True

        return False

    async def _detect_logic_issues(
        self,
        content: str,
        content_type: str,
        character_profiles: List[Dict],
        global_outline: Dict,
        previous_summary: str,
        character_state_snapshot: str,
        context: AgentContext,
        extended_context: Dict[str, str] = None
    ) -> Optional[Dict[str, Any]]:
        """检测逻辑问题"""
        try:
            # 🔴 防御：安全提取 extra（defense-in-depth，__post_init__ 已标准化但保留二次守卫）
            _ext = context.extra if isinstance(context.extra, dict) else {}

            detection_prompt = get_logic_detection_prompt(content_type)

            extended_context_prompt = ""
            if extended_context:
                extended_parts = []
                for key, value in extended_context.items():
                    if value and isinstance(value, str) and value.strip():
                        extended_parts.append(value)
                if extended_parts:
                    extended_context_prompt = "\n\n# 扩展实体一致性参考（重要）\n\n" + "\n\n".join(extended_parts)
                    extended_context_prompt += "\n\n**请确保内容与上述扩展实体状态保持一致。如有冲突，请在issues中指出。**"

            formatted_prompt = detection_prompt.format(
                content=content,
                global_outline=self._format_global_outline(global_outline),
                character_profiles=self._format_character_profiles(character_profiles),
                previous_summary=previous_summary or "暂无前文摘要",
                character_state_snapshot=character_state_snapshot,
                series_type=_ext.get("series_type", "电视剧"),
                script_mode=_ext.get("script_mode", "real"),
                extended_context=extended_context_prompt
            )

            messages = [{"role": "user", "content": formatted_prompt}]

            self.logger.info(f"逻辑检测LLM调用开始 - Task: {context.task_id}")

            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(context.scene_index) if context.scene_index else None
            )

            if not llm_result:
                self.logger.error(f"逻辑检测LLM返回结果为空 - Task: {context.task_id}")
                return None

            llm_content = llm_result.get("content")
            if llm_content is None:
                self.logger.error(f"逻辑检测LLM返回内容为None - Task: {context.task_id}")
                return None

            result = self._parse_detection_response(llm_content)

            if result:
                result["token_usage"] = {
                    "input_tokens": llm_result.get("input_tokens", 0),
                    "output_tokens": llm_result.get("output_tokens", 0),
                    "total_tokens": llm_result.get("total_tokens", 0)
                }
                result["model_id"] = llm_result.get("model", "")

            return result

        except Exception as e:
            self.logger.error(f"逻辑检测执行失败: {type(e).__name__}: {str(e)}")
            return None

    def _parse_detection_response(self, content: str) -> Optional[Dict[str, Any]]:
        """解析逻辑检测响应"""
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
            self.logger.debug("逻辑检测JSON解析成功")
            return result

        self.logger.warning("无法解析逻辑检测响应")
        return {
            "has_issues": False,
            "issues": [],
            "overall_score": 50,
            "summary": "响应解析失败"
        }
