"""
风格润色Agent 包入口

将原 style_editor_agent.py 拆分为多个功能模块，通过 Mixin 多重继承组合。

包结构:
    __init__.py: 统一导出 StyleEditorAgent（从子 Mixin 组合）
    _prompts.py: 提示词构建 Mixin
    _style_analysis.py: 文风分析 Mixin
    _ai_detection.py: AI文风检测与消除 Mixin
    _llm_utils.py: LLM响应解析工具 Mixin

@date: 2026-04-24
@version: v2.0.0
"""
from ._prompts import StyleEditorPromptsMixin
from ._style_analysis import StyleEditorAnalysisMixin
from ._ai_detection import StyleEditorDetectionMixin
from ._llm_utils import StyleEditorUtilsMixin
from app.agents.writing.base_agent import BaseWritingAgent, AgentRole


class StyleEditorAgent(
    BaseWritingAgent,
    StyleEditorUtilsMixin,
    StyleEditorPromptsMixin,
    StyleEditorAnalysisMixin,
    StyleEditorDetectionMixin,
):
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
            humanization_threshold: 人性化改写阈值(0-100)
        """
        super().__init__(config)
        self.enable_ai_detection = enable_ai_detection if enable_ai_detection is not None else self.ENABLE_AI_DETECTION_DEFAULT
        self.enable_humanization = enable_humanization if enable_humanization is not None else self.ENABLE_HUMANIZATION_DEFAULT
        self.humanization_threshold = humanization_threshold if humanization_threshold is not None else self.AI_SCORE_THRESHOLD_DEFAULT

    async def execute(self, context) -> object:
        """对内容进行风格润色

        从上下文中获取待润色内容、风格指南和逻辑问题，
        使用LLM进行风格优化并返回润色后的内容。
        新增：AI文风检测与人性化改写功能。

        Args:
            context: Agent执行上下文

        Returns:
            AgentResult: 包含润色后的内容和相关数据
        """
        from app.agents.writing.base_agent import AgentRole as _AR
        self.agent_role = _AR.STYLE_EDITOR

        from app.agents.writing.prompts.style_prompts import STYLE_PROMPTS

        start_time = self._get_timestamp()

        try:
            # 🔴 防御：安全提取 extra（defense-in-depth，__post_init__ 已标准化但保留二次守卫）
            _ext = context.extra if isinstance(context.extra, dict) else {}

            draft_content = _ext.get("draft_content", "")
            if not draft_content:
                return self._build_error_result(
                    "缺少待润色内容",
                    error_type="missing_content"
                )

            style_guide = context.style_guide or {}
            logic_issues = _ext.get("logic_issues", [])
            character_profiles = context.character_profiles or []
            style_document_features = _ext.get(
                "style_document_features", "")

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

            if style_library_guide:
                system_prompt, user_prompt = self._build_style_library_polish_prompt(
                    content=current_content,
                    style_library_guide=style_library_guide,
                    logic_issues=logic_issues,
                    character_profiles=character_profiles
                )
            else:
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
                    context.scene_index) if context.scene_index else None,
                user_id=context.user_id
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


__all__ = ["StyleEditorAgent"]
