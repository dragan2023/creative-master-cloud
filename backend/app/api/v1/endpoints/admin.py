"""
后台管理API端点
提供用户管理、租户管理、系统配置等功能
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from pydantic import BaseModel, EmailStr, Field

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import get_password_hash
from app.core.logger import get_logger
from app.api.deps import get_current_superuser, get_current_tenant_admin, get_current_user
from app.models import (
    User, UserRole, Tenant, TenantStatus, TenantPlan,
    OperationLog, NovelProject, KnowledgeBase, Generation
)
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/admin", tags=["后台管理"])
settings = get_settings()
logger = get_logger("admin")


# ==================== Schema定义 ====================

class UserListResponse(BaseModel):
    """用户列表响应"""
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    tenant_id: Optional[int]
    tenant_name: Optional[str]
    created_at: Optional[str]
    last_login_at: Optional[str]


class TenantListResponse(BaseModel):
    """租户列表响应"""
    id: int
    name: str
    slug: str
    plan: str
    status: str
    current_users: int
    max_users: int
    current_projects: int
    max_projects: int
    created_at: Optional[str]
    subscription_ends_at: Optional[str]


class UserUpdateRequest(BaseModel):
    """用户更新请求"""
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    nickname: Optional[str] = None


class TenantUpdateRequest(BaseModel):
    """租户更新请求"""
    name: Optional[str] = None
    status: Optional[TenantStatus] = None
    plan: Optional[TenantPlan] = None
    max_users: Optional[int] = None
    max_projects: Optional[int] = None
    max_storage_mb: Optional[int] = None


class DashboardStats(BaseModel):
    """仪表盘统计"""
    total_users: int
    total_tenants: int
    active_users_today: int
    total_projects: int
    total_generations: int
    new_users_this_week: int


class SystemHealth(BaseModel):
    """系统健康状态"""
    database: str
    redis: str
    storage_used_mb: int
    storage_total_mb: int


# ==================== 仪表盘 ====================

@router.get("/dashboard", response_model=ResponseModel[DashboardStats])
async def get_dashboard(
    superuser: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    获取仪表盘统计数据
    
    需要超级管理员权限
    """
    # 统计用户数
    total_users = await db.scalar(select(func.count(User.id)))
    
    # 统计租户数
    total_tenants = await db.scalar(select(func.count(Tenant.id)))
    
    # 统计今日活跃用户
    today = datetime.utcnow().date()
    active_today = await db.scalar(
        select(func.count(User.id)).where(
            func.date(User.last_login_at) == today
        )
    )
    
    # 统计项目数
    total_projects = await db.scalar(select(func.count(NovelProject.id)))
    
    # 统计生成任务数
    total_generations = await db.scalar(select(func.count(Generation.id)))
    
    # 统计本周新用户
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_users_week = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )
    
    return ResponseModel(data=DashboardStats(
        total_users=total_users or 0,
        total_tenants=total_tenants or 0,
        active_users_today=active_today or 0,
        total_projects=total_projects or 0,
        total_generations=total_generations or 0,
        new_users_this_week=new_users_week or 0
    ))


# ==================== 用户管理 ====================

@router.get("/users", response_model=ResponseModel[List[UserListResponse]])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    tenant_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    admin: User = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户列表
    
    超级管理员可查看所有用户，租户管理员只能查看本租户用户
    """
    query = select(User)
    
    # 租户管理员只能查看本租户用户
    if not admin.is_super_admin:
        query = query.where(User.tenant_id == admin.tenant_id)
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
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    # 构建响应
    data = []
    for user in users:
        tenant_name = None
        if user.tenant_id:
            tenant_result = await db.execute(
                select(Tenant.name).where(Tenant.id == user.tenant_id)
            )
            tenant_name = tenant_result.scalar()
        
        data.append(UserListResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
            tenant_id=user.tenant_id,
            tenant_name=tenant_name,
            created_at=str(user.created_at) if user.created_at else None,
            last_login_at=user.last_login_at
        ))
    
    return ResponseModel(data=data)


@router.patch("/users/{user_id}", response_model=ResponseModel)
async def update_user(
    user_id: int,
    data: UserUpdateRequest,
    admin: User = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    更新用户信息
    
    超级管理员可更新所有用户，租户管理员只能更新本租户用户
    """
    # 查找用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 权限检查
    if not admin.is_super_admin and user.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=403, detail="无权操作此用户")
    
    # 更新字段
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.role is not None:
        # 只有超级管理员可以修改角色
        if admin.is_super_admin:
            user.role = data.role
    if data.nickname is not None:
        user.nickname = data.nickname
    
    await db.commit()
    
    logger.info(f"管理员 {admin.username} 更新用户 {user.username}")
    
    return ResponseModel(message="更新成功")


