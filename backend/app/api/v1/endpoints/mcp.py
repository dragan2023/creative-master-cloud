"""
MCP 多内容提供商 API 端点
提供服务状态查询、配置管理、热点数据获取等功能
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import ResponseModel
from app.core.logger import get_logger
from app.tools.mcp.mcp_client import get_mcp_client, MCPClient
from app.tools.mcp.mcp_cache import get_mcp_cache, MCPCache
from app.tools.mcp.mcp_config import get_mcp_config_manager, MCPConfigManager

router = APIRouter(prefix="/mcp", tags=["MCP服务"])
logger = get_logger(__name__)


@router.get("/status")
async def get_mcp_status(
    current_user: User = Depends(get_current_user)
):
    """
    获取所有 MCP 服务状态

    返回各提供者的运行状态、可用性、统计信息等
    """
    try:
        client = get_mcp_client()
        status = await client.get_provider_status()

        # 添加健康检查
        health = await client.health_check()
        for provider_name in status:
            status[provider_name]["healthy"] = health.get(provider_name, False)

        return {
            "success": True,
            "data": {
                "enabled": client.config_manager.is_enabled,
                "cache_enabled": client.config_manager.is_cache_enabled,
                "providers": status
            }
        }
    except Exception as e:
        logger.error(f"获取MCP状态失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/providers")
async def get_mcp_providers(
    current_user: User = Depends(get_current_user)
):
    """
    获取可用的 MCP 提供者列表

    返回提供者名称、类型、描述等信息
    """
    try:
        client = get_mcp_client()
        config_manager = get_mcp_config_manager()

        providers = []
        for name in client.get_available_providers():
            config = config_manager.get_service_config(name)
            if config:
                providers.append({
                    "name": name,
                    "display_name": config.name,
                    "type": config.service_type.value,
                    "description": config.description,
                    "enabled": config.enabled,
                    "platforms": config_manager.get_enabled_platforms(name)
                })

        return {
            "success": True,
            "data": providers
        }
    except Exception as e:
        logger.error(f"获取MCP提供者列表失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/config")
async def get_mcp_config(
    current_user: User = Depends(get_current_user)
):
    """
    获取 MCP 配置信息
    """
    try:
        config_manager = get_mcp_config_manager()
        config = config_manager.to_dict()

        return {
            "success": True,
            "data": config
        }
    except Exception as e:
        logger.error(f"获取MCP配置失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.put("/config")
async def update_mcp_config(
    enabled: bool = True,
    cache_enabled: bool = True,
    cache_ttl: int = 3600,
    timeout: float = 15.0,
    max_retries: int = 3,
    providers: str = "search_hotnews",
    hotnews_api_url: str = None,
    modelscope_token: str = None,
    current_user: User = Depends(get_current_user)
):
    """
    更新 MCP 配置

    注意：此端点更新运行时配置，持久化配置需通过环境变量设置
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()

        # 构建更新结果
        updates = {
            "enabled": enabled,
            "cache_enabled": cache_enabled,
            "cache_ttl": cache_ttl,
            "timeout": timeout,
            "max_retries": max_retries,
            "providers": providers
        }

        # 更新配置管理器
        config_manager = get_mcp_config_manager()

        # 更新全局配置
        config_manager._global_config.enabled = enabled
        config_manager._global_config.cache_enabled = cache_enabled
        config_manager._global_config.default_cache_ttl = cache_ttl
        config_manager._global_config.default_timeout = timeout
        config_manager._global_config.max_retries = max_retries
        config_manager._global_config.enabled_providers = providers.split(
            ",") if isinstance(providers, str) else providers

        logger.info(f"MCP配置已更新: {updates}")

        return {
            "success": True,
            "message": "配置已更新",
            "data": updates
        }
    except Exception as e:
        logger.error(f"更新MCP配置失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/test/{provider}")
async def test_mcp_provider(
    provider: str,
    current_user: User = Depends(get_current_user)
):
    """
    测试指定 MCP 提供者连接

    Args:
        provider: 提供者名称，如 hotnews, trends
    """
    try:
        client = get_mcp_client()

        # 检查提供者是否存在
        if provider not in client.get_available_providers():
            return {
                "success": False,
                "error": f"未找到提供者: {provider}"
            }

        # 执行健康检查
        health = await client.health_check(provider)

        # 尝试获取数据
        test_result = None
        if health.get(provider, False):
            try:
                result = await client.get_trending_topics(
                    platforms=None,
                    provider=provider,
                    limit=5,
                    use_cache=False
                )
                test_result = {
                    "item_count": result.total_items if result.success else 0,
                    "platforms_count": result.platforms_count if result.success else 0
                }
            except Exception as e:
                test_result = {"error": str(e)}

        return {
            "success": True,
            "data": {
                "provider": provider,
                "healthy": health.get(provider, False),
                "test_result": test_result
            }
        }
    except Exception as e:
        logger.error(f"测试MCP提供者失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/trending")
async def get_mcp_trending(
    platforms: Optional[str] = None,
    provider: str = "search_hotnews",
    limit: int = 20,
    use_cache: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取实时热点数据

    Args:
        platforms: 平台列表，逗号分隔，如 "weibo,zhihu"
        provider: 提供者名称（默认 search_hotnews，基于搜索引擎聚合热点）
        limit: 每个平台返回数量
        use_cache: 是否使用缓存
    """
    try:
        client = get_mcp_client()

        # 解析平台列表
        platform_list = None
        if platforms:
            platform_list = [p.strip()
                             for p in platforms.split(",") if p.strip()]

        # 获取热点数据（传递用户上下文以获取API Key）
        result = await client.get_trending_topics(
            platforms=platform_list,
            provider=provider,
            limit=limit,
            use_cache=use_cache,
            db_session=db,
            user_id=current_user.id
        )

        return result.to_dict()
    except Exception as e:
        logger.error(f"获取热点数据失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/cache/stats")
async def get_mcp_cache_stats(
    current_user: User = Depends(get_current_user)
):
    """
    获取 MCP 缓存统计信息
    """
    try:
        cache = get_mcp_cache()
        stats = cache.get_stats()

        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"获取缓存统计失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.delete("/cache")
async def clear_mcp_cache(
    provider: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    清除 MCP 缓存

    Args:
        provider: 指定提供者，不传则清除所有
    """
    try:
        client = get_mcp_client()
        client.clear_cache(provider)

        return {
            "success": True,
            "message": f"已清除缓存: {provider or '全部'}"
        }
    except Exception as e:
        logger.error(f"清除缓存失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/platforms")
async def get_mcp_platforms(
    provider: str = "search_hotnews",
    current_user: User = Depends(get_current_user)
):
    """
    获取指定提供者支持的平台列表
    """
    try:
        config_manager = get_mcp_config_manager()
        config = config_manager.get_service_config(provider)

        if not config:
            return {
                "success": False,
                "error": f"未找到提供者: {provider}"
            }

        platforms = []
        for p in config.platforms:
            platforms.append({
                "value": p.platform.value,
                "enabled": p.enabled,
                "priority": p.priority,
                "max_items": p.max_items
            })

        return {
            "success": True,
            "data": platforms
        }
    except Exception as e:
        logger.error(f"获取平台列表失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
