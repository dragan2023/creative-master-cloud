"""
MCP 提供者基础抽象类
定义所有 MCP 提供者必须实现的接口

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import time

from app.core.logger import get_logger
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


class BaseMCPProvider(ABC):
    """
    MCP 提供者基础抽象类

    所有 MCP 提供者必须继承此类并实现抽象方法
    """

    def __init__(self, config: MCPServiceConfig):
        """
        初始化提供者

        Args:
            config: 服务配置
        """
        self.config = config
        self.name = config.name
        self.provider = config.provider
        self.endpoint = config.endpoint
        self.api_key = config.api_key
        self.timeout = config.timeout
        self.max_retries = config.max_retries

        # 状态
        self._status = MCPServiceStatus.INACTIVE
        self._last_error: Optional[MCPError] = None
        self._last_success_time: Optional[datetime] = None
        self._request_count = 0
        self._error_count = 0

        # 日志
        self.logger = get_logger(f"mcp_provider_{self.provider}")

    @abstractmethod
    async def get_trending_topics(
        self,
        platforms: Optional[List[str]] = None,
        limit: int = 20
    ) -> MCPResponse:
        """
        获取热点话题

        Args:
            platforms: 平台列表，None 表示获取所有平台
            limit: 每个平台返回的最大条目数

        Returns:
            MCPResponse 统一响应
        """
        pass

    @abstractmethod
    async def get_platform_data(
        self,
        platform: str,
        limit: int = 20
    ) -> MCPPlatformData:
        """
        获取指定平台数据

        Args:
            platform: 平台名称
            limit: 返回的最大条目数

        Returns:
            MCPPlatformData 平台数据
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            服务是否可用
        """
        pass

    @abstractmethod
    def get_service_info(self) -> Dict[str, Any]:
        """
        获取服务信息

        Returns:
            服务详细信息
        """
        pass

    @property
    def status(self) -> MCPServiceStatus:
        """获取当前状态"""
        return self._status

    @property
    def is_available(self) -> bool:
        """检查服务是否可用"""
        return self._status in [MCPServiceStatus.ACTIVE, MCPServiceStatus.DEGRADED]

    @property
    def last_error(self) -> Optional[MCPError]:
        """获取最后的错误"""
        return self._last_error

    def _set_status(self, status: MCPServiceStatus):
        """设置状态"""
        self._status = status
        self.logger.debug(f"状态变更: {status.value}")

    def _record_success(self):
        """记录成功请求"""
        self._last_success_time = datetime.now()
        self._request_count += 1
        self._set_status(MCPServiceStatus.ACTIVE)

    def _record_error(self, error: MCPError):
        """记录错误"""
        self._last_error = error
        self._error_count += 1
        self._request_count += 1

        # 根据错误类型调整状态
        if error.code in [MCPErrorCode.TIMEOUT, MCPErrorCode.NETWORK_ERROR]:
            self._set_status(MCPServiceStatus.DEGRADED)
        elif error.code == MCPErrorCode.SERVICE_UNAVAILABLE:
            self._set_status(MCPServiceStatus.ERROR)
        else:
            # 其他错误，保持当前状态
            pass

    async def _execute_with_retry(
        self,
        operation,
        *args,
        **kwargs
    ) -> Any:
        """
        带重试的操作执行

        Args:
            operation: 要执行的异步操作
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            操作结果
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                result = await operation(*args, **kwargs)
                self._record_success()
                return result

            except asyncio.TimeoutError:
                last_error = MCPError(
                    code=MCPErrorCode.TIMEOUT,
                    message=f"请求超时 (尝试 {attempt + 1}/{self.max_retries})",
                    retry_after=2 ** attempt  # 指数退避
                )
                self.logger.warning(last_error.message)

            except Exception as e:
                last_error = MCPError(
                    code=MCPErrorCode.UNKNOWN,
                    message=f"请求异常: {str(e)} (尝试 {attempt + 1}/{self.max_retries})"
                )
                self.logger.warning(last_error.message)

            # 等待重试
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        # 所有重试失败
        self._record_error(last_error)
        raise Exception(last_error.message)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "provider": self.provider,
            "status": self._status.value,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(1, self._request_count),
            "last_success": self._last_success_time.isoformat() if self._last_success_time else None,
            "last_error": self._last_error.to_dict() if self._last_error else None
        }

    def get_platform_display_name(self, platform: str) -> str:
        """获取平台显示名称"""
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
        return platform_names.get(platform, platform)

    def _parse_hot_value(self, value: Any) -> Optional[str]:
        """解析热度值"""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            # 格式化数字
            if value >= 100000000:
                return f"{value / 100000000:.1f}亿"
            elif value >= 10000:
                return f"{value / 10000:.1f}万"
            else:
                return str(int(value))

        return str(value)

    def _create_error_response(self, error: MCPError) -> MCPResponse:
        """创建错误响应"""
        return MCPResponse.create_error_response(
            provider=self.provider,
            error=error
        )

    def _create_platform_error_data(
        self,
        platform: str,
        error: MCPError
    ) -> MCPPlatformData:
        """创建平台错误数据"""
        return MCPPlatformData(
            platform=platform,
            display_name=self.get_platform_display_name(platform),
            items=[],
            is_available=False,
            error=error
        )
