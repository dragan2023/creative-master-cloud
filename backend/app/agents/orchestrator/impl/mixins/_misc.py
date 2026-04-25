"""Agent编排器 - 辅助方法Mixin"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import AsyncGenerator
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
import json
import re
import asyncio
from app.core.logger import get_logger, LoggerAdapter
from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory


class MiscMixin:
    """辅助方法"""

    async def _evaluate_result(
        self,
        content: str,
        input_params: Dict[str, Any],
        module: str
    ) -> Dict[str, Any]:
        """
        评估生成结果质量

        Args:
            content: 生成的内容
            input_params: 输入参数
            module: 模块名称

        Returns:
            评估结果 {"score": 0-100, "issues": [...], "needs_retry": bool}
        """
        issues = []
        score = 100

        # 1. 检查内容长度
        if len(content) < 100:
            issues.append("内容过短")
            score -= 30
        elif len(content) < 300:
            issues.append("内容可能不够详细")
            score -= 10

        # 2. 检查是否包含关键元素
        topic = input_params.get("topic", "") or input_params.get(
            "theme", "") or input_params.get("synopsis", "")
        if topic and topic.lower() not in content.lower():
            issues.append("内容与主题关联度可能不足")
            score -= 15

        # 3. 检查结构完整性
        structure_markers = ["一、", "二、", "三、", "1.", "2.", "3.", "#", "##"]
        has_structure = any(marker in content for marker in structure_markers)
        if not has_structure:
            issues.append("内容结构可能不够清晰")
            score -= 10

        # 4. 检查是否有明确的结尾
        ending_markers = ["总结", "结语", "结尾", "完", "以上"]
        has_ending = any(marker in content for marker in ending_markers)
        if not has_ending and len(content) > 500:
            issues.append("内容可能缺少明确的结尾")
            score -= 5

        # 5. 根据模块检查特定内容
        module_checks = {
            "short_video": ["脚本", "场景", "镜头", "台词"],
            "script": ["场景", "人物", "对话", "剧情"],
            "novel": ["人物", "情节", "背景"],
            "print_ad": ["文案", "视觉", "核心"],
            "tvc": ["场景", "镜头", "旁白"]
        }

        if module in module_checks:
            keywords = module_checks[module]
            missing_keywords = [kw for kw in keywords if kw not in content]
            if len(missing_keywords) > len(keywords) // 2:
                issues.append(f"内容可能缺少关键元素: {', '.join(missing_keywords[:2])}")
                score -= 10

        # 确保分数在合理范围
        score = max(0, min(100, score))

        return {
            "score": score,
            "issues": issues,
            "needs_retry": score < 60 and len(issues) > 2
        }


    async def _generate_revised_content(
        self,
        llm_provider,
        original_content: str,
        evaluation_result: Dict[str, Any],
        kb_contexts: Dict[str, str],
        system_prompt: str,
        temperature: float,
        input_params: Dict[str, Any],
        cancel_event: Optional[asyncio.Event] = None
    ) -> Optional[str]:
        """
        根据评估结果，生成修正后的完整内容（非追加，而是重写）

        Args:
            llm_provider: LLM提供者
            original_content: 原始生成内容
            evaluation_result: 评估结果
            kb_contexts: 三类知识库内容
            system_prompt: 系统提示词
            temperature: 温度参数
            input_params: 输入参数（用于获取AI平台等信息）

        Returns:
            修正后的完整内容
        """
        theory_issues = evaluation_result.get("theory_issues", [])
        case_insights = evaluation_result.get("case_insights", [])
        user_specific_issues = evaluation_result.get(
            "user_specific_issues", [])
        compliance_issues = evaluation_result.get("compliance_issues", [])

        # 获取用户选择的AI平台
        ai_platforms = input_params.get("ai_platforms") or ""
        if isinstance(ai_platforms, list):
            ai_platforms = ", ".join(ai_platforms)
        ai_platforms = ai_platforms.strip()

        ai_platform_hint = ""
        if ai_platforms and ai_platforms != "无":
            ai_platform_hint = f"""

