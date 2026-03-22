"""
创意生成 API 端点
提供短视频脚本、剧本大纲、小说大纲、平面广告、TVC广告脚本的生成功能
支持流式和非流式生成
支持多模态文件上传
"""
from typing import Dict, Any
from pydantic import BaseModel
from app.services.outline_generator import get_outline_generator
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid
import aiofiles
from datetime import datetime

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.schemas.generation import (
    ShortVideoInput, ScriptInput, NovelInput, PrintAdInput, TVCInput,
    GenerateRequest, GenerateResponse, SessionCreateResponse,
    UserActionCreate, UserActionResponse, ActionStatsResponse,
    GenerationHistoryResponse, OptimizeRequest, OptimizeResponse,
    OriginalIPInput
)
from app.schemas.common import ResponseModel
from app.models import User, Generation, GenerationModule, GenerationStatus, UserAction
from app.agents.orchestrator import get_agent_orchestrator
from app.core.logger import get_logger
from app.core.config import get_settings
import json
import asyncio

# 存储取消令牌的字典
cancel_tokens = {}

router = APIRouter(prefix="/generate", tags=["创意生成"])
logger = get_logger(__name__)


def parse_kb_ids(ids_str: Optional[str]) -> Optional[List[int]]:
    """
    安全解析知识库ID列表字符串
    过滤掉 'null', 'undefined', 空字符串等无效值

    Args:
        ids_str: 逗号分隔的ID字符串，如 "1,2,3" 或 "null" 或 None

    Returns:
        整数ID列表或None
    """
    if not ids_str:
        return None
    # 过滤无效值
    invalid_values = {'null', 'undefined', 'none', ''}
    try:
        ids = [int(x.strip()) for x in ids_str.split(",")
               if x.strip().lower() not in invalid_values and x.strip()]
        return ids if ids else None
    except ValueError:
        logger.warning(f"无效的知识库ID字符串: {ids_str}")
        return None


@router.post("/cancel/{session_id}")
async def cancel_generation(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    取消生成任务
    """
    if session_id in cancel_tokens:
        cancel_tokens[session_id].set()
        logger.info(f"用户 {current_user.id} 请求取消生成任务: {session_id}")
        return ResponseModel(success=True, message="取消请求已发送")
    else:
        return ResponseModel(success=False, message="任务不存在或已结束")

# 支持的图片格式
ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp"
}

# 支持的文档格式（大纲文件）
ALLOWED_DOC_TYPES = {
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/pdf": ".pdf"
}

# 支持的文档扩展名
ALLOWED_DOC_EXTENSIONS = [".txt", ".md", ".doc", ".docx", ".pdf"]


# ==================== 文件上传 ====================

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    上传文件（支持图片和文档）

    Args:
        file: 上传的文件

    Returns:
        文件URL和文件信息
    """
    from app.core.config import get_settings
    settings = get_settings()

    content_type = file.content_type or ""
    file_ext = None
    file_type = None  # 'image' or 'document'

    # 检查是否为图片
    if content_type in ALLOWED_IMAGE_TYPES:
        file_ext = ALLOWED_IMAGE_TYPES[content_type]
        file_type = 'image'
        max_size = settings.MAX_IMAGE_SIZE
    # 检查是否为文档
    elif content_type in ALLOWED_DOC_TYPES:
        file_ext = ALLOWED_DOC_TYPES[content_type]
        file_type = 'document'
        max_size = settings.MAX_DOC_SIZE
    else:
        # 尝试通过文件扩展名判断
        original_ext = os.path.splitext(file.filename)[
            1].lower() if file.filename else ""
        if original_ext in ALLOWED_DOC_EXTENSIONS:
            file_ext = original_ext
            file_type = 'document'
            max_size = settings.MAX_DOC_SIZE
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型: {content_type or original_ext}。支持图片(png/jpg/gif/webp)或文档(txt/md/doc/docx/pdf)，最大{int(settings.MAX_IMAGE_SIZE / 1024 / 1024)}MB"
            )

    # 检查文件大小
    content = await file.read()
    if len(content) > max_size:
        size_mb = max_size / 1024 / 1024
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制（{file_type == 'image' and '图片' or '文档'}最大{int(size_mb)}MB）"
        )

    # 获取上传目录
    upload_dir = settings.get_upload_dir()

    # 生成唯一文件名
    file_name = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(upload_dir, file_name)

    # 保存文件
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # 返回文件URL
    file_url = f"/api/v1/generate/uploads/{file_name}"

    return ResponseModel(data={
        "url": file_url,
        "file_name": file_name,
        "content_type": content_type,
        "size": len(content),
        "file_type": file_type
    })


