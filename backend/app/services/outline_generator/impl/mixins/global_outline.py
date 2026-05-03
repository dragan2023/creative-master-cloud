"""大纲生成器 - 全局大纲生成Mixin"""
from typing import AsyncGenerator
from typing import Dict
from typing import List
from typing import Any
from datetime import datetime
import re
from app.agents.orchestrator import extract_input_params_files


def _build_script_style_guidance(
    script_style_type: str,
    script_style_dimensions: Dict,
    script_style_names: List[str],
    script_style_intensity: float,
    script_series_sub_type: str = None
) -> str:
    """
    构建剧本多维风格指导文本

    Args:
        script_style_type: 风格类型 'movie' 或 'series'
        script_style_dimensions: 维度数据 dict，如 {'导演风格': [{'name': '张艺谋'}], ...}
        script_style_names: 选中的风格名称扁平化列表
        script_style_intensity: 风格强度 0.0-1.0
        script_series_sub_type: 剧集子类型 'long' 或 'short'

    Returns:
        格式化的风格指导字符串
    """
    # 安全处理 None 值
    safe_intensity = script_style_intensity if script_style_intensity is not None else 0.7
    intensity_pct = int(safe_intensity * 100)

    if script_style_type == 'movie':
        header = "## 电影风格指导"
        content_type_label = "电影创作风格"
    else:
        sub_label = "（长剧）" if script_series_sub_type == 'long' else "（短剧）" if script_series_sub_type == 'short' else ""
        header = f"## 剧集风格指导{sub_label}"
        content_type_label = "剧集创作风格"

    # 构建维度列表
    dimension_lines = []
    for dim_name, styles in script_style_dimensions.items():
        if styles and len(styles) > 0:
            style_names_in_dim = [
                (s.get('name') or str(s)) if isinstance(s, dict) else str(s)
                for s in styles
            ]
            style_names_str = '、'.join(style_names_in_dim)
            dimension_lines.append(f"- **{dim_name}**：{style_names_str}")

    dimensions_text = '\n'.join(dimension_lines) if dimension_lines else '- （未选择具体风格）'

    # 构建全部选中风格列表
    all_names = '、'.join(script_style_names) if script_style_names else '无'

    return f"""
{header}

你已选择以下{content_type_label}：
{dimensions_text}
- **风格强度**：{intensity_pct}%

**应用规则**：
1. 全局大纲的撰写必须体现所选风格的特征
2. 人物设定、场景设计、故事结构都要符合所选风格特点
3. 视觉风格建议应反映所选风格的审美取向（如色彩方案、画面质感、节奏感等）
4. 对白风格应与所选台词风格保持一致

**风格融合说明**：
已选风格（{all_names}）应在创作中自然融合，不应生硬堆砌
- 主风格维度（第一个维度）作为创作基调
- 其他维度风格作为调味元素渐进式融合

**注意事项**：
- 风格强度{intensity_pct}%意味着风格特征的明显程度
- 强度越高，风格特征越突出
- 但大纲仍需保持结构清晰，不要因追求风格而牺牲可读性
"""


def _resolve_style_guidance(
    input_params: Dict[str, Any],
    style_ids: List[str],
    style_names: List[str],
    style_intensity: float,
    style_guide: Dict = None
) -> str:
    """
    从 input_params 中解析风格指导文本（统一入口，消除重复代码）

    优先检测剧本多维风格（script_style_dimensions），
    回退到小说文风参数（style_ids/style_names），
    最后使用默认提示。

    Args:
        input_params: 用户输入参数字典
        style_ids: 小说文风ID列表
        style_names: 小说文风名称列表
        style_intensity: 小说文风强度
        style_guide: 融合后的风格指南

    Returns:
        格式化的风格指导字符串
    """
    script_style_dimensions = input_params.get('script_style_dimensions')
    script_style_names = input_params.get('script_style_names', [])
    script_style_intensity = input_params.get('script_style_intensity', 0.7)
    script_style_type = input_params.get('script_style_type')
    script_series_sub_type = input_params.get('script_series_sub_type')

    if script_style_dimensions and script_style_names and len(script_style_names) > 0:
        # 剧本多维风格指导
        return _build_script_style_guidance(
            script_style_type=script_style_type,
            script_style_dimensions=script_style_dimensions,
            script_style_names=script_style_names,
            script_style_intensity=script_style_intensity,
            script_series_sub_type=script_series_sub_type
        )
    elif style_ids and len(style_ids) > 0:
        return f"""
## 文风应用指南

你已选择以下写作风格进行融合创作：
- 主风格：{style_names[0] if len(style_names) > 0 else '无'}
- 辅风格：{', '.join(style_names[1:]) if len(style_names) > 1 else '无'}
- 风格强度：{style_intensity * 100:.0f}%

**应用规则**：
1. 全局大纲的撰写必须体现所选文风的特征
2. 人物设定、世界观描述、故事结构都要符合文风特点
3. 语言风格参考：
{style_guide.get('style_library_guide', '') if style_guide else ''}

**注意事项**：
- 文风强度{style_intensity * 100:.0f}%意味着文风特征的明显程度
- 强度越高，文风特征越突出
- 但大纲仍需保持结构清晰，不要因追求文风而牺牲可读性
"""
    else:
        return "（用户未选择特定风格，请使用标准创作风格）"


