# -*- coding: utf-8 -*-
"""
Repository 抽象基类
实现依赖倒置：领域层通过 Repository 接口访问数据，而非直接操作数据库
"""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Type, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

ModelType = TypeVar('ModelType')


class BaseRepository(ABC, Generic[ModelType]):
    """Repository 抽象基类
    
    所有 Repository 必须继承此类，实现数据访问抽象层。
    领域层仅依赖此接口，不直接依赖 SQLAlchemy。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def get(self, id: int) -> Optional[ModelType]:
        """根据ID获取实体"""
        ...

    @abstractmethod
    async def list(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """获取实体列表"""
        ...

    @abstractmethod
    async def create(self, entity: ModelType) -> ModelType:
        """创建实体"""
        ...

    @abstractmethod
    async def update(self, id: int, data: Dict[str, Any]) -> Optional[ModelType]:
        """更新实体"""
        ...

    @abstractmethod
    async def delete(self, id: int) -> bool:
        """删除实体"""
        ...


class SQLAlchemyRepository(BaseRepository[ModelType]):
    """SQLAlchemy 实现的 Repository 基类"""

    def __init__(self, session: AsyncSession, model_class: Type[ModelType]):
        super().__init__(session)
        self.model_class = model_class

    async def get(self, id: int) -> Optional[ModelType]:
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()

    async def list(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        result = await self.session.execute(
            select(self.model_class).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, entity: ModelType) -> ModelType:
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def update(self, id: int, data: Dict[str, Any]) -> Optional[ModelType]:
        entity = await self.get(id)
        if not entity:
            return None
        for key, value in data.items():
            setattr(entity, key, value)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def delete(self, id: int) -> bool:
        entity = await self.get(id)
        if not entity:
            return False
        await self.session.delete(entity)
        await self.session.commit()
        return True