**【强制】AI平台名称保留**：
- 原始内容中的AI视频生成提示词标题必须严格使用平台名称："{ai_platforms}"
- 禁止更改为其他名称（如 SEDANCE、SoraDance、Seedance2 等）
- 禁止添加版本号（如 2.0、2 等）
- 必须完全按照 "{ai_platforms}" 输出"""

        # 构建修正提示词
        revision_prompt = f"""你是专业的创意优化师。你的任务是基于原始回答和知识库参考，生成一份**完整且优化后**的内容。

## 原始回答（必须以此为基础进行优化，保留所有内容）
{original_content}

## 知识库参考（用于优化指导）
- 通用创意理论：{kb_contexts.get('theory', '无')}
- 垂直领域案例：{kb_contexts.get('case', '无')}
- 用户专属知识：{kb_contexts.get('user_specific', '无')}
- 官方规范手册：{kb_contexts.get('manual', '无')}

## 评估发现的问题（需要针对性优化）
- 理论支撑问题：{theory_issues if theory_issues else '无'}
- 案例启发建议：{case_insights if case_insights else '无'}
- 用户专属知识应用：{user_specific_issues if user_specific_issues else '无'}
- 规范符合问题：{compliance_issues if compliance_issues else '无'}

## 优化任务要求（必须严格遵守）

1. **【强制】完整输出**：必须输出完整的优化版本，包含原始回答的所有分镜、所有段落、所有内容。禁止只输出部分片段或修改的部分。
2. **【强制】保留结构**：保留原始回答的完整结构，包括标题、表格、分镜描述、AI提示词等所有部分。
3. **【强制】内容完整**：确保所有分镜序号（如分镜1、分镜2...分镜9）都包含在输出中，不要遗漏任何一部分。
4. **理论融入**：自然地运用相关创意理论，增强专业性
5. **案例转化**：从案例中提取方法论和亮点，创新性转化（绝不照搬）
6. **用户专属知识应用**：合理应用用户专属知识库中的内容，满足用户特定需求
7. **规范遵守**：严格遵守官方规范手册中的所有规定
8. **保持创意**：不要变得死板，保持内容的灵活性和创新性
{ai_platform_hint}

## 输出格式要求
- 输出完整的Markdown格式内容
- 保留所有表格、标题、列表等格式
- 确保内容长度与原始回答相当或更长

请直接输出优化后的**完整内容**（不要省略任何部分）：
"""

        try:
            # 使用流式生成修正内容，设置动态max_tokens确保内容完整
            safe_output_limit = min(
                llm_provider.get_max_output_tokens(), settings.MAX_LLM_OUTPUT_TOKENS)
            revised_content = []
            async for chunk in llm_provider.generate_stream(
                prompt=revision_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=safe_output_limit
            ):
                # 检查取消事件
                if cancel_event and cancel_event.is_set():
                    self.logger.info("内容重写被取消")
                    return None

                revised_content.append(chunk)

            result = "".join(revised_content)
            return result if result.strip() else None

        except Exception as e:
            self.logger.exception("内容重写失败")
            return None


    async def create_session(
        self,
        user_id: int,
        module: str
    ) -> str:
        """
        创建新会话

        Args:
            user_id: 用户ID
            module: 模块名称

        Returns:
            会话ID
        """
        return await self.memory_manager.create_session(
            user_id=user_id,
            module=module
        )


    def _compress_revision_history(self, revision_history: List[Dict], max_rounds: int = 3) -> str:
        """
        压缩修订历史为摘要

        策略:
        - 仅保留最近max_rounds轮
        - 每轮压缩为: "第N轮: 用户要求X → 修改了Y"
        """
        if not revision_history:
            return "无历史修订"

        recent = revision_history[-max_rounds:]
        summaries = []
        for rev in recent:
            feedback = rev.get('user_feedback', '')[:30]
            diff_instructions = rev.get('diff_instructions', '')
            try:
                diff_data = json.loads(
                    diff_instructions) if diff_instructions else {}
                summary = diff_data.get('summary', '已修改')
            except json.JSONDecodeError:
                summary = '已修改'

            summary_text = f"第{rev['round_number']}轮: 用户要求'{feedback}...' → {summary}"
            summaries.append(summary_text)

        return "\n".join(summaries) if summaries else "无历史修订"


    async def _auto_fix_issues(
        self,
        llm_provider,
        original_content: str,
        consistency_result: Dict[str, Any],
        temperature: float
    ) -> Optional[str]:
        """
        自动修正发现的问题

        Args:
            llm_provider: LLM提供者
            original_content: 原始内容
            consistency_result: 自洽性检查结果
            temperature: 温度参数

        Returns:
            修正补充内容
        """
        issues = consistency_result.get("issues", [])
        if not issues:
            return None

        fix_prompt = f"""你是内容修正专家。请根据以下发现的问题，生成修正或补充内容。

