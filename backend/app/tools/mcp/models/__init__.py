"""
MCP 数据模型模块

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from app.tools.mcp.models.mcp_service import (
    MCPServiceConfig,
    MCPServiceStatus,
    MCPServiceType,
    PlatformConfig
)
from app.tools.mcp.models.mcp_response import (
    MCPResponse,
    MCPTrendingItem,
    MCPPlatformData,
    MCPError
)

__all__ = [
    # 服务配置
    "MCPServiceConfig",
    "MCPServiceStatus",
    "MCPServiceType",
    "PlatformConfig",
    # 响应模型
    "MCPResponse",
    "MCPTrendingItem",
    "MCPPlatformData",
    "MCPError",
]
