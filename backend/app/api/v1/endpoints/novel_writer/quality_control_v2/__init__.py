"""
质量管控 v2.0 API 端点

提供:
1. 应用自动修正方案
2. 用户反馈记录
3. SSE实时推送质控进度 (v1.1新增)

@date: 2026-04-14
@version: v2.1.0
"""
# 导入公共定义（模型、辅助函数、SSE订阅器）
from ._common import (
    ApplyFixRequest,
    GenerateFixRequest,
    ReAnalyzeRequest,
    CancelQCRequest,
    FeedbackRequest,
    ImportedOutlineAutoReviseRequest,
    UnitQualityControlRequest,
    GlobalOutlineQCRequest,
    GlobalOutlineReviseRequest,
    QCProgressSubscriber,
    get_qc_subscriber,
    publish_qc_progress,
    _generate_fixes_for_issues,
    _qc_subscriber,
)

# 导入路由注册模块（导入即注册路由到共享router）
from . import _basic
from . import _global
from . import _unit

__all__ = [
    # 请求模型
    "ApplyFixRequest",
    "GenerateFixRequest",
    "ReAnalyzeRequest",
    "CancelQCRequest",
    "FeedbackRequest",
    "ImportedOutlineAutoReviseRequest",
    "UnitQualityControlRequest",
    "GlobalOutlineQCRequest",
    "GlobalOutlineReviseRequest",
    # SSE
    "QCProgressSubscriber",
    "get_qc_subscriber",
    "publish_qc_progress",
    # 辅助函数
    "_generate_fixes_for_issues",
]
