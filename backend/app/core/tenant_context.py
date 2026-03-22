"""
租户上下文管理
用于在请求中管理租户信息
"""
from typing import Optional
from contextvars import ContextVar
from fastapi import Request, HTTPException, status

from app.models import Tenant, TenantStatus


# 使用ContextVar存储当前请求的租户信息
_current_tenant: ContextVar[Optional[Tenant]] = ContextVar("current_tenant", default=None)
_current_tenant_id: ContextVar[Optional[int]] = ContextVar("current_tenant_id", default=None)


class TenantContext:
    """租户上下文管理类"""
    
    @staticmethod
    def set_tenant(tenant: Optional[Tenant]) -> None:
        """设置当前租户"""
        _current_tenant.set(tenant)
        if tenant:
            _current_tenant_id.set(tenant.id)
        else:
            _current_tenant_id.set(None)
    
    @staticmethod
    def get_tenant() -> Optional[Tenant]:
        """获取当前租户"""
        return _current_tenant.get()
    
    @staticmethod
    def get_tenant_id() -> Optional[int]:
        """获取当前租户ID"""
        return _current_tenant_id.get()
    
    @staticmethod
    def clear() -> None:
        """清除租户上下文"""
        _current_tenant.set(None)
        _current_tenant_id.set(None)
    
    @staticmethod
    def require_tenant() -> Tenant:
        """获取当前租户，如果不存在则抛出异常"""
        tenant = _current_tenant.get()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="租户上下文未设置"
            )
        return tenant
    
    @staticmethod
    def require_tenant_id() -> int:
        """获取当前租户ID，如果不存在则抛出异常"""
        tenant_id = _current_tenant_id.get()
        if tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="租户上下文未设置"
            )
        return tenant_id


def get_tenant_from_request(request: Request) -> Optional[int]:
    """
    从请求中提取租户ID
    
    支持以下方式：
    1. 从JWT Token中获取（推荐）
    2. 从请求头 X-Tenant-ID 获取
    3. 从子域名获取
    
    Args:
        request: FastAPI请求对象
    
    Returns:
        租户ID，如果无法确定则返回None
    """
    # 方式1：从请求状态中获取（已由认证中间件设置）
    if hasattr(request.state, "tenant_id"):
        return request.state.tenant_id
    
    # 方式2：从请求头获取
    tenant_id_header = request.headers.get("X-Tenant-ID")
    if tenant_id_header:
        try:
            return int(tenant_id_header)
        except ValueError:
            pass
    
    # 方式3：从子域名获取
    host = request.headers.get("host", "")
    if "." in host:
        subdomain = host.split(".")[0]
        # 这里可以查询数据库获取租户ID
        # 目前返回None，后续可以添加缓存查询
    
    return None


class TenantMiddleware:
    """租户中间件"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive, send)
        
        # 清除之前的租户上下文
        TenantContext.clear()
        
        # 继续处理请求
        await self.app(scope, receive, send)
        
        # 请求结束后清除上下文
        TenantContext.clear()


# 便捷函数
def get_current_tenant() -> Optional[Tenant]:
    """获取当前租户"""
    return TenantContext.get_tenant()


def get_current_tenant_id() -> Optional[int]:
    """获取当前租户ID"""
    return TenantContext.get_tenant_id()


def require_tenant() -> Tenant:
    """获取当前租户（必须存在）"""
    return TenantContext.require_tenant()


def require_tenant_id() -> int:
    """获取当前租户ID（必须存在）"""
    return TenantContext.require_tenant_id()
