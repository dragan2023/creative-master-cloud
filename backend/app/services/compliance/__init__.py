"""
合规审核服务包
提供正文内容的合规性标记功能（非阻塞、非修正）
"""
from app.services.compliance.auditor import ComplianceAuditor

__all__ = ["ComplianceAuditor"]
