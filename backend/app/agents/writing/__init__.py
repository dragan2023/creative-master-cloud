"""
多Agent协作文学作品生成系统 - 模块入口

模块: agents.writing
文件: __init__.py
功能: 导出写作Agent框架的公共接口，包括基类、配置、上下文和统计拦截器

依赖关系:
    - 依赖: base_agent.py, agent_config.py, stats_interceptor.py
    - 被依赖: 具体的写作Agent实现（写手、编辑等）

使用说明:
    from app.agents.writing import (
        BaseWritingAgent,
        AgentContext,
        AgentResult,
        AgentRole,
        AgentConfig,
        AgentModelConfig,
        StatsInterceptor,
        OrchestratorAgent,
        WriterAgent,
        KnowledgeAgent,
        AssemblerAgent,
    )

创建时间: 2026-03-27
最后修改: 2026-05-09

@date: 2026-04-02
@version: v3.1.0 (移除废弃的 StructuralAgent)
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""

from app.agents.writing.base_agent import (
    BaseWritingAgent,
    AgentContext,
    AgentResult,
    AgentRole,
)
from app.agents.writing.agent_config import (
    AgentConfig,
    AgentModelConfig,
)
from app.agents.writing.stats_interceptor import StatsInterceptor

# 核心Agent
from app.agents.writing.orchestrator_agent import OrchestratorAgent
from app.agents.writing.writer_agent import WriterAgent
from app.agents.writing.knowledge_agent import KnowledgeAgent
from app.agents.writing.assembler_agent import AssemblerAgent

# 编辑Agent
from app.agents.writing.logic_editor import LogicEditorAgent
from app.agents.writing.style_editor import StyleEditorAgent
from app.agents.writing.compliance_agent import ComplianceAgent

__all__ = [
    # 基类和数据结构
    "BaseWritingAgent",
    "AgentContext",
    "AgentResult",
    "AgentRole",
    # 配置管理
    "AgentConfig",
    "AgentModelConfig",
    # 统计拦截器
    "StatsInterceptor",
    # 核心Agent
    "OrchestratorAgent",
    "WriterAgent",
    "KnowledgeAgent",
    "AssemblerAgent",
    # 编辑Agent
    "LogicEditorAgent",
    "StyleEditorAgent",
    "ComplianceAgent",
]
