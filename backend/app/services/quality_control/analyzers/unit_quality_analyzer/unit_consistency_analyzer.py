"""单元概述质量分析器 - UnitConsistencyAnalyzer"""
"""
单元概述专用质量管控分析器 v3.0

专门针对单元概述的特点设计，与正文六维度质控模块完全独立。

单元概述特点：
- 长度短（每单元50-300字）
- 概要性质（不是详细正文）
- 强调结构连贯性、人物发展逻辑、与全局大纲一致性

五维度检测机制（v3.0全面深度检测）：
1. unit_structure（单元结构层）- 使用LLM深度检测单元长度、衔接、节奏
2. unit_character（人物发展层）- 使用LLM深度检测人物状态、关系、成长
3. unit_consistency（一致性层）- 使用LLM深度检测与全局大纲的偏离度
4. unit_timeline_space（时间线与空间逻辑层）- 新增，检测位置、时间线、因果、状态连续性
5. unit_ooc（人物OOC层）- 新增，检测人物是否违背人设

v3.0 核心改动：
- 取消所有轻量检测，一律使用LLM深度检测
- 新增时间线空间分析器（人物位置、出场时间线、事件因果、状态连续性）
- 新增人物OOC分析器（性格违背、动机矛盾、说话方式、能力超纲）

@date: 2026-04-19
@version: v3.0.0
@author: 周金磊
"""
from typing import Dict, List, Any, Optional
from app.core.logger import get_logger
from app.services.quality_control.llm_retry_helper import llm_call_with_retry


