"""Agent编排器 - LLM修正与版本差异Mixin"""
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
from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory
from app.core.config import get_settings


class RevisionMixin:
    """LLM修正与版本差异"""

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
- 版本号以用户选择的平台名称原样保留（如"Seedance 2.0""MiniMax H3"），禁止随意增删或改写
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
                llm_provider.get_max_output_tokens(), get_settings().MAX_LLM_OUTPUT_TOKENS)
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
            # 1. 加载LLM provider - 修复：_load_llm_provider 返回 (provider, display_name) 元组，需解包
            llm_provider, _model_display_name = await self._load_llm_provider(db, user_id, provider)
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


    async def generate_revision_full_content(
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
        user_id: int = 0
    ) -> AsyncGenerator[str, None]:
        """
        生成修订后的完整内容(流式)

        与 generate_revision_diff 的差异指令方案不同：
        LLM 直接输出修改后的完整内容，前端整段替换。
        避免 LLM 转写原文与真实内容存在细微差异（换行符、标点、格式等）
        导致 diff 匹配失败而“静默不生效”的问题。

        SSE 事件格式:
        - content: {"text": "修订后内容片段"}
        - diff_complete: {"summary": "修改概述"}
        - error: {"data": "错误信息"}
        """
        import json

        logger = self.logger

        try:
            # 1. 加载LLM provider
            llm_provider, _model_display_name = await self._load_llm_provider(
                db, user_id, provider)
            logger.info(
                f"Revision(full): LLM provider loaded successfully for user {user_id}")

            # 2. 获取修订历史
            logger.info(
                f"Revision(full): Loading revision history for generation {generation_id}")
            revision_history_stmt = select(GenerationRevisionHistory).where(
                GenerationRevisionHistory.generation_id == generation_id
            ).order_by(GenerationRevisionHistory.round_number)
            revision_history_result = await db.execute(revision_history_stmt)
            revision_history = revision_history_result.scalars().all()
            logger.info(
                f"Revision(full): Found {len(revision_history)} previous revisions")

            # 3. 构建全文修订提示词
            logger.info(
                f"Revision(full): Building full-content revision prompt for round {round_number}")
            prompt = self._build_full_revision_prompt(
                module=module,
                original_params=original_params,
                current_content=current_content,
                user_feedback=user_feedback,
                revision_history=[rev.to_dict() for rev in revision_history],
                round_number=round_number
            )
            logger.info(
                f"Revision(full): Prompt length: {len(prompt)} characters")

            # 4. 流式调用LLM，直接输出修订后的完整内容
            logger.info("Revision(full): Starting LLM stream generation")
            async for chunk in llm_provider.generate_stream(prompt):
                yield self._format_sse("content", {"text": chunk})

            # 5. 发送完成事件
            yield self._format_sse("diff_complete", {
                "summary": f"已根据'{user_feedback[:50]}'完成修订",
            })

        except Exception as e:
            logger.error(
                f"Revision(full) generation failed: {e}", exc_info=True)
            yield self._format_sse("error", {"data": f"修订生成失败: {str(e)}"})


    def _build_full_revision_prompt(
        self,
        module: str,
        original_params: Dict[str, Any],
        current_content: str,
        user_feedback: str,
        revision_history: List[Dict],
        round_number: int
    ) -> str:
        """
        构建全文修订提示词

        与 diff 方案不同：要求 LLM 直接输出修订后的完整内容，
        而不是输出差异指令 JSON。
        """
        # 压缩历史修订
        history_summary = self._compress_revision_history(revision_history)

        prompt = f"""# 创意内容全文修订

## 原始创作参数
{json.dumps(original_params, ensure_ascii=False, indent=2)}

## 当前完整内容
{current_content}

## 用户修改意见(本轮)
{user_feedback}

## 历史修订摘要(最近3轮)
{history_summary}

## 任务

请根据用户的修改意见，对上述内容进行修订，并**直接输出修订后的完整内容**。

## 修订原则
1. **保持核心**：保持内容的核心创意、整体结构和原有格式
2. **最小变更**：只修改用户要求的部分，其余内容原样保留
3. **完整输出**：必须输出修改后的完整内容，不得省略或截断
4. **保持连贯**：修改后的内容必须逻辑自洽、可直接使用
5. **遵守原始要求**：不得偏离原始创作参数

现在，请直接输出修订后的完整内容（不要输出 JSON、不要输出任何解释）："""
        return prompt


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


