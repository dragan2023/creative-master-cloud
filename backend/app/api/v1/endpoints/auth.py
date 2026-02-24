"""
用户认证 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    mask_api_key,
    api_key_encryption
)
from app.core.config import get_settings
from app.core.logger import get_logger
from app.api.deps import get_current_user
from app.models import User, UserRole, UserAPIKey
from app.schemas.common import ResponseModel
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserLogin,
    TokenResponse,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyTest,
    APIKeyTestResult
)
from app.models import SystemConfig
from pydantic import BaseModel, Field
from typing import Optional

# ==================== 配置模型定义 ====================


class ProxyConfig(BaseModel):
    """代理配置"""
    http_proxy: Optional[str] = Field(None, description="HTTP代理地址")
    https_proxy: Optional[str] = Field(None, description="HTTPS代理地址")
    is_enabled: bool = Field(False, description="是否启用代理")


class ProxyConfigResponse(BaseModel):
    """代理配置响应"""
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    is_enabled: bool = False


class PreprocessorConfig(BaseModel):
    """文档预处理配置"""
    doc_preprocessor_enabled: bool = Field(True, description="是否启用文档预处理")
    marker_enabled: bool = Field(True, description="是否启用Marker")
    semantic_chunk_enabled: bool = Field(True, description="是否启用语义分块")
    semantic_chunk_size: int = Field(1024, description="语义分块大小")
    semantic_threshold: float = Field(0.7, description="语义阈值")
    summarization_enabled: bool = Field(False, description="是否启用摘要")
    graphrag_enabled: bool = Field(True, description="是否启用GraphRAG知识图谱")


class PreprocessorConfigResponse(BaseModel):
    """文档预处理配置响应"""
    doc_preprocessor_enabled: bool = True
    marker_enabled: bool = True
    semantic_chunk_enabled: bool = True
    semantic_chunk_size: int = 1024
    semantic_threshold: float = 0.7
    summarization_enabled: bool = False
    graphrag_enabled: bool = True
    marker_model_dir: str = ""


router = APIRouter(prefix="/auth", tags=["认证"])
settings = get_settings()


# ==================== 用户注册/登录 ====================

@router.post("/register", response_model=ResponseModel[UserResponse])
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册

    Args:
        user_data: 用户注册数据
        db: 数据库会话

    Returns:
        用户信息
    """
    logger = get_logger("auth")

    # 检查用户名是否存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 检查邮箱是否存在
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    # 创建用户
    user = User(
        username=user_data.username,
        email=user_data.email,
        nickname=user_data.nickname or user_data.username,
        hashed_password=get_password_hash(user_data.password),
        role=UserRole.USER
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"新用户注册: {user.username}")

    return ResponseModel(data=UserResponse.model_validate(user))


@router.post("/login", response_model=ResponseModel[TokenResponse])
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录

    Args:
        credentials: 登录凭据
        db: 数据库会话

    Returns:
        Token 和用户信息
    """
    logger = get_logger("auth")

    # 查询用户
    result = await db.execute(select(User).where(User.username == credentials.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户已被禁用")

    # 创建 Token
    access_token = create_access_token(subject=user.id)

    logger.info(f"用户登录: {user.username}")

    return ResponseModel(data=TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    ))


# ==================== 用户信息 ====================

@router.get("/me", response_model=ResponseModel[UserResponse])
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息"""
    return ResponseModel(data=UserResponse.model_validate(current_user))


