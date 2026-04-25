"""
小说/剧本生成模块 - 大纲管理 API 端点

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
# 导入公共模型
from ._models import (
    UnitSummariesQualityControlRequest,
    UnitSummariesQualityControlResponse,
    UnitSummariesUploadRequest,
    UnitSummariesUploadResponse,
    OutlineInterventionRequest,
)

# 导入辅助函数
from ._upload import (
    extract_chapter_count,
    extract_outline_units,
    parse_unit_summaries_from_content,
)

# 导入路由注册模块
from . import _upload
from . import _crud_generate

__all__ = [
    "UnitSummariesQualityControlRequest",
    "UnitSummariesQualityControlResponse",
    "UnitSummariesUploadRequest",
    "UnitSummariesUploadResponse",
    "OutlineInterventionRequest",
    "extract_chapter_count",
    "extract_outline_units",
    "parse_unit_summaries_from_content",
]
