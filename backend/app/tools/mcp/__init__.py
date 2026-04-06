"""
MCP 多内容提供商工具模块

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
# 核心客户端和缓存
from app.tools.mcp.mcp_client import MCPClient, get_mcp_client
from app.tools.mcp.mcp_cache import MCPCache, get_mcp_cache
from app.tools.mcp.mcp_config import MCPConfigManager, get_mcp_config_manager

# 数据模型
from app.tools.mcp.models import (
    MCPServiceConfig,
    MCPServiceStatus,
    MCPServiceType,
    PlatformConfig,
    MCPResponse,
    MCPTrendingItem,
    MCPPlatformData,
    MCPError,
)

# 提供者
from app.tools.mcp.providers import (
    BaseMCPProvider,
    TrendsProvider,
    SearchBasedHotNewsProvider,
)

__all__ = [
    # 核心类
    "MCPClient",
    "get_mcp_client",
    "MCPCache",
    "get_mcp_cache",
    "MCPConfigManager",
    "get_mcp_config_manager",
    # 数据模型
    "MCPServiceConfig",
    "MCPServiceStatus",
    "MCPServiceType",
    "PlatformConfig",
    "MCPResponse",
    "MCPTrendingItem",
    "MCPPlatformData",
    "MCPError",
    # 提供者
    "BaseMCPProvider",
    "TrendsProvider",
    "SearchBasedHotNewsProvider",
]
