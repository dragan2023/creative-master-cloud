"""
质量修正生成器 - 使用LLM生成智能修正方案

功能:
1. 分析问题类型和位置
2. 结合全局大纲、人物设定、世界观生成修正内容
3. 确保修正内容与上下文逻辑自洽
4. 提供修正说明和置信度评估
5. v2.2新增：批量修正机制，一次性处理多个问题，显著提升效率
6. v2.3新增：AI视觉资源缺失检测与Seedance 2.0提示词规范检查

@date: 2026-04-14
@version: v2.3.0
"""
import json
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_manager import get_llm_manager
from app.core.logger import get_logger

logger = get_logger("quality_control.fix_generator")


# LLM修正提示词模板
QUALITY_FIX_PROMPT = """你是专业的创意写作编辑,擅长修正小说/剧本中的各种问题。

【问题描述】
{issue_description}

【问题类型】
{issue_category}

【原始内容】(第{chapter_number}单元)
{original_content}

【单元概述】（当前单元的原始规划，修正时应作为重要参考）
{unit_summary}

【知识图谱上下文】（项目中的实体状态、关系和剧情线索，修正时必须保持一致）
{knowledge_graph_context}

【人物设定】
{character_profiles}

【世界观设定】
{worldview_settings}

## 修正任务

请根据以上信息,生成修正后的内容。要求:

1. **逻辑自洽**: 修正内容必须与单元概述、知识图谱、人物设定、世界观保持一致
2. **上下文连贯**: 与前后单元自然衔接
3. **问题解决**: 彻底解决指出的问题
4. **保持风格**: 维持原有的文风和叙事风格
5. **尊重原文**: 只做必要的修改,不要重写整个内容
6. **AI视觉资源检查**（仅剧集/电影内容）：如内容为剧本类型，请检查是否包含人物参考图提示词、场景参考图提示词和Seedance 2.0视频生成提示词

## 重要原则

- **正向优化**: 修正是为了提升质量,不是重写。保留原文的核心情节、人物设定和精彩段落
- **适度修改**: 一般情况修改幅度建议不超过30%,但如遇情节重构等特殊情况可酌情突破限制
- **内容完整性**: 修正后的内容长度不应显著少于原文,避免大面积删减导致内容不完整
- **灵活处理**: 如果问题需要修改文本,请在fixed_content中返回修改后的完整内容;如果问题不需要修改文本(如逻辑性建议),请在fixed_content中返回原文,但在description中说明原因
- **保持创造性**: 不要过度保守,当问题确实需要较大修改时,应该大胆重构

## 输出格式

请严格按照以下JSON格式输出:

```json
{{
  "fixed_content": "修正后的完整内容(如果有修改)或原文(如果无需修改)",
  "description": "修正说明,详细解释做了什么修改或为什么不需要修改",
  "changes_made": ["修改点1", "修改点2"],
  "confidence": 0.95
}}
```

只输出JSON,不要其他内容。
"""


# 批量修正提示词模板（v2.2新增 - 一次性处理多个问题）
BATCH_QUALITY_FIX_PROMPT = """你是专业的创意写作编辑,擅长综合修正小说/剧本中的多个问题。

【待修正的问题列表】（共{issue_count}个问题）
{all_issues_list}

【原始内容】(第{chapter_number}单元)
{original_content}

【单元概述】（当前单元的原始规划，修正时应作为重要参考）
{unit_summary}

【知识图谱上下文】（项目中的实体状态、关系和剧情线索，修正时必须保持一致）
{knowledge_graph_context}

【人物设定】
{character_profiles}

【世界观设定】
{worldview_settings}

## 修正任务

请综合分析以上所有问题,生成一次性的修正内容。要求:

1. **整体视角**: 不要逐个问题单独修正,而是综合分析所有问题后整体优化
2. **辩证思考**: 问题之间可能存在关联,修正时需要考虑问题A的修正是否会影响问题B
3. **逻辑自洽**: 修正内容必须与单元概述、知识图谱、人物设定、世界观保持一致
4. **上下文连贯**: 与前后单元自然衔接
5. **彻底解决**: 确保所有列出的问题都得到解决
6. **保持风格**: 维持原有的文风和叙事风格
7. **尊重原文**: 只做必要的修改,不要重写整个内容
8. **AI视觉资源检查**（仅剧集/电影内容）：如内容为剧本类型，请检查是否包含人物/场景/物品参考图提示词和Seedance 2.0视频生成提示词

## 重要原则

- **正向优化**: 修正是为了提升质量,不是重写。保留原文的核心情节、人物设定和精彩段落
- **适度修改**: 一般情况修改幅度建议不超过30%,但如遇情节重构等特殊情况可酌情突破限制
- **内容完整性**: 修正后的内容长度不应显著少于原文,避免大面积删减导致内容不完整
- **灵活处理**: 如果某些问题不需要修改文本(如逻辑性建议),请在description中说明原因
- **保持创造性**: 不要过度保守,当问题确实需要较大修改时,应该大胆重构
- **避免冲突**: 如果问题之间存在冲突,请根据问题严重程度和上下文逻辑判断优先级

## 输出格式

请严格按照以下JSON格式输出:

```json
{{
  "fixed_content": "修正后的完整内容",
  "description": "综合修正说明,详细解释做了什么修改",
  "changes_made": ["修改点1", "修改点2", ...],
  "confidence": 0.90,
  "issues_addressed": ["issue_id1", "issue_id2", ...]
}}
```

只输出JSON,不要其他内容。
"""


