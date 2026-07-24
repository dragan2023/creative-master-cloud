"""
管理员服务模块

封装用户管理和系统管理的数据库操作。

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Tenant, OperationLog, NovelProject, Generation
from app.core.logger import get_logger
from app.core.time import utc_now

logger = get_logger("admin_service")


class AdminService:
    """
    管理员服务类
    
    封装用户管理、租户管理、系统监控等数据库操作。
    """
    
    def __init__(self, db: AsyncSession):
        """
        初始化服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    # ==================== 用户管理 ====================
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        根据ID获取用户
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户对象或None
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def get_user_with_tenant_name(self, user_id: int) -> Tuple[Optional[User], Optional[str]]:
        """
        获取用户及其租户名称
        
        Args:
            user_id: 用户ID
            
        Returns:
            (用户对象, 租户名称) 元组
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return None, None
        
        tenant_name = None
        if user.tenant_id:
            tenant_name = await self.get_tenant_name_by_id(user.tenant_id)
        
        return user, tenant_name
    
    async def get_tenant_name_by_id(self, tenant_id: int) -> Optional[str]:
        """
        根据ID获取租户名称
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            租户名称或None
        """
        result = await self.db.execute(
            select(Tenant.name).where(Tenant.id == tenant_id)
        )
        return result.scalar()
    
    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        tenant_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        admin_tenant_id: Optional[int] = None,
        is_super_admin: bool = False
    ) -> List[User]:
        """
        获取用户列表
        
        Args:
            page: 页码
            page_size: 每页数量
            search: 搜索关键词
            tenant_id: 租户ID过滤
            is_active: 状态过滤
            admin_tenant_id: 管理员租户ID（用于权限过滤）
            is_super_admin: 是否超级管理员
            
        Returns:
            用户列表
        """
        query = select(User)
        
        # 租户管理员只能查看本租户用户
        if not is_super_admin and admin_tenant_id:
            query = query.where(User.tenant_id == admin_tenant_id)
        elif tenant_id:
            query = query.where(User.tenant_id == tenant_id)
        
        # 搜索条件
        if search:
            query = query.where(
                or_(
                    User.username.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )
        
        # 状态过滤
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        
        # 排序和分页
        query = query.order_by(User.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_user(
        self,
        user: User,
        is_active: Optional[bool] = None,
        role = None,
        nickname: Optional[str] = None
    ) -> User:
        """
        更新用户信息
        
        Args:
            user: 用户对象
            is_active: 是否激活
            role: 用户角色
            nickname: 昵称
            
        Returns:
            更新后的用户对象
        """
        if is_active is not None:
            user.is_active = is_active
        if role is not None:
            user.role = role
        if nickname is not None:
            user.nickname = nickname
        
        await self.db.commit()
        return user
    
    async def delete_user(self, user: User) -> None:
        """
        删除用户
        
        Args:
            user: 用户对象
        """
        await self.db.delete(user)
        await self.db.commit()
    
    # ==================== 租户管理 ====================
    
    async def get_tenant_by_id(self, tenant_id: int) -> Optional[Tenant]:
        """
        根据ID获取租户
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            租户对象或None
        """
        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()
    
    async def list_tenants(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status = None,
        plan = None
    ) -> List[Tenant]:
        """
        获取租户列表
        
        Args:
            page: 页码
            page_size: 每页数量
            search: 搜索关键词
            status: 状态过滤
            plan: 套餐过滤
            
        Returns:
            租户列表
        """
        query = select(Tenant)
        
        # 搜索条件
        if search:
            query = query.where(
                or_(
                    Tenant.name.ilike(f"%{search}%"),
                    Tenant.slug.ilike(f"%{search}%")
                )
            )
        
        # 状态过滤
        if status:
            query = query.where(Tenant.status == status)
        # 套餐过滤
        if plan:
            query = query.where(Tenant.plan == plan)
        
        # 排序和分页
        query = query.order_by(Tenant.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_tenant(
        self,
        tenant: Tenant,
        name: Optional[str] = None,
        status = None,
        plan = None,
        max_users: Optional[int] = None,
        max_projects: Optional[int] = None,
        max_storage_mb: Optional[int] = None
    ) -> Tenant:
        """
        更新租户信息
        
        Args:
            tenant: 租户对象
            name: 租户名称
            status: 租户状态
            plan: 套餐类型
            max_users: 最大用户数
            max_projects: 最大项目数
            max_storage_mb: 最大存储空间
            
        Returns:
            更新后的租户对象
        """
        if name is not None:
            tenant.name = name
        if status is not None:
            tenant.status = status
        if plan is not None:
            tenant.plan = plan
        if max_users is not None:
            tenant.max_users = max_users
        if max_projects is not None:
            tenant.max_projects = max_projects
        if max_storage_mb is not None:
            tenant.max_storage_mb = max_storage_mb
        
        await self.db.commit()
        return tenant
    
    # ==================== 操作日志 ====================
    
    async def list_operation_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        action: Optional[str] = None,
        admin_tenant_id: Optional[int] = None,
        is_super_admin: bool = False
    ) -> List[OperationLog]:
        """
        获取操作日志列表
        
        Args:
            page: 页码
            page_size: 每页数量
            user_id: 用户ID过滤
            tenant_id: 租户ID过滤
            action: 操作类型过滤
            admin_tenant_id: 管理员租户ID（用于权限过滤）
            is_super_admin: 是否超级管理员
            
        Returns:
            操作日志列表
        """
        query = select(OperationLog)
        
        # 权限过滤
        if not is_super_admin and admin_tenant_id:
            query = query.where(OperationLog.tenant_id == admin_tenant_id)
        elif tenant_id:
            query = query.where(OperationLog.tenant_id == tenant_id)
        
        # 条件过滤
        if user_id:
            query = query.where(OperationLog.user_id == user_id)
        if action:
            query = query.where(OperationLog.action == action)
        
        # 排序和分页
        query = query.order_by(OperationLog.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    # ==================== 仪表盘统计 ====================
    
    async def get_dashboard_stats(self) -> dict:
        """
        获取仪表盘统计数据
        
        Returns:
            统计数据字典
        """
        # 统计用户数
        total_users = await self.db.scalar(select(func.count(User.id)))
        
        # 统计租户数
        total_tenants = await self.db.scalar(select(func.count(Tenant.id)))
        
        # 统计今日活跃用户
        today = utc_now().date()
        active_today = await self.db.scalar(
            select(func.count(User.id)).where(
                func.date(User.last_login_at) == today
            )
        )
        
        # 统计项目数
        total_projects = await self.db.scalar(select(func.count(NovelProject.id)))
        
        # 统计生成任务数
        total_generations = await self.db.scalar(select(func.count(Generation.id)))
        
        # 统计本周新用户
        week_ago = utc_now() - timedelta(days=7)
        new_users_week = await self.db.scalar(
            select(func.count(User.id)).where(User.created_at >= week_ago)
        )
        
        return {
            "total_users": total_users or 0,
            "total_tenants": total_tenants or 0,
            "active_users_today": active_today or 0,
            "total_projects": total_projects or 0,
            "total_generations": total_generations or 0,
            "new_users_this_week": new_users_week or 0
        }
    
    # ==================== 系统健康检查 ====================
    
    async def check_database_health(self) -> str:
        """
        检查数据库健康状态
        
        Returns:
            状态字符串: "healthy" 或 "unhealthy"
        """
        try:
            await self.db.execute(select(1))
            return "healthy"
        except Exception:
            return "unhealthy"
