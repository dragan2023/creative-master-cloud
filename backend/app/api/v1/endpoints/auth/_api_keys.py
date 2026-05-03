"""API Key 管理处理器"""
import json
import httpx
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundException
from app.core.security import mask_api_key, api_key_encryption
from app.core.logger import get_logger
from app.models import User, UserAPIKey
from app.schemas.common import ResponseModel
from app.schemas.user import APIKeyCreate, APIKeyResponse, APIKeyTest, APIKeyTestResult


async def handle_get_api_keys(current_user: User, db: AsyncSession) -> ResponseModel:
    """获取用户的 API Key 列表"""
    result = await db.execute(
        select(UserAPIKey).where(UserAPIKey.user_id == current_user.id)
    )
    api_keys = result.scalars().all()

    data = []
    for key in api_keys:
        try:
            decrypted_key = api_key_encryption.decrypt(key.encrypted_key)
            api_key_masked = mask_api_key(decrypted_key)
        except Exception:
            api_key_masked = "***解密失败***"
            key.is_valid = False
            await db.commit()

        data.append(APIKeyResponse(
            id=key.id,
            provider=key.provider,
            model_name=key.model_name,
            api_key_masked=api_key_masked,
            api_base=key.api_base,
            channel=key.channel if hasattr(key, 'channel') else "default",
            is_default=key.is_default,
            is_valid=key.is_valid,
            last_used_at=str(key.last_used_at) if key.last_used_at else None,
            created_at=str(key.created_at) if key.created_at else None
        ))

    return ResponseModel(data=data)


async def handle_create_api_key(key_data: APIKeyCreate, current_user: User, db: AsyncSession) -> ResponseModel:
    """创建 API Key"""
    logger = get_logger(str(current_user.id))

    encrypted_key = api_key_encryption.encrypt(key_data.api_key)

    if key_data.is_default:
        result = await db.execute(
            select(UserAPIKey).where(
                UserAPIKey.user_id == current_user.id,
                UserAPIKey.is_default == True
            )
        )
        for key in result.scalars().all():
            key.is_default = False

    api_key = UserAPIKey(
        user_id=current_user.id,
        provider=key_data.provider,
        model_name=key_data.model_name,
        encrypted_key=encrypted_key,
        api_base=key_data.api_base,
        channel=getattr(key_data, 'channel', 'default'),
        is_default=key_data.is_default
    )

    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    logger.info(f"创建 API Key: {key_data.provider}/{key_data.model_name}")

    return ResponseModel(data=APIKeyResponse(
        id=api_key.id,
        provider=api_key.provider,
        model_name=api_key.model_name,
        api_key_masked=mask_api_key(key_data.api_key),
        api_base=api_key.api_base,
        is_default=api_key.is_default,
        is_valid=api_key.is_valid,
        last_used_at=api_key.last_used_at
    ))


async def handle_update_api_key(key_id: int, key_data: APIKeyCreate, current_user: User, db: AsyncSession) -> ResponseModel:
    """更新 API Key"""
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.id == key_id,
            UserAPIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise ResourceNotFoundException("API Key 不存在")

    api_key.provider = key_data.provider
    api_key.model_name = key_data.model_name
    api_key.encrypted_key = api_key_encryption.encrypt(key_data.api_key)
    api_key.api_base = key_data.api_base
    api_key.channel = getattr(key_data, 'channel', 'default')

    if key_data.is_default:
        result = await db.execute(
            select(UserAPIKey).where(
                UserAPIKey.user_id == current_user.id,
                UserAPIKey.is_default == True,
                UserAPIKey.id != key_id
            )
        )
        for key in result.scalars().all():
            key.is_default = False
        api_key.is_default = True

    await db.commit()
    await db.refresh(api_key)

    return ResponseModel(data=APIKeyResponse(
        id=api_key.id,
        provider=api_key.provider,
        model_name=api_key.model_name,
        api_key_masked=mask_api_key(key_data.api_key),
        api_base=api_key.api_base,
        channel=getattr(api_key, 'channel', 'default'),
        is_default=api_key.is_default,
        is_valid=api_key.is_valid,
        last_used_at=api_key.last_used_at
    ))


