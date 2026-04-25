"""
Agent 引擎模块

模块: agents
文件: __init__.py
功能: 导出Agent引擎的公共接口，包括LLM提供商、管理器和协调器

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from app.agents.base_provider import BaseLLMProvider, LLMResponse, LLMProvider
from app.agents.deepseek_provider import DeepSeekProvider
from app.agents.openai_provider import OpenAIProvider
from app.agents.qianwen_provider import QianwenProvider
from app.agents.google_provider import GoogleProvider
from app.agents.doubao_provider import DoubaoProvider
from app.agents.llm_manager import LLMManager, get_llm_manager, llm_manager
from app.agents.memory_manager import MemoryManager, get_memory_manager, memory_manager
from app.agents.prompt_manager import PromptManager, get_prompt_manager, prompt_manager
from app.agents.orchestrator import AgentOrchestrator, get_agent_orchestrator

__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "LLMProvider",
    "DeepSeekProvider",
    "OpenAIProvider",
    "QianwenProvider",
    "GoogleProvider",
    "DoubaoProvider",
    "LLMManager",
    "get_llm_manager",
    "llm_manager",
    "MemoryManager",
    "get_memory_manager",
    "memory_manager",
    "PromptManager",
    "get_prompt_manager",
    "prompt_manager",
    "AgentOrchestrator",
    "get_agent_orchestrator",
]
