"""
多Agent协作文学作品生成系统 - Orchestrator Agent 包

模块: agents.writing.orchestrator_agent
功能: 导出 OrchestratorAgent 主类

使用说明:
    from app.agents.writing.orchestrator_agent import OrchestratorAgent

架构说明:
    本包将原有的 orchestrator_agent.py 单文件拆分为多个功能模块：
    
    - base.py: OrchestratorAgent 主类定义
    - monitoring.py: 监控和错误处理 Mixin
    - agent_communication.py: Agent间消息传递 Mixin  
    - task_scheduler.py: 任务调度和并发管理 Mixin
    - content_pipeline.py: 内容生成流水线 Mixin

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from .base import OrchestratorAgent

__all__ = ["OrchestratorAgent"]