@router.post("/upload/multiple")
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    批量上传文件

    Args:
        files: 上传的文件列表

    Returns:
        文件URL列表
    """
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="最多同时上传5个文件"
        )

    results = []
    for file in files:
        try:
            result = await upload_file(file, current_user)
            results.append(result.data)
        except HTTPException as e:
            results.append({
                "error": e.detail,
                "file_name": file.filename
            })

    return ResponseModel(data={"files": results})


@router.get("/uploads/{file_name}")
async def get_uploaded_file(file_name: str):
    """
    获取上传的文件

    Args:
        file_name: 文件名

    Returns:
        文件内容
    """
    from fastapi.responses import FileResponse
    from app.core.config import get_settings

    settings = get_settings()
    upload_dir = settings.get_upload_dir()
    file_path = os.path.join(upload_dir, file_name)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )

    # 安全检查：防止目录遍历攻击
    if not os.path.abspath(file_path).startswith(os.path.abspath(upload_dir)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="访问被拒绝"
        )

    return FileResponse(file_path)


# ==================== 会话管理 ====================

@router.post("/session", response_model=SessionCreateResponse)
async def create_session(
    module: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新的生成会话

    Args:
        module: 生成模块名称

    Returns:
        会话ID
    """
    orchestrator = get_agent_orchestrator()
    user_id = current_user.id if current_user else 0
    session_id = await orchestrator.create_session(user_id, module)
    return SessionCreateResponse(session_id=session_id)


