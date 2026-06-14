"""AI视觉资源生成引擎

提供独立的AI视觉资源生成能力，支持流式和非流式两种模式。
与剧本正文生成流程完全解耦，用户可基于任意版本剧本触发生成。

@date: 2026-06-04
@version: v1.0.0
"""
import json
from typing import AsyncGenerator, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.logger import get_logger

logger = get_logger("ai_resource.generator")


class AIResourceGenerator:
    """AI视觉资源独立生成引擎

    职责:
    1. 接收剧本正文内容 + 风格配置
    2. 构建AI资源生成提示词
    3. 调用LLM流式/非流式生成
    4. 返回生成结果

    使用方式:
        generator = AIResourceGenerator()
        async for chunk in generator.generate_stream(
            script_content=content,
            unit_title="第1集：黎明之战",
            style_config={"content_type": "series", "aspect_ratio": "16:9"},
            db=db,
            user_id=user_id
        ):
            yield chunk
    """

    async def generate_stream(
        self,
        script_content: str,
        unit_title: str = "",
        style_config: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None,
        user_id: int = 0
    ) -> AsyncGenerator[str, None]:
        """流式生成AI视觉资源

        调用LLM逐块生成AI视觉资源内容，适用于SSE推送给前端。

        Args:
            script_content: 剧本完整内容(含场景列表/正文/拍摄脚本/分镜设计/配乐参考)
            unit_title: 单元标题
            style_config: 风格配置字典
            db: 数据库会话
            user_id: 用户ID

        Yields:
            SSE格式的字符串事件，包括:
            - event: chunk / data: {"text": "..."}
            - event: complete / data: {"message": "...", "content_length": N}
            - event: error / data: {"message": "..."}
        """
        if not script_content:
            yield self._format_sse("error", {"message": "剧本内容为空，无法生成AI资源"})
            return

        style_config = style_config or {}
        logger.info(
            f"[AI资源生成] 开始流式生成, content_length={len(script_content)}, "
            f"unit_title={unit_title}"
        )

        try:
            # 构建提示词
            from app.agents.writing.prompts.ai_resource_prompts import build_ai_resource_generation_prompt
            system_prompt, user_prompt = build_ai_resource_generation_prompt(
                script_content=script_content,
                unit_title=unit_title,
                style_config=style_config
            )

            # 获取LLM provider
            from app.agents.llm_manager import LLMManager
            llm_manager = LLMManager()
            llm_provider = await llm_manager.get_provider_from_db(
                db=db, user_id=user_id
            )
            if not llm_provider:
                yield self._format_sse("error", {"message": "未找到可用的LLM提供商"})
                return

            # 流式调用LLM
            full_content = ""
            if hasattr(llm_provider, 'generate_stream'):
                async for chunk in llm_provider.generate_stream(
                    prompt=user_prompt,
                    system_prompt=system_prompt
                ):
                    if chunk:
                        full_content += chunk
                        yield self._format_sse("chunk", {"text": chunk})
            else:
                # 不支持流式，使用非流式回退
                logger.info("[AI资源生成] LLM不支持流式，使用非流式回退")
                response = await llm_provider.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt
                )
                full_content = response.content if hasattr(response, 'content') else str(response)
                yield self._format_sse("chunk", {"text": full_content})

            logger.info(f"[AI资源生成] 流式生成完成, length={len(full_content)}")
            yield self._format_sse("complete", {
                "message": "AI资源生成完成",
                "content_length": len(full_content),
                "content": full_content,
            })

        except Exception as e:
            logger.error(f"[AI资源生成] 生成失败: {e}", exc_info=True)
            yield self._format_sse("error", {"message": f"AI资源生成失败: {str(e)}"})

    async def generate(
        self,
        script_content: str,
        unit_title: str = "",
        style_config: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None,
        user_id: int = 0
    ) -> Dict[str, Any]:
        """非流式生成AI视觉资源

        Args:
            script_content: 剧本完整内容
            unit_title: 单元标题
            style_config: 风格配置字典
            db: 数据库会话
            user_id: 用户ID

        Returns:
            生成结果字典:
            - success: bool
            - content: str (生成的内容)
            - content_length: int
            - error: str (失败时的错误信息)
        """
        if not script_content:
            return {"success": False, "content": "", "content_length": 0, "error": "剧本内容为空"}

        style_config = style_config or {}
        logger.info(
            f"[AI资源生成] 开始非流式生成, content_length={len(script_content)}"
        )

        try:
            # 构建提示词
            from app.agents.writing.prompts.ai_resource_prompts import build_ai_resource_generation_prompt
            system_prompt, user_prompt = build_ai_resource_generation_prompt(
                script_content=script_content,
                unit_title=unit_title,
                style_config=style_config
            )

            # 获取LLM provider
            from app.agents.llm_manager import LLMManager
            llm_manager = LLMManager()
            llm_provider = await llm_manager.get_provider_from_db(
                db=db, user_id=user_id
            )
            if not llm_provider:
                return {"success": False, "content": "", "content_length": 0, "error": "未找到可用的LLM提供商"}

            # 非流式调用
            response = await llm_provider.generate(
                prompt=user_prompt,
                system_prompt=system_prompt
            )
            full_content = response.content if hasattr(response, 'content') else str(response)

            logger.info(f"[AI资源生成] 非流式生成完成, length={len(full_content)}")
            return {
                "success": True,
                "content": full_content,
                "content_length": len(full_content),
                "error": None
            }

        except Exception as e:
            logger.error(f"[AI资源生成] 非流式生成失败: {e}", exc_info=True)
            return {"success": False, "content": "", "content_length": 0, "error": str(e)}

    @staticmethod
    def _format_sse(event_type: str, data: dict) -> str:
        """格式化SSE事件"""
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
