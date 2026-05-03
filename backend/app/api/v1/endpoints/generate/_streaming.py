"""
创意生成 API - 流式/非流式模块生成端点

包含短视频脚本、剧本大纲、小说大纲、平面广告、TVC广告的生成端点

@date: 2026-04-24
@version: v3.1.0 (从generate.py拆分)
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import GenerationException
from app.core.logger import get_logger
from app.core.module_registry import (
    MODULE_SHORT_VIDEO, MODULE_NOVEL,
    MODULE_PRINT_AD, MODULE_TVC,
    MODULE_MOVIE_OUTLINE, MODULE_SERIES_OUTLINE
)
from app.models import User
from app.schemas.generation import (
    ShortVideoInput, NovelInput, PrintAdInput, TVCInput,
    MovieOutlineInput, SeriesOutlineInput,
    GenerateResponse
)
from app.agents.orchestrator import get_agent_orchestrator

from ._common import parse_kb_ids, _create_streaming_endpoint

logger = get_logger(__name__)


def register_streaming_routes(router: APIRouter):
    """注册各模块的流式/非流式生成路由"""

    # ==================== 短视频脚本生成 ====================

    @router.post("/short-video")
    async def generate_short_video(
        data: ShortVideoInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> GenerateResponse:
        """生成短视频脚本（非流式）"""
        orchestrator = get_agent_orchestrator()

        input_params = data.model_dump()

        # 提取参考视频URL（如果存在）
        reference_video = input_params.get("reference_video")
        videos = [reference_video] if reference_video else None

        result = await orchestrator.generate(
            db=db,
            module=MODULE_SHORT_VIDEO,
            user_id=current_user.id,
            input_params=input_params,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            reference_urls=input_params.get("reference_urls"),
            provider=provider,
            temperature=temperature,
            videos=videos
        )

        if result.get("success"):
            return GenerateResponse(
                success=True,
                content=result.get("content"),
                model=result.get("model"),
                provider=result.get("provider"),
                usage=result.get("usage"),
                duration_ms=result.get("duration_ms"),
                generation_id=result.get("generation_id")
            )
        else:
            raise GenerationException(result.get("error", "生成失败"))

    @router.post("/short-video/stream")
    async def generate_short_video_stream(
        data: ShortVideoInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        enable_mcp: bool = False,
        enable_trending: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        search_keywords: Optional[List[str]] = Query(default=None),
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[str] = None,
        kb_user_specific_ids: Optional[str] = None,
        kb_manual_ids: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """生成短视频脚本（流式）"""
        input_params = data.model_dump()
        reference_video = input_params.get("reference_video")
        videos = [reference_video] if reference_video else None

        logger.info(
            f"短视频流式生成请求: enable_knowledge={enable_knowledge}, enable_search={enable_search}, "
            f"enable_trending={enable_trending}, kb_vertical={kb_vertical}, kb_user_specific={kb_user_specific}, "
            f"kb_manual={kb_manual}, kb_vertical_ids={kb_vertical_ids}, session_id={session_id}"
        )
        logger.debug(f"短视频输入参数: {input_params}")

        return await _create_streaming_endpoint(
            module=MODULE_SHORT_VIDEO,
            input_params=input_params,
            user_id=current_user.id,
            db=db,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            enable_mcp=enable_mcp,
            enable_trending=enable_trending,
            provider=provider,
            temperature=temperature,
            search_keywords=search_keywords,
            kb_vertical=kb_vertical,
            kb_user_specific=kb_user_specific,
            kb_manual=kb_manual,
            kb_vertical_ids=parse_kb_ids(kb_vertical_ids),
            kb_user_specific_ids=parse_kb_ids(kb_user_specific_ids),
            kb_manual_ids=parse_kb_ids(kb_manual_ids),
            videos=videos
        )

    # ==================== 电影大纲生成 ====================

    @router.post("/movie-outline")
    async def generate_movie_outline(
        data: MovieOutlineInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> GenerateResponse:
        """生成电影大纲（非流式）"""
        orchestrator = get_agent_orchestrator()

        input_params = data.model_dump()

        result = await orchestrator.generate(
            db=db,
            module=MODULE_MOVIE_OUTLINE,
            user_id=current_user.id,
            input_params=input_params,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            reference_urls=input_params.get("reference_urls"),
            provider=provider,
            temperature=temperature
        )

        if result.get("success"):
            return GenerateResponse(
                success=True,
                content=result.get("content"),
                model=result.get("model"),
                provider=result.get("provider"),
                usage=result.get("usage"),
                duration_ms=result.get("duration_ms"),
                generation_id=result.get("generation_id")
            )
        else:
            raise GenerationException(result.get("error", "生成失败"))

    @router.post("/movie-outline/stream")
    async def generate_movie_outline_stream(
        data: MovieOutlineInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        enable_mcp: bool = False,
        enable_trending: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        search_keywords: Optional[List[str]] = Query(default=None),
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[str] = None,
        kb_user_specific_ids: Optional[str] = None,
        kb_manual_ids: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """生成电影大纲（流式）"""
        input_params = data.model_dump()
        logger.info(
            f"电影大纲流式生成请求: enable_knowledge={enable_knowledge}, enable_search={enable_search}, "
            f"enable_trending={enable_trending}, kb_vertical={kb_vertical}, session_id={session_id}"
        )
        return await _create_streaming_endpoint(
            module=MODULE_MOVIE_OUTLINE,
            input_params=input_params,
            user_id=current_user.id,
            db=db,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            enable_mcp=enable_mcp,
            enable_trending=enable_trending,
            provider=provider,
            temperature=temperature,
            search_keywords=search_keywords,
            kb_vertical=kb_vertical,
            kb_user_specific=kb_user_specific,
            kb_manual=kb_manual,
            kb_vertical_ids=parse_kb_ids(kb_vertical_ids),
            kb_user_specific_ids=parse_kb_ids(kb_user_specific_ids),
            kb_manual_ids=parse_kb_ids(kb_manual_ids)
        )

    # ==================== 剧集大纲生成 ====================

    @router.post("/series-outline")
    async def generate_series_outline(
        data: SeriesOutlineInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> GenerateResponse:
        """生成剧集大纲（非流式）"""
        orchestrator = get_agent_orchestrator()

        input_params = data.model_dump()

        result = await orchestrator.generate(
            db=db,
            module=MODULE_SERIES_OUTLINE,
            user_id=current_user.id,
            input_params=input_params,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            reference_urls=input_params.get("reference_urls"),
            provider=provider,
            temperature=temperature
        )

        if result.get("success"):
            return GenerateResponse(
                success=True,
                content=result.get("content"),
                model=result.get("model"),
                provider=result.get("provider"),
                usage=result.get("usage"),
                duration_ms=result.get("duration_ms"),
                generation_id=result.get("generation_id")
            )
        else:
            raise GenerationException(result.get("error", "生成失败"))

    @router.post("/series-outline/stream")
    async def generate_series_outline_stream(
        data: SeriesOutlineInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        enable_mcp: bool = False,
        enable_trending: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        search_keywords: Optional[List[str]] = Query(default=None),
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[str] = None,
        kb_user_specific_ids: Optional[str] = None,
        kb_manual_ids: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """生成剧集大纲（流式）"""
        input_params = data.model_dump()
        logger.info(
            f"剧集大纲流式生成请求: enable_knowledge={enable_knowledge}, enable_search={enable_search}, "
            f"enable_trending={enable_trending}, kb_vertical={kb_vertical}, session_id={session_id}"
        )
        return await _create_streaming_endpoint(
            module=MODULE_SERIES_OUTLINE,
            input_params=input_params,
            user_id=current_user.id,
            db=db,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            enable_mcp=enable_mcp,
            enable_trending=enable_trending,
            provider=provider,
            temperature=temperature,
            search_keywords=search_keywords,
            kb_vertical=kb_vertical,
            kb_user_specific=kb_user_specific,
            kb_manual=kb_manual,
            kb_vertical_ids=parse_kb_ids(kb_vertical_ids),
            kb_user_specific_ids=parse_kb_ids(kb_user_specific_ids),
            kb_manual_ids=parse_kb_ids(kb_manual_ids)
        )

    # ==================== 小说大纲生成 ====================

    @router.post("/novel")
    async def generate_novel(
        data: NovelInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> GenerateResponse:
        """生成小说大纲（非流式）"""
        orchestrator = get_agent_orchestrator()

        input_params = data.model_dump()

        result = await orchestrator.generate(
            db=db,
            module=MODULE_NOVEL,
            user_id=current_user.id,
            input_params=input_params,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            reference_urls=input_params.get("reference_urls"),
            provider=provider,
            temperature=temperature
        )

        if result.get("success"):
            return GenerateResponse(
                success=True,
                content=result.get("content"),
                model=result.get("model"),
                provider=result.get("provider"),
                usage=result.get("usage"),
                duration_ms=result.get("duration_ms"),
                generation_id=result.get("generation_id")
            )
        else:
            raise GenerationException(result.get("error", "生成失败"))

    @router.post("/novel/stream")
    async def generate_novel_stream(
        data: NovelInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        enable_mcp: bool = False,
        enable_trending: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        search_keywords: Optional[List[str]] = Query(default=None),
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[str] = None,
        kb_user_specific_ids: Optional[str] = None,
        kb_manual_ids: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """生成小说大纲（流式）"""
        input_params = data.model_dump()
        logger.info(
            f"小说流式生成请求: enable_knowledge={enable_knowledge}, enable_search={enable_search}, "
            f"enable_trending={enable_trending}, kb_vertical={kb_vertical}, session_id={session_id}"
        )
        return await _create_streaming_endpoint(
            module=MODULE_NOVEL,
            input_params=input_params,
            user_id=current_user.id,
            db=db,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            enable_mcp=enable_mcp,
            enable_trending=enable_trending,
            provider=provider,
            temperature=temperature,
            search_keywords=search_keywords,
            kb_vertical=kb_vertical,
            kb_user_specific=kb_user_specific,
            kb_manual=kb_manual,
            kb_vertical_ids=parse_kb_ids(kb_vertical_ids),
            kb_user_specific_ids=parse_kb_ids(kb_user_specific_ids),
            kb_manual_ids=parse_kb_ids(kb_manual_ids)
        )

    # ==================== 平面广告生成 ====================

    @router.post("/print-ad")
    async def generate_print_ad(
        data: PrintAdInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> GenerateResponse:
        """生成平面广告文案（非流式）"""
        orchestrator = get_agent_orchestrator()

        input_params = data.model_dump()

        result = await orchestrator.generate(
            db=db,
            module=MODULE_PRINT_AD,
            user_id=current_user.id,
            input_params=input_params,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            reference_urls=input_params.get("reference_urls"),
            provider=provider,
            temperature=temperature
        )

        if result.get("success"):
            return GenerateResponse(
                success=True,
                content=result.get("content"),
                model=result.get("model"),
                provider=result.get("provider"),
                usage=result.get("usage"),
                duration_ms=result.get("duration_ms"),
                generation_id=result.get("generation_id")
            )
        else:
            raise GenerationException(result.get("error", "生成失败"))

    @router.post("/print-ad/stream")
    async def generate_print_ad_stream(
        data: PrintAdInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        enable_mcp: bool = False,
        enable_trending: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        search_keywords: Optional[List[str]] = Query(default=None),
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[str] = None,
        kb_user_specific_ids: Optional[str] = None,
        kb_manual_ids: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """生成平面广告文案（流式）"""
        input_params = data.model_dump()
        logger.info(
            f"平面广告流式生成请求: enable_knowledge={enable_knowledge}, enable_search={enable_search}, "
            f"enable_trending={enable_trending}, kb_vertical={kb_vertical}, images={len(input_params.get('images', [])) if input_params.get('images') else 0}, session_id={session_id}"
        )
        return await _create_streaming_endpoint(
            module=MODULE_PRINT_AD,
            input_params=input_params,
            user_id=current_user.id,
            db=db,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            enable_mcp=enable_mcp,
            enable_trending=enable_trending,
            provider=provider,
            temperature=temperature,
            search_keywords=search_keywords,
            kb_vertical=kb_vertical,
            kb_user_specific=kb_user_specific,
            kb_manual=kb_manual,
            kb_vertical_ids=parse_kb_ids(kb_vertical_ids),
            kb_user_specific_ids=parse_kb_ids(kb_user_specific_ids),
            kb_manual_ids=parse_kb_ids(kb_manual_ids),
            images=input_params.get("images")
        )

    # ==================== TVC广告脚本生成 ====================

    @router.post("/tvc")
    async def generate_tvc(
        data: TVCInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> GenerateResponse:
        """生成TVC广告脚本（非流式）"""
        orchestrator = get_agent_orchestrator()

        input_params = data.model_dump()

        # 提取参考视频URL（如果存在）
        reference_video = input_params.get("reference_video")
        videos = [reference_video] if reference_video else None

        result = await orchestrator.generate(
            db=db,
            module=MODULE_TVC,
            user_id=current_user.id,
            input_params=input_params,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            reference_urls=input_params.get("reference_urls"),
            provider=provider,
            temperature=temperature,
            videos=videos
        )

        if result.get("success"):
            return GenerateResponse(
                success=True,
                content=result.get("content"),
                model=result.get("model"),
                provider=result.get("provider"),
                usage=result.get("usage"),
                duration_ms=result.get("duration_ms"),
                generation_id=result.get("generation_id")
            )
        else:
            raise GenerationException(result.get("error", "生成失败"))

    @router.post("/tvc/stream")
    async def generate_tvc_stream(
        data: TVCInput,
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        enable_mcp: bool = False,
        enable_trending: bool = False,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        search_keywords: Optional[List[str]] = Query(default=None),
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[str] = None,
        kb_user_specific_ids: Optional[str] = None,
        kb_manual_ids: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """生成TVC广告脚本（流式）"""
        input_params = data.model_dump()
        reference_video = input_params.get("reference_video")
        videos = [reference_video] if reference_video else None

        logger.info(
            f"TVC流式生成请求: enable_knowledge={enable_knowledge}, enable_search={enable_search}, "
            f"enable_trending={enable_trending}, kb_vertical={kb_vertical}, reference_video={'有' if reference_video else '无'}, session_id={session_id}"
        )

        return await _create_streaming_endpoint(
            module=MODULE_TVC,
            input_params=input_params,
            user_id=current_user.id,
            db=db,
            session_id=session_id,
            enable_search=enable_search,
            enable_knowledge=enable_knowledge,
            enable_mcp=enable_mcp,
            enable_trending=enable_trending,
            provider=provider,
            temperature=temperature,
            search_keywords=search_keywords,
            kb_vertical=kb_vertical,
            kb_user_specific=kb_user_specific,
            kb_manual=kb_manual,
            kb_vertical_ids=parse_kb_ids(kb_vertical_ids),
            kb_user_specific_ids=parse_kb_ids(kb_user_specific_ids),
            kb_manual_ids=parse_kb_ids(kb_manual_ids),
            videos=videos
        )