@router.get("/session/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = 20,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    获取会话历史消息

    Args:
        session_id: 会话ID
        limit: 最大消息数

    Returns:
        消息列表
    """
    orchestrator = get_agent_orchestrator()
    messages = await orchestrator.get_session_messages(session_id, limit)
    return {"messages": messages}


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
    """
    生成短视频脚本（非流式）
    """
    orchestrator = get_agent_orchestrator()

    input_params = data.model_dump()

    # 提取参考视频URL（如果存在）
    reference_video = input_params.get("reference_video")
    videos = [reference_video] if reference_video else None

    result = await orchestrator.generate(
        db=db,
        module="short_video",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "生成失败")
        )


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
    # 搜索关键词参数
    search_keywords: Optional[List[str]] = Query(default=None),
    # 知识库类别选择参数
    kb_vertical: bool = False,
    kb_user_specific: bool = False,
    kb_manual: bool = False,
    kb_vertical_ids: Optional[str] = None,  # 逗号分隔的ID列表
    kb_user_specific_ids: Optional[str] = None,
    kb_manual_ids: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成短视频脚本（流式）
    """
    # 解析ID列表
    vertical_ids = parse_kb_ids(kb_vertical_ids)
    user_specific_ids = parse_kb_ids(kb_user_specific_ids)
    manual_ids = parse_kb_ids(kb_manual_ids)

    logger.info(
        f"短视频流式生成请求: enable_knowledge={enable_knowledge}, kb_vertical={kb_vertical}, kb_user_specific={kb_user_specific}, kb_manual={kb_manual}, session_id={session_id}")

    orchestrator = get_agent_orchestrator()

    input_params = data.model_dump()

    # 提取参考视频URL（如果存在）
    reference_video = input_params.get("reference_video")
    videos = [reference_video] if reference_video else None

    # 创建取消令牌
    cancel_event = asyncio.Event()
    if session_id:
        cancel_tokens[session_id] = cancel_event

    async def event_generator():
        try:
            async for chunk in orchestrator.generate_stream(
                db=db,
                module="short_video",
                user_id=current_user.id,
                input_params=input_params,
                session_id=session_id,
                enable_search=enable_search,
                search_keywords=search_keywords,
                enable_knowledge=enable_knowledge,
                enable_mcp=enable_mcp or enable_trending,
                reference_urls=input_params.get("reference_urls"),
                provider=provider,
                temperature=temperature,
                videos=videos,
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
                    logger.info(f"生成任务被取消: {session_id}")
                    break
                yield chunk
        finally:
            # 清理取消令牌
            if session_id and session_id in cancel_tokens:
                del cancel_tokens[session_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


# ==================== 剧本大纲生成 ====================

@router.post("/script")
async def generate_script(
    data: ScriptInput,
    session_id: Optional[str] = None,
    enable_search: bool = False,
    enable_knowledge: bool = False,
    provider: Optional[str] = None,
    temperature: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> GenerateResponse:
    """
    生成剧本大纲（非流式）
    """
    orchestrator = get_agent_orchestrator()

    input_params = data.model_dump()

    result = await orchestrator.generate(
        db=db,
        module="script",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "生成失败")
        )


@router.post("/script/stream")
async def generate_script_stream(
    data: ScriptInput,
    session_id: Optional[str] = None,
    enable_search: bool = False,
    enable_knowledge: bool = False,
    enable_mcp: bool = False,
    enable_trending: bool = False,
    provider: Optional[str] = None,
    temperature: float = 0.7,
    # 搜索关键词参数
    search_keywords: Optional[List[str]] = Query(default=None),
    # 知识库类别选择参数
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
    生成剧本大纲（流式）
    """
    # 解析ID列表
    vertical_ids = parse_kb_ids(kb_vertical_ids)
    user_specific_ids = parse_kb_ids(kb_user_specific_ids)
    manual_ids = parse_kb_ids(kb_manual_ids)

    orchestrator = get_agent_orchestrator()

    input_params = data.model_dump()

    # 创建取消令牌
    cancel_event = asyncio.Event()
    if session_id:
        cancel_tokens[session_id] = cancel_event

    async def event_generator():
        try:
            async for chunk in orchestrator.generate_stream(
                db=db,
                module="script",
                user_id=current_user.id,
                input_params=input_params,
                session_id=session_id,
                enable_search=enable_search,
                search_keywords=search_keywords,
                enable_knowledge=enable_knowledge,
                enable_mcp=enable_mcp or enable_trending,
                reference_urls=input_params.get("reference_urls"),
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
                    logger.info(f"生成任务被取消: {session_id}")
                    break
                yield chunk
        finally:
            # 清理取消令牌
            if session_id and session_id in cancel_tokens:
                del cancel_tokens[session_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
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
    """
    生成小说大纲（非流式）
    """
    orchestrator = get_agent_orchestrator()

    input_params = data.model_dump()

    result = await orchestrator.generate(
        db=db,
        module="novel",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "生成失败")
        )


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
    # 搜索关键词参数
    search_keywords: Optional[List[str]] = Query(default=None),
    # 知识库类别选择参数
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
    生成小说大纲（流式）
    """
    # 解析ID列表
    vertical_ids = parse_kb_ids(kb_vertical_ids)
    user_specific_ids = parse_kb_ids(kb_user_specific_ids)
    manual_ids = parse_kb_ids(kb_manual_ids)

    orchestrator = get_agent_orchestrator()

    input_params = data.model_dump()

    # 创建取消令牌
    cancel_event = asyncio.Event()
    if session_id:
        cancel_tokens[session_id] = cancel_event

    async def event_generator():
        try:
            async for chunk in orchestrator.generate_stream(
                db=db,
                module="novel",
                user_id=current_user.id,
                input_params=input_params,
                session_id=session_id,
                enable_search=enable_search,
                search_keywords=search_keywords,
                enable_knowledge=enable_knowledge,
                enable_mcp=enable_mcp or enable_trending,
                reference_urls=input_params.get("reference_urls"),
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
                    logger.info(f"生成任务被取消: {session_id}")
                    break
                yield chunk
        finally:
            # 清理取消令牌
            if session_id and session_id in cancel_tokens:
                del cancel_tokens[session_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
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
    """
    生成平面广告文案（非流式）
    """
    orchestrator = get_agent_orchestrator()

    input_params = data.model_dump()

    result = await orchestrator.generate(
        db=db,
        module="print_ad",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "生成失败")
        )


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
    # 搜索关键词参数
    search_keywords: Optional[List[str]] = Query(default=None),
    # 知识库类别选择参数
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
    生成平面广告文案（流式）
    """
    # 解析ID列表
    vertical_ids = parse_kb_ids(kb_vertical_ids)
    user_specific_ids = parse_kb_ids(kb_user_specific_ids)
    manual_ids = parse_kb_ids(kb_manual_ids)

    orchestrator = get_agent_orchestrator()

    input_params = data.model_dump()

    # 创建取消令牌
    cancel_event = asyncio.Event()
    if session_id:
        cancel_tokens[session_id] = cancel_event

    async def event_generator():
        try:
            async for chunk in orchestrator.generate_stream(
                db=db,
                module="print_ad",
                user_id=current_user.id,
                input_params=input_params,
                session_id=session_id,
                enable_search=enable_search,
                search_keywords=search_keywords,
                enable_knowledge=enable_knowledge,
                enable_mcp=enable_mcp or enable_trending,
                reference_urls=input_params.get("reference_urls"),
                provider=provider,
                temperature=temperature,
                images=input_params.get("images"),
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
                    logger.info(f"生成任务被取消: {session_id}")
                    break
                yield chunk
        finally:
            # 清理取消令牌
            if session_id and session_id in cancel_tokens:
                del cancel_tokens[session_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
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
    """
    生成TVC广告脚本（非流式）
    """
    orchestrator = get_agent_orchestrator()

    input_params = data.model_dump()

    # 提取参考视频URL（如果存在）
    reference_video = input_params.get("reference_video")
    videos = [reference_video] if reference_video else None

    result = await orchestrator.generate(
        db=db,
        module="tvc",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "生成失败")
        )


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
    # 搜索关键词参数
    search_keywords: Optional[List[str]] = Query(default=None),
    # 知识库类别选择参数
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
    生成TVC广告脚本（流式）
    """
    # 解析ID列表
    vertical_ids = parse_kb_ids(kb_vertical_ids)
    user_specific_ids = parse_kb_ids(kb_user_specific_ids)
    manual_ids = parse_kb_ids(kb_manual_ids)

    orchestrator = get_agent_orchestrator()

    input_params = data.model_dump()

    # 提取参考视频URL（如果存在）
    reference_video = input_params.get("reference_video")
    videos = [reference_video] if reference_video else None

    # 创建取消令牌
    cancel_event = asyncio.Event()
    if session_id:
        cancel_tokens[session_id] = cancel_event

    async def event_generator():
        try:
            async for chunk in orchestrator.generate_stream(
                db=db,
                module="tvc",
                user_id=current_user.id,
                input_params=input_params,
                session_id=session_id,
                enable_search=enable_search,
                search_keywords=search_keywords,
                enable_knowledge=enable_knowledge,
                enable_mcp=enable_mcp or enable_trending,
                reference_urls=input_params.get("reference_urls"),
                provider=provider,
                temperature=temperature,
                videos=videos,
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
                    logger.info(f"生成任务被取消: {session_id}")
                    break
                yield chunk
        finally:
            # 清理取消令牌
            if session_id and session_id in cancel_tokens:
                del cancel_tokens[session_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


# ==================== 生成历史 ====================

@router.get("/history")
async def get_generation_history(
    module: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户的生成历史

    Args:
        module: 模块筛选
        limit: 每页数量
        offset: 偏移量

    Returns:
        生成历史列表
    """
    from sqlalchemy import select, desc, func

    # 构建基础查询条件
    base_query = select(Generation).where(
        Generation.user_id == current_user.id
    )

    if module:
        base_query = base_query.where(Generation.module == module)

    # 获取总数
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 获取分页数据
    query = base_query.order_by(desc(Generation.created_at))
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    generations = result.scalars().all()

    return ResponseModel(data={
        "items": [
            {
                "id": g.id,
                "module": g.module,
                "status": g.status,
                "title": g.title,
                "input_params": g.input_params,
                "output_content": g.output_content,
                "provider": g.provider,
                "model_name": g.model_name,
                "token_count": g.token_count,
                "duration_ms": g.duration_ms,
                "created_at": g.created_at.isoformat() if g.created_at else None
            }
            for g in generations
        ],
        "total": total
    })


@router.get("/history/{generation_id}")
async def get_generation_detail(
    generation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取生成记录详情
    """
    from sqlalchemy import select

    result = await db.execute(
        select(Generation).where(
            Generation.id == generation_id,
            Generation.user_id == current_user.id
        )
    )
    generation = result.scalar_one_or_none()

    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="生成记录不存在"
        )

    return {
        "id": generation.id,
        "module": generation.module,
        "status": generation.status,
        "title": generation.title,
        "input_params": generation.input_params,
        "output_content": generation.output_content,
        "provider": generation.provider,
        "model_name": generation.model_name,
        "token_count": generation.token_count,
        "duration_ms": generation.duration_ms,
        "created_at": generation.created_at.isoformat() if generation.created_at else None
    }


@router.delete("/history/{generation_id}")
async def delete_generation(
    generation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除生成记录
    """
    from sqlalchemy import select, delete

    result = await db.execute(
        select(Generation).where(
            Generation.id == generation_id,
            Generation.user_id == current_user.id
        )
    )
    generation = result.scalar_one_or_none()

    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="生成记录不存在"
        )

    await db.execute(
        delete(Generation).where(Generation.id == generation_id)
    )
    await db.commit()

    logger.info(f"用户 {current_user.id} 删除了生成记录 {generation_id}")

    return ResponseModel(success=True, message="删除成功")

# ==================== 用户行为追踪 ====================


@router.post("/action", response_model=UserActionResponse)
async def track_user_action(
    data: UserActionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    记录用户行为（复制、下载、重新生成等）
    """
    action = UserAction(
        user_id=current_user.id,
        generation_id=data.generation_id,
        module=data.module,
        action=data.action,
        content_snippet=data.content_snippet
    )

    db.add(action)
    await db.commit()
    await db.refresh(action)

    return UserActionResponse(
        id=action.id,
        user_id=action.user_id,
        generation_id=action.generation_id,
        module=action.module,
        action=action.action,
        content_snippet=action.content_snippet,
        created_at=action.created_at.isoformat() if action.created_at else None
    )


@router.get("/action/stats")
async def get_action_stats(
    module: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户行为统计
    """
    from sqlalchemy import select, func

    query = select(UserAction).where(UserAction.user_id == current_user.id)

    if module:
        query = query.where(UserAction.module == module)

    result = await db.execute(query)
    actions = result.scalars().all()

    # 统计各类行为
    copy_count = sum(1 for a in actions if a.action == "copy")
    download_count = sum(1 for a in actions if a.action == "download")
    regenerate_count = sum(1 for a in actions if a.action == "regenerate")
    total = len(actions)

    # 获取总生成数
    gen_query = select(func.count(Generation.id)).where(
        Generation.user_id == current_user.id
    )
    if module:
        gen_query = gen_query.where(Generation.module == module)

    gen_result = await db.execute(gen_query)
    total_generations = gen_result.scalar() or 1  # 避免除以0

    return ActionStatsResponse(
        total_actions=total,
        copy_count=copy_count,
        download_count=download_count,
        regenerate_count=regenerate_count,
        copy_rate=round(copy_count / total_generations, 2),
        download_rate=round(download_count / total_generations, 2)
    )


# ==================== 提示词优化 ====================

@router.post("/optimize")
async def optimize_prompt(
    data: OptimizeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    提示词优化

    将用户笼统的创意描述优化为结构化的提示词，帮助AI更好地理解用户意图。

    支持的模块：
    - short_video: 短视频脚本
    - script: 剧本大纲
    - novel: 小说大纲
    - print_ad: 平面广告
    - tvc: TVC广告
    - original_ip: 原创IP计划
    """
    from app.agents.prompt_optimizer import get_prompt_optimizer

    try:
        optimizer = get_prompt_optimizer()
        result = await optimizer.optimize(
            db=db,
            user_id=current_user.id,
            module=data.module,
            original_text=data.original_text
        )

        logger.info(
            f"用户 {current_user.id} 优化提示词成功 - "
            f"模块: {data.module}, "
            f"原文长度: {result['original_length']}, "
            f"优化后长度: {result['optimized_length']}"
        )

        return ResponseModel(
            success=True,
            data=result
        )

    except ValueError as e:
        logger.warning(f"优化参数错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"优化失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"优化失败: {str(e)}"
        )


@router.get("/optimize/modules")
async def get_optimize_modules():
    """
    获取支持的优化模块列表
    """
    from app.agents.prompt_optimizer import get_prompt_optimizer

    optimizer = get_prompt_optimizer()
    modules = optimizer.get_supported_modules()

    return ResponseModel(
        success=True,
        data={
            "modules": [
                {"id": k, "name": v}
                for k, v in modules.items()
            ]
        }
    )


# ==================== 两阶段大纲生成 API ====================


class GlobalOutlineRequest(BaseModel):
    """全局大纲生成请求"""
    content_type: str  # novel/script
    input_params: Dict[str, Any]
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    enable_knowledge: bool = True  # 是否启用知识库修正


class UnitSummariesRequest(BaseModel):
    """单元概述生成请求"""
    content_type: str  # novel/script
    global_outline: str
    unit_count: int
    series_type: Optional[str] = None  # 剧本类型专用
    episode_duration_range: Optional[str] = None  # 剧本类型专用
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    enable_logic_check: bool = True  # 是否启用逻辑修正


class LogicCheckRequest(BaseModel):
    """逻辑检测请求"""
    content_type: str  # novel/script
    global_outline: str
    unit_summaries: Dict[str, Any]  # 单元概述字典
    provider: Optional[str] = None
    temperature: float = 0.7


@router.post("/outline/global")
async def generate_global_outline(
    data: GlobalOutlineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成全局大纲（第一阶段）

    生成详细的全局大纲，包含世界观、人物谱系、故事结构等完整维度。
    这是两阶段生成流程的第一阶段。
    支持知识库修正，修正后的内容直接替换原始内容。
    """
    try:
        generator = get_outline_generator(db)
        result = await generator.generate_global_outline(
            content_type=data.content_type,
            input_params=data.input_params,
            provider=data.provider,
            model=data.model,
            temperature=data.temperature,
            user_id=current_user.id,
            enable_knowledge=data.enable_knowledge
        )

        if result["success"]:
            logger.info(
                f"用户 {current_user.id} 生成全局大纲成功 - "
                f"类型: {data.content_type}, "
                f"耗时: {result['duration_ms']}ms"
            )
            return ResponseModel(
                success=True,
                data=result
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "生成失败")
            )

    except ValueError as e:
        logger.warning(f"全局大纲参数错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"全局大纲生成失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成失败: {str(e)}"
        )


@router.post("/outline/global/stream")
async def generate_global_outline_stream(
    data: GlobalOutlineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    流式生成全局大纲（第一阶段）
    """
    async def generate():
        generator = get_outline_generator(db)
        async for chunk in generator.generate_global_outline_stream(
            content_type=data.content_type,
            input_params=data.input_params,
            provider=data.provider,
            model=data.model,
            temperature=data.temperature,
            user_id=current_user.id
        ):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


@router.post("/outline/units")
async def generate_unit_summaries(
    data: UnitSummariesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成单元简要概述（第二阶段）

    基于全局大纲生成各单元的简要概述（章节概要/分集概要/分场概要）。
    这是两阶段生成流程的第二阶段。
    支持逻辑性修正，自动检测和修正设定冲突、剧情衔接、人物成长等问题。
    """
    try:
        generator = get_outline_generator(db)
        result = await generator.generate_unit_summaries(
            global_outline=data.global_outline,
            unit_count=data.unit_count,
            content_type=data.content_type,
            series_type=data.series_type,
            episode_duration_range=data.episode_duration_range,
            provider=data.provider,
            model=data.model,
            temperature=data.temperature,
            user_id=current_user.id,
            enable_logic_check=data.enable_logic_check
        )

        if result["success"]:
            logger.info(
                f"用户 {current_user.id} 生成单元概述成功 - "
                f"类型: {data.content_type}, "
                f"单元数: {data.unit_count}, "
                f"耗时: {result['duration_ms']}ms"
            )
            return ResponseModel(
                success=True,
                data=result
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "生成失败")
            )

    except ValueError as e:
        logger.warning(f"单元概述参数错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"单元概述生成失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成失败: {str(e)}"
        )


@router.post("/outline/units/stream")
async def generate_unit_summaries_stream(
    data: UnitSummariesRequest,
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    流式生成单元简要概述（第二阶段）

    支持中断机制：通过 session_id 可以调用 /cancel/{session_id} 取消生成
    """
    # 创建取消令牌
    cancel_event = asyncio.Event()
    if session_id:
        cancel_tokens[session_id] = cancel_event

    async def generate():
        try:
            generator = get_outline_generator(db)
            async for chunk in generator.generate_unit_summaries_stream(
                global_outline=data.global_outline,
                unit_count=data.unit_count,
                content_type=data.content_type,
                series_type=data.series_type,
                episode_duration_range=data.episode_duration_range,
                provider=data.provider,
                model=data.model,
                temperature=data.temperature,
                user_id=current_user.id,
                cancel_event=cancel_event
            ):
                # 检查是否被取消
                if cancel_event.is_set():
                    logger.info(f"单元概述生成被取消: {session_id}")
                    break
                yield chunk
        finally:
            # 清理取消令牌
            if session_id and session_id in cancel_tokens:
                del cancel_tokens[session_id]

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@router.post("/outline/download")
async def download_outline(
    content: str = "",
    filename: str = "outline.md",
    current_user: User = Depends(get_current_user)
):
    """
    下载大纲文件

    Args:
        content: 大纲内容
        filename: 文件名

    Returns:
        文件下载响应
    """
    from fastapi.responses import Response

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="大纲内容不能为空"
        )

    # 确保文件名以 .md 结尾
    if not filename.endswith('.md'):
        filename += '.md'

    return Response(
        content=content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        }
    )


@router.post("/outline/logic-check")
async def check_outline_logic(
    data: LogicCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    独立的逻辑检测API

    检测单元概述中的逻辑问题，包括：
    - 设定冲突：人物设定、世界观设定与单元概述内容的矛盾
    - 剧情衔接跳脱：单元概述之间的情节连贯性问题
    - 人物成长过快：人物性格变化、能力提升的合理性
    - 时间线矛盾：事件发生顺序的逻辑性
    - 核心线索断裂：重要情节线索的连续性

    返回检测结果和修正后的单元概述内容。
    """
    try:
        generator = get_outline_generator(db)
        result = await generator.check_and_fix_logic_issues(
            global_outline=data.global_outline,
            unit_summaries=data.unit_summaries,
            content_type=data.content_type,
            provider=data.provider,
            temperature=data.temperature,
            user_id=current_user.id
        )

        logger.info(
            f"用户 {current_user.id} 逻辑检测完成 - "
            f"类型: {data.content_type}, "
            f"检测到问题: {result.get('has_issues', False)}"
        )

        return ResponseModel(
            success=True,
            data=result
        )

    except ValueError as e:
        logger.warning(f"逻辑检测参数错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"逻辑检测失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检测失败: {str(e)}"
        )


# ==================== 原创IP计划生成 ====================

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
        module="original_ip",
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
            generation = Generation(
                user_id=current_user.id,
                module=GenerationModule.ORIGINAL_IP,
                status=GenerationStatus.COMPLETED,
                input_params=data.model_dump(),
                output_content=result.get("content"),
                provider=result.get("provider"),
                model_name=result.get("model"),
                token_count=result.get("usage", {}).get("total_tokens", 0),
                duration_ms=result.get("duration_ms", 0)
            )
            db.add(generation)
            await db.commit()
            await db.refresh(generation)
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "生成失败")
        )


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
                module="original_ip",
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
                    generation = Generation(
                        user_id=current_user.id,
                        module=GenerationModule.ORIGINAL_IP,
                        status=GenerationStatus.COMPLETED,
                        input_params=data.model_dump(),
                        output_content=full_content,
                        provider=provider
                    )
                    db.add(generation)
                    await db.commit()
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
