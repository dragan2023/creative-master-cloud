"""
统一错误响应模块

定义标准化的错误响应格式。

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any


class ErrorResponse(BaseModel):
    """统一错误响应格式"""
    success: bool = False
    code: str
    message: str
    trace_id: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str