## 原始内容（部分）
{original_content[:2000]}

## 发现的问题
{chr(10).join('- ' + issue for issue in issues)}

## 任务
请直接输出修正或补充的内容。要求：
1. 只输出需要修正或补充的部分
2. 不要重复原始内容
3. 使用清晰的格式

修正内容："""

        try:
            safe_output_limit = min(
                llm_provider.get_max_output_tokens(), settings.MAX_LLM_OUTPUT_TOKENS)
            fix_content = []
            async for chunk in llm_provider.generate_stream(
                prompt=fix_prompt,
                temperature=temperature,
                max_tokens=safe_output_limit
            ):
                fix_content.append(chunk)

            result = "".join(fix_content)
            return result if result.strip() else None

        except Exception as e:
            self.logger.exception("自动修正失败")
            return None


    async def generate_revision_diff(
        self,
        db: AsyncSession,
        generation_id: int,
        user_feedback: str,
        current_content: str,
        original_params: Dict[str, Any],
        module: str,
        round_number: int,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        user_id: int = 0  # 新增user_id参数
    ) -> AsyncGenerator[str, None]:
        """
        生成修订差异指令(流式)

        输出格式(JSON):
        {
            "modifications": [
                {
                    "type": "replace|insert|delete",
                    "location": "第3段第2行",
                    "original_text": "原文内容",
                    "new_text": "新内容",
                    "reason": "用户要求..."
                }
            ],
            "summary": "本次修改概述"
        }
        """
        from app.utils.diff_applier import validate_diff_instructions
        import json

        logger = self.logger

        try:
            # 1. 加载LLM provider - 修复：传入正确的db和user_id参数
            llm_provider = await self._load_llm_provider(db, user_id, provider)
            logger.info(
                f"Revision: LLM provider loaded successfully for user {user_id}")

            # 2. 获取修订历史
            logger.info(
                f"Revision: Loading revision history for generation {generation_id}")
            revision_history_stmt = select(GenerationRevisionHistory).where(
                GenerationRevisionHistory.generation_id == generation_id
            ).order_by(GenerationRevisionHistory.round_number)
            revision_history_result = await db.execute(revision_history_stmt)
            revision_history = revision_history_result.scalars().all()
            logger.info(
                f"Revision: Found {len(revision_history)} previous revisions")

            # 3. 构建修订提示词
            logger.info(
                f"Revision: Building revision prompt for round {round_number}")
            prompt = self._build_revision_prompt(
                module=module,
                original_params=original_params,
                current_content=current_content,
                user_feedback=user_feedback,
                revision_history=[rev.to_dict() for rev in revision_history],
                round_number=round_number
            )
            logger.info(f"Revision: Prompt length: {len(prompt)} characters")

            # 4. 流式调用LLM
            logger.info("Revision: Starting LLM stream generation")
            diff_instructions_text = ""
            chunk_count = 0
            async for chunk in llm_provider.generate_stream(prompt):
                diff_instructions_text += chunk
                chunk_count += 1
                # 发送SSE事件
                yield f"data: {json.dumps({'event': 'diff_chunk', 'data': chunk}, ensure_ascii=False)}\n\n"

            logger.info(
                f"Revision: LLM stream completed, received {chunk_count} chunks, total length: {len(diff_instructions_text)}")

            # 5. 解析JSON
            try:
                # 尝试提取JSON
                json_match = re.search(
                    r'```json\s*({.*?})\s*```', diff_instructions_text, re.DOTALL)
                if json_match:
                    diff_instructions = json.loads(json_match.group(1))
                else:
                    # 尝试直接解析
                    diff_instructions = json.loads(diff_instructions_text)

                # 验证格式
                if not validate_diff_instructions(diff_instructions):
                    raise ValueError("Invalid diff instructions format")

                # 发送完成事件
                yield f"data: {json.dumps({'event': 'diff_complete', 'data': diff_instructions}, ensure_ascii=False)}\n\n"

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse diff instructions: {e}")
                yield f"data: {json.dumps({'event': 'error', 'data': '解析差异指令失败'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(
                f"Revision diff generation failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'data': f'修订生成失败: {str(e)}'}, ensure_ascii=False)}\n\n"


    def _format_sse(self, event: str, data: Dict[str, Any]) -> str:
        """
        格式化为 SSE 格式

        Args:
            event: 事件类型
            data: 数据

        Returns:
            SSE 格式字符串
        """
        data_str = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {data_str}\n\n"


    def _build_revision_prompt(
        self,
        module: str,
        original_params: Dict[str, Any],
        current_content: str,
        user_feedback: str,
        revision_history: List[Dict],
        round_number: int
    ) -> str:
        """
        构建修订提示词

        核心设计:
        1. 包含原始生成参数(保持创作方向)
        2. 包含当前完整内容(作为修改基准)
        3. 包含用户本轮修改意见
        4. 压缩历史修订记录(最近3轮摘要)
        5. 强制要求输出JSON格式diff指令
        """
        # 压缩历史修订
        history_summary = self._compress_revision_history(revision_history)

        prompt = f"""# 创意内容修订指令

