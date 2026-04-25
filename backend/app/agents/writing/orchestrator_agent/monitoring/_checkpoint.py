"""
monitoring/_checkpoint.py - 检查点管理 Mixin

包含 MonitoringCheckpointMixin，提供检查点保存和加载方法。

@date: 2026-04-24
@version: v3.0.0
"""
from typing import Any, Optional


class MonitoringCheckpointMixin:
    """检查点管理 Mixin

    提供：
    - _load_checkpoint: 加载任务的最新检查点
    - _save_checkpoint: 保存检查点
    """

    # 由主类提供的属性
    db: Any
    logger: Any

    async def _load_checkpoint(self, task_id: int) -> Optional[Any]:
        """加载任务的最新检查点"""
        from sqlalchemy import select
        from app.models.writing_checkpoint import WritingCheckpoint

        result = await self.db.execute(
            select(WritingCheckpoint).where(
                WritingCheckpoint.task_id == task_id
            ).order_by(WritingCheckpoint.id.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def _save_checkpoint(
        self,
        task_uuid: str,
        last_unit: int,
        last_scene_id: Optional[int],
        operation: str
    ) -> None:
        """保存检查点

        Args:
            task_uuid: 任务UUID
            last_unit: 最后完成的单元序号
            last_scene_id: 最后完成的场景ID
            operation: 最后执行的操作
        """
        from sqlalchemy import select
        from app.models.writing_task import WritingTask
        from app.models.writing_checkpoint import WritingCheckpoint

        result = await self.db.execute(
            select(WritingTask).where(WritingTask.uuid == task_uuid).limit(1)
        )
        task = result.scalar_one_or_none()
        if not task:
            return

        checkpoint = WritingCheckpoint(
            task_id=task.id,
            last_completed_unit=last_unit,
            last_completed_scene_id=last_scene_id,
            last_operation=operation,
            agent_states={}
        )
        self.db.add(checkpoint)
        await self.db.commit()

        self.logger.info(f"检查点已保存: 单元 {last_unit}, 操作 {operation}")
