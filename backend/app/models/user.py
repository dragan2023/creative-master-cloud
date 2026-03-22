"""
用户模型
支持多租户架构
"""
from sqlalchemy import Column, String, Boolean, Enum, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """用户角色枚举"""
    USER = "user"           # 普通用户
    TENANT_ADMIN = "tenant_admin"  # 租户管理员
    SUPER_ADMIN = "super_admin"    # 超级管理员（平台级）


class User(BaseModel):
    """用户表"""
    __tablename__ = "users"

    # 多租户字段
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), 
                       nullable=True, index=True, comment="租户ID（NULL表示平台管理员）")
    
    # 基本信息
    username = Column(String(50), index=True, nullable=False, comment="用户名")
    email = Column(String(100), index=True, nullable=False, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="密码哈希")
    
    # 角色与状态
    role = Column(
        Enum(UserRole),
        default=UserRole.USER,
        nullable=False,
        comment="用户角色"
    )
    is_active = Column(Boolean, default=True, nullable=False, comment="是否激活")
    is_verified = Column(Boolean, default=False, nullable=False, comment="邮箱是否已验证")
    
    # 个人信息
    avatar = Column(String(255), nullable=True, comment="头像URL")
    nickname = Column(String(50), nullable=True, comment="昵称")
    phone = Column(String(20), nullable=True, comment="手机号")
    
    # 登录信息
    last_login_at = Column(String(30), nullable=True, comment="最后登录时间")
    last_login_ip = Column(String(50), nullable=True, comment="最后登录IP")
    login_count = Column(Integer, default=0, comment="登录次数")
    
    # 关联关系
    tenant = relationship("Tenant", back_populates="users")
    api_keys = relationship(
        "UserAPIKey", back_populates="user", cascade="all, delete-orphan")
    generations = relationship(
        "Generation", back_populates="user", cascade="all, delete-orphan")
    knowledge_bases = relationship(
        "KnowledgeBase", back_populates="user", cascade="all, delete-orphan")
    actions = relationship(
        "UserAction", back_populates="user", cascade="all, delete-orphan")
    novel_projects = relationship(
        "NovelProject", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role={self.role}, tenant_id={self.tenant_id})>"

    def to_dict(self, exclude: list = None) -> dict:
        exclude = exclude or []
        exclude.extend(["hashed_password"])
        return super().to_dict(exclude)
    
    @property
    def is_super_admin(self) -> bool:
        """是否为超级管理员"""
        return self.role == UserRole.SUPER_ADMIN
    
    @property
    def is_tenant_admin(self) -> bool:
        """是否为租户管理员"""
        return self.role == UserRole.TENANT_ADMIN
    
    @property
    def is_platform_user(self) -> bool:
        """是否为平台用户（无租户绑定）"""
        return self.tenant_id is None
