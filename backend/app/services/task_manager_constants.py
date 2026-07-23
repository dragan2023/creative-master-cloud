# -*- coding: utf-8 -*-
"""
批量生成任务常量定义

从 task_manager.py 提取的任务状态和任务类型常量。
同时定义任务状态机的唯一合法迁移表，作为全局唯一事实来源。
"""
from typing import Optional
from datetime import datetime

from app.core.exceptions import InvalidTaskTransitionException

# 任务状态常量
TASK_STATUS_PENDING = "pending"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_CANCELLING = "cancelling"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_CANCELLED = "cancelled"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_INTERRUPTED = "interrupted"

# 任务类型常量
TASK_TYPE_EPISODE_OUTLINE = "episode_outline"      # 分集大纲
TASK_TYPE_CHAPTER_OUTLINE = "chapter_outline"      # 章节大纲
TASK_TYPE_SCENE_OUTLINE = "scene_outline"          # 场景大纲
TASK_TYPE_EPISODE_CONTENT = "episode_content"      # 分集正文
TASK_TYPE_CHAPTER_CONTENT = "chapter_content"      # 章节正文
TASK_TYPE_SCENE_CONTENT = "scene_content"          # 场景正文

# ==================== 任务状态机（单一事实来源） ====================
# 终态：不允许再迁出的状态
TERMINAL_TASK_STATUSES = frozenset({
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_INTERRUPTED,
})

# 允许的状态迁移表：key 为源状态，value 为允许迁入的目标状态集合。
# 终态不出现在 key 中，等价于空集合（禁止任何再迁移）。
# 说明：pending≈queued（保留既有 DB 字符串含义，不引入新 queued 值）。
ALLOWED_TASK_TRANSITIONS = {
    TASK_STATUS_PENDING: frozenset({
        TASK_STATUS_RUNNING, TASK_STATUS_CANCELLED, TASK_STATUS_FAILED,
        TASK_STATUS_INTERRUPTED,
    }),
    TASK_STATUS_RUNNING: frozenset({
        TASK_STATUS_CANCELLING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED,
        TASK_STATUS_INTERRUPTED, TASK_STATUS_CANCELLED,
    }),
    TASK_STATUS_CANCELLING: frozenset({
        TASK_STATUS_CANCELLED, TASK_STATUS_FAILED, TASK_STATUS_INTERRUPTED,
    }),
    # 以下迁移表示在同一任务记录上开始新一轮执行：恢复、重试或继续生成。
    # 它们必须先回到 pending，再由执行器推进到 running，避免绕过状态机。
    TASK_STATUS_INTERRUPTED: frozenset({TASK_STATUS_PENDING}),
    TASK_STATUS_FAILED: frozenset({TASK_STATUS_PENDING}),
    TASK_STATUS_COMPLETED: frozenset({TASK_STATUS_PENDING}),
}


def normalize_task_status(status) -> Optional[str]:
    """将枚举或字符串统一转为小写状态字符串，None 原样返回"""
    if status is None:
        return None
    value = getattr(status, "value", status)
    return str(value)


def is_terminal_task_status(status) -> bool:
    """判断给定状态是否为终态"""
    return normalize_task_status(status) in TERMINAL_TASK_STATUSES


def is_task_transition_allowed(from_status, to_status) -> bool:
    """判断从 from_status 到 to_status 的迁移是否合法"""
    normalized_from = normalize_task_status(from_status)
    normalized_to = normalize_task_status(to_status)
    if normalized_from == normalized_to:
        # 幂等的同态写入不算迁移，交由调用方决定是否放行；此处视为非迁移
        return False
    return normalized_to in ALLOWED_TASK_TRANSITIONS.get(normalized_from, frozenset())


def assert_task_transition_allowed(
    from_status,
    to_status,
    reason: Optional[str] = None,
    ended_at: Optional[datetime] = None,
) -> str:
    """校验任务状态迁移合法性，非法则抛出领域异常并保留原状态。

    Args:
        from_status: 当前状态（枚举或字符串）
        to_status: 目标状态（枚举或字符串）
        reason: 迁移原因（用于日志与错误详情）
        ended_at: 终态结束时间（仅用于错误详情记录）

    Returns:
        规范化后的目标状态字符串

    Raises:
        InvalidTaskTransitionException: 目标状态不在允许迁移集合中
    """
    normalized_from = normalize_task_status(from_status)
    normalized_to = normalize_task_status(to_status)

    if not is_task_transition_allowed(normalized_from, normalized_to):
        details = {"reason": reason} if reason else {}
        if ended_at is not None:
            details["ended_at"] = ended_at.isoformat()
        raise InvalidTaskTransitionException(
            from_status=normalized_from,
            to_status=normalized_to,
            details=details or None,
        )
    return normalized_to

__all__ = [
    "TASK_STATUS_PENDING",
    "TASK_STATUS_RUNNING",
    "TASK_STATUS_CANCELLING",
    "TASK_STATUS_COMPLETED",
    "TASK_STATUS_CANCELLED",
    "TASK_STATUS_FAILED",
    "TASK_STATUS_INTERRUPTED",
    "TASK_TYPE_EPISODE_OUTLINE",
    "TASK_TYPE_CHAPTER_OUTLINE",
    "TASK_TYPE_SCENE_OUTLINE",
    "TASK_TYPE_EPISODE_CONTENT",
    "TASK_TYPE_CHAPTER_CONTENT",
    "TASK_TYPE_SCENE_CONTENT",
    "TERMINAL_TASK_STATUSES",
    "ALLOWED_TASK_TRANSITIONS",
    "normalize_task_status",
    "is_terminal_task_status",
    "is_task_transition_allowed",
    "assert_task_transition_allowed",
]
