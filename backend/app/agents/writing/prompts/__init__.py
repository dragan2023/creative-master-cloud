"""
多Agent协作文学作品生成系统 - 提示词模块

模块: agents.writing.prompts
功能: 集中管理所有Agent的提示词模板

包含提示词:
    - STRUCTURAL_PROMPTS: 结构师Agent提示词
    - WRITER_PROMPTS: 写手Agent提示词
    - EDITOR_PROMPTS: 逻辑编辑Agent提示词
    - STYLE_PROMPTS: 风格润色Agent提示词
    - COMPLIANCE_PROMPTS: 合规审查Agent提示词
    - KNOWLEDGE_PROMPTS: 知识顾问Agent提示词
    - ASSEMBLER_PROMPTS: 合成Agent提示词
    - CHARACTER_STATE_PROMPTS: 人物状态追踪提示词
    - VIRTUAL_MODE_PROMPTS: 虚拟模式AIGC提示词模板

创建时间: 2026-03-27
最后修改: 2026-05-06
版本: 2.1.0
作者: AI Assistant
"""

from .structural_prompts import STRUCTURAL_PROMPTS
from .writer_prompts import WRITER_PROMPTS, get_writer_prompts, get_state_dimensions
from .editor_prompts import EDITOR_PROMPTS, get_editor_prompts, get_state_check_dimensions
from .style_prompts import STYLE_PROMPTS
from .compliance_prompts import COMPLIANCE_PROMPTS
from .knowledge_prompts import KNOWLEDGE_PROMPTS
from .assembler_prompts import ASSEMBLER_PROMPTS
from .character_state_prompts import (
    CHARACTER_STATE_PROMPTS,
    NOVEL_STATE_DIMENSIONS,
    SCRIPT_STATE_DIMENSIONS,
    STATE_CHANGE_TYPES,
    VISUAL_PRESENTATION_GUIDE,
    get_writer_system_prompt,
    get_writer_user_prompt,
    get_editor_system_prompt,
    get_editor_user_prompt,
    format_state_change_table
)
from .virtual_mode_prompts import (
    build_virtual_mode_prompt,
    get_image_prompt_templates,
    get_video_prompt_templates,
    get_audio_prompt_templates,
    get_comprehensive_ref_templates,
    VIRTUAL_MODE_FULL_TEMPLATE,
    STORYBOARD_TEMPLATE,
)

__all__ = [
    "STRUCTURAL_PROMPTS",
    "WRITER_PROMPTS",
    "EDITOR_PROMPTS",
    "STYLE_PROMPTS",
    "COMPLIANCE_PROMPTS",
    "KNOWLEDGE_PROMPTS",
    "ASSEMBLER_PROMPTS",
    "CHARACTER_STATE_PROMPTS",
    "NOVEL_STATE_DIMENSIONS",
    "SCRIPT_STATE_DIMENSIONS",
    "STATE_CHANGE_TYPES",
    "VISUAL_PRESENTATION_GUIDE",
    "get_writer_prompts",
    "get_editor_prompts",
    "get_state_dimensions",
    "get_state_check_dimensions",
    "get_writer_system_prompt",
    "get_writer_user_prompt",
    "get_editor_system_prompt",
    "get_editor_user_prompt",
    "format_state_change_table",
    # virtual_mode_prompts
    "build_virtual_mode_prompt",
    "get_image_prompt_templates",
    "get_video_prompt_templates",
    "get_audio_prompt_templates",
    "get_comprehensive_ref_templates",
    "VIRTUAL_MODE_FULL_TEMPLATE",
    "STORYBOARD_TEMPLATE",
]
