"""
多Agent协作文学作品生成系统 - Agent配置API端点

模块: api.v1.endpoints
文件: agent_config.py
功能: 提供Agent模型配置的RESTful API接口，包括获取、更新配置和可用模型列表

依赖关系:
    - 依赖: app.agents.writing.agent_config (AgentConfig, AgentModelConfig, AgentRole)
    - 被依赖: app.api.v1.router (路由注册)

使用说明:
    本模块提供Agent配置的CRUD API，配置存储在内存中（单例模式）。
    所有端点需要JWT认证。

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, status, Query
from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    AppException,
    ErrorCode,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import ResponseModel
from app.agents.writing.agent_config import (
    AgentConfig, AgentModelConfig, get_default_agent_config, reset_default_agent_config
)
from app.agents.writing.base_agent import AgentRole

router = APIRouter(prefix="/agent-config", tags=["多Agent配置"])
logger = get_logger("agent_config")


# ==================== Schema定义 ====================

class AgentConfigResponse(BaseModel):
    """Agent配置响应"""
    role: str
    model_id: str
    provider: str
    temperature: float
    max_tokens: int
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    api_base: Optional[str] = None


class GlobalConfigResponse(BaseModel):
    """全局配置响应"""
    enable_stats: bool
    enable_retry: bool
    max_retries: int
    retry_delay: float


class FullAgentConfigResponse(BaseModel):
    """完整Agent配置响应"""
    configs: Dict[str, AgentConfigResponse]
    global_config: GlobalConfigResponse


class AgentConfigUpdateRequest(BaseModel):
    """Agent配置更新请求"""
    role: str = Field(..., description="Agent角色: orchestrator/structural/writer/logic_editor/style_editor/compliance/knowledge/assembler")
    model_id: Optional[str] = Field(default=None, description="模型ID")
    provider: Optional[str] = Field(default=None, description="供应商名称")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(default=None, ge=256, le=128000, description="最大输出token数")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Top-p采样参数")
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="频率惩罚")
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="存在惩罚")
    api_base: Optional[str] = Field(default=None, description="自定义API端点地址")
    api_key: Optional[str] = Field(default=None, description="API密钥（可选，不持久化）")


class GlobalConfigUpdateRequest(BaseModel):
    """全局配置更新请求"""
    enable_stats: Optional[bool] = Field(default=None, description="是否启用统计记录")
    enable_retry: Optional[bool] = Field(default=None, description="是否启用失败重试")
    max_retries: Optional[int] = Field(default=None, ge=0, le=10, description="最大重试次数")
    retry_delay: Optional[float] = Field(default=None, ge=0.0, le=60.0, description="重试延迟（秒）")


class AgentConfigUpdateBody(BaseModel):
    """配置更新请求体"""
    agent_configs: Optional[List[AgentConfigUpdateRequest]] = Field(default=None, description="Agent配置列表")
    global_config: Optional[GlobalConfigUpdateRequest] = Field(default=None, description="全局配置")


class ModelInfoResponse(BaseModel):
    """模型信息响应"""
    id: str
    name: str
    description: str
    max_tokens: int
    type: str


class ProviderModelsResponse(BaseModel):
    """供应商模型列表响应"""
    name: str
    models: List[ModelInfoResponse]
    api_base: str
    doc_url: str
    notice: str


class AvailableModelsResponse(BaseModel):
    """可用模型列表响应"""
    providers: Dict[str, ProviderModelsResponse]


class RecommendedModelsResponse(BaseModel):
    """推荐模型响应"""
    role: str
    recommended_models: List[str]


class ProviderModelInfo(BaseModel):
    """Provider模型信息"""
    id: str
    name: str


class ProviderInfo(BaseModel):
    """Provider信息"""
    name: str
    display_name: str
    api_base: str
    is_preset: bool
    has_api_key: bool
    models: List[ProviderModelInfo]


class ProvidersResponse(BaseModel):
    """Provider列表响应"""
    providers: List[ProviderInfo]


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    provider: str = Field(..., description="供应商名称")
    model_id: str = Field(..., description="模型ID")
    api_base: Optional[str] = Field(default=None, description="自定义API端点（可选）")
    api_key: Optional[str] = Field(default=None, description="API密钥（可选，不传则从DB获取）")


# ==================== 辅助函数 ====================

def _build_agent_config_response(role: str, config: AgentModelConfig) -> AgentConfigResponse:
    """构建Agent配置响应"""
    return AgentConfigResponse(
        role=role,
        model_id=config.model_id,
        provider=config.provider,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        top_p=config.top_p,
        frequency_penalty=config.frequency_penalty,
        presence_penalty=config.presence_penalty,
        api_base=config.api_base
        # 注意：api_key 不返回，仅用于运行时
    )


def _build_global_config_response(config: AgentConfig) -> GlobalConfigResponse:
    """构建全局配置响应"""
    return GlobalConfigResponse(
        enable_stats=config.enable_stats,
        enable_retry=config.enable_retry,
        max_retries=config.max_retries,
        retry_delay=config.retry_delay
    )


def _get_role_from_string(role_str: str) -> AgentRole:
    """从字符串获取AgentRole枚举"""
    role_map = {
        "orchestrator": AgentRole.ORCHESTRATOR,
        "structural": AgentRole.STRUCTURAL,
        "writer": AgentRole.WRITER,
        "logic_editor": AgentRole.LOGIC_EDITOR,
        "style_editor": AgentRole.STYLE_EDITOR,
        "compliance": AgentRole.COMPLIANCE,
        "knowledge": AgentRole.KNOWLEDGE,
        "assembler": AgentRole.ASSEMBLER,
    }
    role = role_map.get(role_str.lower())
    if not role:
        raise ValueError(f"无效的角色: {role_str}")
    return role


# ==================== API端点 ====================

@router.get("", response_model=ResponseModel[FullAgentConfigResponse])
async def get_agent_config(
    current_user: User = Depends(get_current_user)
):
    """
    获取当前Agent模型配置
    
    返回所有Agent角色的模型配置和全局设置。
    """
    try:
        config = get_default_agent_config()
        
        # 构建各角色配置响应
        configs = {}
        for role_str, agent_config in config.configs.items():
            configs[role_str] = _build_agent_config_response(role_str, agent_config)
        
        response_data = FullAgentConfigResponse(
            configs=configs,
            global_config=_build_global_config_response(config)
        )
        
        return ResponseModel(
            success=True,
            code=200,
            message="获取配置成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"获取Agent配置失败: {e}")
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            f"获取配置失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.put("", response_model=ResponseModel[FullAgentConfigResponse])
async def update_agent_config(
    request: AgentConfigUpdateBody,
    current_user: User = Depends(get_current_user)
):
    """
    更新Agent模型配置
    
    支持更新单个或多个Agent配置，以及全局设置。
    """
    try:
        config = get_default_agent_config()
        
        # 更新Agent配置
        if request.agent_configs:
            for agent_update in request.agent_configs:
                try:
                    role = _get_role_from_string(agent_update.role)
                except ValueError as e:
                    raise ValidationException(str(e))

                # 获取当前配置
                current_agent_config = config.get_config(role)
                if not current_agent_config:
                    raise ResourceNotFoundException(f"未找到角色配置: {agent_update.role}")
                
                # 更新配置字段
                updated_config = AgentModelConfig(
                    model_id=agent_update.model_id if agent_update.model_id is not None else current_agent_config.model_id,
                    provider=agent_update.provider if agent_update.provider is not None else current_agent_config.provider,
                    temperature=agent_update.temperature if agent_update.temperature is not None else current_agent_config.temperature,
                    max_tokens=agent_update.max_tokens if agent_update.max_tokens is not None else current_agent_config.max_tokens,
                    top_p=agent_update.top_p if agent_update.top_p is not None else current_agent_config.top_p,
                    frequency_penalty=agent_update.frequency_penalty if agent_update.frequency_penalty is not None else current_agent_config.frequency_penalty,
                    presence_penalty=agent_update.presence_penalty if agent_update.presence_penalty is not None else current_agent_config.presence_penalty,
                    api_base=agent_update.api_base if agent_update.api_base is not None else current_agent_config.api_base,
                    # api_key 仅在传入时更新，不保留到配置中（运行时使用）
                    api_key=agent_update.api_key if agent_update.api_key is not None else current_agent_config.api_key
                )
                
                config.update_config(role, updated_config)
                logger.info(f"更新Agent配置: role={agent_update.role}, model_id={updated_config.model_id}")
        
        # 更新全局配置
        if request.global_config:
            global_update = request.global_config
            if global_update.enable_stats is not None:
                config.enable_stats = global_update.enable_stats
            if global_update.enable_retry is not None:
                config.enable_retry = global_update.enable_retry
            if global_update.max_retries is not None:
                config.max_retries = global_update.max_retries
            if global_update.retry_delay is not None:
                config.retry_delay = global_update.retry_delay
            logger.info("更新全局配置")
        
        # 构建响应
        configs = {}
        for role_str, agent_config in config.configs.items():
            configs[role_str] = _build_agent_config_response(role_str, agent_config)
        
        response_data = FullAgentConfigResponse(
            configs=configs,
            global_config=_build_global_config_response(config)
        )
        
        return ResponseModel(
            success=True,
            code=200,
            message="配置更新成功",
            data=response_data
        )
        
    except ValidationException:
        raise
    except ResourceNotFoundException:
        raise
    except Exception as e:
        logger.error(f"更新Agent配置失败: {e}")
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            f"更新配置失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.post("/reset", response_model=ResponseModel[FullAgentConfigResponse])
async def reset_agent_config(
    role: Optional[str] = Query(None, description="要重置的角色，不传则重置所有"),
    current_user: User = Depends(get_current_user)
):
    """
    重置Agent配置为默认值
    
    可重置单个角色或所有配置。
    """
    try:
        config = get_default_agent_config()
        
        if role:
            # 重置单个角色
            try:
                agent_role = _get_role_from_string(role)
            except ValueError as e:
                raise ValidationException(str(e))
            config.reset_config(agent_role)
            logger.info(f"重置Agent配置: role={role}")
        else:
            # 重置所有配置
            config.reset_all()
            logger.info("重置所有Agent配置")
        
        # 构建响应
        configs = {}
        for role_str, agent_config in config.configs.items():
            configs[role_str] = _build_agent_config_response(role_str, agent_config)
        
        response_data = FullAgentConfigResponse(
            configs=configs,
            global_config=_build_global_config_response(config)
        )
        
        return ResponseModel(
            success=True,
            code=200,
            message="配置重置成功",
            data=response_data
        )
        
    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"重置Agent配置失败: {e}")
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            f"重置配置失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/providers", response_model=ResponseModel[ProvidersResponse], summary="获取可用的AI服务提供商列表")
async def get_available_providers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取系统预设Provider + 用户自定义Provider的合并列表。
    
    返回每个Provider的名称、API地址、是否预设、是否有API Key以及可用模型列表。
    最后附加一个 "custom" 选项，允许用户完全自定义。
    """
    from app.core.config import PRESET_MODELS
    from app.models.api_key import UserAPIKey
    from sqlalchemy import select
    
    try:
        providers = []
        
        # 1. 从PRESET_MODELS获取预设provider
        for provider_name, provider_config in PRESET_MODELS.items():
            # 跳过图像和视频生成的provider（写作系统只需要文本模型）
            if '-image' in provider_name or '-video' in provider_name:
                continue
            
            # 获取模型列表
            models = [
                ProviderModelInfo(
                    id=model.get("id", ""),
                    name=model.get("name", model.get("id", ""))
                )
                for model in provider_config.get("models", [])
                if model.get("type") == "text"
            ]
            
            # 查询用户是否已配置该provider的API Key
            has_api_key = False
            try:
                stmt = select(UserAPIKey).where(
                    UserAPIKey.provider == provider_name,
                    UserAPIKey.is_valid == True
                )
                result = await db.execute(stmt)
                api_key_record = result.scalar_one_or_none()
                has_api_key = api_key_record is not None
            except Exception as e:
                logger.warning(f"检查API Key失败: {e}")
                pass
            
            providers.append(ProviderInfo(
                name=provider_name,
                display_name=provider_config.get("name", provider_name),
                api_base=provider_config.get("api_base", ""),
                is_preset=True,
                has_api_key=has_api_key,
                models=models
            ))
        
        
        # 2. 添加一个 "custom" 选项，允许用户完全自定义
        providers.append(ProviderInfo(
            name="custom",
            display_name="自定义服务商",
            api_base="",
            is_preset=False,
            has_api_key=False,
            models=[]
        ))
        
        return ResponseModel(
            success=True,
            code=200,
            message="获取Provider列表成功",
            data=ProvidersResponse(providers=providers)
        )
        
    except Exception as e:
        logger.error(f"获取Provider列表失败: {e}")
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            f"获取Provider列表失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/models", response_model=ResponseModel[AvailableModelsResponse])
async def get_available_models(
    current_user: User = Depends(get_current_user)
):
    """
    获取可用模型列表
    
    返回按供应商分组的可用模型列表。
    """
    try:
        available_models = AgentConfig.get_available_models()
        
        # 构建响应
        providers = {}
        for provider_name, provider_data in available_models.items():
            models = []
            for model in provider_data.get("models", []):
                models.append(ModelInfoResponse(
                    id=model.get("id", ""),
                    name=model.get("name", ""),
                    description=model.get("description", ""),
                    max_tokens=model.get("max_tokens", 0),
                    type=model.get("type", "text")
                ))
            
            providers[provider_name] = ProviderModelsResponse(
                name=provider_data.get("name", provider_name),
                models=models,
                api_base=provider_data.get("api_base", ""),
                doc_url=provider_data.get("doc_url", ""),
                notice=provider_data.get("notice", "")
            )
        
        return ResponseModel(
            success=True,
            code=200,
            message="获取可用模型列表成功",
            data=AvailableModelsResponse(providers=providers)
        )
        
    except Exception as e:
        logger.error(f"获取可用模型列表失败: {e}")
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            f"获取模型列表失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/models/recommended", response_model=ResponseModel[List[RecommendedModelsResponse]])
async def get_recommended_models(
    current_user: User = Depends(get_current_user)
):
    """
    获取每个角色推荐的模型列表
    
    基于模型能力和角色需求推荐合适的模型。
    """
    try:
        recommended = AgentConfig.get_recommended_models()
        
        # 构建响应
        result = []
        for role, model_ids in recommended.items():
            result.append(RecommendedModelsResponse(
                role=role.value,
                recommended_models=model_ids
            ))
        
        return ResponseModel(
            success=True,
            code=200,
            message="获取推荐模型成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"获取推荐模型失败: {e}")
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            f"获取推荐模型失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/models/{model_id}", response_model=ResponseModel[Dict[str, Any]])
async def get_model_info(
    model_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取指定模型的详细信息
    """
    try:
        model_info = AgentConfig.get_model_info(model_id)

        if not model_info:
            raise ResourceNotFoundException(f"模型不存在: {model_id}")

        return ResponseModel(
            success=True,
            code=200,
            message="获取模型信息成功",
            data=model_info
        )

    except ResourceNotFoundException:
        raise
    except Exception as e:
        logger.error(f"获取模型信息失败: model_id={model_id}, error={e}")
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            f"获取模型信息失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.post("/test-connection", summary="测试模型连接")
async def test_model_connection(
    request_data: TestConnectionRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    测试指定模型的连接，并返回模型能力信息（包括max_tokens）。
    
    请求体支持自定义API配置:
    - provider: 供应商名称
    - model_id: 模型ID
    - api_base: 自定义API端点（可选）
    - api_key: API密钥（可选，不传则从DB获取）
    """
    from app.agents.llm_manager import get_llm_manager
    from app.agents.base_provider import LLMResponse
    from app.core.config import PRESET_MODELS
    from app.models.api_key import UserAPIKey
    from app.core.security import api_key_encryption
    from sqlalchemy import select
    import asyncio
    
    model_id = request_data.model_id
    provider_name = request_data.provider
    api_base = request_data.api_base
    api_key = request_data.api_key

    logger.info(f"测试模型连接: model_id={model_id}, provider={provider_name}, api_base={api_base}")

    try:
        # 获取LLM管理器
        llm_manager = get_llm_manager()
        
        # 确定使用的api_base
        final_api_base = api_base
        if not final_api_base:
            preset = PRESET_MODELS.get(provider_name, {})
            final_api_base = preset.get("api_base")
        
        # 确定使用的api_key
        final_api_key = api_key
        if not final_api_key:
            # 尝试从DB获取
            try:
                stmt = select(UserAPIKey).where(
                    UserAPIKey.provider == provider_name,
                    UserAPIKey.is_valid == True
                ).order_by(UserAPIKey.created_at.desc())
                result = await db.execute(stmt)
                api_key_record = result.scalar_one_or_none()
                if api_key_record:
                    final_api_key = api_key_encryption.decrypt(api_key_record.encrypted_key)
            except Exception as e:
                logger.warning(f"从DB获取API Key失败: {e}")
        
        
        if not final_api_key:
            return ResponseModel(
                success=True,
                code=200,
                message="连接测试完成",
                data={
                    "success": False,
                    "max_tokens": None,
                    "message": f"未找到 {provider_name} 的 API Key，请先配置或传入 api_key"
                }
            )
        
        
        # 使用自定义配置创建provider
        provider = llm_manager.create_provider(
            provider_name=provider_name,
            api_key=final_api_key,
            model_name=model_id,
            api_base=final_api_base
        )
        
        # 发送测试消息
        test_messages = [{"role": "user", "content": "Hello, respond with OK"}]
        
        # 使用asyncio.wait_for设置超时
        try:
            response: LLMResponse = await asyncio.wait_for(
                provider.generate(
                    prompt="Hello, respond with OK",
                    system_prompt=None,
                    temperature=0.7,
                    max_tokens=50
                ),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"测试连接超时: model_id={model_id}, provider={provider_name}")
            return ResponseModel(
                success=True,
                code=200,
                message="连接测试完成",
                data={
                    "success": False,
                    "max_tokens": None,
                    "message": "连接超时（超过30秒）"
                }
            )
        
        # 获取模型信息以返回max_tokens
        model_info = AgentConfig.get_model_info(model_id)
        max_tokens = model_info.get("max_tokens") if model_info else None
        
        logger.info(f"测试连接成功: model_id={model_id}, provider={provider_name}")
        
        return ResponseModel(
            success=True,
            code=200,
            message="连接测试完成",
            data={
                "success": True,
                "max_tokens": max_tokens,
                "message": "连接成功"
            }
        )
        
    except ValueError as e:
        # API Key未配置等错误
        logger.error(f"测试连接失败（配置错误）: model_id={model_id}, error={e}")
        return ResponseModel(
            success=True,
            code=200,
            message="连接测试完成",
            data={
                "success": False,
                "max_tokens": None,
                "message": f"配置错误: {str(e)}"
            }
        )
    except Exception as e:
        # 网络错误、认证失败等
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "api key" in error_msg.lower() or "unauthorized" in error_msg.lower():
            error_msg = "API Key认证失败，请检查API Key是否正确"
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            error_msg = "网络连接失败，请检查网络或API地址"
        elif "rate limit" in error_msg.lower() or "too many" in error_msg.lower():
            error_msg = "请求频率过高，请稍后重试"
        
        logger.error(f"测试连接失败: model_id={model_id}, provider={provider_name}, error={e}")
        return ResponseModel(
            success=True,
            code=200,
            message="连接测试完成",
            data={
                "success": False,
                "max_tokens": None,
                "message": f"连接失败: {error_msg}"
            }
        )