@router.put("/me", response_model=ResponseModel[UserResponse])
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新当前用户信息"""
    if user_data.nickname:
        current_user.nickname = user_data.nickname
    if user_data.avatar:
        current_user.avatar = user_data.avatar

    await db.commit()
    await db.refresh(current_user)

    return ResponseModel(data=UserResponse.model_validate(current_user))


# ==================== API Key 管理 ====================

@router.get("/api-keys", response_model=ResponseModel[list])
async def get_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的 API Key 列表"""
    result = await db.execute(
        select(UserAPIKey).where(UserAPIKey.user_id == current_user.id)
    )
    api_keys = result.scalars().all()

    data = [
        APIKeyResponse(
            id=key.id,
            provider=key.provider,
            model_name=key.model_name,
            api_key_masked=mask_api_key(
                api_key_encryption.decrypt(key.encrypted_key)),
            api_base=key.api_base,
            is_default=key.is_default,
            is_valid=key.is_valid,
            last_used_at=str(key.last_used_at) if key.last_used_at else None,
            created_at=str(key.created_at) if key.created_at else None
        )
        for key in api_keys
    ]

    return ResponseModel(data=data)


@router.post("/api-keys", response_model=ResponseModel[APIKeyResponse])
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建 API Key"""
    logger = get_logger(str(current_user.id))

    # 加密 API Key
    encrypted_key = api_key_encryption.encrypt(key_data.api_key)

    # 如果设为默认，取消其他默认
    if key_data.is_default:
        result = await db.execute(
            select(UserAPIKey).where(
                UserAPIKey.user_id == current_user.id,
                UserAPIKey.is_default == True
            )
        )
        for key in result.scalars().all():
            key.is_default = False

    # 创建新记录
    api_key = UserAPIKey(
        user_id=current_user.id,
        provider=key_data.provider,
        model_name=key_data.model_name,
        encrypted_key=encrypted_key,
        api_base=key_data.api_base,
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


@router.put("/api-keys/{key_id}", response_model=ResponseModel[APIKeyResponse])
async def update_api_key(
    key_id: int,
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新 API Key"""
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.id == key_id,
            UserAPIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API Key 不存在")

    # 更新字段
    api_key.provider = key_data.provider
    api_key.model_name = key_data.model_name
    api_key.encrypted_key = api_key_encryption.encrypt(key_data.api_key)
    api_key.api_base = key_data.api_base

    if key_data.is_default:
        # 取消其他默认
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
        is_default=api_key.is_default,
        is_valid=api_key.is_valid,
        last_used_at=api_key.last_used_at
    ))


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除 API Key"""
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.id == key_id,
            UserAPIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API Key 不存在")

    await db.delete(api_key)
    await db.commit()

    return ResponseModel(message="删除成功")


@router.put("/api-keys/{key_id}/default", response_model=ResponseModel[APIKeyResponse])
async def set_default_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """设置默认 API Key"""
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.id == key_id,
            UserAPIKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API Key 不存在")

    # 取消其他默认
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == current_user.id,
            UserAPIKey.is_default == True,
            UserAPIKey.id != key_id
        )
    )
    for key in result.scalars().all():
        key.is_default = False

    # 设置当前为默认
    api_key.is_default = True
    await db.commit()
    await db.refresh(api_key)

    return ResponseModel(data=APIKeyResponse(
        id=api_key.id,
        provider=api_key.provider,
        model_name=api_key.model_name,
        api_key_masked=mask_api_key(api_key.encrypted_key),
        api_base=api_key.api_base,
        is_default=api_key.is_default,
        is_valid=api_key.is_valid,
        last_used_at=api_key.last_used_at
    ))


@router.post("/api-keys/test", response_model=ResponseModel[APIKeyTestResult])
async def test_api_key(
    test_data: APIKeyTest,
    current_user: User = Depends(get_current_user)
):
    """测试 API Key 是否有效（真实调用API验证）"""
    from app.agents import get_llm_manager
    import httpx
    import asyncio

    logger = get_logger(str(current_user.id))

    try:
        llm_manager = get_llm_manager()
        provider = llm_manager.create_provider(
            provider_name=test_data.provider,
            api_key=test_data.api_key,
            model_name=test_data.model_name,
            api_base=test_data.api_base
        )

        # 获取模型信息
        model_info = provider.get_model_info()

        # 真实API调用测试
        test_message = "Hello, this is a connection test. Please respond with 'OK'."

        if test_data.provider == "google":
            # Google Gemini API测试
            import google.generativeai as genai
            genai.configure(api_key=test_data.api_key)
            model = genai.GenerativeModel(test_data.model_name)
            response = model.generate_content(test_message)
            test_result = response.text
        else:
            # OpenAI兼容格式API测试
            api_base = test_data.api_base or model_info.get("api_base", "")

            # 检查api_base是否有效
            if not api_base:
                return ResponseModel(data=APIKeyTestResult(
                    success=False,
                    message="请提供API地址（api_base）"
                ))

            # 确保api_base以http://或https://开头
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
                "messages": [{"role": "user", "content": test_message}],
                "max_tokens": 50
            }

            # 硬编码代理路由：根据域名列表判断是否需要代理
            from app.tools.proxy_router import get_proxy_for_url
            proxy = get_proxy_for_url(f"{api_base}/chat/completions")

            logger.info(f"API测试: provider={test_data.provider}, proxy={proxy}")

            # 国内服务商：trust_env=False 禁用环境变量代理，确保直连
            # 国外服务商：proxy=proxy_url 使用代理
            if proxy:
                async with httpx.AsyncClient(timeout=30.0, proxy=proxy) as client:
                    response = await client.post(
                        f"{api_base}/chat/completions",
                        headers=headers,
                        json=payload
                    )
            else:
                async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                    response = await client.post(
                        f"{api_base}/chat/completions",
                        headers=headers,
                        json=payload
                    )

                if response.status_code != 200:
                    error_detail = response.json().get("error", {}).get("message", response.text)
                    return ResponseModel(data=APIKeyTestResult(
                        success=False,
                        message=f"API调用失败: {error_detail}",
                        model_info=model_info
                    ))

                result = response.json()
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


# ==================== 预置模型 ====================

@router.get("/models", response_model=ResponseModel[dict])
async def get_preset_models():
    """获取预置模型列表"""
    from app.core.config import PRESET_MODELS
    return ResponseModel(data=PRESET_MODELS)


@router.post("/api-keys/{key_id}/test", response_model=ResponseModel[APIKeyTestResult])
async def test_saved_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """测试已保存的 API Key"""
    import httpx

    logger = get_logger(str(current_user.id))

    # 获取API Key
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.id == key_id,
            UserAPIKey.user_id == current_user.id
        )
    )
    api_key_record = result.scalar_one_or_none()

    if not api_key_record:
        raise HTTPException(status_code=404, detail="API Key 不存在")

    # 解密API Key
    decrypted_key = api_key_encryption.decrypt(api_key_record.encrypted_key)

    try:
        # 获取预置模型配置
        from app.core.config import PRESET_MODELS
        preset = PRESET_MODELS.get(api_key_record.provider, {})
        api_base = api_key_record.api_base or preset.get("api_base")

        test_message = "Hello, this is a connection test. Please respond with 'OK'."

        if api_key_record.provider == "google":
            import google.generativeai as genai
            import os

            # 设置代理（Google SDK通过环境变量使用代理）
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
                # 恢复原始环境变量
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

            # OpenRouter 需要额外的请求头
            if api_key_record.provider == "openrouter":
                from app.core.config import get_settings
                settings = get_settings()
                headers["HTTP-Referer"] = settings.APP_BASE_URL
                headers["X-Title"] = settings.APP_NAME

            payload = {
                "model": api_key_record.model_name,
                "messages": [{"role": "user", "content": test_message}],
                "max_tokens": 50
            }

            # 硬编码代理路由：根据域名列表判断是否需要代理
            from app.tools.proxy_router import get_proxy_for_url
            proxy = get_proxy_for_url(f"{api_base}/chat/completions")

            logger.info(
                f"API测试: provider={api_key_record.provider}, proxy={proxy}")

            # 国内服务商：trust_env=False 禁用环境变量代理，确保直连
            # 国外服务商：proxy=proxy_url 使用代理
            if proxy:
                async with httpx.AsyncClient(timeout=30.0, proxy=proxy) as client:
                    response = await client.post(
                        f"{api_base}/chat/completions",
                        headers=headers,
                        json=payload
                    )
            else:
                async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                    response = await client.post(
                        f"{api_base}/chat/completions",
                        headers=headers,
                        json=payload
                    )

            # 检查响应状态（无论是否使用代理都需要检查）
            if response.status_code != 200:
                error_detail = response.json().get("error", {}).get("message", response.text)
                api_key_record.is_valid = False
                await db.commit()
                return ResponseModel(data=APIKeyTestResult(
                    success=False,
                    message=f"API调用失败: {error_detail}"
                ))

            result = response.json()
            test_result = result.get("choices", [{}])[0].get(
                "message", {}).get("content", "")

        # 更新状态
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


# ==================== 用户个人配置 ====================

@router.get("/config/proxy", response_model=ResponseModel[ProxyConfigResponse])
async def get_user_proxy_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户代理配置（用户级别）"""
    import json

    # 从数据库获取配置（使用用户特定的配置键）
    config_key = f"user_proxy_config_{current_user.id}"
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.id == config_key)
    )
    config = result.scalar_one_or_none()

    proxy_config = ProxyConfigResponse(
        model_cache_dir=settings.get_chroma_model_cache_dir()
    )

    if config and config.config_value:
        try:
            data = json.loads(config.config_value)
            proxy_config.http_proxy = data.get("http_proxy")
            proxy_config.https_proxy = data.get("https_proxy")
            proxy_config.is_enabled = config.is_enabled
        except:
            pass

    return ResponseModel(data=proxy_config)


