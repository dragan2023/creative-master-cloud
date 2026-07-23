"""写作任务状态迁移与事件派发的统一入口。"""
from typing import Optional

from app.models.writing_task import TaskStatus, WritingTask


async def transition_task(
    task: WritingTask,
    new_status: TaskStatus,
    websocket_manager=None,
    reason: Optional[str] = None,
) -> None:
    """执行一次受状态机校验的迁移，并在可用时派发标准状态事件。"""
    old_status = task.status
    task.transition_to(new_status, reason=reason)

    if websocket_manager is not None:
        await websocket_manager.send_status_change(
            task.id,
            old_status,
            new_status,
        )
