"""
系统配置模型
存储系统级配置（如代理设置等）
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text

from app.models.base import Base, get_local_now


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_configs"

    # 配置项ID，如 'proxy', 'chroma_cache' 等
    id = Column(String(50), primary_key=True)

    # 配置值（JSON格式存储复杂配置）
    config_value = Column(Text, nullable=True)

    # 配置描述
    description = Column(String(255), nullable=True)

    # 是否启用
    is_enabled = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime, default=get_local_now)
    updated_at = Column(DateTime, default=get_local_now,
                        onupdate=get_local_now)

    def __repr__(self):
        return f"<SystemConfig(id={self.id}, enabled={self.is_enabled})>"
