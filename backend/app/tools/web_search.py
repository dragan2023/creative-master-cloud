"""
联网搜索工具
提供网络搜索能力
支持国内搜索引擎：博查AI搜索、百度搜索

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Optional, List, Dict, Any
import httpx
from abc import ABC, abstractmethod
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


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


class BochaSearch(BaseSearchEngine):
    """博查AI搜索引擎（国内服务，无需代理）"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.bochaai.com/v1"

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """执行博查AI搜索"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "query": query,
            "count": num_results,
            "summary": True,  # 返回智能摘要
            "freshness": "oneYear"  # 优先返回一年内的结果
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self.base_url}/web-search",
                    headers=headers,
                    json=payload
                )

            if response.status_code != 200:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", error_msg)
                except (json.JSONDecodeError, ValueError):
                    pass  # 保持原始错误文本
                return [{"error": f"博查AI搜索失败: {error_msg}"}]

            data = response.json()
            results = []

            # 博查AI返回格式：根级有 code, log_id, msg, data
            # 实际搜索结果在 data.webPages.value 中
            data_obj = data.get("data", {})
            web_pages = data_obj.get("webPages", {}).get("value", [])
            for item in web_pages[:num_results]:
                # 优先使用summary（智能摘要），其次使用snippet
                snippet = item.get("summary") or item.get("snippet", "")
                results.append({
                    "title": item.get("name", ""),
                    "snippet": snippet,
                    "url": item.get("url", ""),
                    "datePublished": item.get("datePublished", "")
                })

            logger.info(f"博查AI搜索成功: {len(results)}条结果")
            return results

        except Exception as e:
            logger.error(f"博查AI搜索失败: {str(e)}")
            return [{"error": f"博查AI搜索失败: {str(e)}"}]


class BaiduSearch(BaseSearchEngine):
    """百度搜索引擎（国内服务，无需代理）"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://qianfan.baidubce.com/v2/ai_search/chat/completions"

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """执行百度搜索"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 百度AI搜索API格式（OpenAI兼容）
        payload = {
            "messages": [
                {"role": "user", "content": query}
            ],
            "search_source": "baidu_search_v2",
            "search_filter": {
                "search_type": "web",
                "top_k": num_results
            },
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )

            if response.status_code != 200:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "error", {}).get("message", error_msg)
                except (json.JSONDecodeError, ValueError):
                    pass  # 保持原始错误文本
                return [{"error": f"百度搜索失败: {error_msg}"}]

            data = response.json()
            results = []

            # 百度AI搜索返回格式：
            # {"request_id": "...", "references": [...]}
            # references 数组中每个元素包含 id, url, title, date, content, snippet 等
            references = data.get("references", [])

            if references:
                for item in references[:num_results]:
                    # 使用 snippet 或 content 作为摘要
                    snippet = item.get("snippet") or item.get("content", "")
                    results.append({
                        "title": item.get("title", ""),
                        "snippet": snippet[:500] if snippet else "",  # 限制摘要长度
                        "url": item.get("url", ""),
                        "datePublished": item.get("date", "")
                    })
                logger.info(f"百度搜索成功: {len(results)}条结果")
            else:
                # 尝试OpenAI兼容格式（备用）
                choices = data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")

                    # 百度AI搜索会返回带有搜索结果的回复
                    # 尝试解析搜索结果
                    search_results = message.get("search_results", [])
                    if search_results:
                        for item in search_results[:num_results]:
                            results.append({
                                "title": item.get("title", ""),
                                "snippet": item.get("snippet", ""),
                                "url": item.get("url", ""),
                                "datePublished": item.get("date", "")
                            })
                    else:
                        # 如果没有结构化搜索结果，使用content作为摘要
                        results.append({
                            "title": f"关于'{query}'的搜索结果",
                            "snippet": content[:500] if content else "",
                            "url": ""
                        })

            logger.info(f"百度搜索成功: {len(results)}条结果")
            return results

        except Exception as e:
            logger.error(f"百度搜索失败: {str(e)}")
            return [{"error": f"百度搜索失败: {str(e)}"}]


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

    def __init__(self, engine: str = "bocha", api_key: Optional[str] = None):
        """
        初始化搜索工具

        Args:
            engine: 搜索引擎类型 (bocha/baidu/mock)
            api_key: API Key（博查和百度需要）
        """
        self._api_key = api_key
        self._engine_name = engine
        self._engine = self._create_engine(engine, api_key)

    def _create_engine(self, engine: str, api_key: Optional[str] = None) -> BaseSearchEngine:
        """创建搜索引擎实例"""
        if engine == "bocha":
            if not api_key:
                raise ValueError("博查AI搜索需要提供API Key")
            return BochaSearch(api_key)
        elif engine == "baidu":
            if not api_key:
                raise ValueError("百度搜索需要提供API Key")
            return BaiduSearch(api_key)
        else:
            return MockSearchEngine()

    def set_engine(self, engine: str, api_key: Optional[str] = None):
        """
        设置搜索引擎

        Args:
            engine: 搜索引擎类型
            api_key: API Key（可选）
        """
        self._engine_name = engine
        self._api_key = api_key
        self._engine = self._create_engine(engine, api_key)

    async def search(
        self,
        query: str,
        num_results: int = 5,
        engine: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        执行搜索

        Args:
            query: 搜索查询
            num_results: 返回结果数量
            engine: 指定搜索引擎（可选，覆盖初始化设置）
            api_key: API Key（可选，覆盖初始化设置）

        Returns:
            搜索结果列表
        """
        # 如果指定了新的引擎或API Key，创建新的引擎实例
        if engine or api_key:
            actual_engine = engine or self._engine_name
            actual_key = api_key or self._api_key
            search_engine = self._create_engine(actual_engine, actual_key)
        else:
            search_engine = self._engine

        return await search_engine.search(query, num_results)

    def format_results(self, results: List[Dict[str, Any]]) -> str:
        """
        格式化搜索结果为文本（基础版）

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

    def format_results_enhanced(
        self,
        results: List[Dict[str, Any]],
        query: str = "",
        max_results: int = 5,
        max_context_length: int = 2000
    ) -> str:
        """
        格式化搜索结果为LLM友好的结构化文本（增强版）

        Args:
            results: 搜索结果列表
            query: 搜索查询（用于相关性标注）
            max_results: 最大结果数量
            max_context_length: 最大上下文长度

        Returns:
            格式化后的结构化文本
        """
        import re

        if not results:
            return ""

        # 过滤错误结果
        valid_results = [r for r in results if "error" not in r]

        if not valid_results:
            return ""

        # 限制结果数量
        valid_results = valid_results[:max_results]

        parts = []
        parts.append("## 📚 参考资料（联网搜索）\n")

        if query:
            parts.append(f"> 搜索关键词：{query}\n")

        total_length = 0

        for i, result in enumerate(valid_results, 1):
            title = result.get("title", "无标题")
            snippet = result.get("snippet", "")
            url = result.get("url", "")
            date = result.get("datePublished", "")

            # 内容清洗
            snippet = self._clean_snippet(snippet)

            # 检查长度限制
            entry_length = len(snippet) + len(title) + 100
            if total_length + entry_length > max_context_length:
                break

            parts.append(f"### [{i}] {title}")

            # 提取关键信息
            key_info = self._extract_key_info(snippet)
            if key_info:
                parts.append(f"📌 **关键信息**：{key_info}")

            # 详细内容
            if snippet:
                parts.append(f"📝 **内容**：{snippet}")

            # 来源
            source_info = f"🔗 来源：{url}"
            if date:
                source_info += f" ({date})"
            parts.append(source_info)
            parts.append("")

            total_length += entry_length

        # 使用指引
        parts.append("---")
        parts.append("\n**💡 使用指引**：")
        parts.append("1. 以上资料可作为创作参考")
        parts.append("2. 请勿直接复制，应进行原创性转化")
        parts.append("3. 如有冲突信息，以权威来源为准")

        return "\n".join(parts)

    def _clean_snippet(self, snippet: str) -> str:
        """清洗摘要内容"""
        if not snippet:
            return ""

        # 移除常见的噪声模式
        noise_patterns = [
            r'点击查看.*',
            r'扫码关注.*',
            r'下载APP.*',
            r'广告.*',
            r'推广.*',
        ]

        clean = snippet
        for pattern in noise_patterns:
            clean = re.sub(pattern, '', clean, flags=re.IGNORECASE)

        return clean.strip()

    def _extract_key_info(self, text: str) -> str:
        """从文本中提取关键信息"""
        if not text or len(text) < 20:
            return ""

        # 提取第一句作为关键信息
        sentences = re.split(r'[。！？\.\!\?]', text)
        if sentences:
            first_sentence = sentences[0].strip()
            if len(first_sentence) > 50:
                return first_sentence[:50] + "..."
            return first_sentence

        return ""


# 全局搜索工具实例（默认使用Mock引擎，实际使用时需要API Key）
web_search_tool = WebSearchTool(engine="mock")


def get_web_search_tool() -> WebSearchTool:
    """获取搜索工具实例"""
    return web_search_tool


async def search_with_user_api_key(
    query: str,
    provider: str,
    api_key: str,
    num_results: int = 5
) -> List[Dict[str, Any]]:
    """
    使用用户提供的API Key执行搜索

    Args:
        query: 搜索查询
        provider: 搜索服务提供商 (bocha/baidu)
        api_key: 用户的API Key
        num_results: 返回结果数量

    Returns:
        搜索结果列表
    """
    tool = WebSearchTool(engine=provider, api_key=api_key)
    return await tool.search(query, num_results)


async def search_with_fallback(
    query: str,
    num_results: int = 5,
    get_user_api_key: Optional[callable] = None
) -> tuple:
    """
    使用降级策略执行搜索（国内服务优先）

    降级顺序：博查AI搜索 → 百度搜索

    Args:
        query: 搜索查询
        num_results: 返回结果数量
        get_user_api_key: 异步函数，用于获取用户的API Key
                         签名: async (provider: str) -> Optional[str]

    Returns:
        (搜索结果列表, 使用的引擎名称)
        例如: ([{"title": "...", ...}], "bocha")
    """
    # 引擎显示名称映射
    engine_names = {
        "bocha": "博查AI搜索",
        "baidu": "百度搜索"
    }

    # 1. 首先尝试博查AI搜索（国内服务，专为AI应用优化）
    if get_user_api_key:
        try:
            bocha_key = await get_user_api_key("bocha")
            if bocha_key:
                results = await search_with_user_api_key(
                    query=query,
                    provider="bocha",
                    api_key=bocha_key,
                    num_results=num_results
                )
                if results and not any("error" in r for r in results):
                    logger.info(f"博查AI搜索成功: {len(results)}条结果")
                    return results, "bocha"
        except Exception as e:
            logger.warning(f"博查AI搜索失败: {str(e)}")

    # 2. 尝试百度搜索（中文搜索质量最高）
    if get_user_api_key:
        try:
            baidu_key = await get_user_api_key("baidu")
            if baidu_key:
                results = await search_with_user_api_key(
                    query=query,
                    provider="baidu",
                    api_key=baidu_key,
                    num_results=num_results
                )
                if results and not any("error" in r for r in results):
                    logger.info(f"百度搜索成功: {len(results)}条结果")
                    return results, "baidu"
        except Exception as e:
            logger.warning(f"百度搜索失败: {str(e)}")

    # 所有引擎都失败
    logger.error("所有搜索引擎都失败，请检查API Key配置")
    return [], None