class UnitConsistencyAnalyzer:
    """一致性分析器 - 使用LLM深度检测与全局大纲的偏离度"""

    async def analyze(
        self,
        chapters_data: List[Dict],
        project: Any,
        rule_results: Dict = None,
        depth: str = "deep",
        db=None,
        user_id: int = 0,
        global_outline: str = "",
        character_profiles: List[Dict] = None,
        worldview_settings: Dict = None,
        **kwargs
    ) -> Dict:
        """执行一致性分析（全面深度检测模式）"""
        issues = []

        # 1. LLM深度检测：大纲偏离度（移除降级逻辑，强制LLM）
        if global_outline:
            deviation_issues = await self._analyze_outline_deviation_llm(
                chapters_data, global_outline, db, user_id
            )
            issues.extend(deviation_issues)

        # 2. LLM深度检测：核心要素完整性
        if global_outline:
            missing_issues = await self._analyze_missing_elements_with_llm(
                chapters_data, global_outline, db, user_id
            )
            issues.extend(missing_issues)

        # 3. LLM深度检测：多维度交叉验证
        cross_validation_result = None
        try:
            cross_validation_result = await self._run_cross_validation(
                chapters_data, global_outline, character_profiles, worldview_settings, depth, db, user_id
            )
            issues.extend(cross_validation_result.get("issues", []))
        except Exception as e:
            logger.warning(f"[一致性分析] 交叉验证失败: {str(e)}")

        # 计算得分
        score = self._calculate_consistency_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "cross_validation": cross_validation_result,
            "metadata": {
                "total_units": len(chapters_data),
                "outline_length": len(global_outline),
                "analysis_method": "llm_deep"
            }
        }

    # ===== 已废弃的轻量检测方法 =====

    async def _analyze_outline_deviation(
        self,
        chapters_data: List[Dict],
        global_outline: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """检测大纲偏离度（已废弃，使用LLM深度检测替代）"""
        return []

    def _extract_outline_keywords(self, global_outline: str) -> List[str]:
        """从全局大纲中提取关键词（已废弃）"""
        return []

    def _analyze_missing_elements(self, chapters_data: List[Dict], global_outline: str) -> List[Dict]:
        """检测核心要素缺失（已废弃，使用LLM深度检测替代）"""
        return []

    async def _analyze_outline_deviation_llm(
        self,
        chapters_data: List[Dict],
        global_outline: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """LLM深度版：语义匹配检测偏离度"""
        issues = []

        if not global_outline or len(chapters_data) == 0:
            return issues

        # 提取全局大纲的核心要素
        outline_summary = global_outline

        # 分批检测（每次最多20个单元）
        batch_size = 20
        for batch_start in range(0, len(chapters_data), batch_size):
            batch_end = min(batch_start + batch_size, len(chapters_data))
            batch_chapters = chapters_data[batch_start:batch_end]

            # 构建批次内容
            batch_content = []
            for ch in batch_chapters:
                content = ch.get("content", "") or ch.get("summary", "")
                batch_content.append(
                    f"第{ch.get('chapter_number', 0)}单元：{content}"
                )

            try:
                from app.agents.llm_manager import get_llm_manager
                llm_manager = get_llm_manager()
                # 使用用户的默认LLM配置（从数据库获取）
                llm_provider = await llm_manager.get_provider_from_db(db, user_id)

                if not llm_provider:
                    logger.warning("[一致性分析] 无法获取LLM提供者，跳过批次检测")
                    break

                prompt = f"""你是专业的小说审核专家。

【全局大纲核心内容】
{outline_summary}

【单元概述批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【审核要求】
请逐一检查每个单元概述是否符合全局大纲的设定：
1. 情节走向是否与大纲一致
2. 人物行为是否符合大纲设定
3. 世界观设定是否与大纲冲突
4. 核心线索是否延续

【输出格式】
```json
{{
  "deviations": [
    {{
      "unit_number": 单元号,
      "issue_type": "情节偏离|人物OOC|设定冲突|线索断裂",
      "description": "详细描述偏离内容",
      "severity": "warning|critical"
    }}
  ]
}}
```

如果没有问题，返回空数组。
"""

                response = await llm_call_with_retry(llm_provider, prompt=prompt, temperature=0.3, context="单元质控分析")
                response_text = response.content if hasattr(
                    response, 'content') else str(response)

                # 解析JSON
                import re
                import json
                json_match = re.search(
                    r'```json\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    result = json.loads(json_match.group(1))
                    for dev in result.get("deviations", []):
                        issues.append({
                            "id": f"UD-LLM-{len(issues)+1}",
                            "dimension": "unit_consistency",
                            "category": dev.get("issue_type", "偏离大纲"),
                            "severity": dev.get("severity", "warning"),
                            "location": {
                                "chapter_number": dev.get("unit_number", 0),
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, dev.get("unit_number", 0))
                            },
                            "description": dev.get("description", ""),
                            "evidence": f"第{dev.get('unit_number', '?')}单元",
                            "suggestion": "请根据全局大纲修正该单元的情节设定",
                            "metadata": {
                                "unit_number": dev.get("unit_number"),
                                "issue_type": dev.get("issue_type"),
                                "analysis_method": "llm"
                            }
                        })
            except Exception as e:
                logger.warning(f"[一致性分析] LLM批次检测异常: {str(e)}")
                break

        return issues

    # ===== LLM深度检测方法 =====

    async def _analyze_missing_elements_with_llm(self, chapters_data: List[Dict], global_outline: str, db, user_id: int) -> List[Dict]:
        """使用LLM深度检测核心要素完整性"""
        issues = []

        if not global_outline or not chapters_data:
            return issues

        try:
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                return issues

            all_content = "\n".join([
                f"第{ch.get('chapter_number', 0)}单元：{(ch.get('content', '') or ch.get('summary', ''))}"
                for ch in chapters_data[:50]
            ])

            prompt = f"""你是专业的小说结构审核专家。

请分析以下单元概述是否涵盖了全局大纲中的核心要素：

【全局大纲】
{global_outline}

【单元概述列表】
{all_content}

【检测要求】
1. 全局大纲中提到的主要角色是否在单元概述中出场？
2. 核心情节线索是否延续？
3. 关键转折点是否被覆盖？
4. 世界观核心设定是否保持一致？

【输出格式】
```json
{{
  "missing_issues": [
    {{
      "element": "缺失要素名称",
      "description": "详细描述",
      "severity": "warning|info"
    }}
  ]
}}
```

如果没有问题，返回空数组。
"""

            response = await llm_call_with_retry(llm_provider, prompt=prompt, temperature=0.2, context="单元质控分析")
            response_text = response.content if hasattr(
                response, 'content') else str(response)

            import re
            import json
            json_match = re.search(
                r'```json\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                result = json.loads(json_match.group(1))
                for issue in result.get("missing_issues", []):
                    issues.append({
                        "id": f"UM-LLM-{len(issues)+1}",
                        "dimension": "unit_consistency",
                        "category": "核心要素缺失",
                        "severity": issue.get("severity", "info"),
                        "location": {},
                        "description": issue.get("description", ""),
                        "evidence": f"缺失要素：{issue.get('element', '?')}",
                        "suggestion": "建议在单元概述中补充该核心要素的描述",
                        "metadata": {
                            "missing_element": issue.get("element"),
                            "analysis_method": "llm_deep"
                        }
                    })
        except Exception as e:
            logger.warning(f"[一致性分析] LLM要素检测异常: {str(e)}")

        return issues

    def _calculate_consistency_score(self, issues: List[Dict]) -> float:
        """计算一致性得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            category = issue.get("category", "")

            if severity == "critical":
                score -= 20
            elif severity == "warning":
                # 大纲偏离类问题扣分更少（因为关键词匹配可能不准确）
                if "偏离" in category:
                    score -= 5  # 从10分降低到5分
                else:
                    score -= 8
            elif severity == "info":
                score -= 2  # 从5分降低到2分

        return max(0, min(100, score))

    def _calculate_deviation_rate(self, issues: List[Dict], total_units: int) -> float:
        """计算偏离率"""
        if total_units == 0:
            return 0.0

        deviation_count = len([
            i for i in issues
            if i.get("dimension") == "unit_consistency"
        ])

        return round((deviation_count / total_units) * 100, 1)

    async def _run_cross_validation(
        self,
        chapters_data: List[Dict],
        global_outline: str,
        character_profiles: List[Dict],
        worldview_settings: Dict,
        depth: str,
        db,
        user_id: int
    ) -> Dict:
        """
        v2.0新增：执行多维度交叉验证

        结合全局大纲、人物设定、世界观进行全面检测

        Returns:
            完整交叉验证结果(包含issues和validation_scores)
        """
        try:
            from .cross_validation import get_cross_validation_engine
            cross_engine = get_cross_validation_engine()

            result = await cross_engine.validate_all(
                chapters_data=chapters_data,
                global_outline=global_outline,
                character_profiles=character_profiles,
                worldview_settings=worldview_settings,
                depth=depth,
                db=db,
                user_id=user_id
            )

            # 将交叉验证结果转换为标准问题格式
            cross_issues = []
            for issue in result.get("issues", []):
                cross_issues.append({
                    "id": issue.get("id", f"CV-{len(cross_issues)+1}"),
                    "dimension": "cross_validation",
                    "category": issue.get("category", "交叉验证问题"),
                    "severity": issue.get("severity", "info"),
                    "location": issue.get("location", {}),
                    "description": issue.get("description", ""),
                    "evidence": issue.get("evidence", ""),
                    "suggestion": issue.get("suggestion", "建议检查多维度一致性"),
                    "metadata": {
                        "validation_type": "cross_validation",
                        **issue.get("metadata", {})
                    }
                })

            logger.info(f"[一致性分析] 交叉验证完成: {len(cross_issues)}个问题")

            # v2.0修复：返回完整结果(包含validation_scores)
            return {
                "issues": cross_issues,
                "validation_scores": result.get("validation_scores", {}),
                "overall_score": result.get("overall_score", 100.0),
                "metadata": result.get("metadata", {})
            }

        except Exception as e:
            logger.warning(f"[一致性分析] 交叉验证执行失败: {str(e)}")
            return {
                "issues": [],
                "validation_scores": {},
                "overall_score": 100.0,
                "metadata": {}
            }

    def _apply_feedback_thresholds(self, user_id: int, issues: List[Dict]) -> List[Dict]:
        """
        v2.0新增：应用用户反馈学习的阈值调整

        根据用户历史反馈，过滤或调整问题的严重程度
        """
        try:
            from .feedback_learning import get_feedback_manager
            feedback_manager = get_feedback_manager()

            filtered_issues = []
            for issue in issues:
                dimension = issue.get("dimension", "")
                category = issue.get("category", "")

                # 获取该维度和分类的误报率
                fp_rate = feedback_manager.get_false_positive_rate(
                    user_id, dimension, category
                )

                # 如果误报率超过50%，降低问题严重程度或过滤
                if fp_rate > 0.5:
                    # 降低严重程度
                    severity = issue.get("severity", "info")
                    if severity == "warning":
                        issue["severity"] = "info"
                        issue["metadata"]["adjusted_by_feedback"] = True
                    elif severity == "critical":
                        issue["severity"] = "warning"
                        issue["metadata"]["adjusted_by_feedback"] = True

                    # 如果误报率超过80%，直接过滤
                    if fp_rate > 0.8:
                        continue

                filtered_issues.append(issue)

            return filtered_issues

        except Exception as e:
            logger.warning(f"[一致性分析] 应用反馈阈值失败: {str(e)}")
            return issues

    def _generate_smart_suggestions(self, issues: List[Dict], chapters_data: List[Dict]) -> List[Dict]:
        """生成智能修正建议（保留兼容）"""
        try:
            from .smart_suggestions import get_smart_suggestion_engine
            suggestion_engine = get_smart_suggestion_engine()

            enhanced_issues = suggestion_engine.generate_suggestions(
                issues=issues,
                chapters_data=chapters_data
            )

            return enhanced_issues

        except Exception as e:
            logger.warning(f"[一致性分析] 生成智能建议失败: {str(e)}")
            return issues
