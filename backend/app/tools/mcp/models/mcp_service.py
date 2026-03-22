"""
MCP 服务定义模型
定义 MCP 服务的配置、状态和类型
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class MCPServiceType(str, Enum):
    """MCP 服务类型枚举"""
    HOT_NEWS = "hot_news"           # 热点新闻聚合
    TRENDS = "trends"               # 趋势聚合
    CONTENT_FETCH = "content_fetch"  # 内容抓取
    AI_RESOURCE = "ai_resource"     # AI资源发现
    ANALYTICS = "analytics"         # 数据分析


class MCPServiceStatus(str, Enum):
    """MCP 服务状态枚举"""
    ACTIVE = "active"           # 正常运行
    DEGRADED = "degraded"       # 降级运行
    INACTIVE = "inactive"       # 未激活
    ERROR = "error"             # 错误状态
    MAINTENANCE = "maintenance"  # 维护中


class PlatformType(str, Enum):
    """支持的社交平台类型"""
    WEIBO = "weibo"             # 微博
    ZHIHU = "zhihu"             # 知乎
    DOUYIN = "douyin"           # 抖音
    BILIBILI = "bilibili"       # B站
    XIAOHONGSHU = "xiaohongshu"  # 小红书
    TOUTIAO = "toutiao"         # 今日头条
    KR36 = "36kr"               # 36氪
    DOUBAN = "douban"           # 豆瓣
    BAIDU = "baidu"             # 百度
    ZHIHU_DAILY = "zhihu_daily"  # 知乎日报


@dataclass
class PlatformConfig:
    """平台配置"""
    platform: PlatformType
    enabled: bool = True
    endpoint: str = ""
    cache_ttl: int = 1800  # 默认30分钟
    priority: int = 0      # 优先级，数值越高越优先
    max_items: int = 20    # 最大返回条目数
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "enabled": self.enabled,
            "endpoint": self.endpoint,
            "cache_ttl": self.cache_ttl,
            "priority": self.priority,
            "max_items": self.max_items,
            "extra_params": self.extra_params
        }


@dataclass
class MCPServiceConfig:
    """MCP 服务配置"""
    # 基本信息
    name: str
    service_type: MCPServiceType
    provider: str  # 提供者名称，如 "hotnews", "modelscope"

    # 连接配置
    endpoint: str
    api_key: Optional[str] = None
    timeout: float = 15.0
    max_retries: int = 3

    # 功能配置
    enabled: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 1800  # 默认30分钟

    # 平台配置（针对热点/趋势类服务）
    platforms: List[PlatformConfig] = field(default_factory=list)

    # 元数据
    description: str = ""
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)

    # 创建和更新时间
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "service_type": self.service_type.value,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "api_key": "***" if self.api_key else None,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "enabled": self.enabled,
            "cache_enabled": self.cache_enabled,
            "cache_ttl": self.cache_ttl,
            "platforms": [p.to_dict() for p in self.platforms],
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServiceConfig":
        """从字典创建配置"""
        platforms = [
            PlatformConfig(
                platform=PlatformType(p["platform"]),
                enabled=p.get("enabled", True),
                endpoint=p.get("endpoint", ""),
                cache_ttl=p.get("cache_ttl", 1800),
                priority=p.get("priority", 0),
                max_items=p.get("max_items", 20),
                extra_params=p.get("extra_params", {})
            )
            for p in data.get("platforms", [])
        ]

        return cls(
            name=data["name"],
            service_type=MCPServiceType(data["service_type"]),
            provider=data["provider"],
            endpoint=data["endpoint"],
            api_key=data.get("api_key"),
            timeout=data.get("timeout", 15.0),
            max_retries=data.get("max_retries", 3),
            enabled=data.get("enabled", True),
            cache_enabled=data.get("cache_enabled", True),
            cache_ttl=data.get("cache_ttl", 1800),
            platforms=platforms,
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            tags=data.get("tags", [])
        )


# 预定义的服务配置模板
DEFAULT_SERVICES: Dict[str, MCPServiceConfig] = {
    "hotnews": MCPServiceConfig(
        name="HotNews 中文社交媒体热点",
        service_type=MCPServiceType.HOT_NEWS,
        provider="hotnews",
        endpoint="official",  # 使用各平台官方API直连
        description="聚合微博、百度、知乎、B站等平台实时热点（官方API直连）",
        tags=["热点", "社交媒体", "中文"],
        platforms=[
            PlatformConfig(PlatformType.WEIBO, priority=10),
            PlatformConfig(PlatformType.BAIDU, priority=9),
            PlatformConfig(PlatformType.ZHIHU, priority=8),
            PlatformConfig(PlatformType.BILIBILI, priority=7),
            PlatformConfig(PlatformType.DOUYIN, priority=6),
            PlatformConfig(PlatformType.TOUTIAO, priority=5),
            PlatformConfig(PlatformType.KR36, priority=4),
            PlatformConfig(PlatformType.DOUBAN, priority=3),
        ]
    ),
    "search_hotnews": MCPServiceConfig(
        name="搜索聚合热点服务",
        service_type=MCPServiceType.HOT_NEWS,
        provider="search_hotnews",
        endpoint="search",  # 使用搜索引擎API
        description="通过国内搜索引擎API聚合热点数据，需要配置博查AI或百度搜索的API Key",
        tags=["热点", "搜索", "国产化"],
        platforms=[
            PlatformConfig(PlatformType.WEIBO, priority=10),
            PlatformConfig(PlatformType.ZHIHU, priority=8),
            PlatformConfig(PlatformType.DOUYIN, priority=6),
            PlatformConfig(PlatformType.BILIBILI, priority=7),
        ]
    ),
    "trends": MCPServiceConfig(
        name="Chinese Trends Hub",
        service_type=MCPServiceType.TRENDS,
        provider="trends",
        endpoint="official",  # 使用各平台官方API直连
        description="中文平台趋势聚合分析（官方API直连）",
        tags=["趋势", "分析", "聚合"],
        platforms=[
            PlatformConfig(PlatformType.WEIBO),
            PlatformConfig(PlatformType.BAIDU),
            PlatformConfig(PlatformType.ZHIHU),
            PlatformConfig(PlatformType.BILIBILI),
        ]
    )
}


def get_default_service_config(provider: str) -> Optional[MCPServiceConfig]:
    """获取默认服务配置"""
    return DEFAULT_SERVICES.get(provider)
