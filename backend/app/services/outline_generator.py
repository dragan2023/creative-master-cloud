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

from app.core.logger import get_logger
from app.core.config import get_settings
from app.tools.knowledge_retrieval import get_knowledge_retrieval_tool


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

    async def generate_global_outline(
        self,
        content_type: str,  # novel/script
        input_params: Dict[str, Any],
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_knowledge: bool = True  # 是否启用知识库修正
    ) -> Dict[str, Any]:
        """
        生成全局大纲（第一阶段）

        Args:
            content_type: 内容类型 (novel/script)
            input_params: 输入参数
            provider: LLM提供商
            model: 模型名称
            temperature: 温度参数
            user_id: 用户ID
            enable_knowledge: 是否启用知识库修正

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
            filled_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params, module_name
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
                        temperature=temperature
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
            self.logger.error(f"[全局大纲] 生成失败: {str(e)}")
            result["error"] = str(e)

        return result

    async def generate_global_outline_stream(
        self,
        content_type: str,
        input_params: Dict[str, Any],
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成全局大纲（第一阶段）

        Args:
            content_type: 内容类型 (novel/script)
            input_params: 输入参数
            provider: LLM提供商
            model: 模型名称
            temperature: 温度参数
            user_id: 用户ID

        Yields:
            生成的文本片段
        """
        try:
            # 确定模块名称
            module_name = f"{content_type}_global_outline"

            # 获取提示词模板（使用默认模板，不需要数据库）
            prompt_template = self.prompt_manager.get_default_prompt(
                module_name)
            if not prompt_template:
                raise ValueError(f"未找到提示词模板: {module_name}")

            # 渲染提示词（填充变量）
            filled_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params, module_name
            )

            self.logger.info(f"[全局大纲流式] 开始生成，模块: {module_name}")

            # 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(
                self.db, user_id, provider
            )
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            # 流式调用LLM生成（不传递model参数，使用provider初始化时的model_name）
            async for chunk in llm_provider.generate_stream(
                prompt=filled_prompt,
                temperature=temperature
            ):
                if hasattr(chunk, 'content'):
                    yield chunk.content
                elif isinstance(chunk, str):
                    yield chunk

        except Exception as e:
            self.logger.error(f"[全局大纲流式] 生成失败: {str(e)}")
            yield f"\n\n[错误] 生成失败: {str(e)}"

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
        enable_logic_check: bool = True  # 是否启用逻辑修正
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
            enable_logic_check: 是否启用逻辑修正

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
            "logic_check": None  # 逻辑检测结果
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

            # 获取提示词模板（使用默认模板，不需要数据库）
            prompt_template = self.prompt_manager.get_default_prompt(
                module_name)
            if not prompt_template:
                raise ValueError(f"未找到提示词模板: {module_name}")

            # 渲染提示词（填充变量）
            filled_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params, module_name
            )

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

            # ==================== 逻辑性修正 ====================
            if enable_logic_check and parsed:
                try:
                    self.logger.info("[单元概述] 开始逻辑性检测...")
                    logic_result = await self.check_and_fix_logic_issues(
                        global_outline=global_outline,
                        unit_summaries=parsed,
                        content_type=content_type,
                        provider=provider,
                        temperature=temperature,
                        user_id=user_id
                    )
                    result["logic_check"] = logic_result

                    # 如果检测到问题并有修正内容，更新解析结果
                    revised_units = logic_result.get("revised_units") or {}
                    original_units = logic_result.get("original_units") or {}
                    if logic_result.get("has_issues") and isinstance(revised_units, dict) and revised_units:
                        for unit_num, revised_content in revised_units.items():
                            if unit_num in parsed:
                                # 保存原始内容用于前端差异对比
                                original_unit = original_units.get(
                                    unit_num, {})
                                parsed[unit_num]["original_summary"] = original_unit.get(
                                    "summary", parsed[unit_num].get("summary", ""))
                                # 保存修正后内容
                                parsed[unit_num]["revised_summary"] = revised_content
                                # 更新单元概述内容
                                parsed[unit_num]["summary"] = revised_content
                                parsed[unit_num]["logic_fixed"] = True
                        self.logger.info(
                            f"[单元概述] 逻辑修正完成，修正了 {len(revised_units)} 个单元")
                except Exception as logic_error:
                    # 逻辑检测失败不影响主流程
                    self.logger.warning(
                        f"[单元概述] 逻辑检测失败，使用原始内容: {str(logic_error)}")
                    result["logic_check"] = {"error": str(logic_error)}

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
        cancel_event=None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成单元简要概述（第二阶段）

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
            cancel_event: 取消事件对象（用于中断生成）

        Yields:
            生成的文本片段
        """
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

            # 获取提示词模板（使用默认模板，不需要数据库）
            prompt_template = self.prompt_manager.get_default_prompt(
                module_name)
            if not prompt_template:
                raise ValueError(f"未找到提示词模板: {module_name}")

            # 渲染提示词（填充变量）
            filled_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params, module_name
            )

            self.logger.info(
                f"[单元概述流式] 开始生成，模块: {module_name}，单元数: {unit_count}")

            # 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(
                self.db, user_id, provider
            )
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            # 获取模型支持的最大输出 token 数，确保不会因输出限制而截断
            max_output_tokens = llm_provider.get_max_output_tokens()
            # 对于大量单元的情况，确保有足够的输出空间
            # 估算：每单元约200字，约需 unit_count * 300 tokens
            estimated_tokens = unit_count * 300
            safe_max_tokens = min(
                max(estimated_tokens, 30000), max_output_tokens)
            self.logger.info(
                f"[单元概述流式] 模型最大输出: {max_output_tokens}, 预估需要: {estimated_tokens}, 使用: {safe_max_tokens}")

            # 流式调用LLM生成（不传递model参数，使用provider初始化时的model_name）
            async for chunk in llm_provider.generate_stream(
                prompt=filled_prompt,
                temperature=temperature,
                max_tokens=safe_max_tokens
            ):
                # 检查是否被取消
                if cancel_event and cancel_event.is_set():
                    self.logger.info("[单元概述流式] 生成被取消")
                    break

                if hasattr(chunk, 'content'):
                    yield chunk.content
                elif isinstance(chunk, str):
                    yield chunk

        except Exception as e:
            self.logger.error(f"[单元概述流式] 生成失败: {str(e)}")
            yield f"\n\n[错误] 生成失败: {str(e)}"

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

        # 匹配章节标题和内容
        # 格式：### 第X章：[章节标题]
        chapter_pattern = r'###\s*第(\d+)章[：:]\s*(.+?)(?:\n|$)'
        matches = re.findall(chapter_pattern, content)

        for match in matches:
            chapter_num = int(match[0])
            chapter_title = match[1].strip()

            # 提取章节概要
            # 查找该章节到下一个章节之间的内容
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

            result[str(chapter_num)] = {
                "unit_number": chapter_num,
                "title": chapter_title,
                "summary": summary,
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

        # 判断是电影类型还是剧集类型
        is_movie = "第" in content and "场" in content and "集" not in content

        if is_movie:
            # 电影类型：匹配场景
            pattern = r'\*\*第(\d+)场[：:]\s*(.+?)(?:\n|$)'
        else:
            # 剧集类型：匹配分集
            pattern = r'\*\*第(\d+)集[：:]\s*(.+?)(?:\n|$)'

        matches = re.findall(pattern, content)

        for match in matches:
            unit_num = int(match[0])
            unit_title = match[1].strip()

            # 提取概要
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

            # 提取概要
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

            result[str(unit_num)] = {
                "unit_number": unit_num,
                "title": unit_title,
                "summary": summary,
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }

        return result

    async def _revise_with_knowledge_base(
        self,
        llm_provider,
        original_content: str,
        input_params: Dict[str, Any],
        temperature: float = 0.7
    ) -> Optional[str]:
        """
        使用知识库修正大纲内容

        直接生成修正后的完整内容，替换原始内容

        Args:
            llm_provider: LLM提供者
            original_content: 原始大纲内容
            input_params: 输入参数
            temperature: 温度参数

        Returns:
            修正后的内容，如果修正失败返回None
        """
        try:
            # 获取知识库检索工具
            knowledge_retrieval = get_knowledge_retrieval_tool()

            # 构建查询文本（使用原始内容的关键信息）
            query_text = input_params.get(
                'title', '') + " " + input_params.get('theme', '') + " " + input_params.get('genre', '')
            if not query_text.strip():
                query_text = original_content[:500]

            # 检索三类知识库
            kb_contexts = await knowledge_retrieval.retrieve(
                query=query_text,
                n_results=5
            )

            # 检查是否有知识库内容
            theory_context = kb_contexts.get('theory', '').strip()
            case_context = kb_contexts.get('case', '').strip()
            manual_context = kb_contexts.get('manual', '').strip()

            if not theory_context and not case_context and not manual_context:
                self.logger.info("[知识库修正] 无相关知识点，跳过修正")
                return None

            # 构建修正提示词
            revision_prompt = OUTLINE_REVISION_PROMPT.format(
                original_outline=original_content[:8000],  # 限制长度
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
            if revised_content and len(revised_content) > 500:
                self.logger.info(
                    f"[知识库修正] 修正成功，原长度={len(original_content)}，新长度={len(revised_content)}")
                return revised_content

            self.logger.warning("[知识库修正] 修正内容过短，使用原始内容")
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
                global_outline=global_outline[:6000],  # 限制长度
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