@router.delete("/users/{user_id}", response_model=ResponseModel)
async def delete_user(
    user_id: int,
    admin: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    删除用户
    
    需要超级管理员权限
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    
    await db.delete(user)
    await db.commit()
    
    logger.info(f"超级管理员 {admin.username} 删除用户 {user.username}")
    
    return ResponseModel(message="删除成功")


# ==================== 租户管理 ====================

@router.get("/tenants", response_model=ResponseModel[List[TenantListResponse]])
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[TenantStatus] = None,
    plan: Optional[TenantPlan] = None,
    superuser: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    获取租户列表
    
    需要超级管理员权限
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
    
    result = await db.execute(query)
    tenants = result.scalars().all()
    
    data = [
        TenantListResponse(
            id=t.id,
            name=t.name,
            slug=t.slug,
            plan=t.plan.value,
            status=t.status.value,
            current_users=t.current_users or 0,
            max_users=t.max_users or 0,
            current_projects=t.current_projects or 0,
            max_projects=t.max_projects or 0,
            created_at=str(t.created_at) if t.created_at else None,
            subscription_ends_at=str(t.subscription_ends_at) if t.subscription_ends_at else None
        )
        for t in tenants
    ]
    
    return ResponseModel(data=data)


@router.patch("/tenants/{tenant_id}", response_model=ResponseModel)
async def update_tenant(
    tenant_id: int,
    data: TenantUpdateRequest,
    superuser: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    更新租户信息
    
    需要超级管理员权限
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    
    # 更新字段
    if data.name is not None:
        tenant.name = data.name
    if data.status is not None:
        tenant.status = data.status
    if data.plan is not None:
        tenant.plan = data.plan
    if data.max_users is not None:
        tenant.max_users = data.max_users
    if data.max_projects is not None:
        tenant.max_projects = data.max_projects
    if data.max_storage_mb is not None:
        tenant.max_storage_mb = data.max_storage_mb
    
    await db.commit()
    
    logger.info(f"超级管理员 {superuser.username} 更新租户 {tenant.name}")
    
    return ResponseModel(message="更新成功")


# ==================== 操作日志 ====================

@router.get("/logs", response_model=ResponseModel[List[dict]])
async def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    action: Optional[str] = None,
    admin: User = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取操作日志
    
    超级管理员可查看所有日志，租户管理员只能查看本租户日志
    """
    query = select(OperationLog)
    
    # 权限过滤
    if not admin.is_super_admin:
        query = query.where(OperationLog.tenant_id == admin.tenant_id)
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
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    data = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "username": log.username,
            "tenant_id": log.tenant_id,
            "action": log.action,
            "module": log.module,
            "description": log.description,
            "ip_address": log.ip_address,
            "status": log.status,
            "created_at": str(log.created_at) if log.created_at else None
        }
        for log in logs
    ]
    
    return ResponseModel(data=data)


# ==================== 系统健康检查 ====================

@router.get("/health", response_model=ResponseModel[SystemHealth])
async def system_health(
    superuser: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    获取系统健康状态
    
    需要超级管理员权限
    """
    # 检查数据库
    try:
        await db.execute(select(1))
        database_status = "healthy"
    except Exception:
        database_status = "unhealthy"
    
    # 检查Redis
    try:
        from app.core.redis_client import redis_manager
        if redis_manager and hasattr(redis_manager, 'ping'):
            await redis_manager.ping()
            redis_status = "healthy"
        else:
            redis_status = "not_configured"
    except Exception:
        redis_status = "unhealthy"
    
    # 存储使用情况
    import os
    from pathlib import Path
    
    data_dir = Path(settings.get_upload_dir()).parent
    storage_used = sum(f.stat().st_size for f in data_dir.rglob('*') if f.is_file())
    storage_used_mb = storage_used // (1024 * 1024)
    
    return ResponseModel(data=SystemHealth(
        database=database_status,
        redis=redis_status,
        storage_used_mb=storage_used_mb,
        storage_total_mb=10240  # 假设总容量10GB
    ))
