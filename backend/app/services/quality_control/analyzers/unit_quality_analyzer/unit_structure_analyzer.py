"""单元概述质量分析器 - UnitStructureAnalyzer"""
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


class UnitStructureAnalyzer:
    """单元结构分析器 - 检测单元概述的结构质量"""

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
        """执行单元结构分析（全面深度检测模式）"""
        issues = []

        # 1. LLM深度检测：单元长度与内容充实度
        length_issues = await self._analyze_length_with_llm(chapters_data, db, user_id)
        issues.extend(length_issues)

        # 2. LLM深度检测：单元衔接流畅度
        transition_issues = await self._analyze_transitions_with_llm(chapters_data, db, user_id)
        issues.extend(transition_issues)

        # 3. LLM深度检测：情节节奏分布
        pacing_issues = await self._analyze_pacing_with_llm(chapters_data, db, user_id)
        if isinstance(pacing_issues, list):
            issues.extend(pacing_issues)

        # 计算得分
        score = self._calculate_structure_score(issues, len(chapters_data))

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_units": len(chapters_data),
                "analysis_method": "llm_deep"
            }
        }

    def _analyze_unit_length_distribution(self, chapters_data: List[Dict]) -> List[Dict]:
        """分析单元长度分布，检测异常（已废弃，使用LLM深度检测替代）"""
        # 保留此方法以防旧代码调用，但不再使用
        return []

    def _analyze_unit_transitions(self, chapters_data: List[Dict]) -> List[Dict]:
        """分析单元之间的衔接流畅度（已废弃，使用LLM深度检测替代）"""
        # 保留此方法以防旧代码调用，但不再使用
        return []

    async def _analyze_pacing_enhanced(
        self,
        chapters_data: List[Dict],
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """增强版情节节奏检测（已废弃，使用LLM深度检测替代）"""
        # 保留此方法以防旧代码调用，但不再使用
        return []

    async def _analyze_length_with_llm(self, chapters_data: List[Dict], db, user_id: int) -> List[Dict]:
        """使用LLM深度检测单元长度和内容充实度"""
        issues = []

        if not chapters_data:
            return issues

        # 分批处理（每批15章）
        batch_size = 15
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
                llm_provider = await llm_manager.get_provider_from_db(db, user_id)

                if not llm_provider:
                    logger.warning("[单元结构分析] 无法获取LLM提供者，跳过长度检测")
                    break

                prompt = f"""你是专业的小说结构分析师。

请分析以下单元概述的内容充实度，检测是否存在过短、信息不足的问题：

【单元概述批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【检测要求】
1. 单元长度是否过短（<80字）且信息不足？
2. 是否缺少关键情节要素（冲突、转折、人物行动）？
3. 内容是否过于简略，无法指导正文写作？

【输出格式】
```json
{{
  "length_issues": [
    {{
      "unit_number": 单元号,
      "issue_type": "过短|信息不足|缺少要素",
      "description": "详细描述问题",
      "severity": "warning|critical"
    }}
  ]
}}
```

如果没有问题，返回空数组。
"""

                response = await llm_call_with_retry(llm_provider, prompt=prompt, temperature=0.2, context="单元质控分析")
                response_text = response.content if hasattr(
                    response, 'content') else str(response)

                # 解析JSON
                import re
                import json
                json_match = re.search(
                    r'```json\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    result = json.loads(json_match.group(1))
                    for issue in result.get("length_issues", []):
                        issues.append({
                            "id": f"UL-LLM-{len(issues)+1}",
                            "dimension": "unit_structure",
                            "category": issue.get("issue_type", "内容充实度问题"),
                            "severity": issue.get("severity", "warning"),
                            "location": {
                                "chapter_number": issue.get("unit_number", 0),
                                "unit_id": self._find_unit_id(chapters_data, issue.get("unit_number", 0))
                            },
                            "description": issue.get("description", ""),
                            "evidence": f"第{issue.get('unit_number', '?')}单元",
                            "suggestion": "建议补充关键情节要素：冲突、转折、人物行动",
                            "metadata": {
                                "unit_number": issue.get("unit_number"),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[单元结构分析] LLM长度检测异常: {str(e)}")
                break

        return issues

    async def _analyze_transitions_with_llm(self, chapters_data: List[Dict], db, user_id: int) -> List[Dict]:
        """使用LLM深度检测单元之间的衔接流畅度"""
        issues = []

        if len(chapters_data) < 2:
            return issues

        # 分批处理（每批15章）
        batch_size = 15
        for batch_start in range(0, len(chapters_data) - 1, batch_size):
            batch_end = min(batch_start + batch_size + 1, len(chapters_data))
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
                llm_provider = await llm_manager.get_provider_from_db(db, user_id)

                if not llm_provider:
                    logger.warning("[单元结构分析] 无法获取LLM提供者，跳过衔接检测")
                    break

                prompt = f"""你是专业的小说结构分析师。

请分析以下单元概述之间的衔接流畅度，检测是否存在逻辑跳跃、断裂的问题：

【单元概述批次】（第{batch_start+1}-{batch_end-1}单元）
{chr(10).join(batch_content)}

【检测要求】
1. 相邻单元之间是否存在逻辑跳跃？
2. 情节过渡是否自然流畅？
3. 是否缺少必要的过渡或铺垫？

【输出格式】
```json
{{
  "transition_issues": [
    {{
      "from_unit": 起始单元号,
      "to_unit": 目标单元号,
      "issue_type": "逻辑跳跃|过渡生硬|缺少铺垫",
      "description": "详细描述问题",
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

                # 解析JSON
                import re
                import json
                json_match = re.search(
                    r'```json\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    result = json.loads(json_match.group(1))
                    for issue in result.get("transition_issues", []):
                        issues.append({
                            "id": f"UT-LLM-{len(issues)+1}",
                            "dimension": "unit_structure",
                            "category": issue.get("issue_type", "单元衔接问题"),
                            "severity": issue.get("severity", "info"),
                            "location": {
                                "chapter_number": issue.get("from_unit", 0),
                                "unit_id": self._find_unit_id(chapters_data, issue.get("from_unit", 0))
                            },
                            "description": issue.get("description", ""),
                            "evidence": f"第{issue.get('from_unit', '?')}单元 → 第{issue.get('to_unit', '?')}单元",
                            "suggestion": "建议在单元概述中增加逻辑关联词或过渡句",
                            "metadata": {
                                "from_unit": issue.get("from_unit"),
                                "to_unit": issue.get("to_unit"),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[单元结构分析] LLM衔接检测异常: {str(e)}")
                break

        return issues

    async def _analyze_pacing_with_llm(
        self,
        chapters_data: List[Dict],
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM进行深度节奏分析"""
        issues = []

        # 构建单元摘要
        unit_summaries = []
        for ch in chapters_data[:50]:  # 最多分析前50个单元
            content = ch.get("content", "") or ch.get("summary", "")
            unit_summaries.append({
                "number": ch.get("chapter_number", 0),
                "summary": content
            })

        if not unit_summaries:
            return issues

        try:
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            # 使用用户的默认LLM配置（从数据库获取）
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[单元结构分析] 无法获取LLM提供者，跳过节奏分析")
                return issues

            prompt = f"""你是专业的小说结构分析师。

请分析以下单元概述的情节节奏分布：

【单元概述列表】（共{len(unit_summaries)}个单元）
{chr(10).join([f"第{u['number']}单元：{u['summary']}" for u in unit_summaries])}

【分析要求】
1. 识别节奏低谷区（连续3个以上单元缺乏冲突或推进）
2. 识别高潮分布是否合理（是否过于集中或分散）
3. 检测情节跳跃（前后单元之间缺少必要的过渡）
4. 评估整体节奏曲线是否起伏有致

【输出格式】
```json
{{
  "issues": [
    {{
      "type": "节奏低谷|高潮集中|情节跳跃|节奏单调",
      "start_unit": 起始单元号,
      "end_unit": 结束单元号,
      "description": "详细描述问题",
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

            # 简化解析：提取JSON
            import re
            import json
            json_match = re.search(
                r'```json\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                result = json.loads(json_match.group(1))
                for issue in result.get("issues", []):
                    issues.append({
                        "id": f"UP-LLM-{len(issues)+1}",
                        "dimension": "unit_structure",
                        "category": issue.get("type", "节奏问题"),
                        "severity": issue.get("severity", "warning"),
                        "location": {
                            "chapter_number": issue.get("start_unit", 0),
                            "unit_id": self._find_unit_id(chapters_data, issue.get("start_unit", 0))
                        },
                        "description": issue.get("description", ""),
                        "evidence": f"第{issue.get('start_unit', '?')}-{issue.get('end_unit', '?')}单元",
                        "suggestion": "建议调整情节安排，增加冲突或转折点",
                        "metadata": {
                            "start_unit": issue.get("start_unit"),
                            "end_unit": issue.get("end_unit"),
                            "analysis_method": "llm"
                        }
                    })
        except Exception as e:
            logger.warning(f"[单元结构分析] LLM节奏分析异常: {str(e)}")

        return issues

    def _analyze_pacing_rules(self, chapters_data: List[Dict]) -> List[Dict]:
        """基于规则的情节节奏检测（基础版）"""
        issues = []

        if len(chapters_data) < 5:
            return issues

        # 检测连续平淡单元（通过长度和内容特征判断）
        calm_streak = 0
        calm_start = 0

        for i, chapter in enumerate(chapters_data):
            content = (chapter.get("content", "")
                       or chapter.get("summary", "")).lower()

            # 简单判断：短小 + 无冲突关键词 = 可能平淡
            is_calm = (
                len(content) < 100 and
                not any(word in content for word in [
                        "冲突", "战斗", "危机", "转折", "发现", "决定", "遭遇"])
            )

            if is_calm:
                if calm_streak == 0:
                    calm_start = i
                calm_streak += 1
            else:
                if calm_streak >= 4:  # 连续4个以上平淡单元
                    issues.append({
                        "id": f"UP-{calm_start+1}",
                        "dimension": "unit_structure",
                        "category": "节奏平淡",
                        "severity": "warning",
                        "location": {
                            "chapter_id": chapters_data[calm_start].get("id", calm_start+1),
                            "chapter_number": chapters_data[calm_start].get("chapter_number", calm_start+1),
                            "unit_id": chapters_data[calm_start].get("unit_id", "")
                        },
                        "description": f"第{calm_start+1}-{i}单元连续{calm_streak}个单元情节较为平淡",
                        "evidence": "连续多个单元缺乏明显的冲突或转折",
                        "suggestion": "建议在适当位置增加冲突、悬念或情节转折，保持读者兴趣",
                        "metadata": {"calm_units": calm_streak, "start_unit": calm_start+1}
                    })
                calm_streak = 0

        # 检查最后一段
        if calm_streak >= 4:
            issues.append({
                "id": f"UP-{calm_start+1}",
                "dimension": "unit_structure",
                "category": "节奏平淡",
                "severity": "warning",
                "location": {
                    "chapter_id": chapters_data[calm_start].get("id", calm_start+1),
                    "chapter_number": chapters_data[calm_start].get("chapter_number", calm_start+1),
                    "unit_id": chapters_data[calm_start].get("unit_id", "")
                },
                "description": f"第{calm_start+1}-{len(chapters_data)}单元连续{calm_streak}个单元情节较为平淡",
                "evidence": "连续多个单元缺乏明显的冲突或转折",
                "suggestion": "建议在适当位置增加冲突、悬念或情节转折，保持读者兴趣",
                "metadata": {"calm_units": calm_streak, "start_unit": calm_start+1}
            })

        return issues

    def _calculate_structure_score(self, issues: List[Dict], total_units: int) -> float:
        """计算结构得分"""
        if total_units == 0:
            return 50.0

        score = 100.0

        # 根据问题严重程度扣分（优化后：降低info类问题的扣分）
        for issue in issues:
            severity = issue.get("severity", "info")
            category = issue.get("category", "")

            if severity == "critical":
                score -= 15
            elif severity == "warning":
                score -= 8
            elif severity == "info":
                # info类问题扣分更少，特别是"单元衔接"这类建议性问题
                if category == "单元衔接":
                    score -= 1  # 从3分降低到1分
                else:
                    score -= 2  # 其他info问题从3分降低到2分

        return max(0, min(100, score))

    def _calculate_avg_length(self, chapters_data: List[Dict]) -> float:
        """计算平均单元长度"""
        if not chapters_data:
            return 0.0

        total_length = sum(
            len(chapter.get("content", "") or chapter.get("summary", ""))
            for chapter in chapters_data
        )
        return total_length / len(chapters_data)

    @staticmethod
    def _find_unit_id(chapters_data: List[Dict], chapter_number: int) -> str:
        """根据chapter_number查找对应的unit_id"""
        for ch in chapters_data:
            if ch.get("chapter_number") == chapter_number:
                return ch.get("unit_id", "")
        return ""

    def _generate_pacing_distribution(self, chapters_data: List[Dict]) -> Dict:
        """
        生成节奏分布数据（用于前端可视化）

        Returns:
            {
                "chart_data": [
                    {"unit": 1, "tension": 65, "type": "normal"},
                    {"unit": 2, "tension": 80, "type": "climax"},
                    ...
                ],
                "statistics": {
                    "avg_tension": 60.5,
                    "climax_count": 5,
                    "valley_count": 3
                }
            }
        """
        if not chapters_data:
            return {"chart_data": [], "statistics": {}}

        chart_data = []
        conflict_keywords = ["冲突", "战斗", "危机", "转折",
                             "发现", "决定", "遭遇", "对决", "突破", "觉醒"]
        calm_keywords = ["平静", "日常", "休息", "思考", "回忆", "准备", "等待"]

        for i, chapter in enumerate(chapters_data):
            content = (chapter.get("content", "")
                       or chapter.get("summary", "")).lower()
            length = len(content)

            # 计算张力值（0-100）
            tension = 50  # 基础值

            # 冲突关键词加分
            conflict_count = sum(
                1 for kw in conflict_keywords if kw in content)
            tension += conflict_count * 10

            # 平静关键词减分
            calm_count = sum(1 for kw in calm_keywords if kw in content)
            tension -= calm_count * 8

            # 长度因素（过短可能信息不足）
            if length < 50:
                tension -= 10
            elif length > 200:
                tension += 5

            # 限制范围
            tension = max(0, min(100, tension))

            # 判断类型
            if tension >= 75:
                unit_type = "climax"  # 高潮
            elif tension >= 60:
                unit_type = "rising"  # 上升
            elif tension >= 40:
                unit_type = "normal"  # 正常
            elif tension >= 25:
                unit_type = "falling"  # 下降
            else:
                unit_type = "valley"  # 低谷

            chart_data.append({
                "unit": chapter.get("chapter_number", i+1),
                "tension": round(tension, 1),
                "type": unit_type,
                "length": length
            })

        # 统计数据
        tensions = [d["tension"] for d in chart_data]
        climax_count = sum(1 for d in chart_data if d["type"] == "climax")
        valley_count = sum(1 for d in chart_data if d["type"] == "valley")

        return {
            "chart_data": chart_data,
            "statistics": {
                "avg_tension": round(sum(tensions) / len(tensions), 1) if tensions else 0,
                "max_tension": max(tensions) if tensions else 0,
                "min_tension": min(tensions) if tensions else 0,
                "climax_count": climax_count,
                "valley_count": valley_count,
                "total_units": len(chart_data)
            }
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
            logger.warning(f"[单元结构分析] 应用反馈阈值失败: {str(e)}")
            return issues  # 失败时返回原始问题列表
