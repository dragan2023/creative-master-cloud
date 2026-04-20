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

logger = get_logger("quality_control.analyzers.unit_quality")


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


class UnitCharacterAnalyzer:
    """人物发展分析器 - 使用LLM深度检测人物状态变化和成长逻辑"""

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
        **kwargs
    ) -> Dict:
        """执行人物发展分析（全面深度检测模式）"""
        issues = []

        # 1. LLM深度检测：人物状态变化合理性
        state_issues = await self._analyze_state_changes_with_llm(chapters_data, db, user_id)
        issues.extend(state_issues)

        # 2. LLM深度检测：人物关系发展逻辑
        relationship_issues = await self._analyze_relationships_with_llm(chapters_data, db, user_id)
        issues.extend(relationship_issues)

        # 计算得分
        score = self._calculate_character_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_units": len(chapters_data),
                "analysis_method": "llm_deep"
            }
        }

    # ===== 已废弃的轻量检测方法 =====

    def _analyze_character_state_changes(self, chapters_data: List[Dict]) -> List[Dict]:
        """分析人物状态变化（已废弃，使用LLM深度检测替代）"""
        return []

    def _analyze_character_relationships(self, chapters_data: List[Dict]) -> List[Dict]:
        """分析人物关系变化（已废弃，使用LLM深度检测替代）"""
        return []

    # ===== LLM深度检测方法 =====

    async def _analyze_state_changes_with_llm(self, chapters_data: List[Dict], db, user_id: int) -> List[Dict]:
        """使用LLM深度检测人物状态变化合理性"""
        issues = []

        if not chapters_data:
            return issues

        batch_size = 15
        for batch_start in range(0, len(chapters_data), batch_size):
            batch_end = min(batch_start + batch_size, len(chapters_data))
            batch_chapters = chapters_data[batch_start:batch_end]

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
                    logger.warning("[人物发展分析] 无法获取LLM提供者，跳过状态检测")
                    break

                prompt = f"""你是专业的人物发展审核专家。

请分析以下单元概述中人物状态变化的合理性，检测是否存在矛盾或不合理之处：

【单元概述批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【检测要求】
1. 人物生死状态是否矛盾？（如某章死亡，后续章节却活着且无复活描写）
2. 人物受伤/康复状态是否合理？
3. 人物胜利/失败状态是否连续？
4. 人物安全/危险状态转换是否有铺垫？

【输出格式】
```json
{{
  "state_issues": [
    {{
      "unit_number": 单元号,
      "character": "人物名（如有）",
      "issue_type": "生死矛盾|受伤矛盾|状态突变",
      "description": "详细描述问题",
      "severity": "critical|warning"
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
                    for issue in result.get("state_issues", []):
                        issues.append({
                            "id": f"UC-LLM-{len(issues)+1}",
                            "dimension": "unit_character",
                            "category": issue.get("issue_type", "状态矛盾"),
                            "severity": issue.get("severity", "warning"),
                            "location": {
                                "chapter_number": issue.get("unit_number", 0),
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("unit_number", 0))
                            },
                            "description": issue.get("description", ""),
                            "evidence": f"第{issue.get('unit_number', '?')}单元",
                            "suggestion": "请检查是否存在状态转换的合理铺垫，或修正矛盾描述",
                            "metadata": {
                                "unit_number": issue.get("unit_number"),
                                "character": issue.get("character", ""),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[人物发展分析] LLM状态检测异常: {str(e)}")
                break

        return issues

    async def _analyze_relationships_with_llm(self, chapters_data: List[Dict], db, user_id: int) -> List[Dict]:
        """使用LLM深度检测人物关系发展逻辑"""
        issues = []

        if len(chapters_data) < 3:
            return issues

        batch_size = 15
        for batch_start in range(0, len(chapters_data), batch_size):
            batch_end = min(batch_start + batch_size, len(chapters_data))
            batch_chapters = chapters_data[batch_start:batch_end]

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
                    logger.warning("[人物发展分析] 无法获取LLM提供者，跳过关系检测")
                    break

                prompt = f"""你是专业的人物关系审核专家。

请分析以下单元概述中人物关系发展的逻辑性，检测是否存在突然转变或不合理之处：

【单元概述批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【检测要求】
1. 人物关系转变是否合理？（如从敌人突然变成盟友且无铺垫）
2. 情感变化是否符合逻辑？（如从深爱突然变成仇恨）
3. 信任/背叛转变是否有充分动机？

