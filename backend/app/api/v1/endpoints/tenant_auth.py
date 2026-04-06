"""
租户认证API端点
支持用户注册、登录、Token刷新等

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import get_password_hash, verify_password
from app.core.logger import get_logger
from app.core.tenant_context import TenantContext
from app.core.exceptions import (
    ValidationException,
    AuthenticationException,
    AuthorizationException,
)
from app.models import User, UserRole, Tenant, TenantStatus, TenantPlan, PLAN_LIMITS
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/auth", tags=["认证"])
settings = get_settings()
logger = get_logger("auth")


# ==================== Schema定义 ====================

class UserRegister(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    tenant_name: Optional[str] = Field(None, description="租户名称（可选，不填则创建个人租户）")


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class TenantCreate(BaseModel):
    """创建租户请求"""
    name: str = Field(..., min_length=2, max_length=100, description="租户名称")
    slug: Optional[str] = Field(
        None, min_length=2, max_length=50, description="租户标识")
    plan: TenantPlan = Field(TenantPlan.FREE, description="套餐类型")


# ==================== Token生成 ====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建JWT访问令牌

    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量

    Returns:
        JWT Token字符串
    """
    import jwt

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


# ==================== 用户注册 ====================

@router.post("/register", response_model=ResponseModel[TokenResponse])
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册

    创建新用户并自动创建个人租户
    """
    # 检查用户名是否已存在
    result = await db.execute(
        select(User).where(
            or_(User.username == data.username, User.email == data.email)
        )
    )
    if result.scalar_one_or_none():
        raise ValidationException(message="用户名或邮箱已被注册")

    # 创建个人租户
    tenant_slug = data.username.lower().replace("_", "-")
    tenant = Tenant(
        name=data.tenant_name or f"{data.username}的工作空间",
        slug=tenant_slug,
        contact_email=data.email,
        plan=TenantPlan.FREE,
        status=TenantStatus.TRIAL,
        max_users=PLAN_LIMITS[TenantPlan.FREE]["max_users"],
        max_projects=PLAN_LIMITS[TenantPlan.FREE]["max_projects"],
        max_storage_mb=PLAN_LIMITS[TenantPlan.FREE]["max_storage_mb"],
        max_api_calls_per_day=PLAN_LIMITS[TenantPlan.FREE]["max_api_calls_per_day"],
        trial_ends_at=datetime.utcnow(
        ) + timedelta(days=PLAN_LIMITS[TenantPlan.FREE]["trial_days"])
    )
    db.add(tenant)
    await db.flush()

    # 创建用户
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role=UserRole.USER,  # 注册用户默认为普通用户
        tenant_id=tenant.id,
        is_active=True,
        is_verified=False
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 更新租户用户数
    tenant.current_users = 1
    await db.commit()

    # 生成Token
    access_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": tenant.id}
    )

    logger.info(f"用户注册成功: {user.username}, 租户: {tenant.name}")

    return ResponseModel(
        data=TokenResponse(
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "tenant_id": tenant.id,
                "tenant_name": tenant.name
            }
        )
    )


# ==================== 用户登录 ====================

@router.post("/login", response_model=ResponseModel[TokenResponse])
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录

    验证用户名/邮箱和密码，返回JWT Token
    """
    # 查找用户
    result = await db.execute(
        select(User).where(
            or_(User.username == data.username, User.email == data.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise AuthenticationException(message="用户名或密码错误")

    if not user.is_active:
        raise AuthorizationException(message="用户已被禁用")

    # 检查租户状态
    tenant_name = None
    if user.tenant_id:
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant:
            tenant_name = tenant.name
            if not tenant.is_active:
                raise AuthorizationException(message="租户已被暂停或过期")

    # 更新登录信息
    user.last_login_at = datetime.utcnow().isoformat()
    user.login_count = (user.login_count or 0) + 1
    await db.commit()

    # 生成Token
    access_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": user.tenant_id}
    )

    logger.info(f"用户登录成功: {user.username}")

    return ResponseModel(
        data=TokenResponse(
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "tenant_id": user.tenant_id,
                "tenant_name": tenant_name
            }
        )
    )


# ==================== OAuth2密码模式登录 ====================

@router.post("/token", response_model=TokenResponse)
async def login_for_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2密码模式登录

    用于兼容标准OAuth2客户端
    """
    login_data = UserLogin(username=form_data.username,
                           password=form_data.password)
    return await login(login_data, db)


# ==================== Token刷新 ====================

@router.post("/refresh", response_model=ResponseModel[TokenResponse])
async def refresh_token(
    current_user: User = Depends(lambda: None),  # 需要从Token获取用户
    db: AsyncSession = Depends(get_db)
):
    """
    刷新Token

    使用当前Token获取新的Token
    """
    from app.api.deps import get_current_user

    # 获取当前用户
    user = await get_current_user(current_user, db)

    # 生成新Token
    access_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": user.tenant_id}
    )

    return ResponseModel(
        data=TokenResponse(
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "tenant_id": user.tenant_id
            }
        )
    )


# ==================== 获取当前用户信息 ====================

@router.get("/me", response_model=ResponseModel[dict])
async def get_me(
    current_user: User = Depends(lambda db: get_current_user(None, db)),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户信息
    """
    from app.api.deps import get_current_user

    user = await get_current_user(None, db)

    tenant_name = None
    if user.tenant_id:
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant:
            tenant_name = tenant.name

    return ResponseModel(
        data={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "nickname": user.nickname,
            "avatar": user.avatar,
            "is_verified": user.is_verified,
            "tenant_id": user.tenant_id,
            "tenant_name": tenant_name,
            "created_at": str(user.created_at) if user.created_at else None
        }
    )


# ==================== 修改密码 ====================

class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6,
                              max_length=50, description="新密码")


@router.post("/change-password", response_model=ResponseModel)
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(lambda db: get_current_user(None, db)),
    db: AsyncSession = Depends(get_db)
):
    """
    修改密码
    """
    from app.api.deps import get_current_user

    user = await get_current_user(None, db)

    # 验证旧密码
    if not verify_password(data.old_password, user.hashed_password):
        raise ValidationException(message="旧密码错误")

    # 更新密码
    user.hashed_password = get_password_hash(data.new_password)
    await db.commit()

    logger.info(f"用户修改密码: {user.username}")

    return ResponseModel(message="密码修改成功")


# ==================== 退出登录 ====================

@router.post("/logout", response_model=ResponseModel)
async def logout():
    """
    退出登录

    JWT是无状态的，服务端不维护Token状态
    客户端需要自行删除Token
    """
    return ResponseModel(message="退出成功")
