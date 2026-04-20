"""
多Agent协作文学作品生成系统 - 风格润色Agent

模块: agents.writing
文件: style_editor_agent.py
功能: 对内容进行文学风格润色和优化，支持文风文档分析和AI文风消除

依赖关系:
    - 依赖: app.agents.writing.base_agent, app.agents.writing.agent_config
    - 依赖: app.agents.writing.prompts.style_prompts
    - 被依赖: 总线Agent、合规审查Agent

创建时间: 2026-03-27
最后修改: 2026-04-01
版本: 2.0.0

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）

更新日志:
    - v2.0.0 (2026-04-01): 新增文风文档分析和AI文风消除功能
      - 支持上传文风文档进行风格特征提取
      - 实现AI生成文本特征检测与消除
      - 提供实时风格指导功能
"""
import json
import re
from typing import Any, Dict, List, Optional

from app.agents.writing.base_agent import BaseWritingAgent, AgentRole, AgentContext, AgentResult
from app.agents.writing.prompts.style_prompts import STYLE_PROMPTS
from app.utils.json_parser import parse_json, RobustJSONParser


class StyleEditorAgent(BaseWritingAgent):
    """风格润色Agent

    负责对内容进行文学风格润色，包括：
    - 提升文学性和可读性
    - 修正逻辑编辑发现的问题
    - 优化对话自然度
    - 增强场景描写的画面感
    - 保持原文核心情节不变
    - 遵循风格指南
    - 文风文档分析与特征提取（新增）
    - AI文风检测与消除（新增）
    - 实时风格指导（新增）

    Attributes:
        agent_name: Agent名称
        agent_role: Agent角色类型
        default_model: 默认使用模型
        default_temperature: 默认温度参数
        enable_ai_detection: 是否启用AI文风检测
        enable_humanization: 是否启用人性化改写
    """

    agent_name = "风格润色Agent"
    agent_role = AgentRole.STYLE_EDITOR
    default_model = ""
    default_temperature = 0.6

    ENABLE_AI_DETECTION_DEFAULT = True
    ENABLE_HUMANIZATION_DEFAULT = True
    AI_SCORE_THRESHOLD_DEFAULT = 50

    def __init__(
        self,
        config=None,
        enable_ai_detection: bool = None,
        enable_humanization: bool = None,
        humanization_threshold: int = None
    ):
        """初始化风格润色Agent

        Args:
            config: Agent配置对象
            enable_ai_detection: 是否启用AI文风检测，默认True
            enable_humanization: 是否启用人性化改写，默认True
            humanization_threshold: 人性化改写阈值(0-100)，AI评分>=此值时触发改写
                                   值越低，触发改写的条件越宽松（更频繁）
                                   值越高，触发改写的条件越严格（更少触发）
        """
        super().__init__(config)
        self.enable_ai_detection = enable_ai_detection if enable_ai_detection is not None else self.ENABLE_AI_DETECTION_DEFAULT
        self.enable_humanization = enable_humanization if enable_humanization is not None else self.ENABLE_HUMANIZATION_DEFAULT
        self.humanization_threshold = humanization_threshold if humanization_threshold is not None else self.AI_SCORE_THRESHOLD_DEFAULT

    async def execute(self, context: AgentContext) -> AgentResult:
        """对内容进行风格润色

        从上下文中获取待润色内容、风格指南和逻辑问题，
        使用LLM进行风格优化并返回润色后的内容。
        新增：AI文风检测与人性化改写功能。

        Args:
            context: Agent执行上下文

        Returns:
            AgentResult: 包含以下字段:
                - content: 润色后的完整内容
                - data.changes_summary: 修改摘要
                - data.word_count: 字数统计
                - data.ai_score: AI痕迹评分（如启用检测）
                - data.humanization_applied: 是否应用了人性化改写
        """
        start_time = self._get_timestamp()

        try:
            draft_content = context.extra.get("draft_content", "")
            if not draft_content:
                return self._build_error_result(
                    "缺少待润色内容",
                    error_type="missing_content"
                )

            style_guide = context.style_guide or {}
            logic_issues = context.extra.get("logic_issues", [])
            character_profiles = context.character_profiles or []
            style_document_features = context.extra.get(
                "style_document_features", "")

            # 新增：获取文风知识库风格指南
            style_library_guide = style_guide.get("style_library_guide", {})

            current_content = draft_content
            ai_detection_result = None
            humanization_result = None

            if self.enable_ai_detection:
                self.logger.info(f"开始AI文风检测 - Task: {context.task_id}")
                ai_detection_result = await self._detect_ai_writing(
                    content=current_content,
                    context=context
                )

                if ai_detection_result:
                    ai_score = ai_detection_result.get("ai_score", 0)
                    self.logger.info(
                        f"AI文风检测完成 - Task: {context.task_id}, "
                        f"AI Score: {ai_score}"
                    )

                    if self.enable_humanization and ai_score >= self.humanization_threshold:
                        self.logger.info(f"开始人性化改写 - Task: {context.task_id}")
                        humanization_result = await self._humanize_content(
                            content=current_content,
                            detected_issues=ai_detection_result.get(
                                "detected_issues", []),
                            style_guide=style_guide,
                            context=context
                        )

                        if humanization_result:
                            current_content = humanization_result.get(
                                "humanized_content", current_content)
                            self.logger.info(
                                f"人性化改写完成 - Task: {context.task_id}, "
                                f"AI Score: {ai_score} -> {humanization_result.get('ai_score_after', ai_score)}"
                            )

            # 优先使用文风知识库进行风格润色（新增）
            if style_library_guide:
                system_prompt, user_prompt = self._build_style_library_polish_prompt(
                    content=current_content,
                    style_library_guide=style_library_guide,
                    logic_issues=logic_issues,
                    character_profiles=character_profiles
                )
            else:
                # 使用原有风格润色逻辑
                system_prompt = STYLE_PROMPTS["system"]
                user_prompt = STYLE_PROMPTS["polish_content"].format(
                    draft_content=current_content,
                    style_guide=self._format_style_guide(
                        style_guide, style_document_features),
                    logic_issues=self._format_logic_issues(logic_issues),
                    character_profiles=self._format_character_profiles(
                        character_profiles)
                )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(
                    context.scene_index) if context.scene_index else None
            )

            try:
                result_data = self._parse_llm_response(llm_result["content"])
            except Exception as e:
                self.logger.error(f"LLM返回结果解析失败: {e}")
                result_data = {
                    "polished_content": llm_result["content"],
                    "changes_summary": "直接返回润色内容",
                    "word_count": len(llm_result["content"])
                }

            duration_ms = self._get_timestamp() - start_time

            polished_content = result_data.get(
                "polished_content", llm_result["content"])
            changes_summary = result_data.get("changes_summary", "")
            word_count = result_data.get("word_count", len(polished_content))

            result_data_out = {
                "changes_summary": changes_summary,
                "word_count": word_count,
                "original_length": len(draft_content),
                "humanization_applied": humanization_result is not None
            }

            if ai_detection_result:
                result_data_out["ai_score_before"] = ai_detection_result.get(
                    "ai_score", 0)
                result_data_out["ai_issues_detected"] = len(
                    ai_detection_result.get("detected_issues", []))

            if humanization_result:
                result_data_out["ai_score_after"] = humanization_result.get(
                    "ai_score_after", 0)
                result_data_out["humanization_transformations"] = len(
                    humanization_result.get("transformations", []))

            self.logger.info(
                f"风格润色完成 - Task: {context.task_id}, "
                f"Original: {len(draft_content)} chars, Polished: {word_count} chars, "
                f"Humanization: {humanization_result is not None}"
            )

            return self._build_success_result(
                content=polished_content,
                token_usage={
                    "input_tokens": llm_result.get("input_tokens", 0),
                    "output_tokens": llm_result.get("output_tokens", 0),
                    "total_tokens": llm_result.get("total_tokens", 0)
                },
                duration_ms=duration_ms,
                model_id=llm_result.get("model", ""),
                **result_data_out
            )

        except Exception as e:
            self.logger.error(f"风格润色执行失败: {e}")
            return self._build_error_result(str(e))

    async def analyze_style_document(
        self,
        style_document: str,
        context: AgentContext
    ) -> Optional[Dict[str, Any]]:
        """分析文风文档，提取风格特征

        Args:
            style_document: 文风参考文档内容
            context: Agent上下文

        Returns:
            风格特征字典，包含style_profile、style_guide_for_writing等
        """
        try:
            analysis_prompt = STYLE_PROMPTS["analyze_style_document"].format(
                style_document=style_document
            )

            messages = [{"role": "user", "content": analysis_prompt}]

            self.logger.info(f"文风文档分析开始 - Task: {context.task_id}")

            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(
                    context.scene_index) if context.scene_index else None
            )

            if not llm_result:
                self.logger.error(f"文风文档分析LLM返回结果为空 - Task: {context.task_id}")
                return None

            result = self._parse_style_analysis_response(
                llm_result.get("content", ""))

            if result:
                self.logger.info(
                    f"文风文档分析完成 - Task: {context.task_id}, "
                    f"Style: {result.get('style_profile', {}).get('name', 'Unknown')}"
                )

            return result

        except Exception as e:
            self.logger.error(f"文风文档分析失败: {e}")
            return None

    async def get_real_time_style_guide(
        self,
        content_type: str,
        scene_title: str,
        target_words: int,
        project_style_params: Dict[str, Any],
        style_document_features: str,
        context: AgentContext
    ) -> Optional[Dict[str, Any]]:
        """获取实时风格指导

        为写手Agent提供写作过程中的实时风格指导。

        Args:
            content_type: 内容类型（novel/script）
            scene_title: 场景/章节标题
            target_words: 目标字数
            project_style_params: 项目风格参数
            style_document_features: 文风文档特征（如有）
            context: Agent上下文

        Returns:
            风格指导字典
        """
        try:
            guide_prompt = STYLE_PROMPTS["real_time_style_guide"].format(
                content_type=content_type,
                scene_title=scene_title,
                target_words=target_words,
                project_style_params=self._format_style_guide(
                    project_style_params),
                style_document_features=style_document_features or "未上传文风文档"
            )

            messages = [{"role": "user", "content": guide_prompt}]

            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(
                    context.scene_index) if context.scene_index else None
            )

            if not llm_result:
                return None

            return self._parse_llm_response(llm_result.get("content", ""))

        except Exception as e:
            self.logger.error(f"获取实时风格指导失败: {e}")
            return None

    async def _detect_ai_writing(
        self,
        content: str,
        context: AgentContext
    ) -> Optional[Dict[str, Any]]:
        """检测AI写作特征

        Args:
            content: 待检测内容
            context: Agent上下文

        Returns:
            检测结果字典，包含ai_score、detected_issues等
        """
        try:
            detection_prompt = STYLE_PROMPTS["detect_ai_writing"].format(
                content=content
            )

            messages = [{"role": "user", "content": detection_prompt}]

            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(
                    context.scene_index) if context.scene_index else None
            )

            if not llm_result:
                return None

            return self._parse_llm_response(llm_result.get("content", ""))

        except Exception as e:
            self.logger.error(f"AI文风检测失败: {e}")
            return None

    async def _humanize_content(
        self,
        content: str,
        detected_issues: List[Dict],
        style_guide: Dict,
        context: AgentContext
    ) -> Optional[Dict[str, Any]]:
        """人性化改写内容

        Args:
            content: 原始内容
            detected_issues: 检测到的AI写作问题
            style_guide: 风格指南
            context: Agent上下文

        Returns:
            改写结果字典，包含humanized_content、transformations等
        """
        try:
            issues_text = self._format_ai_issues(detected_issues)

            humanization_prompt = STYLE_PROMPTS["eliminate_ai_style"].format(
                detected_issues=issues_text,
                original_content=content,
                style_guide=self._format_style_guide(style_guide)
            )

            messages = [{"role": "user", "content": humanization_prompt}]

            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(
                    context.scene_index) if context.scene_index else None
            )

            if not llm_result:
                return None

            return self._parse_llm_response(llm_result.get("content", ""))

        except Exception as e:
            self.logger.error(f"人性化改写失败: {e}")
            return None

    def _format_ai_issues(self, issues: List[Dict]) -> str:
        """格式化AI检测问题

        Args:
            issues: AI检测问题列表

        Returns:
            格式化后的字符串
        """
        if not issues:
            return "未检测到AI写作特征"

        formatted = []
        for i, issue in enumerate(issues, 1):
            category = issue.get("category", "未知类别")
            issue_type = issue.get("type", "未知类型")
            severity = issue.get("severity", "medium")
            location = issue.get("location", "")
            description = issue.get("description", "")
            ai_pattern = issue.get("ai_pattern", "")
            human_alternative = issue.get("human_alternative", "")

            formatted.append(
                f"【问题{i}】\n"
                f"类别: {category}\n"
                f"类型: {issue_type}\n"
                f"严重程度: {severity}\n"
                f"位置: {location}\n"
                f"描述: {description}\n"
                f"AI模式: {ai_pattern}\n"
                f"人类写法: {human_alternative}"
            )

        return "\n\n".join(formatted)

    def _build_style_library_polish_prompt(
        self,
        content: str,
        style_library_guide: Dict,
        logic_issues: List[Dict],
        character_profiles: List[Dict]
    ) -> tuple:
        """构建基于文风知识库的风格润色提示词

        Args:
            content: 待润色内容
            style_library_guide: 文风知识库风格指南
            logic_issues: 逻辑问题列表
            character_profiles: 人物档案列表

        Returns:
            (system_prompt, user_prompt) 元组
        """
        from app.tools.style_library import format_style_for_prompt

        system_prompt = """你是一位资深的文学编辑和文风专家，擅长根据指定的文学风格进行精准润色。

## 核心职责

1. **风格对齐**：确保文本严格符合指定的文风特征
2. **语言润色**：提升文字表现力，保持风格一致性
3. **逻辑修正**：修复逻辑问题，保持情节连贯
4. **对话优化**：使对话符合角色身份和文风要求
5. **描写增强**：增强场景描写的画面感和风格特征

## 润色原则

- **风格优先**：所有修改必须服务于目标文风
- **保留原意**：不改变核心情节和人物关系
- **精准调整**：针对性调整词汇、句式、叙事节奏
- **自然流畅**：润色后的文本必须自然，不生硬"""

        # 格式化文风特征
        style_section = format_style_for_prompt(style_library_guide)

        user_prompt = f"""请根据以下文风要求对内容进行精准润色。

## 目标文风（**必须严格遵循**）

{style_section}

## 待润色内容

{content}

## 逻辑问题修正（如有）

{self._format_logic_issues(logic_issues)}

## 角色设定（用于优化对话）

{self._format_character_profiles(character_profiles)}

## 润色要求

1. **词汇层面**
   - 根据文风特征调整用词偏好
   - 使用标志性词汇和特色表达
   - 避免文风要求中明确禁止的词汇

2. **句式层面**
   - 调整句子长度比例（如极简主义用短句，浪漫主义用长句）
   - 使用偏好句式结构
   - 控制标点使用风格

3. **叙事层面**
   - 确保叙事视角符合文风要求
   - 调整叙事节奏（快速/缓慢/跳跃/平稳）
   - 优化时空处理方式

4. **描写层面**
   - 强化文风指定的描写重点
   - 调整感官描写的比例和方式
   - 运用文风偏好的修辞手法

5. **对话层面**
   - 使对话符合文风的整体特征
   - 调整对话密度和功能性
   - 增强角色语言的个性化

## 输出格式

```json
{{
    "polished_content": "润色后的完整内容",
    "changes_summary": "修改摘要，重点说明风格对齐的改动",
    "word_count": 1200,
    "style_alignment_score": 90,
    "style_adjustments": [
        {{
            "dimension": "词汇|句式|叙事|描写|对话",
            "original": "原文特征",
            "adjusted": "调整后特征",
            "reason": "调整原因"
        }}
    ]
}}
```

请直接输出JSON格式的润色结果。"""

        return system_prompt, user_prompt

    def _format_style_guide(self, style_guide: Dict, style_document_features: str = "") -> str:
        """格式化风格指南

        Args:
            style_guide: 风格指南字典
            style_document_features: 文风文档特征（可选）

        Returns:
            格式化后的字符串
        """
        lines = []

        if style_guide:
            if "genre" in style_guide:
                lines.append(f"体裁: {style_guide['genre']}")
            if "tone" in style_guide:
                lines.append(f"基调: {style_guide['tone']}")
            if "narrative_style" in style_guide:
                lines.append(f"叙事风格: {style_guide['narrative_style']}")
            if "language_style" in style_guide:
                lines.append(f"语言风格: {style_guide['language_style']}")
            if "style_reference" in style_guide and style_guide["style_reference"]:
                lines.append(
                    f"风格参考: {style_guide['style_reference'][:500]}...")
            if "special_requirements" in style_guide:
                reqs = style_guide["special_requirements"]
                if isinstance(reqs, list):
                    lines.append(f"特殊要求: {'; '.join(reqs)}")
                else:
                    lines.append(f"特殊要求: {reqs}")

        if style_document_features:
            lines.append(f"\n【文风文档特征】\n{style_document_features}")

        return "\n".join(lines) if lines else "无特定风格要求，保持原文风格即可"

    def _format_logic_issues(self, issues: List[Dict]) -> str:
        """格式化逻辑问题

        Args:
            issues: 逻辑问题列表

        Returns:
            格式化后的字符串
        """
        if not issues:
            return "无逻辑问题需要修正"

        formatted = []
        for i, issue in enumerate(issues, 1):
            issue_type = issue.get("type", "未知类型")
            severity = issue.get("severity", "medium")
            description = issue.get("description", "")
            suggestion = issue.get("suggestion", "")

            lines = [f"{i}. [{severity.upper()}] {issue_type}"]
            if description:
                lines.append(f"   问题: {description}")
            if suggestion:
                lines.append(f"   建议: {suggestion}")

            formatted.append("\n".join(lines))

        return "\n\n".join(formatted)

    def _format_character_profiles(self, profiles: List[Dict]) -> str:
        """格式化角色档案

        Args:
            profiles: 角色档案列表

        Returns:
            格式化后的字符串
        """
        if not profiles:
            return "无角色设定"

        formatted = []
        for profile in profiles:
            name = profile.get("name", "未知")
            voice = profile.get("voice", "")  # 角色的语言风格/说话方式
            personality = profile.get("personality", "")

            lines = [f"【{name}】"]
            if voice:
                lines.append(f"  语言特点: {voice}")
            if personality:
                lines.append(f"  性格: {personality}")

            formatted.append("\n".join(lines))

        return "\n\n".join(formatted)

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """解析LLM返回的JSON响应

        使用健壮的JSON解析器，支持多种格式的LLM返回

        Args:
            content: LLM返回的原始内容

        Returns:
            解析后的字典
        """
        if not content:
            return {
                "polished_content": "",
                "changes_summary": "LLM返回内容为空",
                "word_count": 0
            }

        # 使用健壮的JSON解析器
        result = parse_json(content, default=None)

        if result is not None and isinstance(result, dict):
            self.logger.debug("润色JSON解析成功")
            return result

        # 如果解析失败，返回默认结构
        self.logger.warning("无法解析润色JSON，使用默认结构")
        return {
            "polished_content": content,
            "changes_summary": "直接返回润色内容",
            "word_count": len(content)
        }

    def _parse_style_analysis_response(self, content: str) -> Dict[str, Any]:
        """解析风格文档分析的LLM响应

        使用系统级JSON格式化工具进行统一处理，
        支持多种格式的LLM返回，自动修复常见格式问题

        Args:
            content: LLM返回的原始内容

        Returns:
            风格分析结果字典
        """
        if not content:
            self.logger.error("LLM返回内容为空")
            return self._extract_style_from_text("")

        self.logger.info(f"风格分析 - LLM返回长度: {len(content)} 字符")
        self.logger.debug(f"风格分析 - LLM返回前200字符: {content[:200]}")

        # 使用健壮的JSON解析器
        result, parse_logs = RobustJSONParser.parse(
            content,
            default=None,
            repair_truncated=True
        )

        # 记录解析日志
        for log in parse_logs:
            self.logger.debug(f"JSON解析: {log}")

        if result is not None and isinstance(result, dict):
            if self._validate_style_analysis_result(result):
                style_name = result.get('style_profile', {}).get(
                    'name', 'Unknown') if isinstance(result.get('style_profile'), dict) else 'N/A'
                self.logger.info(f"风格分析JSON解析成功: Style={style_name}")
                return result
            else:
                self.logger.warning(
                    f"JSON验证失败: 缺少必要字段 "
                    f"(style_profile: {'style_profile' in result}, "
                    f"style_guide_for_writing: {'style_guide_for_writing' in result})"
                )
                # 即使验证失败，如果有部分数据也返回
                if result.get('style_profile') or result.get('style_guide_for_writing'):
                    self.logger.info("返回部分有效的风格分析结果")
                    return result

        self.logger.warning("所有JSON解析方法均失败，尝试从文本提取关键信息")
        return self._extract_style_from_text(content)

    def _clean_control_characters(self, text: str) -> str:
        """
        清理JSON字符串中的非法控制字符和未转义引号

        解决JSON解析错误：
        1. "Invalid control character" - LLM返回包含原始控制字符(\n, \t等)
        2. "Expecting ',' / 'Expecting property name'" - 字符串值内部包含未转义的引号

        处理策略（智能状态机）：
        - 区分"结构层引号"和"字符串值内部的引号"
        - 在字符串值内部时：将控制字符替换为空格，将未转义双引号转义为\\"

        Args:
            text: 可能包含问题的JSON文本

        Returns:
            清理后的安全JSON文本
        """
        if not text:
            return text

        original_len = len(text)
        result = []
        i = 0
        text_len = len(text)

        while i < text_len:
            char = text[i]

            if char == '\\':
                result.append(char)
                if i + 1 < text_len:
                    result.append(text[i + 1])
                    i += 2
                    continue
                else:
                    i += 1
                    continue

            if char != '"':
                code = ord(char)
                if len(result) >= 2 and result[-2] == '"' and result[-1] != '\\' and code < 0x20 and code not in (0x09, 0x0A, 0x0D):
                    pass
                elif code == 0x0A or code == 0x09:
                    result.append(' ')
                elif code == 0x0D:
                    pass
                else:
                    result.append(char)
                i += 1
                continue

            is_likely_end_quote = False
            j = i + 1
            while j < text_len and text[j] in ' \t\n\r':
                j += 1

            if j < text_len:
                next_char = text[j]
                if next_char in ':,]}])':
                    is_likely_end_quote = True
                elif j > i + 1:
                    k = i - 1
                    while k >= 0 and text[k] in ' \t\n\r':
                        k -= 1
                    if k >= 0 and text[k] in '([{,:':
                        is_likely_end_quote = True
            else:
                is_likely_end_quote = True

            if is_likely_end_quote:
                result.append(char)
            else:
                result.append('\\"')

            i += 1

        cleaned = ''.join(result)
        import re
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', cleaned)

        if len(cleaned) != original_len:
            removed_count = original_len - len(cleaned)
            self.logger.info(
                f"JSON文本清理完成: 原始{original_len}字符 -> 清理后{len(cleaned)}字符 (差异{removed_count})")

        return cleaned

    def _validate_style_analysis_result(self, result: Dict[str, Any]) -> bool:
        """验证风格分析结果是否包含必要的字段

        Args:
            result: 解析后的结果字典

        Returns:
            是否有效
        """
        if not isinstance(result, dict):
            return False

        # 必须包含style_profile或style_guide_for_writing
        has_style_profile = "style_profile" in result and isinstance(
            result["style_profile"], dict)
        has_style_guide = "style_guide_for_writing" in result

        return has_style_profile or has_style_guide

    def _try_fix_truncated_json(self, response: str) -> Optional[str]:
        """
        尝试修复被截断的JSON

        参考知识图谱实体提取的方法，修复LLM返回的不完整JSON

        Args:
            response: LLM返回的原始内容

        Returns:
            修复后的JSON字符串，如果无法修复则返回None
        """
        # 找到关键字段的位置
        style_profile_start = response.find('"style_profile"')
        style_guide_start = response.find('"style_guide_for_writing"')

        if style_profile_start == -1 and style_guide_start == -1:
            return None

        # 尝试提取style_profile对象
        style_profile_obj = None
        if style_profile_start != -1:
            brace_start = response.find('{', style_profile_start)
            if brace_start != -1:
                style_profile_obj = self._extract_complete_object(
                    response, brace_start)

        # 尝试提取style_guide_for_writing字符串
        style_guide_value = None
        if style_guide_start != -1:
            # 查找冒号后的值
            colon_pos = response.find(':', style_guide_start)
            if colon_pos != -1:
                # 跳过空格和引号
                value_start = colon_pos + 1
                while value_start < len(response) and (response[value_start] in [' ', '\t', '\n']):
                    value_start += 1

                if value_start < len(response):
                    if response[value_start] == '"':
                        # 字符串值，找到结束引号
                        end_quote = self._find_closing_quote(
                            response, value_start)
                        if end_quote != -1:
                            style_guide_value = response[value_start+1:end_quote]
                    else:
                        # 可能是其他类型的值，截取到下一个逗号或大括号
                        next_comma = response.find(',', value_start)
                        next_brace = response.find('}', value_start)
                        end_pos = min(
                            next_comma if next_comma != -1 else len(response),
                            next_brace if next_brace != -1 else len(response)
                        )
                        style_guide_value = response[value_start:end_pos].strip().strip(
                            '"')

        # 构建修复后的JSON
        if style_profile_obj or style_guide_value:
            parts = []
            if style_profile_obj:
                parts.append(f'"style_profile": {style_profile_obj}')
            if style_guide_value:
                escaped_guide = style_guide_value.replace(
                    '\\', '\\\\').replace('"', '\\"')
                parts.append(f'"style_guide_for_writing": "{escaped_guide}"')

            return '{' + ', '.join(parts) + '}'

        return None

    def _extract_complete_object(self, json_str: str, start: int) -> Optional[str]:
        """
        从JSON字符串中提取完整的对象

        Args:
            json_str: JSON字符串
            start: 对象起始位置

        Returns:
            完整的对象字符串，如果无法提取则返回None
        """
        depth = 0
        in_string = False
        escape_next = False
        last_complete_pos = start

        for i in range(start, len(json_str)):
            char = json_str[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\' and in_string:
                escape_next = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return json_str[start:i+1]
                    elif depth == 1:
                        last_complete_pos = i
                elif char == ']' and depth == 1:
                    last_complete_pos = i

        # 对象不完整，尝试截断到最后一个完整的键值对
        if last_complete_pos > start:
            truncated = json_str[start:last_complete_pos+1]
            # 尾部清理
            truncated = truncated.rstrip()
            while truncated.endswith(',') or truncated.endswith(':'):
                truncated = truncated[:-1]
            return truncated + '}'

        return None

    def _find_closing_quote(self, s: str, start: int) -> int:
        """
        查找匹配的结束引号

        Args:
            s: 字符串
            start: 开始引号的位置

        Returns:
            结束引号的位置，如果没有找到返回-1
        """
        escape = False
        for i in range(start + 1, len(s)):
            if escape:
                escape = False
                continue
            if s[i] == '\\':
                escape = True
                continue
            if s[i] == '"':
                return i
        return -1

    def _extract_style_from_text(self, content: str) -> Dict[str, Any]:
        """从非结构化文本中提取风格信息

        当LLM返回的不是标准JSON格式时，尝试从文本中提取有用信息

        Args:
            content: LLM返回的原始文本

        Returns:
            构建的风格分析结果
        """
        import re

        # 尝试提取关键信息
        style_name = "未知风格"
        style_guide = content[:500] if len(content) > 500 else content

        # 尝试从文本中提取风格名称
        name_patterns = [
            r'风格名称[：:]\s*["\']?([^"\'\n，,]+)["\']?',
            r'name[：:]\s*["\']?([^"\'\n，,]+)["\']?',
            r'风格[：:]\s*["\']?([^"\'\n，,]+)["\']?'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, content)
            if match:
                style_name = match.group(1).strip()
                break

        # 构建基本的风格分析结果
        return {
            "style_profile": {
                "name": style_name,
                "vocabulary": {
                    "word_preference": "从文档中自动提取",
                    "signature_words": []
                },
                "sentence_structure": {
                    "average_length": "未知",
                    "preferred_patterns": []
                },
                "narrative_style": {
                    "perspective": "未知",
                    "pacing": "未知"
                }
            },
            "style_guide_for_writing": style_guide,
            "key_imitation_points": [
                "请参考上传的文风文档进行写作",
                "注意保持原文的语言风格特点"
            ],
            "avoid_patterns": [
                "避免与原文风格差异过大的表达"
            ],
            "_raw_content": content[:2000] if len(content) > 2000 else content,
            "_parse_warning": "LLM返回格式非标准JSON，已自动提取关键信息"
        }

    def _get_timestamp(self) -> int:
        """获取当前时间戳（毫秒）"""
        import time
        return int(time.time() * 1000)
