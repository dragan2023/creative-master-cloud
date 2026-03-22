"""
认证依赖
支持JWT Token认证和多租户上下文
"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Depends, Query, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt

from app.core.database import get_db
from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.tenant_context import TenantContext
from app.models import User, UserRole, Tenant, TenantStatus


# HTTP Bearer 认证
security = HTTPBearer(auto_error=False)

# 默认用户ID缓存（兼容无认证模式）
_default_user_id = None

settings = get_settings()
logger = get_logger("auth")


async def verify_token(token: str) -> dict:
    """
    验证JWT Token
    
    Args:
        token: JWT Token字符串
    
    Returns:
        Token解码后的payload
    
    Raises:
        HTTPException: Token无效或过期
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的Token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_or_create_default_user(db: AsyncSession) -> User:
    """
    获取或创建默认用户（兼容模式）

    用于本地开发或无认证场景

    Args:
        db: 数据库会话

    Returns:
        默认用户
    """
    global _default_user_id

    # 如果缓存了用户ID，直接查询
    if _default_user_id:
        result = await db.execute(select(User).where(User.id == _default_user_id))
        user = result.scalar_one_or_none()
        if user:
            return user

    # 查找名为 "default" 的用户
    result = await db.execute(select(User).where(User.username == 'default'))
    user = result.scalar_one_or_none()

    if user:
        _default_user_id = user.id
        return user

    # 如果没有 default 用户，查找第一个用户
    result = await db.execute(select(User).order_by(User.id.asc()).limit(1))
    user = result.scalar_one_or_none()

    if user:
        _default_user_id = user.id
        return user

    # 如果没有任何用户，创建一个默认用户
    from app.core.security import get_password_hash

    user = User(
        username="default",
        email="default@local.host",
        hashed_password=get_password_hash("default_password"),
        role=UserRole.USER,
        is_active=True,
        nickname="默认用户"
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    _default_user_id = user.id

    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前用户（支持JWT认证）

    Args:
        credentials: 认证凭据
        db: 数据库会话

    Returns:
        当前用户
    """
    # 如果没有提供Token，检查是否启用了多租户模式
    if not credentials:
        if settings.MULTI_TENANT_ENABLED if hasattr(settings, 'MULTI_TENANT_ENABLED') else False:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未提供认证Token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # 兼容模式：返回默认用户
        return await get_or_create_default_user(db)
    
    # 验证Token
    token = credentials.credentials
    payload = await verify_token(token)
    
    # 从Token中获取用户ID
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token格式错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token格式错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 查询用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    
    # 设置租户上下文
    if user.tenant_id:
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if tenant:
            # 检查租户状态
            if not tenant.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="租户已被暂停或过期",
                )
            TenantContext.set_tenant(tenant)
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    获取当前用户（可选）

    Args:
        credentials: 认证凭据
        db: 数据库会话

    Returns:
        当前用户，如果未认证则返回None
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取当前活跃用户

    Args:
        current_user: 当前用户

    Returns:
        当前活跃用户

    Raises:
        HTTPException: 用户未激活
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户未激活"
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取当前超级管理员用户

    Args:
        current_user: 当前用户

    Returns:
        当前超级管理员

    Raises:
        HTTPException: 非超级管理员
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限"
        )
    return current_user


async def get_current_tenant_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取当前租户管理员或超级管理员

    Args:
        current_user: 当前用户

    Returns:
        当前管理员用户

    Raises:
        HTTPException: 非管理员
    """
    if not (current_user.is_super_admin or current_user.is_tenant_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def get_current_user_from_query_or_header(
    token: Optional[str] = Query(None, description="JWT Token"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前用户（支持Query参数和Header）

    用于SSE等特殊场景

    Args:
        token: Query参数中的JWT Token
        credentials: Header中的认证凭据
        db: 数据库会话

    Returns:
        当前用户
    """
    # 优先使用Header中的Token
    if credentials:
        return await get_current_user(credentials, db)
    
    # 使用Query参数中的Token
    if token:
        payload = await verify_token(token)
        user_id = payload.get("sub")
        if user_id:
            try:
                user_id = int(user_id)
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user and user.is_active:
                    # 设置租户上下文
                    if user.tenant_id:
                        tenant_result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
                        tenant = tenant_result.scalar_one_or_none()
                        if tenant:
                            TenantContext.set_tenant(tenant)
                    return user
            except (ValueError, Exception) as e:
                logger.warning(f"Token解析失败: {e}")
    
    # 兼容模式：返回默认用户
    return await get_or_create_default_user(db)
