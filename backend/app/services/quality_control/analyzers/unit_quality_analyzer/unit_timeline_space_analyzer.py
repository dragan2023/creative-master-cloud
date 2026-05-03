"""单元概述质量分析器 - UnitTimelineSpaceAnalyzer"""
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
