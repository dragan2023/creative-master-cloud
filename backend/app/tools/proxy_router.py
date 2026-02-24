"""
代理路由工具
国内模型直连，国外模型使用代理
"""
import httpx
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse
from functools import lru_cache

from app.core.config import get_settings
from app.core.logger import get_logger

# 国内AI服务商域名列表（直连）
DOMESTIC_PROVIDERS = {
    # 阿里云/通义千问
    "dashscope.aliyuncs.com",
    "dashscope.cn",
    "aliyuncs.com",
    "qwen.aliyuncs.com",
    # 火山引擎/豆包
    "ark.cn-beijing.volces.com",
    "ark.cn-shanghai.volces.com",
    "ark.cn-guangzhou.volces.com",
    "volces.com",
    # 百度
    "aip.baidubce.com",
    "qianfan.baidubce.com",
    "baidubce.com",
    # 智谱
    "open.bigmodel.cn",
    "bigmodel.cn",
    # 月之暗面
    "api.moonshot.cn",
    "moonshot.cn",
    # 讯飞
    "spark-api.xf-yun.com",
    "xf-yun.com",
    # 腾讯
    "hunyuan.tencentcloudapi.com",
    "tencentcloudapi.com",
    # 商汤
    "api.sensenova.cn",
    "sensenova.cn",
    # 深度求索 (国内版)
    "api.deepseek.com.cn",
    "deepseek.com.cn",
    # 零一万物
    "api.lingyiwanwu.com",
    "lingyiwanwu.com",
    # 百川
    "api.baichuan-ai.com",
    "baichuan-ai.com",
    # MiniMax
    "api.minimax.chat",
    "minimax.chat",
    # 硅基流动
    "api.siliconflow.cn",
    "siliconflow.cn",
    # OpenRouter (国外模型聚合平台，国内直连)
    "openrouter.ai",
    # 其他国内域名
    "localhost",
    "127.0.0.1",
}

# 国外AI服务商域名列表（需要代理）
INTERNATIONAL_PROVIDERS = {
    # OpenAI
    "api.openai.com",
    "openai.com",
    # Anthropic
    "api.anthropic.com",
    "anthropic.com",
    # Google
    "generativelanguage.googleapis.com",
    "googleapis.com",
    # Grok
    "api.x.ai",
    "x.ai",
    # 深度求索 (国际版需要代理)
    "api.deepseek.com",
    "deepseek.com",
    # Cohere
    "api.cohere.ai",
    # Mistral
    "api.mistral.ai",
}

# URL连接缓存（避免重复测试同一域名）
_url_connectivity_cache = {}


def get_proxy_for_url(url: str) -> Optional[str]:
    """
    根据硬编码列表判断是否需要代理

    Args:
        url: 目标URL

    Returns:
        代理URL或None（国内服务商返回None直连，国外服务商返回代理）
    """
    # 解析域名
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain:
            domain = url.lower()
    except Exception:
        domain = url.lower()

    # 检查是否是国内服务商
    for domestic_domain in DOMESTIC_PROVIDERS:
        if domestic_domain in domain or domain.endswith(domestic_domain):
            # 国内服务商，直连
            return None

    # 国外服务商，返回代理
    settings = get_settings()
    proxy_url = settings.HTTPS_PROXY or settings.HTTP_PROXY
    return proxy_url


def check_proxy_available() -> Tuple[bool, Optional[str]]:
    """
    检查代理是否可用

    Returns:
        (是否可用, 代理URL)
    """
    settings = get_settings()
    proxy_url = settings.HTTPS_PROXY or settings.HTTP_PROXY

    if not proxy_url:
        return False, None

    try:
        proxy_host = proxy_url.replace(
            "http://", "").replace("https://", "").split(":")[0]
        proxy_port = int(proxy_url.split(":")[-1].rstrip("/"))

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((proxy_host, proxy_port))
        sock.close()

        if result == 0:
            return True, proxy_url
    except Exception:
        pass

    return False, None


