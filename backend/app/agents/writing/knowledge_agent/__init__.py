"""
多Agent协作文学作品生成系统 - 知识顾问Agent 包入口

将原 knowledge_agent.py 拆分为多个功能模块，通过 Mixin 多重继承组合。

包结构:
    __init__.py: KnowledgeAgent 主类，继承自子 Mixin
    _adapters.py: 适配器类 (ContextManagerAdapter, KnowledgeBaseAdapter)
    _knowledge_mixin.py: 知识检索和上下文构建方法 (KnowledgeExecutionMixin)

@date: 2026-04-24
@version: v2.0.0
"""

from typing import Optional

from app.agents.writing.base_agent import (
    BaseWritingAgent,
    AgentRole
)
from ._adapters import ContextManagerAdapter, KnowledgeBaseAdapter
from ._knowledge_mixin import KnowledgeExecutionMixin


class KnowledgeAgent(BaseWritingAgent, KnowledgeExecutionMixin):
    """知识顾问Agent - 上下文知识检索专家

    为其他Agent提供上下文知识检索和一致性参考，确保创作内容的连贯性和准确性。

    主要职责：
    1. 从向量存储检索相关内容片段
    2. 从知识图谱检索角色关系、事件线索
    3. 整合为结构化的上下文信息
    4. 提供一致性检查参考

    特点：
    - 使用较低温度(0.3)确保知识准确
    - 通过适配器模式松耦合引用旧模块
    - 支持多种知识类型检索
    """

    agent_name = "知识顾问Agent"
    agent_role = AgentRole.KNOWLEDGE
    default_model = ""
    default_temperature = 0.3

    def __init__(self, config=None):
        """初始化知识顾问Agent

        Args:
            config: Agent配置
        """
        super().__init__(config)
        self._context_adapter: Optional[ContextManagerAdapter] = None
        self._kb_adapter: Optional[KnowledgeBaseAdapter] = None

    @property
    def context_adapter(self) -> ContextManagerAdapter:
        """获取上下文适配器（懒加载）"""
        if self._context_adapter is None:
            self._context_adapter = ContextManagerAdapter()
        return self._context_adapter

    @property
    def kb_adapter(self) -> KnowledgeBaseAdapter:
        """获取知识库适配器（懒加载）"""
        if self._kb_adapter is None:
            self._kb_adapter = KnowledgeBaseAdapter()
        return self._kb_adapter
