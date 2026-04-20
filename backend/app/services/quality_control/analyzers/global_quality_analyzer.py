"""
全局大纲专用质量管控分析器 v1.1

专门针对全局大纲的特点设计,与单元概述质控模块完全独立。

全局大纲特点:
- 长度较长(建议5000-30000字，确保LLM能够完整输出)
- 宏观性质(整体结构设计)
- 强调结构完整性、设定合理性、逻辑自洽

四维度检测机制:
1. global_structure(宏观结构层) - 检测大纲整体结构、章节分布、故事弧线
2. global_character_worldview(人物与世界观层) - 检测人物设定、世界观规则一致性
3. global_plot_consistency(剧情线一致性层) - 检测主线剧情逻辑、伏笔设置
4. global_storyline_integrity(故事线完整性) - 检测起承转合、高潮分布、结局合理性

v1.0 防错设计:
- LLM超时配置: 1200秒(20分钟)
- JSON解析保护: 正则提取 + try-catch + 降级处理
- Response安全访问: hasattr检查 + 可选链模式

v1.1 优化 (2026-04-15):
- 并行调用: 使用asyncio.gather并行执行四维度分析,加速3-4倍
- 伏笔检测: 新增伏笔回收检测(规则版+LLM版)
- 反馈学习增强: 时间衰减权重、自适应严重程度、用户偏好分析

@date: 2026-04-15
@version: v1.1.0
@author: 周金磊
"""
from typing import Dict, List, Any, Optional
import asyncio
from app.core.logger import get_logger

logger = get_logger("quality_control.analyzers.global_quality")


def clean_json_string(json_str: str) -> str:
    """
    清理和修复LLM返回的JSON字符串

    处理常见问题:
    1. 移除markdown代码块标记
    2. 替换中文引号为英文引号
    3. 处理截断的JSON(移除最后一个不完整的字段)
    4. 修复常见的JSON格式错误

    Args:
        json_str: 原始JSON字符串

    Returns:
        清理后的JSON字符串
    """
    import re

    # 1. 移除markdown代码块标记
    json_str = re.sub(r'^```json\s*', '', json_str, flags=re.MULTILINE)
    json_str = re.sub(r'\s*```$', '', json_str, flags=re.MULTILINE)
    json_str = json_str.strip()

    # 2. 替换中文引号（避免干扰JSON结构）
    # 将中文双引号替换为书名号（避免与JSON字符串边界冲突）
    json_str = json_str.replace('\u201c', '\u300c').replace('\u201d', '\u300d')
    # 将中文单引号替换为书名号
    json_str = json_str.replace('\u2018', '\u300e').replace('\u2019', '\u300f')

    # 3. 处理截断的JSON - 移除最后一个不完整的字段
    # 查找最后一个完整的逗号位置
    last_comma = json_str.rfind(',')
    last_colon = json_str.rfind(':')

    # 如果最后一个冒号在最后一个逗号之后，说明最后一个字段不完整
    if last_colon > last_comma:
        # 找到最后一个逗号，截断后面的内容
        json_str = json_str[:last_comma] + '\n  }'

    # 4. 确保JSON以大括号结尾
    json_str = json_str.rstrip()
    if not json_str.endswith('}'):
        json_str = json_str.rstrip(',') + '\n}'

    # 5. 修复转义字符问题
    # 移除无效的转义序列
    json_str = re.sub(r'\\([^"\\/bfnrtu])', r'\1', json_str)

    return json_str


def parse_llm_json_response(response_text: str, logger, context: str = "") -> Dict:
    """
    解析LLM返回的JSON响应（带三级修复机制）

    Args:
        response_text: LLM响应文本
        logger: 日志对象
        context: 上下文标识（用于日志）

    Returns:
        解析后的字典，如果解析失败返回{"issues": []}
    """
    import re
    import json

    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
    if not json_match:
        logger.warning(
            f"[{context}] 未找到JSON代码块, "
            f"响应前500字: {response_text[:500]}"
        )
        return {"issues": []}

    json_str = json_match.group(1)

    # 第一次尝试：直接解析
    try:
        result = json.loads(json_str)
        return result
    except json.JSONDecodeError as e1:
        # 第二次尝试：清理后解析
        logger.info(f"[{context}] 首次JSON解析失败，尝试清理修复: {e1}")
        json_str = clean_json_string(json_str)

        try:
            result = json.loads(json_str)
            logger.info(f"[{context}] JSON清理修复成功")
            return result
        except json.JSONDecodeError as e2:
            # 第三次尝试：移除最后一个不完整对象后解析
            logger.warning(f"[{context}] 清理后仍失败，尝试移除不完整字段: {e2}")

            # 找到最后一个完整的issue对象
            last_complete_brace = json_str.rfind('}')
            if last_complete_brace > 0:
                # 截断到最后一个完整的对象
                json_str = json_str[:last_complete_brace + 1]
                # 确保issues数组闭合
                if ']' not in json_str[last_complete_brace:]:
                    json_str = json_str.rstrip('}') + ']}'

                try:
                    result = json.loads(json_str)
                    logger.info(f"[{context}] 移除不完整字段后解析成功")
                    return result
                except json.JSONDecodeError as e3:
                    logger.warning(
                        f"[{context}] 所有修复尝试均失败: {e3}, "
                        f"响应前500字: {response_text[:500]}"
                    )
                    return {"issues": []}
            else:
                logger.warning(
                    f"[{context}] JSON结构严重损坏，无法修复: {e2}"
                )
                return {"issues": []}


