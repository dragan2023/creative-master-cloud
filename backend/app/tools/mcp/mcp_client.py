"""
MCP 多内容提供商客户端
统一管理所有 MCP 服务，提供统一的调用接口

设计模式：策略模式 + 工厂模式
"""
from typing import Dict, List, Optional, Any
import asyncio
import time
from datetime import datetime

from app.core.logger import get_logger
from app.tools.mcp.mcp_config import get_mcp_config_manager, MCPConfigManager
from app.tools.mcp.mcp_cache import get_mcp_cache, MCPCache
from app.tools.mcp.models.mcp_service import (
    MCPServiceConfig,
    MCPServiceStatus,
    MCPServiceType
)
from app.tools.mcp.models.mcp_response import (
    MCPResponse,
    MCPPlatformData,
    MCPTrendingItem,
    MCPError,
    MCPErrorCode
)
from app.tools.mcp.providers.base_provider import BaseMCPProvider
from app.tools.mcp.providers.trends_provider import TrendsProvider
from app.tools.mcp.providers.search_hotnews_provider import SearchBasedHotNewsProvider


class MCPClient:
    """
    MCP 多内容提供商客户端

    职责：
    1. 管理所有 MCP 提供者的生命周期
    2. 提供统一的调用接口
    3. 处理缓存逻辑
    4. 提供健康检查和状态监控
    """

    # 提供者类映射
    PROVIDER_CLASSES = {
        "trends": TrendsProvider,
        "search_hotnews": SearchBasedHotNewsProvider,
    }

    def __init__(self):
        self.logger = get_logger("mcp_client")
        self.config_manager = get_mcp_config_manager()
        self.cache = get_mcp_cache()

        # 提供者实例
        self._providers: Dict[str, BaseMCPProvider] = {}

        # 初始化提供者
        self._initialize_providers()

    def _initialize_providers(self):
        """初始化所有启用的提供者"""
        if not self.config_manager.is_enabled:
            self.logger.info("MCP 服务未启用")
            return

        enabled_providers = self.config_manager.get_enabled_providers()

        for provider_name in enabled_providers:
            config = self.config_manager.get_service_config(provider_name)
            if not config:
                self.logger.warning(f"未找到配置: {provider_name}")
                continue

            provider_class = self.PROVIDER_CLASSES.get(provider_name)
            if not provider_class:
                self.logger.warning(f"未知的提供者: {provider_name}")
                continue

            try:
                provider = provider_class(config)
                self._providers[provider_name] = provider
                self.logger.info(f"已初始化 MCP 提供者: {provider_name}")
            except Exception as e:
                self.logger.error(f"初始化提供者失败 {provider_name}: {str(e)}")

    def get_provider(self, name: str) -> Optional[BaseMCPProvider]:
        """获取指定提供者"""
        return self._providers.get(name)

    def get_available_providers(self) -> List[str]:
        """获取所有可用提供者名称"""
        return list(self._providers.keys())

    async def get_trending_topics(
        self,
        platforms: Optional[List[str]] = None,
        provider: str = "search_hotnews",
        limit: int = 20,
        use_cache: bool = True,
        db_session=None,
        user_id: Optional[int] = None
    ) -> MCPResponse:
        """
        获取热点话题

        Args:
            platforms: 平台列表，如 ["weibo", "zhihu"]
            provider: 提供者名称（默认 search_hotnews）
            limit: 每个平台返回数量
            use_cache: 是否使用缓存
            db_session: 数据库会话（用于获取用户API Key）
            user_id: 用户ID

        Returns:
            MCPResponse 统一响应
        """
        # 检查 MCP 是否启用
        if not self.config_manager.is_enabled:
            return MCPResponse.create_error_response(
                provider=provider,
                error=MCPError(
                    code=MCPErrorCode.SERVICE_UNAVAILABLE,
                    message="MCP 服务未启用"
                )
            )

        # 获取提供者
        mcp_provider = self._providers.get(provider)
        if not mcp_provider:
            return MCPResponse.create_error_response(
                provider=provider,
                error=MCPError(
                    code=MCPErrorCode.INVALID_RESPONSE,
                    message=f"未找到提供者: {provider}"
                )
            )

        # 如果提供了db_session和user_id，设置到provider中
        if db_session and user_id and hasattr(mcp_provider, 'db_session'):
            mcp_provider.db_session = db_session
            mcp_provider.user_id = user_id
            self.logger.info(f"已设置Provider用户上下文: user_id={user_id}")
        elif not db_session or not user_id:
            self.logger.warning(
                f"未提供用户上下文: db_session={db_session is not None}, user_id={user_id}")

        # 构建缓存键
        cache_key = None
        if use_cache and self.config_manager.is_cache_enabled:
            platform_key = ",".join(sorted(platforms)) if platforms else "all"
            cache_key = f"trending:{provider}:{platform_key}:{limit}"

            # 尝试从缓存获取
            cached = self.cache.get(cache_key)
            if cached:
                self.logger.debug(f"缓存命中: {cache_key}")
                cached.from_cache = True
                return cached

        # 调用提供者
        start_time = time.time()
        try:
            response = await mcp_provider.get_trending_topics(platforms, limit)

            # 添加缓存信息
            response.cache_key = cache_key
            response.cache_ttl = self.config_manager.global_config.default_cache_ttl

            # 存入缓存
            if cache_key and response.success:
                self.cache.set(cache_key, response)
                self.logger.debug(f"已缓存: {cache_key}")

            return response

        except Exception as e:
            self.logger.error(f"获取热点数据失败: {str(e)}")
            return MCPResponse.create_error_response(
                provider=provider,
                error=MCPError(
                    code=MCPErrorCode.UNKNOWN,
                    message=str(e)
                )
            )

    async def get_platform_data(
        self,
        platform: str,
        provider: str = "search_hotnews",
        limit: int = 20
    ) -> MCPPlatformData:
        """
        获取指定平台数据

        Args:
            platform: 平台名称
            provider: 提供者名称（默认 search_hotnews）
            limit: 返回数量

        Returns:
            MCPPlatformData 平台数据
        """
        mcp_provider = self._providers.get(provider)
        if not mcp_provider:
            return MCPPlatformData(
                platform=platform,
                display_name=platform,
                is_available=False,
                error=MCPError(
                    code=MCPErrorCode.INVALID_RESPONSE,
                    message=f"未找到提供者: {provider}"
                )
            )

        return await mcp_provider.get_platform_data(platform, limit)

    async def health_check(self, provider: str = None) -> Dict[str, bool]:
        """
        健康检查

        Args:
            provider: 指定提供者，None 表示检查所有

        Returns:
            各提供者的健康状态
        """
        results = {}

        if provider:
            mcp_provider = self._providers.get(provider)
            if mcp_provider:
                results[provider] = await mcp_provider.health_check()
        else:
            for name, mcp_provider in self._providers.items():
                results[name] = await mcp_provider.health_check()

        return results

    async def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有提供者状态"""
        status = {}

        for name, provider in self._providers.items():
            status[name] = {
                "status": provider.status.value,
                "is_available": provider.is_available,
                "stats": provider.get_stats(),
                "service_info": provider.get_service_info()
            }

        return status

    def format_for_context(
        self,
        response: MCPResponse,
        max_items: int = 20
    ) -> str:
        """
        格式化响应数据为 LLM 上下文

        Args:
            response: MCP 响应
            max_items: 最大显示条目数

        Returns:
            格式化的文本
        """
        return response.format_for_context(max_items)

    def clear_cache(self, provider: str = None):
        """
        清除缓存

        Args:
            provider: 指定提供者，None 表示清除所有
        """
        if provider:
            pattern = f"trending:{provider}:*"
            self.cache.clear_pattern(pattern)
        else:
            self.cache.clear_all()

    def reload_providers(self):
        """重新加载提供者"""
        self.config_manager.reload_config()
        self._providers.clear()
        self._initialize_providers()
        self.logger.info("MCP 提供者已重新加载")


# 全局 MCP 客户端实例
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """获取 MCP 客户端实例"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


# 别名，保持向后兼容
mcp_client = None


def _get_mcp_client_instance():
    """延迟获取实例"""
    global mcp_client
    if mcp_client is None:
        mcp_client = get_mcp_client()
    return mcp_client
