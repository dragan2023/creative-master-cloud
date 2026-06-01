"""认证 API 端点包

FastAPI路由定义，将请求分发给各处理函数
"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.config import get_settings
from app.models import User
from app.schemas.common import ResponseModel
from app.schemas.user import (
    UserResponse,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyTest,
    APIKeyTestResult
)

from ._models import ProxyConfig, ProxyConfigResponse, PreprocessorConfig, PreprocessorConfigResponse, ThinkingModeConfig, ThinkingModeConfigResponse
from ._api_keys import (
    handle_get_api_keys,
    handle_create_api_key,
    handle_update_api_key,
    handle_delete_api_key,
    handle_set_default_api_key,
    handle_test_api_key,
    handle_test_saved_api_key,
)
from ._config import (
    handle_get_user_proxy_config,
    handle_set_user_proxy_config,
    handle_test_user_proxy,
    handle_get_user_preprocessor_config,
    handle_set_user_preprocessor_config,
    handle_get_thinking_mode_config,
    handle_set_thinking_mode_config,
)

router = APIRouter(prefix="/auth", tags=["配置"])
settings = get_settings()


# ==================== 用户信息 ====================

@router.get("/me", response_model=ResponseModel[UserResponse])
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息（返回默认用户）"""
    return ResponseModel(data=UserResponse.model_validate(current_user))


# ==================== API Key 管理 ====================

@router.get("/api-keys", response_model=ResponseModel[list])
async def get_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的 API Key 列表"""
    return await handle_get_api_keys(current_user, db)


@router.post("/api-keys", response_model=ResponseModel[APIKeyResponse])
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建 API Key"""
    return await handle_create_api_key(key_data, current_user, db)


@router.put("/api-keys/{key_id}", response_model=ResponseModel[APIKeyResponse])
async def update_api_key(
    key_id: int,
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新 API Key"""
    return await handle_update_api_key(key_id, key_data, current_user, db)


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除 API Key"""
    return await handle_delete_api_key(key_id, current_user, db)


@router.put("/api-keys/{key_id}/default", response_model=ResponseModel[APIKeyResponse])
async def set_default_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """设置默认 API Key"""
    return await handle_set_default_api_key(key_id, current_user, db)


@router.post("/api-keys/test", response_model=ResponseModel[APIKeyTestResult])
async def test_api_key(
    test_data: APIKeyTest,
    current_user: User = Depends(get_current_user)
):
    """测试 API Key 是否有效（真实调用API验证）"""
    return await handle_test_api_key(test_data, current_user)


# ==================== 预置模型 ====================

@router.get("/models", response_model=ResponseModel[dict])
async def get_preset_models():
    """获取预置模型列表"""
    from app.core.config import PRESET_MODELS
    return ResponseModel(data=PRESET_MODELS)


# ==================== 测试已保存的 API Key ====================

@router.post("/api-keys/{key_id}/test", response_model=ResponseModel[APIKeyTestResult])
async def test_saved_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """测试已保存的 API Key"""
    return await handle_test_saved_api_key(key_id, current_user, db)


# ==================== 用户代理配置 ====================

@router.get("/config/proxy", response_model=ResponseModel[ProxyConfigResponse])
async def get_user_proxy_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户代理配置（用户级别）"""
    return await handle_get_user_proxy_config(current_user, db)


@router.post("/config/proxy")
async def set_user_proxy_config(
    config_data: ProxyConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """设置用户代理配置（用户级别）"""
    return await handle_set_user_proxy_config(config_data, current_user, db)


@router.post("/config/proxy/test")
async def test_user_proxy(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """测试用户代理连接（用户级别）"""
    return await handle_test_user_proxy(current_user, db)


# ==================== 用户预处理配置 ====================

@router.get("/config/preprocessor", response_model=ResponseModel[PreprocessorConfigResponse])
async def get_user_preprocessor_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户文档预处理配置（用户级别）"""
    return await handle_get_user_preprocessor_config(current_user, db)


@router.post("/config/preprocessor")
async def set_user_preprocessor_config(
    config_data: PreprocessorConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """设置用户文档预处理配置（用户级别）"""
    return await handle_set_user_preprocessor_config(config_data, current_user, db)


# ==================== DeepSeek思考模式配置 ====================

@router.get("/config/thinking-mode", response_model=ResponseModel[ThinkingModeConfigResponse])
async def get_thinking_mode_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取DeepSeek思考模式配置（用户级别，回退到系统设置）"""
    return await handle_get_thinking_mode_config(current_user, db)


@router.post("/config/thinking-mode")
async def set_thinking_mode_config(
    config_data: ThinkingModeConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """设置DeepSeek思考模式配置（用户级别）"""
    return await handle_set_thinking_mode_config(config_data, current_user, db)
