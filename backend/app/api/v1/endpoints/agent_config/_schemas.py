"""Agent配置 Schema 定义"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

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