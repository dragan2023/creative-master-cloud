"""
AI辅助长篇写作质量管控服务模块

基于六维度质量管控体系:
1. 宏观结构层 - 情节节奏、伏笔回收、卷末情绪
2. 人物塑造层 - 角色一致性、台词指纹、配角活跃度
3. 场景与感官层 - 五感平衡、时空跳跃、动作逻辑
4. 文笔与修辞层 - 高频词疲劳、陈词滥调、被动语态
5. 阅读体验层 - 章末悬念、金句密度、段落舒适度
6. 技术性排雷层 - 视角越界、时代穿帮、合规检查

@date: 2026-04-12
@version: v3.1.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.quality_control.service import (
    QualityControlService,
    QualityIssue,
    QualityReport,
)

__all__ = [
    "QualityControlService",
    "QualityIssue",
    "QualityReport",
    "get_quality_control_service",
]


def get_quality_control_service(db: AsyncSession) -> QualityControlService:
    """获取质量管控服务实例"""
    return QualityControlService(db)
