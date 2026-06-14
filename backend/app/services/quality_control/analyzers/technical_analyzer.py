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

        # 敏感实体类型中文标签
        compliance_type_labels = {
            "sensitive_location": "敏感地名",
            "sensitive_person": "名人姓名",
            "sensitive_event": "历史事件",
            "sensitive_word": "敏感词",
        }

        all_issues = []
        checker = SensitiveChecker(compliance_level="normal")
        checker.initialize()

        for ch in chapters_data[:10]:  # 最多检查10章
            content = ch.get("content", "")
            sensitive_issues = checker.check(content)

            for issue in sensitive_issues[:5]:  # 每章最多5个
                issue_type = issue.issue_type if hasattr(issue, 'issue_type') else "sensitive_word"
                type_label = compliance_type_labels.get(issue_type, "敏感内容")
                entity_name = issue.text

                # 构建更有信息量的描述
                if issue_type == "sensitive_location":
                    description = f"检测到中国地名「{entity_name}」，请确认是否需要使用虚构地名替代"
                elif issue_type == "sensitive_person":
                    description = f"检测到知名人物「{entity_name}」，请确认为虚构人物或已获得授权"
                elif issue_type == "sensitive_event":
                    description = f"检测到历史事件「{entity_name}」，请确认内容表述是否恰当"
                else:
                    description = f"检测到敏感内容「{entity_name}」"

                suggestion = issue.suggestion if hasattr(issue, 'suggestion') else f"此为合规提醒（{type_label}），不会自动修正，请根据创作需要自行判断是否修改"

                all_issues.append({
                    "id": f"SENS-{len(all_issues)+1}",
                    "dimension": "technical",
                    "category": f"合规提醒 - {type_label}",
                    "severity": "warning",
                    "is_compliance": True,
                    "location": {"chapter": ch["chapter_number"]},
                    "description": description,
                    "evidence": entity_name,
                    "suggestion": suggestion,
                    "metadata": {
                        "compliance_type": issue_type,
                        "entity_name": entity_name,
                        "entity_category": getattr(issue, 'metadata', {}).get('category', '') if hasattr(issue, 'metadata') else '',
                    }
                })

        # 敏感实体不扣分（仅提醒，不计入质量评分）
        score = 100
        return {"score": score, "issues": all_issues, "tokens": 0, "compliance_only": True}
