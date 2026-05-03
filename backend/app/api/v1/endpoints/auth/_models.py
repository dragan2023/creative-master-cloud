"""认证模块 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import Optional


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
    marker_enabled: bool = Field(True, description="是否启用Marker转换")
    semantic_chunk_enabled: bool = Field(True, description="是否启用语义切片")
    semantic_chunk_size: int = Field(1024, description="语义切片大小(Token数)")
    semantic_threshold: float = Field(0.7, description="语义相似度阈值")
    summarization_enabled: bool = Field(False, description="是否启用摘要压缩")
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
