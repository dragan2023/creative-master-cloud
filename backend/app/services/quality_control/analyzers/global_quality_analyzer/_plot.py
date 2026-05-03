"""
全局大纲质控 - 剧情线一致性分析器 (GlobalPlotConsistencyAnalyzer)

检测主线剧情逻辑、伏笔设置

@date: 2026-04-24
@version: v1.1.0
"""
from typing import Dict, List, Any

from app.core.logger import get_logger
from ._common import call_llm_with_retry, parse_llm_json_response

logger = get_logger("quality_control.analyzers.global_quality")


class GlobalPlotConsistencyAnalyzer:
    """剧情线一致性分析器 - 检测主线剧情逻辑和伏笔设置"""

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
        """执行剧情线一致性分析(v1.1优化版: 新增伏笔回收检测)"""
        issues = []

        # 1. 核心要素检测
        core_issues = self._analyze_core_elements(global_outline)
        issues.extend(core_issues)

        # 2. LLM主线剧情逻辑性检测
        if depth in ["standard", "deep"]:
            logic_issues = await self._analyze_plot_logic_with_llm(
                global_outline, depth, db, user_id
            )
            if isinstance(logic_issues, list):
                issues.extend(logic_issues)

        # 3. 关键词一致性检测
        keyword_issues = self._analyze_keyword_consistency(global_outline)
        issues.extend(keyword_issues)

        # 4. v1.1新增: 伏笔回收检测
        foreshadowing_issues = self._analyze_foreshadowing_payoff(
            global_outline)
        issues.extend(foreshadowing_issues)

        # 5. v1.1新增: LLM伏笔深度分析
        if depth in ["standard", "deep"]:
            foreshadowing_llm_issues = await self._analyze_foreshadowing_with_llm(
                global_outline, depth, db, user_id
            )
            if isinstance(foreshadowing_llm_issues, list):
                issues.extend(foreshadowing_llm_issues)

        # 6. 应用用户反馈学习的阈值调整
        issues = self._apply_feedback_thresholds(user_id, issues)

        # 计算得分
        score = self._calculate_consistency_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "outline_length": len(global_outline),
                "analysis_depth": depth,
                "foreshadowing_count": self._count_foreshadowing_keywords(global_outline)
            }
        }

    def _analyze_core_elements(self, global_outline: str) -> List[Dict]:
        """检测核心要素是否完整"""
        issues = []
        content = global_outline.lower()

        core_elements = {
            "主角": ["主角", "主人公", "主人公"],
            "目标": ["目标", "目的", "使命", "任务"],
            "冲突": ["冲突", "矛盾", "危机", "对抗"],
            "转折": ["转折", "变化", "意外", "突然"],
            "结局": ["结局", "结尾", "最终", "最后"]
        }

        missing_elements = []
        for element, keywords in core_elements.items():
            if not any(kw in content for kw in keywords):
                missing_elements.append(element)

        if missing_elements:
            issues.append({
                "id": "GP-CORE-MISSING",
                "dimension": "global_plot_consistency",
                "category": "核心要素缺失",
                "severity": "warning",
                "location": {},
                "description": f"全局大纲缺少以下核心要素: {', '.join(missing_elements)}",
                "evidence": f"缺失要素: {', '.join(missing_elements)}",
                "suggestion": "建议补充这些核心要素的描述,确保故事完整性",
                "metadata": {"missing_elements": missing_elements}
            })

        return issues

    async def _analyze_plot_logic_with_llm(
        self,
        global_outline: str,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM检测主线剧情逻辑性(防错版: 超时1200秒)"""
        issues = []

        try:
            logger.info("[剧情线一致性分析] 开始LLM剧情逻辑分析...")
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[剧情线一致性分析] 无法获取LLM提供者,跳过逻辑分析")
                return issues

            logger.info("[剧情线一致性分析] 成功获取LLM提供者，开始调用...")

            outline_sample = global_outline  # 不再截断大纲，完整上下文有助于LLM准确分析

            prompt = f"""你是专业的剧情逻辑分析师。

    请分析以下全局大纲的剧情逻辑:

    【全局大纲内容】(前15000字)
    {outline_sample}

    【分析要求】
    1. 检测主线剧情是否有清晰的因果链
    2. 评估伏笔设置是否合理(是否有铺垫和回收)
    3. 检测情节发展是否符合逻辑(是否存在突兀的跳跃)
    4. 评估剧情节奏是否合理

    【输出格式】
    ```json
    {{
      "issues": [
        {{
          "type": "问题类型",
          "severity": "warning|critical|info",
          "description": "详细描述",
          "location": "问题所在位置"
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
            result = parse_llm_json_response(response_text, logger, "剧情线一致性分析")

            for issue in result.get("issues", []):
                issues.append({
                    "id": f"GP-LOGIC-{len(issues)+1}",
                    "dimension": "global_plot_consistency",
                    "category": issue.get("type", "剧情逻辑问题"),
                    "severity": issue.get("severity", "warning"),
                    "location": {
                        "description": issue.get("location", "")
                    },
                    "description": issue.get("description", ""),
                    "evidence": f"剧情逻辑分析",
                    "suggestion": "建议修正剧情逻辑,确保因果链清晰",
                    "metadata": {
                        "analysis_method": "llm",
                        "issue_type": issue.get("type")
                    }
                })

        except Exception as e:
            logger.warning(f"[剧情线一致性分析] LLM分析异常: {str(e)}")

        return issues

    def _analyze_keyword_consistency(self, global_outline: str) -> List[Dict]:
        """分析关键词一致性(术语统一)"""
        issues = []

        # 简单检测: 查找可能的术语不一致
        # 例如: "灵力"/"灵气"/"真气" 混用
        term_groups = [
            ["灵力", "灵气", "真气", "元力"],
            ["修为", "实力", "境界", "等级"],
            ["宗门", "门派", "家族", "势力"]
        ]

        content = global_outline.lower()
        for group in term_groups:
            found_terms = [term for term in group if term in content]
            if len(found_terms) >= 2:
                issues.append({
                    "id": f"GP-TERM-{len(issues)+1}",
                    "dimension": "global_plot_consistency",
                    "category": "术语不统一",
                    "severity": "info",
                    "location": {},
                    "description": f"检测到可能的术语混用: {', '.join(found_terms)}",
                    "evidence": f"术语组: {', '.join(found_terms)}",
                    "suggestion": "建议统一使用同一个术语,避免读者混淆",
                    "metadata": {"terms": found_terms}
                })

        return issues

    def _analyze_foreshadowing_payoff(self, global_outline: str) -> List[Dict]:
        """
        v1.1新增: 伏笔回收检测(规则版)

        检测伏笔关键词,评估是否有铺垫和回收
        """
        issues = []

        # 伏笔关键词模式
        foreshadowing_patterns = {
            "伏笔铺垫": [
                "暗藏", "隐藏", "秘密", "神秘", "不知", "未觉", "尚未",
                "悄然", "隐隐", "似乎", "仿佛", "预感", "直觉",
                "注定", "命运", "宿命", "预言", "传说"
            ],
            "伏笔回收": [
                "原来", "竟然", "居然", "真相", "揭晓", "揭开",
                "揭示", "暴露", "显现", "发现", "终于", "最终",
                "揭晓谜底", "水落石出", "恍然大悟"
            ]
        }

        content = global_outline.lower()

        # 统计伏笔关键词出现次数
        setup_count = sum(
            content.count(keyword)
            for keyword in foreshadowing_patterns["伏笔铺垫"]
        )
        payoff_count = sum(
            content.count(keyword)
            for keyword in foreshadowing_patterns["伏笔回收"]
        )

        # 检测伏笔不平衡
        if setup_count > 0 and payoff_count == 0:
            issues.append({
                "id": "GP-FORESHADOW-UNRECOVERED",
                "dimension": "global_plot_consistency",
                "category": "伏笔未回收",
                "severity": "warning",
                "location": {},
                "description": f"检测到{setup_count}处伏笔铺垫,但未发现明显的回收描述",
                "evidence": f"铺垫关键词出现{setup_count}次,回收关键词出现{payoff_count}次",
                "suggestion": "建议在后续章节中回收这些伏笔,避免读者感到困惑",
                "metadata": {
                    "setup_count": setup_count,
                    "payoff_count": payoff_count,
                    "analysis_method": "rule_based"
                }
            })
        elif setup_count > payoff_count * 2 and setup_count > 5:
            # 铺垫远多于回收(比例超过2:1)
            issues.append({
                "id": "GP-FORESHADOW-IMBALANCE",
                "dimension": "global_plot_consistency",
                "category": "伏笔比例失衡",
                "severity": "info",
                "location": {},
                "description": f"伏笔铺垫({setup_count}次)远多于回收({payoff_count}次),可能存在伏笔遗漏",
                "evidence": f"铺垫/回收比例: {setup_count}/{payoff_count} (建议1:1到1:1.5)",
                "suggestion": "建议检查是否有伏笔未回收,或适当减少铺垫",
                "metadata": {
                    "setup_count": setup_count,
                    "payoff_count": payoff_count,
                    "ratio": setup_count / max(payoff_count, 1),
                    "analysis_method": "rule_based"
                }
            })

        return issues

    async def _analyze_foreshadowing_with_llm(
        self,
        global_outline: str,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """
        v1.1新增: 使用LLM深度分析伏笔设置和回收(防错版: 超时1200秒)
        """
        issues = []

        try:
            logger.info("[伏笔分析] 开始LLM伏笔深度分析...")
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[伏笔分析] 无法获取LLM提供者,跳过深度分析")
                return issues

            logger.info("[伏笔分析] 成功获取LLM提供者，开始调用...")

            outline_sample = global_outline  # 不再截断大纲，完整上下文有助于LLM准确分析

            prompt = f"""你是专业的剧情结构分析师。

    请分析以下全局大纲中的伏笔设置和回收情况:

    【全局大纲内容】(前15000字)
    {outline_sample}

    【分析要求】
    1. 识别大纲中设置的伏笔(暗示、悬念、未解之谜)
    2. 检测这些伏笔是否在后续有回收(揭示、解答、悬念解除)
    3. 评估伏笔的合理性(是否过于明显或过于隐晦)
    4. 检测是否有伏笔被遗忘或遗漏

    【输出格式】
    ```json
    {{
      "issues": [
        {{
          "type": "问题类型(伏笔未回收/伏笔过于隐晦/伏笔过于明显)",
          "severity": "warning|critical|info",
          "description": "详细描述",
          "foreshadowing": "伏笔内容简述",
          "location": "伏笔所在位置"
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
            result = parse_llm_json_response(response_text, logger, "伏笔分析")

            for issue in result.get("issues", []):
                issues.append({
                    "id": f"GP-FORESHADOW-LLM-{len(issues)+1}",
                    "dimension": "global_plot_consistency",
                    "category": issue.get("type", "伏笔问题"),
                    "severity": issue.get("severity", "warning"),
                    "location": {
                        "description": issue.get("location", "")
                    },
                    "description": issue.get("description", ""),
                    "evidence": f"伏笔: {issue.get('foreshadowing', '未知')}",
                    "suggestion": "建议调整伏笔设置或增加回收描述",
                    "metadata": {
                        "analysis_method": "llm",
                        "foreshadowing": issue.get("foreshadowing"),
                        "issue_type": issue.get("type")
                    }
                })

        except Exception as e:
            logger.warning(f"[伏笔分析] LLM分析异常: {str(e)}")

        return issues

    def _count_foreshadowing_keywords(self, global_outline: str) -> int:
        """统计伏笔关键词总数"""
        content = global_outline.lower()
        keywords = [
            "伏笔", "暗藏", "隐藏", "秘密", "神秘", "悬念",
            "暗示", "预示", "预兆", "征兆"
        ]
        return sum(content.count(kw) for kw in keywords)

    def _calculate_consistency_score(self, issues: List[Dict]) -> float:
        """计算一致性得分"""
        score = 100.0

        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 20
            elif severity == "warning":
                score -= 8
            elif severity == "info":
                score -= 2

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
            logger.warning(f"[剧情线一致性分析] 应用反馈阈值失败: {str(e)}")
            return issues
