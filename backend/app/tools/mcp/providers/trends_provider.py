"""
趋势聚合提供者
提供更深入的趋势分析和跨平台对比功能

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, List, Optional, Any
import asyncio
import time
from datetime import datetime

import httpx

from app.tools.mcp.providers.base_provider import BaseMCPProvider
from app.tools.mcp.models.mcp_service import (
    MCPServiceConfig,
    MCPServiceStatus,
    PlatformType
)
from app.tools.mcp.models.mcp_response import (
    MCPResponse,
    MCPPlatformData,
    MCPTrendingItem,
    MCPError,
    MCPErrorCode
)


class TrendsProvider(BaseMCPProvider):
    """
    趋势聚合提供者

    功能：
    - 跨平台趋势对比
    - 趋势变化追踪
    - 热度趋势分析
    """

    # 平台端点映射
    PLATFORM_ENDPOINTS = {
        PlatformType.WEIBO: "/trends/weibo",
        PlatformType.ZHIHU: "/trends/zhihu",
        PlatformType.DOUYIN: "/trends/douyin",
        PlatformType.BILIBILI: "/trends/bilibili",
    }

    def __init__(self, config: MCPServiceConfig):
        super().__init__(config)
        self._set_status(MCPServiceStatus.ACTIVE)
        self._trends_cache: Dict[str, List[Dict]] = {}

    async def get_trending_topics(
        self,
        platforms: Optional[List[str]] = None,
        limit: int = 20
    ) -> MCPResponse:
        """
        获取趋势话题

        Args:
            platforms: 平台列表
            limit: 每个平台返回的最大条目数

        Returns:
            MCPResponse 统一响应
        """
        start_time = time.time()

        target_platforms = self._get_target_platforms(platforms)

        if not target_platforms:
            return self._create_error_response(MCPError(
                code=MCPErrorCode.INVALID_RESPONSE,
                message="没有可用的平台配置"
            ))

        # 并发获取
        tasks = [
            self.get_platform_data(platform, limit)
            for platform in target_platforms
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        platform_data_list = []
        for platform, result in zip(target_platforms, results):
            if isinstance(result, MCPPlatformData):
                platform_data_list.append(result)
            elif isinstance(result, Exception):
                platform_data_list.append(self._create_platform_error_data(
                    platform,
                    MCPError(code=MCPErrorCode.UNKNOWN, message=str(result))
                ))

        duration_ms = int((time.time() - start_time) * 1000)

        return MCPResponse.create_success_response(
            provider=self.provider,
            service_type="trends",
            data=platform_data_list,
            duration_ms=duration_ms
        )

    async def get_platform_data(
        self,
        platform: str,
        limit: int = 20
    ) -> MCPPlatformData:
        """获取指定平台趋势数据"""
        try:
            platform_type = PlatformType(platform)
            endpoint = self.PLATFORM_ENDPOINTS.get(platform_type)

            if not endpoint:
                return self._create_platform_error_data(
                    platform,
                    MCPError(
                        code=MCPErrorCode.INVALID_RESPONSE,
                        message=f"不支持的平台: {platform}"
                    )
                )

            url = f"{self.endpoint}{endpoint}"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            items = self._parse_trends_response(data, platform, limit)

            return MCPPlatformData(
                platform=platform,
                display_name=self.get_platform_display_name(platform),
                items=items,
                total_count=len(items),
                is_available=True,
                source_url=url
            )

        except httpx.TimeoutException:
            return self._create_platform_error_data(
                platform,
                MCPError(code=MCPErrorCode.TIMEOUT, message="请求超时")
            )
        except Exception as e:
            return self._create_platform_error_data(
                platform,
                MCPError(code=MCPErrorCode.UNKNOWN, message=str(e))
            )

    async def get_cross_platform_analysis(
        self,
        platforms: List[str],
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        获取跨平台趋势分析

        Args:
            platforms: 要分析的平台列表
            limit: 分析条目数

        Returns:
            分析结果
        """
        response = await self.get_trending_topics(platforms, limit)

        if not response.success:
            return {"error": response.error.to_dict() if response.error else "Unknown error"}

        # 统计分析
        all_items = response.get_all_items()
        title_frequency: Dict[str, int] = {}

        for item in all_items:
            title = item.title.lower()
            title_frequency[title] = title_frequency.get(title, 0) + 1

        # 找出跨平台热点
        cross_platform_hot = [
            {"title": title, "count": count, "platforms": []}
            for title, count in sorted(
                title_frequency.items(),
                key=lambda x: x[1],
                reverse=True
            )
            if count > 1
        ][:10]

        return {
            "total_items": len(all_items),
            "platforms_analyzed": len(response.data),
            "cross_platform_hot": cross_platform_hot,
            "analysis_time": datetime.now().isoformat()
        }

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            url = f"{self.endpoint}/trends/weibo"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    self._set_status(MCPServiceStatus.ACTIVE)
                    return True
                else:
                    self._set_status(MCPServiceStatus.DEGRADED)
                    return False
        except Exception:
            self._set_status(MCPServiceStatus.ERROR)
            return False

    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "name": self.name,
            "provider": self.provider,
            "type": "trends",
            "endpoint": self.endpoint,
            "supported_platforms": list(self.PLATFORM_ENDPOINTS.keys()),
            "status": self._status.value,
            "stats": self.get_stats()
        }

    def _get_target_platforms(self, platforms: Optional[List[str]]) -> List[str]:
        """确定要查询的平台列表"""
        if platforms:
            return [p for p in platforms if p in self.PLATFORM_ENDPOINTS]

        enabled_platforms = []
        for platform_config in self.config.platforms:
            if platform_config.enabled:
                enabled_platforms.append(platform_config.platform.value)

        if not enabled_platforms:
            enabled_platforms = [
                p.value for p in self.PLATFORM_ENDPOINTS.keys()]

        return enabled_platforms

    def _parse_trends_response(
        self,
        data: Any,
        platform: str,
        limit: int
    ) -> List[MCPTrendingItem]:
        """解析趋势响应"""
        items = []

        if isinstance(data, list):
            raw_items = data
        elif isinstance(data, dict):
            raw_items = data.get("data", data.get("trends", []))
        else:
            return items

        for idx, item in enumerate(raw_items[:limit]):
            if not isinstance(item, dict):
                continue

            title = item.get("title") or item.get(
                "name") or item.get("keyword", "")
            if not title:
                continue

            trending_item = MCPTrendingItem(
                title=title,
                rank=idx + 1,
                hot_value=self._parse_hot_value(
                    item.get("hot") or item.get("trend_score")
                ),
                trend=item.get("trend_direction") or item.get("trend"),
                url=item.get("url", ""),
                platform=platform,
                extra={
                    "change_rate": item.get("change_rate"),
                    "peak_time": item.get("peak_time"),
                    "duration": item.get("duration")
                }
            )
            items.append(trending_item)

        return items
