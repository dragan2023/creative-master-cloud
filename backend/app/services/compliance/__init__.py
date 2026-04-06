"""
合规审核服务包
提供正文内容的合规性标记功能（非阻塞、非修正）

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from app.services.compliance.auditor import ComplianceAuditor

__all__ = ["ComplianceAuditor"]
