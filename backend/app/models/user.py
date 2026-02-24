"""
用户模型
"""
from sqlalchemy import Column, String, Boolean, Enum, Text
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """用户角色枚举"""
    USER = "user"       # 普通用户
    ADMIN = "admin"     # 管理员


class User(BaseModel):
    """用户表"""
    __tablename__ = "users"

    username = Column(String(50), unique=True, index=True,
                      nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True,
                   nullable=False, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="密码哈希")
    role = Column(
        Enum(UserRole),
        default=UserRole.USER,
        nullable=False,
        comment="用户角色"
    )
    is_active = Column(Boolean, default=True, nullable=False, comment="是否激活")
    avatar = Column(String(255), nullable=True, comment="头像URL")
    nickname = Column(String(50), nullable=True, comment="昵称")

    # 关联关系
    api_keys = relationship(
        "UserAPIKey", back_populates="user", cascade="all, delete-orphan")
    generations = relationship(
        "Generation", back_populates="user", cascade="all, delete-orphan")
    knowledge_bases = relationship(
        "KnowledgeBase", back_populates="user", cascade="all, delete-orphan")
    actions = relationship(
        "UserAction", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role={self.role})>"

    def to_dict(self, exclude: list = None) -> dict:
        exclude = exclude or []
        exclude.extend(["hashed_password"])
        return super().to_dict(exclude)