async def call_llm_with_retry(llm_provider, prompt: str, temperature: float = 0.3,
                              timeout: int = 1200, max_retries: int = 3,
                              retry_delay: int = 5, context: str = "") -> Any:
    """
    带重试机制的LLM调用辅助函数

    Args:
        llm_provider: LLM提供者实例
        prompt: 提示词
        temperature: 温度参数
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
        retry_delay: 初始重试延迟(秒)
        context: 上下文标识(用于日志)

    Returns:
        LLM响应对象

    Raises:
        Exception: 非429错误或重试耗尽后的错误
    """
    response = None
    for attempt in range(max_retries):
        try:
            response = await llm_provider.generate(
                prompt=prompt,
                temperature=temperature,
                timeout=timeout
            )
            return response  # 成功则返回
        except Exception as e:
            error_str = str(e)
            if '429' in error_str or 'TooManyRequests' in error_str or 'ServerOverloaded' in error_str:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * \
                        (2 ** attempt)  # 指数退避: 5s, 10s, 20s
                    logger.warning(
                        f"[{context}] LLM返回429错误,第{attempt+1}次重试,"
                        f"等待{wait_time}秒..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"[{context}] LLM 429错误,已重试{max_retries}次,放弃")
                    raise  # 重试耗尽,抛出错误
            else:
                raise  # 其他错误直接抛出

    return response


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
            outline_sample = global_outline[:15000]

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


class GlobalCharacterWorldviewAnalyzer:
    """人物与世界观分析器 - 检测人物设定和世界观规则一致性"""

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
        """执行人物与世界观分析(v1.0防错版)"""
        issues = []

        # 1. 人物状态矛盾检测
        contradiction_issues = self._analyze_character_contradictions(
            global_outline)
        issues.extend(contradiction_issues)

        # 2. 人物设定完整性检测
        if character_profiles:
            completeness_issues = self._analyze_character_completeness(
                global_outline, character_profiles
            )
            issues.extend(completeness_issues)

        # 3. 世界观规则一致性检测
        if worldview_settings:
            worldview_issues = self._analyze_worldview_consistency(
                global_outline, worldview_settings
            )
            issues.extend(worldview_issues)

        # 4. LLM深度分析人物关系合理性
        if depth in ["standard", "deep"]:
            llm_issues = await self._analyze_character_relations_with_llm(
                global_outline, depth, db, user_id
            )
            if isinstance(llm_issues, list):
                issues.extend(llm_issues)

        # 5. 应用用户反馈学习的阈值调整
        issues = self._apply_feedback_thresholds(user_id, issues)

        # 计算得分
        score = self._calculate_character_score(issues)

        return {
            "score": score,
            "issues": issues,
            "tokens": 0,
            "metadata": {
                "character_count": len(character_profiles) if character_profiles else 0,
                "analysis_depth": depth
            }
        }

    def _analyze_character_contradictions(self, global_outline: str) -> List[Dict]:
        """分析人物状态矛盾(复用单元概述的矛盾词对检测)"""
        issues = []
        content = global_outline.lower()

        contradictory_states = [
            ("生", "死"),
            ("活着", "死亡"),
            ("存活", "死去"),
            ("胜利", "失败"),
            ("成功", "失败"),
            ("安全", "危险")
        ]

        exclude_phrases = [
            "生死关头", "生死存亡", "生死搏", "生死战", "决一死战",
            "胜利失败", "成败", "成败得失",
            "安全危险", "安危",
            "复活", "重生", "重生后", "复活后"
        ]

        for state1, state2 in contradictory_states:
            if state1 in content and state2 in content:
                is_false_positive = any(
                    phrase in content for phrase in exclude_phrases
                )

                if is_false_positive:
                    continue

                has_transition = any(
                    word in content
                    for word in ["但是", "然而", "却", "没想到", "意外",
                                 "复活", "重生", "醒来", "恢复", "转变"]
                )

                if not has_transition:
                    issues.append({
                        "id": f"GC-CONTRADICTION-{len(issues)+1}",
                        "dimension": "global_character_worldview",
                        "category": "状态矛盾",
                        "severity": "warning",
                        "location": {},
                        "description": f"全局大纲中同时出现'{state1}'和'{state2}'的状态描述,可能存在逻辑矛盾",
                        "evidence": f"矛盾词对: {state1}/{state2}",
                        "suggestion": "请检查是否存在状态转换的合理铺垫,或修正矛盾描述",
                        "metadata": {"contradictory_states": [state1, state2]}
                    })

        return issues

    def _analyze_character_completeness(
        self,
        global_outline: str,
        character_profiles: List[Dict]
    ) -> List[Dict]:
        """分析人物设定完整性"""
        issues = []

        for char in character_profiles[:10]:  # 最多检测10个主要人物
            char_name = char.get("name", "")
            if not char_name:
                continue

            # 检查人物是否在大网中有详细描述
            char_mentions = global_outline.count(char_name)

            if char_mentions == 0:
                issues.append({
                    "id": f"GC-MISSING-{char_name}",
                    "dimension": "global_character_worldview",
                    "category": "人物缺失",
                    "severity": "warning",
                    "location": {},
                    "description": f"主要人物'{char_name}'在全局大纲中未被提及",
                    "evidence": f"人物设定中存在,但大纲中未出现",
                    "suggestion": "建议在大网中补充该人物的背景、目标和作用",
                    "metadata": {"character_name": char_name}
                })

        return issues

    def _analyze_worldview_consistency(
        self,
        global_outline: str,
        worldview_settings: Dict
    ) -> List[Dict]:
        """分析世界观规则一致性"""
        issues = []

        # 简单检测: 检查世界观中的关键规则是否在大网中被遵循
        rules = worldview_settings.get("rules", [])
        for rule in rules[:5]:  # 最多检测5条规则
            rule_text = rule.get("description", "")
            if not rule_text:
                continue

            # 检查是否有明显的规则冲突(简化版)
            if "禁止" in rule_text or "不允许" in rule_text:
                # 检测大纲中是否有违反描述
                pass  # 需要更复杂的NLP分析,暂时跳过

        return issues

    async def _analyze_character_relations_with_llm(
        self,
        global_outline: str,
        depth: str,
        db,
        user_id: int
    ) -> List[Dict]:
        """使用LLM深度分析人物关系合理性(防错版: 超时1200秒)"""
        issues = []

        try:
            logger.info("[人物与世界观分析] 开始LLM人物关系分析...")
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(db, user_id)

            if not llm_provider:
                logger.warning("[人物与世界观分析] 无法获取LLM提供者,跳过深度分析")
                return issues

            logger.info("[人物与世界观分析] 成功获取LLM提供者，开始调用...")

            outline_sample = global_outline[:15000]

            prompt = f"""你是专业的人物关系分析师。

请分析以下全局大纲中的人物设定和关系:

【全局大纲内容】(前15000字)
{outline_sample}

【分析要求】
1. 检测主要人物是否有明确的动机和目标
2. 评估人物关系是否合理(是否存在突兀的转变)
3. 检测人物性格是否前后一致
4. 评估世界观规则是否自洽

【输出格式】
```json
{{
  "issues": [
    {{
      "type": "问题类型",
      "severity": "warning|critical|info",
      "description": "详细描述",
      "character": "涉及的人物名称"
    }}
  ]
}}
```

如果没有问题,返回空数组。
"""

            # ✅ 使用带重试机制的LLM调用
            response = await call_llm_with_retry(
                llm_provider,
                prompt=prompt,
                temperature=0.3,
                timeout=1200,
                context="人物与世界观分析"
            )

            response_text = response.content if hasattr(
                response, 'content') else str(response)

            # ✅ 使用统一的JSON解析函数（带三级修复机制）
            result = parse_llm_json_response(response_text, logger, "人物与世界观分析")

            for issue in result.get("issues", []):
                issues.append({
                    "id": f"GC-REL-{len(issues)+1}",
                    "dimension": "global_character_worldview",
                    "category": issue.get("type", "人物关系问题"),
                    "severity": issue.get("severity", "warning"),
                    "location": {},
                    "description": issue.get("description", ""),
                    "evidence": f"涉及人物: {issue.get('character', '未知')}",
                    "suggestion": "建议修正人物设定或关系描述",
                    "metadata": {
                        "analysis_method": "llm",
                        "character": issue.get("character")
                    }
                })

        except Exception as e:
            logger.warning(f"[人物与世界观分析] LLM分析异常: {str(e)}")

        return issues

    def _calculate_character_score(self, issues: List[Dict]) -> float:
        """计算人物与世界观得分"""
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
        """应用用户反馈学习的阈值调整(同GlobalStructureAnalyzer)"""
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
            logger.warning(f"[人物与世界观分析] 应用反馈阈值失败: {str(e)}")
            return issues


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

            outline_sample = global_outline[:15000]

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

            outline_sample = global_outline[:15000]

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
            logger.warning(f"[剧情线一致性分析] 应用反馈阈值失败: {str(e)}")
            return issues


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
            logger.warning(f"[故事线完整性分析] 应用反馈阈值失败: {str(e)}")
            return issues
