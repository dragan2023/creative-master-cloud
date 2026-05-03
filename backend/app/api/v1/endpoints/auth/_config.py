"""用户配置处理器（代理、预处理器等）"""
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.config import get_settings
from app.models import User, SystemConfig
from app.schemas.common import ResponseModel
from ._models import ProxyConfig, ProxyConfigResponse, PreprocessorConfig, PreprocessorConfigResponse


async def handle_get_user_proxy_config(current_user: User, db: AsyncSession) -> ResponseModel:
    """获取用户代理配置（用户级别）"""
    settings = get_settings()

    config_key = f"user_proxy_config_{current_user.id}"
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.id == config_key)
    )
    config = result.scalar_one_or_none()

    proxy_config = ProxyConfigResponse()

    if config and config.config_value:
        try:
            data = json.loads(config.config_value)
            proxy_config.http_proxy = data.get("http_proxy")
            proxy_config.https_proxy = data.get("https_proxy")
            proxy_config.is_enabled = config.is_enabled
        except (json.JSONDecodeError, KeyError) as e:
            logger = get_logger(str(current_user.id))
            logger.warning(f"解析代理配置失败: {str(e)}")

    return ResponseModel(data=proxy_config)


async def handle_set_user_proxy_config(config_data: ProxyConfig, current_user: User, db: AsyncSession) -> ResponseModel:
    """设置用户代理配置（用户级别）"""
    logger = get_logger(str(current_user.id))

    config_key = f"user_proxy_config_{current_user.id}"
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.id == config_key)
    )
    config = result.scalar_one_or_none()

    config_value = json.dumps({
        "http_proxy": config_data.http_proxy,
        "https_proxy": config_data.https_proxy
    })

    if config:
        config.config_value = config_value
        config.is_enabled = config_data.is_enabled
    else:
        config = SystemConfig(
            id=config_key,
            config_value=config_value,
            is_enabled=config_data.is_enabled
        )
        db.add(config)

    await db.commit()
    logger.info(f"用户代理配置已保存: {current_user.username}")

    return ResponseModel(message="代理配置已保存")


async def handle_test_user_proxy(current_user: User, db: AsyncSession) -> ResponseModel:
    """测试用户代理连接（用户级别）"""
    import httpx

    config_key = f"user_proxy_config_{current_user.id}"
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.id == config_key)
    )
    config = result.scalar_one_or_none()

    if not config or not config.is_enabled:
        return ResponseModel(data={
            "success": False,
            "message": "代理未启用"
        })

    try:
        data = json.loads(config.config_value) if config.config_value else {}
        http_proxy = data.get("http_proxy")

        if not http_proxy:
            return ResponseModel(data={
                "success": False,
                "message": "未配置代理地址"
            })

        if http_proxy.startswith("http://") or http_proxy.startswith("https://"):
            proxy_url = http_proxy
        else:
            settings = get_settings()
            base_url = settings.APP_BASE_URL
            if "://" in base_url:
                host_part = base_url.split(
                    "://")[1].split("/")[0].split(":")[0]
                proxy_host = host_part if host_part != "localhost" else "127.0.0.1"
            else:
                proxy_host = "127.0.0.1"
            proxy_url = f"http://{proxy_host}:{http_proxy}"

        async with httpx.AsyncClient(
            proxy=proxy_url,
            timeout=10.0
        ) as client:
            response = await client.get("https://www.google.com")
            if response.status_code == 200:
                return ResponseModel(data={
                    "success": True,
                    "message": "代理连接测试成功"
                })
            else:
                return ResponseModel(data={
                    "success": False,
                    "message": f"代理返回异常状态码: {response.status_code}"
                })

    except Exception as e:
        return ResponseModel(data={
            "success": False,
            "message": f"代理测试失败: {str(e)}"
        })


async def handle_get_user_preprocessor_config(current_user: User, db: AsyncSession) -> ResponseModel:
    """获取用户文档预处理配置（用户级别）"""
    config_key = f"user_preprocessor_config_{current_user.id}"
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.id == config_key)
    )
    config = result.scalar_one_or_none()

    default_config = PreprocessorConfigResponse(
        doc_preprocessor_enabled=True,
        graphrag_enabled=True
    )

    if config and config.config_value:
        try:
            data = json.loads(config.config_value)
            default_config.doc_preprocessor_enabled = data.get(
                "doc_preprocessor_enabled", True)
            default_config.marker_enabled = data.get(
                "marker_enabled", True)
            default_config.semantic_chunk_enabled = data.get(
                "semantic_chunk_enabled", True)
            default_config.semantic_chunk_size = data.get(
                "semantic_chunk_size", 1024)
            default_config.semantic_threshold = data.get(
                "semantic_threshold", 0.7)
            default_config.summarization_enabled = data.get(
                "summarization_enabled", False)
            default_config.graphrag_enabled = data.get(
                "graphrag_enabled", True)
        except (json.JSONDecodeError, KeyError) as e:
            logger = get_logger(str(current_user.id))
            logger.warning(f"解析预处理器配置失败: {str(e)}")

    return ResponseModel(data=default_config)


async def handle_set_user_preprocessor_config(config_data: PreprocessorConfig, current_user: User, db: AsyncSession) -> ResponseModel:
    """设置用户文档预处理配置（用户级别）"""

    logger = get_logger(str(current_user.id))

    config_key = f"user_preprocessor_config_{current_user.id}"
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.id == config_key)
    )
    config = result.scalar_one_or_none()

    config_value = json.dumps({
        "doc_preprocessor_enabled": config_data.doc_preprocessor_enabled,
        "marker_enabled": config_data.marker_enabled,
        "semantic_chunk_enabled": config_data.semantic_chunk_enabled,
        "semantic_chunk_size": config_data.semantic_chunk_size,
        "semantic_threshold": config_data.semantic_threshold,
        "summarization_enabled": config_data.summarization_enabled,
        "graphrag_enabled": config_data.graphrag_enabled
    })

    if config:
        config.config_value = config_value
        config.is_enabled = config_data.doc_preprocessor_enabled
    else:
        config = SystemConfig(
            id=config_key,
            config_value=config_value,
            is_enabled=config_data.doc_preprocessor_enabled
        )
        db.add(config)

    await db.commit()
    logger.info(f"用户预处理配置已保存: {current_user.username}")

    return ResponseModel(message="预处理配置已保存")