【输出格式】
```json
{{
  "relationship_issues": [
    {{
      "unit_number": 单元号,
      "characters": ["人物A", "人物B"],
      "issue_type": "关系突变|情感矛盾|信任转变缺乏铺垫",
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

                import re
                import json
                json_match = re.search(
                    r'```json\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    result = json.loads(json_match.group(1))
                    for issue in result.get("relationship_issues", []):
                        issues.append({
                            "id": f"UR-LLM-{len(issues)+1}",
                            "dimension": "unit_character",
                            "category": issue.get("issue_type", "关系问题"),
                            "severity": issue.get("severity", "info"),
                            "location": {
                                "chapter_number": issue.get("unit_number", 0),
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("unit_number", 0))
                            },
                            "description": issue.get("description", ""),
                            "evidence": f"第{issue.get('unit_number', '?')}单元",
                            "suggestion": "建议增加人物关系转变的铺垫和动机描写",
                            "metadata": {
                                "unit_number": issue.get("unit_number"),
                                "characters": issue.get("characters", []),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[人物发展分析] LLM关系检测异常: {str(e)}")
                break

        return issues

    def _calculate_character_score(self, issues: List[Dict]) -> float:
        """计算人物发展得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 20
            elif severity == "warning":
                score -= 10
            elif severity == "info":
                score -= 3

        return max(0, min(100, score))

    def _apply_feedback_thresholds(self, user_id: int, issues: List[Dict]) -> List[Dict]:
        """应用用户反馈学习的阈值调整"""
        try:
            from .feedback_learning import get_feedback_manager
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
            logger.warning(f"[人物发展分析] 应用反馈阈值失败: {str(e)}")
            return issues


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


class UnitTimelineSpaceAnalyzer:
    """时间线与空间逻辑分析器 - 使用LLM深度检测人物位置、出场时间线、事件因果、状态连续性"""

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
        """执行时间线空间综合分析（全部使用LLM深度检测）"""
        issues = []

        # 1. 人物位置追踪(LLM深度检测)
        location_issues = await self._track_character_locations_llm(chapters_data, db, user_id)
        issues.extend(location_issues)

        # 2. 人物出场时间线(LLM深度检测)
        debut_issues = await self._check_character_debut_timeline_llm(chapters_data, db, user_id)
        issues.extend(debut_issues)

        # 3. 事件因果关系(LLM深度检测)
        causality_issues = await self._check_event_causality_llm(chapters_data, db, user_id, worldview_settings)
        issues.extend(causality_issues)

        # 4. 人物状态连续性(LLM深度检测)
        state_issues = await self._check_character_state_continuity(
            chapters_data, character_profiles, db, user_id
        )
        issues.extend(state_issues)

        # 计算得分
        score = self._calculate_timeline_space_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_units": len(chapters_data),
                "analysis_method": "llm_deep"
            }
        }

    async def _track_character_locations_llm(self, chapters_data: List[Dict], db, user_id: int) -> List[Dict]:
        """使用LLM深度检测人物位置逻辑错误"""
        issues = []

        if not chapters_data:
            return issues

        batch_size = 15
        for batch_start in range(0, len(chapters_data), batch_size):
            batch_end = min(batch_start + batch_size, len(chapters_data))
            batch_chapters = chapters_data[batch_start:batch_end]

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
                    logger.warning("[时间线空间分析] 无法获取LLM提供者，跳过位置追踪")
                    break

                prompt = f"""你是专业的小说逻辑审核专家，专门检测人物位置逻辑错误。

请分析以下单元概述中人物的位置逻辑是否一致：

【单元概述批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【检测要求】
1. 某人物在某单元被派往A地执行任务，但在后续单元中却出现在B地且无移动说明
2. 同一场景中不应该在场的人物却出现了
3. 人物在两个不同地点同时出现
4. 位置移动不合理（如短时间内跨越极远距离且无传送手段）

【输出格式】
```json
{{
  "location_issues": [
    {{
      "unit_number": 单元号,
      "character": "人物名",
      "issue_type": "位置矛盾|同时出现|移动不合理|不在场却出现",
      "description": "详细描述位置逻辑错误",
      "severity": "critical|warning"
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
                    for issue in result.get("location_issues", []):
                        issues.append({
                            "id": f"TL-LOC-{len(issues)+1}",
                            "dimension": "unit_timeline_space",
                            "category": issue.get("issue_type", "位置逻辑错误"),
                            "severity": issue.get("severity", "warning"),
                            "location": {
                                "chapter_number": issue.get("unit_number", 0),
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("unit_number", 0))
                            },
                            "description": issue.get("description", ""),
                            "evidence": f"第{issue.get('unit_number', '?')}单元 - {issue.get('character', '?')}",
                            "suggestion": "请修正人物位置逻辑，或添加合理的移动说明",
                            "metadata": {
                                "unit_number": issue.get("unit_number"),
                                "character": issue.get("character", ""),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[时间线空间分析] LLM位置追踪异常: {str(e)}")
                break

        return issues

    async def _check_character_debut_timeline_llm(self, chapters_data: List[Dict], db, user_id: int) -> List[Dict]:
        """使用LLM深度检测人物出场时间线错误"""
        issues = []

        if not chapters_data:
            return issues

        # 构建完整单元概述供LLM分析
        all_content = "\n".join([
            f"第{ch.get('chapter_number', 0)}单元：{(ch.get('content', '') or ch.get('summary', ''))}"
            for ch in chapters_data[:50]
        ])

        try:
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[时间线空间分析] 无法获取LLM提供者，跳过出场时间线检测")
                return issues

            prompt = f"""你是专业的小说逻辑审核专家，专门检测人物出场时间线错误。

请分析以下单元概述中人物的出场时间线是否合理：

【单元概述列表】（共{len(chapters_data)}个单元）
{all_content}

【检测要求】
1. 某角色在后面的单元才"首次登场"，但在之前的单元中主角就已经"遇到"或"认识"该角色
2. 人物在被介绍出场之前就已经被提及，且不是以"神秘人"等匿名方式
3. 角色的出场顺序与全局设定矛盾

注意区分：
- 合理的预提及（如传闻、信件、神秘人）是允许的
- 不合理的是：明确描述与该人物见面/对话/互动，但该人物还未正式出场

【输出格式】
```json
{{
  "debut_issues": [
    {{
      "character": "人物名",
      "first_appear_unit": 首次互动单元号,
      "official_debut_unit": 正式出场单元号,
      "issue_type": "提前互动|出场顺序矛盾",
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

            import re
            import json
            json_match = re.search(
                r'```json\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                result = json.loads(json_match.group(1))
                for issue in result.get("debut_issues", []):
                    issues.append({
                        "id": f"TL-DEB-{len(issues)+1}",
                        "dimension": "unit_timeline_space",
                        "category": issue.get("issue_type", "出场时间线错误"),
                        "severity": issue.get("severity", "warning"),
                        "location": {
                            "chapter_number": issue.get("first_appear_unit", 0),
                            "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("first_appear_unit", 0))
                        },
                        "description": issue.get("description", ""),
                        "evidence": f"{issue.get('character', '?')}：首次互动第{issue.get('first_appear_unit', '?')}单元，正式出场第{issue.get('official_debut_unit', '?')}单元",
                        "suggestion": "请调整人物出场顺序，或在更早的单元中添加该角色的正式出场",
                        "metadata": {
                            "character": issue.get("character", ""),
                            "first_appear_unit": issue.get("first_appear_unit"),
                            "official_debut_unit": issue.get("official_debut_unit"),
                            "analysis_method": "llm_deep"
                        }
                    })
        except Exception as e:
            logger.warning(f"[时间线空间分析] LLM出场时间线检测异常: {str(e)}")

        return issues

    async def _check_event_causality_llm(self, chapters_data: List[Dict], db, user_id: int, worldview_settings: Dict = None) -> List[Dict]:
        """使用LLM深度检测事件因果关系和故事情节合理性"""
        issues = []

        if not chapters_data:
            return issues

        # 构建完整内容
        all_content = "\n".join([
            f"第{ch.get('chapter_number', 0)}单元：{(ch.get('content', '') or ch.get('summary', ''))}"
            for ch in chapters_data[:50]
        ])

        worldview_info = ""
        if worldview_settings:
            if isinstance(worldview_settings, dict):
                worldview_info = str(worldview_settings.get(
                    "description", worldview_settings.get("content", "")))
            elif isinstance(worldview_settings, str):
                worldview_info = worldview_settings

        try:
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[时间线空间分析] 无法获取LLM提供者，跳过因果检测")
                return issues

            worldview_section = f"\n【世界观设定】\n{worldview_info}" if worldview_info else ""

            prompt = f"""你是专业的小说逻辑审核专家，专门检测故事情节的合理性和逻辑性。

请分析以下单元概述中事件的因果关系和情节逻辑：

【单元概述列表】（共{len(chapters_data)}个单元）
{all_content}{worldview_section}

【检测要求】
1. **因果倒置**：结果事件是否发生在原因事件之前？
2. **缺失前提**：某事件发生但缺少必要的铺垫或前提事件？
3. **世界观冲突**：情节发展是否符合世界观设定？
4. **时间矛盾**：事件的先后顺序是否符合逻辑？
5. **空间逻辑**：人物在不同地点的活动是否合理？

【输出格式】
```json
{{
  "causality_issues": [
    {{
      "unit_number": 单元号,
      "issue_type": "因果倒置|缺失前提|世界观冲突|时间矛盾|空间逻辑",
      "description": "详细描述问题",
      "severity": "critical|warning"
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
                for issue in result.get("causality_issues", []):
                    issues.append({
                        "id": f"TL-CAU-{len(issues)+1}",
                        "dimension": "unit_timeline_space",
                        "category": issue.get("issue_type", "因果关系错误"),
                        "severity": issue.get("severity", "warning"),
                        "location": {
                            "chapter_number": issue.get("unit_number", 0),
                            "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("unit_number", 0))
                        },
                        "description": issue.get("description", ""),
                        "evidence": f"第{issue.get('unit_number', '?')}单元",
                        "suggestion": "请修正因果关系，确保事件发生顺序符合逻辑",
                        "metadata": {
                            "unit_number": issue.get("unit_number"),
                            "issue_type": issue.get("issue_type"),
                            "analysis_method": "llm_deep"
                        }
                    })
        except Exception as e:
            logger.warning(f"[时间线空间分析] LLM因果检测异常: {str(e)}")

        return issues

    async def _check_character_state_continuity(
        self,
        chapters_data: List[Dict],
        character_profiles: List[Dict],
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM深度检测人物状态连续性错误"""
        issues = []

        if not chapters_data:
            return issues

        # 构建人物设定信息
        profile_info = ""
        if character_profiles:
            profile_parts = []
            for char in character_profiles:
                if isinstance(char, dict):
                    name = char.get("name", char.get("character_name", "未知"))
                    role = char.get("role", char.get("position", ""))
                    profile_parts.append(f"- {name}（{role}）")
            profile_info = "\n【人物设定】\n" + \
                "\n".join(profile_parts) if profile_parts else ""

        # 构建完整内容
        all_content = "\n".join([
            f"第{ch.get('chapter_number', 0)}单元：{(ch.get('content', '') or ch.get('summary', ''))}"
            for ch in chapters_data[:50]
        ])

        try:
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[时间线空间分析] 无法获取LLM提供者，跳过状态连续性检测")
                return issues

            prompt = f"""你是专业的小说逻辑审核专家，专门检测人物状态变化的连续性错误。

请分析以下单元概述中人物状态变化是否连续一致：

【单元概述列表】（共{len(chapters_data)}个单元）
{all_content}{profile_info}

【检测要求】
追踪每个人物在各单元的状态变化轨迹，检测以下状态变化错误：
1. **职位变化不连续**：如第10章升任知府，第12章仍被称为县令
2. **地理位置突变**：如第5章在北京，第6章突然出现在南京且无移动说明
3. **情感关系突变**：如第15章还深爱某人，第16章无故变为仇恨
4. **能力状态矛盾**：如第8章武功被废，第10章却施展绝技
5. **健康状况矛盾**：如第12章重伤卧床，第13章却活蹦乱跳
6. **装备物品矛盾**：如第7章宝剑已毁，第9章却继续使用

【输出格式】
```json
{{
  "state_issues": [
    {{
      "character": "人物名",
      "from_unit": 变化前单元号,
      "to_unit": 变化后单元号,
      "state_type": "职位|位置|情感|能力|健康|装备",
      "issue_type": "职位变化不连续|地理位置突变|情感关系突变|能力状态矛盾|健康状况矛盾|装备物品矛盾",
      "description": "详细描述状态变化错误",
      "severity": "critical|warning"
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
                for issue in result.get("state_issues", []):
                    issues.append({
                        "id": f"TL-STATE-{len(issues)+1}",
                        "dimension": "unit_timeline_space",
                        "category": issue.get("issue_type", "状态连续性错误"),
                        "severity": issue.get("severity", "warning"),
                        "location": {
                            "chapter_number": issue.get("from_unit", 0),
                            "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("from_unit", 0))
                        },
                        "description": issue.get("description", ""),
                        "evidence": f"{issue.get('character', '?')}：第{issue.get('from_unit', '?')}单元 → 第{issue.get('to_unit', '?')}单元",
                        "suggestion": "请修正人物状态变化，确保连续性合理或有适当铺垫",
                        "metadata": {
                            "character": issue.get("character", ""),
                            "from_unit": issue.get("from_unit"),
                            "to_unit": issue.get("to_unit"),
                            "state_type": issue.get("state_type", ""),
                            "analysis_method": "llm_deep"
                        }
                    })
        except Exception as e:
            logger.warning(f"[时间线空间分析] LLM状态连续性检测异常: {str(e)}")

        return issues

    def _calculate_timeline_space_score(self, issues: List[Dict]) -> float:
        """计算时间线空间得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 15
            elif severity == "warning":
                score -= 8
            elif severity == "info":
                score -= 3

        return max(0, min(100, score))


class UnitOOCAnalyzer:
    """人物OOC分析器 - 使用LLM深度检测人物是否违背人设"""

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
        """执行人物OOC分析（全部使用LLM深度检测）"""
        issues = []

        # 1. LLM深度检测：人物行为OOC
        behavior_issues = await self._check_character_behavior_ooc(
            chapters_data, character_profiles, db, user_id
        )
        issues.extend(behavior_issues)

        # 2. LLM深度检测：人物关系OOC
        relation_issues = await self._check_character_relationship_ooc(
            chapters_data, character_profiles, db, user_id
        )
        issues.extend(relation_issues)

        # 计算得分
        score = self._calculate_ooc_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_units": len(chapters_data),
                "analysis_method": "llm_deep"
            }
        }

    async def _check_character_behavior_ooc(
        self,
        chapters_data: List[Dict],
        character_profiles: List[Dict],
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM深度检测人物行为是否违背人设"""
        issues = []

        if not chapters_data:
            return issues

        # 构建人物设定信息
        profile_info = ""
        if character_profiles:
            profile_parts = []
            for char in character_profiles:
                if isinstance(char, dict):
                    name = char.get("name", char.get("character_name", "未知"))
                    personality = char.get(
                        "personality", char.get("character_traits", ""))
                    background = char.get(
                        "background", char.get("backstory", ""))
                    motivation = char.get("motivation", char.get("goal", ""))
                    abilities = char.get("abilities", char.get("skills", ""))
                    profile_parts.append(
                        f"- {name}：性格({personality})，背景({background})，动机({motivation})，能力({abilities})"
                    )
            profile_info = "\n【人物设定】\n" + \
                "\n".join(profile_parts) if profile_parts else ""

        # 构建单元概述内容
        all_content = "\n".join([
            f"第{ch.get('chapter_number', 0)}单元：{(ch.get('content', '') or ch.get('summary', ''))}"
            for ch in chapters_data[:50]
        ])

        try:
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[人物OOC分析] 无法获取LLM提供者，跳过行为OOC检测")
                return issues

            prompt = f"""你是专业的人物设定审核专家，专门检测人物行为是否违背其人设（OOC，Out of Character）。

请分析以下单元概述中人物的行为是否符合其设定：

【单元概述列表】（共{len(chapters_data)}个单元）
{all_content}{profile_info}

【检测要求】
1. **性格违背**：如懦弱的角色突然变得勇敢且无合理铺垫
2. **动机矛盾**：如追求权力的角色突然放弃一切且无解释
3. **说话方式不符**：如文盲角色突然引用诗词
4. **能力超纲**：如不会武功的角色突然施展绝世武功
5. **转变缺乏铺垫**：人物性格转变但缺少触发事件

注意区分：
- 有合理铺垫的性格成长是允许的（如经历了重大事件后性格转变）
- OOC是指无铺垫、无解释的突然违背人设的行为

【输出格式】
```json
{{
  "ooc_issues": [
    {{
      "character": "人物名",
      "unit_number": 单元号,
      "issue_type": "性格违背|动机矛盾|说话方式不符|能力超纲|转变缺乏铺垫",
      "description": "详细描述OOC问题",
      "severity": "critical|warning"
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
                for issue in result.get("ooc_issues", []):
                    issues.append({
                        "id": f"OOC-BEH-{len(issues)+1}",
                        "dimension": "unit_ooc",
                        "category": issue.get("issue_type", "人物OOC"),
                        "severity": issue.get("severity", "warning"),
                        "location": {
                            "chapter_number": issue.get("unit_number", 0),
                            "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("unit_number", 0))
                        },
                        "description": issue.get("description", ""),
                        "evidence": f"{issue.get('character', '?')} - 第{issue.get('unit_number', '?')}单元",
                        "suggestion": "请修正人物行为使其符合人设，或添加合理的转变铺垫",
                        "metadata": {
                            "character": issue.get("character", ""),
                            "unit_number": issue.get("unit_number"),
                            "analysis_method": "llm_deep"
                        }
                    })
        except Exception as e:
            logger.warning(f"[人物OOC分析] LLM行为OOC检测异常: {str(e)}")

        return issues

    async def _check_character_relationship_ooc(
        self,
        chapters_data: List[Dict],
        character_profiles: List[Dict],
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM深度检测人物关系处理是否违背人设"""
        issues = []

        if not chapters_data:
            return issues

        # 构建人物设定信息
        profile_info = ""
        if character_profiles:
            profile_parts = []
            for char in character_profiles:
                if isinstance(char, dict):
                    name = char.get("name", char.get("character_name", "未知"))
                    personality = char.get(
                        "personality", char.get("character_traits", ""))
                    profile_parts.append(f"- {name}：{personality}")
            profile_info = "\n【人物设定】\n" + \
                "\n".join(profile_parts) if profile_parts else ""

        # 构建单元概述内容
        all_content = "\n".join([
            f"第{ch.get('chapter_number', 0)}单元：{(ch.get('content', '') or ch.get('summary', ''))}"
            for ch in chapters_data[:50]
        ])

        try:
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[人物OOC分析] 无法获取LLM提供者，跳过关系OOC检测")
                return issues

            prompt = f"""你是专业的人物关系审核专家，专门检测人物对待他人的方式是否违背其人设。

请分析以下单元概述中人物的关系处理是否符合其性格设定：

【单元概述列表】（共{len(chapters_data)}个单元）
{all_content}{profile_info}

【检测要求】
1. **对待方式不符**：如温柔的角色突然对亲近的人残暴且无解释
2. **忠诚度矛盾**：如忠诚的角色无故背叛
3. **情感表达不符**：如冷摸的角色突然过度表达情感且无铺垫
4. **社交方式矛盾**：如独来独往的角色突然变得极虚社交且无原因

注意区分合理的情感成长与OOC：
- 经历重大事件后的合理转变是允许的
- OOC是无铺垫、无解释的突然违背人设的社交行为

【输出格式】
```json
{{
  "relation_ooc_issues": [
    {{
      "character": "人物名",
      "target": "对方人物名",
      "unit_number": 单元号,
      "issue_type": "对待方式不符|忠诚度矛盾|情感表达不符|社交方式矛盾",
      "description": "详细描述关系OOC问题",
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
                for issue in result.get("relation_ooc_issues", []):
                    issues.append({
                        "id": f"OOC-REL-{len(issues)+1}",
                        "dimension": "unit_ooc",
                        "category": issue.get("issue_type", "关系OOC"),
                        "severity": issue.get("severity", "info"),
                        "location": {
                            "chapter_number": issue.get("unit_number", 0),
                            "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("unit_number", 0))
                        },
                        "description": issue.get("description", ""),
                        "evidence": f"{issue.get('character', '?')} → {issue.get('target', '?')}：第{issue.get('unit_number', '?')}单元",
                        "suggestion": "请修正人物关系处理使其符合人设，或添加合理的转变铺垫",
                        "metadata": {
                            "character": issue.get("character", ""),
                            "target": issue.get("target", ""),
                            "unit_number": issue.get("unit_number"),
                            "analysis_method": "llm_deep"
                        }
                    })
        except Exception as e:
            logger.warning(f"[人物OOC分析] LLM关系OOC检测异常: {str(e)}")

        return issues

    def _calculate_ooc_score(self, issues: List[Dict]) -> float:
        """计算OOC得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 15
            elif severity == "warning":
                score -= 8
            elif severity == "info":
                score -= 3

        return max(0, min(100, score))


class CharacterStateChangeAnalyzer:
    """人物状态变化检测器 - 检测人物的地点、身份、情感、成长轨迹等状态变化"""

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
        """执行人物状态变化分析"""
        issues = []

        if not character_profiles:
            character_profiles = []

        # 分批检测（每批10章）
        batch_size = 10
        for batch_start in range(0, len(chapters_data), batch_size):
            batch_end = min(batch_start + batch_size, len(chapters_data))
            batch_chapters = chapters_data[batch_start:batch_end]

            # 构建批次内容和前文状态记录
            batch_content = []
            previous_states = []
            for ch in batch_chapters:
                content = ch.get("content", "") or ch.get("summary", "")
                batch_content.append(
                    f"第{ch.get('chapter_number', 0)}单元：{content}"
                )

            # 提取前文状态记录（批次前的5章）
            if batch_start > 0:
                prev_chapters = chapters_data[max(
                    0, batch_start-5):batch_start]
                for ch in prev_chapters:
                    content = ch.get("content", "") or ch.get("summary", "")
                    previous_states.append(
                        f"第{ch.get('chapter_number', 0)}单元：{content}"
                    )

            try:
                from app.agents.llm_manager import get_llm_manager
                llm_manager = get_llm_manager()
                llm_provider = await llm_manager.get_provider_from_db(db, user_id)

                if not llm_provider:
                    logger.warning("[人物状态变化检测] 无法获取LLM提供者，跳过批次检测")
                    break

                # 格式化人物设定
                profiles_text = "\n".join([
                    f"- {p.get('name', '未知')}: {p.get('description', '')}"
                    for p in character_profiles[:10]
                ]) if character_profiles else "无"

                previous_states_text = "\n".join(
                    previous_states) if previous_states else "无前文记录"

                prompt = f"""你是专业的人物状态审核专家。

请分析以下单元概述中人物状态的各个维度变化：

【当前单元批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【人物设定】
{profiles_text}

【前文状态记录】
{previous_states_text}

【检测要求】
1. 地点变化：人物位置转换是否合理？是否有移动说明？
2. 身份变化：职位、地位、角色身份的转变是否有铺垫？
3. 情感状态：情绪转换是否自然？是否有触发事件？
4. 成长轨迹：能力、认知、性格的成长是否符合逻辑？
5. 健康状况：受伤、康复、疲劳等状态是否连续？
6. 关系状态：与其他人物关系的转变是否合理？

【输出格式】
```json
{{
  "state_changes": [
    {{
      "character_name": "人物名",
      "state_dimension": "地点|身份|情感|成长|健康|关系",
      "previous_state": "之前状态",
      "current_state": "当前状态",
      "has_transition": true,
      "transition_natural": false,
      "severity": "critical|warning|info",
      "description": "详细描述状态变化及问题",
      "suggestion": "修正建议"
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
                    for issue in result.get("state_changes", []):
                        issues.append({
                            "id": f"CS-{len(issues)+1}",
                            "dimension": "character_state",
                            "category": issue.get("state_dimension", "状态变化"),
                            "severity": issue.get("severity", "warning"),
                            "location": {
                                "chapter_number": batch_end,
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, batch_end)
                            },
                            "description": issue.get("description", ""),
                            "evidence": f"{issue.get('character_name', '?')}：{issue.get('previous_state', '?')} → {issue.get('current_state', '?')}",
                            "suggestion": issue.get("suggestion", "建议补充状态转换的合理铺垫"),
                            "metadata": {
                                "character_name": issue.get("character_name"),
                                "state_dimension": issue.get("state_dimension"),
                                "has_transition": issue.get("has_transition"),
                                "transition_natural": issue.get("transition_natural"),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[人物状态变化检测] 批次{batch_start}检测异常: {str(e)}")
                continue

        # 计算得分
        score = self._calculate_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_units": len(chapters_data),
                "analysis_method": "llm_deep"
            }
        }

    def _calculate_score(self, issues: List[Dict]) -> float:
        """计算人物状态变化得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 15
            elif severity == "warning":
                score -= 8
            elif severity == "info":
                score -= 3

        return max(0, min(100, score))


class WorldviewConsistencyAnalyzer:
    """世界观一致性检测器 - 检测正文内容与设定的世界观、规则、背景等是否保持一致"""

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
        """执行世界观一致性分析"""
        issues = []

        if not worldview_settings:
            worldview_settings = {}

        # 分批检测（每批8章）
        batch_size = 8
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
                    logger.warning("[世界观一致性检测] 无法获取LLM提供者，跳过批次检测")
                    break

                # 格式化世界观设定
                worldview_text = ""
                if isinstance(worldview_settings, dict):
                    for key, value in worldview_settings.items():
                        if isinstance(value, str):
                            worldview_text += f"- {key}: {value}\n"
                        elif isinstance(value, (list, dict)):
                            worldview_text += f"- {key}: {json.dumps(value, ensure_ascii=False, indent=2)}\n"
                elif isinstance(worldview_settings, str):
                    worldview_text = worldview_settings

                if not worldview_text:
                    worldview_text = "无详细世界观设定"

                prompt = f"""你是专业的世界观一致性审核专家。

请检测以下单元内容是否与设定的世界观、规则、背景保持一致：

【当前单元批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【世界观设定】
{worldview_text}

【检测要求】
1. 物理法则：是否符合世界观中的物理规则？（如魔法系统、科技水平）
2. 社会制度：是否符合设定的社会结构、阶级、法律？
3. 文化习俗：是否符合设定的文化传统、礼仪、禁忌？
4. 经济体系：货币、交易、资源分配是否合理？
5. 力量体系：修炼等级、能力限制、代价是否一致？
6. 历史背景：是否与既定的历史事件、时间线冲突？
7. 地理环境：地形、气候、距离是否合理？
8. 生物设定：种族特性、寿命、能力是否符合设定？

【输出格式】
```json
{{
  "consistency_issues": [
    {{
      "rule_category": "物理法则|社会制度|文化习俗|经济体系|力量体系|历史背景|地理环境|生物设定",
      "rule_description": "违反的规则描述",
      "text_evidence": "原文引用",
      "conflict_description": "冲突说明",
      "severity": "critical|warning|info",
      "suggestion": "修正建议"
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
                    for issue in result.get("consistency_issues", []):
                        issues.append({
                            "id": f"WV-{len(issues)+1}",
                            "dimension": "worldview_consistency",
                            "category": issue.get("rule_category", "世界观冲突"),
                            "severity": issue.get("severity", "warning"),
                            "location": {
                                "chapter_number": batch_end,
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, batch_end)
                            },
                            "description": issue.get("conflict_description", ""),
                            "evidence": issue.get("text_evidence", ""),
                            "suggestion": issue.get("suggestion", "建议修正内容使其符合世界观设定"),
                            "metadata": {
                                "rule_category": issue.get("rule_category"),
                                "rule_description": issue.get("rule_description"),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[世界观一致性检测] 批次{batch_start}检测异常: {str(e)}")
                continue

        # 计算得分
        score = self._calculate_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_units": len(chapters_data),
                "analysis_method": "llm_deep"
            }
        }

    def _calculate_score(self, issues: List[Dict]) -> float:
        """计算世界观一致性得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 20
            elif severity == "warning":
                score -= 10
            elif severity == "info":
                score -= 4

        return max(0, min(100, score))


class TimelineConsistencyAnalyzer:
    """时间线一致性检测器 - 检测故事情节的时间线是否连贯，事件发生的先后顺序是否合理"""

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
        """执行时间线一致性分析"""
        issues = []

        # 构建完整时间线记录（最多前30章）
        timeline_records = []
        for ch in chapters_data[:30]:
            content = ch.get("content", "") or ch.get("summary", "")
            timeline_records.append(
                f"第{ch.get('chapter_number', 0)}单元：{content}"
            )

        # 提取全局大纲中的时间线信息
        outline_timeline = global_outline[:
                                          2000] if global_outline else "无全局大纲时间线"

        # 分批检测（每批10章）
        batch_size = 10
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
                    logger.warning("[时间线一致性检测] 无法获取LLM提供者，跳过批次检测")
                    break

                timeline_text = "\n".join(timeline_records)

                prompt = f"""你是专业的时间线一致性审核专家。

请检测以下单元内容的时间线是否连贯，事件发生的先后顺序是否合理：

【当前单元批次】（第{batch_start+1}-{batch_end}单元）
{chr(10).join(batch_content)}

【完整时间线记录】（前30章）
{timeline_text}

【全局大纲时间线】
{outline_timeline}

【检测要求】
1. 时间顺序：事件发生的先后顺序是否合理？是否有时间倒流？
2. 时间跨度：两个事件之间的时间间隔是否合理？
3. 季节/天气：季节变化、天气描述是否连贯？
4. 年龄/成长：人物年龄增长、技能提升的时间是否合理？
5. 事件持续时间：长期事件（战争、旅行、修炼）的时间跨度是否一致？
6. 时间标记：明确的时间标记（如"三天后"、"次年春天"）是否前后矛盾？
7. 并行事件：同时发生的不同事件线是否有时间冲突？
8. 历史事件：回忆、flashback中的时间线是否与主线一致？

【输出格式】
```json
{{
  "timeline_issues": [
    {{
      "issue_type": "时间顺序|时间跨度|季节天气|年龄成长|事件持续|时间标记|并行事件|历史事件",
      "chapter_number": 单元号,
      "time_reference": "时间引用",
      "conflict_description": "冲突描述",
      "previous_timeline": "之前的时间线",
      "current_timeline": "当前的时间线",
      "severity": "critical|warning|info",
      "suggestion": "修正建议"
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
                    for issue in result.get("timeline_issues", []):
                        issues.append({
                            "id": f"TL-{len(issues)+1}",
                            "dimension": "timeline_consistency",
                            "category": issue.get("issue_type", "时间线矛盾"),
                            "severity": issue.get("severity", "warning"),
                            "location": {
                                "chapter_number": issue.get("chapter_number", batch_end),
                                "unit_id": UnitStructureAnalyzer._find_unit_id(chapters_data, issue.get("chapter_number", batch_end))
                            },
                            "description": issue.get("conflict_description", ""),
                            "evidence": f"{issue.get('time_reference', '?')}：{issue.get('previous_timeline', '?')} → {issue.get('current_timeline', '?')}",
                            "suggestion": issue.get("suggestion", "建议修正时间线使其保持连贯"),
                            "metadata": {
                                "issue_type": issue.get("issue_type"),
                                "time_reference": issue.get("time_reference"),
                                "previous_timeline": issue.get("previous_timeline"),
                                "current_timeline": issue.get("current_timeline"),
                                "analysis_method": "llm_deep"
                            }
                        })
            except Exception as e:
                logger.warning(f"[时间线一致性检测] 批次{batch_start}检测异常: {str(e)}")
                continue

        # 计算得分
        score = self._calculate_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "total_units": len(chapters_data),
                "analysis_method": "llm_deep"
            }
        }

    def _calculate_score(self, issues: List[Dict]) -> float:
        """计算时间线一致性得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 18
            elif severity == "warning":
                score -= 9
            elif severity == "info":
                score -= 3

        return max(0, min(100, score))
