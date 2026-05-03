"""单元概述质量分析器 - CharacterStateChangeAnalyzer"""
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
from .unit_structure_analyzer import UnitStructureAnalyzer

logger = get_logger(__name__)


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
