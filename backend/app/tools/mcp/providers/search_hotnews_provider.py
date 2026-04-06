"""
基于联网搜索的热点聚合提供者

通过搜索引擎API聚合热点数据，支持博查AI搜索和百度搜索
用户需要在前端配置搜索服务的API Key

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, List, Optional, Any
import asyncio
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.core.security import api_key_encryption
from app.core.logger import get_logger

logger = get_logger(__name__)


# 搜索策略配置（精简为4个核心平台，减少API调用次数）
SEARCH_STRATEGIES = {
    PlatformType.WEIBO: {
        "keywords": ["weibo hot search today trending", "微博热搜榜 今日热点", "sina weibo trending topics china"],
        "platform": "微博热搜",
        "priority": 1
    },
    PlatformType.ZHIHU: {
        "keywords": ["zhihu trending topics questions", "知乎热榜 今日热门问题", "zhihu hot questions china"],
        "platform": "知乎热榜",
        "priority": 2
    },
    PlatformType.DOUYIN: {
        "keywords": ["douyin trending videos china", "抖音热点 今日热门视频", "tiktok china hot trends"],
        "platform": "抖音热点",
        "priority": 3
    },
    PlatformType.BILIBILI: {
        "keywords": ["bilibili popular videos ranking", "B站热门 今日排行榜", "bilibili hot videos china"],
        "platform": "B站热门",
        "priority": 4
    }
}


class SearchBasedHotNewsProvider(BaseMCPProvider):
    """
    基于联网搜索的热点聚合提供者

    功能：
    - 使用用户配置的搜索API Key（博查AI/百度）
    - 通过搜索策略聚合各平台热点数据
    - 支持多搜索引擎降级（博查AI优先，百度备用）
    """

    def __init__(self, config: MCPServiceConfig, db_session: Optional[AsyncSession] = None, user_id: Optional[int] = None):
        """
        初始化提供者

        Args:
            config: 服务配置
            db_session: 数据库会话（用于获取用户API Key）
            user_id: 用户ID
        """
        super().__init__(config)
        self.db_session = db_session
        self.user_id = user_id
        self._search_api_keys: Dict[str, str] = {}  # 缓存搜索API Key

    async def _get_user_search_api_key(self, provider: str) -> Optional[str]:
        """
        获取用户配置的搜索API Key

        Args:
            provider: 搜索服务提供商 (bocha/baidu)

        Returns:
            API Key或None
        """
        if not self.db_session or not self.user_id:
            self.logger.warning(
                f"获取搜索API Key失败: db_session={self.db_session is not None}, user_id={self.user_id}")
            return None

        # 检查缓存
        if provider in self._search_api_keys:
            return self._search_api_keys[provider]

        try:
            from app.models import UserAPIKey

            result = await self.db_session.execute(
                select(UserAPIKey).where(
                    UserAPIKey.user_id == self.user_id,
                    UserAPIKey.provider == provider,
                    UserAPIKey.is_valid == True
                ).order_by(UserAPIKey.is_default.desc())
            )
            api_key_record = result.scalar_one_or_none()

            if api_key_record:
                decrypted_key = api_key_encryption.decrypt(
                    api_key_record.encrypted_key)
                self._search_api_keys[provider] = decrypted_key
                self.logger.info(f"成功获取用户搜索API Key: provider={provider}")
                return decrypted_key
            else:
                self.logger.warning(
                    f"未找到用户的搜索API Key: provider={provider}, user_id={self.user_id}")

        except Exception as e:
            self.logger.error(f"获取用户搜索API Key失败: {str(e)}")

        return None

    async def _search_with_fallback(
        self,
        query: str,
        num_results: int = 10
    ) -> tuple:
        """
        使用搜索引擎执行搜索，支持降级（国内服务优先）

        降级顺序：博查AI搜索 → 百度搜索

        Args:
            query: 搜索查询
            num_results: 结果数量

        Returns:
            (搜索结果列表, 使用的引擎名称)
        """
        from app.tools.web_search import search_with_user_api_key

        self.logger.info(f"开始搜索: query={query[:50]}...")

        # 1. 首先尝试博查AI搜索（国内服务，专为AI应用优化）
        bocha_key = await self._get_user_search_api_key("bocha")
        if bocha_key:
            self.logger.info(f"使用博查AI搜索...")
            try:
                results = await search_with_user_api_key(
                    query=query,
                    provider="bocha",
                    api_key=bocha_key,
                    num_results=num_results
                )
                if results and not any("error" in r for r in results):
                    self.logger.info(f"博查AI搜索成功: {len(results)}条结果")
                    return results, "bocha"
                else:
                    self.logger.warning(f"博查AI搜索返回空结果或错误: {results}")
            except Exception as e:
                self.logger.warning(f"博查AI搜索失败: {str(e)}")
        else:
            self.logger.warning("未配置博查AI搜索API Key，跳过")

        # 2. 尝试百度搜索（中文搜索质量最高）
        baidu_key = await self._get_user_search_api_key("baidu")
        if baidu_key:
            self.logger.info(f"使用百度搜索...")
            try:
                results = await search_with_user_api_key(
                    query=query,
                    provider="baidu",
                    api_key=baidu_key,
                    num_results=num_results
                )
                if results and not any("error" in r for r in results):
                    self.logger.info(f"百度搜索成功: {len(results)}条结果")
                    return results, "baidu"
                else:
                    self.logger.warning(f"百度搜索返回空结果或错误: {results}")
            except Exception as e:
                self.logger.warning(f"百度搜索失败: {str(e)}")
        else:
            self.logger.warning("未配置百度搜索API Key，跳过")

        self.logger.error("所有搜索引擎都失败，请检查API Key配置")
        return [], None

    def _extract_hot_items_from_search(
        self,
        search_results: List[Dict[str, Any]],
        platform: PlatformType,
        limit: int = 20
    ) -> List[MCPTrendingItem]:
        """
        从搜索结果中提取热点条目

        Args:
            search_results: 搜索结果列表
            platform: 平台类型
            limit: 最大返回数量

        Returns:
            热点条目列表
        """
        items = []
        seen_titles = set()

        for result in search_results:
            if len(items) >= limit:
                break

            title = result.get("title", "")
            snippet = result.get("snippet", "")
            url = result.get("url", "")

            # 跳过空标题或重复标题
            if not title or title in seen_titles:
                continue

            # 跳过错误结果
            if "error" in result:
                continue

            seen_titles.add(title)

            # 清理标题
            clean_title = self._clean_title(title)

            # 创建热点条目
            item = MCPTrendingItem(
                title=clean_title,
                url=url,
                hot_value=None,  # 搜索结果没有热度值
                rank=len(items) + 1,
                platform=platform.value  # 平台标识
            )
            # 将摘要存入extra字段
            if snippet:
                item.extra["snippet"] = snippet[:200]
            items.append(item)

        return items

    def _clean_title(self, title: str) -> str:
        """清理标题"""
        # 移除常见的前缀和后缀
        patterns = [
            r'^[\d]+\.\s*',  # 数字前缀
            r'^【[^】]+】\s*',  # 中文方括号标签
            r'^\[[^\]]+\]\s*',  # 英文方括号标签
            r'\s*[-_|]\s*.*$',  # 后缀分隔符
        ]

        clean = title.strip()
        for pattern in patterns:
            clean = re.sub(pattern, '', clean)

        return clean.strip() or title

    async def get_trending_topics(
        self,
        platforms: Optional[List[str]] = None,
        limit: int = 20
    ) -> MCPResponse:
        """
        获取热点话题

        Args:
            platforms: 平台列表，None表示获取所有平台
            limit: 每个平台返回的最大条目数

        Returns:
            MCPResponse 统一响应
        """
        self.logger.info(f"开始获取热点话题，平台: {platforms}, 限制: {limit}")

        # 确定要获取的平台
        target_platforms = []
        if platforms:
            for p in platforms:
                try:
                    target_platforms.append(PlatformType(p))
                except ValueError:
                    self.logger.warning(f"未知平台: {p}")
        else:
            target_platforms = list(SEARCH_STRATEGIES.keys())

        # 并发获取各平台数据
        tasks = [
            self.get_platform_data(platform.value, limit)
            for platform in target_platforms
        ]

        platform_data_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        all_platforms_data = []
        errors = []

        for i, data in enumerate(platform_data_list):
            if isinstance(data, Exception):
                errors.append(str(data))
                self.logger.error(
                    f"平台 {target_platforms[i]} 获取异常: {str(data)}")
            elif isinstance(data, MCPPlatformData):
                all_platforms_data.append(data)

        self.logger.info(
            f"热点聚合完成: 成功{len(all_platforms_data)}个平台, 失败{len(errors)}个")

        # 创建响应
        response = MCPResponse(
            success=len(all_platforms_data) > 0,
            provider=self.provider,
            service_type="hot_news",
            data=all_platforms_data,
            total_items=sum(len(p.items) for p in all_platforms_data),
            platforms_count=len(all_platforms_data)
        )

        if errors:
            response.error = MCPError(
                code=MCPErrorCode.PARTIAL_FAILURE,
                message=f"部分平台获取失败: {', '.join(errors)}"
            )

        return response

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
        try:
            platform_type = PlatformType(platform)
        except ValueError:
            return self._create_platform_error_data(
                platform,
                MCPError(
                    code=MCPErrorCode.INVALID_PARAMS,
                    message=f"不支持的平台: {platform}"
                )
            )

        strategy = SEARCH_STRATEGIES.get(platform_type)
        if not strategy:
            return self._create_platform_error_data(
                platform,
                MCPError(
                    code=MCPErrorCode.INVALID_PARAMS,
                    message=f"平台 {platform} 没有配置搜索策略"
                )
            )

        # 构建搜索查询
        keywords = strategy["keywords"]
        query = " OR ".join(keywords[:2])  # 使用前两个关键词

        self.logger.info(f"搜索平台 {platform}，查询: {query}")

        try:
            # 执行搜索（返回结果和引擎名称）
            search_results, engine_used = await self._search_with_fallback(query, limit * 2)

            if not search_results:
                self.logger.warning(f"平台 {platform} 搜索未返回结果")
                return self._create_platform_error_data(
                    platform,
                    MCPError(
                        code=MCPErrorCode.NO_DATA,
                        message="搜索未返回结果"
                    )
                )

            # 提取热点条目
            items = self._extract_hot_items_from_search(
                search_results,
                platform_type,
                limit
            )

            if not items:
                self.logger.warning(f"平台 {platform} 无法从搜索结果中提取热点数据")
                return self._create_platform_error_data(
                    platform,
                    MCPError(
                        code=MCPErrorCode.NO_DATA,
                        message="无法从搜索结果中提取热点数据"
                    )
                )

            self.logger.info(f"平台 {platform} 获取成功: {len(items)}条热点")
            # 创建平台数据
            return MCPPlatformData(
                platform=platform,
                display_name=strategy["platform"],
                items=items,
                is_available=True,
                fetched_at=datetime.now()
            )

        except Exception as e:
            self.logger.error(f"获取平台 {platform} 数据失败: {str(e)}")
            return self._create_platform_error_data(
                platform,
                MCPError(
                    code=MCPErrorCode.NETWORK_ERROR,
                    message=f"获取数据失败: {str(e)}"
                )
            )

    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            服务是否可用
        """
        try:
            # 尝试一个简单的搜索
            results, engine = await self._search_with_fallback("test", 1)
            return len(results) > 0
        except Exception:
            return False

    def get_service_info(self) -> Dict[str, Any]:
        """
        获取服务信息

        Returns:
            服务详细信息
        """
        return {
            "provider": self.provider,
            "name": "基于搜索的热点聚合",
            "description": "通过国内搜索引擎API聚合各平台热点数据，降级策略：博查AI搜索 → 百度搜索",
            "supported_platforms": [p.value for p in SEARCH_STRATEGIES.keys()],
            "search_engines": {
                "primary": "bocha",
                "fallback": ["baidu"]
            },
            "requires_api_key": True,
            "api_key_providers": ["bocha", "baidu"],
            "status": self._status.value,
            "stats": self.get_stats()
        }
