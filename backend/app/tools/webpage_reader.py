"""
网页链接读取工具
从用户提供的网页链接中提取内容，用于增强创意生成

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import List, Dict, Any, Optional
import httpx
import re
from urllib.parse import urlparse
import asyncio

from app.core.logger import get_logger
from app.core.config import get_settings


class WebpageReader:
    """网页链接读取工具"""

    def __init__(self):
        self.timeout = 30.0
        self.max_content_length = 50000  # 最大内容长度（字符）
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # 智能代理路由：根据URL自动判断是否需要代理
        # 在fetch_url中动态获取代理配置
        pass

    async def fetch_url(self, url: str) -> Optional[str]:
        """
        获取网页内容

        Args:
            url: 网页URL

        Returns:
            网页HTML内容
        """
        logger = get_logger("webpage_reader")

        try:
            # 验证URL格式
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"无效的URL格式: {url}")
                return None

            # 硬编码代理路由：根据域名列表判断是否需要代理
            from app.tools.proxy_router import get_proxy_for_url
            proxy = get_proxy_for_url(url)

            # 国内服务商：trust_env=False 禁用环境变量代理，确保直连
            # 国外服务商：proxy=proxy_url 使用代理
            if proxy:
                async with httpx.AsyncClient(timeout=self.timeout, proxy=proxy) as client:
                    response = await client.get(
                        url,
                        headers=self.headers,
                        follow_redirects=True,
                        max_redirects=5
                    )
                    response.raise_for_status()

                    # 检测编码
                    content_type = response.headers.get("content-type", "")
                    if "charset=" in content_type:
                        encoding = content_type.split(
                            "charset=")[-1].split(";")[0].strip()
                        response.encoding = encoding

                    return response.text
            else:
                async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                    response = await client.get(
                        url,
                        headers=self.headers,
                        follow_redirects=True,
                        max_redirects=5
                    )
                    response.raise_for_status()

                    # 检测编码
                    content_type = response.headers.get("content-type", "")
                    if "charset=" in content_type:
                        encoding = content_type.split(
                            "charset=")[-1].split(";")[0].strip()
                        response.encoding = encoding

                    return response.text

        except httpx.TimeoutException:
            logger.warning(f"获取网页超时: {url}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP错误 {e.response.status_code}: {url}")
            return None
        except Exception as e:
            logger.error(f"获取网页失败 {url}: {str(e)}")
            return None

    def extract_content(self, html: str, url: str) -> Dict[str, Any]:
        """
        从HTML中提取主要内容

        Args:
            html: HTML内容
            url: 原始URL

        Returns:
            提取的内容字典 {title, content, url}
        """
        try:
            # 使用 readability-lxml 提取主要内容
            from readability import Document

            doc = Document(html)
            title = doc.title()
            content_html = doc.summary()

            # 使用 BeautifulSoup 清理HTML，提取纯文本
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(content_html, 'lxml')

            # 移除脚本和样式
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # 获取纯文本
            text = soup.get_text(separator='\n', strip=True)

            # 清理多余空白
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip()
                      for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            # 截断过长的内容
            if len(text) > self.max_content_length:
                text = text[:self.max_content_length] + "\n...(内容已截断)"

            return {
                "title": title,
                "content": text,
                "url": url
            }

        except ImportError:
            # 如果没有 readability，使用简单的 BeautifulSoup 提取
            return self._simple_extract(html, url)
        except Exception as e:
            get_logger("webpage_reader").error(f"提取内容失败: {str(e)}")
            return self._simple_extract(html, url)

    def _simple_extract(self, html: str, url: str) -> Dict[str, Any]:
        """
        简单的内容提取（备用方案）

        Args:
            html: HTML内容
            url: 原始URL

        Returns:
            提取的内容字典
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'lxml')

            # 移除脚本、样式、导航等
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()

            # 尝试获取标题
            title = ""
            if soup.title:
                title = soup.title.string or ""

            # 尝试获取主要内容区域
            main_content = (
                soup.find("main") or
                soup.find("article") or
                soup.find("div", class_=re.compile(r"content|article|post|entry|main")) or
                soup.find("div", id=re.compile(r"content|article|post|entry|main")) or
                soup.body
            )

            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)

            # 清理
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip()
                      for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            # 截断
            if len(text) > self.max_content_length:
                text = text[:self.max_content_length] + "\n...(内容已截断)"

            return {
                "title": title.strip() or urlparse(url).netloc,
                "content": text,
                "url": url
            }

        except Exception as e:
            get_logger("webpage_reader").error(f"简单提取失败: {str(e)}")
            return {
                "title": urlparse(url).netloc,
                "content": "",
                "url": url
            }

    async def read_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        批量读取多个URL的内容

        Args:
            urls: URL列表

        Returns:
            内容列表
        """
        logger = get_logger("webpage_reader")
        results = []

        # 并发获取（限制并发数）
        semaphore = asyncio.Semaphore(3)  # 最多同时3个请求

        async def fetch_with_semaphore(url: str) -> Optional[Dict[str, Any]]:
            async with semaphore:
                html = await self.fetch_url(url)
                if html:
                    return self.extract_content(html, url)
                return None

        tasks = [fetch_with_semaphore(url) for url in urls if url.strip()]
        task_results = await asyncio.gather(*tasks)

        for result in task_results:
            if result and result.get("content"):
                results.append(result)

        logger.info(f"成功读取 {len(results)}/{len(urls)} 个网页")
        return results

    def format_for_context(self, contents: List[Dict[str, Any]]) -> str:
        """
        格式化内容用于LLM上下文

        Args:
            contents: 内容列表

        Returns:
            格式化的上下文文本
        """
        if not contents:
            return ""

        parts = ["以下是参考网页的内容：\n"]

        for i, item in enumerate(contents, 1):
            parts.append(f"\n[参考网页 {i}] {item['title']}")
            parts.append(f"来源：{item['url']}")
            parts.append(f"内容：\n{item['content']}\n")
            parts.append("-" * 50)

        return "\n".join(parts)


# 全局网页读取工具实例
webpage_reader = WebpageReader()


def get_webpage_reader() -> WebpageReader:
    """获取网页读取工具实例"""
    return webpage_reader
