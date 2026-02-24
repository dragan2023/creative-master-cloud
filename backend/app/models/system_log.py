"""
系统日志模型
用于管理员查看系统运行日志
"""
from sqlalchemy import Column, String, Text, Enum
import enum

from app.models.base import BaseModel


class LogLevel(str, enum.Enum):
    """日志级别枚举"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SystemLog(BaseModel):
    """系统日志表"""
    __tablename__ = "system_logs"
    
    level = Column(
        Enum(LogLevel),
        nullable=False,
        index=True,
        comment="日志级别"
    )
    user_id = Column(String(50), nullable=True, index=True, comment="用户ID")
    module = Column(String(50), nullable=True, comment="模块名称")
    action = Column(String(100), nullable=True, comment="操作动作")
    message = Column(Text, nullable=False, comment="日志消息")
    request_id = Column(String(50), nullable=True, index=True, comment="请求ID")
    ip_address = Column(String(50), nullable=True, comment="IP地址")
    user_agent = Column(String(255), nullable=True, comment="用户代理")
    extra_data = Column(Text, nullable=True, comment="额外数据 (JSON格式)")
    stack_trace = Column(Text, nullable=True, comment="堆栈信息")
    
    def __repr__(self):
        return f"<SystemLog(id={self.id}, level={self.level}, module='{self.module}')>"
