"""
全局大纲质控 - 故事线完整性分析器 (GlobalStorylineIntegrityAnalyzer)

检测起承转合、高潮分布、结局合理性

@date: 2026-04-24
@version: v1.1.0
"""
from typing import Dict, List, Any

from app.core.logger import get_logger
from ._common import call_llm_with_retry, parse_llm_json_response

logger = get_logger("quality_control.analyzers.global_quality")


class GlobalStorylineIntegrityAnalyzer:
    """故事线完整性分析器(新增) - 检测起承转合、高潮分布、结局合理性"""

    async def analyze(
        self,
        global_outline: str,
        project: Any,
        rule_results: Dict = None,
        depth: str = "standard",
        db=None,
        user_id: int = 0,
        **kwargs
    ) -> Dict:
        """执行故事线完整性分析(v1.0防错版)"""
        issues = []

        # 1. LLM起承转合完整性检测
        if depth in ["standard", "deep"]:
            structure_issues = await self._analyze_narrative_structure_with_llm(
                global_outline, depth, db, user_id
            )
            if isinstance(structure_issues, list):
                issues.extend(structure_issues)

        # 2. LLM高潮分布合理性检测
        if depth in ["standard", "deep"]:
            climax_issues = await self._analyze_climax_distribution_with_llm(
                global_outline, depth, db, user_id
            )
            if isinstance(climax_issues, list):
                issues.extend(climax_issues)

        # 3. 应用用户反馈学习的阈值调整
        issues = self._apply_feedback_thresholds(user_id, issues)

        # 计算得分
        score = self._calculate_integrity_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "outline_length": len(global_outline),
                "analysis_depth": depth
            }
        }

    async def _analyze_narrative_structure_with_llm(
        self,
        global_outline: str,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM分析起承转合完整性(防错版: 超时1200秒)"""
        issues = []

        try:
            logger.info("[故事线完整性分析] 开始LLM起承转合分析...")
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[故事线完整性分析] 无法获取LLM提供者,跳过起承转合分析")
                return issues

            logger.info("[故事线完整性分析] 成功获取LLM提供者，开始调用...")

            outline_sample = global_outline[:15000]

            prompt = f"""你是专业的故事结构分析师。

    请分析以下全局大纲的起承转合结构:

    【全局大纲内容】(前15000字)
    {outline_sample}

    【分析要求】
    1. 评估起(开端)是否清晰(是否引入了主要人物和背景)
    2. 评估承(发展)是否充分(是否有足够的情节推进)
    3. 评估转(高潮)是否有力(是否有足够的冲突和张力)
    4. 评估合(结局)是否完整(是否解决了主要冲突并呼应开头)

    【输出格式】
    ```json
    {{
      "issues": [
        {{
          "type": "问题类型(起不清晰/承不充分/转无力/合不完整)",
          "severity": "warning|critical|info",
          "description": "详细描述",
          "stage": "起/承/转/合"
        }}
      ]
    }}
    ```

    如果没有问题,返回空数组。
    """

            response = await call_llm_with_retry(
                llm_provider,
                prompt=prompt,
                temperature=0.3,
                timeout=1200,
                context="剧情线一致性分析"
            )

            response_text = response.content if hasattr(
                response, 'content') else str(response)

            # ✅ 使用统一的JSON解析函数（带三级修复机制）
            result = parse_llm_json_response(response_text, logger, "故事线完整性分析")

            for issue in result.get("issues", []):
                issues.append({
                    "id": f"GI-STRUCT-{len(issues)+1}",
                    "dimension": "global_storyline_integrity",
                    "category": issue.get("type", "结构问题"),
                    "severity": issue.get("severity", "warning"),
                    "location": {},
                    "description": issue.get("description", ""),
                    "evidence": f"阶段: {issue.get('stage', '未知')}",
                    "suggestion": "建议完善故事结构,确保起承转合完整",
                    "metadata": {
                        "analysis_method": "llm",
                        "stage": issue.get("stage")
                    }
                })

        except Exception as e:
            logger.warning(f"[故事线完整性分析] LLM分析异常: {str(e)}")

        return issues

    async def _analyze_climax_distribution_with_llm(
        self,
        global_outline: str,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM分析高潮分布合理性(防错版: 超时1200秒)"""
        issues = []

        try:
            logger.info("[故事线完整性分析] 开始LLM高潮分布分析...")
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[故事线完整性分析] 无法获取LLM提供者,跳过高潮分布分析")
                return issues

            logger.info("[故事线完整性分析] 成功获取LLM提供者，开始调用...")

            outline_sample = global_outline[:15000]

            prompt = f"""你是专业的剧情节奏分析师。

    请分析以下全局大纲的高潮分布:

    【全局大纲内容】(前15000字)
    {outline_sample}

    【分析要求】
    1. 检测高潮是否过于集中(多个高潮挤在一起)
    2. 检测高潮是否过于分散(高潮之间间隔太长)
    3. 评估高潮强度是否递进(最后一个高潮应该是最强的)
    4. 检测是否有足够的铺垫来支撑高潮

    【输出格式】
    ```json
    {{
      "issues": [
        {{
          "type": "问题类型",
          "severity": "warning|critical|info",
          "description": "详细描述"
        }}
      ]
    }}
    ```

    如果没有问题,返回空数组。
    """

            response = await call_llm_with_retry(
                llm_provider,
                prompt=prompt,
                temperature=0.3,
                timeout=1200,
                context="剧情线一致性分析"
            )

            response_text = response.content if hasattr(
                response, 'content') else str(response)

            # ✅ 使用统一的JSON解析函数（带三级修复机制）
            result = parse_llm_json_response(response_text, logger, "高潮分布分析")

            for issue in result.get("issues", []):
                issues.append({
                    "id": f"GI-CLIMAX-{len(issues)+1}",
                    "dimension": "global_storyline_integrity",
                    "category": issue.get("type", "高潮分布问题"),
                    "severity": issue.get("severity", "warning"),
                    "location": {},
                    "description": issue.get("description", ""),
                    "evidence": f"高潮分布分析",
                    "suggestion": "建议调整高潮分布,确保节奏合理",
                    "metadata": {
                        "analysis_method": "llm",
                        "issue_type": issue.get("type")
                    }
                })

        except Exception as e:
            logger.warning(f"[故事线完整性分析] LLM高潮分析异常: {str(e)}")

        return issues

    def _calculate_integrity_score(self, issues: List[Dict]) -> float:
        """计算故事线完整性得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 18
            elif severity == "warning":
                score -= 10
            elif severity == "info":
                score -= 3

        return max(0, min(100, score))

    def _apply_feedback_thresholds(self, user_id: int, issues: List[Dict]) -> List[Dict]:
        """应用用户反馈学习的阈值调整"""
        try:
            from ..feedback_learning import get_feedback_manager
            feedback_manager = get_feedback_manager()

            filtered_issues = []
            for issue in issues:
                dimension = issue.get("dimension", "")
                category = issue.get("category", "")
                fp_rate = feedback_manager.get_false_positive_rate(
                    user_id, dimension, category
                )

                if fp_rate > 0.5:
                    severity = issue.get("severity", "info")
                    if severity == "warning":
                        issue["severity"] = "info"
                        issue["metadata"]["adjusted_by_feedback"] = True
                    elif severity == "critical":
                        issue["severity"] = "warning"
                        issue["metadata"]["adjusted_by_feedback"] = True
                    if fp_rate > 0.8:
                        continue

                filtered_issues.append(issue)

            return filtered_issues

        except Exception as e:
            logger.warning(f"[故事线完整性分析] 应用反馈阈值失败: {str(e)}")
            return issues
