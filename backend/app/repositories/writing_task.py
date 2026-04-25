# -*- coding: utf-8 -*-
"""
WritingTask Repository
实现 WritingTask 模型的数据访问层
"""
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import SQLAlchemyRepository
from app.models.writing_task import WritingTask


class WritingTaskRepository(SQLAlchemyRepository[WritingTask]):
    """WritingTask Repository"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, WritingTask)

    async def get_by_project_id(self, project_id: int) -> List[WritingTask]:
        """按项目ID获取所有任务"""
        result = await self.session.execute(
            select(WritingTask)
            .where(WritingTask.project_id == project_id)
            .order_by(WritingTask.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_user_id(self, user_id: int, skip: int = 0, limit: int = 100) -> List[WritingTask]:
        """按用户ID获取任务列表"""
        result = await self.session.execute(
            select(WritingTask)
            .where(WritingTask.user_id == user_id)
            .order_by(WritingTask.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> List[WritingTask]:
        """按状态获取任务列表"""
        result = await self.session.execute(
            select(WritingTask).where(WritingTask.status == status)
        )
        return list(result.scalars().all())

    async def get_by_uuid(self, uuid: str) -> Optional[WritingTask]:
        """按UUID查询任务"""
        result = await self.session.execute(
            select(WritingTask).where(WritingTask.uuid == uuid)
        )
        return result.scalar_one_or_none()

    async def get_running_tasks(self) -> List[WritingTask]:
        """获取所有运行中的任务"""
        result = await self.session.execute(
            select(WritingTask).where(WritingTask.status == "running")
        )
        return list(result.scalars().all())
