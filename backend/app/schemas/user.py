"""
用户相关 Schema
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


class UserRole(str, Enum):
    """用户角色"""
    USER = "user"
    ADMIN = "admin"


class UserBase(BaseModel):
    """用户基础 Schema"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")


class UserCreate(UserBase):
    """创建用户 Schema"""
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class UserUpdate(BaseModel):
    """更新用户 Schema"""
    nickname: Optional[str] = Field(None, max_length=50)
    avatar: Optional[str] = Field(None, max_length=255)


class UserResponse(UserBase):
    """用户响应 Schema"""
    id: int
    role: UserRole
    is_active: bool
    avatar: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """用户登录 Schema"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """Token 响应 Schema"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class APIKeyCreate(BaseModel):
    """创建 API Key Schema"""
    provider: str = Field(..., description="提供商")
    model_name: str = Field(..., description="模型名称")
    api_key: str = Field(..., description="API Key")
    api_base: Optional[str] = Field(None, description="自定义 API 地址")
    is_default: bool = Field(default=False, description="是否设为默认")


class APIKeyResponse(BaseModel):
    """API Key 响应 Schema"""
    id: int
    provider: str
    model_name: str
    api_key_masked: str = Field(..., description="脱敏后的 API Key")
    api_base: Optional[str] = None
    is_default: bool
    is_valid: bool
    last_used_at: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class APIKeyTest(BaseModel):
    """API Key 测试 Schema"""
    provider: str
    model_name: str
    api_key: str
    api_base: Optional[str] = None


class APIKeyTestResult(BaseModel):
    """API Key 测试结果"""
    success: bool
    message: str
    model_info: Optional[dict] = None
