# -*- coding: utf-8 -*-
"""
任务流事件 Schema

为所有任务流事件（进度、状态变更、完成、失败）提供固定结构与语义：
    - task_id + sequence 单调递增，前端据此丢弃过期重放事件；
    - retryable 标记该事件对应的错误是否值得重试（来自领域异常语义）。

事件结构固定为：
    {
        "task_id": 42,
        "sequence": 17,
        "type": "task_progress",
        "status": "running",
        "progress": 0.45,
        "message": "正在生成第 3 章",
        "retryable": false
    }
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.core.exceptions import AppException, classify_provider_error


class TaskEvent(BaseModel):
    """统一任务流事件

    所有经 WebSocket / SSE 推送给前端的任务事件都应符合此结构。
    """
    task_id: int = Field(..., description="任务ID", examples=[42])
    sequence: int = Field(..., description="任务内单调递增序号，用于丢弃过期重放事件", examples=[17])
    type: str = Field(..., description="事件类型，如 task_progress / status_change / task_failed", examples=["task_progress"])
    status: Optional[str] = Field(None, description="任务当前状态", examples=["running"])
    old_status: Optional[str] = Field(None, description="状态变更前的任务状态", examples=["pending"])
    progress: Optional[float] = Field(None, description="进度比例 0.0~1.0", examples=[0.45])
    message: Optional[str] = Field(None, description="人类可读的进度或错误消息", examples=["正在生成第 3 章"])
    retryable: bool = Field(False, description="对应错误是否值得重试；非错误事件恒为 False")
    error_code: Optional[str] = Field(None, description="错误事件对应的错误码，非错误事件为空", examples=["PROVIDER_TIMEOUT"])


def build_error_event(task_id: int, sequence: int, exc: Exception) -> TaskEvent:
    """将任意异常归一化为携带明确错误码与 retryable 的失败事件。

    先经 classify_provider_error 把第三方原始异常翻译为领域异常，
    再从领域异常读取错误码与 retryable 语义，避免把裸异常字符串推给前端。

    Args:
        task_id: 任务ID
        sequence: 由事件序列器分配的单调序号
        exc: 原始异常或领域异常

    Returns:
        TaskEvent: type=task_failed 的失败事件
    """
    app_exc: AppException = classify_provider_error(exc)
    return TaskEvent(
        task_id=task_id,
        sequence=sequence,
        type="task_failed",
        status="failed",
        message=app_exc.message,
        retryable=app_exc.retryable,
        error_code=app_exc.error_code.value,
    )