class GlobalOutlineMixin:
    """全局大纲生成"""

    async def generate_global_outline(
        self,
        content_type: str,  # novel/script
        input_params: Dict[str, Any],
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_knowledge: bool = False,  # 是否启用知识库修正（默认False，由用户主动控制）
        style_ids: List[str] = [],  # 文风ID列表
        style_names: List[str] = [],  # 文风名称列表
        style_intensity: float = 0.7,  # 文风强度
        style_guide: Dict = None  # 融合后的风格指南
    ) -> Dict[str, Any]:
        """
        生成全局大纲(第一阶段)

        Args:
            content_type: 内容类型 (novel/script)
            input_params: 输入参数
            provider: LLM提供商
            model: 模型名称
            temperature: 温度参数
            user_id: 用户ID
            enable_knowledge: 是否启用知识库修正（默认False，由用户主动控制）

        Returns:
            生成结果，包含全局大纲内容
        """
        start_time = datetime.now()
        result = {
            "success": False,
            "content": None,
            "error": None,
            "duration_ms": 0,
            "knowledge_revision": False  # 是否进行了知识库修正
        }

        try:
            # 确定模块名称
            module_name = f"{content_type}_global_outline"

            # 获取提示词模板（使用默认模板，不需要数据库）
            prompt_template = self.prompt_manager.get_default_prompt(
                module_name)
            if not prompt_template:
                raise ValueError(f"未找到提示词模板: {module_name}")

            # 渲染提示词（填充变量）
            # 生成风格指导（统一入口，支持剧本多维风格和小说文风两种模式）
            style_guidance = _resolve_style_guidance(
                input_params=input_params,
                style_ids=style_ids,
                style_names=style_names,
                style_intensity=style_intensity,
                style_guide=style_guide
            )

            render_params = {
                **input_params,
                'style_ids': style_ids,
                'style_names': style_names,
                'style_intensity': style_intensity,
                'style_guide': style_guide or {},
                'style_guidance': style_guidance
            }
            filled_prompt = self.prompt_manager.render_prompt(
                prompt_template, render_params, module_name
            )

            self.logger.info(f"[全局大纲] 开始生成，模块: {module_name}")

            # 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(
                self.db, user_id, provider
            )
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            # 调用LLM生成（不传递model参数，使用provider初始化时的model_name）
            llm_response = await llm_provider.generate(
                prompt=filled_prompt,
                temperature=temperature
            )

            content = llm_response.content if hasattr(
                llm_response, 'content') else str(llm_response)

            # ==================== 知识库修正 ====================
            if enable_knowledge:
                try:
                    self.logger.info("[全局大纲] 开始知识库修正...")
                    revised_content = await self._revise_with_knowledge_base(
                        llm_provider=llm_provider,
                        original_content=content,
                        input_params=input_params,
                        temperature=temperature,
                        db=self.db,
                        user_id=user_id,
                        content_type=content_type
                    )
                    if revised_content:
                        content = revised_content
                        result["knowledge_revision"] = True
                        self.logger.info("[全局大纲] 知识库修正完成")
                except Exception as kb_error:
                    # 知识库修正失败不影响主流程，使用原始内容
                    self.logger.warning(
                        f"[全局大纲] 知识库修正失败，使用原始内容: {str(kb_error)}")

            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            result["success"] = True
            result["content"] = content
            result["duration_ms"] = duration_ms
            result["model"] = getattr(
                llm_response, 'model', llm_provider.model_name)
            result["provider"] = provider

            self.logger.info(
                f"[全局大纲] 生成完成，耗时: {duration_ms}ms，内容长度: {len(content)}")

        except Exception as e:
            self.logger.error(f"[全局大纲] 生成失败: {e!r}")
            result["error"] = str(e)[:500]

        return result


    async def generate_global_outline_stream(
        self,
        content_type: str,
        input_params: Dict[str, Any],
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_knowledge: bool = False,  # 是否启用知识库修正（默认False，由用户主动控制）
        enable_auto_qc: bool = True,  # v2.3新增：是否启用自动质控修正
        style_ids: List[str] = [],
        style_names: List[str] = [],
        style_intensity: float = 0.7,
        style_guide: Dict = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成全局大纲（第一阶段）- v2.3新增自动质控修正

        通过 SSE 事件流式输出：
        - workflow 事件：通知前端当前执行步骤
        - content 事件：流式输出内容
        - replace_content 事件：通知前端替换内容（知识库修正后/质控修正后）

        Args:
            content_type: 内容类型 (novel/script)
            input_params: 输入参数
            provider: LLM提供商
            model: 模型名称
            temperature: 温度参数
            user_id: 用户ID
            enable_knowledge: 是否启用知识库修正（默认False，由用户主动控制）
            enable_auto_qc: 是否启用自动质控修正（v2.3新增）

        Yields:
            SSE 事件字符串
        """
        try:
            # v2.3修复：初始化revised_content变量，避免后续引用时出现NameError
            revised_content = None

            module_name = f"{content_type}_global_outline"
            input_params = await extract_input_params_files(input_params, self.logger)

            prompt_template = self.prompt_manager.get_default_prompt(
                module_name)
            if not prompt_template:
                raise ValueError(f"未找到提示词模板: {module_name}")

            # 生成风格指导（统一入口，支持剧本多维风格和小说文风两种模式）
            style_guidance = _resolve_style_guidance(
                input_params=input_params,
                style_ids=style_ids,
                style_names=style_names,
                style_intensity=style_intensity,
                style_guide=style_guide
            )

            render_params = {
                **input_params,
                'style_ids': style_ids,
                'style_names': style_names,
                'style_intensity': style_intensity,
                'style_guide': style_guide or {},
                'style_guidance': style_guidance
            }
            filled_prompt = self.prompt_manager.render_prompt(
                prompt_template, render_params, module_name)
            self.logger.info(f"[全局大纲流式] 开始生成，模块: {module_name}")

            # 发送开始生成的工作流事件
            yield self._format_sse("workflow", {
                "type": "step", "step": "generate", "status": "running",
                "message": "正在生成全局大纲...", "icon": "MagicStick"
            })

            llm_provider = await self.llm_manager.get_provider_from_db(self.db, user_id, provider)
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            full_content_chunks = []

            async for chunk in llm_provider.generate_stream(prompt=filled_prompt, temperature=temperature):
                if hasattr(chunk, 'content'):
                    full_content_chunks.append(chunk.content)
                    yield self._format_sse("content", {"text": chunk.content})
                elif isinstance(chunk, str):
                    full_content_chunks.append(chunk)
                    yield self._format_sse("content", {"text": chunk})

            # 发送生成完成的工作流事件
            yield self._format_sse("workflow", {
                "type": "step", "step": "generate", "status": "done",
                "message": "全局大纲生成完成", "icon": "MagicStick"
            })

            # ==================== 知识库修正 ====================
            # 自动执行知识库修正（如果启用）
            if enable_knowledge:
                try:
                    self.logger.info("[全局大纲流式] 开始知识库修正...")
                    yield self._format_sse("workflow", {
                        "type": "step", "step": "knowledge_revise", "status": "running",
                        "message": "正在基于知识库优化全局大纲...", "icon": "Collection"
                    })

                    revised_content = await self._revise_with_knowledge_base(
                        llm_provider=llm_provider,
                        original_content=''.join(full_content_chunks),
                        input_params=input_params,
                        temperature=temperature,
                        db=self.db,
                        user_id=user_id,
                        content_type=content_type
                    )

                    if revised_content:
                        yield self._format_sse("workflow", {
                            "type": "step", "step": "knowledge_revise", "status": "done",
                            "message": "知识库优化完成", "icon": "Collection"
                        })
                        # 发送替换内容事件，通知前端替换整个内容
                        yield self._format_sse("replace_content", {
                            "content": revised_content,
                            "message": "已基于知识库优化全局大纲"
                        })
                        self.logger.info("[全局大纲流式] 知识库修正完成")
                    else:
                        yield self._format_sse("workflow", {
                            "type": "step", "step": "knowledge_revise", "status": "done",
                            "message": "知识库验证通过，无需修正", "icon": "Collection"
                        })
                        self.logger.info("[全局大纲流式] 知识库验证通过，无需修正")
                except Exception as kb_error:
                    # 知识库修正失败不影响主流程
                    self.logger.warning(f"[全局大纲流式] 知识库修正失败: {str(kb_error)}")
                    yield self._format_sse("workflow", {
                        "type": "step", "step": "knowledge_revise", "status": "error",
                        "message": "知识库修正失败，使用原始内容", "icon": "Collection"
                    })

            # ==================== v2.3新增：自动质控修正 ====================
            # 获取当前内容（知识库修正后的或原始内容）
            # v2.3修复：简化逻辑，直接检查revised_content是否为None
            current_content = revised_content if (
                enable_knowledge and revised_content) else ''.join(full_content_chunks)

            if enable_auto_qc:
                try:
                    self.logger.info("[全局大纲流式] 开始自动质控修正...")
                    yield self._format_sse("workflow", {
                        "type": "step", "step": "auto_qc", "status": "running",
                        "message": "正在进行质量检测与修正...", "icon": "Check"
                    })

                    # 执行自动质控修正
                    qc_result = await self._auto_qc_and_revise(
                        content=current_content,
                        user_id=user_id,
                        llm_provider=llm_provider
                    )

                    if qc_result.get("success") and qc_result.get("revised_content"):
                        # 有修正内容，发送替换事件
                        yield self._format_sse("replace_content", {
                            "content": qc_result["revised_content"],
                            "original_content": current_content,  # v2.4新增：传递原始内容用于对比
                            # v2.4新增：明确传递修正后内容
                            "revised_content": qc_result["revised_content"],
                            "qc_applied": True,
                            "issues_fixed": qc_result.get("issues_fixed", 0),
                            "qc_report": qc_result.get("qc_report"),
                            # v2.4新增：原始长度
                            "original_length": len(current_content),
                            # v2.4新增：修正后长度
                            "revised_length": len(qc_result["revised_content"])
                        })
                        yield self._format_sse("workflow", {
                            "type": "step", "step": "auto_qc", "status": "done",
                            "message": f"质量检测完成，已修正{qc_result.get('issues_fixed', 0)}个问题", "icon": "Check"
                        })
                        self.logger.info(
                            f"[全局大纲流式] 自动质控修正完成，修正{qc_result.get('issues_fixed', 0)}个问题")
                    else:
                        # 无问题或修正失败
                        yield self._format_sse("workflow", {
                            "type": "step", "step": "auto_qc", "status": "done",
                            "message": "质量检测完成，未发现需要修正的问题", "icon": "Check"
                        })
                        # 仍发送质控报告供历史记录
                        yield self._format_sse("qc_report", {
                            "qc_applied": False,
                            "issues_fixed": 0,
                            "qc_report": qc_result.get("qc_report")
                        })
                        self.logger.info("[全局大纲流式] 质量检测完成，无需修正")

                except Exception as qc_error:
                    # 质控修正失败不影响主流程
                    self.logger.warning(f"[全局大纲流式] 自动质控修正失败: {str(qc_error)}")
                    yield self._format_sse("workflow", {
                        "type": "step", "step": "auto_qc", "status": "error",
                        "message": "质量检测失败，跳过修正", "icon": "Check"
                    })

            yield self._format_sse("workflow", {"type": "complete"})

        except Exception as e:
            self.logger.error(f"[全局大纲流式] 生成失败: {e!r}")
            yield self._format_sse("workflow", {"type": "error", "message": f"生成失败: {str(e)[:200]}"})


