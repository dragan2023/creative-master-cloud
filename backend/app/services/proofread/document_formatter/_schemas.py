"""Document Formatter Schema"""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

class FormattingStats:
    """格式化统计信息"""
    original_lines: int = 0
    formatted_lines: int = 0
    original_chapters: int = 0
    formatted_chapters: int = 0
    duplicate_titles_removed: int = 0
    noise_content_removed: int = 0
    titles_normalized: int = 0
    encoding_fixes: int = 0
    markdown_headers_processed: int = 0
    steps_completed: List[str] = field(default_factory=list)

