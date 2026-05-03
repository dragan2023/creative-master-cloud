"""
Agent基类 - 执行和结果构建模块

包含辅助方法如构建系统提示词、错误/成功结果。

@date: 2026-04-24
@version: v1.0.0
"""
from typing import Any, Dict, Optional

from ._types import AgentResult


class AgentExecutionMixin:
    """Agent执行辅助 Mixin"""

    def _build_system_prompt(self, role_description: str, additional_instructions: str = "") -> str:
        """构建系统提示词"""
        base_prompt = f"""# 角色定义

你是【{self.agent_name}】，一个专业的{role_description}。

## 核心职责

{role_description}

## 工作原则

1. 专业性：始终保持高质量、专业化的输出
2. 一致性：确保内容与上下文保持一致
3. 创意性：在保证质量的前提下，发挥创意
4. 准确性：确保所有信息的准确性和合理性

"""

        if additional_instructions:
            base_prompt += f"""## 特别指令

{additional_instructions}

"""

        return base_prompt

    def _build_error_result(self, error_message: str, **kwargs) -> AgentResult:
        """构建错误结果"""
        return AgentResult(
            success=False,
            agent_role=self.agent_role,
            content="",
            errors=[error_message],
            data=kwargs
        )

    def _build_success_result(
        self, content: str, token_usage: Dict[str, int] = None,
        duration_ms: int = 0, model_id: str = "", **kwargs
    ) -> AgentResult:
        """构建成功结果"""
        return AgentResult(
            success=True,
            agent_role=self.agent_role,
            content=content,
            token_usage=token_usage or {
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            duration_ms=duration_ms,
            model_id=model_id,
            data=kwargs
        )
