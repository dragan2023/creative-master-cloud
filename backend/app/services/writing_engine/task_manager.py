"""
多Agent协作文学作品生成系统 - 任务管理服务

模块: services.writing_engine
文件: task_manager.py
功能: 写作任务的CRUD服务，管理任务生命周期和关联数据查询

依赖关系:
    - 依赖: app.core.database, app.models.writing_task, app.models.writing_unit, 
            app.models.writing_scene, app.models.writing_stat
    - 被依赖: WritingPipeline, API层

创建时间: 2026-03-27
最后修改: 2026-03-27
版本: 1.0.0
作者: AI Assistant
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.writing_task import WritingTask, TaskStatus
from app.models.writing_unit import WritingUnit, UnitStatus
from app.models.writing_scene import WritingScene, SceneStatus
from app.models.writing_stat import WritingStat


logger = get_logger("writing_engine.task_manager")


class TaskManager:
    """任务管理服务 - 提供写作任务的CRUD操作
    
    负责管理WritingTask、WritingUnit、WritingScene和WritingStat的数据访问，
    不包含业务逻辑（业务逻辑由WritingPipeline处理）。
    """
    
    def __init__(self, db: AsyncSession):
        """初始化任务管理器
        
        Args:
            db: 数据库异步会话
        """
        self.db = db
    
    async def create_task(
        self,
        project_id: int,
        user_id: int,
        config: Dict[str, Any]
    ) -> WritingTask:
        """创建新的写作任务
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
            config: 任务配置（包含total_units、start_from、unit_count等）
            
        Returns:
            WritingTask: 新创建的任务对象
        """
        task = WritingTask(
            uuid=str(uuid4()),
            project_id=project_id,
            user_id=user_id,
            status=TaskStatus.PENDING,
            total_units=config.get("total_units", 1),
            completed_units=0,
            config=config,
            start_from=config.get("start_from", 1),
            unit_count=config.get("unit_count"),
            total_tokens=0,
            total_cost=0.0
        )
        
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        
        logger.info(f"创建写作任务: id={task.id}, uuid={task.uuid}, project_id={project_id}")
        return task
    
    async def get_task(self, task_id: int, user_id: int) -> Optional[WritingTask]:
        """根据任务ID获取任务
        
        Args:
            task_id: 任务ID
            user_id: 用户ID（用于权限校验）
            
        Returns:
            WritingTask或None
        """
        result = await self.db.execute(
            select(WritingTask).where(
                and_(
                    WritingTask.id == task_id,
                    WritingTask.user_id == user_id
                )
            ).limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_task_by_uuid(self, uuid: str, user_id: int) -> Optional[WritingTask]:
        """根据任务UUID获取任务
        
        Args:
            uuid: 任务UUID
            user_id: 用户ID（用于权限校验）
            
        Returns:
            WritingTask或None
        """
        result = await self.db.execute(
            select(WritingTask).where(
                and_(
                    WritingTask.uuid == uuid,
                    WritingTask.user_id == user_id
                )
            ).limit(1)
        )
        return result.scalar_one_or_none()
    
    async def list_tasks(
        self,
        user_id: int,
        project_id: Optional[int] = None,
        status: Optional[TaskStatus] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[WritingTask]:
        """获取任务列表
        
        Args:
            user_id: 用户ID
            project_id: 项目ID（可选，用于过滤）
            status: 任务状态（可选，用于过滤）
            skip: 跳过记录数
            limit: 返回记录数
            
        Returns:
            List[WritingTask]: 任务列表
        """
        conditions = [WritingTask.user_id == user_id]
        
        if project_id is not None:
            conditions.append(WritingTask.project_id == project_id)
        
        if status is not None:
            conditions.append(WritingTask.status == status)
        
        query = (
            select(WritingTask)
            .where(and_(*conditions))
            .order_by(WritingTask.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_task_status(
        self,
        task_id: int,
        status: TaskStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            error_message: 错误信息（可选，失败时记录）
            
        Returns:
            bool: 是否更新成功
        """
        try:
            task = await self.db.get(WritingTask, task_id)
            if not task:
                logger.warning(f"任务不存在: task_id={task_id}")
                return False
            
            old_status = task.status
            task.status = status
            
            if error_message:
                task.error_message = error_message
            
            if status == TaskStatus.RUNNING and not task.start_time:
                task.start_time = datetime.now()
            
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.end_time = datetime.now()
            
            await self.db.commit()
            
            logger.info(f"任务状态更新: task_id={task_id}, {old_status.value} -> {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"更新任务状态失败: task_id={task_id}, error={str(e)}")
            await self.db.rollback()
            return False
    
    async def get_task_units(self, task_id: int) -> List[WritingUnit]:
        """获取任务的所有单元
        
        Args:
            task_id: 任务ID
            
        Returns:
            List[WritingUnit]: 单元列表
        """
        result = await self.db.execute(
            select(WritingUnit)
            .where(WritingUnit.task_id == task_id)
            .order_by(WritingUnit.unit_index)
        )
        return list(result.scalars().all())
    
    async def get_unit_scenes(self, unit_id: int) -> List[WritingScene]:
        """获取单元的所有场景
        
        Args:
            unit_id: 单元ID
            
        Returns:
            List[WritingScene]: 场景列表
        """
        result = await self.db.execute(
            select(WritingScene)
            .where(WritingScene.unit_id == unit_id)
            .order_by(WritingScene.scene_index)
        )
        return list(result.scalars().all())
    
    async def get_task_stats(self, task_id: int) -> Dict[str, Any]:
        """获取任务的统计信息（按agent_name分组聚合）
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 统计信息，格式为 {agent_name: {total_tokens, total_duration, call_count, ...}}
        """
        # 按agent_name分组聚合
        query = (
            select(
                WritingStat.agent_name,
                func.sum(WritingStat.input_tokens).label("total_input_tokens"),
                func.sum(WritingStat.output_tokens).label("total_output_tokens"),
                func.sum(WritingStat.total_tokens).label("total_tokens"),
                func.sum(WritingStat.duration_sec).label("total_duration_sec"),
                func.sum(WritingStat.estimated_cost).label("total_cost"),
                func.count(WritingStat.id).label("call_count")
            )
            .where(WritingStat.task_id == task_id)
            .group_by(WritingStat.agent_name)
        )
        
        result = await self.db.execute(query)
        rows = result.all()
        
        # 构建返回结果
        stats = {}
        total_summary = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_duration_sec": 0.0,
            "total_cost": 0.0,
            "total_calls": 0
        }
        
        for row in rows:
            agent_name = row.agent_name
            stats[agent_name] = {
                "input_tokens": row.total_input_tokens or 0,
                "output_tokens": row.total_output_tokens or 0,
                "total_tokens": row.total_tokens or 0,
                "duration_sec": row.total_duration_sec or 0.0,
                "cost": row.total_cost or 0.0,
                "call_count": row.call_count
            }
            
            total_summary["total_input_tokens"] += row.total_input_tokens or 0
            total_summary["total_output_tokens"] += row.total_output_tokens or 0
            total_summary["total_tokens"] += row.total_tokens or 0
            total_summary["total_duration_sec"] += row.total_duration_sec or 0.0
            total_summary["total_cost"] += row.total_cost or 0.0
            total_summary["total_calls"] += row.call_count
        
        stats["_summary"] = total_summary
        
        return stats
    
    async def delete_task(self, task_id: int, user_id: int) -> bool:
        """删除任务（需验证用户权限）
        
        删除任务会级联删除所有关联的单元、场景和统计数据。
        
        Args:
            task_id: 任务ID
            user_id: 用户ID（用于权限校验）
            
        Returns:
            bool: 是否删除成功
        """
        try:
            task = await self.get_task(task_id, user_id)
            if not task:
                logger.warning(f"任务不存在或无权限: task_id={task_id}, user_id={user_id}")
                return False
            
            # 检查任务状态，运行中的任务不能删除
            if task.status == TaskStatus.RUNNING:
                logger.warning(f"运行中的任务不能删除: task_id={task_id}")
                return False
            
            await self.db.delete(task)
            await self.db.commit()
            
            logger.info(f"任务已删除: task_id={task_id}, uuid={task.uuid}")
            return True
            
        except Exception as e:
            logger.error(f"删除任务失败: task_id={task_id}, error={str(e)}")
            await self.db.rollback()
            return False
    
    async def update_task_progress(
        self,
        task_id: int,
        completed_units: int,
        total_tokens: int = 0,
        total_cost: float = 0.0
    ) -> bool:
        """更新任务进度
        
        Args:
            task_id: 任务ID
            completed_units: 已完成单元数
            total_tokens: 累计token消耗
            total_cost: 累计费用
            
        Returns:
            bool: 是否更新成功
        """
        try:
            task = await self.db.get(WritingTask, task_id)
            if not task:
                return False
            
            task.completed_units = completed_units
            if total_tokens > 0:
                task.total_tokens = total_tokens
            if total_cost > 0:
                task.total_cost = total_cost
            
            await self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"更新任务进度失败: task_id={task_id}, error={str(e)}")
            await self.db.rollback()
            return False
    
    async def get_task_by_project(
        self,
        project_id: int,
        user_id: int,
        include_completed: bool = False
    ) -> List[WritingTask]:
        """获取项目的所有写作任务
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
            include_completed: 是否包含已完成的任务
            
        Returns:
            List[WritingTask]: 任务列表
        """
        conditions = [
            WritingTask.project_id == project_id,
            WritingTask.user_id == user_id
        ]
        
        if not include_completed:
            conditions.append(WritingTask.status != TaskStatus.COMPLETED)
        
        query = (
            select(WritingTask)
            .where(and_(*conditions))
            .order_by(WritingTask.created_at.desc())
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def count_tasks(
        self,
        user_id: int,
        project_id: Optional[int] = None,
        status: Optional[TaskStatus] = None
    ) -> int:
        """统计任务数量
        
        Args:
            user_id: 用户ID
            project_id: 项目ID（可选）
            status: 任务状态（可选）
            
        Returns:
            int: 任务数量
        """
        conditions = [WritingTask.user_id == user_id]
        
        if project_id is not None:
            conditions.append(WritingTask.project_id == project_id)
        
        if status is not None:
            conditions.append(WritingTask.status == status)
        
        query = select(func.count(WritingTask.id)).where(and_(*conditions))
        result = await self.db.execute(query)
        return result.scalar() or 0

