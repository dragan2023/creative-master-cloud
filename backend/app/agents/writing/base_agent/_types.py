"""
Agent基类 - 类型定义模块

包含 AgentRole 枚举、AgentContext 和 AgentResult 数据类。

@date: 2026-04-24
@version: v1.0.0
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import enum


class AgentRole(str, enum.Enum):
    """Agent角色枚举

    定义多Agent协作系统中的角色类型，每个角色有特定的职责。
    """
    ORCHESTRATOR = "orchestrator"
    STRUCTURAL = "structural"
    WRITER = "writer"
    LOGIC_EDITOR = "logic_editor"
    STYLE_EDITOR = "style_editor"
    COMPLIANCE = "compliance"
    KNOWLEDGE = "knowledge"
    ASSEMBLER = "assembler"


@dataclass
class AgentContext:
    """Agent执行上下文 - Agent间通信标准数据结构"""
    task_id: str
    unit_index: int
    scene_index: Optional[int] = None
    project_id: int = 0
    user_id: int = 0

    outline: Dict[str, Any] = field(default_factory=dict)
    previous_content: str = ""
    global_context: str = ""
    character_profiles: List[Dict[str, Any]] = field(default_factory=list)
    world_settings: Dict[str, Any] = field(default_factory=dict)
    style_guide: Dict[str, Any] = field(default_factory=dict)

    character_state_snapshot: str = ""
    character_state_evolution: Dict[str, str] = field(default_factory=dict)
    relationship_summary: str = ""
    character_states: Dict[str, Any] = field(default_factory=dict)
    previous_chapter_characters: List[str] = field(default_factory=list)
    character_location_map: Dict[str, str] = field(default_factory=dict)
    character_identity_map: Dict[str, str] = field(default_factory=dict)
    active_characters: List[str] = field(default_factory=list)
    new_characters_detected: List[Dict[str, Any]] = field(default_factory=list)

    config: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Agent执行结果 - 标准返回结构"""
    success: bool
    agent_role: AgentRole
    content: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    token_usage: Dict[str, int] = field(default_factory=lambda: {
        "input_tokens": 0, "output_tokens": 0, "total_tokens": 0
    })
    duration_ms: int = 0
    model_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