async def handle_delete_api_key(key_id: int, current_user: User, db: AsyncSession) -> ResponseModel:
    """删除 API Key"""
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.id == key_id,
            UserAPIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise ResourceNotFoundException("API Key 不存在")

    await db.delete(api_key)
    await db.commit()

    return ResponseModel(message="删除成功")


async def handle_set_default_api_key(key_id: int, current_user: User, db: AsyncSession) -> ResponseModel:
    """设置默认 API Key"""
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.id == key_id,
            UserAPIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise ResourceNotFoundException("API Key 不存在")

    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == current_user.id,
            UserAPIKey.is_default == True,
            UserAPIKey.id != key_id
        )
    )
    for key in result.scalars().all():
        key.is_default = False

    api_key.is_default = True
    await db.commit()
    await db.refresh(api_key)

    return ResponseModel(data=APIKeyResponse(
        id=api_key.id,
        provider=api_key.provider,
        model_name=api_key.model_name,
        api_key_masked=mask_api_key(api_key.encrypted_key),
        api_base=api_key.api_base,
        channel=getattr(api_key, 'channel', 'default'),
        is_default=api_key.is_default,
        is_valid=api_key.is_valid,
        last_used_at=api_key.last_used_at
    ))


async def handle_test_api_key(test_data: APIKeyTest, current_user: User) -> ResponseModel:
    """测试 API Key 是否有效（真实调用API验证）"""
    from app.agents import get_llm_manager
    from app.core.config import PRESET_MODELS

    logger = get_logger(str(current_user.id))

    def get_model_type(provider: str, model_name: str) -> str:
        """获取模型类型 (text/image/video/search)"""
        preset = PRESET_MODELS.get(provider, {})
        models = preset.get("models", [])
        for m in models:
            if m.get("id") == model_name:
                return m.get("type", "text")
        return "text"

    def get_test_config(model_type: str) -> dict:
        """根据模型类型返回测试配置（含提示词和超时时间）"""
        configs = {
            "text": {
                "prompt": "Hello, this is a connection test. Please respond with 'OK'.",
                "max_tokens": 50,
                "timeout": 30.0
            },
            "image": {
                "prompt": "A simple red circle on white background",
                "max_tokens": None,
                "timeout": 120.0
            },
            "video": {
                "prompt": "A peaceful sunset over the ocean",
                "max_tokens": None,
                "timeout": 300.0
            }
        }
        return configs.get(model_type, configs["text"])

    try:
        if test_data.provider in ["bocha", "baidu"]:
            return await _test_search_api_key(test_data.provider, test_data.api_key, logger)

        model_type = get_model_type(test_data.provider, test_data.model_name)
        test_config = get_test_config(model_type)
        test_message = test_config["prompt"]

        llm_manager = get_llm_manager()
        provider = llm_manager.create_provider(
            provider_name=test_data.provider,
            api_key=test_data.api_key,
            model_name=test_data.model_name,
            api_base=test_data.api_base
        )

        model_info = provider.get_model_info()

        if model_type == "image":
            logger.info(
                f"图像模型测试: provider={test_data.provider}, model={test_data.model_name}")
        elif model_type == "video":
            logger.info(
                f"视频模型测试: provider={test_data.provider}, model={test_data.model_name}")

        if test_data.provider == "google":
            import google.generativeai as genai
            genai.configure(api_key=test_data.api_key)
            model = genai.GenerativeModel(test_data.model_name)
            response = model.generate_content(test_message)
            test_result = response.text
        else:
            api_base = test_data.api_base or model_info.get("api_base", "")

            if not api_base:
                return ResponseModel(data=APIKeyTestResult(
                    success=False,
                    message="请提供API地址（api_base）"
                ))

            if not api_base.startswith(('http://', 'https://')):
                return ResponseModel(data=APIKeyTestResult(
                    success=False,
                    message="API地址必须以 http:// 或 https:// 开头"
                ))

            headers = {
                "Authorization": f"Bearer {test_data.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": test_data.model_name,
                "messages": [{"role": "user", "content": test_message}]
            }
            if test_config.get("max_tokens"):
                payload["max_tokens"] = test_config["max_tokens"]

            from app.tools.proxy_router import get_proxy_for_url
            proxy = get_proxy_for_url(f"{api_base}/chat/completions")

            logger.info(
                f"API测试: provider={test_data.provider}, model_type={model_type}, proxy={proxy}")

            if proxy:
                async with httpx.AsyncClient(timeout=test_config["timeout"], proxy=proxy) as client:
                    response = await client.post(
                        f"{api_base}/chat/completions",
                        headers=headers,
                        json=payload
                    )
            else:
                async with httpx.AsyncClient(timeout=test_config["timeout"], trust_env=False) as client:
                    response = await client.post(
                        f"{api_base}/chat/completions",
                        headers=headers,
                        json=payload
                    )

            if response.status_code == 404 and model_type == "video":
                logger.info(
                    f"chat/completions 返回 404，尝试 /v2/videos/generations 端点")
                video_payload = {
                    "model": test_data.model_name,
                    "prompt": test_message
                }
                if proxy:
                    async with httpx.AsyncClient(timeout=test_config["timeout"], proxy=proxy) as client:
                        response = await client.post(
                            f"{api_base}/v2/videos/generations",
                            headers=headers,
                            json=video_payload
                        )
                else:
                    async with httpx.AsyncClient(timeout=test_config["timeout"], trust_env=False) as client:
                        response = await client.post(
                            f"{api_base}/v2/videos/generations",
                            headers=headers,
                            json=video_payload
                        )

            if response.status_code != 200:
                error_detail = response.json().get("error", {}).get("message", response.text)
                return ResponseModel(data=APIKeyTestResult(
                    success=False,
                    message=f"API调用失败: {error_detail}",
                    model_info=model_info
                ))

            result = response.json()
            if model_type == "video" and result.get("status"):
                test_result = f"视频任务已创建: {result.get('id', 'unknown')}"
            else:
                test_result = result.get("choices", [{}])[0].get(
                    "message", {}).get("content", "")

        logger.info(f"API Key 测试成功: {test_data.provider}")

        return ResponseModel(data=APIKeyTestResult(
            success=True,
            message="API Key 配置正确，连接测试成功",
            model_info=model_info
        ))

    except httpx.TimeoutException:
        logger.error(f"API Key 测试超时: {test_data.provider}")
        return ResponseModel(data=APIKeyTestResult(
            success=False,
            message="连接超时，请检查网络或API地址"
        ))
    except httpx.HTTPStatusError as e:
        logger.error(f"API Key 测试HTTP错误: {e}")
        return ResponseModel(data=APIKeyTestResult(
            success=False,
            message=f"HTTP错误: {e.response.status_code}"
        ))
    except Exception as e:
        logger.error(f"API Key 测试失败: {str(e)}", exc_info=True)
        return ResponseModel(data=APIKeyTestResult(
            success=False,
            message=f"测试失败: {str(e)}"
        ))


