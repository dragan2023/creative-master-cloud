"""Agent编排器 - 反思生成与完成Mixin"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
import re
from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory


class ReflectionMixin:
    """反思生成与完成"""

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


