"""
版本管理模型
用于系统版本发布与回滚
"""
from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class SystemVersion(BaseModel):
    """系统版本表"""
    __tablename__ = "system_versions"

    version = Column(String(20), unique=True,
                     nullable=False, comment="版本号 (如 1.0.0)")
    name = Column(String(100), nullable=False, comment="版本名称")
    description = Column(Text, nullable=True, comment="版本描述")
    changelog = Column(Text, nullable=True, comment="更新日志")

    # 发布信息
    is_released = Column(Boolean, default=False,
                         nullable=False, comment="是否已发布")
    released_at = Column(String(30), nullable=True, comment="发布时间")

    # 回滚信息
    is_current = Column(Boolean, default=False,
                        nullable=False, comment="是否当前版本")
    previous_version_id = Column(Integer, ForeignKey(
        "system_versions.id"), nullable=True, comment="上一版本ID")

    # 部署信息
    commit_hash = Column(String(50), nullable=True, comment="Git提交哈希")
    deploy_user = Column(String(50), nullable=True, comment="部署人")

    # 备份信息
    backup_path = Column(String(500), nullable=True, comment="备份文件路径")
    backup_size = Column(Integer, default=0, comment="备份大小(字节)")
    backup_created_at = Column(String(30), nullable=True, comment="备份创建时间")

    def __repr__(self):
        return f"<SystemVersion(id={self.id}, version='{self.version}', released={self.is_released})>"
