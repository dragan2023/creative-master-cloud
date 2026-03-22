"""
合规审核服务
基于SensitiveChecker实现内容合规性标记（非阻塞、非修正）

功能：
- 复用现有SensitiveChecker的检测能力
- 标记内容中的潜在合规问题
- 提供详细的违规位置和修改建议
- 不中断生成流程，仅做标记提醒
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from app.services.proofread.checkers.sensitive_checker import (
    SensitiveChecker,
    SensitiveIssue
)
from app.core.logger import get_logger

logger = get_logger("compliance.auditor")


@dataclass
class ComplianceIssue:
    """合规问题"""
    id: int
    # sensitive_word/sensitive_location/sensitive_person/sensitive_event
    type: str
    severity: str                # high/medium/low
    text: str                    # 违规文本
    paragraph: int               # 所在段落（从1开始）
    start: int                   # 段落内起始位置
    end: int                     # 段落内结束位置
    context: str                 # 上下文
    reason: str                  # 违规原因
    suggestion: str              # 修改建议


@dataclass
class ComplianceResult:
    """合规审核结果"""
    checked: bool
    check_time: str
    level: str
    has_issues: bool
    issue_count: int
    issue_summary: Dict[str, int]
    issues: List[Dict[str, Any]]


class ComplianceAuditor:
    """
    合规审核器

    特点：
    - 非阻塞：不中断生成流程
    - 非修正：不自动修改内容
    - 透明化：清晰展示违规信息
    """

    # 敏感等级阈值映射（与SensitiveChecker保持一致）
    SEVERITY_LEVELS = {
        "strict": ["high", "medium", "low"],
        "normal": ["high", "medium"],
        "loose": ["high"]
    }

    # 问题类型中文映射
    ISSUE_TYPE_LABELS = {
        "sensitive_word": "敏感词",
        "sensitive_location": "敏感地名",
        "sensitive_person": "名人姓名",
        "sensitive_event": "历史事件"
    }

    def __init__(self, level: str = "normal"):
        """
        初始化审核器

        Args:
            level: 审核级别 (strict/normal/loose)
        """
        self.level = level
        self._checker: Optional[SensitiveChecker] = None

    def _get_checker(self) -> SensitiveChecker:
        """获取或创建SensitiveChecker实例"""
        if self._checker is None:
            self._checker = SensitiveChecker(compliance_level=self.level)
            self._checker.initialize()
        return self._checker

    def check(self, content: str) -> List[ComplianceIssue]:
        """
        检查内容合规性

        Args:
            content: 待检查的文本内容

        Returns:
            合规问题列表
        """
        if not content or not content.strip():
            return []

        checker = self._get_checker()
        raw_issues = checker.check(content)

        # 转换为ComplianceIssue格式
        issues = []
        paragraphs = content.split('\n')

        for idx, issue in enumerate(raw_issues, 1):
            # 计算所在段落
            paragraph, para_start = self._find_paragraph(
                content, issue.position_start)

            # 提取上下文
            context = self._extract_context(
                content, issue.position_start, issue.position_end)

            compliance_issue = ComplianceIssue(
                id=idx,
                type=issue.issue_type,
                severity=issue.severity,
                text=issue.text,
                paragraph=paragraph,
                start=issue.position_start - para_start,
                end=issue.position_end - para_start,
                context=context,
                reason=issue.description,
                suggestion=issue.suggestion
            )
            issues.append(compliance_issue)

        return issues

    def check_and_mark(self, content: str, level: str = None) -> ComplianceResult:
        """
        检查内容并生成标记结果

        Args:
            content: 待检查的文本内容
            level: 审核级别（可选，覆盖初始化时的级别）

        Returns:
            ComplianceResult 审核结果
        """
        if level:
            self.level = level
            self._checker = None  # 重置checker以使用新级别

        issues = self.check(content)

        # 统计各级别问题数量
        issue_summary = {
            "high": len([i for i in issues if i.severity == "high"]),
            "medium": len([i for i in issues if i.severity == "medium"]),
            "low": len([i for i in issues if i.severity == "low"])
        }

        return ComplianceResult(
            checked=True,
            check_time=datetime.now().isoformat(),
            level=self.level,
            has_issues=len(issues) > 0,
            issue_count=len(issues),
            issue_summary=issue_summary,
            issues=[asdict(issue) for issue in issues]
        )

    def _find_paragraph(self, content: str, position: int) -> tuple:
        """
        找到指定位置所在的段落

        Args:
            content: 完整内容
            position: 字符位置

        Returns:
            (段落编号, 段落起始位置)
        """
        paragraphs = content.split('\n')
        current_pos = 0
        paragraph_num = 1

        for para in paragraphs:
            para_len = len(para)
            if current_pos + para_len >= position:
                return paragraph_num, current_pos
            current_pos += para_len + 1  # +1 for newline
            paragraph_num += 1

        return paragraph_num, current_pos

    def _extract_context(
        self,
        content: str,
        start: int,
        end: int,
        context_len: int = 50
    ) -> str:
        """
        提取违规内容的上下文

        Args:
            content: 完整内容
            start: 违规起始位置
            end: 违规结束位置
            context_len: 上下文长度

        Returns:
            带上下文的文本片段
        """
        context_start = max(0, start - context_len)
        context_end = min(len(content), end + context_len)

        before = content[context_start:start]
        target = content[start:end]
        after = content[end:context_end]

        # 添加省略号
        prefix = "..." if context_start > 0 else ""
        suffix = "..." if context_end < len(content) else ""

        return f"{prefix}{before}【{target}】{after}{suffix}"


def check_content_compliance(
    content: str,
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    便捷函数：检查内容合规性

    Args:
        content: 待检查内容
        config: 合规配置

    Returns:
        合规标记结果字典
    """
    config = config or {}
    level = config.get("level", "normal")

    auditor = ComplianceAuditor(level=level)
    result = auditor.check_and_mark(content)

    return asdict(result)