@router.post("/config/proxy")
async def set_user_proxy_config(
    config_data: ProxyConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """设置用户代理配置（用户级别）"""
    import json

    logger = get_logger(str(current_user.id))

    # 保存到数据库（使用用户特定的配置键）
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


@router.post("/config/proxy/test")
async def test_user_proxy(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """测试用户代理连接（用户级别）"""
    import json
    import httpx

    # 获取用户代理配置
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

        # 测试代理连接 - 处理完整URL或仅端口号
        if http_proxy.startswith("http://") or http_proxy.startswith("https://"):
            proxy_url = http_proxy
        else:
            # 如果只有端口号，构造完整URL（使用当前主机或127.0.0.1）
            from app.core.config import get_settings
            settings = get_settings()
            # 从APP_BASE_URL解析主机，或默认使用127.0.0.1
            base_url = settings.APP_BASE_URL
            if "://" in base_url:
                host_part = base_url.split("://")[1].split("/")[0].split(":")[0]
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


@router.get("/config/preprocessor", response_model=ResponseModel[PreprocessorConfigResponse])
async def get_user_preprocessor_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户文档预处理配置（用户级别）"""
    import json

    # 从数据库获取配置（使用用户特定的配置键）
    config_key = f"user_preprocessor_config_{current_user.id}"
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.id == config_key)
    )
    config = result.scalar_one_or_none()

    default_config = PreprocessorConfigResponse(
        doc_preprocessor_enabled=True,
        marker_enabled=True,
        semantic_chunk_enabled=True,
        semantic_chunk_size=1024,
        semantic_threshold=0.7,
        summarization_enabled=False,
        graphrag_enabled=True,
        marker_model_dir=settings.MARKER_MODEL_DIR or ""
    )

    if config and config.config_value:
        try:
            data = json.loads(config.config_value)
            default_config.doc_preprocessor_enabled = data.get(
                "doc_preprocessor_enabled", True)
            default_config.marker_enabled = data.get("marker_enabled", True)
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
        except:
            pass

    return ResponseModel(data=default_config)


@router.post("/config/preprocessor")
async def set_user_preprocessor_config(
    config_data: PreprocessorConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """设置用户文档预处理配置（用户级别）"""
    import json

    logger = get_logger(str(current_user.id))

    # 保存到数据库（使用用户特定的配置键）
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