async def handle_test_saved_api_key(key_id: int, current_user: User, db: AsyncSession) -> ResponseModel:
    """测试已保存的 API Key"""
    logger = get_logger(str(current_user.id))

    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.id == key_id,
            UserAPIKey.user_id == current_user.id
        )
    )
    api_key_record = result.scalar_one_or_none()

    if not api_key_record:
        raise ResourceNotFoundException("API Key 不存在")

    try:
        decrypted_key = api_key_encryption.decrypt(
            api_key_record.encrypted_key)
    except Exception:
        api_key_record.is_valid = False
        await db.commit()
        return ResponseModel(
            code=400,
            message="API Key 解密失败，请删除后重新添加",
            data=APIKeyTestResult(
                success=False,
                message="API Key 解密失败，可能是系统密钥已变更",
                provider=api_key_record.provider,
                model=api_key_record.model_name,
                error="API Key 解密失败，可能是系统密钥已变更"
            )
        )

    try:
        if api_key_record.provider in ["bocha", "baidu"]:
            return await _test_search_api_key(api_key_record.provider, decrypted_key, logger)

        from app.core.config import PRESET_MODELS
        preset = PRESET_MODELS.get(api_key_record.provider, {})
        api_base = api_key_record.api_base or preset.get("api_base")

        def get_model_type(provider: str, model_name: str) -> str:
            preset = PRESET_MODELS.get(provider, {})
            models = preset.get("models", [])
            for m in models:
                if m.get("id") == model_name:
                    return m.get("type", "text")
            return "text"

        def get_test_config(model_type: str) -> dict:
            configs = {
                "text": {
                    "prompt": "Hello, this is a connection test. Please respond with 'OK'.",
                    "max_tokens": 50,
                    "timeout": 30.0
                },
                "image": {
                    "prompt": "A simple red circle on white background",
                    "max_tokens": None,
                    "timeout": 120.0
                },
                "video": {
                    "prompt": "A peaceful sunset over the ocean",
                    "max_tokens": None,
                    "timeout": 300.0
                }
            }
            return configs.get(model_type, configs["text"])

        model_type = get_model_type(
            api_key_record.provider, api_key_record.model_name)
        test_config = get_test_config(model_type)
        test_message = test_config["prompt"]

        if api_key_record.provider == "google":
            import google.generativeai as genai
            import os

            from app.core.config import get_settings
            settings = get_settings()
            original_http_proxy = os.environ.get("HTTP_PROXY")
            original_https_proxy = os.environ.get("HTTPS_PROXY")

            if settings.HTTPS_PROXY:
                os.environ["HTTPS_PROXY"] = settings.HTTPS_PROXY
            if settings.HTTP_PROXY:
                os.environ["HTTP_PROXY"] = settings.HTTP_PROXY

            try:
                genai.configure(api_key=decrypted_key)
                model = genai.GenerativeModel(api_key_record.model_name)
                response = model.generate_content(test_message)
                test_result = response.text
            finally:
                if original_http_proxy:
                    os.environ["HTTP_PROXY"] = original_http_proxy
                elif "HTTP_PROXY" in os.environ:
                    del os.environ["HTTP_PROXY"]
                if original_https_proxy:
                    os.environ["HTTPS_PROXY"] = original_https_proxy
                elif "HTTPS_PROXY" in os.environ:
                    del os.environ["HTTPS_PROXY"]
        else:
            headers = {
                "Authorization": f"Bearer {decrypted_key}",
                "Content-Type": "application/json"
            }

            if api_key_record.provider == "openrouter":
                from app.core.config import get_settings
                settings = get_settings()
                headers["HTTP-Referer"] = settings.APP_BASE_URL
                headers["X-Title"] = settings.APP_NAME

            payload = {
                "model": api_key_record.model_name,
                "messages": [{"role": "user", "content": test_message}]
            }
            if test_config.get("max_tokens"):
                payload["max_tokens"] = test_config["max_tokens"]

            from app.tools.proxy_router import get_proxy_for_url
            proxy = get_proxy_for_url(f"{api_base}/chat/completions")

            logger.info(
                f"API测试: provider={api_key_record.provider}, model_type={model_type}, proxy={proxy}")

            if proxy:
                async with httpx.AsyncClient(timeout=test_config["timeout"], proxy=proxy) as client:
                    response = await client.post(
                        f"{api_base}/chat/completions",
                        headers=headers,
                        json=payload
                    )
            else:
                async with httpx.AsyncClient(timeout=test_config["timeout"], trust_env=False) as client:
                    response = await client.post(
                        f"{api_base}/chat/completions",
                        headers=headers,
                        json=payload
                    )

            if response.status_code == 404 and model_type == "video":
                logger.info(
                    f"chat/completions 返回 404，尝试 /v2/videos/generations 端点")
                video_payload = {
                    "model": api_key_record.model_name,
                    "prompt": test_message
                }
                if proxy:
                    async with httpx.AsyncClient(timeout=test_config["timeout"], proxy=proxy) as client:
                        response = await client.post(
                            f"{api_base}/v2/videos/generations",
                            headers=headers,
                            json=video_payload
                        )
                else:
                    async with httpx.AsyncClient(timeout=test_config["timeout"], trust_env=False) as client:
                        response = await client.post(
                            f"{api_base}/v2/videos/generations",
                            headers=headers,
                            json=video_payload
                        )

            if response.status_code != 200:
                error_detail = response.json().get("error", {}).get("message", response.text)
                api_key_record.is_valid = False
                await db.commit()
                return ResponseModel(data=APIKeyTestResult(
                    success=False,
                    message=f"API调用失败: {error_detail}"
                ))

            result = response.json()
            if model_type == "video" and result.get("status"):
                test_result = f"视频任务已创建: {result.get('id', 'unknown')}"
            else:
                test_result = result.get("choices", [{}])[0].get(
                    "message", {}).get("content", "")

        api_key_record.is_valid = True
        await db.commit()

        logger.info(f"API Key 测试成功: {api_key_record.provider}")

        return ResponseModel(data=APIKeyTestResult(
            success=True,
            message="API Key 配置正确，连接测试成功"
        ))

    except httpx.TimeoutException:
        api_key_record.is_valid = False
        await db.commit()
        return ResponseModel(data=APIKeyTestResult(
            success=False,
            message="连接超时，请检查网络或API地址"
        ))
    except Exception as e:
        logger.error(f"API Key 测试失败: {str(e)}", exc_info=True)
        api_key_record.is_valid = False
        await db.commit()
        return ResponseModel(data=APIKeyTestResult(
            success=False,
            message=f"测试失败: {str(e)}"
        ))


