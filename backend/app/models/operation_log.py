"""
操作日志模型
用于审计和追踪用户操作
"""
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class OperationLog(BaseModel):
    """操作日志表"""
    __tablename__ = "operation_logs"

    # 操作者信息
    user_id = Column(Integer, nullable=True, index=True, comment="操作用户ID")
    username = Column(String(50), nullable=True, comment="操作用户名")
    tenant_id = Column(Integer, nullable=True, index=True, comment="租户ID")
    
    # 操作信息
    action = Column(String(50), nullable=False, index=True, comment="操作类型")
    module = Column(String(50), nullable=True, comment="操作模块")
    description = Column(Text, nullable=True, comment="操作描述")
    
    # 请求信息
    request_method = Column(String(10), nullable=True, comment="请求方法")
    request_path = Column(String(255), nullable=True, comment="请求路径")
    request_params = Column(Text, nullable=True, comment="请求参数")
    request_body = Column(Text, nullable=True, comment="请求体")
    
    # 响应信息
    response_status = Column(Integer, nullable=True, comment="响应状态码")
    response_time_ms = Column(Integer, nullable=True, comment="响应时间(毫秒)")
    
    # 客户端信息
    ip_address = Column(String(50), nullable=True, comment="IP地址")
    user_agent = Column(String(255), nullable=True, comment="用户代理")
    
    # 资源信息
    resource_type = Column(String(50), nullable=True, comment="资源类型")
    resource_id = Column(Integer, nullable=True, comment="资源ID")
    
    # 额外数据
    extra_data = Column(JSON, nullable=True, comment="额外数据")
    
    # 状态
    status = Column(String(20), default="success", comment="操作状态(success/failed)")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    # 创建时间索引
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="创建时间")
    
    # 索引
    __table_args__ = (
        Index('ix_operation_logs_tenant_created', 'tenant_id', 'created_at'),
        Index('ix_operation_logs_user_created', 'user_id', 'created_at'),
        Index('ix_operation_logs_action_created', 'action', 'created_at'),
    )
    
    def __repr__(self):
        return f"<OperationLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"
    
    def to_dict(self, exclude: list = None) -> dict:
        exclude = exclude or []
        return super().to_dict(exclude)


# 操作类型常量
class ActionType:
    """操作类型常量"""
    # 用户相关
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTER = "user_register"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_PASSWORD_CHANGE = "user_password_change"
    USER_PASSWORD_RESET = "user_password_reset"
    
    # 租户相关
    TENANT_CREATE = "tenant_create"
    TENANT_UPDATE = "tenant_update"
    TENANT_DELETE = "tenant_delete"
    TENANT_SUSPEND = "tenant_suspend"
    TENANT_ACTIVATE = "tenant_activate"
    
    # 项目相关
    PROJECT_CREATE = "project_create"
    PROJECT_UPDATE = "project_update"
    PROJECT_DELETE = "project_delete"
    PROJECT_EXPORT = "project_export"
    
    # 知识库相关
    KB_CREATE = "kb_create"
    KB_UPDATE = "kb_update"
    KB_DELETE = "kb_delete"
    KB_UPLOAD = "kb_upload"
    
    # API Key相关
    APIKEY_CREATE = "apikey_create"
    APIKEY_DELETE = "apikey_delete"
    
    # 系统相关
    SYSTEM_CONFIG_UPDATE = "system_config_update"
    SYSTEM_BACKUP = "system_backup"
    SYSTEM_RESTORE = "system_restore"
    
    # 管理员相关
    ADMIN_LOGIN = "admin_login"
    ADMIN_USER_MANAGE = "admin_user_manage"
    ADMIN_TENANT_MANAGE = "admin_tenant_manage"


class ModuleType:
    """模块类型常量"""
    AUTH = "auth"
    USER = "user"
    TENANT = "tenant"
    PROJECT = "project"
    KNOWLEDGE = "knowledge"
    GENERATION = "generation"
    SYSTEM = "system"
    ADMIN = "admin"
