# MCP 提供者模块
from app.tools.mcp.providers.base_provider import BaseMCPProvider
from app.tools.mcp.providers.trends_provider import TrendsProvider
from app.tools.mcp.providers.search_hotnews_provider import SearchBasedHotNewsProvider

__all__ = [
    "BaseMCPProvider",
    "TrendsProvider",
    "SearchBasedHotNewsProvider"
]