async def _test_search_api_key(provider: str, api_key: str, logger) -> ResponseModel:
    """测试搜索服务API Key是否有效（支持博查AI和百度搜索）"""
    from app.core.config import SEARCH_PROVIDERS

    provider_config = SEARCH_PROVIDERS.get(provider)
    if not provider_config:
        return ResponseModel(data=APIKeyTestResult(
            success=False,
            message=f"未知的搜索服务提供商: {provider}"
        ))

    api_base = provider_config["api_base"]

    try:
        if provider == "bocha":
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                response = await client.post(
                    f"{api_base}/web-search",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": "test",
                        "count": 1,
                        "summary": False
                    }
                )

                if response.status_code == 200:
                    logger.info(f"博查AI API Key 测试成功")
                    return ResponseModel(data=APIKeyTestResult(
                        success=True,
                        message="博查AI搜索 API Key 配置正确，连接测试成功",
                        provider=provider
                    ))
                elif response.status_code == 401:
                    return ResponseModel(data=APIKeyTestResult(
                        success=False,
                        message="API Key 无效，请检查是否正确",
                        provider=provider
                    ))
                else:
                    error_msg = response.text
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", error_msg)
                    except (json.JSONDecodeError, ValueError):
                        pass
                    return ResponseModel(data=APIKeyTestResult(
                        success=False,
                        message=f"博查AI API 调用失败: {error_msg}",
                        provider=provider
                    ))

        elif provider == "baidu":
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                response = await client.post(
                    f"{api_base}/ai_search/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "messages": [{"role": "user", "content": "test"}],
                        "search_source": "baidu_search_v2",
                        "search_filter": {"search_type": "web", "top_k": 1},
                        "stream": False
                    }
                )

                if response.status_code == 200:
                    logger.info(f"百度搜索 API Key 测试成功")
                    return ResponseModel(data=APIKeyTestResult(
                        success=True,
                        message="百度搜索 API Key 配置正确，连接测试成功",
                        provider=provider
                    ))
                elif response.status_code == 401:
                    return ResponseModel(data=APIKeyTestResult(
                        success=False,
                        message="API Key 无效或格式错误，百度API Key格式应为：bce-v3/ALTAK-xxx/xxx",
                        provider=provider
                    ))
                else:
                    error_msg = response.text
                    try:
                        error_data = response.json()
                        error_msg = error_data.get(
                            "error", {}).get("message", error_msg)
                    except (json.JSONDecodeError, ValueError):
                        pass
                    return ResponseModel(data=APIKeyTestResult(
                        success=False,
                        message=f"百度搜索 API 调用失败: {error_msg}",
                        provider=provider
                    ))

    except httpx.TimeoutException:
        logger.error(f"搜索服务API Key 测试超时: {provider}")
        return ResponseModel(data=APIKeyTestResult(
            success=False,
            message="连接超时，请检查网络",
            provider=provider
        ))
    except Exception as e:
        logger.error(f"搜索服务API Key 测试失败: {str(e)}", exc_info=True)
        return ResponseModel(data=APIKeyTestResult(
            success=False,
            message=f"测试失败: {str(e)}",
            provider=provider
        ))
