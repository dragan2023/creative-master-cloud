"""
共享工具模块
保留被其他模块使用的共享组件

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from app.services.proofread.document_formatter import DocumentFormatter
from app.services.proofread.trie_matcher import TrieMatcher, MultiTrieMatcher, MatchResult
from app.services.proofread.checkers.sensitive_checker import SensitiveChecker, SensitiveIssue
from app.services.proofread.chapter_recognizer import (
    ChapterRecognizer, ChapterMatch, count_chapters, recognize_chapters
)

__all__ = [
    "DocumentFormatter",
    "TrieMatcher",
    "MultiTrieMatcher",
    "MatchResult",
    "SensitiveChecker",
    "SensitiveIssue",
    "ChapterRecognizer",
    "ChapterMatch",
    "count_chapters",
    "recognize_chapters",
]
