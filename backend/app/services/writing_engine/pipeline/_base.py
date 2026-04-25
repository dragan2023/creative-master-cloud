"""
写作流水线 - 基类及生命周期管理

@date: 2026-04-24
@version: v1.0.0
"""
import asyncio
from typing import Dict, Optional, TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.writing_task import WritingTask, TaskStatus
from app.agents.writing.orchestrator_agent import OrchestratorAgent
from app.agents.writing.base_agent import AgentContext, AgentResult
from app.agents.writing.agent_config import AgentConfig

if TYPE_CHECKING:
    from app.services.writing_engine.websocket_manager import WebSocketManager
    from app.agents.writing.stats_interceptor import StatsInterceptor

logger = get_logger("writing_engine.pipeline")


class PipelineBase:
    """写作流水线基类 - 提供基础属性和生命周期管理"""

    # 类变量：存储所有活跃的流水线实例
    _active_pipelines: Dict[int, "PipelineBase"] = {}

    def __init__(
        self,
        task_id: int,
        config: Optional[AgentConfig] = None
    ):
        """初始化写作流水线

        Args:
            task_id: 写作任务ID
            config: Agent配置（可选，使用默认配置）
        """
        self.task_id = task_id
        self.config = config or AgentConfig()

        # 数据库会话（在_execute中动态创建）
        self.db: Optional[AsyncSession] = None

        # 任务对象（在_execute中加载）
        self.task: Optional[WritingTask] = None

        # OrchestratorAgent实例
        self._orchestrator: Optional[OrchestratorAgent] = None

        # WebSocket管理器
        self._ws_manager: Optional["WebSocketManager"] = None

        # 统计拦截器
        self._stats_interceptor: Optional["StatsInterceptor"] = None

        # 执行任务
        self._execution_task: Optional[asyncio.Task] = None

        # 执行结果
        self._result: Optional[AgentResult] = None

    @classmethod
    def get_active_pipeline(cls, task_id: int) -> Optional["PipelineBase"]:
        """获取指定任务的活跃流水线

        Args:
            task_id: 任务ID

        Returns:
            WritingPipeline或None
        """
        return cls._active_pipelines.get(task_id)

    @classmethod
    def remove_active_pipeline(cls, task_id: int) -> None:
        """从活跃列表中移除流水线

        Args:
            task_id: 任务ID
        """
        if task_id in cls._active_pipelines:
            del cls._active_pipelines[task_id]
            logger.info(f"流水线已从活跃列表移除: task_id={task_id}")

    @classmethod
    def get_all_active_pipelines(cls) -> Dict[int, "PipelineBase"]:
        """获取所有活跃流水线"""
        return dict(cls._active_pipelines)

    def set_ws_manager(self, ws_manager: "WebSocketManager") -> None:
        """注入WebSocket管理器

        Args:
            ws_manager: WebSocket管理器实例
        """
        self._ws_manager = ws_manager
        logger.debug(f"WebSocket管理器已设置: task_id={self.task_id}")

    def set_stats_interceptor(self, interceptor: "StatsInterceptor") -> None:
        """注入统计拦截器

        Args:
            interceptor: 统计拦截器实例
        """
        self._stats_interceptor = interceptor
        logger.debug(f"统计拦截器已设置: task_id={self.task_id}")

    async def _notify_status_change(
        self,
        old_status: TaskStatus,
        new_status: TaskStatus
    ) -> None:
        """通知任务状态变更

        Args:
            old_status: 旧状态
            new_status: 新状态
        """
        if self._ws_manager:
            try:
                await self._ws_manager.send_status_change(
                    task_id=self.task.id if self.task else self.task_id,
                    old_status=old_status,
                    new_status=new_status
                )
            except Exception as e:
                logger.error(
                    f"发送状态变更通知失败: task_id={self.task_id}, error={str(e)}")

    async def wait_for_completion(self, timeout: Optional[float] = None) -> Optional[AgentResult]:
        """等待任务完成

        Args:
            timeout: 超时时间（秒），None表示无限等待

        Returns:
            AgentResult或None（超时）
        """
        if not self._execution_task:
            return self._result

        try:
            await asyncio.wait_for(self._execution_task, timeout=timeout)
            return self._result
        except asyncio.TimeoutError:
            logger.warning(
                f"等待任务完成超时: task_id={self.task.id}, timeout={timeout}")
            return None

    @property
    def is_running(self) -> bool:
        """检查流水线是否在运行"""
        return (self.task is not None and
                self.task.status == TaskStatus.RUNNING and
                self._execution_task is not None)

    @property
    def result(self) -> Optional[AgentResult]:
        """获取执行结果"""
        return self._result
