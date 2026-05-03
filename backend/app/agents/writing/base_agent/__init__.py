"""
Agent基类 包入口

将原 base_agent.py 拆分为多个功能模块，通过 Mixin 多重继承组合。

包结构:
    __init__.py: 统一导出 BaseWritingAgent（从子 Mixin 组合）
    _types.py: AgentRole, AgentContext, AgentResult 类型定义
    _llm.py: LLM调用相关方法 (call_llm, call_llm_stream)
    _execution.py: 辅助方法 (_build_system_prompt, _build_error_result, _build_success_result)

@date: 2026-04-24
@version: v2.0.0
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.writing.agent_config import AgentConfig
    from app.agents.writing.stats_interceptor import StatsInterceptor

from app.core.logger import get_logger
from ._types import AgentRole, AgentContext, AgentResult
from ._llm import AgentLLMMixin
from ._execution import AgentExecutionMixin


class BaseWritingAgent(ABC, AgentLLMMixin, AgentExecutionMixin):
    """Agent抽象基类 - 所有写作Agent的父类

    定义了写作Agent的基本接口和行为，包括：
    - LLM调用封装
    - 日志记录
    - 统计拦截
    - 系统提示词构建
    - LLM调用权限控制

    子类需要实现：
    - agent_name: Agent名称
    - agent_role: Agent角色
    - default_model: 默认模型
    - default_temperature: 默认温度
    - execute(): 核心执行逻辑
    """

    agent_name: str = "base_agent"
    agent_role: AgentRole = AgentRole.WRITER
    default_model: str = ""
    default_temperature: float = 0.7
    requires_llm: bool = True

    def __init__(self, config: Optional['AgentConfig'] = None):
        """初始化Agent"""
        self.config = config
        self.logger = get_logger(f"agent.{self.agent_role.value}")
        self._stats_interceptor: Optional['StatsInterceptor'] = None
        self._llm_manager: Optional[Any] = None
        self._provider: Optional[Any] = None

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行Agent任务 - 子类必须实现"""
        pass

    def set_stats_interceptor(self, interceptor: 'StatsInterceptor') -> None:
        """注入统计拦截器"""
        self._stats_interceptor = interceptor


__all__ = [
    "BaseWritingAgent",
    "AgentRole",
    "AgentContext",
    "AgentResult",
]
