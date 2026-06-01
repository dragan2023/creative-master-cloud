"""
多Agent协作文学作品生成系统 - Agent模型配置管理

模块: agents.writing
文件: agent_config.py
功能: 管理各Agent的模型配置，包括模型选择、参数设置和持久化

依赖关系:
    - 依赖: app.core.config, app.agents.writing.base_agent
    - 被依赖: BaseWritingAgent, 具体的Agent实现

使用说明:
    # 获取默认配置
    config = AgentConfig()
    model_config = config.get_config(AgentRole.WRITER)
    
    # 更新配置
    config.update_config(AgentRole.WRITER, AgentModelConfig(
        model_id="gpt-5.2-pro",
        provider="t8star",
        temperature=0.8,
        max_tokens=8192
    ))
    
    # 持久化
    config_dict = config.to_dict()
    config = AgentConfig.from_dict(config_dict)

创建时间: 2026-03-27
最后修改: 2026-03-27

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum

from app.core.config import PRESET_MODELS
from app.agents.writing.base_agent import AgentRole


class AgentModelConfig(BaseModel):
    """单个Agent的模型配置
    
    使用Pydantic v2定义，支持序列化和验证。
    支持完全自定义API配置，用户可自由输入任意provider、model_id、api_base、api_key。
    """
    model_id: str = Field(..., description="模型ID，如 gpt-5.2-pro")
    provider: str = Field(..., description="供应商名称，如 t8star")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数，控制创意度")
    max_tokens: int = Field(default=32000, ge=256, le=128000, description="最大输出token数（v2.4: 4096→32000以支持10000+中文字输出）")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Top-p采样参数")
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="频率惩罚")
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0, description="存在惩罚")
    # 自定义API配置字段 - 支持完全开放的模型配置
    api_base: Optional[str] = Field(default=None, description="自定义API端点地址")
    api_key: Optional[str] = Field(default=None, description="API密钥（运行时使用，不持久化）")
    # 配置ID引用 - 用于续传时从数据库重新加载API Key
    config_id: Optional[int] = Field(default=None, description="数据库中的模型配置ID，用于续传时重新加载API Key")
    
    model_config = {"from_attributes": True}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return self.model_dump(exclude_none=True)


# 默认配置映射 - 开放自由配置，预设为空
DEFAULT_AGENT_CONFIGS: Dict[AgentRole, AgentModelConfig] = {}


class AgentConfig(BaseModel):
    """全局Agent配置管理
    
    管理所有Agent的模型配置，支持：
    - 获取/更新单个Agent配置
    - 序列化/反序列化
    - 获取可用模型列表
    """
    
    # 各角色的模型配置
    configs: Dict[str, AgentModelConfig] = Field(
        default_factory=dict,
        description="各角色的模型配置映射"
    )
    
    # 全局设置
    enable_stats: bool = Field(default=True, description="是否启用统计记录")
    enable_retry: bool = Field(default=True, description="是否启用失败重试")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    retry_delay: float = Field(default=2.0, ge=0.0, le=60.0, description="重试延迟（秒）")
    
    model_config = {"from_attributes": True}
    
    def get_config(self, role: AgentRole) -> Optional[AgentModelConfig]:
        """获取指定角色的模型配置
        
        Args:
            role: Agent角色
            
        Returns:
            AgentModelConfig或None（如果角色不存在）
        """
        return self.configs.get(role.value)
    
    def update_config(self, role: AgentRole, config: AgentModelConfig) -> None:
        """更新指定角色的模型配置
        
        Args:
            role: Agent角色
            config: 新的配置
        """
        self.configs[role.value] = config
    
    def reset_config(self, role: AgentRole) -> None:
        """重置指定角色配置（删除该角色的配置）
        
        Args:
            role: Agent角色
        """
        self.configs.pop(role.value, None)
    
    def reset_all(self) -> None:
        """重置所有配置为空"""
        self.configs = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于持久化"""
        return {
            "configs": {
                role: config.model_dump(exclude_none=True)
                for role, config in self.configs.items()
            },
            "enable_stats": self.enable_stats,
            "enable_retry": self.enable_retry,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        """从字典创建配置实例
        
        Args:
            data: 字典数据
            
        Returns:
            AgentConfig实例
        """
        configs = {}
        for role_str, config_data in data.get("configs", {}).items():
            configs[role_str] = AgentModelConfig(**config_data)
        
        return cls(
            configs=configs,
            enable_stats=data.get("enable_stats", True),
            enable_retry=data.get("enable_retry", True),
            max_retries=data.get("max_retries", 3),
            retry_delay=data.get("retry_delay", 2.0)
        )
    
    @staticmethod
    def get_available_models() -> Dict[str, List[Dict[str, Any]]]:
        """获取可用模型列表
        
        从PRESET_MODELS读取可用模型，按provider分组。
        
        Returns:
            Dict[provider_name, List[model_info]]
        """
        result = {}
        for provider_name, provider_config in PRESET_MODELS.items():
            # 只返回文本模型
            models = [
                model for model in provider_config.get("models", [])
                if model.get("type") == "text"
            ]
            if models:
                result[provider_name] = {
                    "name": provider_config.get("name", provider_name),
                    "models": models,
                    "api_base": provider_config.get("api_base", ""),
                    "doc_url": provider_config.get("doc_url", ""),
                    "notice": provider_config.get("notice", "")
                }
        return result
    
    @staticmethod
    def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
        """获取指定模型的详细信息
        
        Args:
            model_id: 模型ID
            
        Returns:
            模型信息字典或None
        """
        for provider_name, provider_config in PRESET_MODELS.items():
            for model in provider_config.get("models", []):
                if model.get("id") == model_id:
                    return {
                        **model,
                        "provider": provider_name,
                        "provider_name": provider_config.get("name", provider_name),
                        "api_base": provider_config.get("api_base", "")
                    }
        return None
    
    @staticmethod
    def get_recommended_models() -> Dict[AgentRole, List[str]]:
        """获取每个角色推荐的模型列表
            
        已废弃：用户应自行配置模型，不再提供推荐模型。
    
        Returns:
            空字典
        """
        return {}


# 全局默认配置实例
_default_config: Optional[AgentConfig] = None


def get_default_agent_config() -> AgentConfig:
    """获取全局默认Agent配置实例"""
    global _default_config
    if _default_config is None:
        _default_config = AgentConfig()
    return _default_config


def reset_default_agent_config() -> None:
    """重置全局默认配置"""
    global _default_config
    _default_config = AgentConfig()
