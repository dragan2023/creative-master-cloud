"""
MCP 配置管理模块
集中管理所有 MCP 服务的配置
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.logger import get_logger
from app.tools.mcp.models.mcp_service import (
    MCPServiceConfig,
    MCPServiceType,
    MCPServiceStatus,
    PlatformConfig,
    DEFAULT_SERVICES,
    get_default_service_config
)


@dataclass
class MCPGlobalConfig:
    """MCP 全局配置"""
    # 总开关
    enabled: bool = True

    # 缓存配置
    cache_enabled: bool = True
    default_cache_ttl: int = 1800  # 30分钟

    # 请求配置
    default_timeout: float = 15.0
    max_retries: int = 3
    retry_delay: float = 1.0

    # 并发配置
    max_concurrent_requests: int = 5
    request_delay: float = 0.1  # 请求间隔（秒）

    # 启用的提供者列表
    enabled_providers: List[str] = field(
        default_factory=lambda: ["search_hotnews"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cache_enabled": self.cache_enabled,
            "default_cache_ttl": self.default_cache_ttl,
            "default_timeout": self.default_timeout,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "max_concurrent_requests": self.max_concurrent_requests,
            "request_delay": self.request_delay,
            "enabled_providers": self.enabled_providers
        }


class MCPConfigManager:
    """
    MCP 配置管理器

    职责：
    1. 从 Settings 加载配置
    2. 管理服务配置的生命周期
    3. 提供配置查询接口
    """

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger("mcp_config")

        # 全局配置
        self._global_config = self._load_global_config()

        # 服务配置缓存
        self._service_configs: Dict[str, MCPServiceConfig] = {}

        # 加载所有启用的服务配置
        self._load_service_configs()

    def _load_global_config(self) -> MCPGlobalConfig:
        """加载全局配置"""
        return MCPGlobalConfig(
            enabled=self.settings.MCP_ENABLED,
            cache_enabled=self.settings.MCP_CACHE_ENABLED,
            default_cache_ttl=self.settings.MCP_CACHE_TTL,
            default_timeout=15.0,
            max_retries=3,
            retry_delay=1.0,
            max_concurrent_requests=5,
            request_delay=0.1,
            enabled_providers=self._parse_providers()
        )

    def _parse_providers(self) -> List[str]:
        """解析启用的提供者列表"""
        providers_str = self.settings.MCP_PROVIDERS
        if not providers_str:
            return ["search_hotnews"]  # 默认启用 search_hotnews

        providers = [p.strip() for p in providers_str.split(",") if p.strip()]
        return providers

    def _load_service_configs(self):
        """加载所有启用的服务配置"""
        for provider in self._global_config.enabled_providers:
            # 检查是否在 settings 中启用
            if provider == "hotnews" and not self.settings.MCP_HOTNEWS_ENABLED:
                continue
            if provider == "search_hotnews":
                # search_hotnews 不需要额外检查，直接加载
                pass

            # 加载配置
            config = self._load_service_config(provider)
            if config:
                self._service_configs[provider] = config
                self.logger.info(f"已加载 MCP 服务配置: {provider}")

    def _load_service_config(self, provider: str) -> Optional[MCPServiceConfig]:
        """加载单个服务配置"""
        # 获取默认配置
        default_config = get_default_service_config(provider)
        if not default_config:
            self.logger.warning(f"未找到默认配置: {provider}")
            return None

        # 从 settings 覆盖特定配置
        if provider == "hotnews":
            default_config.endpoint = self.settings.MCP_HOTNEWS_API_URL

        return default_config

    @property
    def global_config(self) -> MCPGlobalConfig:
        """获取全局配置"""
        return self._global_config

    @property
    def is_enabled(self) -> bool:
        """检查 MCP 是否启用"""
        return self._global_config.enabled

    @property
    def is_cache_enabled(self) -> bool:
        """检查缓存是否启用"""
        return self._global_config.cache_enabled

    def get_service_config(self, provider: str) -> Optional[MCPServiceConfig]:
        """获取指定服务的配置"""
        return self._service_configs.get(provider)

    def get_all_service_configs(self) -> Dict[str, MCPServiceConfig]:
        """获取所有服务配置"""
        return self._service_configs.copy()

    def get_enabled_providers(self) -> List[str]:
        """获取所有启用的提供者"""
        return list(self._service_configs.keys())

    def is_provider_enabled(self, provider: str) -> bool:
        """检查指定提供者是否启用"""
        return provider in self._service_configs

    def get_platform_config(
        self,
        provider: str,
        platform: str
    ) -> Optional[PlatformConfig]:
        """获取指定平台配置"""
        service_config = self._service_configs.get(provider)
        if not service_config:
            return None

        for platform_config in service_config.platforms:
            if platform_config.platform.value == platform:
                return platform_config

        return None

    def get_enabled_platforms(self, provider: str) -> List[str]:
        """获取指定提供者启用的平台列表"""
        service_config = self._service_configs.get(provider)
        if not service_config:
            return []

        return [
            p.platform.value
            for p in service_config.platforms
            if p.enabled
        ]

    def update_service_config(
        self,
        provider: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        更新服务配置

        Args:
            provider: 提供者名称
            updates: 更新内容

        Returns:
            是否更新成功
        """
        config = self._service_configs.get(provider)
        if not config:
            return False

        # 更新配置
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)

        self.logger.info(f"已更新服务配置: {provider}")
        return True

    def reload_config(self):
        """重新加载配置"""
        self._global_config = self._load_global_config()
        self._service_configs.clear()
        self._load_service_configs()
        self.logger.info("MCP 配置已重新加载")

    def to_dict(self) -> Dict[str, Any]:
        """导出配置为字典"""
        return {
            "global": self._global_config.to_dict(),
            "services": {
                name: config.to_dict()
                for name, config in self._service_configs.items()
            }
        }


# 全局配置管理器实例
_mcp_config_manager: Optional[MCPConfigManager] = None


def get_mcp_config_manager() -> MCPConfigManager:
    """获取 MCP 配置管理器实例"""
    global _mcp_config_manager
    if _mcp_config_manager is None:
        _mcp_config_manager = MCPConfigManager()
    return _mcp_config_manager
