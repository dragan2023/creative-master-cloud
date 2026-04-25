# -*- coding: utf-8 -*-
"""
NovelProject Repository
实现 NovelProject 模型的数据访问层
"""
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import SQLAlchemyRepository
from app.models.novel_project import NovelProject


class NovelProjectRepository(SQLAlchemyRepository[NovelProject]):
    """NovelProject Repository"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, NovelProject)

    async def get_by_user_id(self, user_id: int, skip: int = 0, limit: int = 100) -> List[NovelProject]:
        """获取用户的项目列表"""
        result = await self.session.execute(
            select(NovelProject)
            .where(NovelProject.user_id == user_id)
            .order_by(NovelProject.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[NovelProject]:
        """按状态获取项目列表"""
        result = await self.session.execute(
            select(NovelProject)
            .where(NovelProject.status == status)
            .order_by(NovelProject.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_project_code(self, project_code: str) -> Optional[NovelProject]:
        """按项目代码查询"""
        result = await self.session.execute(
            select(NovelProject).where(NovelProject.project_code == project_code)
        )
        return result.scalar_one_or_none()
