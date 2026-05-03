"""Writing Model Config Schema 定义"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List

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
