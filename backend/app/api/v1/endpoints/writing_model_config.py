"""
写作模型配置 - API端点
提供模型配置的CRUD、测试连接、导入导出功能

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import asyncio

from app.core.database import get_db
from app.core.exceptions import ResourceNotFoundException
from app.core.security import api_key_encryption, mask_api_key
from app.core.logger import get_logger
from app.core.config import PRESET_MODELS
from app.api.deps import get_current_user
from app.models import User
from app.models.writing_model_config import WritingModelConfig
from app.schemas.common import ResponseModel

logger = get_logger(__name__)

router = APIRouter(prefix="/writing-model-configs", tags=["写作模型配置"])


# ==================== Schema 定义 ====================

class WritingModelConfigCreate(BaseModel):
    """创建模型配置请求"""
    name: str = Field(..., max_length=100, description="配置名称")
    provider: str = Field(..., max_length=50, description="服务商标识")
    provider_display: Optional[str] = Field(None, max_length=100, description="服务商显示名")
    model_id: str = Field(..., max_length=200, description="模型ID")
    api_key: str = Field(..., description="明文API密钥")
    api_base: Optional[str] = Field(None, max_length=255, description="API端点地址")


class WritingModelConfigUpdate(BaseModel):
    """更新模型配置请求"""
    name: Optional[str] = Field(None, max_length=100)
    provider: Optional[str] = Field(None, max_length=50)
    provider_display: Optional[str] = Field(None, max_length=100)
    model_id: Optional[str] = Field(None, max_length=200)
    api_key: Optional[str] = Field(None, description="如果传入则重新加密")
    api_base: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class WritingModelConfigResponse(BaseModel):
    """模型配置响应"""
    id: int
    name: str
    provider: str
    provider_display: Optional[str] = None
    model_id: str
    api_key_masked: str = Field(..., description="脱敏后的API密钥")
    api_base: Optional[str] = None
    is_valid: bool
    is_active: bool
    last_tested_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WritingModelConfigTestRequest(BaseModel):
    """测试未保存配置请求"""
    provider: str = Field(..., max_length=50)
    model_id: str = Field(..., max_length=200)
    api_key: str = Field(..., description="明文API密钥")
    api_base: Optional[str] = Field(None, max_length=255)


class WritingModelConfigImportItem(BaseModel):
    """导入配置项"""
    name: str = Field(..., max_length=100)
    provider: str = Field(..., max_length=50)
    provider_display: Optional[str] = Field(None, max_length=100)
    model_id: str = Field(..., max_length=200)
    api_key: str = Field(..., description="明文API密钥")
    api_base: Optional[str] = Field(None, max_length=255)


class WritingModelConfigImportRequest(BaseModel):
    """导入配置请求"""
    configs: List[WritingModelConfigImportItem]


class WritingModelConfigExportItem(BaseModel):
    """导出配置项"""
    name: str
    provider: str
    provider_display: Optional[str] = None
    model_id: str
    api_key: str = ""  # 导出时为空字符串
    api_base: Optional[str] = None


class WritingModelConfigExportResponse(BaseModel):
    """导出配置响应"""
    configs: List[WritingModelConfigExportItem]
    export_time: str
    version: str = "1.0"


# ==================== 辅助函数 ====================

def config_to_response(config: WritingModelConfig) -> WritingModelConfigResponse:
    """将模型配置转换为响应对象"""
    try:
        decrypted_key = api_key_encryption.decrypt(config.encrypted_key)
        api_key_masked = mask_api_key(decrypted_key)
    except Exception:
        api_key_masked = "***解密失败***"
    
    return WritingModelConfigResponse(
        id=config.id,
        name=config.name,
        provider=config.provider,
        provider_display=config.provider_display,
        model_id=config.model_id,
        api_key_masked=api_key_masked,
        api_base=config.api_base,
        is_valid=config.is_valid,
        is_active=config.is_active,
        last_tested_at=config.last_tested_at,
        created_at=config.created_at,
        updated_at=config.updated_at
    )


# ==================== API 端点 ====================

@router.get("", response_model=ResponseModel[List[WritingModelConfigResponse]], summary="获取所有模型配置")
async def get_all_configs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户所有模型配置"""
    result = await db.execute(
        select(WritingModelConfig)
        .where(WritingModelConfig.user_id == current_user.id)
        .order_by(WritingModelConfig.created_at.desc())
    )
    configs = result.scalars().all()
    
    data = [config_to_response(config) for config in configs]
    return ResponseModel(data=data, message=f"获取到 {len(data)} 条配置")


