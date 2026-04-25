"""Agent编排器 - 主类（组合所有Mixin）"""

from app.core.logger import get_logger, LoggerAdapter
from app.core.config import PRESET_MODELS, get_settings
from app.agents.llm_manager import get_llm_manager, LLMManager
from app.agents.memory_manager import get_memory_manager, MemoryManager
from app.agents.prompt_manager import get_prompt_manager, PromptManager
from app.agents.orchestrator.impl.mixins import (
    ContextUtilsMixin,
    GenerationCoreMixin,
    GenerateSyncMixin,
    GenerateStreamMixinMixin,
    KnowledgeRetrievalMixin,
    EvaluationMixin,
    RevisionMixin,
    SessionMixin,
    ReflectionMixin,
)

class AgentOrchestrator(
    ContextUtilsMixin,
    GenerationCoreMixin,
    GenerateSyncMixin,
    GenerateStreamMixinMixin,
    KnowledgeRetrievalMixin,
    EvaluationMixin,
    RevisionMixin,
    SessionMixin,
    ReflectionMixin,
):
    """Agent编排器 - 组合Mixin实现"""

    def __init__(
        self,
        llm_manager=None,
        memory_manager=None,
        prompt_manager=None,
        web_search=None,
        knowledge_retrieval=None,
        webpage_reader=None,
        mcp_client=None,
        logger=None,
    ):
        """初始化编排器，支持依赖注入（便于测试Mock）

        所有参数可选，不传时使用默认工厂函数创建实例。
        """
        self.llm_manager = llm_manager or get_llm_manager()
        self.memory_manager = memory_manager or get_memory_manager()
        self.prompt_manager = prompt_manager or get_prompt_manager()
        self.web_search = web_search or get_web_search_tool()
        self.knowledge_retrieval = knowledge_retrieval or get_knowledge_retrieval_tool()
        self.webpage_reader = webpage_reader or get_webpage_reader()
        self.mcp_client = mcp_client or get_mcp_client()
        self.logger = logger or get_logger("orchestrator")


# 全局实例
_orchestrator = None


def get_agent_orchestrator() -> "AgentOrchestrator":
    """获取Agent编排器实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
