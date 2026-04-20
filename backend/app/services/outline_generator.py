"""
大纲生成器服务
负责两阶段大纲生成的核心逻辑：
- 第一阶段：生成详细的全局大纲（支持知识库修正）
- 第二阶段：基于全局大纲生成各单元的简要概述
"""
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime
import json
import re
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_manager import get_llm_manager, LLMManager
from app.agents.prompt_manager import get_prompt_manager, PromptManager
from app.agents.orchestrator import process_input_params_files

from app.core.logger import get_logger
from app.core.config import get_settings
from app.tools.knowledge_retrieval import get_knowledge_retrieval_tool
from app.agents.orchestrator import get_agent_orchestrator

# ==================== 功能开关配置 ====================
# 使用环境变量控制，避免硬编码 if False
# 设置 ENABLE_QUALITY_CONTROL=false 可禁用质控功能
ENABLE_QUALITY_CONTROL = os.getenv(
    "ENABLE_QUALITY_CONTROL", "true").lower() == "true"


# 知识库修正提示词模板
OUTLINE_REVISION_PROMPT = """你是专业的创意写作顾问，擅长基于知识库优化大纲内容。

【原始大纲】
{original_outline}

【创意理论知识库】
{theory_context}

【案例资料知识库】
{case_context}

【用户规范手册】
{manual_context}

## 优化任务

请基于以上知识库内容，对原始大纲进行优化修正：

1. **理论运用**：确保大纲运用了知识库中的创意理论（如三幕剧结构、人物弧光等）
2. **案例启发**：借鉴案例中的成功元素，但避免直接抄袭
3. **规范遵守**：确保符合用户规范手册的要求

## 输出要求

请直接输出优化后的完整大纲内容，不要添加任何解释或说明。
优化后的大纲应该：
- 保持原有结构和核心创意
- 融入知识库中的理论支撑
- 具有更强的戏剧张力和吸引力
"""


# 逻辑性修正提示词模板
LOGIC_CHECK_PROMPT = """你是专业的剧本/小说逻辑审核专家，擅长检测和修正故事中的逻辑问题。

【全局大纲】
{global_outline}

【单元概述列表】
{unit_summaries}

## 检测任务

请仔细分析以上内容，检测以下类型的逻辑风险点：

1. **设定冲突**：检测人物设定、世界观设定与单元概述内容的矛盾
   - 人物性格前后不一致
   - 能力设定与表现不符
   - 世界观规则违反

2. **剧情衔接跳脱**：检测单元概述之间的情节连贯性问题
   - 场景转换突兀
   - 因果关系断裂
   - 时间跨度不合理

3. **人物成长过快**：检测人物性格变化、能力提升的合理性
   - 技能习得过快
   - 性格转变缺乏铺垫
   - 关系进展不合理

4. **时间线矛盾**：检测事件发生顺序的逻辑性
   - 时间顺序错乱
   - 季节/时间设定矛盾
   - 年龄时间线问题

5. **核心线索断裂**：检测重要情节线索的连续性
   - 伏笔未回收
   - 主线偏移
   - 关键道具/信息消失

## 输出要求

请以JSON格式输出检测结果，格式如下：

```json
{{
  "has_issues": true或false,
  "issues": [
    {{
      "type": "设定冲突|剧情衔接跳脱|人物成长过快|时间线矛盾|核心线索断裂",
      "unit_number": "受影响的单元编号",
      "description": "问题描述",
      "severity": "high|medium|low"
    }}
  ],
  "revised_units": {{
    "1": "第1个单元的修正后完整内容",
    "2": "第2个单元的修正后完整内容"
  }}
}}
```

**重要**：
1. `revised_units` 中的 key 必须是纯数字字符串（如 "1", "2", "3"），对应单元的序号
2. `issues` 中的 `unit_number` 也必须是纯数字字符串
3. 如果检测到问题，请在 `revised_units` 中提供修正后的完整单元概述内容
如果没有问题，设置 `has_issues` 为 false，`issues` 和 `revised_units` 为空。

注意：修正时应保持原有风格和核心情节，只修复逻辑问题。
"""


