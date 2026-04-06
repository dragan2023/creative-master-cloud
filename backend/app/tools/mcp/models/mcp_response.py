"""
MCP 响应数据结构
定义 MCP 服务的响应数据模型

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MCPErrorCode(str, Enum):
    """MCP 错误码"""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    RATE_LIMIT = "rate_limit"
    INVALID_RESPONSE = "invalid_response"
    SERVICE_UNAVAILABLE = "service_unavailable"
    AUTH_ERROR = "auth_error"
    UNKNOWN = "unknown"
    # 新增错误码
    PARTIAL_FAILURE = "partial_failure"
    NO_DATA = "no_data"
    INVALID_PARAMS = "invalid_params"


@dataclass
class MCPError:
    """MCP 错误信息"""
    code: MCPErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None
    retry_after: Optional[int] = None  # 重试等待时间（秒）

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "code": self.code.value,
            "message": self.message
        }
        if self.details:
            result["details"] = self.details
        if self.retry_after:
            result["retry_after"] = self.retry_after
        return result


@dataclass
class MCPTrendingItem:
    """热点条目"""
    # 基本信息
    title: str
    rank: int = 0

    # 热度信息
    hot_value: Optional[str] = None  # 热度值（字符串，因为格式不统一）
    hot_label: Optional[str] = None   # 热度标签，如 "爆"、"热"
    trend: Optional[str] = None       # 趋势方向：up/down/new/stable

    # 链接信息
    url: Optional[str] = None
    mobile_url: Optional[str] = None

    # 来源信息
    platform: Optional[str] = None
    category: Optional[str] = None    # 分类，如 "娱乐"、"科技"

    # 时间信息
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # 扩展数据
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "title": self.title,
            "rank": self.rank,
            "hot_value": self.hot_value,
            "hot_label": self.hot_label,
            "trend": self.trend,
            "url": self.url,
            "platform": self.platform
        }
        if self.mobile_url:
            result["mobile_url"] = self.mobile_url
        if self.category:
            result["category"] = self.category
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            result["updated_at"] = self.updated_at.isoformat()
        if self.extra:
            result["extra"] = self.extra
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPTrendingItem":
        """从字典创建"""
        return cls(
            title=data.get("title", ""),
            rank=data.get("rank", 0),
            hot_value=data.get("hot_value") or data.get(
                "hot") or data.get("heat"),
            hot_label=data.get("hot_label") or data.get("label"),
            trend=data.get("trend"),
            url=data.get("url") or data.get("link"),
            mobile_url=data.get("mobile_url"),
            platform=data.get("platform"),
            category=data.get("category"),
            extra=data.get("extra", {})
        )


@dataclass
class MCPPlatformData:
    """平台数据集合"""
    platform: str
    display_name: str
    items: List[MCPTrendingItem] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=datetime.now)
    total_count: int = 0
    source_url: Optional[str] = None

    # 平台状态
    is_available: bool = True
    error: Optional[MCPError] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "items": [item.to_dict() for item in self.items],
            "fetched_at": self.fetched_at.isoformat(),
            "total_count": self.total_count or len(self.items),
            "source_url": self.source_url,
            "is_available": self.is_available,
            "error": self.error.to_dict() if self.error else None
        }

    @property
    def item_count(self) -> int:
        return len(self.items)


@dataclass
class MCPResponse:
    """MCP 统一响应结构"""
    # 状态信息
    success: bool
    provider: str
    service_type: str

    # 数据
    data: List[MCPPlatformData] = field(default_factory=list)

    # 元数据
    total_items: int = 0
    platforms_count: int = 0
    fetched_at: datetime = field(default_factory=datetime.now)
    duration_ms: int = 0

    # 缓存信息
    from_cache: bool = False
    cache_key: Optional[str] = None
    cache_ttl: int = 0

    # 错误信息
    error: Optional[MCPError] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "provider": self.provider,
            "service_type": self.service_type,
            "data": [d.to_dict() for d in self.data],
            "total_items": self.total_items,
            "platforms_count": self.platforms_count,
            "fetched_at": self.fetched_at.isoformat(),
            "duration_ms": self.duration_ms,
            "from_cache": self.from_cache,
            "cache_key": self.cache_key,
            "cache_ttl": self.cache_ttl,
            "error": self.error.to_dict() if self.error else None
        }

    def get_all_items(self) -> List[MCPTrendingItem]:
        """获取所有热点条目"""
        all_items = []
        for platform_data in self.data:
            all_items.extend(platform_data.items)
        return all_items

    def get_items_by_platform(self, platform: str) -> List[MCPTrendingItem]:
        """获取指定平台的热点条目"""
        for platform_data in self.data:
            if platform_data.platform == platform:
                return platform_data.items
        return []

    def format_for_context(self, max_items: int = 20) -> str:
        """
        格式化为 LLM 上下文

        Args:
            max_items: 最大显示条目数

        Returns:
            格式化的文本
        """
        if not self.success or not self.data:
            return ""

        parts = ["## 📰 实时热点资讯（必须参考）\n"]
        parts.append(
            "> ⚠️ **重要指令**：以下热点数据来自社交媒体实时热点，你**必须**从中选择1-3个与创作主题相关的热点进行融合创作。\n")
        parts.append("> 在创作内容中，请明确标注你参考了哪些热点（例如：\"参考热点：XXX\"）。\n")

        # 平台显示名称映射
        platform_names = {
            "weibo": "微博热搜",
            "zhihu": "知乎热榜",
            "douyin": "抖音热点",
            "bilibili": "B站热门",
            "xiaohongshu": "小红书热门",
            "toutiao": "今日头条",
            "36kr": "36氪科技",
            "douban": "豆瓣热门",
            "baidu": "百度热搜",
        }

        total_shown = 0
        for platform_data in self.data:
            if not platform_data.is_available or not platform_data.items:
                continue

            if total_shown >= max_items:
                break

            platform_name = platform_names.get(
                platform_data.platform,
                platform_data.display_name or platform_data.platform
            )
            parts.append(f"\n### {platform_name}\n")

            for item in platform_data.items[:5]:
                if total_shown >= max_items:
                    break

                title = item.title
                hot = item.hot_value

                if hot:
                    parts.append(f"- {title} (热度: {hot})")
                else:
                    parts.append(f"- {title}")
                total_shown += 1

        parts.append("\n---")
        parts.append("\n**💡 创作要求**：")
        parts.append("1. 从上述热点中选择1-3个与你的创作主题相关的话题")
        parts.append("2. 将热点元素自然融入你的创作内容中")
        parts.append("3. 在内容末尾明确标注：\"📌 参考热点：[热点名称]\"\n")

        return "\n".join(parts)

    @classmethod
    def create_error_response(
        cls,
        provider: str,
        error: MCPError
    ) -> "MCPResponse":
        """创建错误响应"""
        return cls(
            success=False,
            provider=provider,
            service_type="unknown",
            error=error
        )

    @classmethod
    def create_success_response(
        cls,
        provider: str,
        service_type: str,
        data: List[MCPPlatformData],
        duration_ms: int = 0
    ) -> "MCPResponse":
        """创建成功响应"""
        total_items = sum(len(d.items) for d in data)
        return cls(
            success=True,
            provider=provider,
            service_type=service_type,
            data=data,
            total_items=total_items,
            platforms_count=len(data),
            duration_ms=duration_ms
        )
