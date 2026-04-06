"""
MCP 提供者模块

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from app.tools.mcp.providers.base_provider import BaseMCPProvider
from app.tools.mcp.providers.trends_provider import TrendsProvider
from app.tools.mcp.providers.search_hotnews_provider import SearchBasedHotNewsProvider

__all__ = [
    "BaseMCPProvider",
    "TrendsProvider",
    "SearchBasedHotNewsProvider"
]
