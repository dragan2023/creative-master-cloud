"""
写作模型配置 - 数据模型
用于多Agent写作系统的独立模型配置管理

创建时间: 2026-03-28
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import BaseModel


class WritingModelConfig(BaseModel):
    """写作模型预配置表 - 存储用户的AI模型配置，跨项目复用"""
    __tablename__ = "writing_model_configs"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    name = Column(String(100), nullable=False, comment="配置名称，如'我的GPT-4配置'")
    provider = Column(String(50), nullable=False, comment="服务商标识，如qianwen/doubao/siliconflow/openrouter/t8star/custom")
    provider_display = Column(String(100), nullable=True, comment="服务商显示名，如'通义千问 (阿里云百炼)'")
    model_id = Column(String(200), nullable=False, comment="模型ID，如qwen3.5-plus")
    encrypted_key = Column(Text, nullable=False, comment="加密后的API密钥")
    api_base = Column(String(255), nullable=True, comment="API端点地址")
    is_valid = Column(Boolean, default=False, nullable=False, comment="最近测试是否有效")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    last_tested_at = Column(DateTime, nullable=True, comment="最后测试时间")
    
    # 关联关系
    user = relationship("User", back_populates="writing_model_configs")
    
    def __repr__(self):
        return f"<WritingModelConfig(id={self.id}, name='{self.name}', provider='{self.provider}', model_id='{self.model_id}')>"