## 原始创作参数
{json.dumps(original_params, ensure_ascii=False, indent=2)}

## 当前完整内容
{current_content}

## 用户修改意见(本轮)
{user_feedback}

## 历史修订摘要(最近3轮)
{history_summary}

## 输出格式要求(强制)

你必须严格按照以下JSON格式输出修订指令,不得包含其他内容:

```json
{{
    "modifications": [
        {{
            "type": "replace",  // replace|insert|delete
            "location": "精确定位(如:第3节第2段)",
            "original_text": "被替换的原文(仅replace/delete需要)",
            "new_text": "新增或替换的内容",
            "reason": "修改原因"
        }}
    ],
    "summary": "本次修改的简要说明(50字以内)"
}}
```

## 修订原则
1. **精确定位**: 必须明确指出修改位置
2. **最小变更**: 只修改用户要求的部分,保持其他内容不变
3. **保持连贯**: 修改后的内容必须与上下文连贯
4. **遵守原始要求**: 不得偏离原始创作参数

现在,请根据用户修改意见生成修订指令。"""
        return prompt


    async def _reflect_and_retry(
        self,
        db: AsyncSession,
        module: str,
        user_id: int,
        input_params: Dict[str, Any],
        original_content: str,
        evaluation: Dict[str, Any],
        session_id: Optional[str] = None,
        enable_search: bool = False,
        knowledge_base_id: Optional[str] = None,
        reference_urls: Optional[List[str]] = None,
        provider: Optional[str] = None,
        max_retries: int = 1
    ) -> Dict[str, Any]:
        """
        反思并重试生成

        Args:
            原始参数...
            original_content: 原始生成内容
            evaluation: 评估结果
            max_retries: 最大重试次数

        Returns:
            改进后的生成结果
        """
        logger = get_logger(str(user_id))

        if max_retries <= 0 or not evaluation.get("needs_retry"):
            return {
                "success": True,
                "content": original_content,
                "reflected": False
            }

        logger.info(f"开始反思重试 - 问题: {evaluation['issues']}")

        try:
            # 获取 LLM 提供者
            llm_provider = await self.llm_manager.get_provider_from_db(
                db=db, user_id=user_id, provider_name=provider
            )

            # 构建反思提示
            reflection_prompt = f"""
你之前生成的内容存在以下问题：
{chr(10).join('- ' + issue for issue in evaluation['issues'])}

原始内容：
{original_content[:1000]}...

请改进内容，确保：
1. 内容更加详细和完整
2. 结构清晰，有明确的章节划分
3. 紧扣主题，提供有价值的信息
4. 符合{module}类型的标准格式

