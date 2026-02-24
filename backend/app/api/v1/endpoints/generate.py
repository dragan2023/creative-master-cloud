"""
创意生成 API 端点
提供短视频脚本、剧本大纲、小说大纲、平面广告、TVC广告脚本的生成功能
支持流式和非流式生成
支持多模态文件上传
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
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
    GenerationHistoryResponse
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


@router.post("/short-video/stream")
async def generate_short_video_stream(
    data: ShortVideoInput,
    session_id: Optional[str] = None,
    enable_search: bool = False,
    enable_knowledge: bool = False,
    provider: Optional[str] = None,
    temperature: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成短视频脚本（流式）
    """
    logger.info(
        f"短视频流式生成请求: enable_knowledge={enable_knowledge}, session_id={session_id}")

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
                module="short_video",
                user_id=current_user.id,
                input_params=input_params,
                session_id=session_id,
                enable_search=enable_search,
                enable_knowledge=enable_knowledge,
                reference_urls=input_params.get("reference_urls"),
                provider=provider,
                temperature=temperature,
                cancel_event=cancel_event
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
        media_type="text/event-stream"
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
    provider: Optional[str] = None,
    temperature: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成剧本大纲（流式）
    """
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
                enable_knowledge=enable_knowledge,
                reference_urls=input_params.get("reference_urls"),
                provider=provider,
                temperature=temperature,
                cancel_event=cancel_event
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
        media_type="text/event-stream"
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
    provider: Optional[str] = None,
    temperature: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成小说大纲（流式）
    """
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
                enable_knowledge=enable_knowledge,
                reference_urls=input_params.get("reference_urls"),
                provider=provider,
                temperature=temperature,
                cancel_event=cancel_event
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
        media_type="text/event-stream"
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
    provider: Optional[str] = None,
    temperature: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成平面广告文案（流式）
    """
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
                enable_knowledge=enable_knowledge,
                reference_urls=input_params.get("reference_urls"),
                provider=provider,
                temperature=temperature,
                images=input_params.get("images"),
                cancel_event=cancel_event
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
        media_type="text/event-stream"
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


@router.post("/tvc/stream")
async def generate_tvc_stream(
    data: TVCInput,
    session_id: Optional[str] = None,
    enable_search: bool = False,
    enable_knowledge: bool = False,
    provider: Optional[str] = None,
    temperature: float = 0.7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成TVC广告脚本（流式）
    """
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
                module="tvc",
                user_id=current_user.id,
                input_params=input_params,
                session_id=session_id,
                enable_search=enable_search,
                enable_knowledge=enable_knowledge,
                reference_urls=input_params.get("reference_urls"),
                provider=provider,
                temperature=temperature,
                images=input_params.get("images"),
                cancel_event=cancel_event
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
        media_type="text/event-stream"
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