@router.post("", response_model=ResponseModel[WritingModelConfigResponse], summary="创建模型配置")
async def create_config(
    request_data: WritingModelConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建模型配置"""
    # 加密API密钥
    encrypted_key = api_key_encryption.encrypt(request_data.api_key)
    
    # 创建配置
    config = WritingModelConfig(
        user_id=current_user.id,
        name=request_data.name,
        provider=request_data.provider,
        provider_display=request_data.provider_display,
        model_id=request_data.model_id,
        encrypted_key=encrypted_key,
        api_base=request_data.api_base,
        is_valid=False,
        is_active=True
    )
    
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    logger.info(f"创建写作模型配置: user_id={current_user.id}, name={config.name}, provider={config.provider}")
    
    return ResponseModel(data=config_to_response(config), message="创建成功")


@router.put("/{config_id}", response_model=ResponseModel[WritingModelConfigResponse], summary="更新模型配置")
async def update_config(
    config_id: int,
    request_data: WritingModelConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新模型配置"""
    # 查询配置
    result = await db.execute(
        select(WritingModelConfig)
        .where(WritingModelConfig.id == config_id, WritingModelConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise ResourceNotFoundException("配置不存在或无权限")
    
    # 更新字段
    update_data = request_data.model_dump(exclude_unset=True)
    
    # 如果传入api_key，重新加密
    if "api_key" in update_data and update_data["api_key"]:
        config.encrypted_key = api_key_encryption.encrypt(update_data.pop("api_key"))
        config.is_valid = False  # 重置验证状态
    
    # 更新其他字段
    for key, value in update_data.items():
        setattr(config, key, value)
    
    await db.commit()
    await db.refresh(config)
    
    logger.info(f"更新写作模型配置: id={config_id}, name={config.name}")
    
    return ResponseModel(data=config_to_response(config), message="更新成功")


@router.delete("/{config_id}", response_model=ResponseModel, summary="删除模型配置")
async def delete_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除模型配置"""
    # 查询配置
    result = await db.execute(
        select(WritingModelConfig)
        .where(WritingModelConfig.id == config_id, WritingModelConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise ResourceNotFoundException("配置不存在或无权限")
    
    await db.delete(config)
    await db.commit()
    
    logger.info(f"删除写作模型配置: id={config_id}, name={config.name}")
    
    return ResponseModel(message="删除成功")


@router.post("/{config_id}/test", response_model=ResponseModel, summary="测试已保存的配置")
async def test_saved_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """测试已保存的模型配置连接"""
    from app.agents.llm_manager import get_llm_manager
    
    # 查询配置
    result = await db.execute(
        select(WritingModelConfig)
        .where(WritingModelConfig.id == config_id, WritingModelConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise ResourceNotFoundException("配置不存在或无权限")
    
    try:
        # 解密API密钥
        api_key = api_key_encryption.decrypt(config.encrypted_key)
        
        # 确定使用的api_base
        api_base = config.api_base
        if not api_base:
            preset = PRESET_MODELS.get(config.provider, {})
            api_base = preset.get("api_base")
        
        # 获取LLM管理器
        llm_manager = get_llm_manager()
        
        # 创建provider
        provider = llm_manager.create_provider(
            provider_name=config.provider,
            api_key=api_key,
            model_name=config.model_id,
            api_base=api_base
        )
        
        # 发送测试消息
        try:
            response = await asyncio.wait_for(
                provider.generate(
                    prompt="Hello, respond with OK",
                    system_prompt=None,
                    temperature=0.7,
                    max_tokens=50
                ),
                timeout=30.0
            )
            
            # 更新验证状态
            config.is_valid = True
            config.last_tested_at = datetime.now()
            await db.commit()
            
            logger.info(f"测试写作模型配置成功: id={config_id}, provider={config.provider}")
            
            return ResponseModel(
                data={
                    "success": True,
                    "message": "连接成功"
                },
                message="连接测试完成"
            )
            
        except asyncio.TimeoutError:
            config.is_valid = False
            config.last_tested_at = datetime.now()
            await db.commit()
            
            return ResponseModel(
                data={
                    "success": False,
                    "max_tokens": None,
                    "message": "连接超时（超过30秒）"
                },
                message="连接测试完成"
            )
            
    except ValueError as e:
        config.is_valid = False
        config.last_tested_at = datetime.now()
        await db.commit()
        
        logger.error(f"测试写作模型配置失败（配置错误）: id={config_id}, error={e}")
        return ResponseModel(
            data={
                "success": False,
                "message": f"配置错误: {str(e)}"
            },
            message="连接测试完成"
        )
        
    except Exception as e:
        config.is_valid = False
        config.last_tested_at = datetime.now()
        await db.commit()
        
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "api key" in error_msg.lower() or "unauthorized" in error_msg.lower():
            error_msg = "API Key认证失败，请检查API Key是否正确"
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            error_msg = "网络连接失败，请检查网络或API地址"
        elif "rate limit" in error_msg.lower() or "too many" in error_msg.lower():
            error_msg = "请求频率过高，请稍后重试"
        
        logger.error(f"测试写作模型配置失败: id={config_id}, error={e}")
        return ResponseModel(
            data={
                "success": False,
                "message": f"连接失败: {error_msg}"
            },
            message="连接测试完成"
        )


@router.post("/test", response_model=ResponseModel, summary="测试未保存的配置")
async def test_unsaved_config(
    request_data: WritingModelConfigTestRequest,
    current_user: User = Depends(get_current_user)
):
    """测试未保存的模型配置连接"""
    from app.agents.llm_manager import get_llm_manager
    
    try:
        # 确定使用的api_base
        api_base = request_data.api_base
        if not api_base:
            preset = PRESET_MODELS.get(request_data.provider, {})
            api_base = preset.get("api_base")
        
        # 获取LLM管理器
        llm_manager = get_llm_manager()
        
        # 创建provider
        provider = llm_manager.create_provider(
            provider_name=request_data.provider,
            api_key=request_data.api_key,
            model_name=request_data.model_id,
            api_base=api_base
        )
        
        # 发送测试消息
        try:
            response = await asyncio.wait_for(
                provider.generate(
                    prompt="Hello, respond with OK",
                    system_prompt=None,
                    temperature=0.7,
                    max_tokens=50
                ),
                timeout=30.0
            )
            
            logger.info(f"测试临时模型配置成功: provider={request_data.provider}, model_id={request_data.model_id}")
            
            return ResponseModel(
                data={
                    "success": True,
                    "message": "连接成功"
                },
                message="连接测试完成"
            )
            
        except asyncio.TimeoutError:
            return ResponseModel(
                data={
                    "success": False,
                    "message": "连接超时（超过30秒）"
                },
                message="连接测试完成"
            )
            
    except ValueError as e:
        logger.error(f"测试临时模型配置失败（配置错误）: provider={request_data.provider}, error={e}")
        return ResponseModel(
            data={
                "success": False,
                "message": f"配置错误: {str(e)}"
            },
            message="连接测试完成"
        )
        
    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "api key" in error_msg.lower() or "unauthorized" in error_msg.lower():
            error_msg = "API Key认证失败，请检查API Key是否正确"
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            error_msg = "网络连接失败，请检查网络或API地址"
        elif "rate limit" in error_msg.lower() or "too many" in error_msg.lower():
            error_msg = "请求频率过高，请稍后重试"
        
        logger.error(f"测试临时模型配置失败: provider={request_data.provider}, error={e}")
        return ResponseModel(
            data={
                "success": False,
                "message": f"连接失败: {error_msg}"
            },
            message="连接测试完成"
        )


@router.get("/export", response_model=ResponseModel[WritingModelConfigExportResponse], summary="导出配置")
async def export_configs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """导出所有模型配置（API Key为空字符串）"""
    result = await db.execute(
        select(WritingModelConfig)
        .where(WritingModelConfig.user_id == current_user.id)
        .order_by(WritingModelConfig.created_at.desc())
    )
    configs = result.scalars().all()
    
    export_items = [
        WritingModelConfigExportItem(
            name=config.name,
            provider=config.provider,
            provider_display=config.provider_display,
            model_id=config.model_id,
            api_key="",  # 导出时API Key为空
            api_base=config.api_base
        )
        for config in configs
    ]
    
    export_data = WritingModelConfigExportResponse(
        configs=export_items,
        export_time=datetime.now().isoformat()
    )
    
    logger.info(f"导出写作模型配置: user_id={current_user.id}, count={len(export_items)}")
    
    return ResponseModel(data=export_data, message=f"导出 {len(export_items)} 条配置")


@router.post("/import", response_model=ResponseModel, summary="导入配置")
async def import_configs(
    request_data: WritingModelConfigImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """导入模型配置"""
    success_count = 0
    failed_count = 0
    errors = []
    
    for item in request_data.configs:
        try:
            # 验证必填字段
            if not item.name or not item.provider or not item.model_id or not item.api_key:
                failed_count += 1
                errors.append(f"配置 '{item.name}' 缺少必填字段")
                continue
            
            # 加密API密钥
            encrypted_key = api_key_encryption.encrypt(item.api_key)
            
            # 创建配置
            config = WritingModelConfig(
                user_id=current_user.id,
                name=item.name,
                provider=item.provider,
                provider_display=item.provider_display,
                model_id=item.model_id,
                encrypted_key=encrypted_key,
                api_base=item.api_base,
                is_valid=False,  # 导入的配置需要用户手动测试
                is_active=True
            )
            
            db.add(config)
            success_count += 1
            
        except Exception as e:
            failed_count += 1
            errors.append(f"配置 '{item.name}' 导入失败: {str(e)}")
    
    await db.commit()
    
    logger.info(f"导入写作模型配置: user_id={current_user.id}, success={success_count}, failed={failed_count}")
    
    return ResponseModel(
        data={
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors
        },
        message=f"导入完成：成功 {success_count} 条，失败 {failed_count} 条"
    )
