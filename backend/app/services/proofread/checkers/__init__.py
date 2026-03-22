"""
共享检查器模块
"""
from app.services.proofread.checkers.sensitive_checker import SensitiveChecker, SensitiveIssue

__all__ = [
    "SensitiveChecker",
    "SensitiveIssue",
]
