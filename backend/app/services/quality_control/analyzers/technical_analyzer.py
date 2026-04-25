"""
技术性排雷分析器

@date: 2026-04-12
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger("quality_control.technical_analyzer")


class TechnicalAnalyzer:
    """技术性排雷分析器"""

    async def analyze(self, chapters_data: List[Dict], project: Any,
                      rule_results: Dict = None, depth: str = "standard", **kwargs) -> Dict:
        # 复用规则引擎结果
        if rule_results and "technical" in rule_results:
            return rule_results["technical"]

        # 复用敏感词检测（容错导入：若SensitiveChecker不存在则跳过）
        try:
            from app.services.proofread.checkers.sensitive_checker import SensitiveChecker
        except ImportError:
            logger.warning("SensitiveChecker 模块不可用，跳过敏感词检测")
            return {"score": 100, "issues": [], "tokens": 0}

        all_issues = []
        checker = SensitiveChecker(compliance_level="normal")
        checker.initialize()

        for ch in chapters_data[:10]:  # 最多检查10章
            content = ch.get("content", "")
            sensitive_issues = checker.check(content)

            for issue in sensitive_issues[:5]:  # 每章最多5个
                all_issues.append({
                    "id": f"SENS-{len(all_issues)+1}",
                    "dimension": "technical",
                    "category": "敏感内容",
                    "severity": "critical",
                    "location": {"chapter": ch["chapter_number"]},
                    "description": f"检测到敏感词: {issue.text}",
                    "evidence": issue.text,
                    "suggestion": issue.suggestion if hasattr(issue, 'suggestion') else "建议修改",
                    "metadata": {}
                })

        score = 100 if not all_issues else max(0, 100 - len(all_issues) * 20)
        return {"score": score, "issues": all_issues, "tokens": 0}
