"""
后台管理API端点
提供用户管理、租户管理、系统配置等功能

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import get_password_hash
from app.core.logger import get_logger
from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    AuthorizationException,
)
from app.api.deps import get_current_superuser, get_current_user
from app.models import (
    User, UserRole, Tenant, TenantStatus, TenantPlan,
    OperationLog, NovelProject, KnowledgeBase, Generation
)
from app.schemas.common import ResponseModel
from app.services.admin_service import AdminService

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
    admin_service = AdminService(db)
    stats = await admin_service.get_dashboard_stats()

    return ResponseModel(data=DashboardStats(**stats))


# ==================== 用户管理 ====================

@router.get("/users", response_model=ResponseModel[List[UserListResponse]])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    tenant_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    superuser: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户列表

    需要超级管理员权限
    """
    admin_service = AdminService(db)
    users = await admin_service.list_users(
        page=page,
        page_size=page_size,
        search=search,
        tenant_id=tenant_id,
        is_active=is_active,
        admin_tenant_id=None,
        is_super_admin=True
    )

    # 构建响应
    data = []
    for user in users:
        tenant_name = None
        if user.tenant_id:
            tenant_name = await admin_service.get_tenant_name_by_id(user.tenant_id)

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
    superuser: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    更新用户信息

    需要超级管理员权限
    """
    admin_service = AdminService(db)

    # 查找用户
    user = await admin_service.get_user_by_id(user_id)

    if not user:
        raise ResourceNotFoundException(message="用户不存在")

    await admin_service.update_user(
        user=user,
        is_active=data.is_active,
        role=data.role,
        nickname=data.nickname
    )

    logger.info(f"超级管理员 {superuser.username} 更新用户 {user.username}")

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
    admin_service = AdminService(db)

    user = await admin_service.get_user_by_id(user_id)

    if not user:
        raise ResourceNotFoundException(message="用户不存在")

    if user.id == admin.id:
        raise ValidationException(message="不能删除自己")

    username = user.username
    await admin_service.delete_user(user)

    logger.info(f"超级管理员 {admin.username} 删除用户 {username}")

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
    admin_service = AdminService(db)
    tenants = await admin_service.list_tenants(
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        plan=plan
    )

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
            subscription_ends_at=str(
                t.subscription_ends_at) if t.subscription_ends_at else None
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
    admin_service = AdminService(db)

    tenant = await admin_service.get_tenant_by_id(tenant_id)

    if not tenant:
        raise ResourceNotFoundException(message="租户不存在")

    await admin_service.update_tenant(
        tenant=tenant,
        name=data.name,
        status=data.status,
        plan=data.plan,
        max_users=data.max_users,
        max_projects=data.max_projects,
        max_storage_mb=data.max_storage_mb
    )

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
    superuser: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    获取操作日志

    需要超级管理员权限
    """
    admin_service = AdminService(db)
    logs = await admin_service.list_operation_logs(
        page=page,
        page_size=page_size,
        user_id=user_id,
        tenant_id=tenant_id,
        action=action,
        admin_tenant_id=None,
        is_super_admin=True
    )

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
    admin_service = AdminService(db)

    # 检查数据库
    database_status = await admin_service.check_database_health()

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
    storage_used = sum(
        f.stat().st_size for f in data_dir.rglob('*') if f.is_file())
    storage_used_mb = storage_used // (1024 * 1024)

    return ResponseModel(data=SystemHealth(
        database=database_status,
        redis=redis_status,
        storage_used_mb=storage_used_mb,
        storage_total_mb=10240  # 假设总容量10GB
    ))
