"""大纲生成器 - API层"""
from app.services.outline_generator.api.interfaces import OutlineGeneratorProtocol
from app.services.outline_generator.api.constants import (
    ENABLE_QUALITY_CONTROL,
    MIN_REVISION_LENGTH,
    OUTLINE_REVISION_PROMPT,
    LOGIC_CHECK_PROMPT,
)

__all__ = [
    "OutlineGeneratorProtocol",
    "ENABLE_QUALITY_CONTROL",
    "MIN_REVISION_LENGTH",
    "OUTLINE_REVISION_PROMPT",
    "LOGIC_CHECK_PROMPT",
]