请重新生成改进后的内容：
"""

            # 获取提示词模板
            prompt_template = await self.prompt_manager.get_prompt(db, module)
            system_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params)

            # 调用 LLM 重新生成
            response = await llm_provider.generate(
                prompt=reflection_prompt,
                system_prompt=system_prompt,
                temperature=0.8  # 稍微提高温度以获得更多变化
            )

            # 评估新结果
            new_evaluation = await self._evaluate_result(response.content, input_params, module)

            # 如果新结果更好，使用新结果
            if new_evaluation["score"] > evaluation["score"]:
                logger.info(f"反思改进成功 - 新分数: {new_evaluation['score']}")
                return {
                    "success": True,
                    "content": response.content,
                    "model": response.model,
                    "provider": response.provider,
                    "reflected": True,
                    "improvement": new_evaluation["score"] - evaluation["score"]
                }
            else:
                logger.info("反思未改善结果，保留原始内容")
                return {
                    "success": True,
                    "content": original_content,
                    "reflected": True,
                    "improvement": 0
                }

        except Exception as e:
            logger.exception("反思重试失败")
            return {
                "success": True,
                "content": original_content,
                "reflected": False,
                "error": str(e)
            }


    async def _evaluate_with_llm(
        self,
        llm_provider,
        first_answer: str,
        kb_contexts: Dict[str, str],
        input_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用 LLM 评估初次回答与三类知识库的偏差

        评估维度：
        1. 理论支撑：是否恰当运用创意理论？
        2. 案例启发：是否受案例启发但非照搬？
        3. 规范符合：是否遵守用户手册？

        Args:
            llm_provider: LLM提供者
            first_answer: 初次生成的回答
            kb_contexts: 三类知识库内容
            input_params: 用户输入参数

        Returns:
            {
                "theory_issues": ["问题1", "问题2"],
                "case_insights": ["启发点1", "启发点2"],
                "compliance_issues": ["违规1"],
                "needs_revision": true/false,
                "explanation": "评估说明"
            }
        """
        evaluation_prompt = f"""你是专业的创意质量评审专家。

【用户需求】
{json.dumps(input_params, ensure_ascii=False, indent=2)}

【初次回答】
{first_answer[:2500]}

【创意理论知识库】
{kb_contexts.get('theory', '无相关理论')}

【垂直领域案例知识库】
{kb_contexts.get('case', '无相关案例')}

【用户专属知识库】
{kb_contexts.get('user_specific', '无用户专属知识')}

【官方规范手册】
{kb_contexts.get('manual', '无规范手册')}

## 评估任务

请从以下四个维度评估初次回答：

### 1. 理论支撑性
- 是否运用了知识库中的创意理论？
- 理论应用是否恰当合理？
- **注意**：不要求死板套用理论，重点是看是否有理论支撑

### 2. 案例启发性（重点）
- 是否从案例中提取了创意思路、爆点设计或吸引点？
- **严格要求**：禁止直接复制案例的具体内容、框架或文案
- **正确做法**：分析案例背后的方法论和亮点，进行创新性转化

### 3. 用户专属知识应用
- 是否合理应用了用户专属知识库中的内容？
- 是否符合用户的特定需求和偏好？

### 4. 规范符合性
- 是否违反官方规范手册中的要求？
- 如有明确规范，是否严格遵守？

## 输出要求

请以JSON格式输出评估结果：

{{
    "theory_issues": ["如：未运用知识库中的'悬念理论'"],
    "case_insights": ["如：可借鉴案例中的'反差式开头'但需重新设计"],
    "user_specific_issues": ["如：未应用用户专属知识中的特定要求"],
    "compliance_issues": ["如：违反手册'禁止使用夸张词汇'的规定"],
    "needs_revision": true,
    "explanation": "简要说明是否需要修正及原因"
}}

如果内容质量良好、无重大问题，返回：
{{"theory_issues": [], "case_insights": [], "user_specific_issues": [], "compliance_issues": [], "needs_revision": false, "explanation": "内容符合要求"}}
"""

        try:
            # 使用较低温度进行稳定分析
            response = await llm_provider.generate(
                prompt=evaluation_prompt,
                temperature=0.3,
                max_tokens=30000
            )

            result_text = response.content.strip()

            # 尝试解析JSON结果
            import re
            json_match = re.search(
                r'\{[^{}]*"needs_revision"[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return {
                        "theory_issues": result.get("theory_issues", []),
                        "case_insights": result.get("case_insights", []),
                        "user_specific_issues": result.get("user_specific_issues", []),
                        "compliance_issues": result.get("compliance_issues", []),
                        "needs_revision": result.get("needs_revision", False),
                        "explanation": result.get("explanation", "")
                    }
                except json.JSONDecodeError:
                    pass

            # 如果JSON解析失败，返回默认结果
            return {
                "theory_issues": [],
                "case_insights": [],
                "user_specific_issues": [],
                "compliance_issues": [],
                "needs_revision": False,
                "explanation": "评估完成"
            }

        except Exception as e:
            # 使用 logger 记录错误
            self.logger.exception("LLM评估失败")
            return {
                "theory_issues": [],
                "case_insights": [],
                "user_specific_issues": [],
                "compliance_issues": [],
                "needs_revision": False,
                "explanation": f"评估失败: {str(e)}"
            }


    async def _get_user_graphrag_config(
        self,
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """
        获取用户的 GraphRAG 配置

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            是否启用 GraphRAG，默认为 True
        """
        try:
            from app.models import SystemConfig
            import json

            config_key = f"user_preprocessor_config_{user_id}"
            result = await db.execute(
                select(SystemConfig).where(SystemConfig.id == config_key)
            )
            config_record = result.scalar_one_or_none()

            if config_record and config_record.config_value:
                config_data = json.loads(config_record.config_value)
                return config_data.get("graphrag_enabled", True)

            return True  # 默认启用
        except Exception as e:
            self.logger.exception("获取 GraphRAG 配置失败")
            return True  # 出错时默认启用


    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        获取会话消息

        Args:
            session_id: 会话ID
            limit: 最大消息数

        Returns:
            消息列表
        """
        return await self.memory_manager.get_messages(session_id, limit)


    async def generate_with_reflection(
        self,
        db: AsyncSession,
        module: str,
        user_id: int,
        input_params: Dict[str, Any],
        session_id: Optional[str] = None,
        enable_search: bool = False,
        knowledge_base_id: Optional[str] = None,
        reference_urls: Optional[List[str]] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        enable_reflection: bool = True
    ) -> Dict[str, Any]:
        """
        带自主反思的生成

        Args:
            同 generate 方法
            enable_reflection: 是否启用反思机制

        Returns:
            生成结果
        """
        # 先执行正常生成
        result = await self.generate(
            db=db,
            module=module,
            user_id=user_id,
            input_params=input_params,
            session_id=session_id,
            enable_search=enable_search,
            knowledge_base_id=knowledge_base_id,
            reference_urls=reference_urls,
            provider=provider,
            temperature=temperature
        )

        if not result.get("success"):
            return result

        # 如果启用反思，评估结果
        if enable_reflection:
            evaluation = await self._evaluate_result(
                result["content"],
                input_params,
                module
            )

            result["evaluation"] = evaluation

            # 如果需要重试
            if evaluation.get("needs_retry"):
                reflection_result = await self._reflect_and_retry(
                    db=db,
                    module=module,
                    user_id=user_id,
                    input_params=input_params,
                    original_content=result["content"],
                    evaluation=evaluation,
                    session_id=session_id,
                    enable_search=enable_search,
                    knowledge_base_id=knowledge_base_id,
                    reference_urls=reference_urls,
                    provider=provider
                )

                if reflection_result.get("reflected"):
                    result.update(reflection_result)

        return result


    async def finalize_generation(
        self,
        db: AsyncSession,
        generation_id: int,
        final_content: str,
        enable_knowledge_check: bool = True,
        enable_self_reflection: bool = True
    ) -> Dict[str, Any]:
        """
        最终确认生成内容,执行优化

        流程:
        1. 更新generation记录(is_finalized=True)
        2. 如启用知识库检查:
           - 调用_evaluate_with_llm验证内容
           - 生成优化建议
        3. 如启用自反思:
           - 调用_evaluate_result评估质量
           - 如需要优化,调用_reflect_and_retry生成改进版本
        4. 返回最终内容
        """
        logger = self.logger

        try:
            # 1. 更新数据库
            generation = await db.get(Generation, generation_id)
            if not generation:
                return {"success": False, "error": "Generation not found"}

            generation.output_content = final_content
            generation.is_finalized = True
            await db.commit()

            optimized_content = final_content
            knowledge_issues = []
            reflection_suggestions = []

            # 2. 知识库验证(可选)
            if enable_knowledge_check:
                try:
                    # TODO: 实现知识库验证逻辑
                    # evaluation_result = await self._evaluate_with_llm(...)
                    logger.info(
                        "Knowledge check enabled (not yet implemented)")
                except Exception as e:
                    logger.error(f"Knowledge check failed: {e}")

            # 3. 自反思优化(可选)
            if enable_self_reflection:
                try:
                    # TODO: 实现自反思逻辑
                    # reflection_result = await self._reflect_and_retry(...)
                    logger.info(
                        "Self-reflection enabled (not yet implemented)")
                except Exception as e:
                    logger.error(f"Self-reflection failed: {e}")

            # 4. 更新最终内容
            generation.output_content = optimized_content
            await db.commit()

            return {
                "success": True,
                "final_content": optimized_content,
                "knowledge_issues": knowledge_issues,
                "reflection_suggestions": reflection_suggestions
            }

        except Exception as e:
            logger.error(f"Finalize generation failed: {e}")
            return {"success": False, "error": str(e)}


    async def _check_self_consistency(
        self,
        llm_provider,
        content: str,
        input_params: Dict[str, Any],
        module: str,
        temperature: float
    ) -> Dict[str, Any]:
        """
        自洽性检查：验证内容的逻辑一致性、事实准确性

        使用LLM进行多维度分析：
        1. 逻辑一致性：前后内容是否矛盾
        2. 事实准确性：关键信息是否合理
        3. 格式完整性：是否遗漏必要元素

        Args:
            llm_provider: LLM提供者
            content: 生成的内容
            input_params: 输入参数
            module: 模块名称
            temperature: 温度参数

        Returns:
            {"issues": [...], "needs_fix": bool, "details": str}
        """
        issues = []

        # 构建自洽性检查提示词
        consistency_prompt = f"""你是一个专业的内容审核专家。请对以下内容进行自洽性检查，识别逻辑问题、矛盾或不合理之处。

## 用户原始需求
{json.dumps(input_params, ensure_ascii=False, indent=2)}

## 生成的内容
{content[:3000]}

## 检查要求
请检查以下维度：
1. **逻辑一致性**：内容前后是否矛盾？时间线是否合理？
2. **主题相关性**：内容是否紧扣用户的主题需求？
3. **格式完整性**：是否包含用户要求的特定格式（如AI视频提示词、分镜脚本等）？
4. **信息准确性**：是否有明显的事实错误或不合理描述？

## 输出格式
请用JSON格式输出检查结果：
{{"issues": ["问题1", "问题2"], "needs_fix": true/false, "summary": "简要总结"}}

如果内容质量良好，无重大问题，返回：{{"issues": [], "needs_fix": false, "summary": "内容质量良好，逻辑清晰"}}"""

        try:
            # 使用较低温度进行稳定分析
            response = await llm_provider.generate(
                prompt=consistency_prompt,
                temperature=0.3,
                max_tokens=30000
            )

            result_text = response.content.strip()

            # 尝试解析JSON结果
            import re
            json_match = re.search(
                r'\{[^{}]*"issues"[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return {
                        "issues": result.get("issues", []),
                        "needs_fix": result.get("needs_fix", False),
                        "summary": result.get("summary", "")
                    }
                except json.JSONDecodeError:
                    pass

            # 如果JSON解析失败，返回基本结果
            return {
                "issues": [],
                "needs_fix": False,
                "summary": "检查完成"
            }

        except Exception as e:
            self.logger.exception("自洽性检查失败")
            return {
                "issues": [],
                "needs_fix": False,
                "summary": f"检查失败: {str(e)}"
            }


