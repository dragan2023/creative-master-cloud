"""
生成记录服务模块

封装生成记录的CRUD操作，提供统一的数据访问接口。

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from app.models.generation import Generation, GenerationModule, GenerationStatus
from app.core.logger import get_logger

logger = get_logger("generation_service")


class GenerationService:
    """生成记录服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def save_generation(
        self,
        user_id: int,
        module: GenerationModule,
        input_params: dict,
        title: str,
        output_content: str,
        provider: str = None,
        model_name: str = None,
        token_count: int = 0,
        duration_ms: int = 0,
        status: GenerationStatus = GenerationStatus.COMPLETED,
    ) -> Generation:
        """保存生成记录"""
        generation = Generation(
            user_id=user_id,
            module=module,
            status=status,
            input_params=input_params,
            title=title,
            output_content=output_content,
            provider=provider,
            model_name=model_name,
            token_count=token_count,
            duration_ms=duration_ms,
        )
        self.db.add(generation)
        await self.db.commit()
        await self.db.refresh(generation)
        logger.info(f"保存生成记录: id={generation.id}, module={module}, user_id={user_id}")
        return generation
    
    async def get_generation_by_id(self, generation_id: int) -> Optional[Generation]:
        """根据ID获取生成记录"""
        stmt = select(Generation).where(Generation.id == generation_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_generations(
        self,
        user_id: int,
        module: Optional[GenerationModule] = None,
        skip: int = 0,
        limit: int = 10,
    ) -> List[Generation]:
        """获取用户生成历史"""
        stmt = select(Generation).where(Generation.user_id == user_id)
        if module:
            stmt = stmt.where(Generation.module == module)
        stmt = stmt.order_by(Generation.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def count_user_generations(
        self,
        user_id: int,
        module: Optional[GenerationModule] = None,
    ) -> int:
        """统计用户生成记录数"""
        stmt = select(func.count(Generation.id)).where(Generation.user_id == user_id)
        if module:
            stmt = stmt.where(Generation.module == module)
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def delete_generation(self, generation_id: int) -> bool:
        """删除生成记录"""
        generation = await self.get_generation_by_id(generation_id)
        if not generation:
            return False
        if not generation.can_delete():
            logger.warning(f"尝试删除不可删除的生成记录: id={generation_id}, status={generation.status}")
            return False
        await self.db.delete(generation)
        await self.db.commit()
        logger.info(f"删除生成记录: id={generation_id}")
        return True
