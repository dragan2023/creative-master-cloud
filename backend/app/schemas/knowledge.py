"""
知识库相关 Schema
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class KnowledgeBaseType(str, Enum):
    """知识库类型"""
    TEMP = "temp"
    STATIC = "static"
    API = "api"


class KnowledgeBaseStatus(str, Enum):
    """知识库状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class KnowledgeBaseCategory(str, Enum):
    """知识库业务板块分类"""
    SHORT_VIDEO = "short-video"
    SCRIPT = "script"
    NOVEL = "novel"
    PRINT_AD = "print-ad"
    TVC = "tvc"
    GENERAL = "general"
    USER_SPECIFIC = "user-specific"
    MANUAL = "manual"


class KnowledgeBaseCreate(BaseModel):
    """创建知识库"""
    name: str = Field(..., min_length=2, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, description="描述")


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""
    id: int
    name: str
    description: Optional[str] = None
    type: KnowledgeBaseType
    category: Optional[KnowledgeBaseCategory] = None
    status: KnowledgeBaseStatus
    file_type: Optional[str] = None
    file_size: int = 0
    document_count: int = 0
    preprocessor_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,  # 枚举类型序列化为字符串值
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
    }


class KnowledgeBaseUploadResponse(BaseModel):
    """知识库上传响应"""
    id: int
    name: str
    status: KnowledgeBaseStatus
    message: str
    document_count: int = 0


# ==================== 管理员知识库管理 ====================

class StaticKnowledgeBaseCreate(BaseModel):
    """创建静态知识库"""
    name: str = Field(..., min_length=2, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, description="描述")
    category: str = Field(..., description="业务板块分类")


class StaticKnowledgeBaseResponse(BaseModel):
    """静态知识库响应"""
    id: int
    name: str
    type: KnowledgeBaseType = KnowledgeBaseType.STATIC
    description: Optional[str] = None
    category: KnowledgeBaseCategory
    status: KnowledgeBaseStatus
    file_type: Optional[str] = None
    file_size: int = 0
    document_count: int = 0
    preprocessor_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,  # 枚举类型序列化为字符串值
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
    }


class StaticKnowledgeBaseListResponse(BaseModel):
    """静态知识库列表响应"""
    items: List[StaticKnowledgeBaseResponse]
    total: int


class APIKnowledgeBaseCreate(BaseModel):
    """创建API数据源知识库"""
    name: str = Field(..., min_length=2, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, description="描述")
    category: KnowledgeBaseCategory = Field(..., description="业务板块分类")
    api_config: Dict[str, Any] = Field(..., description="API配置信息")


class APIConfigAutoGenerate(BaseModel):
    """AI自动生成API配置请求"""
    api_doc: str = Field(..., description="API接口文档内容或URL")
    category: KnowledgeBaseCategory = Field(..., description="业务板块分类")
    name: Optional[str] = Field(None, description="知识库名称（可选）")


class APIKnowledgeBaseResponse(BaseModel):
    """API知识库响应"""
    id: int
    name: str
    description: Optional[str] = None
    category: KnowledgeBaseCategory
    status: KnowledgeBaseStatus
    api_config: Optional[Dict[str, Any]] = None
    document_count: int = 0
    created_at: datetime
    last_sync: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,  # 枚举类型序列化为字符串值
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
    }


class KnowledgeBaseSyncRequest(BaseModel):
    """知识库同步请求"""
    force: bool = Field(False, description="是否强制同步")


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库"""
    name: Optional[str] = Field(
        None, min_length=2, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, description="描述")
    category: Optional[KnowledgeBaseCategory] = Field(
        None, description="业务板块分类")


# ==================== GraphRAG 双轨知识库 ====================

class TheoryConnection(BaseModel):
    """理论连接 - 垂直实体与通用理论的关系"""
    vertical_entity: str = Field(..., description="垂直领域实体")
    general_theory: str = Field(..., description="通用理论实体")
    relation: str = Field(..., description="关系类型 (体现了/应用了/符合/违背了)")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    explanation: Optional[str] = Field(None, description="匹配解释")


class GraphRAGEntity(BaseModel):
    """GraphRAG 实体"""
    text: str = Field(..., description="实体文本")
    type: str = Field(..., description="实体类型")
    theory_tags: Optional[List[str]] = Field(None, description="理论标签（通用知识库）")
    theory_connections: Optional[List[Dict[str, Any]]] = Field(
        None, description="理论连接（垂直知识库）")


class GraphRAGRelation(BaseModel):
    """GraphRAG 关系"""
    source: str = Field(..., description="源实体")
    target: str = Field(..., description="目标实体")
    relation: str = Field(..., description="关系类型")
    weight: Optional[float] = Field(None, ge=0, le=1, description="关系权重")
    context: Optional[str] = Field(None, description="关系上下文")


class GraphRAGExtractionResult(BaseModel):
    """GraphRAG 实体关系提取结果"""
    entities: List[GraphRAGEntity]
    relations: List[GraphRAGRelation]


class DualTrackRetrieveRequest(BaseModel):
    """双轨知识库检索请求"""
    query: str = Field(..., description="查询文本")
    general_kb_id: Optional[int] = Field(
        None, description="通用知识库ID（固定调用）")
    vertical_kb_id: Optional[int] = Field(
        None, description="垂直领域知识库ID")
    vertical_category: Optional[KnowledgeBaseCategory] = Field(
        None, description="垂直领域类别")
    n_results: int = Field(5, ge=1, le=20, description="返回结果数量")


class DualTrackRetrieveResponse(BaseModel):
    """三层知识库检索响应"""
    query: str
    general_results: Optional[Dict[str, Any]] = Field(
        None, description="通用知识库检索结果（创意理论）")
    vertical_results: Optional[Dict[str, Any]] = Field(
        None, description="垂直领域检索结果（应用案例）")
    manual_results: Optional[Dict[str, Any]] = Field(
        None, description="官方手册检索结果（不使用GraphRAG）")
    connections: List[TheoryConnection] = Field(
        default_factory=list, description="理论连接列表")
    enhanced_context: str = Field("", description="增强后的上下文")


class KnowledgeGraphData(BaseModel):
    """知识图谱数据（用于可视化）"""
    nodes: List[Dict[str, Any]] = Field(
        default_factory=list, description="节点列表")
    edges: List[Dict[str, Any]] = Field(
        default_factory=list, description="边列表")
    stats: Dict[str, Any] = Field(default_factory=dict, description="统计信息")
