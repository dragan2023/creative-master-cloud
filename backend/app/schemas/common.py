"""
通用响应 Schema
"""
from typing import Optional, Generic, TypeVar, List, Annotated
from datetime import datetime
from pydantic import BaseModel, Field, PlainSerializer


def _serialize_iso_datetime(v: datetime | None) -> str | None:
    """将 datetime 序列化为 ISO 8601 字符串，None 保持为 None"""
    if v is None:
        return None
    return v.isoformat()


# 替代 json_encoders 的 Pydantic V2 惯用写法
# 使用方式：将 `created_at: datetime` 改为 `created_at: IsoDatetime`
IsoDatetime = Annotated[
    datetime,
    PlainSerializer(_serialize_iso_datetime, when_used='json')
]

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """通用响应模型"""
    success: bool = Field(default=True, description="是否成功")
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="消息")
    data: Optional[T] = Field(default=None, description="数据")


class PaginationModel(BaseModel, Generic[T]):
    """分页响应模型"""
    items: List[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页")
    page_size: int = Field(default=20, description="每页大小")
    pages: int = Field(default=0, description="总页数")


class SimpleErrorResponse(BaseModel):
    """简单错误响应（用于API端点内联返回），与 core.error_responses.ErrorResponse 区分"""
    code: int
    message: str
    detail: Optional[str] = None