class OutlineGenerator:
    """大纲生成器（两阶段）"""

    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.logger = get_logger(__name__)
        self.prompt_manager = get_prompt_manager()
        self.llm_manager = get_llm_manager()

    def _format_sse(self, event_type: str, data: dict) -> str:
        """格式化 SSE 事件"""
        import json
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

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
            # 合并input_params和文风参数
            # 生成文风指导
            if style_ids and len(style_ids) > 0:
                style_guidance = f"""
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
                style_guidance = "（用户未选择特定文风，请使用标准创作风格）"

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
            input_params = await process_input_params_files(input_params, self.logger)

            prompt_template = self.prompt_manager.get_default_prompt(
                module_name)
            if not prompt_template:
                raise ValueError(f"未找到提示词模板: {module_name}")

            # 合并input_params和文风参数
            # 生成文风指导
            if style_ids and len(style_ids) > 0:
                style_guidance = f"""
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
                style_guidance = "（用户未选择特定文风，请使用标准创作风格）"

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

    async def generate_unit_summaries(
        self,
        global_outline: str,
        unit_count: int,
        content_type: str,  # novel/script
        series_type: str = None,  # 剧本类型专用
        episode_duration_range: str = None,  # 剧本类型专用
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_quality_control: bool = True,  # 是否启用质量管控
        title_style: str = None,  # 标题风格ID（新增）
        title_style_name: str = None  # 标题风格名称（新增）
    ) -> Dict[str, Any]:
        """
        生成单元简要概述（第二阶段）

        Args:
            global_outline: 全局大纲内容
            unit_count: 单元数量（章节数/集数）
            content_type: 内容类型 (novel/script)
            series_type: 剧本类型（剧本专用）
            episode_duration_range: 每集时长区间（剧本专用）
            provider: LLM提供商
            model: 模型名称
            temperature: 温度参数
            user_id: 用户ID
            enable_quality_control: 是否启用质量管控
            title_style: 标题风格ID
            title_style_name: 标题风格名称

        Returns:
            生成结果，包含单元概述列表
        """
        start_time = datetime.now()
        result = {
            "success": False,
            "content": None,
            "parsed": None,
            "error": None,
            "duration_ms": 0,
            "quality_control": None  # 质量管控结果
        }

        try:
            # 确定模块名称
            module_name = f"{content_type}_unit_summaries"

            # 构建输入参数
            input_params = {
                "global_outline": global_outline,
                "chapter_count": str(unit_count),
                "episode_count": str(unit_count),
                "series_type": series_type or "网剧",
                "episode_duration_range": episode_duration_range or "30-45分钟"
            }

            # 生成标题风格指导文本（新增）
            if content_type == "novel" and title_style:
                from app.agents.writing.prompts.title_style_guidance import get_title_style_guidance
                title_style_guidance = get_title_style_guidance(
                    title_style, title_style_name or "")
                input_params["title_style_guidance"] = title_style_guidance
                self.logger.info(
                    f"[单元概述] 使用标题风格: {title_style_name} ({title_style})")
            else:
                input_params["title_style_guidance"] = ""

            # 获取提示词模板（使用默认模板，不需要数据库）
            prompt_template = self.prompt_manager.get_default_prompt(
                module_name)
            if not prompt_template:
                raise ValueError(f"未找到提示词模板: {module_name}")

            # 渲染提示词（填充变量）
            filled_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params, module_name
            )

            # 添加第一批生成的批次约束提示（防止LLM提前生成后续章节内容）
            unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
                content_type, "章"
            )
            filled_prompt += f"""

## 🚨🚨🚨 极其重要：第1批生成任务 - 严格的章节范围约束

### 当前任务状态
- **本次任务**：生成第1-{unit_count}{unit_label}的概述（第1批）
- **全局大纲**：已提供完整的1-{unit_count}章以上的大纲（供参考整体设定）
- **后续批次**：第{unit_count + 1}章及之后会在后续批次中生成

### ⛔ 绝对禁止的行为
1. ❌ 严禁生成超过第{unit_count}章的内容
2. ❌ 严禁跳过任何章节（必须1, 2, 3, ..., {unit_count}连续）
3. ❌ 严禁将第{unit_count + 1}章及之后的情节压缩到当前批次

### ✅ 必须严格遵守的规则
1. ✅ **必须从第1{unit_label}开始生成**
2. ✅ **必须按顺序生成**：第1章 → 第2章 → ... → 第{unit_count}章
3. ✅ **必须生成恰好{unit_count}个章节**，不多不少
4. ✅ **章节编号必须连续**：1, 2, 3, ..., {unit_count}

### 情节分配要求
- 根据全局大纲中第1-{unit_count}{unit_label}的情节分配进行生成
- 每个章节只生成对应章节的情节，不要提前生成后续章节
- 保持情节发展的自然节奏
- 为后续章节留下发展空间

### 输出格式示例
```
第1章 [章节标题]
梗概：[本章情节概述]
...

第2章 [章节标题]
梗概：[本章情节概述]
...

（继续直到第{unit_count}章）
```

**再次强调：从第1章开始，生成到第{unit_count}章结束，共{unit_count}章！**
"""

            self.logger.info(
                f"[单元概述] 开始生成，模块: {module_name}，单元数: {unit_count}")

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

            # 解析单元概述
            parsed = self.parse_unit_summaries(
                content, unit_count, content_type)

            # ==================== 截断检测与接续生成 ====================
            # 注意: 截断检测已禁用,现在使用分段生成机制替代
            # expected_count = self.get_expected_unit_count(...)
            # truncation_info = self.detect_truncated_units(...)

            # self.logger.info(
            #     f"[单元概述] 截断检测已禁用,使用分段生成机制"
            # )

            # 记录截断信息为空(保持兼容性)
            result["truncation_info"] = {
                "has_truncation": False,
                "missing_units": [],
                "truncated_units": [],
                "message": "截断检测已禁用,使用分段生成机制"
            }

            # ==================== 质量管控系统检查 ====================
            # 注意：质控功能已移出手动触发流程，用户可在生成完成后点击"质量检测"按钮执行
            # 使用环境变量 ENABLE_QUALITY_CONTROL 控制是否启用
            if ENABLE_QUALITY_CONTROL and enable_quality_control and parsed:
                try:
                    self.logger.info("[单元概述] 开始质量管控系统检查...")

                    # 初始化质量管控服务
                    from app.services.quality_control import QualityControlService
                    qc_service = QualityControlService(db=self.db)

                    # 构建章节数据(用于质量管控系统)
                    chapters_data = []
                    for unit_num, unit_data in parsed.items():
                        chapters_data.append({
                            "id": int(unit_num),
                            "unit_id": unit_data.get("unit_id", f"unit-{unit_num}"),
                            "chapter_number": int(unit_num),
                            "content": unit_data.get("full_content", "") or unit_data.get("summary", ""),
                            "summary": unit_data.get("summary", ""),
                            "full_content": unit_data.get("full_content", ""),
                            "title": unit_data.get("title", ""),
                            "status": "completed"
                        })

                    # 执行质量分析（使用专用的单元概述五维度质控机制）
                    quality_report_dict = await self._analyze_unit_summaries_quality(
                        qc_service=qc_service,
                        chapters_data=chapters_data,
                        dimensions=["unit_structure",
                                    "unit_character", "unit_consistency",
                                    "unit_timeline_space", "unit_ooc"],
                        depth="deep",
                        global_outline=global_outline,
                        user_id=user_id
                    )

                    result["quality_control"] = quality_report_dict

                    # 如果有严重问题,尝试自动修正
                    issues = quality_report_dict.get("issues", [])
                    critical_issues = [
                        issue for issue in issues
                        if issue.get("severity") == "critical"
                    ]

                    if critical_issues:
                        self.logger.info(
                            f"[单元概述] 发现{len(critical_issues)}个严重问题,尝试修正..."
                        )

                        # 构建修正提示词
                        revision_prompt = self._build_quality_revision_prompt(
                            unit_summaries=parsed,
                            quality_report_dict=quality_report_dict,
                            global_outline=global_outline,
                            content_type=content_type
                        )

                        # 调用LLM修正
                        revision_response = await llm_provider.generate(
                            prompt=revision_prompt,
                            temperature=temperature
                        )

                        # 解析修正结果并应用
                        revised_parsed = self._parse_quality_revision_result(
                            revision_response.content, parsed
                        )

                        if revised_parsed:
                            # 保存修正前后的对比信息
                            for unit_num, revised_data in revised_parsed.items():
                                if unit_num in parsed:
                                    parsed[unit_num]["original_summary"] = parsed[unit_num].get(
                                        "summary", "")
                                    parsed[unit_num]["summary"] = revised_data.get(
                                        "summary", parsed[unit_num]["summary"])
                                    parsed[unit_num]["quality_revised"] = True
                                    parsed[unit_num]["revision_reason"] = revised_data.get(
                                        "revision_reason", "")

                            self.logger.info("[单元概述] 质量管控修正完成")

                except Exception as qc_error:
                    # 质量管控失败不影响主流程
                    self.logger.warning(
                        f"[单元概述] 质量管控检查失败,使用原始内容: {str(qc_error)}"
                    )
                    result["quality_control"] = {"error": str(qc_error)}

            # 记录质控状态（供前端参考）
            result["quality_control_enabled"] = False
            result["quality_control_message"] = "质控检测已改为手动触发，请在生成完成后点击'质量检测'按钮"

            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            result["success"] = True
            result["content"] = content
            result["parsed"] = parsed
            result["duration_ms"] = duration_ms
            result["model"] = getattr(
                llm_response, 'model', llm_provider.model_name)
            result["provider"] = provider

            self.logger.info(
                f"[单元概述] 生成完成，耗时: {duration_ms}ms，解析单元数: {len(parsed)}")

        except Exception as e:
            self.logger.error(f"[单元概述] 生成失败: {str(e)}")
            result["error"] = str(e)

        return result

    async def generate_unit_summaries_stream(
        self,
        global_outline: str,
        unit_count: int,
        content_type: str,
        series_type: str = None,
        episode_duration_range: str = None,
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_quality_control: bool = True,
        cancel_event=None,
        # 续生成参数
        existing_content: str = "",
        existing_parsed: Dict[str, Dict[str, Any]] = None,
        start_from_unit: int = 1,
        # 标题风格参数（新增）
        title_style: str = None,
        title_style_name: str = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成单元简要概述（第二阶段）

        支持续生成模式和后置分层质量管控：
        - workflow 事件：通知前端当前执行步骤
        - content 事件：流式输出内容
        - replace_content 事件：质量修正后替换内容

        Args:
            global_outline: 全局大纲内容
            unit_count: 单元数量
            content_type: 内容类型
            series_type: 剧本类型
            episode_duration_range: 每集时长区间
            provider: LLM提供商
            model: 模型名称
            temperature: 温度参数
            user_id: 用户ID
            enable_quality_control: 是否启用质量管控
            cancel_event: 取消事件对象（用于中断生成）
            existing_content: 已生成的内容（续生成时使用）
            existing_parsed: 已解析的单元数据（续生成时使用）
            start_from_unit: 从第几章开始续生成（默认1表示全新生成）
            title_style: 标题风格ID
            title_style_name: 标题风格名称

        Yields:
            SSE 事件字符串
        """
        try:
            # 检测是否为续生成模式
            is_resume = bool(
                existing_content and existing_parsed and start_from_unit > 1)

            if is_resume:
                self.logger.info(
                    f"[单元概述续生成] 检测到续生成模式: "
                    f"已有{len(existing_parsed)}章, 从第{start_from_unit}章开始, "
                    f"目标{unit_count}章"
                )
                yield self._format_sse("workflow", {
                    "type": "step", "step": "resume_detection", "status": "done",
                    "message": f"检测到续生成模式，从第{start_from_unit}章继续生成至第{unit_count}章",
                    "icon": "RefreshRight"
                })

            # 确定模块名称
            module_name = f"{content_type}_unit_summaries"

            # 构建输入参数（区分续生成和全新生成）
            if is_resume:
                # 续生成模式：构建续生成上下文
                context_prefix = self._build_resume_context(
                    existing_parsed=existing_parsed,
                    start_from_unit=start_from_unit,
                    content_type=content_type
                )

                filled_prompt = self._build_resume_prompt(
                    module_name=module_name,
                    global_outline=global_outline,
                    context_prefix=context_prefix,
                    start_from_unit=start_from_unit,
                    unit_count=unit_count,
                    content_type=content_type,
                    series_type=series_type,
                    episode_duration_range=episode_duration_range,
                    title_style=title_style,  # 传递标题风格参数
                    title_style_name=title_style_name  # 传递标题风格名称
                )

                units_to_generate = unit_count - start_from_unit + 1
                self.logger.info(
                    f"[单元概述流式] 续生成模式，将生成第{start_from_unit}-{unit_count}章，"
                    f"共{units_to_generate}章"
                )
            else:
                # 全新生成模式
                input_params = {
                    "global_outline": global_outline,
                    "chapter_count": str(unit_count),
                    "episode_count": str(unit_count),
                    "series_type": series_type or "网剧",
                    "episode_duration_range": episode_duration_range or "30-45分钟"
                }

                # 生成标题风格指导文本（新增）
                if content_type == "novel" and title_style:
                    from app.agents.writing.prompts.title_style_guidance import get_title_style_guidance
                    title_style_guidance = get_title_style_guidance(
                        title_style, title_style_name or "")
                    input_params["title_style_guidance"] = title_style_guidance
                    self.logger.info(
                        f"[单元概述流式] 使用标题风格: {title_style_name} ({title_style})")
                else:
                    input_params["title_style_guidance"] = ""

                # 获取提示词模板（使用默认模板，不需要数据库）
                prompt_template = self.prompt_manager.get_default_prompt(
                    module_name)
                if not prompt_template:
                    raise ValueError(f"未找到提示词模板: {module_name}")

                # 渲染提示词（填充变量）
                filled_prompt = self.prompt_manager.render_prompt(
                    prompt_template, input_params, module_name
                )
                units_to_generate = unit_count

            self.logger.info(
                f"[单元概述流式] 开始生成，模块: {module_name}，单元数: {units_to_generate}")

            # 发送开始生成的工作流事件
            yield self._format_sse("workflow", {
                "type": "step", "step": "generate", "status": "running",
                "message": f"正在生成第{start_from_unit}-{unit_count}章概述..." if is_resume else f"正在生成{unit_count}个单元概述...",
                "icon": "MagicStick"
            })

            # 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(
                self.db, user_id, provider
            )
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            self.logger.info(
                f"[单元概述流式] 使用LLM提供商: {llm_provider.get_model_info()['provider']}")

            self.logger.info(
                f"[单元概述流式] 开始生成 {units_to_generate} 个单元概述，不设置token上限")

            # 流式调用LLM生成（不传递max_tokens，让LLM自主控制输出长度）
            # 提示词中已包含完整性保障指令：LLM接近token上限时必须提前结束并确保最后单元完整
            new_content_chunks = []
            async for chunk in llm_provider.generate_stream(
                prompt=filled_prompt,
                temperature=temperature
            ):
                # 检查是否被取消
                if cancel_event and cancel_event.is_set():
                    self.logger.info("[单元概述流式] 生成被取消")
                    # 发送取消事件
                    yield self._format_sse("workflow", {
                        "type": "cancelled", "message": "生成已取消"
                    })
                    break

                # 使用 SSE 格式包装内容
                if hasattr(chunk, 'content'):
                    new_content_chunks.append(chunk.content)
                    yield self._format_sse("content", {"text": chunk.content})
                elif isinstance(chunk, str):
                    new_content_chunks.append(chunk)
                    yield self._format_sse("content", {"text": chunk})

            # 发送生成完成的工作流事件
            yield self._format_sse("workflow", {
                "type": "step", "step": "generate", "status": "done",
                "message": f"第{start_from_unit}-{unit_count}章概述生成完成" if is_resume else "单元概述生成完成",
                "icon": "MagicStick"
            })

            # ==================== 合并内容 ====================
            new_content = ''.join(new_content_chunks)

            if is_resume:
                # 续生成模式：合并已有内容和新生成内容
                unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
                    content_type, "章"
                )
                full_content = existing_content + "\n\n" + new_content

                # 解析新生成的章节
                # 注意：expected_count 必须使用 unit_count（总目标章节数），而非 units_to_generate
                # 因为 _parse_novel_chapters 使用 expected_count 判断是否为最后一章（end_marker=None），
                # 如果传入 units_to_generate（如25），而章节号从26开始（都>25），
                # 则所有章节都会被当作最后一章处理，导致 full_content 越界截取
                new_parsed = self.parse_unit_summaries(
                    new_content,
                    unit_count,
                    content_type
                )

                # 为新生成的章节添加续生成标记
                # 注意：LLM已经生成了正确的绝对章节号（第51-100章），不需要调整
                adjusted_new_parsed = {}
                skipped_duplicates = []
                out_of_range = []

                for unit_num, data in new_parsed.items():
                    unit_num_int = int(unit_num)

                    # 防御性检查1：跳过已存在的章节号（LLM意外重复生成）
                    if unit_num_int < start_from_unit:
                        skipped_duplicates.append(unit_num_int)
                        self.logger.warning(
                            f"[单元概述续生成] 跳过重复章节: 第{unit_num_int}{unit_label}"
                        )
                        continue

                    # 防御性检查2：跳过超出目标范围的章节号
                    if unit_num_int > unit_count:
                        out_of_range.append(unit_num_int)
                        self.logger.warning(
                            f"[单元概述续生成] 跳过超范围章节: 第{unit_num_int}{unit_label}（目标上限{unit_count}）"
                        )
                        continue

                    adjusted_new_parsed[unit_num] = {
                        **data,
                        "is_resumed": True  # 标记为续生成
                    }

                # 合并已解析的和新生成的（已有章节不会被覆盖）
                full_parsed = {**existing_parsed, **adjusted_new_parsed}

                # 合并后完整性验证日志
                if skipped_duplicates:
                    self.logger.warning(
                        f"[单元概述续生成] 跳过了{len(skipped_duplicates)}个重复章节: "
                        f"{skipped_duplicates[:5]}{'...' if len(skipped_duplicates) > 5 else ''}"
                    )
                if out_of_range:
                    self.logger.warning(
                        f"[单元概述续生成] 跳过了{len(out_of_range)}个超范围章节: "
                        f"{out_of_range[:5]}{'...' if len(out_of_range) > 5 else ''}"
                    )

                self.logger.info(
                    f"[单元概述续生成] 合并完成: 已有{len(existing_parsed)}章 + "
                    f"新生成{len(adjusted_new_parsed)}章 = 总计{len(full_parsed)}章"
                )

                # 验证合并后章节连续性
                expected_total = unit_count
                if len(full_parsed) < expected_total:
                    self.logger.warning(
                        f"[单元概述续生成] 合并后章节数({len(full_parsed)})"
                        f"少于预期({expected_total})，可能需要再次续生成"
                    )
            else:
                # 全新生成模式
                full_content = new_content
                full_parsed = self.parse_unit_summaries(
                    full_content, unit_count, content_type
                )

            # ==================== 截断检测(已禁用) ====================
            # 注意: 截断检测已禁用,现在使用分段生成机制替代
            # expected_count = self.get_expected_unit_count(...)
            # truncation_info = self.detect_truncated_units(...)

            # 记录截断信息为空(保持兼容性)
            # 不再发送truncation_detected事件

            # self.logger.info(
            #     f"[单元概述流式] 截断检测已禁用,使用分段生成机制"
            # )

            # ==================== 后置分层质量管控 ====================
            # 注意：质控功能已移出手动触发流程，用户可在生成完成后点击"质量检测"按钮执行
            # 使用环境变量 ENABLE_QUALITY_CONTROL 控制是否启用
            if ENABLE_QUALITY_CONTROL and enable_quality_control and full_parsed:
                # 注意：_perform_layered_quality_control 是异步生成器，需要使用 async for 迭代
                async for qc_event in self._perform_layered_quality_control(
                    full_parsed=full_parsed,
                    global_outline=global_outline,
                    content_type=content_type,
                    is_resume=is_resume,
                    new_units_start=start_from_unit if is_resume else None,
                    llm_provider=llm_provider,
                    temperature=temperature,
                    workflow_yield=lambda event: event,
                    replace_content_yield=lambda content, msg: (content, msg),
                    user_id=user_id
                ):
                    # 处理质量管控产生的事件
                    if isinstance(qc_event, tuple):
                        # replace_content 事件
                        content, msg = qc_event
                        yield self._format_sse("replace_content", {
                            "content": content,
                            "message": msg
                        })
                    else:
                        # workflow 事件
                        yield self._format_sse("workflow", qc_event)

            # 发送质控提示信息
            yield self._format_sse("workflow", {
                "type": "qc_hint",
                "message": "质控检测已改为手动触发，请在生成完成后点击'质量检测'按钮"
            })

            # 发送完成事件
            yield self._format_sse("workflow", {"type": "complete"})

        except Exception as e:
            self.logger.error(f"[单元概述流式] 生成失败: {str(e)}")
            yield self._format_sse("workflow", {
                "type": "error", "message": f"生成失败: {str(e)}"
            })

    def parse_unit_summaries(
        self,
        content: str,
        expected_count: int,
        content_type: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        解析单元概述内容

        Args:
            content: LLM生成的原始内容
            expected_count: 预期单元数量
            content_type: 内容类型 (novel/script)

        Returns:
            解析后的单元概述字典
        """
        result = {}

        try:
            # 根据内容类型选择解析模式
            if content_type == "novel":
                result = self._parse_novel_chapters(content, expected_count)
            else:
                result = self._parse_script_episodes(content, expected_count)

            self.logger.info(
                f"[单元概述解析] 解析完成，预期: {expected_count}，实际: {len(result)}")

        except Exception as e:
            self.logger.error(f"[单元概述解析] 解析失败: {str(e)}")

        return result

    def _parse_novel_chapters(
        self,
        content: str,
        expected_count: int
    ) -> Dict[str, Dict[str, Any]]:
        """解析小说章节概述"""
        result = {}
        import uuid

        # 匹配章节标题和内容
        # 格式：### 第X章：[章节标题]
        chapter_pattern = r'###\s*第(\d+)章[：:]\s*(.+?)(?:\n|$)'
        matches = re.findall(chapter_pattern, content)

        for match in matches:
            chapter_num = int(match[0])
            chapter_title = match[1].strip()

            # 提取章节概要
            start_marker = f"第{chapter_num}章"
            end_marker = f"第{chapter_num + 1}章" if chapter_num < expected_count else None

            start_idx = content.find(start_marker)
            if start_idx == -1:
                continue

            start_idx = content.find('\n', start_idx)
            if start_idx == -1:
                continue

            if end_marker:
                end_idx = content.find(end_marker, start_idx)
                if end_idx == -1:
                    end_idx = len(content)
            else:
                end_idx = len(content)

            chapter_content = content[start_idx:end_idx].strip()

            # 提取概要
            summary_match = re.search(
                r'\*\*本章梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
                chapter_content, re.DOTALL
            )
            summary = summary_match.group(1).strip() if summary_match else ""

            # v2.1: 为每个单元分配唯一ID
            unit_id = f"unit-{chapter_num}-{uuid.uuid4().hex[:8]}"

            result[str(chapter_num)] = {
                "unit_id": unit_id,
                "unit_number": chapter_num,
                "title": chapter_title,
                "summary": summary,
                "full_content": chapter_content,  # v2.1: 保存完整内容
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }

        return result

    def _parse_script_episodes(
        self,
        content: str,
        expected_count: int
    ) -> Dict[str, Dict[str, Any]]:
        """解析剧本分集/分场概述"""
        result = {}
        import uuid

        # 判断是电影类型还是剧集类型
        is_movie = "第" in content and "场" in content and "集" not in content

        if is_movie:
            pattern = r'\*\*第(\d+)场[：:]\s*(.+?)(?:\n|$)'
        else:
            pattern = r'\*\*第(\d+)集[：:]\s*(.+?)(?:\n|$)'

        matches = re.findall(pattern, content)

        for match in matches:
            unit_num = int(match[0])
            unit_title = match[1].strip()

            if is_movie:
                start_marker = f"第{unit_num}场"
            else:
                start_marker = f"第{unit_num}集"

            start_idx = content.find(start_marker)
            if start_idx == -1:
                continue

            start_idx = content.find('\n', start_idx)
            if start_idx == -1:
                continue

            next_unit = unit_num + 1
            if is_movie:
                end_marker = f"第{next_unit}场"
            else:
                end_marker = f"第{next_unit}集"

            end_idx = content.find(end_marker, start_idx)
            if end_idx == -1:
                end_idx = len(content)

            unit_content = content[start_idx:end_idx].strip()

            if is_movie:
                summary_match = re.search(
                    r'\*\*本场梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
                    unit_content, re.DOTALL
                )
            else:
                summary_match = re.search(
                    r'\*\*本集梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
                    unit_content, re.DOTALL
                )
            summary = summary_match.group(1).strip() if summary_match else ""

            # v2.1: 为每个单元分配唯一ID
            unit_id = f"unit-{unit_num}-{uuid.uuid4().hex[:8]}"

            result[str(unit_num)] = {
                "unit_id": unit_id,
                "unit_number": unit_num,
                "title": unit_title,
                "summary": summary,
                "full_content": unit_content,  # v2.1: 保存完整内容
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }

        return result

    # ==================== 截断检测与接续生成模块 ====================

    def get_expected_unit_count(
        self,
        global_outline: str,
        user_input_count: int = None,
        content_type: str = "novel"
    ) -> int:
        """
        获取预期单元数量(用于截断检测)

        优先级:
        1. 从全局大纲解析的实际单元数(最高)
        2. 用户输入的参数值(次之)
        3. 默认值(最低)

        Args:
            global_outline: 全局大纲内容
            user_input_count: 用户输入的单元数量
            content_type: 内容类型(novel/script)

        Returns:
            预期单元数量
        """
        # 1. 优先从全局大纲解析
        outline_count = self._parse_unit_count_from_outline(
            global_outline, content_type)
        if outline_count and outline_count > 0:
            self.logger.info(
                f"[截断检测] 从全局大纲解析到{outline_count}个单元,使用此值作为expected_count")
            return outline_count

        # 2. 回退到用户输入
        if user_input_count and user_input_count > 0:
            self.logger.info(f"[截断检测] 全局大纲未解析到单元数,使用用户输入:{user_input_count}")
            return user_input_count

        # 3. 使用默认值
        default_count = 50 if content_type == "novel" else 24
        self.logger.warning(f"[截断检测] 无法获取单元数量,使用默认值:{default_count}")
        return default_count

    def _parse_unit_count_from_outline(
        self,
        outline: str,
        content_type: str
    ) -> int:
        """
        从全局大纲内容中解析单元数量

        匹配模式:
        - "共X章" / "总计X章" / "一共X章"
        - "共X集" / "总计X集"
        - "共X场" / "总计X场"
        - "Chapter 1-100" / "第1章至第100章"

        Args:
            outline: 全局大纲内容
            content_type: 内容类型

        Returns:
            解析出的单元数量,失败返回0
        """
        if content_type == "novel":
            patterns = [
                r'共\s*([一二三四五六七八九十百千万\d]+)\s*章',
                r'总计\s*([一二三四五六七八九十百千万\d]+)\s*章',
                r'一共\s*([一二三四五六七八九十百千万\d]+)\s*章',
                r'第\s*1\s*章\s*(?:至|到|~|-)\s*第\s*([一二三四五六七八九十百千万\d]+)\s*章',
            ]
        else:  # script
            patterns = [
                r'共\s*([一二三四五六七八九十百千万\d]+)\s*集',
                r'总计\s*([一二三四五六七八九十百千万\d]+)\s*集',
                r'一共\s*([一二三四五六七八九十百千万\d]+)\s*集',
                r'共\s*([一二三四五六七八九十百千万\d]+)\s*场',
                r'总计\s*([一二三四五六七八九十百千万\d]+)\s*场',
            ]

        for pattern in patterns:
            match = re.search(pattern, outline)
            if match:
                # 获取匹配的数字(可能是第1个或第2个捕获组)
                count_str = match.group(1)
                if match.lastindex == 2:
                    count_str = match.group(2)

                # 中文数字转阿拉伯数字
                if count_str and not count_str.isdigit():
                    count = self._chinese_to_number(count_str)
                else:
                    count = int(count_str) if count_str else 0

                if count > 0:
                    return count

        return 0

    def detect_truncated_units(
        self,
        content: str,
        parsed: Dict[str, Dict[str, Any]],
        expected_count: int,
        content_type: str
    ) -> Dict[str, Any]:
        """
        检测单元概述是否被截断

        Args:
            content: LLM生成的原始内容
            parsed: 解析后的单元概述字典
            expected_count: 预期单元数量
            content_type: 内容类型

        Returns:
            {
                "has_truncation": bool,
                "truncated_units": List[int],  # 被截断的单元号列表
                "missing_units": List[int],     # 完全缺失的单元号列表
                "truncation_details": Dict      # 每个截断单元的详细信息
            }
        """
        result = {
            "has_truncation": False,
            "truncated_units": [],
            "missing_units": [],
            "truncation_details": {}
        }

        try:
            # 1. 数量完整性检测
            parsed_count = len(parsed)
            if parsed_count < expected_count:
                # 检测缺失的单元号
                parsed_units = set(int(k) for k in parsed.keys())
                all_expected_units = set(range(1, expected_count + 1))
                missing_units = sorted(all_expected_units - parsed_units)

                result["missing_units"] = missing_units
                result["has_truncation"] = True

                self.logger.info(
                    f"[截断检测] 数量不完整: 预期{expected_count}个, 实际{parsed_count}个, "
                    f"缺失{len(missing_units)}个单元: {missing_units[:10]}..."
                )

            # 2. 结构完整性检测(检查每个已解析的单元)
            for unit_num_str, unit_data in parsed.items():
                unit_num = int(unit_num_str)
                full_content = unit_data.get("full_content", "")

                # 检测内容是否完整
                is_truncated = self._check_unit_completeness(
                    full_content, content_type, unit_num
                )

                if is_truncated:
                    result["truncated_units"].append(unit_num)
                    result["has_truncation"] = True
                    result["truncation_details"][unit_num] = {
                        "type": "incomplete_structure",
                        "reason": "内容结构不完整(可能因token限制被截断)"
                    }
                    self.logger.warning(
                        f"[截断检测] 第{unit_num}单元结构不完整,可能被截断"
                    )

            if not result["has_truncation"]:
                self.logger.info(
                    f"[截断检测] 完整性检查通过: {parsed_count}/{expected_count}个单元")

        except Exception as e:
            self.logger.error(f"[截断检测] 检测失败: {str(e)}")

        return result

    def _check_unit_completeness(
        self,
        unit_content: str,
        content_type: str,
        unit_num: int
    ) -> bool:
        """
        检查单个单元的内容完整性

        Args:
            unit_content: 单元的完整内容
            content_type: 内容类型
            unit_num: 单元号

        Returns:
            True表示不完整(被截断),False表示完整
        """
        if not unit_content or len(unit_content.strip()) < 50:
            return True

        # 1. 检查结尾是否为完整标点
        stripped = unit_content.rstrip()
        if not stripped:
            return True

        last_char = stripped[-1]
        complete_punctuation = {'。', '！', '？', '”', '）', ']', '}', '…', '\n'}

        if last_char not in complete_punctuation:
            # 结尾不是完整标点,可能被截断
            self.logger.debug(
                f"[完整性检测] 第{unit_num}单元结尾字符'{last_char}'不是完整标点"
            )
            return True

        # 2. 检查必要字段是否存在
        if content_type == "novel":
            # 小说章节应包含"本章梗概"标记
            if "**本章梗概**" not in unit_content and "本章梗概：" not in unit_content:
                self.logger.debug(f"[完整性检测] 第{unit_num}单元缺少'本章梗概'字段")
                return True
        else:
            # 剧本应包含"本集梗概"或"本场梗概"
            if "**本集梗概**" not in unit_content and "本集梗概：" not in unit_content:
                if "**本场梗概**" not in unit_content and "本场梗概：" not in unit_content:
                    self.logger.debug(f"[完整性检测] 第{unit_num}单元缺少梗概字段")
                    return True

        # 3. 检查是否突然中断(最后一句是否完整)
        lines = unit_content.split('\n')
        if lines:
            last_line = lines[-1].strip()
            # 如果最后一行超过50字符且没有标点,可能不完整
            if len(last_line) > 50 and not any(p in last_line for p in {'。', '！', '？', '…'}):
                self.logger.debug(f"[完整性检测] 第{unit_num}单元最后一行过长且无标点")
                return True

        return False

    async def continue_unit_summaries_generation(
        self,
        global_outline: str,
        existing_content: str,
        existing_parsed: Dict[str, Dict[str, Any]],
        truncation_info: Dict[str, Any],
        content_type: str,
        llm_provider,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        接续生成被截断或缺失的单元概述

        Args:
            global_outline: 全局大纲内容
            existing_content: 已生成的内容
            existing_parsed: 已解析的单元概述
            truncation_info: 截断检测信息
            content_type: 内容类型
            llm_provider: LLM提供者
            temperature: 温度参数

        Returns:
            {
                "success": bool,
                "continued_content": str,
                "continued_parsed": Dict,
                "continued_units": List[int]
            }
        """
        result = {
            "success": False,
            "continued_content": existing_content,
            "continued_parsed": existing_parsed,
            "continued_units": [],
            "error": None,
            "history": []  # 新增:接续历史记录
        }

        try:
            missing_units = truncation_info.get("missing_units", [])
            truncated_units = truncation_info.get("truncated_units", [])

            if not missing_units and not truncated_units:
                result["success"] = True
                return result

            self.logger.info(
                f"[接续生成] 开始接续{len(missing_units)}个缺失单元, "
                f"{len(truncated_units)}个不完整单元"
            )

            # 1. 生成缺失的单元
            if missing_units:
                # 记录接续历史(新增)
                result["history"].append({
                    "type": "generate_missing",
                    "units": missing_units,
                    "count": len(missing_units),
                    "timestamp": "now"
                })

                missing_content = await self._generate_missing_units(
                    global_outline=global_outline,
                    existing_parsed=existing_parsed,
                    missing_units=missing_units,
                    content_type=content_type,
                    llm_provider=llm_provider,
                    temperature=temperature
                )

                if missing_content:
                    existing_content += "\n\n" + missing_content
                    result["continued_units"].extend(missing_units)
                    self.logger.info(f"[接续生成] 缺失单元生成完成: {missing_units}")

            # 2. 接续不完整的单元(新增)
            if truncated_units:
                for unit_num in truncated_units:
                    unit_data = existing_parsed.get(str(unit_num))
                    if unit_data:
                        original_content = unit_data.get("full_content", "")

                        continued_unit = await self._continue_single_unit(
                            global_outline=global_outline,
                            unit_num=unit_num,
                            truncated_content=original_content,
                            content_type=content_type,
                            llm_provider=llm_provider,
                            temperature=temperature
                        )

                        if continued_unit:
                            # 记录接续历史(新增)
                            result["history"].append({
                                "unit_num": unit_num,
                                "type": "continue_single",
                                "original_length": len(original_content),
                                "continued_length": len(continued_unit),
                                "timestamp": "now"
                            })

                            # 安全替换原有内容(修复:防止空字符串误替换)
                            if original_content and original_content in existing_content:
                                existing_content = existing_content.replace(
                                    original_content,
                                    continued_unit,
                                    1  # 只替换第一次出现
                                )
                                result["continued_units"].append(unit_num)
                                self.logger.info(f"[接续生成] 第{unit_num}单元接续完成")
                            else:
                                self.logger.warning(
                                    f"[接续生成] 第{unit_num}单元原始内容为空或未找到,跳过替换"
                                )

            # 3. 质量验证(新增)
            quality_check = await self._validate_continuation_quality(
                original_parsed=existing_parsed,
                continued_content=existing_content,
                content_type=content_type,
                continued_units=result["continued_units"]
            )

            result["quality_validation"] = quality_check

            if not quality_check["passed"]:
                self.logger.warning(
                    f"[接续生成] 质量验证未通过: {quality_check['issues']}")
                # 不阻断流程,仅记录警告

            # 4. 重新解析合并后的内容
            expected_unit_count = len(original_parsed)
            if result["continued_units"]:
                expected_unit_count = max(
                    expected_unit_count, max(result["continued_units"]))

            new_parsed = self.parse_unit_summaries(
                continued_content, expected_unit_count, content_type
            )

            if new_parsed and len(new_parsed) >= len(existing_parsed):
                result["success"] = True
                result["continued_content"] = existing_content
                result["continued_parsed"] = new_parsed

                self.logger.info(
                    f"[接续生成] 完成: 原{len(existing_parsed)}个单元 → "
                    f"新{len(new_parsed)}个单元"
                )
            else:
                result["error"] = "接续后重新解析失败"
                self.logger.error(f"[接续生成] {result['error']}")

        except Exception as e:
            self.logger.error(f"[接续生成] 失败: {str(e)}")
            result["error"] = str(e)

        return result

    async def _generate_missing_units(
        self,
        global_outline: str,
        existing_parsed: Dict[str, Dict[str, Any]],
        missing_units: List[int],
        content_type: str,
        llm_provider,
        temperature: float = 0.7,
        max_batch_size: int = 20  # 新增:批量大小限制
    ) -> str:
        """
        生成缺失的单元概述(支持批量优化和智能重试)

        Args:
            global_outline: 全局大纲
            existing_parsed: 已存在的单元概述
            missing_units: 缺失的单元号列表
            content_type: 内容类型
            llm_provider: LLM提供者
            temperature: 温度参数
            max_batch_size: 每批最大生成单元数(默认20)

        Returns:
            新生成的单元概述内容
        """
        all_content = []

        # 创建副本避免修改原对象(修复:防止副作用)
        working_parsed = {k: v for k, v in existing_parsed.items()}

        try:
            # 批量优化:如果缺失单元超过max_batch_size,分批生成
            if len(missing_units) > max_batch_size:
                self.logger.info(
                    f"[批量接续] 缺失单元{len(missing_units)}个,超过阈值{max_batch_size},开始分批生成"
                )

                # 分批处理
                batches = [
                    missing_units[i:i+max_batch_size]
                    for i in range(0, len(missing_units), max_batch_size)
                ]

                for batch_idx, batch_units in enumerate(batches, 1):
                    self.logger.info(
                        f"[批量接续] 处理第{batch_idx}/{len(batches)}批: {batch_units[0]}-{batch_units[-1]}"
                    )

                    # 智能重试:每批最多重试3次
                    batch_content = None
                    max_retries = 3

                    for retry in range(max_retries):
                        try:
                            batch_content = await self._generate_units_batch(
                                global_outline=global_outline,
                                existing_parsed=existing_parsed,
                                missing_units=batch_units,
                                content_type=content_type,
                                llm_provider=llm_provider,
                                temperature=temperature
                            )

                            if batch_content and len(batch_content) > 100:
                                # 验证生成质量
                                if "**" in batch_content or "梗概" in batch_content:
                                    self.logger.info(
                                        f"[批量接续] 第{batch_idx}批生成成功(尝试{retry+1}/{max_retries})"
                                    )
                                    break
                                else:
                                    self.logger.warning(
                                        f"[批量接续] 第{batch_idx}批内容格式异常,重试..."
                                    )
                            else:
                                self.logger.warning(
                                    f"[批量接续] 第{batch_idx}批内容为空或过短,重试..."
                                )

                        except Exception as e:
                            self.logger.error(
                                f"[批量接续] 第{batch_idx}批生成异常(尝试{retry+1}/{max_retries}): {str(e)}"
                            )

                        # 重试前等待(指数退避)
                        if retry < max_retries - 1:
                            import asyncio
                            wait_time = 2 ** retry  # 1s, 2s, 4s
                            self.logger.info(f"[批量接续] 等待{wait_time}秒后重试...")
                            await asyncio.sleep(wait_time)

                    if batch_content:
                        all_content.append(batch_content)

                        # 更新working_parsed用于下一批的参考(使用副本)
                        temp_content = "\n\n".join(all_content)
                        temp_parsed = self.parse_unit_summaries(
                            temp_content, len(all_content), content_type
                        )
                        if temp_parsed:
                            working_parsed.update(temp_parsed)
                    else:
                        self.logger.error(
                            f"[批量接续] 第{batch_idx}批生成失败,跳过"
                        )
            else:
                # 少量单元,直接生成(带重试)
                max_retries = 3

                for retry in range(max_retries):
                    try:
                        content = await self._generate_units_batch(
                            global_outline=global_outline,
                            existing_parsed=existing_parsed,
                            missing_units=missing_units,
                            content_type=content_type,
                            llm_provider=llm_provider,
                            temperature=temperature
                        )

                        if content and len(content) > 100:
                            if "**" in content or "梗概" in content:
                                self.logger.info(
                                    f"[接续生成] 生成成功(尝试{retry+1}/{max_retries})"
                                )
                                all_content.append(content)
                                break
                            else:
                                self.logger.warning(
                                    f"[接续生成] 内容格式异常,重试..."
                                )
                        else:
                            self.logger.warning(
                                f"[接续生成] 内容为空或过短,重试..."
                            )

                    except Exception as e:
                        self.logger.error(
                            f"[接续生成] 生成异常(尝试{retry+1}/{max_retries}): {str(e)}"
                        )

                    # 重试前等待(指数退避)
                    if retry < max_retries - 1:
                        import asyncio
                        wait_time = 2 ** retry  # 1s, 2s, 4s
                        self.logger.info(f"[接续生成] 等待{wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)

            return "\n\n".join(all_content) if all_content else ""

        except Exception as e:
            self.logger.error(f"[接续生成] 生成缺失单元失败: {str(e)}")
            return ""

    async def _generate_units_batch(
        self,
        global_outline: str,
        existing_parsed: Dict[str, Dict[str, Any]],
        missing_units: List[int],
        content_type: str,
        llm_provider,
        temperature: float = 0.7
    ) -> str:
        """
        生成一批单元概述(内部方法,不含重试逻辑)
        """
        try:
            # 获取前序单元作为参考
            previous_units_text = self._build_previous_units_reference(
                existing_parsed, content_type, max_units=5
            )

            start_num = min(missing_units)
            end_num = max(missing_units)
            # 统一使用content_type判断(修复:与_continue_single_unit保持一致)
            unit_label = "章" if content_type == "novel" else (
                "集" if content_type == "series_script" else "场"
            )

            prompt = f"""你是专业的创意写作顾问。

## 任务
以下单元概述缺失,请根据全局大纲和已生成的前序单元,生成这些单元的概述。

## 全局大纲(参考故事结构)
{global_outline[:1500]}

## 已生成的前序单元(参考情节连贯性)
{previous_units_text}

## 需要生成的单元
- 第{start_num}{unit_label} 至 第{end_num}{unit_label}

## 生成要求
1. 保持与前序单元的情节连贯性
2. 遵循全局大纲的故事结构
3. 确保每个单元的概述完整(包含标题、梗概等)
4. 严格按照以下格式输出:

"""

            if content_type == "novel":
                prompt += """### 第X章：[章节标题]
**本章梗概**：[概述内容，200-300字]

"""
            else:
                prompt += """**第X集**：[集标题]
**本集梗概**：[概述内容，200-300字]

"""

            prompt += f"""
## 开始生成
请从第{start_num}{unit_label}开始生成,一直到第{end_num}{unit_label}。
"""

            response = await llm_provider.generate(
                prompt=prompt,
                temperature=temperature
            )

            content = response.content if hasattr(
                response, 'content') else str(response)
            return content

        except Exception as e:
            self.logger.error(f"[接续生成] 生成缺失单元失败: {str(e)}")
            return ""

    async def _continue_single_unit(
        self,
        global_outline: str,
        unit_num: int,
        truncated_content: str,
        content_type: str,
        llm_provider,
        temperature: float = 0.7
    ) -> str:
        """
        接续单个不完整的单元

        Args:
            global_outline: 全局大纲
            unit_num: 单元号
            truncated_content: 被截断的内容
            content_type: 内容类型
            llm_provider: LLM提供者
            temperature: 温度参数

        Returns:
            接续后的完整内容
        """
        try:
            # 分析截断位置
            lines = truncated_content.strip().split('\n')
            last_line = lines[-1] if lines else ""

            # 提取已有信息
            title = ""
            summary_so_far = ""

            if content_type == "novel":
                # 提取标题
                for line in lines:
                    if line.strip().startswith("### 第"):
                        title_match = re.search(r'### 第\d+章[：:]\s*(.+)', line)
                        if title_match:
                            title = title_match.group(1).strip()
                            break

                # 提取已有梗概
                summary_start = -1
                for i, line in enumerate(lines):
                    if "**本章梗概**" in line or "本章梗概：" in line:
                        summary_start = i
                        break

                if summary_start >= 0:
                    summary_so_far = '\n'.join(lines[summary_start:])
            else:
                # 剧本类似
                for line in lines:
                    if line.strip().startswith("**第"):
                        title_match = re.search(
                            r'\*\*第\d+[集场][：:]\s*\*\*(.+?)\*\*', line)
                        if title_match:
                            title = title_match.group(1).strip()
                            break

                summary_start = -1
                for i, line in enumerate(lines):
                    if "**本集梗概**" in line or "本集梗概：" in line:
                        summary_start = i
                        break
                    if "**本场梗概**" in line or "本场梗概：" in line:
                        summary_start = i
                        break

                if summary_start >= 0:
                    summary_so_far = '\n'.join(lines[summary_start:])

            unit_label = "章" if content_type == "novel" else (
                "集" if content_type == "series_script" else "场")

            prompt = f"""你是专业的创意写作顾问。

## 任务
第{unit_num}{unit_label}的概述被截断,请根据已有内容接续完成。

## 全局大纲(参考故事结构)
{global_outline[:1000]}

## 已有内容(从断点处接续)
{truncated_content}

## 截断分析
- 最后一行: "{last_line}"
- 问题: 内容不完整,需要补充完整

## 接续要求
1. 从断点处自然接续,不要重复已有内容
2. 保持与前文的情节连贯性
3. 遵循全局大纲的故事结构
4. 确保接续后内容完整(包含所有必要字段)
5. 梗概内容应达到200-300字

## 输出格式
请只输出接续部分,不要包含已有的内容。
"""

            response = await llm_provider.generate(
                prompt=prompt,
                temperature=temperature
            )

            continued_part = response.content if hasattr(
                response, 'content') else str(response)

            # 合并已有内容和接续部分
            full_content = truncated_content + "\n" + continued_part

            return full_content

        except Exception as e:
            self.logger.error(f"[接续生成] 接续第{unit_num}单元失败: {str(e)}")
            return ""

    async def _validate_continuation_quality(
        self,
        original_parsed: Dict[str, Dict[str, Any]],
        continued_content: str,
        content_type: str,
        continued_units: List[int]
    ) -> Dict[str, Any]:
        """
        验证接续生成的质量

        Args:
            original_parsed: 原始解析结果
            continued_content: 接续后的内容
            content_type: 内容类型
            continued_units: 接续的单元号列表

        Returns:
            {
                "passed": bool,
                "issues": List[str],
                "metrics": Dict
            }
        """
        result = {
            "passed": True,
            "issues": [],
            "metrics": {}
        }

        try:
            # 防御性检查:验证continued_units有效性
            if continued_units and any(u < 1 for u in continued_units):
                result["issues"].append(f"接续单元号包含无效值: {continued_units}")
                result["passed"] = False
                return result

            # 重新解析接续后的内容
            expected_count = len(original_parsed)
            if continued_units:
                expected_count = max(expected_count, max(continued_units))

            new_parsed = self.parse_unit_summaries(
                continued_content,
                expected_count,
                content_type
            )

            if not new_parsed:
                result["passed"] = False
                result["issues"].append("接续后无法解析内容")
                return result

            # 验证1: 单元数量检查
            expected_count = max(len(original_parsed), len(new_parsed))
            if len(new_parsed) < expected_count:
                result["issues"].append(
                    f"单元数量不足: 预期{expected_count},实际{len(new_parsed)}")
                result["passed"] = False

            # 验证2: 接续单元完整性检查
            for unit_num in continued_units:
                unit_data = new_parsed.get(str(unit_num))
                if not unit_data:
                    result["issues"].append(f"第{unit_num}单元解析失败")
                    result["passed"] = False
                    continue

                # 检查必要字段
                full_content = unit_data.get("full_content", "")
                title = unit_data.get("title", "")
                summary = unit_data.get("summary", "")

                if not title:
                    result["issues"].append(f"第{unit_num}单元缺少标题")
                    result["passed"] = False

                if not summary or len(summary) < 50:
                    result["issues"].append(
                        f"第{unit_num}单元梗概过短({len(summary)}字)")
                    result["passed"] = False

                # 检查结构完整性
                if content_type == "novel":
                    if "**本章梗概**" not in full_content and "本章梗概：" not in full_content:
                        result["issues"].append(f"第{unit_num}单元缺少梗概字段")
                        result["passed"] = False
                else:
                    if "**本集梗概**" not in full_content and "本集梗概：" not in full_content:
                        if "**本场梗概**" not in full_content and "本场梗概：" not in full_content:
                            result["issues"].append(f"第{unit_num}单元缺少梗概字段")
                            result["passed"] = False

            # 验证3: 内容连贯性检查(启发式)
            # 检查接续单元与前序单元的主题连贯性
            sorted_units = sorted(new_parsed.items(), key=lambda x: int(x[0]))
            for i, (unit_num, unit_data) in enumerate(sorted_units):
                if int(unit_num) in continued_units and i > 0:
                    prev_unit = sorted_units[i-1][1]
                    prev_summary = prev_unit.get("summary", "")
                    curr_summary = unit_data.get("summary", "")

                    # 简单检查:如果梗概完全相同,可能有问题
                    if prev_summary and curr_summary and prev_summary == curr_summary:
                        result["issues"].append(f"第{unit_num}单元梗概与前序单元重复")
                        result["passed"] = False

            # 记录指标
            result["metrics"] = {
                "total_units": len(new_parsed),
                "continued_units_count": len(continued_units),
                "avg_summary_length": sum(
                    len(u.get("summary", "")) for u in new_parsed.values()
                ) / len(new_parsed) if new_parsed else 0
            }

        except Exception as e:
            self.logger.error(f"[接续生成] 质量验证失败: {str(e)}")
            result["passed"] = False
            result["issues"].append(f"质量验证异常: {str(e)}")

        return result

    def _build_previous_units_reference(
        self,
        parsed: Dict[str, Dict[str, Any]],
        content_type: str,
        max_units: int = 5
    ) -> str:
        """
        构建前序单元的参考文本

        Args:
            parsed: 单元概述字典
            content_type: 内容类型
            max_units: 最多包含的单元数

        Returns:
            前序单元参考文本
        """
        units_text = []
        unit_label = "章" if content_type == "novel" else (
            "集" if content_type == "series_script" else "场")

        # 获取最后max_units个单元
        sorted_units = sorted(parsed.items(), key=lambda x: int(x[0]))
        recent_units = sorted_units[-max_units:] if len(
            sorted_units) > max_units else sorted_units

        for unit_num, unit_data in recent_units:
            title = unit_data.get("title", "")
            summary = unit_data.get("summary", "")

            units_text.append(
                f"第{unit_num}{unit_label}《{title}》：{summary[:150]}")

        return "\n".join(units_text) if units_text else "（无前序单元）"

    async def _revise_with_knowledge_base(
        self,
        llm_provider,
        original_content: str,
        input_params: Dict[str, Any],
        temperature: float = 0.7,
        db: AsyncSession = None,
        user_id: int = None,
        content_type: str = "script"
    ) -> Optional[str]:
        """
        使用知识库修正大纲内容

        直接生成修正后的完整内容，替换原始内容

        Args:
            llm_provider: LLM提供者
            original_content: 原始大纲内容
            input_params: 输入参数
            temperature: 温度参数
            db: 数据库会话（用于知识库检索）
            user_id: 用户ID（用于知识库检索）
            content_type: 内容类型（用于确定检索模块）

        Returns:
            修正后的内容，如果修正失败返回None
        """
        # 常量定义 - 已禁用截断
        MIN_REVISION_LENGTH = 100  # 修正结果最小长度阈值

        try:
            # 检查是否有必要的参数进行知识库检索
            if not db or not user_id:
                self.logger.info("[知识库修正] 缺少db或user_id参数，跳过知识库修正")
                return None

            # 获取 orchestrator 实例（用于知识库检索）
            orchestrator = get_agent_orchestrator()

            # 构建查询文本（使用原始内容的关键信息）
            # 注意：input_params 的值可能是列表，需要转换为字符串
            def _safe_get_str(params, key, default=''):
                """安全获取字符串值，处理列表类型"""
                val = params.get(key, default)
                if isinstance(val, list):
                    return ' '.join(str(v) for v in val)
                return str(val) if val else default

            query_text = (_safe_get_str(input_params, 'title') + " " +
                          _safe_get_str(input_params, 'theme') + " " +
                          _safe_get_str(input_params, 'genre')).strip()

            # 不再截断查询文本
            if not query_text.strip():
                query_text = original_content  # 使用完整内容

            # 确定模块名称
            module_name = f"{content_type}_global_outline"

            # 使用 orchestrator 的知识库检索方法（检索三类知识库）
            kb_contexts = await orchestrator._retrieve_classified_knowledge(
                db=db,
                user_id=user_id,
                module=module_name,
                query_text=query_text,
                kb_vertical=True,  # 启用垂直领域知识库
                kb_user_specific=False,  # 暂不启用用户专属
                kb_manual=True  # 启用官方手册
            )

            # 检查是否有知识库内容
            theory_context = kb_contexts.get('theory', '').strip()
            case_context = kb_contexts.get('case', '').strip()
            manual_context = kb_contexts.get('manual', '').strip()

            if not theory_context and not case_context and not manual_context:
                self.logger.info("[知识库修正] 无相关知识点，跳过修正")
                return None

            # 不再截断大纲内容，直接使用完整内容

            # 构建修正提示词
            revision_prompt = OUTLINE_REVISION_PROMPT.format(
                original_outline=original_content,  # 使用完整内容
                theory_context=theory_context or "无相关理论",
                case_context=case_context or "无相关案例",
                manual_context=manual_context or "无规范手册"
            )

            # 调用LLM进行修正
            response = await llm_provider.generate(
                prompt=revision_prompt,
                temperature=temperature
            )

            revised_content = response.content if hasattr(
                response, 'content') else str(response)

            # 验证修正后的内容
            if revised_content and len(revised_content) > MIN_REVISION_LENGTH:
                self.logger.info(
                    f"[知识库修正] 修正成功，原长度={len(original_content)}，新长度={len(revised_content)}")
                return revised_content
            else:
                self.logger.warning(
                    f"[知识库修正] 修正结果长度不足（{len(revised_content) if revised_content else 0}字符），使用原始内容")
                return None

        except Exception as e:
            self.logger.error(f"[知识库修正] 修正失败: {str(e)}")
            return None

    async def check_and_fix_logic_issues(
        self,
        global_outline: str,
        unit_summaries: Dict[str, Dict[str, Any]],
        content_type: str,
        provider: str = None,
        temperature: float = 0.7,
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        检测并修正单元概述中的逻辑问题

        Args:
            global_outline: 全局大纲内容
            unit_summaries: 单元概述字典
            content_type: 内容类型 (novel/script)
            provider: LLM提供商
            temperature: 温度参数
            user_id: 用户ID

        Returns:
            修正结果，包含问题列表和修正后的单元概述
        """
        result = {
            "has_issues": False,
            "issues": [],
            "revised_units": {},
            "original_units": {},  # 保存原始单元内容，用于前端差异对比
            "error": None
        }

        try:
            # 格式化单元概述列表
            formatted_units = self._format_unit_summaries_for_check(
                unit_summaries)

            if not formatted_units:
                self.logger.info("[逻辑检测] 无单元概述内容，跳过检测")
                return result

            # 构建检测提示词
            check_prompt = LOGIC_CHECK_PROMPT.format(
                global_outline=global_outline,  # 使用完整内容
                unit_summaries=formatted_units
            )

            self.logger.info(f"[逻辑检测] 开始检测，单元数: {len(unit_summaries)}")

            # 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(
                self.db, user_id, provider
            )
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            # 调用LLM进行检测
            response = await llm_provider.generate(
                prompt=check_prompt,
                temperature=temperature
            )

            response_content = response.content if hasattr(
                response, 'content') else str(response)

            # 记录响应内容以便调试
            self.logger.debug(f"[逻辑检测] LLM响应长度: {len(response_content)}")
            self.logger.debug(f"[逻辑检测] LLM响应前500字符: {response_content[:500]}")

            # 解析JSON响应
            parsed_result = self._parse_logic_check_response(response_content)

            if parsed_result:
                result["has_issues"] = parsed_result.get("has_issues", False)

                # 规范化 issues 中的 unit_number
                issues = parsed_result.get("issues", [])
                for issue in issues:
                    if "unit_number" in issue:
                        # 提取 unit_number 中的数字部分
                        num_match = re.search(
                            r'(\d+)', str(issue["unit_number"]))
                        if num_match:
                            issue["unit_number"] = num_match.group(1)
                result["issues"] = issues

                revised_units = parsed_result.get("revised_units", {})

                # 规范化 revised_units 的 key（确保是纯数字字符串）
                normalized_revised_units = {}
                for key, value in revised_units.items():
                    # 提取 key 中的数字部分
                    num_match = re.search(r'(\d+)', str(key))
                    if num_match:
                        normalized_key = num_match.group(1)
                        normalized_revised_units[normalized_key] = value
                        self.logger.debug(
                            f"[逻辑检测] 规范化 key: '{key}' -> '{normalized_key}'")
                    else:
                        # 如果没有数字，保留原始 key
                        normalized_revised_units[str(key)] = value
                        self.logger.warning(f"[逻辑检测] 无法从 key '{key}' 中提取数字")
                result["revised_units"] = normalized_revised_units

                # 保存被修正单元的原始内容，用于前端差异对比
                if normalized_revised_units:
                    original_units = {}
                    unit_summaries_keys = list(unit_summaries.keys())
                    self.logger.debug(
                        f"[逻辑检测] unit_summaries 的 keys: {unit_summaries_keys[:10]}...")
                    for unit_num in normalized_revised_units.keys():
                        self.logger.debug(
                            f"[逻辑检测] 检查 unit_num '{unit_num}' 是否在 unit_summaries 中: {unit_num in unit_summaries}")
                        if unit_num in unit_summaries:
                            original_units[unit_num] = {
                                "title": unit_summaries[unit_num].get("title", ""),
                                "summary": unit_summaries[unit_num].get("summary", "")
                            }
                    result["original_units"] = original_units
                    self.logger.info(
                        f"[逻辑检测] 保存了 {len(original_units)} 个原始单元内容")

                if result["has_issues"]:
                    self.logger.info(
                        f"[逻辑检测] 检测到 {len(result['issues'])} 个问题，"
                        f"修正 {len(result['revised_units'])} 个单元"
                    )
                else:
                    self.logger.info("[逻辑检测] 未检测到逻辑问题")
            else:
                self.logger.warning("[逻辑检测] 响应解析失败")

        except Exception as e:
            import traceback
            self.logger.error(f"[逻辑检测] 检测失败: {str(e)}")
            self.logger.error(f"[逻辑检测] 异常类型: {type(e).__name__}")
            self.logger.error(f"[逻辑检测] 堆栈跟踪: {traceback.format_exc()}")
            result["error"] = str(e)

        return result

    def _format_unit_summaries_for_check(
        self,
        unit_summaries: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        格式化单元概述用于逻辑检测

        Args:
            unit_summaries: 单元概述字典

        Returns:
            格式化后的文本
        """
        lines = []
        for unit_num in sorted(unit_summaries.keys(), key=lambda x: int(x) if x.isdigit() else 0):
            unit = unit_summaries[unit_num]
            title = unit.get("title", "")
            summary = unit.get("summary", "")
            lines.append(f"### 单元 {unit_num}: {title}")
            lines.append(summary)
            lines.append("")
        return "\n".join(lines)

    def _parse_logic_check_response(self, response_content: str) -> Optional[Dict[str, Any]]:
        """
        解析逻辑检测响应

        Args:
            response_content: LLM响应内容

        Returns:
            解析后的结果字典
        """
        try:
            # 记录原始响应以便调试
            self.logger.debug(f"[逻辑检测] 原始响应长度: {len(response_content)}")

            # 尝试提取JSON块
            json_match = re.search(
                r'```json\s*([\s\S]*?)\s*```',
                response_content
            )
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试查找JSON对象的开始和结束
                start_idx = response_content.find('{')
                end_idx = response_content.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = response_content[start_idx:end_idx + 1]
                else:
                    json_str = response_content

            # 清理可能的注释和多余空白
            json_str = json_str.strip()

            # 记录提取的JSON字符串前200字符
            self.logger.debug(f"[逻辑检测] 提取的JSON前200字符: {json_str[:200]}")

            # 解析JSON
            parsed = json.loads(json_str)

            # 验证必要字段
            if "has_issues" in parsed:
                return {
                    "has_issues": parsed.get("has_issues", False),
                    "issues": parsed.get("issues", []),
                    "revised_units": parsed.get("revised_units", {})
                }

            return None

        except json.JSONDecodeError as e:
            self.logger.error(
                f"[逻辑检测] JSON解析失败: {str(e)}, 位置: {e.pos if hasattr(e, 'pos') else 'unknown'}")
            self.logger.error(
                f"[逻辑检测] 问题JSON片段: {json_str[max(0, e.pos-50):e.pos+50] if hasattr(e, 'pos') and e.pos else json_str[:100]}")
            return None
        except Exception as e:
            self.logger.error(f"[逻辑检测] 响应解析失败: {str(e)}")
            return None

    async def _analyze_unit_summaries_quality(
        self,
        qc_service: Any,
        chapters_data: List[Dict],
        dimensions: List[str],
        depth: str = "deep",
        global_outline: str = "",
        character_profiles: List[Dict] = None,
        worldview_settings: Dict = None,
        db: Any = None,
        user_id: int = 0,
        project_id: int = 0
    ) -> Dict[str, Any]:
        """
        分析单元概述质量（使用专用的单元概述五维度质控机制）

        五维度检测：
        1. unit_structure（单元结构层）- 单元长度分布、衔接流畅度、情节节奏
        2. unit_character（人物发展层）- 人物状态变化、关系逻辑
        3. unit_consistency（一致性层）- 与全局大纲的偏离度、核心要素完整性
        4. unit_timeline_space（时间线与空间逻辑层）- 人物位置、出场时间线、事件因果、状态连续性
        5. unit_ooc（人物OOC层）- 人物行为是否违背人设

        Args:
            qc_service: QualityControlService 实例
            chapters_data: 章节数据列表
            dimensions: 分析维度
            depth: 分析深度（v3.0强制deep）
            global_outline: 全局大纲内容
            user_id: 用户ID
            project_id: 项目ID

        Returns:
            质量报告字典
        """
        try:
            # 导入专用的单元概述分析器
            from app.services.quality_control.analyzers.unit_quality_analyzer import (
                UnitStructureAnalyzer,
                UnitCharacterAnalyzer,
                UnitConsistencyAnalyzer,
                UnitTimelineSpaceAnalyzer,
                UnitOOCAnalyzer
            )

            # 创建虚拟项目对象（单元概述阶段还没有project_id）
            class VirtualProject:
                def __init__(self):
                    self.id = project_id
                    self.title = "单元概述"
                    self.genre = ""
                    self.target_audience = ""
                    self.style_tags = []
                    # 使用传入的真实数据，而非空字典
                    self.character_profiles = character_profiles or {}
                    self.world_settings = worldview_settings or {}
                    self.plot_outline = global_outline

            virtual_project = VirtualProject()

            # 执行五个维度的分析
            all_issues = []
            dimension_scores = {}
            total_tokens = 0
            cross_validation_data = None

            # 维度1: 单元结构层
            if "unit_structure" in dimensions:
                self.logger.info("[单元概述质控] 开始单元结构层检测...")
                structure_analyzer = UnitStructureAnalyzer()
                structure_result = await structure_analyzer.analyze(
                    chapters_data=chapters_data,
                    project=virtual_project,
                    depth=depth,
                    db=db or self.db,
                    user_id=user_id,
                    global_outline=global_outline,
                    character_profiles=virtual_project.character_profiles,  # v2.0新增
                    worldview_settings=virtual_project.world_settings  # v2.0新增
                )
                all_issues.extend(structure_result.get("issues", []))
                dimension_scores["unit_structure"] = structure_result.get(
                    "score", 50)
                total_tokens += structure_result.get("tokens", 0)
                self.logger.info(
                    f"[单元概述质控] 单元结构层完成，得分: {structure_result.get('score', 50)}")

            # 维度2: 人物发展层
            if "unit_character" in dimensions:
                self.logger.info("[单元概述质控] 开始人物发展层检测...")
                character_analyzer = UnitCharacterAnalyzer()
                character_result = await character_analyzer.analyze(
                    chapters_data=chapters_data,
                    project=virtual_project,
                    depth=depth,
                    global_outline=global_outline,
                    character_profiles=virtual_project.character_profiles,  # v2.0新增
                    db=db or self.db,
                    user_id=user_id
                )
                all_issues.extend(character_result.get("issues", []))
                dimension_scores["unit_character"] = character_result.get(
                    "score", 50)
                total_tokens += character_result.get("tokens", 0)
                self.logger.info(
                    f"[单元概述质控] 人物发展层完成，得分: {character_result.get('score', 50)}")

            # 维度3: 一致性层
            if "unit_consistency" in dimensions:
                self.logger.info("[单元概述质控] 开始一致性层检测...")
                consistency_analyzer = UnitConsistencyAnalyzer()
                consistency_result = await consistency_analyzer.analyze(
                    chapters_data=chapters_data,
                    project=virtual_project,
                    depth=depth,
                    db=db or self.db,
                    user_id=user_id,
                    global_outline=global_outline,
                    character_profiles=virtual_project.character_profiles,  # v2.0新增
                    worldview_settings=virtual_project.world_settings  # v2.0新增
                )
                all_issues.extend(consistency_result.get("issues", []))
                dimension_scores["unit_consistency"] = consistency_result.get(
                    "score", 50)
                total_tokens += consistency_result.get("tokens", 0)

            # v2.0新增: 提取交叉验证数据
                cross_validation_data = consistency_result.get(
                    "cross_validation")

                self.logger.info(
                    f"[单元概述质控] 一致性层完成，得分: {consistency_result.get('score', 50)}")

            # 维度4: 时间线与空间逻辑层
            if "unit_timeline_space" in dimensions:
                self.logger.info("[单元概述质控] 开始时间线与空间逻辑层检测...")
                timeline_analyzer = UnitTimelineSpaceAnalyzer()
                timeline_result = await timeline_analyzer.analyze(
                    chapters_data=chapters_data,
                    project=virtual_project,
                    depth=depth,
                    db=db or self.db,
                    user_id=user_id,
                    global_outline=global_outline,
                    character_profiles=virtual_project.character_profiles,
                    worldview_settings=virtual_project.world_settings
                )
                all_issues.extend(timeline_result.get("issues", []))
                dimension_scores["unit_timeline_space"] = timeline_result.get(
                    "score", 50)
                total_tokens += timeline_result.get("tokens", 0)
                self.logger.info(
                    f"[单元概述质控] 时间线空间层完成，得分: {timeline_result.get('score', 50)}")

            # 维度5: 人物OOC层
            if "unit_ooc" in dimensions:
                self.logger.info("[单元概述质控] 开始人物OOC层检测...")
                ooc_analyzer = UnitOOCAnalyzer()
                ooc_result = await ooc_analyzer.analyze(
                    chapters_data=chapters_data,
                    project=virtual_project,
                    depth=depth,
                    db=db or self.db,
                    user_id=user_id,
                    global_outline=global_outline,
                    character_profiles=virtual_project.character_profiles,
                    worldview_settings=virtual_project.world_settings
                )
                all_issues.extend(ooc_result.get("issues", []))
                dimension_scores["unit_ooc"] = ooc_result.get(
                    "score", 50)
                total_tokens += ooc_result.get("tokens", 0)
                self.logger.info(
                    f"[单元概述质控] 人物OOC层完成，得分: {ooc_result.get('score', 50)}")

            # 计算综合评分
            overall_score = (
                sum(dimension_scores.values()) / len(dimension_scores)
                if dimension_scores else 0
            )

            # 构建质量报告
            # v2.1: 为每个issue添加auto_fix字段(初始为None,用户点击时动态生成)
            issues_with_auto_fix = []
            for issue in all_issues:
                issue_with_fix = issue.copy()
                issue_with_fix["auto_fix"] = None  # 初始为None
                issues_with_auto_fix.append(issue_with_fix)

            report = {
                "overall_score": round(overall_score, 2),
                "dimension_scores": dimension_scores,
                "issues": issues_with_auto_fix,
                "project_id": project_id,  # v2.1新增: 添加项目ID
                "statistics": {
                    "total_tokens": total_tokens,
                    "total_units": len(chapters_data),
                    "critical_issues": len([i for i in all_issues if i.get("severity") == "critical"]),
                    "warning_issues": len([i for i in all_issues if i.get("severity") == "warning"])
                }
            }

            # v2.0新增: 添加交叉验证数据(如果有)
            if cross_validation_data:
                report["cross_validation"] = cross_validation_data

            self.logger.info(
                f"[单元概述质控] 检测完成，综合得分: {overall_score:.2f}, "
                f"发现问题: {len(all_issues)}个"
            )

            return report

        except Exception as e:
            self.logger.error(f"[单元概述质量分析] 分析失败: {str(e)}")
            import traceback
            self.logger.error(f"[单元概述质量分析] 异常堆栈: {traceback.format_exc()}")
            # 返回空报告
            return {
                "overall_score": 0,
                "dimension_scores": {},
                "issues": [],
                "statistics": {}
            }

    def _build_quality_revision_prompt(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        quality_report_dict: Dict[str, Any],
        global_outline: str,
        content_type: str
    ) -> str:
        """
        构建基于质量报告的修正提示词

        Args:
            unit_summaries: 单元概述字典
            quality_report_dict: 质量报告字典
            global_outline: 全局大纲内容
            content_type: 内容类型

        Returns:
            修正提示词字符串
        """
        # 提取所有问题（不仅限于critical，包含major和minor）
        # 修复1：确保所有级别的问题都被修正
        issues = quality_report_dict.get("issues", [])

        # 按严重程度排序：critical > major > minor
        severity_order = {"critical": 0, "major": 1, "minor": 2}
        sorted_issues = sorted(
            issues,
            key=lambda x: severity_order.get(x.get("severity", "minor"), 2)
        )

        # 构建问题描述
        issues_description = []
        for i, issue in enumerate(sorted_issues, 1):
            severity = issue.get('severity', 'minor')
            issue_text = f"{i}. [{severity.upper()}] [{issue.get('dimension', '')}] {issue.get('description', '')}"
            location = issue.get('location', {})
            if location:
                chapter = location.get('chapter', '')
                if chapter:
                    issue_text += f" (第{chapter}单元)"
            evidence = issue.get('evidence', '')
            if evidence:
                issue_text += f"\n   原文证据: {evidence[:100]}"
            suggestion = issue.get('suggestion', '')
            if suggestion:
                issue_text += f"\n   修改建议: {suggestion}"
            issues_description.append(issue_text)

        # 构建单元概述文本（包含完整结构化信息）
        units_text = []
        for unit_num, unit_data in sorted(unit_summaries.items(), key=lambda x: int(x[0])):
            unit_label = "章" if content_type == "novel" else "集"
            unit_parts = [
                f"【第{unit_num}{unit_label}】{unit_data.get('title', '')}"]

            # 添加梗概
            summary = unit_data.get('summary', '')
            if summary:
                unit_parts.append(f"梗概：{summary}")

            # 添加完整内容（包含情节要点、人物状态标注等所有结构化信息）
            full_content = unit_data.get('full_content', '')
            if full_content:
                unit_parts.append(f"完整内容：\n{full_content}")

            units_text.append('\n'.join(unit_parts))

        prompt = f"""你是专业的创意写作顾问和剧本/小说结构专家。

## 任务
以下单元概述存在严重的质量问题，请基于质量分析报告进行修正。

## 全局大纲（参考）
{global_outline[:2000]}

## 当前单元概述
{chr(10).join(units_text)}

## 发现的质量问题
{chr(10).join(issues_description)}

## 修正要求
1. 针对每个严重问题，修正对应的单元概述内容
2. **重要：必须保留原有的"情节要点"、"人物状态标注"等所有结构化信息**
3. 在修正梗概时，要考虑并整合这些结构化信息
4. 保持与全局大纲的一致性
5. 确保单元之间的逻辑连贯性
6. 修正后内容应该解决所有标注的质量问题
7. 保持原有的创意和风格
8. 如果修正了梗概，确保与情节要点和人物状态标注保持一致

## 输出格式
请严格按照以下 JSON 格式输出修正结果：
```json
{{
  "revisions": {{
    "1": {{
      "summary": "修正后的第1单元梗概内容",
      "full_content": "修正后的第1单元完整内容（必须包含情节要点、人物状态标注等所有结构化信息）",
      "revision_reason": "修正原因说明"
    }},
    "2": {{
      "summary": "修正后的第2单元梗概内容",
      "full_content": "修正后的第2单元完整内容（必须包含情节要点、人物状态标注等所有结构化信息）",
      "revision_reason": "修正原因说明"
    }}
  }}
}}
```

注意：
- 只输出需要修正的单元
- summary 字段是修正后的梗概
- **full_content 字段必须包含完整的单元内容，包括情节要点、人物状态标注等所有结构化信息**
- 如果某个结构化信息不需要修改，请原样保留
- revision_reason 简要说明修正了什么问题
- 确保 JSON 格式正确，可以被解析
"""
        return prompt

    def _parse_quality_revision_result(
        self,
        revision_text: str,
        original_parsed: Dict[str, Dict[str, Any]]
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        解析质量修正结果

        Args:
            revision_text: LLM 返回的修正文本
            original_parsed: 原始解析结果

        Returns:
            修正后的单元概述字典，解析失败返回 None
        """
        import json
        import re

        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', revision_text)
            if not json_match:
                self.logger.warning("[质量修正] 未找到 JSON 格式的输出")
                return None

            json_str = json_match.group(0)
            revision_data = json.loads(json_str)

            # 验证格式
            if "revisions" not in revision_data:
                self.logger.warning("[质量修正] JSON 格式错误，缺少 revisions 字段")
                return None

            revisions = revision_data["revisions"]
            if not isinstance(revisions, dict):
                self.logger.warning("[质量修正] revisions 字段格式错误")
                return None

            # 构建修正结果
            result = {}
            for unit_num, revision_info in revisions.items():
                if not isinstance(revision_info, dict):
                    continue

                summary = revision_info.get("summary", "").strip()
                full_content = revision_info.get("full_content", "").strip()
                revision_reason = revision_info.get(
                    "revision_reason", "").strip()

                if not summary:
                    continue

                result[unit_num] = {
                    "summary": summary,
                    # 如果没有full_content，使用summary
                    "full_content": full_content if full_content else summary,
                    "revision_reason": revision_reason
                }

            if result:
                self.logger.info(f"[质量修正] 成功解析 {len(result)} 个单元的修正结果")
                return result
            else:
                self.logger.warning("[质量修正] 未找到有效的修正内容")
                return None

        except json.JSONDecodeError as e:
            self.logger.error(f"[质量修正] JSON 解析失败: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"[质量修正] 解析修正结果失败: {str(e)}")
            return None

    def save_outline_to_file(
        self,
        content: str,
        file_type: str,  # global_outline/unit_summaries
        project_id: int,
        user_id: int
    ) -> str:
        """
        保存大纲内容到文件

        Args:
            content: 大纲内容
            file_type: 文件类型
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            文件路径
        """
        settings = get_settings()
        upload_dir = settings.get_upload_dir()

        # 创建大纲目录
        outline_dir = os.path.join(upload_dir, "outlines")
        os.makedirs(outline_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{file_type}_{project_id}_{timestamp}.md"
        file_path = os.path.join(outline_dir, filename)

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        self.logger.info(f"[大纲保存] 文件已保存: {file_path}")

        return file_path

    # ==================== 续生成辅助方法 ====================

    def _extract_structured_context(
        self,
        existing_parsed: Dict[str, Dict[str, Any]],
        start_from_unit: int,
        content_type: str
    ) -> Dict[str, Any]:
        """
        从已有章节中提取结构化上下文信息

        提取四类关键信息，用于增强续生成的连贯性：
        1. 角色追踪：主要角色及其最新状态
        2. 情节线追踪：活跃的和已关闭的情节线
        3. 情感基调追踪：最后一章的情感基调
        4. 直接衔接点：最后一章的完整梗概

        Args:
            existing_parsed: 已解析的单元数据
            start_from_unit: 续生成起始章节号
            content_type: 内容类型

        Returns:
            结构化上下文字典
        """
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
            content_type, "章"
        )

        existing_count = len(existing_parsed)

        # ===== 1. 角色追踪 =====
        # 从最后5章的 full_content 中提取角色出场信息
        character_mentions = {}  # {角色名: 最近出现章节号}
        character_states = {}    # {角色名: 最新状态描述}

        recent_start = max(1, start_from_unit - 5)
        for num in range(recent_start, start_from_unit):
            if str(num) not in existing_parsed:
                continue
            unit = existing_parsed[str(num)]
            full_content = unit.get(
                'full_content', '') or unit.get('summary', '')
            summary = unit.get('summary', '')

            # 从梗概中提取角色名（简单启发式：中文人名通常是2-3字）
            # 使用常见的角色引出词匹配
            import re
            # 匹配格式如：张三、李四 或 张三与李四 或 张三被/将/把/在
            name_patterns = re.findall(
                r'[\u4e00-\u9fff]{2,4}(?=[，。、与和被将把在从向对给让又或者的])',
                summary
            )
            # 过滤常见非人名词汇
            stop_words = {'这时', '此时', '然而', '但是', '因此', '于是', '虽然',
                          '尽管', '不过', '而且', '并且', '或者', '同时', '随后',
                          '最终', '突然', '原来', '终于', '忽然', '显然', '似乎',
                          '正在', '已经', '即将', '渐渐', '默默', '缓缓', '悄悄',
                          '此刻', '随后', '后来', '之后', '之前', '期间', '当中',
                          '其中', '这里', '那里', '这个', '那个', '一个', '另一'}
            for name in name_patterns:
                if name not in stop_words and len(name) >= 2:
                    character_mentions[name] = num

            # 从梗概中提取角色状态变化（格式如：张三...变得/发现/决定/意识到...）
            state_patterns = re.findall(
                r'([\u4e00-\u9fff]{2,4})(?:变得|发现|决定|意识到|终于|开始|逐渐|学会了|成长为|蜕变为|转变为)([^，。！？]{2,20})',
                summary
            )
            for char_name, state_desc in state_patterns:
                if char_name not in stop_words and len(char_name) >= 2:
                    character_states[char_name] = state_desc.strip()

        # 构建角色信息列表（按最近出现排序）
        active_characters = []
        for name, last_chapter in sorted(
            character_mentions.items(), key=lambda x: x[1], reverse=True
        )[:10]:  # 最多追踪10个角色
            char_info = f"{name}（最近出现于第{last_chapter}{unit_label}）"
            if name in character_states:
                char_info += f" - {character_states[name]}"
            active_characters.append(char_info)

        # ===== 2. 情节线追踪 =====
        # 从所有章节中提取关键情节线索（基于梗概中的关键词）
        plot_keywords = ['伏笔', '悬念', '秘密', '谜团', '阴谋', '真相', '线索',
                         '承诺', '约定', '使命', '目标', '计划', '预言', '诅咒']
        open_plot_lines = []  # 未解决的情节线

        # 检查最后5章中是否有引入但未解决的情节线
        for num in range(recent_start, start_from_unit):
            if str(num) not in existing_parsed:
                continue
            unit = existing_parsed[str(num)]
            summary = unit.get('summary', '')
            for keyword in plot_keywords:
                if keyword in summary:
                    # 提取包含关键词的句子
                    sentences = re.split(r'[。！？]', summary)
                    for sentence in sentences:
                        if keyword in sentence and len(sentence.strip()) > 5:
                            open_plot_lines.append(
                                f"第{num}{unit_label}: {sentence.strip()[:60]}"
                            )
                            break  # 每章每个关键词只取一个

        # 去重，最多保留8条
        seen = set()
        unique_plot_lines = []
        for line in open_plot_lines:
            if line not in seen:
                seen.add(line)
                unique_plot_lines.append(line)
        unique_plot_lines = unique_plot_lines[:8]

        # ===== 3. 情感基调追踪 =====
        # 从最后一章提取情感基调
        last_unit = existing_parsed.get(str(start_from_unit - 1), {})
        last_summary = last_unit.get('summary', '')

        emotion_keywords = {
            '紧张': ['紧张', '危机', '危险', '威胁', '紧迫', '焦虑'],
            '悲伤': ['悲伤', '痛苦', '失去', '牺牲', '离别', '绝望'],
            '愤怒': ['愤怒', '暴怒', '仇恨', '报复', '不甘', '愤慨'],
            '温馨': ['温馨', '感动', '温暖', '守护', '陪伴', '关怀'],
            '欢乐': ['欢乐', '喜悦', '庆祝', '胜利', '团聚', '欢笑'],
            '悬疑': ['悬疑', '疑惑', '未知', '谜团', '暗藏', '诡异'],
            '壮阔': ['壮阔', '史诗', '壮观', '宏大', '磅礴', '震撼']
        }

        detected_emotions = []
        for emotion, keywords in emotion_keywords.items():
            for kw in keywords:
                if kw in last_summary:
                    detected_emotions.append(emotion)
                    break

        emotion_desc = '、'.join(
            detected_emotions) if detected_emotions else '平稳'

        # ===== 4. 直接衔接点 =====
        # 最后一章的完整梗概
        last_chapter_title = last_unit.get('title', '')
        last_chapter_summary = last_summary
        # 如果有 full_content 且比 summary 更丰富，使用 full_content 的前200字
        last_full_content = last_unit.get('full_content', '')
        if last_full_content and len(last_full_content) > len(last_summary) + 50:
            # full_content 更丰富，提取梗概部分作为衔接参考
            summary_match = re.search(
                r'\*\*本章梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
                last_full_content, re.DOTALL
            )
            if summary_match:
                last_chapter_summary = summary_match.group(1).strip()

        return {
            'active_characters': active_characters,
            'open_plot_lines': unique_plot_lines,
            'emotion_tone': emotion_desc,
            'last_chapter_title': last_chapter_title,
            'last_chapter_summary': last_chapter_summary,
            'existing_count': existing_count
        }

    def _build_resume_context(
        self,
        existing_parsed: Dict[str, Dict[str, Any]],
        start_from_unit: int,
        content_type: str
    ) -> str:
        """
        构建续生成的上下文（增强版 v2）

        提供三层上下文信息，确保续生成内容与前文高度连贯：
        1. 全局概览：开头3章 + 关键转折 + 最近章节的标题、一句话摘要和主要角色
        2. 详细参考：前5章完整梗概 + 结构化上下文（角色状态、情节线、情感基调、直接衔接点）
        3. 续生成指令：明确的接续起点、情节衔接、伏笔回收和连贯性要求
        """
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
            content_type, "章"
        )

        existing_count = len(existing_parsed)

        # ===== 提取结构化上下文信息 =====
        structured = self._extract_structured_context(
            existing_parsed, start_from_unit, content_type
        )

        # ===== 第一层：全局概览（所有章节的标题+一句话摘要+角色）=====
        overview_units = []
        for num in range(1, start_from_unit):
            if str(num) in existing_parsed:
                unit = existing_parsed[str(num)]
                title = unit.get('title', f'第{num}{unit_label}')
                summary = unit.get('summary', '')
                # 一句话摘要：取summary的前80字
                one_liner = summary[:80] + \
                    '...' if len(summary) > 80 else summary
                overview_entry = f"第{num}{unit_label}《{title}》：{one_liner}"
                overview_units.append(overview_entry)

        # 如果章节过多，只取开头3章 + 中间关键转折 + 最后5章的概览
        if len(overview_units) > 20:
            head = overview_units[:3]
            tail = overview_units[-5:]
            mid_start = len(overview_units) // 2 - 1
            mid = overview_units[mid_start:mid_start + 2]
            overview_display = head + \
                ['...（中间章节省略）...'] + mid + ['...（中间章节省略）...'] + tail
        else:
            overview_display = overview_units

        overview_text = chr(10).join(
            overview_display) if overview_display else "（无前文）"

        # ===== 第二层：详细参考（前5章完整梗概 + 结构化上下文）=====
        context_units = []
        start_num = max(1, start_from_unit - 5)
        for num in range(start_num, start_from_unit):
            if str(num) in existing_parsed:
                unit = existing_parsed[str(num)]
                title = unit.get('title', '')
                summary = unit.get('summary', '')
                full_content = unit.get('full_content', '')

                # 使用更丰富的内容作为参考
                # 优先使用 full_content 中的梗概部分
                if full_content and len(full_content) > len(summary) + 50:
                    import re
                    summary_match = re.search(
                        r'\*\*本章梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
                        full_content, re.DOTALL
                    )
                    if summary_match:
                        summary = summary_match.group(1).strip()

                context_entry = f"第{num}{unit_label}《{title}》\n梗概：{summary}"
                context_units.append(context_entry)

        detail_text = chr(10).join(
            context_units) if context_units else "（无详细参考）"

        # ===== 构建结构化上下文补充信息 =====
        # 角色信息
        characters_text = chr(10).join(
            f"  - {c}" for c in structured['active_characters']
        ) if structured['active_characters'] else "  （未检测到活跃角色）"

        # 情节线信息
        plot_lines_text = chr(10).join(
            f"  - {p}" for p in structured['open_plot_lines']
        ) if structured['open_plot_lines'] else "  （无明确的未解决情节线）"

        # 最后一章衔接点
        last_chapter_info = ""
        if structured['last_chapter_title']:
            last_chapter_info = (
                f"第{start_from_unit - 1}{unit_label}《{structured['last_chapter_title']}》\n"
                f"完整梗概：{structured['last_chapter_summary']}"
            )
        else:
            last_chapter_info = "（无前文章节）"

        # ===== 第三层：续生成指令（增强版）=====
        context = f"""【全局概览（已生成第1-{existing_count}{unit_label}）】
{overview_text}

【前文详细参考（最后{len(context_units)}{unit_label}）】
{detail_text}

【直接衔接点（第{start_from_unit - 1}{unit_label}完整梗概）】
{last_chapter_info}

【活跃角色状态】
{characters_text}

【未解决的情节线索】
{plot_lines_text}

【当前情感基调】
{structured['emotion_tone']}

【续生成要求】
请从第{start_from_unit}{unit_label}开始继续生成后续章节概述。
关键要求：
1. 第{start_from_unit}{unit_label}必须与第{start_from_unit - 1}{unit_label}的情节自然衔接，从上一章结尾的情境继续发展
2. 人物状态和关系必须与「活跃角色状态」中描述的一致，不得出现状态矛盾
3. 「未解决的情节线索」中的伏笔和悬念必须在后续章节中继续发展或回收
4. 情感基调应从「{structured['emotion_tone']}」自然过渡，不宜突变
5. 参考全局大纲中第{start_from_unit}{unit_label}之后的情节分配
6. 保持与前文相同的叙事风格和节奏
"""
        return context

    def _build_resume_prompt(
        self,
        module_name: str,
        global_outline: str,
        context_prefix: str,
        start_from_unit: int,
        unit_count: int,
        content_type: str,
        series_type: str = None,
        episode_duration_range: str = None,
        title_style: str = None,  # 标题风格ID（新增）
        title_style_name: str = None  # 标题风格名称（新增）
    ) -> str:
        """构建续生成的提示词"""
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
            content_type, "章"
        )

        units_to_generate = unit_count - start_from_unit + 1

        input_params = {
            "global_outline": global_outline + "\n\n" + context_prefix,
            "chapter_count": str(units_to_generate),
            "episode_count": str(units_to_generate),
            "series_type": series_type or "网剧",
            "episode_duration_range": episode_duration_range or "30-45分钟"
        }

        # 生成标题风格指导文本（新增）
        if content_type == "novel" and title_style:
            from app.agents.writing.prompts.title_style_guidance import get_title_style_guidance
            title_style_guidance = get_title_style_guidance(
                title_style, title_style_name or "")
            input_params["title_style_guidance"] = title_style_guidance
            self.logger.info(
                f"[单元概述续生成] 使用标题风格: {title_style_name} ({title_style})")
        else:
            input_params["title_style_guidance"] = ""

        prompt_template = self.prompt_manager.get_default_prompt(module_name)
        filled_prompt = self.prompt_manager.render_prompt(
            prompt_template, input_params, module_name
        )

        # 添加续生成特别说明（三重约束机制）
        filled_prompt += f"""

## 🚨🚨🚨 极其重要：续生成模式 - 严格的批次约束

### 当前任务状态
- **已生成章节**：第1-{start_from_unit - 1}{unit_label}（共{start_from_unit - 1}章）
- **本次任务**：生成第{start_from_unit}-{unit_count}{unit_label}（共{units_to_generate}章）
- **全局大纲**：已提供完整的1-{unit_count}{unit_label}的大纲（供参考整体设定）

### ⛔ 绝对禁止的行为
1. ❌ 严禁从第1章重新开始生成
2. ❌ 严禁重复生成第1-{start_from_unit - 1}章的内容
3. ❌ 严禁跳过第{start_from_unit}章，从后面的章节开始
4. ❌ 严禁生成超过第{unit_count}章的内容

### ✅ 必须严格遵守的规则
1. ✅ **必须从第{start_from_unit}{unit_label}开始生成**（这是你的起点）
2. ✅ **必须按顺序生成**：第{start_from_unit}章 → 第{start_from_unit + 1}章 → ... → 第{unit_count}章
3. ✅ **必须生成恰好{units_to_generate}个章节**，不多不少
4. ✅ **章节编号必须连续**：{start_from_unit}, {start_from_unit + 1}, {start_from_unit + 2}, ..., {unit_count}

### 情节连贯性要求
- 你生成的第{start_from_unit}章必须与第{start_from_unit - 1}章的情节自然衔接
- 人物状态、关系发展要与前文保持一致
- 伏笔、线索要继续发展或回收
- 参考全局大纲中第{start_from_unit}-{unit_count}章的情节分配

### 输出完整性保障（防截断）
- 当你感觉到输出即将达到token上限时，**必须提前结束**
- 结束时必须确保最后一个章节概述是**完整的**，包含标题、梗概、情节要点等全部要素
- **绝对禁止输出不完整的章节概述**——如果来不及写完某一章，就不要开始写这一章
- 正确做法：写完当前章节后，判断是否还有足够空间写完下一章，如果空间不足就停在此处
- 未生成的章节可以通过续生成机制补全，但被截断的半章内容无法使用

### 输出格式示例
```
第{start_from_unit}章 [章节标题]
梗概：[本章情节概述]
...

第{start_from_unit + 1}章 [章节标题]
梗概：[本章情节概述]
...

（继续直到第{unit_count}章）
```

**再次强调：从第{start_from_unit}章开始，生成到第{unit_count}章结束，共{units_to_generate}章！**
"""

        return filled_prompt

    # ==================== 分层质量管控方法 ====================

    async def _perform_layered_quality_control(
        self,
        full_parsed: Dict[str, Dict[str, Any]],
        global_outline: str,
        content_type: str,
        is_resume: bool,
        new_units_start: int = None,
        llm_provider=None,
        temperature: float = 0.7,
        workflow_yield=None,
        replace_content_yield=None,
        user_id: int = 0
    ) -> Dict:
        """
        分层质量管控（核心方法）

        架构：
        - 第一层：局部检查（所有章节）
        - 第二层：边界检查（续生成时增强）
        - 第三层：增量全局检查（续生成时抽查）
        """
        from app.services.quality_control import QualityControlService

        qc_service = QualityControlService(db=self.db)

        # ==================== 第一层：局部检查 ====================
        if workflow_yield:
            yield {
                "type": "step", "step": "qc_local", "status": "running",
                "message": "正在进行局部质量检查...",
                "icon": "Search"
            }

        # 构建章节数据
        chapters_data = []
        for unit_num, unit_data in full_parsed.items():
            chapters_data.append({
                "id": int(unit_num),
                "unit_id": unit_data.get("unit_id", f"unit-{unit_num}"),
                "chapter_number": int(unit_num),
                "content": unit_data.get("full_content", "") or unit_data.get("summary", ""),
                "summary": unit_data.get("summary", ""),
                "full_content": unit_data.get("full_content", ""),
                "title": unit_data.get("title", ""),
                "status": "completed",
                "is_resumed": unit_data.get("is_resumed", False)
            })

        # 执行单元概述专用的5维度质量分析
        quality_report = await self._analyze_unit_summaries_quality(
            qc_service=qc_service,
            chapters_data=chapters_data,
            dimensions=["unit_structure",
                        "unit_character", "unit_consistency",
                        "unit_timeline_space", "unit_ooc"],
            depth="deep",
            global_outline=global_outline,
            user_id=user_id
        )

        if workflow_yield:
            issue_count = len(quality_report.get("issues", []))
            yield {
                "type": "step", "step": "qc_local", "status": "done",
                "message": f"局部检查完成，发现{issue_count}个问题",
                "icon": "Search"
            }

        # ==================== 第二层：边界检查（续生成增强）====================
        if is_resume and new_units_start:
            if workflow_yield:
                yield {
                    "type": "step", "step": "qc_boundary", "status": "running",
                    "message": "正在检查续生成边界连贯性...",
                    "icon": "Connection"
                }

            boundary_report = await self._check_resume_boundary(
                full_parsed=full_parsed,
                new_units_start=new_units_start,
                content_type=content_type,
                llm_provider=llm_provider,
                temperature=temperature
            )

            # 合并边界检查问题
            quality_report.setdefault("issues", []).extend(
                boundary_report.get("issues", [])
            )

            if workflow_yield:
                yield {
                    "type": "step", "step": "qc_boundary", "status": "done",
                    "message": f"边界检查完成，发现{len(boundary_report.get('issues', []))}个问题",
                    "icon": "Connection"
                }

        # ==================== 第三层：增量全局检查（续生成抽查）====================
        if is_resume:
            if workflow_yield:
                yield {
                    "type": "step", "step": "qc_global_incremental", "status": "running",
                    "message": "正在进行增量全局检查...",
                    "icon": "Grid"
                }

            global_report = await self._check_global_consistency_incremental(
                full_parsed=full_parsed,
                global_outline=global_outline,
                new_units_start=new_units_start,
                content_type=content_type,
                llm_provider=llm_provider,
                temperature=temperature
            )

            # 合并全局检查问题
            quality_report.setdefault("issues", []).extend(
                global_report.get("issues", [])
            )

            if workflow_yield:
                yield {
                    "type": "step", "step": "qc_global_incremental", "status": "done",
                    "message": f"全局检查完成，发现{len(global_report.get('issues', []))}个问题",
                    "icon": "Grid"
                }

        # ==================== 自动修正严重问题 ====================
        critical_issues = [
            issue for issue in quality_report.get("issues", [])
            if issue.get("severity") == "critical"
        ]

        if critical_issues:
            if workflow_yield:
                yield {
                    "type": "step", "step": "qc_revision", "status": "running",
                    "message": f"发现{len(critical_issues)}个严重问题，正在修正...",
                    "icon": "Edit"
                }

            revision_prompt = self._build_quality_revision_prompt(
                unit_summaries=full_parsed,
                quality_report_dict=quality_report,
                global_outline=global_outline,
                content_type=content_type
            )

            # 调用LLM修正
            revision_response = await llm_provider.generate(
                prompt=revision_prompt,
                temperature=temperature
            )

            # 解析修正结果并应用
            revised_parsed = self._parse_quality_revision_result(
                revision_response.content, full_parsed
            )

            if revised_parsed:
                # 保存修正前后的对比信息
                for unit_num, revised_data in revised_parsed.items():
                    if unit_num in full_parsed:
                        full_parsed[unit_num]["original_summary"] = full_parsed[unit_num].get(
                            "summary", "")
                        full_parsed[unit_num]["summary"] = revised_data.get(
                            "summary", full_parsed[unit_num]["summary"])
                        full_parsed[unit_num]["quality_revised"] = True
                        full_parsed[unit_num]["revision_reason"] = revised_data.get(
                            "revision_reason", "")

                # 重新生成完整内容
                revised_content = self._format_all_units(
                    full_parsed, content_type)

                if replace_content_yield:
                    yield revised_content, f"已修正{len(revised_parsed)}个单元的质量问题"

                self.logger.info("[单元概述] 质量管控修正完成")

            if workflow_yield:
                yield {
                    "type": "step", "step": "qc_revision", "status": "done",
                    "message": "质量修正完成",
                    "icon": "Edit"
                }
        else:
            if workflow_yield:
                yield {
                    "type": "step", "step": "quality_control", "status": "done",
                    "message": "质量检查通过，无需修正",
                    "icon": "Check"
                }

        # 发送质量管控报告给前端
        if workflow_yield and quality_report:
            yield {
                "type": "quality_report",
                "report": quality_report
            }

        # 异步生成器不能使用return返回值

    async def _check_resume_boundary(
        self,
        full_parsed: Dict[str, Dict[str, Any]],
        new_units_start: int,
        content_type: str,
        llm_provider,
        temperature: float
    ) -> Dict:
        """
        边界检查：确保续生成部分与前文连贯

        检查范围：第(new_units_start-5) 到 第(new_units_start+5)章
        """
        unit_label = {"novel": "章", "series_script": "集"}.get(
            content_type, "章")

        # 获取边界章节（前后各5章）
        boundary_start = max(1, new_units_start - 5)
        boundary_end = min(new_units_start + 5, max(int(k)
                           for k in full_parsed.keys()))

        boundary_units = []
        for num in range(boundary_start, boundary_end + 1):
            if str(num) in full_parsed:
                unit = full_parsed[str(num)]
                is_new = num >= new_units_start
                boundary_units.append(
                    f"{'【新生成】' if is_new else '【已有】'}"
                    f"第{num}{unit_label}《{unit.get('title', '')}》\n"
                    f"梗概：{unit.get('summary', '')}"
                )

        check_prompt = f"""你是专业的小说/剧本结构审核专家。

## 任务
检查续生成章节与前文的连贯性。重点关注：

1. **情节衔接**：第{new_units_start-1}章到第{new_units_start}章的过渡是否自然？
2. **人物状态**：人物性格、关系、能力是否保持一致？
3. **伏笔线索**：前文埋下的伏笔是否在后续章节中得到发展或回收？
4. **时间线**：时间顺序是否合理？
5. **节奏变化**：情节节奏是否有突兀变化？

## 边界章节内容
{chr(10).join(boundary_units)}

## 输出格式
以JSON格式输出检查结果：
```json
{{
  "issues": [
    {{
      "type": "boundary_continuity",
      "description": "问题描述",
      "severity": "critical|high|medium|low",
      "affected_units": ["88", "89", "90", "91"],
      "suggestion": "修改建议"
    }}
  ]
}}
```
"""

        try:
            response = await llm_provider.generate(
                prompt=check_prompt,
                temperature=temperature
            )

            # 解析JSON响应
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                result = json.loads(json_match.group(0))
                return {"issues": result.get("issues", [])}

            return {"issues": []}

        except Exception as e:
            self.logger.error(f"[边界检查] 失败: {str(e)}")
            return {"issues": []}

    async def _check_global_consistency_incremental(
        self,
        full_parsed: Dict[str, Dict[str, Any]],
        global_outline: str,
        new_units_start: int,
        content_type: str,
        llm_provider,
        temperature: float
    ) -> Dict:
        """
        增量全局检查：续生成时抽查关键路径

        不检查全部章节，而是抽查：
        1. 开头3章（故事起点）
        2. 中间3章（转折点）
        3. 结尾3章（高潮结局）
        4. 新生成的章节（重点）
        """
        total_units = len(full_parsed)
        unit_label = {"novel": "章", "series_script": "集"}.get(
            content_type, "章")

        # 选择抽查章节
        sample_units = set()

        # 开头3章
        for num in range(1, min(4, total_units + 1)):
            sample_units.add(num)

        # 中间3章
        mid = total_units // 2
        for num in range(mid - 1, mid + 2):
            if 1 <= num <= total_units:
                sample_units.add(num)

        # 结尾3章
        for num in range(max(1, total_units - 2), total_units + 1):
            sample_units.add(num)

        # 新生成的章节（重点）
        for num in range(new_units_start, total_units + 1):
            sample_units.add(num)

        # 构建抽查内容
        sample_units_text = []
        for num in sorted(sample_units):
            if str(num) in full_parsed:
                unit = full_parsed[str(num)]
                is_new = num >= new_units_start
                sample_units_text.append(
                    f"{'【新生成】' if is_new else '【抽查】'}"
                    f"第{num}{unit_label}《{unit.get('title', '')}》\n"
                    f"梗概：{unit.get('summary', '')}"
                )

        check_prompt = f"""你是专业的小说/剧本质量审核专家。

## 任务
对以下抽查章节进行全局一致性检查：

1. **结构完整性**：故事三幕结构是否完整？
2. **伏笔回收**：开头埋下的伏笔是否在结尾得到回收？
3. **人物弧线**：主要角色的成长弧线是否合理？
4. **主题一致性**：全篇是否围绕核心主题展开？
5. **新生成章节质量**：第{new_units_start}-{total_units}{unit_label}是否与前面章节质量一致？

## 抽查章节内容
{chr(10).join(sample_units_text)}

## 全局大纲（参考）
{global_outline[:3000]}

## 输出格式
```json
{{
  "issues": [
    {{
      "type": "global_consistency",
      "description": "问题描述",
      "severity": "critical|high|medium|low",
      "affected_units": ["5", "95"],
      "suggestion": "修改建议"
    }}
  ]
}}
```
"""

        try:
            response = await llm_provider.generate(
                prompt=check_prompt,
                temperature=temperature
            )

            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                result = json.loads(json_match.group(0))
                return {"issues": result.get("issues", [])}

            return {"issues": []}

        except Exception as e:
            self.logger.error(f"[增量全局检查] 失败: {str(e)}")
            return {"issues": []}

    def _format_all_units(
        self,
        full_parsed: Dict[str, Dict[str, Any]],
        content_type: str
    ) -> str:
        """格式化所有单元为完整文本"""
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
            content_type, "章"
        )

        lines = []
        for unit_num in sorted(full_parsed.keys(), key=lambda x: int(x)):
            unit = full_parsed[unit_num]
            title = unit.get("title", "")
            summary = unit.get("summary", "")

            lines.append(f"### 第{unit_num}{unit_label}：{title}")
            lines.append(f"**本{unit_label}梗概**：{summary}")
            lines.append("")

        return "\n".join(lines)

    # ==================== 全局大纲质量管控方法 ====================

    async def analyze_global_outline_quality(
        self,
        global_outline_content: str,
        project,
        user_id: int,
        dimensions: List[str] = None,
        depth: str = "standard",
        task_id: str = None  # v1.1新增: SSE任务ID，用于实时进度推送
    ) -> Dict[str, Any]:
        """
        对全局大纲执行质量分析(用户手动触发)

        Args:
            global_outline_content: 全局大纲内容
            project: 项目对象
            user_id: 用户ID
            dimensions: 分析维度(默认全部四维度)
            depth: 分析深度(quick/standard/deep)
            task_id: SSE任务ID(v1.1新增,用于实时进度推送)

        Returns:
            质控报告字典
        """
        if dimensions is None:
            dimensions = [
                "global_structure",
                "global_character_worldview",
                "global_plot_consistency",
                "global_storyline_integrity"
            ]

        self.logger.info(f"[全局大纲质控] 开始分析,维度: {dimensions}, 深度: {depth}")

        try:
            # 1. 初始化质控服务
            from app.services.quality_control import QualityControlService
            qc_service = QualityControlService(db=self.db)

            # 2. 构建分析数据
            analysis_data = {
                "content": global_outline_content,
                "project": project,
                "character_profiles": getattr(project, 'character_profiles', None) or [],
                "worldview_settings": getattr(project, 'worldview_settings', None) or {}
            }

            # 3. 执行多维度分析
            quality_report = await self._analyze_global_outline_dimensions(
                qc_service=qc_service,
                analysis_data=analysis_data,
                dimensions=dimensions,
                depth=depth,
                user_id=user_id,
                task_id=task_id  # v1.1新增: 传递task_id以支持SSE推送
            )

            self.logger.info(
                f"[全局大纲质控] 分析完成,总分: {quality_report.get('overall_score', 0)}, "
                f"问题数: {len(quality_report.get('issues', []))}"
            )

            return quality_report

        except Exception as e:
            self.logger.error(f"[全局大纲质控] 分析失败: {e!r}")
            return {
                "success": False,
                "error": str(e),
                "overall_score": 0,
                "dimension_scores": {},
                "issues": []
            }

    async def _analyze_global_outline_dimensions(
        self,
        qc_service,
        analysis_data,
        dimensions,
        depth,
        user_id,
        task_id: str = None  # v1.1新增: SSE任务ID
    ) -> Dict[str, Any]:
        """
        执行全局大纲多维度分析(v1.1优化: 并行调用+SSE进度推送)

        优化点:
        - 使用asyncio.gather并行执行四个维度的LLM分析
        - SSE实时推送每个维度的分析进度
        - 预计加速比: 3-4倍(原需40-80分钟,现需10-20分钟)
        """
        import asyncio

        dimension_scores = {}
        all_issues = []

        global_outline = analysis_data["content"]
        project = analysis_data["project"]
        character_profiles = analysis_data.get("character_profiles", [])
        worldview_settings = analysis_data.get("worldview_settings", {})

        total_dimensions = len(dimensions)
        self.logger.info(
            f"[全局大纲质控] 开始并行分析 {total_dimensions} 个维度: {dimensions}"
        )

        # v1.1新增: SSE进度推送 - 开始
        if task_id:
            try:
                from app.api.v1.endpoints.novel_writer.quality_control_v2 import publish_qc_progress
                await publish_qc_progress(
                    task_id=task_id,
                    event_type="started",
                    message=f"开始分析{total_dimensions}个维度",
                    data={"total_dimensions": total_dimensions,
                          "dimensions": dimensions}
                )
            except Exception as e:
                self.logger.warning(f"[全局大纲质控] SSE推送失败: {e}")

        # v1.1修复: 使用共享计数器跟踪已完成维度数
        completed_count = 0
        completed_lock = asyncio.Lock()

        # ✅ 优化: 并行执行所有维度分析
        async def analyze_single_dimension(dimension: str, index: int):
            """单个维度分析任务"""
            nonlocal completed_count
            try:
                self.logger.info(f"[全局大纲质控] 维度 {dimension} 开始分析...")

                # v1.1新增: SSE进度推送 - 维度开始
                if task_id:
                    from app.api.v1.endpoints.novel_writer.quality_control_v2 import publish_qc_progress
                    await publish_qc_progress(
                        task_id=task_id,
                        event_type="progress",
                        dimension=dimension,
                        status="running",
                        progress=0,  # 开始时进度为0
                        message=f"正在分析: {dimension}"
                    )

                analyzer = qc_service._get_analyzer(dimension)
                self.logger.info(
                    f"[全局大纲质控] 维度 {dimension} 获取分析器成功，准备调用analyze方法...")

                result = await analyzer.analyze(
                    global_outline=global_outline,
                    project=project,
                    character_profiles=character_profiles,
                    worldview_settings=worldview_settings,
                    depth=depth,
                    db=self.db,
                    user_id=user_id
                )

                self.logger.info(
                    f"[全局大纲质控] 维度 {dimension} 分析完成，得分: {result.get('score', 0)}, 问题数: {len(result.get('issues', []))}")

                # v1.1修复: 原子更新已完成计数
                async with completed_lock:
                    completed_count += 1
                    current_progress = int(
                        (completed_count / total_dimensions) * 100)

                # v1.1新增: SSE进度推送 - 维度完成
                if task_id:
                    from app.api.v1.endpoints.novel_writer.quality_control_v2 import publish_qc_progress
                    await publish_qc_progress(
                        task_id=task_id,
                        event_type="progress",
                        dimension=dimension,
                        status="success",
                        progress=current_progress,
                        message=f"分析完成: {dimension}",
                        data={
                            "score": result.get("score", 0),
                            "issues_count": len(result.get("issues", [])),
                            "completed_dimensions": completed_count
                        }
                    )

                return {
                    "dimension": dimension,
                    "success": True,
                    "score": result.get("score", 0),
                    "issues": result.get("issues", []),
                    "metadata": result.get("metadata", {})
                }

            except Exception as e:
                self.logger.error(
                    f"[全局大纲质控] 维度 {dimension} 分析失败: {e!r}"
                )

                # v1.1修复: 原子更新已完成计数（失败也算完成）
                async with completed_lock:
                    completed_count += 1
                    current_progress = int(
                        (completed_count / total_dimensions) * 100)

                # v1.1新增: SSE进度推送 - 维度失败
                if task_id:
                    try:
                        from app.api.v1.endpoints.novel_writer.quality_control_v2 import publish_qc_progress
                        await publish_qc_progress(
                            task_id=task_id,
                            event_type="progress",
                            dimension=dimension,
                            status="failed",
                            progress=current_progress,
                            message=f"分析失败: {dimension}",
                            data={"error": str(
                                e), "completed_dimensions": completed_count}
                        )
                    except:
                        pass

                return {
                    "dimension": dimension,
                    "success": False,
                    "score": 0,
                    "issues": [],
                    "error": str(e)
                }

        # 并行执行所有维度分析
        tasks = [analyze_single_dimension(dim, idx)
                 for idx, dim in enumerate(dimensions)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"[全局大纲质控] 维度分析异常: {result!r}")
                continue

            dimension = result["dimension"]
            dimension_scores[dimension] = result["score"]
            all_issues.extend(result["issues"])

            if result["success"]:
                self.logger.info(
                    f"[全局大纲质控] 维度 {dimension} 分析完成, "
                    f"得分: {result['score']}, 问题数: {len(result['issues'])}"
                )
            else:
                self.logger.warning(
                    f"[全局大纲质控] 维度 {dimension} 分析失败: {result.get('error')}"
                )

        # 计算总分(各维度平均分)
        overall_score = (
            sum(dimension_scores.values()) / len(dimension_scores)
            if dimension_scores else 0
        )

        self.logger.info(
            f"[全局大纲质控] 并行分析完成, "
            f"总分: {overall_score:.1f}, 总问题数: {len(all_issues)}"
        )

        # v1.1新增: SSE进度推送 - 全部完成
        if task_id:
            try:
                from app.api.v1.endpoints.novel_writer.quality_control_v2 import publish_qc_progress
                await publish_qc_progress(
                    task_id=task_id,
                    event_type="completed",
                    progress=100,
                    message="所有维度分析完成",
                    data={
                        "overall_score": overall_score,
                        "total_issues": len(all_issues),
                        "dimension_scores": dimension_scores
                    }
                )
            except Exception as e:
                self.logger.warning(f"[全局大纲质控] SSE完成推送失败: {e}")

        # 生成智能建议
        all_issues = self._generate_global_outline_smart_suggestions(
            all_issues, global_outline
        )

        return {
            "success": True,
            "overall_score": round(overall_score, 1),
            "dimension_scores": dimension_scores,
            "issues": all_issues,
            "original_outline": global_outline,  # 保存原始大纲内容，用于LLM修正
            "metadata": {
                "dimensions_analyzed": dimensions,
                "depth": depth,
                "outline_length": len(global_outline),
                "total_issues": len(all_issues)
            }
        }

    def _generate_global_outline_smart_suggestions(
        self,
        issues: List[Dict],
        global_outline: str
    ) -> List[Dict]:
        """为全局大纲问题生成智能修正建议"""
        try:
            from app.services.quality_control.analyzers.smart_suggestions import get_smart_suggestion_engine
            suggestion_engine = get_smart_suggestion_engine()

            # 构建chapters_data格式(兼容smart_suggestions)
            chapters_data = [{
                "content": global_outline,
                "summary": global_outline[:500]
            }]

            enhanced_issues = suggestion_engine.generate_suggestions(
                issues=issues,
                chapters_data=chapters_data
            )

            return enhanced_issues

        except Exception as e:
            self.logger.warning(f"[全局大纲质控] 生成智能建议失败: {e!r}")
            return issues

    async def revise_global_outline_by_quality(
        self,
        original_outline: str,
        quality_report: Dict,
        issues_to_fix: List[str],
        project,
        user_id: int
    ) -> Dict[str, Any]:
        """
        根据质控报告修正全局大纲

        Args:
            original_outline: 原始大纲内容
            quality_report: 质控报告
            issues_to_fix: 需要修正的问题ID列表
            project: 项目对象
            user_id: 用户ID

        Returns:
            修正结果 {"success": bool, "revised_content": str, "changes": []}
        """
        result = {
            "success": False,
            "revised_content": None,
            "changes": [],
            "error": None
        }

        try:
            # 1. 筛选需要修正的问题
            issues = quality_report.get("issues", [])
            issues_to_fix_list = [
                issue for issue in issues
                if issue.get("id") in issues_to_fix
            ]

            if not issues_to_fix_list:
                result["error"] = "没有选择需要修正的问题"
                return result

            self.logger.info(
                f"[全局大纲修正] 开始修正,问题数: {len(issues_to_fix_list)}"
            )

            # 2. 获取LLM提供者
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(self.db, user_id)

            if not llm_provider:
                result["error"] = "无法获取LLM提供者"
                return result

            # 3. 构建修正提示词
            revision_prompt = self._build_global_outline_revision_prompt(
                original_outline=original_outline,
                issues=issues_to_fix_list
            )

            # 4. 调用LLM执行修正 - 超时1200秒(20分钟),带429重试
            self.logger.info("[全局大纲修正] 调用LLM执行修正...")

            # 添加429重试机制
            import asyncio
            max_retries = 3
            retry_delay = 5
            response = None

            for attempt in range(max_retries):
                try:
                    response = await llm_provider.generate(
                        prompt=revision_prompt,
                        temperature=0.3,
                        timeout=1200  # ✅ 20分钟超时
                    )
                    break  # 成功则跳出
                except Exception as e:
                    error_str = str(e)
                    if '429' in error_str or 'TooManyRequests' in error_str or 'ServerOverloaded' in error_str:
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (2 ** attempt)
                            self.logger.warning(
                                f"[全局大纲修正] LLM返回429错误,第{attempt+1}次重试,"
                                f"等待{wait_time}秒..."
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            self.logger.error(
                                f"[全局大纲修正] LLM 429错误,已重试{max_retries}次")
                            raise
                    else:
                        raise  # 其他错误直接抛出

            # ✅ 安全访问response
            revised_content = response.content if hasattr(
                response, 'content') else str(response)

            # 5. 清理修正内容（移除可能的Markdown标记）
            revised_content = self._clean_revised_content(revised_content)

            # v2.4优化：直接使用LLM输出的完整大纲，不再增量合并
            # LLM已经基于整体视角输出了完整的修正后大纲
            revision_effective = False  # 标记修正是否真正生效

            if revised_content and len(revised_content) > 100:
                # 验证输出是否有效（至少包含基本的大纲结构）
                if '##' in revised_content or '###' in revised_content:
                    revision_effective = True
                    self.logger.info(
                        f"[全局大纲修正] v2.4整体修正完成, 原始长度: {len(original_outline)}, "
                        f"修正后长度: {len(revised_content)}"
                    )
                else:
                    # 如果输出不包含大纲结构，可能LLM输出异常，使用原始内容
                    self.logger.warning(
                        "[全局大纲修正] LLM输出缺少大纲结构，保留原始内容"
                    )
                    revised_content = original_outline
                    result["revision_skipped"] = True
                    result["skip_reason"] = "LLM输出缺少大纲结构"
            else:
                # 输出过短，可能是异常
                self.logger.warning(
                    f"[全局大纲修正] LLM输出过短({len(revised_content) if revised_content else 0}字)，保留原始内容"
                )
                revised_content = original_outline
                result["revision_skipped"] = True
                result["skip_reason"] = f"LLM输出过短({len(revised_content) if revised_content else 0}字)"

            # 7. 构建变更说明
            changes = []
            if revision_effective:
                for issue in issues_to_fix_list:
                    changes.append({
                        "issue_id": issue.get("id"),
                        "category": issue.get("category"),
                        "description": issue.get("description"),
                        "suggestion": issue.get("suggestion")
                    })

            result["success"] = True
            result["revised_content"] = revised_content
            result["changes"] = changes
            # v2.4.1: 明确标记修正是否生效
            result["revision_effective"] = revision_effective

            if revision_effective:
                self.logger.info(
                    f"[全局大纲修正] 修正完成,原始长度: {len(original_outline)}, "
                    f"修正后长度: {len(revised_content)}"
                )
            else:
                self.logger.warning(
                    f"[全局大纲修正] 修正未生效,保留原始内容,长度: {len(original_outline)}"
                )

        except Exception as e:
            self.logger.error(f"[全局大纲修正] 修正失败: {e!r}")
            result["error"] = str(e)

        return result

    def _build_global_outline_revision_prompt(
        self,
        original_outline: str,
        issues: List[Dict]
    ) -> str:
        """构建全局大纲修正提示词 - v2.4优化：辩证性整体修正模式

        核心改进：
        1. LLM一次性获取所有问题信息
        2. 基于整体视角进行辩证性修正
        3. 考虑问题之间的相互关系和整体协调性
        4. 输出完整的修正后大纲
        """
        # 构建问题列表
        issues_text = "\n".join([
            f"- [{issue.get('id')}] [{issue.get('dimension', '未知维度')}] {issue.get('category', '未知分类')}\n"
            f"  问题描述: {issue.get('description', '无描述')}\n"
            f"  修正建议: {issue.get('suggestion', '请根据专业判断修正')}"
            + (f"\n  相关证据: {issue.get('evidence', '')[:300]}" if issue.get('evidence') else "")
            for issue in issues
        ])

        # 提取问题维度统计
        dimensions = {}
        for issue in issues:
            dim = issue.get('dimension', '未知维度')
            dimensions[dim] = dimensions.get(dim, 0) + 1

        dimension_summary = "\n".join([
            f"- {dim}: {count}个问题"
            for dim, count in dimensions.items()
        ])

        prompt = f"""你是一位资深的小说主编，拥有丰富的创作指导和内容审核经验。现在需要你基于质控报告，对全局大纲进行辩证性整体修正。

【重要原则】
1. **整体视角**：不要逐个问题单独修正，而是综合分析所有问题后，从整体协调性出发进行修正
2. **辩证思考**：问题之间可能存在关联，修正时需要考虑问题A的修正是否会影响问题B
3. **一致性保证**：确保修正后的内容在逻辑、人物、世界观、情节线上保持一致
4. **保留优点**：修正问题的同时，保留原始大纲的优点和特色

【原始全局大纲】
{original_outline}

【质控报告摘要】
共检测到 {len(issues)} 个问题，分布如下：
{dimension_summary}

【详细问题列表】
{issues_text}

【修正要求】
1. 首先阅读并理解所有问题，分析问题之间的关联性
2. 识别哪些问题是核心问题，哪些是衍生问题（解决核心问题可能同时解决衍生问题）
3. 制定整体修正策略，而非逐个问题打补丁
4. 输出完整的修正后全局大纲（保持原有格式和结构）
5. 确保修正后的内容：
   - 逻辑自洽，前后呼应
   - 人物性格和发展弧线一致
   - 世界观设定无矛盾
   - 情节推进合理、节奏得当

【输出格式】
请直接输出修正后的完整全局大纲，不要添加额外说明。
使用与原文相同的Markdown格式结构。

【修正后的全局大纲】
"""
        return prompt

    def _clean_revised_content(self, content: str) -> str:
        """清理修正后的内容(移除Markdown标记等)"""
        import re

        # 移除可能的```标记
        content = re.sub(r'^```\s*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^```[a-z]*\s*$', '', content, flags=re.MULTILINE)

        # 移除开头和结尾的空白
        content = content.strip()

        return content

    # ==================== v2.3新增：自动质控修正方法 ====================

    async def _auto_qc_and_revise(
        self,
        content: str,
        user_id: int,
        llm_provider=None,
        dimensions: List[str] = None,
        depth: str = "standard"  # 自动质控默认使用standard模式以确保LLM深度分析
    ) -> Dict[str, Any]:
        """
        自动执行质控分析并修正（v2.3新增）

        整合质控分析和修正逻辑，一步完成检测和修正。

        Args:
            content: 待检测和修正的内容
            user_id: 用户ID
            llm_provider: LLM提供者实例
            dimensions: 分析维度（默认四维度）
            depth: 分析深度（默认quick以提升速度）

        Returns:
            {
                "success": bool,
                "revised_content": str or None,
                "issues_fixed": int,
                "qc_report": dict
            }
        """
        result = {
            "success": False,
            "revised_content": None,
            "issues_fixed": 0,
            "qc_report": None
        }

        if not content or len(content.strip()) < 100:
            self.logger.warning("[自动质控] 内容过短，跳过质控")
            return result

        if dimensions is None:
            dimensions = [
                "global_structure",
                "global_character_worldview",
                "global_plot_consistency",
                "global_storyline_integrity"
            ]

        try:
            self.logger.info(f"[自动质控] 开始分析，维度: {dimensions}, 深度: {depth}")

            # 1. 执行质控分析
            qc_report = await self.analyze_global_outline_quality(
                global_outline_content=content,
                project=None,  # 两阶段模式无项目
                user_id=user_id,
                dimensions=dimensions,
                depth=depth
            )

            if not qc_report.get("success", False):
                self.logger.warning("[自动质控] 质控分析失败")
                result["qc_report"] = qc_report
                return result

            issues = qc_report.get("issues", [])
            overall_score = qc_report.get("overall_score", 0)

            self.logger.info(
                f"[自动质控] 分析完成，得分: {overall_score}, 问题数: {len(issues)}"
            )

            # 2. 判断是否需要修正
            if not issues or len(issues) == 0:
                self.logger.info("[自动质控] 未发现问题，无需修正")
                result["success"] = True
                result["qc_report"] = qc_report
                return result

            # 3. 筛选需要修正的问题（所有问题）
            issues_to_fix = [issue.get("id")
                             for issue in issues if issue.get("id")]

            if not issues_to_fix:
                self.logger.info("[自动质控] 无有效问题ID，跳过修正")
                result["success"] = True
                result["qc_report"] = qc_report
                return result

            self.logger.info(f"[自动质控] 开始修正 {len(issues_to_fix)} 个问题")

            # 4. 执行修正
            revision_result = await self.revise_global_outline_by_quality(
                original_outline=content,
                quality_report=qc_report,
                issues_to_fix=issues_to_fix,
                project=None,
                user_id=user_id
            )

            if revision_result.get("success"):
                revised_content = revision_result.get("revised_content")
                result["success"] = True
                result["revised_content"] = revised_content

                # v2.4.1: 只有修正真正生效时才统计issues_fixed
                revision_effective = revision_result.get(
                    "revision_effective", False)
                if revision_effective:
                    result["issues_fixed"] = len(issues_to_fix)
                else:
                    result["issues_fixed"] = 0
                    result["revision_skipped"] = True
                    result["skip_reason"] = revision_result.get(
                        "skip_reason", "修正未生效")

                # 更新质控报告中的修正标记
                qc_report["auto_applied"] = revision_effective
                qc_report["applied_at"] = datetime.now().isoformat()
                qc_report["issues_fixed"] = result["issues_fixed"]
                result["qc_report"] = qc_report

                self.logger.info(
                    f"[自动质控] 修正完成，原始长度: {len(content)}, "
                    f"修正后长度: {len(revised_content)}"
                )
            else:
                self.logger.warning(
                    f"[自动质控] 修正失败: {revision_result.get('error')}")
                result["qc_report"] = qc_report

        except Exception as e:
            self.logger.error(f"[自动质控] 执行失败: {e!r}")
            result["error"] = str(e)

        return result

    async def analyze_unit_summaries_quality_manual(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        global_outline: str,
        content_type: str,
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        手动触发单元概述质量检测（使用LLM，参照全局大纲流程）

        Args:
            unit_summaries: 已解析的单元概述字典
            global_outline: 全局大纲
            content_type: 内容类型
            user_id: 用户ID

        Returns:
            质量检测报告
        """
        self.logger.info(f"[单元概述质控] 开始LLM质量检测，单元数: {len(unit_summaries)}")

        try:
            # 1. 构建完整的单元概述文本
            unit_label = "章" if content_type == "novel" else "集"
            full_content_parts = []

            for unit_num, unit_data in sorted(unit_summaries.items(), key=lambda x: int(x[0])):
                title = unit_data.get("title", "")
                full_content = unit_data.get(
                    "full_content", "") or unit_data.get("summary", "")
                full_content_parts.append(
                    f"### 第{unit_num}{unit_label}：{title}\n{full_content}")

            complete_outline = "\n\n".join(full_content_parts)

            # 2. 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(self.db, user_id, None)
            if not llm_provider:
                raise ValueError("未找到LLM提供商，请检查API KEY配置")

            # 3. 构建LLM检测提示词
            analysis_prompt = f"""你是资深的小说/剧本质控专家，拥有10年以上的编辑经验。你的任务是**严格、全面**地检测单元概述的质量问题。

## 全局大纲（故事的整体规划）
{global_outline if global_outline else "未提供"}

## 单元概述（待检测的具体内容）
{complete_outline}

---

## 🔍 检测任务：逐单元深度审查

你必须**按顺序逐个检查每个单元**，从以下四个维度进行深度分析：

### 📐 维度1：结构检测（structure）

**1.1 单元长度合理性**
- 检查每个单元的篇幅是否合理（过短<100字或过长>800字都要指出）
- 对比各单元长度，是否存在明显不平衡

**1.2 单元衔接流畅度**
- 检查前一个单元的结尾与后一个单元的开头是否自然衔接
- 是否存在情节跳跃、时间断层、场景突兀转换
- 是否有必要的过渡内容

**1.3 情节节奏控制**
- 检查情节发展是否有起伏（不能所有单元都是平淡叙述）
- 是否有高潮、转折、缓冲的节奏变化
- 连续多个单元是否都是同一类型的情节（如全是打斗或全是对话）

**1.4 核心事件明确性**
- 每个单元是否有一个清晰的核心事件或主要冲突
- 单元内容是否围绕核心事件展开，有无跑题

### 👥 维度2：人物检测（character）

**2.1 人物状态连续性**
- 检查人物在单元之间的状态变化是否合理（如：受伤→恢复需要时间）
- 是否存在人物状态突变（如：前一单元重伤，下一单元完好无损）
- 人物情绪变化是否有铺垫

**2.2 人物关系一致性**
- 检查人物关系是否前后矛盾（如：前文是敌人，后文突然变成朋友且无解释）
- 人物称呼、身份、职位是否一致
- 人物性格是否保持连贯（OOC检测）

**2.3 人物成长逻辑**
- 人物的能力成长、心理变化是否有合理的过程
- 是否存在人物突然掌握某项技能而无学习过程
- 重要人物的成长线索是否完整

**2.4 人物遗漏检查**
- 全局大纲中的重要人物是否在单元概述中被遗漏
- 是否有单元缺少必要的人物出场

### 🎯 维度3：一致性检测（consistency）

**3.1 情节走向一致性**
- 对比单元概述与全局大纲，检查情节走向是否一致
- 单元概述是否偏离了全局大纲设定的故事线
- 是否有全局大纲中没有的突兀情节

**3.2 核心要素完整性**
- 全局大纲中的关键情节点、转折点是否在单元概述中得到体现
- 是否有遗漏全局大纲中明确要求的重要事件
- 核心线索（如：寻找某物、解开某谜团）是否在单元中延续

**3.3 世界观设定一致性**
- 检查单元概述中的世界观设定是否与全局大纲冲突
- 力量体系、规则设定、地理环境是否前后一致
- 是否存在违背已建立设定的内容

**3.4 时间线一致性**
- 检查时间线是否合理（如：季节变化、时间跨度）
- 是否存在时间倒流或时间矛盾
- 事件发生的先后顺序是否合理

### ✍️ 维度4：质量检测（quality）

**4.1 情节要点清晰度**
- 每个单元的情节要点是否清晰明确
- 是否包含必要的"情节要点"部分
- 情节要点是否具体而非模糊笼统

**4.2 人物状态标注完整性**
- 是否包含"人物状态标注"部分
- 人物状态标注是否详细（包含情绪、伤势、能力变化等）
- 状态标注是否与单元内容匹配

**4.3 逻辑漏洞检测**
- 检查是否存在明显的逻辑错误（如：人物同时出现在两个地方）
- 因果关系是否合理（如：A导致B，但A和B之间没有必然联系）
- 是否存在违背常识的内容

**4.4 标题准确性**
- 单元标题是否准确概括了该单元的核心内容
- 标题是否与单元内容匹配
- 标题是否具有吸引力且不过度夸张

---

## ⚠️ 检测标准与要求

### 强制性要求
1. **必须逐单元检查**：不能跳过任何一个单元，必须对每个单元进行四个维度的检测
2. **发现问题必须报告**：即使是不确定是否算问题的地方，也要列为minor级别
3. **提供具体证据**：每个问题必须引用原文内容作为证据（evidence字段）
4. **给出修正建议**：每个问题必须提供具体可操作的修正建议

### severity分级标准（严格执行）
- **critical（严重）**：
  - 情节严重偏离全局大纲
  - 人物状态突变且无解释
  - 明显的逻辑矛盾或违背常识
  - 遗漏全局大纲中的关键情节
  - 人物关系严重矛盾
  
- **major（重要）**：
  - 单元衔接不流畅
  - 人物成长缺乏铺垫
  - 情节节奏失衡
  - 世界观设定轻微冲突
  - 核心要素部分缺失

- **minor（次要）**：
  - 单元长度略有不平衡
  - 标题不够吸引人
  - 情节要点表述不够清晰
  - 人物状态标注不够详细
  - 可以优化的细节

### 评分标准
- **90-100分**：几乎没有问题，质量极高
- **80-89分**：有少量minor问题，整体优秀
- **70-79分**：有一些major问题，需要改进
- **60-69分**：有critical问题，必须修正
- **60分以下**：存在严重质量问题，需要大幅修改

---

## 📋 输出格式（必须严格遵守）

请严格按照以下JSON格式输出检测结果：

```json
{{
  "overall_score": 75,
  "dimension_scores": {{
    "structure": 80,
    "character": 70,
    "consistency": 75,
    "quality": 75
  }},
  "issues": [
    {{
      "id": "ISSUE-001",
      "dimension": "structure",
      "category": "衔接问题",
      "severity": "critical",
      "unit_number": 1,
      "location": {{
        "chapter_number": 1,
        "unit_id": "unit-1"
      }},
      "description": "第1单元与第2单元之间衔接不流畅，存在情节跳跃",
      "evidence": "第1单元结尾：'他倒在地上，身受重伤'；第2单元开头：'他精神抖擞地走进大厅'",
      "suggestion": "在第1单元结尾或第2单元开头增加过渡内容，说明他是如何恢复的"
    }},
    {{
      "id": "ISSUE-002",
      "dimension": "character",
      "category": "人物状态突变",
      "severity": "critical",
      "unit_number": 3,
      "location": {{
        "chapter_number": 3,
        "unit_id": "unit-3"
      }},
      "description": "主角在第2单元中左手骨折，但第3单元中左手正常使用且无任何说明",
      "evidence": "第2单元人物状态标注：'左手骨折，无法使用武器'；第3单元情节：'他左手持剑，与敌人战斗'",
      "suggestion": "在第3单元中说明主角左手是否已经恢复，或者改为右手战斗"
    }}
  ]
}}
```

### 输出要求
1. **overall_score**：根据上述评分标准给出总体得分（0-100的整数）
2. **dimension_scores**：四个维度的独立得分（0-100的整数）
3. **issues**：必须列出**所有发现的问题**，按严重程度排序（critical在前）
4. 每个issue必须包含所有必填字段：id, dimension, category, severity, unit_number, location, description, evidence, suggestion
5. **evidence字段必须引用原文内容**，不能只说"存在某某问题"
6. 如果没有问题，issues返回空数组 []

---

## 💡 检测提示

在检测时，请特别注意以下常见但容易被忽视的问题：
1. **时间跳跃**：单元之间的时间跨度是否合理
2. **场景转换**：场景切换是否突兀
3. **人物消失/出现**：重要人物是否无故消失或突然出现
4. **能力变化**：人物能力是否有合理的成长或衰退过程
5. **情感逻辑**：人物的情感变化是否有铺垫
6. **因果链条**：事件之间的因果关系是否成立
7. **伏笔回收**：前面埋下的伏笔是否在后续单元中得到回应
8. **设定冲突**：是否违背已建立的世界观、规则体系

**记住：你的职责是找出所有问题，宁可错报也不要漏报！**
"""

            self.logger.info("[单元概述质控] 调用LLM进行质量分析...")
            self.logger.info(
                f"[单元概述质控] 全局大纲长度: {len(global_outline) if global_outline else 0} 字")
            self.logger.info(f"[单元概述质控] 单元概述总长度: {len(complete_outline)} 字")
            self.logger.info(f"[单元概述质控] 单元数量: {len(unit_summaries)}")

            response = await llm_provider.generate(prompt=analysis_prompt, temperature=0.3, timeout=1200)
            response_text = response.content if hasattr(
                response, 'content') else str(response)

            self.logger.info(f"[单元概述质控] LLM响应长度: {len(response_text)} 字")

            # 4. 解析LLM返回的JSON
            import json
            import re

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                raise ValueError(f"LLM返回格式错误，未找到JSON: {response_text[:200]}")

            quality_report = json.loads(json_match.group(0))

            # 5. 确保报告格式完整
            if "overall_score" not in quality_report:
                quality_report["overall_score"] = 50
            if "dimension_scores" not in quality_report:
                quality_report["dimension_scores"] = {}
            if "issues" not in quality_report:
                quality_report["issues"] = []

            # 6. 为每个issue添加必要字段
            for i, issue in enumerate(quality_report.get("issues", []), 1):
                if "id" not in issue:
                    issue["id"] = f"ISSUE-{i:03d}"
                if "location" not in issue:
                    unit_num = issue.get("unit_number", "")
                    issue["location"] = {
                        "chapter_number": unit_num,
                        "unit_id": f"unit-{unit_num}" if unit_num else ""
                    }

            # 详细日志输出
            issues = quality_report.get("issues", [])
            critical_count = sum(
                1 for i in issues if i.get("severity") == "critical")
            major_count = sum(
                1 for i in issues if i.get("severity") == "major")
            minor_count = sum(
                1 for i in issues if i.get("severity") == "minor")

            self.logger.info(f"[单元概述质控] LLM检测完成")
            self.logger.info(
                f"[单元概述质控] 总分: {quality_report.get('overall_score', 0)}")
            self.logger.info(
                f"[单元概述质控] 维度得分: {quality_report.get('dimension_scores', {})}")
            self.logger.info(
                f"[单元概述质控] 问题统计: 总计{len(issues)}个 (critical: {critical_count}, major: {major_count}, minor: {minor_count})")

            # 输出前5个问题的摘要
            for issue in issues[:5]:
                self.logger.info(
                    f"[单元概述质控] 问题示例: [{issue.get('severity')}] {issue.get('description', '')[:100]}")

            return quality_report

        except Exception as e:
            self.logger.error(f"[单元概述质控] LLM检测失败: {e!r}", exc_info=True)
            # 返回空报告
            return {
                "overall_score": 0,
                "dimension_scores": {},
                "issues": [],
                "error": str(e)
            }

    async def revise_unit_summaries_quality(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        quality_report: Dict[str, Any],
        global_outline: str,
        content_type: str,
        temperature: float = 0.7,
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        对单元概述执行质量修正

        Args:
            unit_summaries: 已解析的单元概述字典
            quality_report: 质量检测报告
            global_outline: 全局大纲
            content_type: 内容类型
            temperature: 温度参数
            user_id: 用户ID

        Returns:
            修正结果
        """
        # 获取LLM提供商
        llm_provider = await self.llm_manager.get_provider_from_db(
            self.db, user_id, None
        )
        if not llm_provider:
            raise ValueError("未找到LLM提供商")

        # 构建修正提示词
        revision_prompt = self._build_quality_revision_prompt(
            unit_summaries=unit_summaries,
            quality_report_dict=quality_report,
            global_outline=global_outline,
            content_type=content_type
        )

        # 调用LLM修正
        revision_response = await llm_provider.generate(
            prompt=revision_prompt,
            temperature=temperature
        )

        # 解析修正结果
        revised_parsed = self._parse_quality_revision_result(
            revision_response.content, unit_summaries
        )

        if not revised_parsed:
            self.logger.warning("[质量修正] 修正结果解析失败")
            return {
                "revised_content": None,
                "revised_parsed": None
            }

        # 合并修正数据与原始数据，保留所有原始字段
        merged_parsed = {}
        for unit_num, original_data in unit_summaries.items():
            if unit_num in revised_parsed:
                # 该单元被修正，合并数据
                revised_data = revised_parsed[unit_num]
                merged_data = {
                    **original_data,  # 保留所有原始字段
                    "summary": revised_data.get("summary", original_data.get("summary", "")),
                    "full_content": revised_data.get("full_content", original_data.get("full_content", "")),
                    "revision_reason": revised_data.get("revision_reason", ""),
                    "revised_at": datetime.now().isoformat()  # 添加修正时间标记
                }
                # 保留title（如果修正结果中有）
                if "title" in revised_data:
                    merged_data["title"] = revised_data["title"]

                merged_parsed[unit_num] = merged_data
                self.logger.info(f"[质量修正] 第{unit_num}单元已修正并合并数据")
            else:
                # 该单元未被修正，保留原始数据
                merged_parsed[unit_num] = original_data

        # 构建修正后的内容
        revised_content = self._build_revised_content(
            merged_parsed, content_type)

        # 构建变更说明（参照全局大纲的流程）
        # 修复1：修正所有级别的问题（critical + major + minor），不仅限于critical
        all_issues = quality_report.get("issues", [])
        changes = []

        for issue in all_issues:
            changes.append({
                "issue_id": issue.get("id"),
                "category": issue.get("category"),
                "description": issue.get("description"),
                "suggestion": issue.get("suggestion"),
                "severity": issue.get("severity"),  # 添加severity字段
                "unit_number": issue.get("location", {}).get("chapter_number") or issue.get("unit_number")
            })

        return {
            "revised_content": revised_content,
            "revised_parsed": merged_parsed,
            "changes": changes
        }

    def _build_revised_content(
        self,
        revised_parsed: Dict[str, Dict[str, Any]],
        content_type: str
    ) -> str:
        """
        根据修正后的解析结果构建完整内容

        Args:
            revised_parsed: 修正后的单元概述字典
            content_type: 内容类型

        Returns:
            完整的单元概述文本
        """
        unit_label = "章" if content_type == "novel" else "集"
        lines = []

        for unit_num in sorted(revised_parsed.keys(), key=int):
            unit_data = revised_parsed[unit_num]
            title = unit_data.get("title", "")
            summary = unit_data.get("summary", "")
            full_content = unit_data.get("full_content", "")

            # 优先使用full_content（包含情节要点、人物状态标注等完整结构化信息）
            # 如果没有full_content，则使用summary
            content_to_use = full_content if full_content else summary

            # 修复2：去除full_content中可能已有的标题行，避免重复
            # 检测并移除开头的标题行（如：### 第X章：XXX 或 **第X集**：XXX）
            import re
            title_patterns = [
                rf"^###\s*第{unit_num}{unit_label}[:：]\s*.*$",  # ### 第X章：标题
                rf"^\*\*第{unit_num}{unit_label}\*\*[:：]\s*.*$",  # **第X集**：标题
                # # 第X章 等各种Markdown标题
                rf"^#{1, 3}\s*.*{unit_num}.*{unit_label}.*$",
            ]

            content_lines = content_to_use.split('\n')
            cleaned_lines = []
            title_removed = False

            for line in content_lines:
                line_stripped = line.strip()
                # 检查是否匹配标题模式
                is_title = False
                for pattern in title_patterns:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        is_title = True
                        title_removed = True
                        break

                # 如果不是标题行，保留
                if not is_title:
                    cleaned_lines.append(line)

            # 如果移除了标题，记录日志
            if title_removed:
                self.logger.info(f"[质量修正] 第{unit_num}单元：移除full_content中的重复标题")

            # 使用清理后的内容
            content_to_use = '\n'.join(cleaned_lines)

            if content_type == "novel":
                lines.append(f"### 第{unit_num}章：{title}")
                lines.append(content_to_use)
            else:
                lines.append(f"**第{unit_num}集**：{title}")
                lines.append(content_to_use)

            lines.append("")  # 空行分隔

        return "\n".join(lines)


# 全局实例
_outline_generator = None


def get_outline_generator(db: AsyncSession = None) -> OutlineGenerator:
    """获取大纲生成器实例"""
    global _outline_generator
    if _outline_generator is None:
        _outline_generator = OutlineGenerator(db)
    elif db is not None:
        _outline_generator.db = db
    return _outline_generator
