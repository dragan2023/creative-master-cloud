"""
管理员相关 Schema
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from app.schemas.user import UserResponse
from app.schemas.generation import GenerationHistoryResponse
from app.schemas.knowledge import KnowledgeBaseResponse


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ==================== 用户管理 ====================

class AdminUserListResponse(BaseModel):
    """管理员用户列表响应"""
    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    """管理员更新用户"""
    email: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None


# ==================== 提示词管理 ====================

class PromptTemplateCreate(BaseModel):
    """创建提示词模板"""
    module: str = Field(..., description="模块名称")
    name: str = Field(..., description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    content: str = Field(..., description="提示词内容")
    variables: Optional[List[str]] = Field(default=None, description="变量列表")
    is_active: Optional[bool] = Field(default=True, description="是否启用")


class PromptTemplateResponse(BaseModel):
    """提示词模板响应"""
    id: int
    module: str
    name: str
    description: Optional[str] = None
    content: str
    variables: Optional[List[str]] = None
    version: str
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PromptTemplateListResponse(BaseModel):
    """提示词模板列表响应"""
    items: List[PromptTemplateResponse]
    total: int


# ==================== 日志管理 ====================

class LogQueryParams(BaseModel):
    """日志查询参数"""
    level: Optional[LogLevel] = None
    user_id: Optional[str] = None
    module: Optional[str] = None
    keyword: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class LogResponse(BaseModel):
    """日志响应"""
    id: int
    level: LogLevel
    user_id: Optional[str] = None
    module: Optional[str] = None
    action: Optional[str] = None
    message: str
    request_id: Optional[str] = None
    created_at: str
    extra_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class LogListResponse(BaseModel):
    """日志列表响应"""
    items: List[LogResponse]
    total: int
    page: int
    page_size: int


# ==================== 版本管理 ====================

class VersionCreate(BaseModel):
    """创建版本"""
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="版本号")
    name: str = Field(..., description="版本名称")
    description: Optional[str] = Field(None, description="版本描述")
    changelog: Optional[str] = Field(None, description="更新日志")


class VersionResponse(BaseModel):
    """版本响应"""
    id: int
    version: str
    name: str
    description: Optional[str] = None
    changelog: Optional[str] = None
    is_released: bool
    is_current: bool
    released_at: Optional[str] = None
    created_at: str
    backup_path: Optional[str] = None
    backup_size: Optional[int] = None

    class Config:
        from_attributes = True


class VersionListResponse(BaseModel):
    """版本列表响应"""
    items: List[VersionResponse]
    total: int


class VersionBackupResponse(BaseModel):
    """版本备份响应"""
    id: int
    version: str
    name: str
    backup_path: Optional[str] = None
    backup_size: Optional[int] = None
    created_at: str
    is_current: bool

    class Config:
        from_attributes = True


class VersionBackupListResponse(BaseModel):
    """版本备份列表响应"""
    items: List[VersionBackupResponse]
    total: int
    max_backups: int = 5


class VersionSwitchRequest(BaseModel):
    """版本切换请求"""
    version_id: int = Field(..., description="目标版本ID")


# ==================== 监控统计 ====================

class MonitorStats(BaseModel):
    """监控统计"""
    total_users: int
    active_users_today: int
    total_generations: int
    generations_today: int
    total_tokens_used: int
    tokens_today: int
    avg_response_time_ms: float
    error_rate: float


class TrafficData(BaseModel):
    """流量数据"""
    date: str
    request_count: int
    unique_users: int
    avg_response_time: float


class TrafficStats(BaseModel):
    """流量统计"""
    daily: List[TrafficData]
    total_requests: int
    total_unique_users: int
