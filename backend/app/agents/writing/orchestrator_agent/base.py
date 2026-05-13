"""
多Agent协作文学作品生成系统 - 总线Agent（Orchestrator）

模块: agents.writing.orchestrator_agent
文件: base.py
功能: 核心调度器，负责任务状态机管理、单元拆解、并发调度和流程编排

依赖关系:
    - 依赖: base_agent.py, agent_config.py, stats_interceptor.py
    - 依赖模型: WritingTask, WritingUnit, WritingScene, WritingCheckpoint
    - 依赖其他Agent: WriterAgent（其他Agent按需通过 _get_agent 惰性创建）
    - 被依赖: API层、任务管理器

使用说明:
    orchestrator = OrchestratorAgent(db=db_session, config=agent_config)
    result = await orchestrator.execute(context)
    
    # 中断任务
    await orchestrator.interrupt()
    
    # 续传任务
    result = await orchestrator.resume(context)

创建时间: 2026-03-27
最后修改: 2026-04-02

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import asyncio
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.writing.base_agent import BaseWritingAgent, AgentContext, AgentResult, AgentRole
from app.agents.writing.agent_config import AgentConfig
from app.agents.writing.stats_interceptor import StatsInterceptor
from app.core.logger import get_logger

# 导入各功能 Mixin
from .monitoring import MonitoringMixin
from .agent_communication import AgentCommunicationMixin
from .task_scheduler import TaskSchedulerMixin
from .content_pipeline import ContentPipelineMixin

# 延迟导入类型，避免循环依赖
if TYPE_CHECKING:
    from app.services.writing_engine.websocket_manager import WebSocketManager
    from app.agents.writing.character_state_tracker import CharacterStateTracker
    from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase


class OrchestratorAgent(
    MonitoringMixin,
    AgentCommunicationMixin,
    TaskSchedulerMixin,
    ContentPipelineMixin,
    BaseWritingAgent
):
    """总线Agent - 多Agent协作系统的核心调度器
    
    职责：
    1. 状态机管理：驱动任务从 pending → running → completed/failed 的完整生命周期
    2. 整章直接生成：对每个Unit使用整章直接生成模式（direct mode），由 WriterAgent 一次性生成完整章节
    3. 并发调度：使用asyncio.Semaphore控制并发写手数量
    4. 中断/续传：支持中断当前任务，从最后检查点续传
    5. 错误处理：单个单元失败不影响其他单元，支持重试

    注意：本Agent为纯调度类Agent，不需要LLM调用。

    架构说明：
    本类通过多重继承组合各功能模块：
    - MonitoringMixin: 中断控制、WebSocket通信、检查点管理、人物状态追踪
    - AgentCommunicationMixin: 各专业Agent的调用封装
    - TaskSchedulerMixin: 任务续传、调度控制
    - ContentPipelineMixin: 核心执行流程、整章直接生成、数据库操作
    """
    
    agent_name = "总线Agent"
    agent_role = AgentRole.ORCHESTRATOR
    default_model = ""  # 不需要模型
    default_temperature = 0.3
    requires_llm = False  # 禁用LLM调用，本Agent为纯调度类
    
    def __init__(self, db: AsyncSession, config: Optional[AgentConfig] = None):
        """初始化总线Agent
        
        Args:
            db: 数据库异步会话
            config: Agent配置对象
        """
        super().__init__(config)
        self.db = db
        self._interrupt_event = asyncio.Event()  # 中断信号
        self._interrupt_event.set()  # 默认非中断状态
        self._semaphore: Optional[asyncio.Semaphore] = None  # 并发控制信号量
        
        # Agent实例缓存（惰性创建）
        self._agent_instances: Dict[AgentRole, BaseWritingAgent] = {}
        
        # 统计拦截器
        self._stats_interceptor: Optional[StatsInterceptor] = None
                
        # WebSocket管理器（用于实时进度推送）
        self._ws_manager: Optional["WebSocketManager"] = None
                
        # 当前任务状态
        self._current_task = None
        self._max_concurrent_writers = 3  # 默认最大并发写手数
        
        # 人物状态追踪器（新增）
        self._character_tracker: Optional["CharacterStateTracker"] = None
        
        # 项目知识库管理器（用于人物状态图谱集成）
        self._project_knowledge_base: Optional["ProjectKnowledgeBase"] = None
    
    def set_stats_interceptor(self, interceptor: StatsInterceptor) -> None:
        """设置统计拦截器并传递给子Agent"""
        super().set_stats_interceptor(interceptor)
        self._stats_interceptor = interceptor
        # 传递给已创建的子Agent
        for agent in self._agent_instances.values():
            agent.set_stats_interceptor(interceptor)
        
    def set_ws_manager(self, ws_manager: "WebSocketManager") -> None:
        """设置WebSocket管理器
            
        Args:
            ws_manager: WebSocket管理器实例
        """
        self._ws_manager = ws_manager
        self.logger.debug("WebSocket管理器已设置")
