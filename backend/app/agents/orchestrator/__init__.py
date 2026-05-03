"""Agent编排器包

协调 LLM、工具和记忆系统完成创意生成任务。
此包替代原 orchestrator.py 单文件，保持完全向后兼容。
"""
from app.agents.orchestrator.impl import AgentOrchestrator
from app.agents.orchestrator.impl.generator import get_agent_orchestrator
from app.agents.orchestrator.api import (
    convert_images_to_base64,
    convert_file_url_to_content,
    extract_input_params_files,
    get_model_friendly_name,
    GenerateStreamContext,
)

__all__ = [
    "AgentOrchestrator", "get_agent_orchestrator",
    "convert_images_to_base64",
    "convert_file_url_to_content",
    "extract_input_params_files",
    "get_model_friendly_name",
    "GenerateStreamContext",
]
