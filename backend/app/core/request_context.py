"""
请求与任务上下文

使用 contextvars 在异步调用链中透传 request_id / task_id，供日志契约按
request/task 关联。该模块不依赖任何业务组件，避免循环导入。

@date: 2026-07-23
"""
import uuid
from contextvars import ContextVar
from typing import Optional

# 缺省占位符，保证日志字段始终有值，便于结构化检索
UNSET = "-"

_request_id_var: ContextVar[str] = ContextVar("request_id", default=UNSET)
_task_id_var: ContextVar[str] = ContextVar("task_id", default=UNSET)


def new_request_id() -> str:
    """生成一个新的 request_id（无横线的 uuid4，便于日志检索）。"""
    return uuid.uuid4().hex


def set_request_id(request_id: str) -> None:
    """设置当前上下文的 request_id。"""
    _request_id_var.set(request_id or UNSET)


def get_request_id() -> str:
    """获取当前上下文的 request_id，缺省返回占位符。"""
    return _request_id_var.get()


def set_task_id(task_id: Optional[int | str]) -> None:
    """设置当前上下文的 task_id（接受 int 或 str）。"""
    _task_id_var.set(str(task_id) if task_id is not None else UNSET)


def get_task_id() -> str:
    """获取当前上下文的 task_id，缺省返回占位符。"""
    return _task_id_var.get()


def clear_context() -> None:
    """清理上下文，避免协程复用时串号。"""
    _request_id_var.set(UNSET)
    _task_id_var.set(UNSET)
