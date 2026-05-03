"""人物状态追踪提示词模板包

包含写手/编辑提示词、状态常量、大纲提示词、逻辑修正提示词
"""

from ._state_constants import (
    NOVEL_STATE_DIMENSIONS,
    SCRIPT_STATE_DIMENSIONS,
    STATE_CHANGE_TYPES,
    VISUAL_PRESENTATION_GUIDE,
)

from ._writer_editor_prompts import (
    CHARACTER_STATE_PROMPTS,
    _is_script_type,
    get_writer_system_prompt,
    get_writer_user_prompt,
    get_editor_system_prompt,
    get_editor_user_prompt,
    format_state_change_table,
)

from ._outline_prompts import (
    CHAPTER_DETAILED_OUTLINE_PROMPTS,
    get_chapter_outline_system_prompt,
    get_chapter_outline_user_prompt,
    format_character_state_trajectory,
)

from ._logic_prompts import (
    LOGIC_CORRECTION_PROMPTS,
    get_logic_detection_prompt,
    get_logic_correction_prompt,
    get_feasibility_checker_prompts,
)

__all__ = [
    "CHARACTER_STATE_PROMPTS",
    "NOVEL_STATE_DIMENSIONS",
    "SCRIPT_STATE_DIMENSIONS",
    "STATE_CHANGE_TYPES",
    "VISUAL_PRESENTATION_GUIDE",
    "CHAPTER_DETAILED_OUTLINE_PROMPTS",
    "LOGIC_CORRECTION_PROMPTS",
    "get_writer_system_prompt",
    "get_writer_user_prompt",
    "get_editor_system_prompt",
    "get_editor_user_prompt",
    "format_state_change_table",
    "get_chapter_outline_system_prompt",
    "get_chapter_outline_user_prompt",
    "format_character_state_trajectory",
    "get_logic_detection_prompt",
    "get_logic_correction_prompt",
    "get_feasibility_checker_prompts",
]
