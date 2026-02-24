"""
联网搜索工具
提供网络搜索能力
"""
from typing import Optional, List, Dict, Any
import httpx
from abc import ABC, abstractmethod
from app.core.config import get_settings


class BaseSearchEngine(ABC):
    """搜索引擎基类"""

    @abstractmethod
    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        执行搜索

        Args:
            query: 搜索查询
            num_results: 返回结果数量

        Returns:
            搜索结果列表
        """
        pass


class DuckDuckGoSearch(BaseSearchEngine):
    """DuckDuckGo 搜索引擎（免费，无需 API Key）"""

    def __init__(self):
        self.base_url = "https://api.duckduckgo.com/"
        # DuckDuckGo是国外服务，使用硬编码代理路由
        from app.tools.proxy_router import get_proxy_for_url
        self.proxy = get_proxy_for_url(self.base_url)

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """执行 DuckDuckGo 搜索"""
        # DuckDuckGo 是国外服务，需要代理
        if self.proxy:
            async with httpx.AsyncClient(timeout=15, proxy=self.proxy) as client:
                return await self._do_search(client, query, num_results)
        else:
            async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                return await self._do_search(client, query, num_results)

    async def _do_search(self, client, query: str, num_results: int) -> List[Dict[str, Any]]:
        """执行搜索请求"""
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }

        try:
            response = await client.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = []

            # 相关主题
            if data.get("RelatedTopics"):
                for topic in data["RelatedTopics"][:num_results]:
                    if isinstance(topic, dict) and "Text" in topic:
                        results.append({
                            "title": topic.get("Text", "")[:100],
                            "snippet": topic.get("Text", ""),
                            "url": topic.get("FirstURL", "")
                        })

            # 抽象结果
            if data.get("Abstract"):
                results.insert(0, {
                    "title": "Summary",
                    "snippet": data["Abstract"],
                    "url": data.get("AbstractURL", "")
                })

            return results[:num_results]

        except Exception as e:
            return [{"error": f"搜索失败: {str(e)}"}]


class MockSearchEngine(BaseSearchEngine):
    """模拟搜索引擎（开发测试用）"""

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """返回模拟搜索结果"""
        return [
            {
                "title": f"关于'{query}'的参考信息 {i+1}",
                "snippet": f"这是关于'{query}'的第{i+1}条参考信息，包含相关内容摘要...",
                "url": f"https://example.com/result/{i+1}"
            }
            for i in range(num_results)
        ]


class WebSearchTool:
    """联网搜索工具"""

    def __init__(self, engine: str = "duckduckgo"):
        """
        初始化搜索工具

        Args:
            engine: 搜索引擎类型
        """
        self.engines = {
            "duckduckgo": DuckDuckGoSearch(),
            "mock": MockSearchEngine()
        }
        self._engine = self.engines.get(engine, MockSearchEngine())

    async def search(
        self,
        query: str,
        num_results: int = 5,
        engine: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        执行搜索

        Args:
            query: 搜索查询
            num_results: 返回结果数量
            engine: 指定搜索引擎

        Returns:
            搜索结果列表
        """
        if engine and engine in self.engines:
            self._engine = self.engines[engine]

        return await self._engine.search(query, num_results)

    def format_results(self, results: List[Dict[str, Any]]) -> str:
        """
        格式化搜索结果为文本

        Args:
            results: 搜索结果列表

        Returns:
            格式化后的文本
        """
        if not results:
            return "未找到相关结果。"

        formatted = []
        for i, result in enumerate(results, 1):
            if "error" in result:
                formatted.append(f"错误: {result['error']}")
            else:
                formatted.append(
                    f"[{i}] {result.get('title', '无标题')}\n"
                    f"    {result.get('snippet', '无摘要')}\n"
                    f"    来源: {result.get('url', '无链接')}"
                )

        return "\n\n".join(formatted)


# 全局搜索工具实例
web_search_tool = WebSearchTool()


def get_web_search_tool() -> WebSearchTool:
    """获取搜索工具实例"""
    return web_search_tool
