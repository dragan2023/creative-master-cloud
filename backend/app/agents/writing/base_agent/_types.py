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
    """Agent执行上下文 - Agent间通信标准数据结构

    🔴 类型安全保证：
    - __post_init__ 自动对 config/extra/style_guide 调用 safe_json_dict 标准化
    - 确保下游所有 .get() 调用永不因字符串类型而崩溃
    - 标准化是幂等的（已是 dict 时原样返回，零开销）
    """
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

    def __post_init__(self):
        """🔴 源头根治：自动标准化 config/extra/style_guide 为安全 dict

        解决问题：SQLAlchemy JSON 列可能返回字符串、知识图谱返回非 dict 值等场景下，
        下游 .get() 调用因字符串无 .get() 方法而崩溃（AttributeError）。

        标准化策略：
        - 已是 dict → 原样返回（零开销）
        - JSON 字符串 → 自动解析为 dict
        - 非 JSON 字符串 → 包装为 {"_raw_text": value} 降级嵌入
        - None → 返回 {}

        此方法在每次 AgentContext 实例化时自动调用，确保所有 Agent 收到的
        config/extra/style_guide 永远是安全的 dict 类型。
        """
        from app.utils.type_adapter import safe_json_dict

        self.config = safe_json_dict(self.config, "AgentContext.config")
        self.extra = safe_json_dict(self.extra, "AgentContext.extra")
        self.style_guide = safe_json_dict(self.style_guide, "AgentContext.style_guide")


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
