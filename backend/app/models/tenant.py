"""
租户模型
支持多租户SaaS架构
"""
from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.models.base import BaseModel


class TenantStatus(str, enum.Enum):
    """租户状态枚举"""
    TRIAL = "trial"        # 试用中
    ACTIVE = "active"      # 正常使用
    SUSPENDED = "suspended"  # 已暂停
    EXPIRED = "expired"    # 已过期


class TenantPlan(str, enum.Enum):
    """租户套餐枚举"""
    FREE = "free"          # 免费版
    BASIC = "basic"        # 基础版
    PRO = "pro"            # 专业版
    ENTERPRISE = "enterprise"  # 企业版


class Tenant(BaseModel):
    """租户表"""
    __tablename__ = "tenants"

    # 基本信息
    name = Column(String(100), unique=True, nullable=False, index=True, comment="租户名称")
    slug = Column(String(50), unique=True, nullable=False, index=True, comment="租户标识（用于URL）")
    logo = Column(String(255), nullable=True, comment="租户Logo URL")
    
    # 联系信息
    contact_name = Column(String(50), nullable=True, comment="联系人姓名")
    contact_email = Column(String(100), nullable=False, comment="联系邮箱")
    contact_phone = Column(String(20), nullable=True, comment="联系电话")
    
    # 套餐与状态
    plan = Column(
        Enum(TenantPlan),
        default=TenantPlan.FREE,
        nullable=False,
        comment="套餐类型"
    )
    status = Column(
        Enum(TenantStatus),
        default=TenantStatus.TRIAL,
        nullable=False,
        comment="租户状态"
    )
    
    # 配额限制
    max_users = Column(Integer, default=5, comment="最大用户数")
    max_projects = Column(Integer, default=10, comment="最大项目数")
    max_storage_mb = Column(Integer, default=1024, comment="最大存储空间(MB)")
    max_api_calls_per_day = Column(Integer, default=1000, comment="每日API调用上限")
    
    # 使用统计
    current_users = Column(Integer, default=0, comment="当前用户数")
    current_projects = Column(Integer, default=0, comment="当前项目数")
    current_storage_mb = Column(Integer, default=0, comment="当前存储使用(MB)")
    api_calls_today = Column(Integer, default=0, comment="今日API调用数")
    api_calls_total = Column(Integer, default=0, comment="总API调用数")
    
    # 时间相关
    trial_ends_at = Column(DateTime, nullable=True, comment="试用结束时间")
    subscription_ends_at = Column(DateTime, nullable=True, comment="订阅结束时间")
    last_active_at = Column(DateTime, nullable=True, comment="最后活跃时间")
    
    # 配置
    settings = Column(Text, nullable=True, comment="租户自定义配置(JSON)")
    custom_domain = Column(String(100), nullable=True, comment="自定义域名")
    
    # 功能开关
    features_enabled = Column(Text, nullable=True, comment="启用的功能列表(JSON)")
    
    # 关联关系
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, name='{self.name}', status={self.status})>"
    
    def to_dict(self, exclude: list = None) -> dict:
        exclude = exclude or []
        return super().to_dict(exclude)
    
    @property
    def is_active(self) -> bool:
        """检查租户是否可用"""
        return self.status in [TenantStatus.TRIAL, TenantStatus.ACTIVE]
    
    @property
    def is_trial(self) -> bool:
        """检查是否为试用租户"""
        return self.status == TenantStatus.TRIAL
    
    def check_quota(self, resource: str) -> bool:
        """
        检查资源配额是否充足
        
        Args:
            resource: 资源类型 (users/projects/storage/api_calls)
        
        Returns:
            是否在配额范围内
        """
        from datetime import datetime
        
        if resource == "users":
            return self.current_users < self.max_users
        elif resource == "projects":
            return self.current_projects < self.max_projects
        elif resource == "storage":
            return self.current_storage_mb < self.max_storage_mb
        elif resource == "api_calls":
            # 每日API调用检查
            return self.api_calls_today < self.max_api_calls_per_day
        return True
    
    def increment_usage(self, resource: str, amount: int = 1) -> None:
        """
        增加使用量
        
        Args:
            resource: 资源类型
            amount: 增加数量
        """
        if resource == "users":
            self.current_users += amount
        elif resource == "projects":
            self.current_projects += amount
        elif resource == "storage":
            self.current_storage_mb += amount
        elif resource == "api_calls":
            self.api_calls_today += amount
            self.api_calls_total += amount


# 套餐配置常量
PLAN_LIMITS = {
    TenantPlan.FREE: {
        "max_users": 1,
        "max_projects": 3,
        "max_storage_mb": 100,
        "max_api_calls_per_day": 100,
        "trial_days": 0
    },
    TenantPlan.BASIC: {
        "max_users": 5,
        "max_projects": 20,
        "max_storage_mb": 1024,
        "max_api_calls_per_day": 1000,
        "trial_days": 7
    },
    TenantPlan.PRO: {
        "max_users": 20,
        "max_projects": 100,
        "max_storage_mb": 10240,
        "max_api_calls_per_day": 10000,
        "trial_days": 14
    },
    TenantPlan.ENTERPRISE: {
        "max_users": -1,  # 无限制
        "max_projects": -1,
        "max_storage_mb": -1,
        "max_api_calls_per_day": -1,
        "trial_days": 30
    }
}
