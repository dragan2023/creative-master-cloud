"""
创意生成 API - 原创IP计划生成与修订相关端点

@date: 2026-04-24
@version: v3.1.0 (从generate.py拆分)
"""
import json
import asyncio
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import (
    GenerationException,
    ResourceNotFoundException,
)
from app.core.logger import get_logger
from app.core.module_registry import MODULE_ORIGINAL_IP
from app.models import User, GenerationModule, GenerationStatus
from app.models.generation import GenerationRevisionHistory
from app.schemas.generation import (
    OriginalIPInput, RevisionRequest, FinalizeRequest,
    GenerateResponse,
)
from app.schemas.common import ResponseModel
from app.services.generation_service import GenerationService
from app.agents.orchestrator import get_agent_orchestrator

from ._common import parse_kb_ids, cancel_tokens

logger = get_logger(__name__)


def register_original_ip_routes(router: APIRouter):
    """注册原创IP计划生成路由"""

    @router.post("/original-ip")
    async def generate_original_ip(
        data: OriginalIPInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.8,
        # 搜索关键词参数
        search_keywords: Optional[List[str]] = Query(default=None),
        # 知识库类别选择参数（与其他模块保持一致）
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[str] = None,
        kb_user_specific_ids: Optional[str] = None,
        kb_manual_ids: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> GenerateResponse:
        """
        生成原创IP计划（非流式）

        用户只需提供一个概括性的IP角色描述，AI将自动解析并构建完整的角色IP档案。

        输出包含：
        - 完整的角色IP档案（五维度构建）
        - 实操流程
        - 落地方案
        - AI辅助执行方案
        - 角色发展路线图
        """
        # 使用 orchestrator 统一处理
        orchestrator = get_agent_orchestrator()

        # 解析知识库ID
        vertical_ids = parse_kb_ids(kb_vertical_ids)
        user_specific_ids = parse_kb_ids(kb_user_specific_ids)
        manual_ids = parse_kb_ids(kb_manual_ids)

        # 解析搜索关键词
        keywords_list = search_keywords if search_keywords else None

        # 构建输入参数
        input_params = {
            "ip_description": data.ip_description,
            "target_platform": data.target_platform or "综合",
            "reference_ip": data.reference_ip,
            "commercial_goal": data.commercial_goal,
            "custom_requirements": data.custom_requirements,
            "topic": data.ip_description[:100] if data.ip_description else "IP角色设计",
        }

        result = await orchestrator.generate(
            db=db,
            module=MODULE_ORIGINAL_IP,
            user_id=current_user.id,
            input_params=input_params,
            session_id=session_id,
            enable_search=enable_search,
            search_keywords=keywords_list,
            enable_knowledge=True,
            reference_urls=None,
            provider=provider,
            temperature=temperature,
            kb_vertical=kb_vertical,
            kb_user_specific=kb_user_specific,
            kb_manual=kb_manual,
            kb_vertical_ids=vertical_ids,
            kb_user_specific_ids=user_specific_ids,
            kb_manual_ids=manual_ids
        )

        if result.get("success"):
            # 保存生成记录
            try:
                # 从 input_params 中提取标题
                title = None
                input_params_dict = data.model_dump()
                if input_params_dict:
                    title_keys = ['ip_name', 'title',
                                  'topic', 'theme', 'subject', 'name']
                    for key in title_keys:
                        if key in input_params_dict and input_params_dict[key]:
                            title = str(input_params_dict[key])[:200]
                            break

                generation_service = GenerationService(db)
                generation = await generation_service.save_generation(
                    user_id=current_user.id,
                    module=GenerationModule.ORIGINAL_IP,
                    input_params=input_params_dict,
                    title=title,
                    output_content=result.get("content"),
                    provider=result.get("provider"),
                    model_name=result.get("model"),
                    token_count=result.get("usage", {}).get("total_tokens", 0),
                    duration_ms=result.get("duration_ms", 0),
                    status=GenerationStatus.COMPLETED,
                )
                generation_id = generation.id
            except Exception as e:
                logger.warning(f"保存生成记录失败: {e}")
                generation_id = None

            logger.info(
                f"用户 {current_user.id} 生成原创IP计划成功 - "
                f"描述长度: {len(data.ip_description)}, "
                f"耗时: {result.get('duration_ms')}ms"
            )

            return GenerateResponse(
                success=True,
                content=result.get("content"),
                model=result.get("model"),
                provider=result.get("provider"),
                usage=result.get("usage"),
                duration_ms=result.get("duration_ms"),
                generation_id=generation_id
            )
        else:
            raise GenerationException(result.get("error", "生成失败"))

    @router.post("/original-ip/stream")
    async def generate_original_ip_stream(
        data: OriginalIPInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.8,
        # 搜索关键词参数
        search_keywords: Optional[List[str]] = Query(default=None),
        # 知识库类别选择参数（与其他模块保持一致）
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[str] = None,
        kb_user_specific_ids: Optional[str] = None,
        kb_manual_ids: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        生成原创IP计划（流式）

        用户只需提供一个概括性的IP角色描述，AI将自动解析并构建完整的角色IP档案。
        支持中断机制：通过 session_id 可以调用 /cancel/{session_id} 取消生成。
        """
        # 使用 orchestrator 统一处理，确保工作流程与其他模块一致
        orchestrator = get_agent_orchestrator()

        # 创建取消令牌
        cancel_event = asyncio.Event()
        if session_id:
            cancel_tokens[session_id] = cancel_event

        # 解析知识库ID
        vertical_ids = parse_kb_ids(kb_vertical_ids)
        user_specific_ids = parse_kb_ids(kb_user_specific_ids)
        manual_ids = parse_kb_ids(kb_manual_ids)

        # 解析搜索关键词
        keywords_list = search_keywords if search_keywords else None

        # 构建输入参数（映射到 orchestrator 期望的格式）
        input_params = {
            "ip_description": data.ip_description,
            "target_platform": data.target_platform or "综合",
            "reference_ip": data.reference_ip,
            "commercial_goal": data.commercial_goal,
            "custom_requirements": data.custom_requirements,
            # 用于知识库检索
            "topic": data.ip_description[:100] if data.ip_description else "IP角色设计",
        }

        # 用于收集完整内容的缓冲区
        content_buffer = []

        async def generate():
            try:
                async for chunk in orchestrator.generate_stream(
                    db=db,
                    module=MODULE_ORIGINAL_IP,
                    user_id=current_user.id,
                    input_params=input_params,
                    session_id=session_id,
                    enable_search=enable_search,
                    search_keywords=keywords_list,
                    enable_knowledge=True,  # 启用知识库
                    reference_urls=None,
                    provider=provider,
                    temperature=temperature,
                    cancel_event=cancel_event,
                    kb_vertical=kb_vertical,
                    kb_user_specific=kb_user_specific,
                    kb_manual=kb_manual,
                    kb_vertical_ids=vertical_ids,
                    kb_user_specific_ids=user_specific_ids,
                    kb_manual_ids=manual_ids
                ):
                    # 检查是否被取消
                    if cancel_event.is_set():
                        logger.info(f"原创IP生成被取消: {session_id}")
                        break

                    # 解析 SSE 数据以提取内容
                    if chunk.startswith("event: content\ndata: "):
                        try:
                            json_str = chunk.split("data: ", 1)[1].strip()
                            if json_str:
                                content_data = json.loads(json_str)
                                if content_data.get("text"):
                                    content_buffer.append(content_data["text"])
                        except (json.JSONDecodeError, IndexError):
                            pass

                    yield chunk
            finally:
                # 清理取消令牌
                if session_id and session_id in cancel_tokens:
                    del cancel_tokens[session_id]

                # 保存生成记录
                if content_buffer:
                    try:
                        full_content = "".join(content_buffer)
                        # 从 input_params 中提取标题
                        title = None
                        input_params_dict = data.model_dump()
                        if input_params_dict:
                            title_keys = ['ip_name', 'title',
                                          'topic', 'theme', 'subject', 'name']
                            for key in title_keys:
                                if key in input_params_dict and input_params_dict[key]:
                                    title = str(input_params_dict[key])[:200]
                                    break

                        generation_service = GenerationService(db)
                        await generation_service.save_generation(
                            user_id=current_user.id,
                            module=GenerationModule.ORIGINAL_IP,
                            input_params=input_params_dict,
                            title=title,
                            output_content=full_content,
                            provider=provider,
                            status=GenerationStatus.COMPLETED,
                        )
                    except Exception as e:
                        logger.warning(f"保存生成记录失败: {e}")

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )


def register_revision_routes(router: APIRouter):
    """注册修订相关路由"""

    @router.post("/revision/{generation_id}/stream")
    async def revise_content_stream(
        generation_id: int,
        request: RevisionRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        流式生成修订差异指令

        工作流程:
        1. 加载原始生成记录和上下文
        2. 构建修订提示词(包含原始内容+用户反馈)
        3. LLM输出差异指令(流式)
        4. 前端接收后应用diff
        """
        orchestrator = get_agent_orchestrator()

        async def event_generator():
            try:
                logger.info(
                    f"Revision stream started: generation_id={generation_id}, user={current_user.id}")

                # 保存修订历史记录
                revision_record = GenerationRevisionHistory(
                    generation_id=generation_id,
                    round_number=request.round_number,
                    user_feedback=request.user_feedback,
                    content_before=request.current_content
                )
                db.add(revision_record)
                await db.commit()
                logger.info(
                    f"Revision history record saved for round {request.round_number}")

                # 流式生成修订差异 - 修复：传递user_id参数
                logger.info(
                    f"Calling generate_revision_diff with user_id={current_user.id}")
                async for chunk in orchestrator.generate_revision_diff(
                    db=db,
                    generation_id=generation_id,
                    user_feedback=request.user_feedback,
                    current_content=request.current_content,
                    original_params=request.original_params,
                    module=request.module,
                    round_number=request.round_number,
                    provider=request.provider,
                    temperature=request.temperature,
                    user_id=current_user.id  # 修复：传递user_id
                ):
                    yield chunk

                logger.info(
                    f"Revision stream completed successfully for generation {generation_id}")

            except Exception as e:
                logger.error(f"Revision stream failed: {e}", exc_info=True)
                yield f"data: {json.dumps({'event': 'error', 'data': f'修订流失败: {str(e)}'}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )

    @router.post("/finalize/{generation_id}")
    async def finalize_generation(
        generation_id: int,
        request: FinalizeRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """最终确认生成内容,执行知识库修正和自反思优化"""
        try:
            orchestrator = get_agent_orchestrator()

            result = await orchestrator.finalize_generation(
                db=db,
                generation_id=generation_id,
                final_content=request.final_content,
                enable_knowledge_check=request.enable_knowledge_check,
                enable_self_reflection=request.enable_self_reflection
            )

            if result.get("success"):
                return ResponseModel(
                    code=200,
                    message="最终确认成功",
                    data=result
                )
            else:
                raise GenerationException(result.get("error", "最终确认失败"))

        except Exception as e:
            logger.error(f"Finalize generation failed: {e}")
            raise GenerationException(str(e))

    @router.get("/revision/{generation_id}/history")
    async def get_revision_history(
        generation_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """获取某次生成的修订历史记录"""
        try:
            from sqlalchemy import select

            stmt = select(GenerationRevisionHistory).where(
                GenerationRevisionHistory.generation_id == generation_id
            ).order_by(GenerationRevisionHistory.round_number)

            result = await db.execute(stmt)
            revisions = result.scalars().all()

            return ResponseModel(
                code=200,
                message="获取修订历史成功",
                data=[rev.to_dict() for rev in revisions]
            )

        except Exception as e:
            logger.error(f"Get revision history failed: {e}")
            raise ResourceNotFoundException(str(e))
