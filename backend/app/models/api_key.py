"""
用户 API Key 模型
用于存储用户自定义的 LLM API Key
支持预设Provider和自定义Provider
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Text, JSON
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class UserAPIKey(BaseModel):
    """用户 API Key 表"""
    __tablename__ = "user_api_keys"

    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    provider = Column(String(50), nullable=False,
                      comment="提供商 (deepseek/openai/google/qianwen/doubao/custom)")
    model_name = Column(String(100), nullable=False, comment="模型名称")
    encrypted_key = Column(Text, nullable=False, comment="加密后的 API Key")
    api_base = Column(String(255), nullable=True, comment="自定义 API 地址")
    is_default = Column(Boolean, default=False,
                        nullable=False, comment="是否默认模型")
    is_valid = Column(Boolean, default=True, nullable=False, comment="是否有效")
    last_used_at = Column(String(30), nullable=True, comment="最后使用时间")
    # 自定义Provider支持
    is_custom = Column(Boolean, default=False,
                       nullable=False, comment="是否自定义Provider")
    provider_config = Column(JSON, nullable=True, comment="自定义Provider配置")
    # provider_config 结构示例:
    # {
    #   "display_name": "智谱AI",
    #   "api_format": "openai",  # openai/anthropic/custom
    #   "supports_vision": true,
    #   "models": [{"id": "glm-4", "name": "GLM-4", "context": "128K"}]
    # }

    # 关联关系
    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<UserAPIKey(id={self.id}, provider='{self.provider}', model='{self.model_name}')>"
