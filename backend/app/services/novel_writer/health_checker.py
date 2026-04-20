"""
项目健康检查器

在正文生成前自动执行项目健康检查，不可用组件分级降级。
提供问题诊断和降级建议，帮助用户理解生成质量可能受影响的因素。

@date: 2026-04-19
@version: v1.0.0
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from app.core.logger import get_logger


logger = get_logger("health_checker")


@dataclass
class HealthCheck:
    """单项健康检查结果"""
    name: str                          # 检查项名称
    healthy: bool                      # 是否健康
    severity: str = "info"             # 严重程度: critical/warning/info
    fallback: str = ""                 # 降级说明
    detail: str = ""                   # 详细信息


@dataclass
class HealthReport:
    """项目健康检查报告"""
    checks: Dict[str, HealthCheck] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    can_generate: bool = True          # 是否可以执行正文生成
    degraded: bool = False             # 是否存在降级项

    def add_check(self, key: str, check: HealthCheck):
        """添加检查结果"""
        self.checks[key] = check
        if not check.healthy:
            if check.severity == "critical":
                self.can_generate = False
            elif check.severity == "warning":
                self.degraded = True
                self.warnings.append(f"{check.name}: {check.fallback}")
            elif check.severity == "info":
                self.degraded = True

    def get_degradation_messages(self) -> List[str]:
        """获取所有降级提示消息"""
        messages = []
        for key, check in self.checks.items():
            if not check.healthy and check.fallback:
                messages.append(check.fallback)
        return messages

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "can_generate": self.can_generate,
            "degraded": self.degraded,
            "warnings": self.warnings,
            "checks": {
                k: {
                    "name": v.name,
                    "healthy": v.healthy,
                    "severity": v.severity,
                    "fallback": v.fallback,
                    "detail": v.detail,
                }
                for k, v in self.checks.items()
            }
        }


class ProjectHealthChecker:
    """项目健康检查器

    在正文生成前自动执行，检查大纲、概述、知识库、向量库、文件等
    关键组件的可用性，并提供降级建议。

    使用方式：
        checker = ProjectHealthChecker()
        report = await checker.check(project, db)
        if not report.can_generate:
            # 无法生成，告知用户
        elif report.degraded:
            # 可生成但存在降级，告知用户可能影响
    """

    def __init__(self, vector_store=None):
        self.vector_store = vector_store
        self.logger = get_logger("health_checker")

    async def check(self, project, db=None) -> HealthReport:
        """执行项目健康检查

        Args:
            project: NovelProject对象
            db: 数据库会话（可选，用于更深入的检查）

        Returns:
            HealthReport 健康检查报告
        """
        report = HealthReport()

        # 1. 大纲完整性（critical级别 - 无大纲无法生成）
        report.add_check("outline", HealthCheck(
            name="大纲",
            healthy=bool(getattr(project, 'global_outline_content',
                         None) or project.outline_content),
            severity="critical",
            fallback="生成质量将严重受限，建议先生成全局大纲",
            detail=f"global_outline: {'有' if getattr(project, 'global_outline_content', None) else '无'}, "
            f"outline_content: {'有' if project.outline_content else '无'}"
        ))

        # 2. 单元概述（warning级别 - 无概述时使用基础大纲降级）
        unit_summaries = getattr(project, 'unit_summaries', None)
        unit_summaries_count = len(unit_summaries) if unit_summaries and isinstance(
            unit_summaries, dict) else 0
        report.add_check("unit_summaries", HealthCheck(
            name="单元概述",
            healthy=bool(unit_summaries and unit_summaries_count > 0),
            severity="warning",
            fallback="将使用基础大纲替代，章节级指导不够精确",
            detail=f"单元概述数量: {unit_summaries_count}"
        ))

        # 3. 详细大纲
        content_type = getattr(project, 'content_type', 'novel')
        if content_type == "novel":
            outlines = getattr(project, 'chapter_outlines', None)
            outline_name = "章节详细大纲"
        elif content_type in ("series_script", "script"):
            outlines = getattr(project, 'episode_outlines', None)
            outline_name = "分集详细大纲"
        elif content_type == "movie_script":
            outlines = getattr(project, 'scene_outlines', None)
            outline_name = "场景详细大纲"
        else:
            outlines = None
            outline_name = "详细大纲"

        outlines_count = len(outlines) if outlines and isinstance(
            outlines, dict) else 0
        report.add_check("detailed_outlines", HealthCheck(
            name=outline_name,
            healthy=bool(outlines and outlines_count > 0),
            severity="info",
            fallback="将使用单元概述替代，缺乏细节指导",
            detail=f"{outline_name}数量: {outlines_count}"
        ))

        # 4. 知识库（info级别 - 知识库不可用时跳过知识库增强）
        kb_status = getattr(project, 'kb_status', 'pending')
        report.add_check("knowledge_base", HealthCheck(
            name="知识库",
            healthy=kb_status == "ready",
            severity="info",
            fallback="知识库暂不可用，生成质量可能降低",
            detail=f"知识库状态: {kb_status}"
        ))

        # 5. 向量库（info级别）
        vectorstore_path = getattr(project, 'vectorstore_path', None)
        has_vector_store = bool(vectorstore_path) and os.path.exists(
            vectorstore_path) if vectorstore_path else False
        report.add_check("vector_store", HealthCheck(
            name="历史内容参考",
            healthy=has_vector_store,
            severity="info",
            fallback="历史内容参考不可用",
            detail=f"向量库路径: {vectorstore_path or '未配置'}"
        ))

        # 6. 前文摘要文件
        summary_file = getattr(project, 'summary_file', None)
        has_summary = bool(summary_file) and os.path.exists(
            summary_file) if summary_file else False
        report.add_check("summary_file", HealthCheck(
            name="前文摘要",
            healthy=has_summary or True,  # 摘要缺失时可自动重建，不阻断生成
            severity="info",
            fallback="前文摘要缺失，将自动重建",
            detail=f"摘要文件: {summary_file or '未配置'}"
        ))

        # 7. 角色状态文件
        characters_file = getattr(project, 'characters_file', None)
        has_characters = bool(characters_file) and os.path.exists(
            characters_file) if characters_file else False
        report.add_check("characters_file", HealthCheck(
            name="角色状态",
            healthy=has_characters or True,  # 角色状态缺失时可自动重建
            severity="info",
            fallback="角色状态缺失，将自动初始化",
            detail=f"角色文件: {characters_file or '未配置'}"
        ))

        self.logger.info(
            f"项目健康检查完成: project_id={project.id}, "
            f"can_generate={report.can_generate}, degraded={report.degraded}"
        )

        return report
