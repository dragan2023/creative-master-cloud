"""
多Agent协作文学作品生成系统 - Agent间消息传递模块

模块: agents.writing.orchestrator_agent
文件: agent_communication.py
功能: Agent实例管理与获取

注意: 场景拆解模式已废弃，相关的 _call_structural_agent, _call_logic_editor,
_call_style_editor, _call_compliance_agent, _call_assembler_agent 已移除。
系统统一使用整章直接生成模式（direct mode）。

@date: 2026-04-02
@version: v3.1.0 (清理废弃的场景拆解模式)
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Any, Dict, Type

from app.agents.writing.base_agent import AgentRole, BaseWritingAgent


class AgentCommunicationMixin:
    """Agent间消息传递 Mixin
    
    提供：
    - Agent实例获取与缓存
    """
    
    # 这些属性由主类提供，类型提示
    db: Any  # AsyncSession
    _agent_instances: Dict[AgentRole, BaseWritingAgent]
    _stats_interceptor: Any  # StatsInterceptor
    logger: Any
    config: Any  # AgentConfig
    
    def _get_agent(
        self, 
        role: AgentRole, 
        agent_class: Type[BaseWritingAgent],
        **kwargs
    ) -> BaseWritingAgent:
        """获取或创建子Agent实例（惰性创建）

        Args:
            role: Agent角色
            agent_class: Agent类
            **kwargs: 传递给Agent构造函数的额外参数

        Returns:
            Agent实例
        """
        if role not in self._agent_instances:
            agent = agent_class(config=self.config, **kwargs)
            if self._stats_interceptor:
                agent.set_stats_interceptor(self._stats_interceptor)
            self._agent_instances[role] = agent
        return self._agent_instances[role]
