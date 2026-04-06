"""
提示词模板模型
用于管理各模块的提示词
"""
from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class PromptTemplate(BaseModel):
    """提示词模板表"""
    __tablename__ = "prompt_templates"

    module = Column(String(50), nullable=False, index=True,
                    comment="模块名称 (short_video/script/novel/print_ad/tvc)")
    name = Column(String(100), nullable=False, comment="模板名称")
    description = Column(Text, nullable=True, comment="模板描述")
    content = Column(Text, nullable=False, comment="提示词内容")
    variables = Column(String(500), nullable=True, comment="变量列表 (JSON格式)")

    # 版本管理
    version = Column(String(20), default="1.0.0",
                     nullable=False, comment="版本号")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否激活")
    parent_id = Column(Integer, ForeignKey(
        "prompt_templates.id"), nullable=True, comment="父版本ID")

    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, module='{self.module}', version='{self.version}')>"

    def to_dict(self, exclude: list = None) -> dict:
        """转换为字典"""
        result = super().to_dict(exclude)
        # 解析变量 JSON
        if self.variables:
            import json
            try:
                result["variables"] = json.loads(self.variables)
            except (json.JSONDecodeError, TypeError) as e:
                # 解析失败时返回空列表
                result["variables"] = []
        else:
            result["variables"] = []
        return result
