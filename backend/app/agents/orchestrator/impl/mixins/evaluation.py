"""Agent编排器 - 评估与自洽检查Mixin"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
import json
import re
from app.core.logger import get_logger, LoggerAdapter
from app.core.config import get_settings


class EvaluationMixin:
    """评估与自洽检查"""

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
{content}

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
{original_content}

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
                llm_provider.get_max_output_tokens(), get_settings().MAX_LLM_OUTPUT_TOKENS)
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
{original_content}

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