def is_domestic_provider(url: str) -> bool:
    """
    判断是否为国内服务商（硬编码列表）

    Args:
        url: 目标URL

    Returns:
        是否是国内服务商（True=国内直连，False=国外需代理）
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain:
            domain = url.lower()
    except Exception:
        domain = url.lower()

    logger = get_logger("proxy_router")
    logger.debug(f"检查域名: {domain}")

    # 优先检查国外服务商列表（更精确匹配）
    for intl_domain in INTERNATIONAL_PROVIDERS:
        if domain == intl_domain or domain.endswith("." + intl_domain):
            logger.debug(f"匹配国外服务商: {intl_domain}")
            return False

    # 检查国内服务商列表
    for domestic_domain in DOMESTIC_PROVIDERS:
        if domestic_domain in domain or domain.endswith(domestic_domain) or domain == domestic_domain:
            logger.debug(f"匹配国内服务商: {domestic_domain}")
            return True

    # 默认视为国外服务商（需要代理）
    logger.debug(f"未匹配到任何列表，默认国外服务商: {domain}")
    return False


async def test_url_connectivity(url: str, timeout: float = 5.0, use_cache: bool = True) -> Tuple[bool, str, Optional[str]]:
    """
    测试URL可达性，根据硬编码列表判断是否需要代理

    核心逻辑：
    - 国内服务商 → 直连
    - 国外服务商 → 使用代理

    Args:
        url: 目标URL
        timeout: 超时时间（保留参数用于兼容）
        use_cache: 是否使用缓存

    Returns:
        (是否可达, 状态信息, 建议使用的代理)
        状态信息: "direct" | "proxy" | "failed" | "need_proxy"
    """
    logger = get_logger("proxy_router")

    # 提取域名用于缓存
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain:
            domain = url
    except Exception:
        domain = url

    # 检查缓存
    if use_cache and domain in _url_connectivity_cache:
        cached = _url_connectivity_cache[domain]
        return cached["reachable"], cached["status"], cached["proxy"]

    # 根据硬编码列表判断
    if is_domestic_provider(url):
        # 国内服务商：直连
        logger.debug(f"国内服务商，使用直连: {domain}")
        result = (True, "direct", None)
        _url_connectivity_cache[domain] = {
            "reachable": True, "status": "direct", "proxy": None}
        return result
    else:
        # 国外服务商：需要代理
        proxy_available, proxy_url = check_proxy_available()

        if proxy_available:
            logger.debug(f"国外服务商，使用代理: {domain}")
            result = (True, "proxy", proxy_url)
            _url_connectivity_cache[domain] = {
                "reachable": True, "status": "proxy", "proxy": proxy_url}
            return result
        else:
            logger.debug(f"国外服务商，代理不可用: {domain}")
            result = (False, "need_proxy", None)
            _url_connectivity_cache[domain] = {
                "reachable": False, "status": "need_proxy", "proxy": None}
            return result


async def get_smart_proxy_async(url: str, timeout: float = 5.0) -> Tuple[Optional[str], str]:
    """
    异步智能获取代理配置（通过实际连接测试）

    Args:
        url: 目标URL
        timeout: 测试超时时间

    Returns:
        (代理URL或None, 状态信息)
        状态信息: "direct" | "proxy" | "need_proxy_but_unavailable" | "failed"
    """
    reachable, status, proxy = await test_url_connectivity(url, timeout)

    if status == "direct":
        return None, "direct"
    elif status == "proxy":
        return proxy, "proxy"
    elif status == "need_proxy":
        return None, "need_proxy_but_unavailable"
    else:
        return None, "failed"


def get_smart_proxy(provider: str = None, url: str = None) -> Tuple[Optional[str], str]:
    """
    同步版本：根据硬编码列表获取代理配置

    Args:
        provider: 服务商标识（保留参数，用于日志）
        url: 目标URL

    Returns:
        (代理URL或None, 状态信息)
    """
    # 检查缓存
    if url:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain in _url_connectivity_cache:
                cached = _url_connectivity_cache[domain]
                if cached["status"] == "direct":
                    return None, "direct"
                elif cached["status"] == "proxy":
                    return cached["proxy"], "proxy"
        except Exception:
            pass

    # 根据硬编码列表判断
    if url and is_domestic_provider(url):
        # 国内服务商：直连
        return None, "direct"
    else:
        # 国外服务商：需要代理
        proxy_available, proxy_url = check_proxy_available()
        if proxy_available:
            return proxy_url, "proxy"
        else:
            return None, "need_proxy_but_unavailable"


async def smart_http_request(
    url: str,
    method: str = "GET",
    timeout: float = 30.0,
    test_connectivity: bool = True,
    **kwargs
) -> httpx.Response:
    """
    智能HTTP请求，自动选择直连或代理

    Args:
        url: 目标URL
        method: HTTP方法
        timeout: 超时时间
        test_connectivity: 是否先测试连接（推荐True）
        **kwargs: 其他httpx参数

    Returns:
        httpx.Response

    Raises:
        httpx.HTTPError: 请求失败
        Exception: 需要代理但代理不可用
    """
    proxy = None

    if test_connectivity:
        # 先测试连接，获取最佳访问方式
        proxy, status = await get_smart_proxy_async(url, timeout=5.0)

        if status == "need_proxy_but_unavailable":
            raise Exception("该服务需要代理访问，请启动代理软件（如Clash/V2Ray）后重试")
        elif status == "failed":
            raise Exception("无法访问该URL，请检查地址是否正确")
    else:
        # 不测试连接，检查代理是否可用
        proxy_available, proxy_url = check_proxy_available()
        if proxy_available:
            proxy = proxy_url

    # httpx 代理配置
    if proxy:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, proxy=proxy) as client:
            if method.upper() == "GET":
                return await client.get(url, **kwargs)
            elif method.upper() == "POST":
                return await client.post(url, **kwargs)
            elif method.upper() == "HEAD":
                return await client.head(url, **kwargs)
            else:
                return await client.request(method, url, **kwargs)
    else:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, trust_env=False) as client:
            if method.upper() == "GET":
                return await client.get(url, **kwargs)
            elif method.upper() == "POST":
                return await client.post(url, **kwargs)
            elif method.upper() == "HEAD":
                return await client.head(url, **kwargs)
            else:
                return await client.request(method, url, **kwargs)


def clear_cache():
    """清除URL连接缓存"""
    global _url_connectivity_cache
    _url_connectivity_cache = {}
