"""
全局大纲质控 - 宏观结构分析器 (GlobalStructureAnalyzer)

检测全局大纲的整体结构、章节分布、故事弧线

@date: 2026-04-24
@version: v1.1.0
"""
from typing import Dict, List, Any

from app.core.logger import get_logger
from ._common import call_llm_with_retry, parse_llm_json_response

logger = get_logger("quality_control.analyzers.global_quality")


class GlobalStructureAnalyzer:
    """宏观结构分析器 - 检测全局大纲的结构质量"""

    async def analyze(
        self,
        global_outline: str,
        project: Any,
        rule_results: Dict = None,
        depth: str = "standard",
        db=None,
        user_id: int = 0,
        character_profiles: List[Dict] = None,
        worldview_settings: Dict = None,
        **kwargs
    ) -> Dict:
        """执行宏观结构分析(v1.0防错版)"""
        issues = []

        # 1. 大纲长度检测(10000-20000字)
        length_issues = self._analyze_outline_length(global_outline)
        issues.extend(length_issues)

        # 2. 章节分布检测
        distribution_issues = self._analyze_chapter_distribution(
            global_outline)
        issues.extend(distribution_issues)

        # 3. 故事弧线检测(LLM深度分析)
        if depth in ["standard", "deep"]:
            arc_issues = await self._analyze_story_arc_with_llm(
                global_outline, depth, db, user_id
            )
            if isinstance(arc_issues, list):
                issues.extend(arc_issues)

        # 4. 应用用户反馈学习的阈值调整
        issues = self._apply_feedback_thresholds(user_id, issues)

        # 计算得分
        score = self._calculate_structure_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "outline_length": len(global_outline),
                "chapter_count": self._count_chapters(global_outline),
                "analysis_depth": depth
            }
        }

    def _analyze_outline_length(self, global_outline: str) -> List[Dict]:
        """分析大纲长度是否合理(建议30000字以内，确保LLM能够完整输出)"""
        issues = []
        length = len(global_outline)

        if length < 5000:
            issues.append({
                "id": "GS-LENGTH-SHORT",
                "dimension": "global_structure",
                "category": "大纲过短",
                "severity": "warning",
                "location": {},
                "description": f"全局大纲仅{length}字,建议5000-30000字",
                "evidence": f"当前长度: {length}字",
                "suggestion": "建议补充世界观设定、人物背景、主线剧情等核心要素",
                "metadata": {"length": length, "recommended_min": 5000}
            })
        elif length > 30000:
            issues.append({
                "id": "GS-LENGTH-LONG",
                "dimension": "global_structure",
                "category": "大纲过长",
                "severity": "info",
                "location": {},
                "description": f"全局大纲{length}字,超出建议范围(5000-30000字)",
                "evidence": f"当前长度: {length}字",
                "suggestion": "建议精简冗余描述,保留核心设定和主线剧情",
                "metadata": {"length": length, "recommended_max": 30000}
            })

        return issues

    def _analyze_chapter_distribution(self, global_outline: str) -> List[Dict]:
        """分析章节分布是否合理"""
        issues = []
        import re

        # 提取章节号
        chapter_pattern = r'第([一二三四五六七八九十百千万\d]+)[章节集场]'
        chapters = re.findall(chapter_pattern, global_outline)

        if len(chapters) < 10:
            issues.append({
                "id": "GS-CHAPTER-FEW",
                "dimension": "global_structure",
                "category": "章节过少",
                "severity": "info",
                "location": {},
                "description": f"全局大纲仅包含{len(chapters)}个章节,可能结构不够完整",
                "evidence": f"检测到章节数: {len(chapters)}",
                "suggestion": "建议规划更多章节以完整展开故事",
                "metadata": {"chapter_count": len(chapters)}
            })

        return issues

    async def _analyze_story_arc_with_llm(
        self,
        global_outline: str,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM进行深度故事弧线分析(防错版: 超时1200秒)"""
        issues = []

        try:
            logger.info("[宏观结构分析] 开始LLM故事弧线分析...")
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            # 使用用户的默认LLM配置(从数据库获取)
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[宏观结构分析] 无法获取LLM提供者,跳过故事弧线分析")
                return issues

            logger.info("[宏观结构分析] 成功获取LLM提供者，开始调用...")

            # 截取大纲前15000字用于LLM分析(避免超长)
            outline_sample = global_outline  # 不再截断大纲，完整上下文有助于LLM准确分析

            prompt = f"""你是专业的小说结构分析师。

    请分析以下全局大纲的故事弧线质量:

    【全局大纲内容】(前15000字)
    {outline_sample}

    【分析要求】
    1. 评估故事弧线是否完整(起承转合/三幕结构)
    2. 检测章节分布是否合理(是否有明显的节奏起伏)
    3. 评估高潮分布是否合理(是否过于集中或分散)
    4. 检测核心要素是否完整(主角/目标/冲突/转折/结局)

    【输出格式】
    ```json
    {{
      "issues": [
        {{
          "type": "结构缺陷类型",
          "severity": "warning|critical|info",
          "description": "详细描述问题",
          "location": "问题所在位置(章节号或段落)"
        }}
      ]
    }}
    ```

    如果没有问题,返回空数组。
    """

            # ✅ 使用带重试机制的LLM调用
            logger.info("[宏观结构分析] 正在调用LLM（超时1200秒）...")
            response = await call_llm_with_retry(
                llm_provider,
                prompt=prompt,
                temperature=0.3,
                timeout=1200,
                context="宏观结构分析"
            )
            logger.info("[宏观结构分析] LLM调用完成，开始解析响应...")

            # ✅ 防错点2: 安全访问response属性
            response_text = response.content if hasattr(
                response, 'content') else str(response)

            # ✅ 防错点3: JSON解析带三级修复机制
            result = parse_llm_json_response(response_text, logger, "宏观结构分析")

            # 处理解析结果
            for issue in result.get("issues", []):
                issues.append({
                    "id": f"GS-ARC-{len(issues)+1}",
                    "dimension": "global_structure",
                    "category": issue.get("type", "结构问题"),
                    "severity": issue.get("severity", "warning"),
                    "location": {
                        "description": issue.get("location", "")
                    },
                    "description": issue.get("description", ""),
                    "evidence": f"故事弧线分析",
                    "suggestion": "建议调整故事结构,确保起承转合完整",
                    "metadata": {
                        "analysis_method": "llm",
                        "issue_type": issue.get("type")
                    }
                })

        except Exception as e:
            logger.warning(f"[宏观结构分析] LLM故事弧线分析异常: {str(e)}")
            # 降级处理: 返回空问题列表,不阻塞流程

        return issues

    def _calculate_structure_score(self, issues: List[Dict]) -> float:
        """计算结构得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 15
            elif severity == "warning":
                score -= 8
            elif severity == "info":
                score -= 2

        return max(0, min(100, score))

    def _count_chapters(self, global_outline: str) -> int:
        """统计章节数量"""
        import re
        chapter_pattern = r'第([一二三四五六七八九十百千万\d]+)[章节集场]'
        return len(re.findall(chapter_pattern, global_outline))

    def _apply_feedback_thresholds(self, user_id: int, issues: List[Dict]) -> List[Dict]:
        """
        v1.0新增: 应用用户反馈学习的阈值调整

        根据用户历史反馈,过滤或调整问题的严重程度
        """
        try:
            from ..feedback_learning import get_feedback_manager
            feedback_manager = get_feedback_manager()

            filtered_issues = []
            for issue in issues:
                dimension = issue.get("dimension", "")
                category = issue.get("category", "")

                # 获取该维度和分类的误报率
                fp_rate = feedback_manager.get_false_positive_rate(
                    user_id, dimension, category
                )

                # 如果误报率超过50%,降低问题严重程度或过滤
                if fp_rate > 0.5:
                    severity = issue.get("severity", "info")
                    if severity == "warning":
                        issue["severity"] = "info"
                        issue["metadata"]["adjusted_by_feedback"] = True
                    elif severity == "critical":
                        issue["severity"] = "warning"
                        issue["metadata"]["adjusted_by_feedback"] = True

                    # 如果误报率超过80%,直接过滤
                    if fp_rate > 0.8:
                        continue

                filtered_issues.append(issue)

            return filtered_issues

        except Exception as e:
            logger.warning(f"[宏观结构分析] 应用反馈阈值失败: {str(e)}")
            return issues
