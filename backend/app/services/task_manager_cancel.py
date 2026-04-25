# -*- coding: utf-8 -*-
"""
任务内存取消令牌模块

当 Redis 不可用时，提供基于内存的异步取消令牌。
从 task_manager.py 提取的独立模块。
"""
import asyncio
from typing import Dict, Optional

from app.core.logger import get_logger

logger = get_logger("task_manager")

# 内存取消令牌字典（当 Redis 不可用时使用）
_memory_cancel_tokens: Dict[int, asyncio.Event] = {}


def set_memory_cancel_token(project_id: int) -> asyncio.Event:
    """为项目创建内存取消令牌"""
    event = asyncio.Event()
    _memory_cancel_tokens[project_id] = event
    return event


def get_memory_cancel_token(project_id: int) -> Optional[asyncio.Event]:
    """获取项目的内存取消令牌"""
    return _memory_cancel_tokens.get(project_id)


def clear_memory_cancel_token(project_id: int):
    """清除项目的内存取消令牌"""
    if project_id in _memory_cancel_tokens:
        del _memory_cancel_tokens[project_id]


def trigger_memory_cancel(project_id: int):
    """触发内存取消令牌"""
    token = _memory_cancel_tokens.get(project_id)
    if token:
        token.set()
        logger.info(f"已触发内存取消令牌: project_id={project_id}")


def is_memory_cancelled(project_id: int) -> bool:
    """检查内存取消令牌是否被触发"""
    token = _memory_cancel_tokens.get(project_id)
    return token is not None and token.is_set()


__all__ = [
    "set_memory_cancel_token",
    "get_memory_cancel_token",
    "clear_memory_cancel_token",
    "trigger_memory_cancel",
    "is_memory_cancelled",
]