class QualityFixGenerator:
    """质量修正生成器 - 使用LLM生成智能修正方案"""

    def __init__(self):
        self.llm_manager = get_llm_manager()

    async def generate_fix(
        self,
        issue: Dict,
        chapter_content: str,
        unit_summary: str = "",
        character_profiles: List[Dict] = None,
        worldview_settings: Dict = None,
        knowledge_graph_context: str = "",  # 知识图谱上下文
        db: AsyncSession = None,
        user_id: int = 0
    ) -> Dict:
        """
        生成智能修正方案

        Args:
            issue: 问题字典,包含category, description, location等
            chapter_content: 当前单元内容
            global_outline: 全局大纲
            character_profiles: 人物设定列表
            worldview_settings: 世界观设定
            db: 数据库会话
            user_id: 用户ID

        Returns:
            修正方案字典,包含:
            - original: 原始内容
            - fixed: 修正后内容
            - description: 修正说明
            - changes_made: 修改点列表
            - confidence: 置信度(0-1)
            - tokens_used: 消耗的token数
        """
        try:
            chapter_number = issue.get("location", {}).get("chapter_number", 0)
            category = issue.get("category", "未知问题")
            description = issue.get("description", "")

            logger.info(
                f"开始生成修正方案: issue={issue.get('id')}, "
                f"category={category}, chapter={chapter_number}"
            )

            # 构建人物设定文本
            character_text = self._format_character_profiles(
                character_profiles or [])

            # 构建世界观设定文本
            worldview_text = self._format_worldview_settings(
                worldview_settings or {})

            # 构建提示词（不再静默截断内容，LLM 上下文由模型自行处理）
            prompt = QUALITY_FIX_PROMPT.format(
                issue_description=description,
                issue_category=category,
                chapter_number=chapter_number,
                original_content=chapter_content,
                unit_summary=unit_summary if unit_summary else "无",
                knowledge_graph_context=knowledge_graph_context if knowledge_graph_context else "暂无知识图谱数据",
                character_profiles=character_text if character_text else "无",
                worldview_settings=worldview_text if worldview_text else "无"
            )

            # 获取用户的默认LLM provider
            if db and user_id:
                llm_provider = await self.llm_manager.get_provider_from_db(db, user_id)
            else:
                # 如果没有db或user_id，使用系统默认
                llm_provider = await self.llm_manager.get_system_provider("qianwen")

            # 调用LLM生成修正内容
            response = await llm_provider.generate(
                prompt=prompt,
                temperature=0.3,  # 较低温度确保稳定性
                max_tokens=30000  # v2.1: 统一设置为30000确保输出完整
            )

            # 解析LLM响应
            fix_result = self._parse_llm_response(
                response.content, chapter_content)

            # 添加原始内容和token消耗
            fix_result["original"] = chapter_content
            # LLMResponse.usage 是 Dict[str, int]，包含 prompt_tokens, completion_tokens, total_tokens
            usage = response.usage or {}
            fix_result["tokens_used"] = usage.get("total_tokens", 0)

            logger.info(
                f"修正方案生成成功: confidence={fix_result.get('confidence', 0):.2f}, "
                f"tokens={fix_result.get('tokens_used', 0)}"
            )

            return fix_result

        except Exception as e:
            logger.error(f"生成修正方案失败: {str(e)}", exc_info=True)
            # 返回降级方案
            return self._fallback_fix(issue, chapter_content, str(e))

    async def generate_batch_fix(
        self,
        issues: List[Dict],
        chapter_content: str,
        unit_summary: str = "",
        character_profiles: List[Dict] = None,
        worldview_settings: Dict = None,
        knowledge_graph_context: str = "",
        db: AsyncSession = None,
        user_id: int = 0
    ) -> Dict:
        """
        批量修正：一次性处理同一章节的多个问题（v2.2新增）

        Args:
            issues: 同一章节的所有问题列表
            chapter_content: 当前单元内容
            unit_summary: 单元概述
            character_profiles: 人物设定列表
            worldview_settings: 世界观设定
            knowledge_graph_context: 知识图谱上下文
            db: 数据库会话
            user_id: 用户ID

        Returns:
            批量修正方案字典,包含:
            - original: 原始内容
            - fixed: 修正后内容
            - description: 综合修正说明
            - changes_made: 修改点列表
            - confidence: 置信度(0-1)
            - issues_addressed: 已处理的问题ID列表
            - tokens_used: 消耗的token数
        """
        try:
            if not issues:
                logger.warning("批量修正：问题列表为空")
                return {
                    "fixed": chapter_content,
                    "description": "无需修正",
                    "changes_made": [],
                    "confidence": 1.0,
                    "issues_addressed": [],
                    "original": chapter_content,
                    "tokens_used": 0,
                    "type": "no_issues"
                }

            chapter_number = issues[0].get("location", {}).get("chapter_number", 0)
            issue_count = len(issues)

            logger.info(
                f"开始批量修正: chapter={chapter_number}, "
                f"issue_count={issue_count}"
            )

            # 构建问题列表文本
            all_issues_list = self._format_issues_list(issues)

            # 构建人物设定文本
            character_text = self._format_character_profiles(
                character_profiles or [])

            # 构建世界观设定文本
            worldview_text = self._format_worldview_settings(
                worldview_settings or {})

            # 构建批量修正提示词
            prompt = BATCH_QUALITY_FIX_PROMPT.format(
                issue_count=issue_count,
                all_issues_list=all_issues_list,
                chapter_number=chapter_number,
                original_content=chapter_content,
                unit_summary=unit_summary if unit_summary else "无",
                knowledge_graph_context=knowledge_graph_context if knowledge_graph_context else "暂无知识图谱数据",
                character_profiles=character_text if character_text else "无",
                worldview_settings=worldview_text if worldview_text else "无"
            )

            # 获取用户的默认LLM provider
            if db and user_id:
                llm_provider = await self.llm_manager.get_provider_from_db(db, user_id)
            else:
                llm_provider = await self.llm_manager.get_system_provider("qianwen")

            # 调用LLM生成批量修正内容
            response = await llm_provider.generate(
                prompt=prompt,
                temperature=0.3,  # 较低温度确保稳定性
                max_tokens=30000
            )

            # 解析LLM响应
            fix_result = self._parse_batch_llm_response(
                response.content, chapter_content, issues)

            # 添加原始内容和token消耗
            fix_result["original"] = chapter_content
            usage = response.usage or {}
            fix_result["tokens_used"] = usage.get("total_tokens", 0)

            logger.info(
                f"批量修正方案生成成功: issues_addressed={len(fix_result.get('issues_addressed', []))}, "
                f"confidence={fix_result.get('confidence', 0):.2f}, "
                f"tokens={fix_result.get('tokens_used', 0)}"
            )

            return fix_result

        except Exception as e:
            logger.error(f"批量修正失败: {str(e)}", exc_info=True)
            # 降级为逐个修正
            return await self._fallback_batch_fix(issues, chapter_content, str(e), db, user_id)

    def _format_character_profiles(self, profiles: List[Dict]) -> str:
        """格式化人物设定为文本"""
        if not profiles:
            return ""

        lines = []
        for profile in profiles:
            name = profile.get("name", "未知人物")
            lines.append(f"人物: {name}")

            # 添加关键属性
            for key in ["personality", "role", "background", "goals"]:
                if key in profile and profile[key]:
                    key_name = {
                        "personality": "性格",
                        "role": "角色",
                        "background": "背景",
                        "goals": "目标"
                    }.get(key, key)
                    lines.append(f"  {key_name}: {profile[key]}")

            lines.append("")

        return "\n".join(lines)

    def _format_issues_list(self, issues: List[Dict]) -> str:
        """格式化问题列表为文本（v2.2新增）"""
        if not issues:
            return "无问题"

        lines = []
        for idx, issue in enumerate(issues, 1):
            issue_id = issue.get("id", f"issue_{idx}")
            category = issue.get("category", "未知类型")
            severity = issue.get("severity", "未知严重程度")
            description = issue.get("description", "无描述")
            suggestion = issue.get("suggestion", "")

            lines.append(f"问题{idx} [{issue_id}]")
            lines.append(f"  类型: {category}")
            lines.append(f"  严重程度: {severity}")
            lines.append(f"  描述: {description}")
            if suggestion:
                lines.append(f"  建议: {suggestion}")
            lines.append("")

        return "\n".join(lines)

    def _parse_batch_llm_response(self, content: str, original_content: str, issues: List[Dict]) -> Dict:
        """解析批量修正LLM响应（v2.2新增）"""
        try:
            # 尝试提取JSON
            json_start = content.find("```json")
            if json_start != -1:
                json_start = content.find("{", json_start)
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            else:
                json_str = content

            # 解析JSON
            data = json.loads(json_str)

            # 验证必要字段
            if "fixed_content" not in data:
                raise ValueError("缺少fixed_content字段")

            return {
                "fixed": data.get("fixed_content", original_content),
                "description": data.get("description", "已根据问题描述生成修正内容"),
                "changes_made": data.get("changes_made", []),
                "confidence": min(max(float(data.get("confidence", 0.7)), 0.0), 1.0),
                "issues_addressed": data.get("issues_addressed", [issue.get("id") for issue in issues]),
                "type": "batch_llm_generated"
            }

        except json.JSONDecodeError as e:
            logger.warning(f"批量修正LLM响应JSON解析失败: {str(e)}")
            # 尝试从内容中提取
            return self._extract_fix_from_text(content, original_content)
        except Exception as e:
            logger.error(f"解析批量修正LLM响应失败: {str(e)}")
            raise

    async def _fallback_batch_fix(
        self,
        issues: List[Dict],
        chapter_content: str,
        error: str,
        db: AsyncSession = None,
        user_id: int = 0
    ) -> Dict:
        """批量修正降级方案：逐个修正（v2.2新增）"""
        logger.warning(f"批量修正失败，降级为逐个修正: {error}")

        # 尝试逐个修正第一个问题
        if issues:
            first_issue = issues[0]
            fallback_result = await self.generate_fix(
                issue=first_issue,
                chapter_content=chapter_content,
                db=db,
                user_id=user_id
            )
            fallback_result["issues_addressed"] = [first_issue.get("id")]
            fallback_result["type"] = "fallback_single"
            return fallback_result

        # 如果连逐个修正都失败，返回原文
        return {
            "fixed": chapter_content,
            "description": f"批量修正和逐个修正均失败({error}),保持原内容",
            "changes_made": [],
            "confidence": 0.0,
            "issues_addressed": [],
            "original": chapter_content,
            "tokens_used": 0,
            "type": "fallback_failed"
        }

    def _format_worldview_settings(self, settings: Dict) -> str:
        """格式化世界观设定为文本"""
        if not settings:
            return ""

        lines = []
        for key, value in settings.items():
            key_name = {
                "time_period": "时代背景",
                "location": "地点设定",
                "rules": "世界规则",
                "magic_system": "魔法体系",
                "technology": "科技水平",
                "social_structure": "社会结构"
            }.get(key, key)

            if isinstance(value, str):
                lines.append(f"{key_name}: {value}")
            elif isinstance(value, list):
                lines.append(f"{key_name}:")
                for item in value:
                    lines.append(f"  - {item}")
            lines.append("")

        return "\n".join(lines)

    def _parse_llm_response(self, content: str, original_content: str) -> Dict:
        """解析LLM响应,提取修正方案"""
        try:
            # 尝试提取JSON
            json_start = content.find("```json")
            if json_start != -1:
                json_start = content.find("{", json_start)
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            else:
                # 直接尝试解析整个内容
                json_str = content

            # 解析JSON
            data = json.loads(json_str)

            # 验证必要字段
            if "fixed_content" not in data:
                raise ValueError("缺少fixed_content字段")

            return {
                "fixed": data.get("fixed_content", original_content),
                "description": data.get("description", "已根据问题描述生成修正内容"),
                "changes_made": data.get("changes_made", []),
                "confidence": min(max(float(data.get("confidence", 0.7)), 0.0), 1.0),
                "type": "llm_generated"
            }

        except json.JSONDecodeError as e:
            logger.warning(f"LLM响应JSON解析失败: {str(e)}")
            # 尝试从内容中提取
            return self._extract_fix_from_text(content, original_content)
        except Exception as e:
            logger.error(f"解析LLM响应失败: {str(e)}")
            raise

    def _extract_fix_from_text(self, text: str, original_content: str) -> Dict:
        """从文本中提取修正内容(降级方案)"""
        # 如果文本包含"修正后的内容"等关键词,尝试提取
        keywords = ["修正后的内容", "修正后内容", "fixed_content", "修正内容"]

        for keyword in keywords:
            pos = text.find(keyword)
            if pos != -1:
                # 提取关键词后的内容
                fixed_content = text[pos + len(keyword):].strip()
                # 移除可能的冒号
                if fixed_content.startswith(":") or fixed_content.startswith("："):
                    fixed_content = fixed_content[1:].strip()

                if len(fixed_content) > 50:  # 确保内容有意义
                    return {
                        "fixed": fixed_content,  # 不再截断修正内容
                        "description": "从LLM响应中提取的修正内容",
                        "changes_made": [],
                        "confidence": 0.6,
                        "type": "extracted"
                    }

        # 无法提取,返回原始内容
        return {
            "fixed": original_content,
            "description": "LLM生成失败,保持原内容",
            "changes_made": [],
            "confidence": 0.0,
            "type": "fallback"
        }

    def _fallback_fix(self, issue: Dict, chapter_content: str, error: str) -> Dict:
        """降级修正方案(LLM失败时使用)

        v2.3: 新增 AI视觉资源缺失 和 Seedance提示词格式 两种降级修正类型
        """
        category = issue.get("category", "")

        # 根据问题类型提供简单的修正建议
        fallback_suggestions = {
            "单元衔接": {
                "fixed": chapter_content + "\n\n然而,这仅仅是开始,更大的挑战还在后面...",
                "description": "添加了过渡句以增强单元衔接",
                "confidence": 0.5
            },
            "节奏平淡": {
                "fixed": chapter_content.replace("。", "。突然,", 1) if "。" in chapter_content else chapter_content,
                "description": "在开头添加了突发事件以增强节奏",
                "confidence": 0.4
            },
            "单元过短": {
                "fixed": chapter_content + "\n\n这个决定带来了深远的影响,故事的走向从此改变。",
                "description": "补充了情节发展以丰富单元内容",
                "confidence": 0.5
            },
            "AI视觉资源缺失": {
                "fixed": chapter_content,
                "description": "检测到剧集/电影内容可能缺少AI视觉资源（参考图提示词、Seedance 2.0视频提示词），建议在后续版本中补充图像参考资源和Seedance 2.0全能参考模式的视频生成提示词",
                "confidence": 0.3
            },
            "Seedance提示词格式": {
                "fixed": chapter_content,
                "description": "检测到Seedance 2.0视频生成提示词格式可能不符合全能参考模式规范，建议检查是否包含[参考模式]、[人物参考图]、[场景参考图]、[物品参考图]等必要字段",
                "confidence": 0.3
            },
        }

        fallback = fallback_suggestions.get(category, {
            "fixed": chapter_content,
            "description": f"LLM生成失败({error}),建议手动修改",
            "confidence": 0.0
        })

        fallback.update({
            "original": chapter_content,
            "changes_made": [],
            "tokens_used": 0,
            "type": "fallback"
        })

        return fallback
