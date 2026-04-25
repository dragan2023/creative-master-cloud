"""
大纲生成器包

两阶段大纲生成的核心逻辑：
- 第一阶段：生成详细的全局大纲（支持知识库修正）
- 第二阶段：基于全局大纲生成各单元的简要概述

此包替代原 outline_generator.py 单文件，保持完全向后兼容。

使用方式不变：
    from app.services.outline_generator import OutlineGenerator, get_outline_generator
"""
from app.services.outline_generator.impl import OutlineGenerator
from app.services.outline_generator.impl.generator import get_outline_generator
from app.services.outline_generator.api import (
    OutlineGeneratorProtocol,
    ENABLE_QUALITY_CONTROL,
    MIN_REVISION_LENGTH,
    OUTLINE_REVISION_PROMPT,
    LOGIC_CHECK_PROMPT,
)

__all__ = [
    "OutlineGenerator",
    "OutlineGeneratorProtocol",
    "get_outline_generator",
    "ENABLE_QUALITY_CONTROL",
    "MIN_REVISION_LENGTH",
    "OUTLINE_REVISION_PROMPT",
    "LOGIC_CHECK_PROMPT",
]
