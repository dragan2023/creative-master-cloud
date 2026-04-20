"""
创意生成 API 端点
提供短视频脚本、剧本大纲、小说大纲、平面广告、TVC广告脚本的生成功能
支持流式和非流式生成
支持多模态文件上传

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any
from pydantic import BaseModel
from app.services.outline_generator import get_outline_generator
from typing import Optional, List
from fastapi import APIRouter, Depends, status, File, UploadFile, Query
from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    AuthorizationException,
    GenerationException,
)
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
    OriginalIPInput, RevisionRequest, FinalizeRequest, UnitSummariesQCRequest
)
from app.schemas.common import ResponseModel
from app.models import User, Generation, GenerationModule, GenerationStatus, UserAction
from app.services.generation_service import GenerationService
from app.services.user_action_service import UserActionService
from app.agents.orchestrator import get_agent_orchestrator
from app.core.logger import get_logger
from app.core.config import get_settings
from app.core.redis_client import redis_manager
from app.core.module_registry import (
    get_module_config, MODULE_REGISTRY,
    MODULE_SHORT_VIDEO, MODULE_SCRIPT, MODULE_NOVEL,
    MODULE_PRINT_AD, MODULE_TVC, MODULE_ORIGINAL_IP
)
import json
import asyncio

# 取消令牌的 Redis 键前缀
CANCEL_KEY_PREFIX = "generate:cancel:"
# 取消令牌过期时间（秒）
CANCEL_EXPIRE_SECONDS = 3600  # 1小时
# 内存取消令牌存储（用于流式生成的取消控制）
# TODO: 考虑完全迁移到Redis后移除内存级取消令牌
cancel_tokens: Dict[str, asyncio.Event] = {}

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


@router.get("/latest/{module}")
async def get_latest_generation(
    module: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户最近的生成记录(通用API,适用于所有模块)

    用于在前端页面加载时恢复上次的生成状态。
    """
    from app.utils.generation_state_manager import GenerationStateManager

    try:
        state = await GenerationStateManager.get_latest_generation(
            db, current_user.id, module, days=7
        )

        return ResponseModel(success=True, data=state)

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"获取最近生成记录失败: {str(e)}")
        raise GenerationException(f"获取失败: {str(e)}")


@router.get("/{generation_id}/restore")
async def restore_generation(
    generation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    恢复指定的生成记录

    返回完整的生成状态,包括修订历史等。
    """
    from app.models.generation import Generation
    from sqlalchemy import select

    try:
        stmt = select(Generation).where(
            Generation.id == generation_id,
            Generation.user_id == current_user.id
        )

        result = await db.execute(stmt)
        generation = result.scalar_one_or_none()

        if not generation:
            raise ValidationException("生成记录不存在")

        return ResponseModel(
            success=True,
            data={
                "id": generation.id,
                "title": generation.title,
                "module": generation.module.value,
                "status": generation.status.value,
                "outline_stage": generation.outline_stage,
                "global_outline_content": generation.global_outline_content,
                "unit_summaries_content": generation.unit_summaries_content,
                "revision_messages": generation.revision_messages,
                "revision_count": generation.revision_count,
                "is_finalized": generation.is_finalized,
                "output_content": generation.output_content,
                "created_at": generation.created_at.isoformat(),
                "updated_at": generation.updated_at.isoformat(),
                "input_params": generation.input_params
            }
        )

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"恢复生成记录失败: {str(e)}")
        raise GenerationException(f"恢复失败: {str(e)}")


@router.post("/cancel/{session_id}")
async def cancel_generation(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    取消生成任务
    使用 Redis 存储取消状态，支持多 worker 环境
    同时设置内存中的 Event 实现立即中断
    """
    cancel_key = f"{CANCEL_KEY_PREFIX}{session_id}"

    try:
        # 1. 设置 Redis 取消标记（支持多 worker 环境）
        await redis_manager.set(cancel_key, "1", expire=CANCEL_EXPIRE_SECONDS)

        # 2. 设置内存中的 Event（实现立即中断）
        if session_id in cancel_tokens:
            cancel_tokens[session_id].set()
            logger.info(f"已设置内存取消事件: {session_id}")

        logger.info(
            f"用户 {current_user.id} 请求取消生成任务: {session_id}, Redis key: {cancel_key}")
        return ResponseModel(success=True, message="取消请求已发送")
    except Exception as e:
        logger.error(f"设置取消标记失败: {e}")
        return ResponseModel(success=False, message=f"取消请求失败: {str(e)}")

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


async def is_cancelled(session_id: str) -> bool:
    """
    检查生成任务是否被取消
    使用 Redis 存储取消状态，支持多 worker 环境

    Args:
        session_id: 会话ID

    Returns:
        是否被取消
    """
    if not session_id:
        return False
    cancel_key = f"{CANCEL_KEY_PREFIX}{session_id}"
    try:
        result = await redis_manager.exists(cancel_key)
        if result:
            logger.info(f"检测到取消请求: session_id={session_id}")
        return result
    except Exception as e:
        logger.error(f"检查取消状态失败: {e}")
        return False


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

    logger.info(
        f"[上传] 开始处理文件上传: filename={file.filename}, content_type={file.content_type}")

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
        # 尝试通过文件扩展名判断（优先于 MIME 类型）
        original_ext = os.path.splitext(file.filename)[
            1].lower() if file.filename else ""
        if original_ext in ALLOWED_DOC_EXTENSIONS:
            file_ext = original_ext
            file_type = 'document'
            max_size = settings.MAX_DOC_SIZE
        elif content_type == "application/octet-stream":
            # 对于 application/octet-stream，尝试通过扩展名判断
            original_ext = os.path.splitext(file.filename)[
                1].lower() if file.filename else ""
            if original_ext in ALLOWED_DOC_EXTENSIONS:
                file_ext = original_ext
                file_type = 'document'
                max_size = settings.MAX_DOC_SIZE
            elif original_ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
                # 检查是否是图片扩展名
                for mime_type, ext in ALLOWED_IMAGE_TYPES.items():
                    if ext == original_ext or (original_ext == ".jpeg" and ext == ".jpg"):
                        file_ext = ext
                        file_type = 'image'
                        max_size = settings.MAX_IMAGE_SIZE
                        break
            else:
                logger.warning(
                    f"[上传] 不支持的文件类型: {content_type}, 扩展名: {original_ext}")
                raise ValidationException(
                    f"不支持的文件类型: {original_ext}。支持图片(png/jpg/gif/webp)或文档(txt/md/doc/docx/pdf)，最大{int(settings.MAX_DOC_SIZE / 1024 / 1024)}MB"
                )
        else:
            logger.warning(f"[上传] 不支持的文件类型: {content_type or original_ext}")
            raise ValidationException(
                f"不支持的文件类型: {content_type or original_ext}。支持图片(png/jpg/gif/webp)或文档(txt/md/doc/docx/pdf)，最大{int(settings.MAX_DOC_SIZE / 1024 / 1024)}MB"
            )

    # 检查文件大小
    content = await file.read()
    if len(content) > max_size:
        size_mb = max_size / 1024 / 1024
        raise ValidationException(
            f"文件大小超过限制（{file_type == 'image' and '图片' or '文档'}最大{int(size_mb)}MB）"
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

    logger.info(
        f"[上传] 文件上传成功: filename={file.filename}, saved_as={file_name}, size={len(content)} bytes, url={file_url}")

    return ResponseModel(data={
        "url": file_url,
        "file_name": file_name,
        "content_type": content_type,
        "size": len(content),
        "file_type": file_type
    })


@router.post("/upload-outline-import")
async def upload_outline_for_import(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    上传大纲文件用于导入（解析文件内容并返回）

    支持格式：.txt, .md, .docx, .doc

    Args:
        file: 上传的大纲文件

    Returns:
        文件内容文本
    """
    from app.core.config import get_settings
    from app.tools.file_parser import parse_document_file

    settings = get_settings()

    logger.info(
        f"[导入大纲上传] 开始处理文件上传: filename={file.filename}, content_type={file.content_type}")

    # 验证文件类型
    allowed_extensions = ['.txt', '.md', '.docx', '.doc']
    original_ext = os.path.splitext(file.filename)[
        1].lower() if file.filename else ""

    if original_ext not in allowed_extensions:
        logger.warning(f"[导入大纲上传] 不支持的文件类型: {original_ext}")
        raise ValidationException(
            f"不支持的文件类型: {original_ext}。支持 .txt, .md, .docx, .doc 格式"
        )

    # 检查文件大小（使用配置的最大文档大小）
    content = await file.read()
    max_size = settings.MAX_DOC_SIZE
    if len(content) > max_size:
        raise ValidationException(
            f"文件大小超过限制（最大{int(max_size / 1024 / 1024)}MB）")

    try:
        # 解析文件内容
        text_content = await parse_document_file(file.filename, content)

        if not text_content or not text_content.strip():
            raise ValidationException("文件内容为空")

        logger.info(
            f"[导入大纲上传] 文件上传并解析成功: filename={file.filename}, content_length={len(text_content)}")

        return ResponseModel(data={
            "content": text_content,
            "file_name": file.filename,
            "file_type": original_ext,
            "size": len(content)
        })

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"[导入大纲上传] 文件解析失败: {str(e)}")
        raise ValidationException(f"文件解析失败: {str(e)}")


@router.post("/upload-unit-summaries-import")
async def upload_unit_summaries_for_import(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    上传单元概述文件用于导入

    支持格式：.txt, .md, .docx, .doc

    Args:
        file: 上传的单元概述文件

    Returns:
        文件内容文本
    """
    from app.core.config import get_settings
    from app.tools.file_parser import parse_document_file

    settings = get_settings()

    logger.info(
        f"[导入单元概述上传] 开始处理文件上传: filename={file.filename}, content_type={file.content_type}")

    # 验证文件类型
    allowed_extensions = ['.txt', '.md', '.docx', '.doc']
    original_ext = os.path.splitext(file.filename)[
        1].lower() if file.filename else ""

    if original_ext not in allowed_extensions:
        logger.warning(f"[导入单元概述上传] 不支持的文件类型: {original_ext}")
        raise ValidationException(
            f"不支持的文件类型: {original_ext}。支持 .txt, .md, .docx, .doc 格式"
        )

    # 检查文件大小（使用配置的最大文档大小）
    content = await file.read()
    max_size = settings.MAX_DOC_SIZE
    if len(content) > max_size:
        raise ValidationException(
            f"文件大小超过限制（最大{int(max_size / 1024 / 1024)}MB）")

    try:
        # 解析文件内容
        text_content = await parse_document_file(file.filename, content)

        if not text_content or not text_content.strip():
            raise ValidationException("文件内容为空")

        logger.info(
            f"[导入单元概述上传] 文件上传并解析成功: filename={file.filename}, content_length={len(text_content)}")

        return ResponseModel(data={
            "content": text_content,
            "file_name": file.filename,
            "file_type": original_ext,
            "size": len(content)
        })

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"[导入单元概述上传] 文件解析失败: {str(e)}")
        raise ValidationException(f"文件解析失败: {str(e)}")


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
        raise ValidationException("最多同时上传5个文件")

    results = []
    for file in files:
        try:
            result = await upload_file(file, current_user)
            results.append(result.data)
        except ValidationException as e:
            results.append({
                "error": e.message,
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
        raise ResourceNotFoundException("文件不存在")

    # 安全检查：防止目录遍历攻击
    if not os.path.abspath(file_path).startswith(os.path.abspath(upload_dir)):
        raise AuthorizationException(message="访问被拒绝")

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


# ==================== 流式生成端点工厂 ====================

async def _create_streaming_endpoint(
    module: str,
    input_params: dict,
    user_id: int,
    db: AsyncSession,
    session_id: Optional[str] = None,
    enable_search: bool = False,
    enable_knowledge: bool = False,
    enable_mcp: bool = False,
    enable_trending: bool = False,
    provider: Optional[str] = None,
    temperature: float = 0.7,
    search_keywords: Optional[List[str]] = None,
    kb_vertical: bool = False,
    kb_user_specific: bool = False,
    kb_manual: bool = False,
    kb_vertical_ids: Optional[List[int]] = None,
    kb_user_specific_ids: Optional[List[int]] = None,
    kb_manual_ids: Optional[List[int]] = None,
    **kwargs
) -> StreamingResponse:
    """
    通用流式生成端点工厂 - 消除8个端点的重复代码

    已集成状态持久化: 自动保存生成状态到数据库

    Args:
        module: 模块名称 (short_video, script, novel, print_ad, tvc, original_ip)
        input_params: 输入参数字典
        user_id: 用户ID
        db: 数据库会话
        session_id: 会话ID
        enable_search: 是否启用搜索
        enable_knowledge: 是否启用知识库
        enable_mcp: 是否启用MCP
        enable_trending: 是否启用趋势
        provider: 模型提供者
        temperature: 温度参数
        search_keywords: 搜索关键词列表
        kb_vertical: 是否启用垂直知识库
        kb_user_specific: 是否启用用户专属知识库
        kb_manual: 是否启用手动知识库
        kb_vertical_ids: 垂直知识库ID列表
        kb_user_specific_ids: 用户专属知识库ID列表
        kb_manual_ids: 手动知识库ID列表
        **kwargs: 额外参数（videos, images等）

    Returns:
        StreamingResponse: 流式响应
    """
    from app.models.generation import Generation, GenerationModule, GenerationStatus
    from app.utils.generation_state_manager import GenerationStateManager

    # 映射模块名称到枚举
    module_map = {
        'short_video': GenerationModule.SHORT_VIDEO,
        'script': GenerationModule.SCRIPT,
        'novel': GenerationModule.NOVEL,
        'print_ad': GenerationModule.PRINT_AD,
        'tvc': GenerationModule.TVC,
        'original_ip': GenerationModule.ORIGINAL_IP
    }

    module_enum = module_map.get(module, GenerationModule.SHORT_VIDEO)

    # 创建Generation记录
    generation = Generation(
        user_id=user_id,
        module=module_enum,
        status=GenerationStatus.PROCESSING,
        input_params=input_params,
        title=input_params.get('title', input_params.get(
            'ip_description', '未命名生成'))[:100],
        current_stage='generating'
    )
    db.add(generation)
    await db.commit()
    await db.refresh(generation)

    state_manager = GenerationStateManager(db, generation.id)

    orchestrator = get_agent_orchestrator()

    # 创建内存取消事件（实现立即中断）
    cancel_event = asyncio.Event()
    if session_id:
        cancel_tokens[session_id] = cancel_event

    # 用于收集完整内容
    content_buffer = []
    has_error = False  # 标记是否有异常发生

    async def event_generator():
        try:
            # 保存“生成中”状态
            await state_manager.save_stage(
                stage='generating',
                stage_data={'progress': 0},
                status=GenerationStatus.PROCESSING
            )

            async for chunk in orchestrator.generate_stream(
                db=db,
                module=module,
                user_id=user_id,
                input_params=input_params,
                session_id=session_id,
                enable_search=enable_search,
                search_keywords=search_keywords,
                enable_knowledge=enable_knowledge,
                enable_mcp=enable_mcp or enable_trending,
                reference_urls=input_params.get("reference_urls"),
                provider=provider,
                temperature=temperature,
                cancel_event=cancel_event,  # 传入内存事件
                kb_vertical=kb_vertical,
                kb_user_specific=kb_user_specific,
                kb_manual=kb_manual,
                kb_vertical_ids=kb_vertical_ids,
                kb_user_specific_ids=kb_user_specific_ids,
                kb_manual_ids=kb_manual_ids,
                **kwargs
            ):
                # 优先检查内存事件（立即中断）
                if cancel_event.is_set():
                    logger.info(f"生成任务被立即取消: {session_id}")
                    # 保存“已取消”状态
                    try:
                        await state_manager.save_stage(
                            stage='generating',
                            stage_data={
                                'partial_content': ''.join(content_buffer),
                                'cancelled': True
                            },
                            status=GenerationStatus.CANCELLED
                        )
                    except Exception as e:
                        logger.error(f"保存取消状态失败: {e}")
                    break
                # 同时检查 Redis（多 worker 兼容）
                if await is_cancelled(session_id):
                    logger.info(f"生成任务被取消(Redis): {session_id}")
                    # 保存“已取消”状态
                    try:
                        await state_manager.save_stage(
                            stage='generating',
                            stage_data={
                                'partial_content': ''.join(content_buffer),
                                'cancelled': True
                            },
                            status=GenerationStatus.CANCELLED
                        )
                    except Exception as e:
                        logger.error(f"保存取消状态失败: {e}")
                    break

                yield chunk

                # 累积内容
                try:
                    if chunk.startswith('event: content\ndata: '):
                        import json
                        json_str = chunk.split('data: ', 2)[1].strip()
                        if json_str:
                            content_data = json.loads(json_str)
                            text = content_data.get('text', '')
                            content_buffer.append(text)

                            # 定期保存进度和内容(每500字符保存一次)
                            total_length = sum(len(t) for t in content_buffer)
                            if total_length > 0 and total_length % 500 < len(text):
                                try:
                                    await state_manager.save_stage(
                                        stage='generating',
                                        stage_data={
                                            # 假设5000字符完成
                                            'progress': min(total_length / 5000, 1.0),
                                            'partial_content': ''.join(content_buffer)
                                        },
                                        status=GenerationStatus.PROCESSING
                                    )
                                except Exception as save_err:
                                    # 保存失败不影响生成
                                    pass
                except Exception as parse_err:
                    logger.debug(f"解析chunk失败: {parse_err}")

        except asyncio.CancelledError:
            logger.info(f"生成任务被取消: {session_id}")
            has_error = True  # 标记有异常
            raise
        except Exception as e:
            logger.error(f"生成任务失败: {e}")
            has_error = True  # 标记有异常
            # 保存“失败”状态
            try:
                await state_manager.save_stage(
                    stage='generating',
                    stage_data={
                        'partial_content': ''.join(content_buffer),
                        'error': str(e)[:500]
                    },
                    status=GenerationStatus.FAILED
                )
            except Exception as save_error:
                logger.error(f"保存失败状态失败: {save_error}")
        finally:
            # 清理取消令牌
            if session_id and session_id in cancel_tokens:
                del cancel_tokens[session_id]
            # 清理 Redis 标记
            if session_id:
                cancel_key = f"{CANCEL_KEY_PREFIX}{session_id}"
                await redis_manager.delete(cancel_key)

            # 如果内容完整且没有异常，保存“完成”状态
            if content_buffer and not has_error:
                try:
                    await state_manager.save_stage(
                        stage='completed',
                        stage_data={
                            'content': ''.join(content_buffer),
                            'progress': 1.0
                        },
                        status=GenerationStatus.COMPLETED
                    )
                except Exception as e:
                    logger.error(f"保存完成状态失败: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


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

    # 详细日志：记录所有关键参数
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
        module=MODULE_SCRIPT,
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
    """生成剧本大纲（流式）"""
    input_params = data.model_dump()
    logger.info(
        f"剧本流式生成请求: enable_knowledge={enable_knowledge}, enable_search={enable_search}, "
        f"enable_trending={enable_trending}, kb_vertical={kb_vertical}, session_id={session_id}"
    )
    return await _create_streaming_endpoint(
        module=MODULE_SCRIPT,
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
    """
    生成小说大纲（非流式）
    """
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
    """
    生成平面广告文案（非流式）
    """
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
        raise ResourceNotFoundException("生成记录不存在")

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
        raise ResourceNotFoundException("生成记录不存在")

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
    action_service = UserActionService(db)
    action = await action_service.track_action(
        user_id=current_user.id,
        generation_id=data.generation_id,
        module=data.module,
        action=data.action,
        content_snippet=data.content_snippet
    )

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
        raise ValidationException(str(e))
    except Exception as e:
        logger.error(f"优化失败: {str(e)}")
        raise GenerationException(f"优化失败: {str(e)}")


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
    enable_knowledge: bool = False  # 是否启用知识库修正（默认False，由用户主动控制）
    enable_auto_qc: bool = False  # v2.3新增：是否启用自动质控修正（默认False，由用户主动控制）

    # 文风参数（可选）
    style_ids: Optional[List[str]] = []
    style_names: Optional[List[str]] = []
    style_intensity: Optional[float] = 0.7
    style_guide: Optional[Dict[str, Any]] = None

    # 标题风格参数（可选，新增）
    title_style: Optional[str] = None
    title_style_name: Optional[str] = None


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
    enable_quality_control: bool = True  # 是否启用质量管控

    # 续生成参数（可选）
    existing_content: Optional[str] = None  # 已生成的内容
    existing_parsed: Optional[Dict[str, Any]] = None  # 已解析的单元数据
    start_from_unit: int = 1  # 从第几章开始续生成（默认1表示全新生成）

    # 标题风格参数（可选，新增）
    title_style: Optional[str] = None
    title_style_name: Optional[str] = None


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
            enable_knowledge=data.enable_knowledge,
            # 文风参数
            style_ids=data.style_ids or [],
            style_names=data.style_names or [],
            style_intensity=data.style_intensity or 0.7,
            style_guide=data.style_guide
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
            raise GenerationException(result.get("error", "生成失败"))

    except ValueError as e:
        logger.warning(f"全局大纲参数错误: {str(e)}")
        raise ValidationException(str(e))
    except Exception as e:
        logger.error(f"全局大纲生成失败: {str(e)}")
        raise GenerationException(f"生成失败: {str(e)}")


@router.post("/outline/global/revise")
async def revise_global_outline_with_knowledge(
    data: GlobalOutlineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    对全局大纲执行知识库修正（用户确认后调用）

    此API在全局大纲生成完成后，由用户审核确认后再执行知识库修正。
    这样可以确保知识库修正是基于用户最终确认的大纲内容进行的。
    已集成状态持久化：自动保存修正后的大纲内容
    """
    from app.models.generation import Generation, GenerationModule, GenerationStatus
    from app.utils.generation_state_manager import GenerationStateManager

    try:
        # 1. 查找最近的generation记录
        module_enum = GenerationModule.NOVEL if data.content_type == 'novel' else GenerationModule.SCRIPT
        state = await GenerationStateManager.get_latest_generation(
            db, current_user.id, module_enum.value, days=7
        )

        state_manager = None
        if state:
            state_manager = GenerationStateManager(db, state['id'])

        generator = get_outline_generator(db)

        # 2. 获取LLM provider
        llm_provider = await generator.llm_manager.get_provider_from_db(
            db, current_user.id, data.provider
        )
        if not llm_provider:
            raise ValueError(f"未找到LLM提供商: {data.provider}")

        # 3. 执行知识库修正
        revised_content = await generator._revise_with_knowledge_base(
            llm_provider=llm_provider,
            original_content=data.input_params.get('existing_outline', ''),
            input_params=data.input_params,
            temperature=data.temperature,
            db=db,
            user_id=current_user.id,
            content_type=data.content_type
        )

        # 4. 更新状态
        if state_manager and revised_content:
            try:
                stage_data = state.get('stage_data', {})
                stage_data['global_outline'] = revised_content

                await state_manager.save_stage(
                    stage='knowledge_revising',
                    stage_data=stage_data,
                    status=GenerationStatus.PROCESSING
                )
            except Exception as save_err:
                logger.error(f"保存知识库修正状态失败: {save_err}")

        if revised_content:
            logger.info(f"用户 {current_user.id} 全局大纲知识库修正完成")
            return ResponseModel(
                success=True,
                data={
                    "revised_content": revised_content,
                    "message": "知识库优化完成"
                }
            )
        else:
            return ResponseModel(
                success=True,
                data={
                    "revised_content": data.input_params.get('existing_outline', ''),
                    "message": "知识库验证通过，无需修正"
                }
            )

    except Exception as e:
        logger.error(f"全局大纲知识库修正失败: {str(e)}")
        raise GenerationException(f"知识库修正失败: {str(e)}")


class GlobalOutlineReviseRequest(BaseModel):
    """全局大纲流式修订请求"""
    content_type: str  # novel/script
    current_content: str  # 当前大纲内容
    user_feedback: str  # 用户修改意见
    revision_history: Optional[List[Dict[str, Any]]] = []  # 修订历史
    input_params: Optional[Dict[str, Any]] = {}
    provider: Optional[str] = None
    temperature: float = 0.7


@router.post("/outline/global/revise-stream")
async def revise_global_outline_stream(
    data: GlobalOutlineReviseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    流式修订全局大纲（多轮对话）

    用户可以对全局大纲进行多轮对话修正，LLM流式输出修订后的内容。
    """
    from app.utils.generation_state_manager import GenerationStateManager

    # 获取最近的generation记录
    state = await GenerationStateManager.get_latest_generation(
        db, current_user.id, data.content_type, days=7
    )

    if not state:
        # 如果没有找到，创建一个新的
        from app.models.generation import Generation, GenerationModule, GenerationStatus
        module_enum = GenerationModule.NOVEL if data.content_type == 'novel' else GenerationModule.SCRIPT
        generation = Generation(
            user_id=current_user.id,
            module=module_enum,
            status=GenerationStatus.PROCESSING,
            input_params=data.input_params,
            title='大纲修订',
            current_stage='revising_global'
        )
        db.add(generation)
        await db.commit()
        await db.refresh(generation)
        state_manager = GenerationStateManager(db, generation.id)
    else:
        state_manager = GenerationStateManager(db, state['id'])

    async def generate():
        try:
            generator = get_outline_generator(db)

            # 保存“修订中”状态
            await state_manager.save_stage(
                stage='revising_global',
                stage_data=state.get('stage_data', {}) if state else {},
                session_context={
                    'revising': True,
                    'current_feedback': data.user_feedback
                }
            )

            # 获取LLM provider
            llm_provider = await generator.llm_manager.get_provider_from_db(
                db, current_user.id, data.provider
            )
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {data.provider}")

            # 构建修订提示词
            history_text = ""
            if data.revision_history:
                history_text = "\n\n## 修订历史\n"
                for rev in data.revision_history[-3:]:  # 只保留最近3轮
                    history_text += f"- 第{rev.get('round', '?')}轮: {rev.get('feedback', '')}\n"

            revise_prompt = f"""您是一位专业的大纲修订助手。

## 当前大纲内容
{data.current_content}

## 用户修改意见
{data.user_feedback}
{history_text}
## 任务
请根据用户的修改意见，对大纲进行修订。

**修订规则**：
1. 保持大纲的整体结构和核心设定
2. 只修改用户提到的部分
3. 确保修改后的内容逻辑自洽
4. 输出完整的修订后大纲内容

请直接输出修订后的大纲内容：
"""

            # 流式生成修订内容
            full_content = []
            async for chunk in llm_provider.generate_stream(prompt=revise_prompt, temperature=data.temperature):
                content = chunk.content if hasattr(chunk, 'content') else chunk
                if isinstance(content, str):
                    full_content.append(content)
                    yield generator._format_sse("content", {"text": content})

            revised_content = ''.join(full_content)

            # 追加修订消息
            await state_manager.append_revision_message({
                'role': 'user',
                'content': data.user_feedback
            })

            # 保存修订后状态
            stage_data = state.get('stage_data', {}) if state else {}
            stage_data['global_outline'] = revised_content

            await state_manager.save_stage(
                stage='global_completed',
                stage_data=stage_data,
                session_context={'revising': False}
            )

            # 发送修订完成事件
            yield generator._format_sse("diff_complete", {
                "summary": f"已根据'{data.user_feedback}'完成修订",
                "content_length": len(revised_content)
            })

        except Exception as e:
            logger.error(f"全局大纲修订失败: {e!r}")
            yield generator._format_sse("error", {"data": str(e)[:200]})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@router.post("/outline/global/stream")
async def generate_global_outline_stream(
    data: GlobalOutlineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    流式生成全局大纲（第一阶段）

    支持知识库修正：生成完成后，自动调用知识库进行内容优化。
    修正后的内容会以分隔线标识，前端可识别并替换显示。
    """
    from app.models.generation import Generation, GenerationModule, GenerationStatus
    from app.utils.generation_state_manager import GenerationStateManager

    # 创建generation记录
    module_enum = GenerationModule.NOVEL if data.content_type == 'novel' else GenerationModule.SCRIPT
    generation = Generation(
        user_id=current_user.id,
        module=module_enum,
        status=GenerationStatus.PROCESSING,
        input_params=data.input_params,
        title=data.input_params.get('title', '未命名大纲'),
        current_stage='global_generating'
    )
    db.add(generation)
    await db.commit()
    await db.refresh(generation)

    state_manager = GenerationStateManager(db, generation.id)

    async def generate():
        generator = get_outline_generator(db)
        full_content = []

        try:
            # 保存“生成中”状态
            await state_manager.save_stage(
                stage='global_generating',
                stage_data={'progress': 0},
                status=GenerationStatus.PROCESSING
            )

            async for chunk in generator.generate_global_outline_stream(
                content_type=data.content_type,
                input_params=data.input_params,
                provider=data.provider,
                model=data.model,
                temperature=data.temperature,
                user_id=current_user.id,
                enable_knowledge=data.enable_knowledge,
                enable_auto_qc=data.enable_auto_qc,  # v2.3新增：传递自动质控参数
                # 文风参数
                style_ids=data.style_ids or [],
                style_names=data.style_names or [],
                style_intensity=data.style_intensity or 0.7,
                style_guide=data.style_guide
            ):
                yield chunk

                # 累积内容
                if chunk.startswith('event: content\ndata: '):
                    try:
                        import json
                        json_str = chunk.split('data: ', 2)[1].strip()
                        if json_str:
                            content_data = json.loads(json_str)
                            full_content.append(content_data.get('text', ''))
                    except:
                        pass

            # 生成完成，保存状态
            complete_content = ''.join(full_content)
            await state_manager.save_stage(
                stage='global_completed',
                stage_data={
                    'global_outline': complete_content,
                    'progress': 1.0
                },
                status=GenerationStatus.COMPLETED
            )

        except Exception as e:
            # 保存错误状态
            try:
                await state_manager.save_stage(
                    stage='global_generating',
                    stage_data={'error': str(e)[:500]},
                    status=GenerationStatus.FAILED
                )
            except:
                pass
            raise

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
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
    支持质量管控系统，自动检测和修正结构、人物、技术性等问题。
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
            enable_quality_control=data.enable_quality_control,
            title_style=data.title_style,
            title_style_name=data.title_style_name
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
            raise GenerationException(result.get("error", "生成失败"))

    except ValueError as e:
        logger.warning(f"单元概述参数错误: {str(e)}")
        raise ValidationException(str(e))
    except Exception as e:
        logger.error(f"单元概述生成失败: {str(e)}")
        raise GenerationException(f"生成失败: {str(e)}")


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
    已集成状态持久化：自动保存生成状态到数据库
    """
    from app.models.generation import Generation, GenerationModule, GenerationStatus
    from app.utils.generation_state_manager import GenerationStateManager

    # 1. 查找最近的generation记录
    module_enum = GenerationModule.NOVEL if data.content_type == 'novel' else GenerationModule.SCRIPT
    state = await GenerationStateManager.get_latest_generation(
        db, current_user.id, module_enum.value, days=7
    )

    if not state:
        # 创建新记录
        generation = Generation(
            user_id=current_user.id,
            module=module_enum,
            status=GenerationStatus.PROCESSING,
            input_params={'content_type': data.content_type},
            title='单元概述生成',
            current_stage='units_generating'
        )
        db.add(generation)
        await db.commit()
        await db.refresh(generation)
        state_manager = GenerationStateManager(db, generation.id)
    else:
        state_manager = GenerationStateManager(db, state['id'])

    # 2. 保存"单元概述生成中"状态
    await state_manager.save_stage(
        stage='units_generating',
        stage_data={
            'global_outline': data.global_outline,  # 保留全局大纲
            'progress': 0
        },
        status=GenerationStatus.PROCESSING
    )

    # 3. 创建取消令牌
    cancel_event = asyncio.Event()
    if session_id:
        cancel_tokens[session_id] = cancel_event

    content_buffer = []

    async def generate():
        try:
            generator = get_outline_generator(db)

            logger.info(
                f"[单元概述] 开始生成: 从第{data.start_from_unit}章开始, 共{data.unit_count}章"
            )

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
                enable_quality_control=data.enable_quality_control,
                cancel_event=cancel_event,
                # 续生成参数
                existing_content=data.existing_content or "",
                existing_parsed=data.existing_parsed,
                start_from_unit=data.start_from_unit,
                # 标题风格参数
                title_style=data.title_style,
                title_style_name=data.title_style_name
            ):
                # 检查是否被取消
                if cancel_event.is_set():
                    logger.info(f"单元概述生成被取消: {session_id}")
                    # 保存取消状态
                    try:
                        await state_manager.save_stage(
                            stage='units_generating',
                            stage_data={
                                'global_outline': data.global_outline,
                                'partial_unit_summaries': ''.join(content_buffer),
                                'cancelled': True
                            },
                            status=GenerationStatus.CANCELLED
                        )
                    except Exception as save_err:
                        logger.error(f"保存取消状态失败: {save_err}")
                    break

                yield chunk

                # 累积内容
                try:
                    if chunk.startswith('event: content\ndata: '):
                        import json
                        json_str = chunk.split('data: ', 2)[1].strip()
                        if json_str:
                            content_data = json.loads(json_str)
                            content_buffer.append(content_data.get('text', ''))
                except Exception as parse_err:
                    logger.debug(f"解析chunk失败: {parse_err}")

            # 生成完成,保存状态
            if content_buffer:
                try:
                    await state_manager.save_stage(
                        stage='units_completed',
                        stage_data={
                            'global_outline': data.global_outline,
                            'unit_summaries': ''.join(content_buffer),
                            'progress': 1.0
                        },
                        status=GenerationStatus.COMPLETED
                    )
                except Exception as save_err:
                    logger.error(f"保存完成状态失败: {save_err}")

        except Exception as e:
            logger.error(f"单元概述生成失败: {e}")
            # 保存失败状态
            try:
                await state_manager.save_stage(
                    stage='units_generating',
                    stage_data={
                        'global_outline': data.global_outline,
                        'partial_unit_summaries': ''.join(content_buffer),
                        'error': str(e)[:500]
                    },
                    status=GenerationStatus.FAILED
                )
            except Exception as save_err:
                logger.error(f"保存失败状态失败: {save_err}")
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


@router.get("/outline/units/resume-info/{project_id}")
async def get_unit_summaries_resume_info(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取单元概述断点续生成信息

    根据项目ID自动识别当前生成状态和断点位置，返回续生成所需的全部信息：
    - existing_parsed: 已解析的单元数据
    - existing_content: 已生成的原始文本内容
    - existing_count: 已生成章节数
    - expected_count: 预期总章节数（来自全局大纲/项目设置）
    - start_from_unit: 建议续生成的起始章节号
    - global_outline: 全局大纲内容
    """
    from app.models.novel_project import NovelProject
    from app.core.exceptions import NotFoundException
    from sqlalchemy import select

    # 获取项目
    query = select(NovelProject).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise NotFoundException(f"项目不存在: {project_id}")

    # 获取已有的单元概述数据
    existing_parsed = project.unit_summaries or {}
    existing_count = len(existing_parsed)

    # 获取预期总章节数
    expected_count = project.total_chapters or 0

    # 如果 unit_summaries 中有更多数据，以实际数量为准
    if existing_count > expected_count:
        expected_count = existing_count

    # 如果预期数仍为0，尝试从全局大纲推断
    if expected_count == 0 and project.global_outline_content:
        # 从全局大纲中尝试提取章节数
        import re
        chapter_matches = re.findall(
            r'第[一二三四五六七八九十百千万\d]+章',
            project.global_outline_content
        )
        if chapter_matches:
            expected_count = len(set(chapter_matches))

    # 获取全局大纲内容
    global_outline = project.global_outline_content or ""

    # 计算续生成起始位置
    start_from_unit = existing_count + 1 if existing_count > 0 else 1

    # 重建 existing_content 文本
    existing_content_parts = []
    content_type = getattr(project, 'content_type', 'novel')
    unit_label = '章' if content_type == 'novel' else '集' if content_type in (
        'series_script', 'script') else '场'

    for unit_num, unit_data in sorted(existing_parsed.items(), key=lambda x: int(x[0])):
        title = unit_data.get("title", "")
        summary = unit_data.get("summary", "")
        full_content = unit_data.get("full_content", "") or summary
        existing_content_parts.append(
            f"### 第{unit_num}{unit_label}：{title}\n{full_content}"
        )
    existing_content = "\n\n".join(existing_content_parts)

    # 判断是否可以续生成
    can_resume = existing_count > 0 and existing_count < expected_count

    return ResponseModel(
        success=True,
        message="断点信息获取成功",
        data={
            "project_id": project_id,
            "project_title": project.title or "未命名项目",
            "content_type": content_type,
            "existing_count": existing_count,
            "expected_count": expected_count,
            "start_from_unit": start_from_unit,
            "can_resume": can_resume,
            "remaining_count": max(0, expected_count - existing_count),
            "global_outline": global_outline,
            "existing_parsed": existing_parsed,
            "existing_content": existing_content
        }
    )


@router.post("/outline/units/quality-control")
async def quality_control_unit_summaries(
    data: UnitSummariesQCRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    对单元概述执行质量检测和修正（手动触发）

    流程（参照全局大纲质控）：
    1. 调用LLM检测质量问题
    2. 如果发现critical问题且enable_auto_revise=True，自动调用LLM修正
    3. 返回质控报告 + 修正后内容 + 变更列表（用于前端高亮对比）
    """
    try:
        # 参数验证
        if not data.unit_summaries:
            from app.core.exceptions import ValidationException
            raise ValidationException("单元概述数据不能为空")

        if not isinstance(data.unit_summaries, dict):
            from app.core.exceptions import ValidationException
            raise ValidationException("单元概述数据格式错误，应为字典类型")

        if len(data.unit_summaries) == 0:
            from app.core.exceptions import ValidationException
            raise ValidationException("单元概述数据为空，至少需要一个单元")

        from app.services.outline_generator import get_outline_generator

        generator = get_outline_generator(db)

        # 步骤1: 调用LLM执行质量检测
        logger.info(f"[单元概述质控] 开始LLM质量检测，单元数: {len(data.unit_summaries)}")

        quality_report = await generator.analyze_unit_summaries_quality_manual(
            unit_summaries=data.unit_summaries,
            global_outline=data.global_outline,
            content_type=data.content_type,
            user_id=current_user.id
        )

        logger.info(f"[单元概述质控] 检测完成，总分: {quality_report.get('overall_score', 0)}, "
                    f"问题数: {len(quality_report.get('issues', []))}")

        # 步骤2: 检查是否有问题需要修正（所有级别：critical + major + minor）
        # 修复1：不限制只修正critical，而是修正所有问题
        all_issues = quality_report.get("issues", [])

        revised_content = None
        revised_parsed = None
        changes = []

        if all_issues and data.enable_auto_revise:
            logger.info(f"[单元概述质控] 发现{len(all_issues)}个问题，执行LLM自动修正...")

            # 构建完整的单元概述文本（修正前）
            unit_label = "章" if data.content_type == "novel" else "集"
            original_content_parts = []
            for unit_num, unit_data in sorted(data.unit_summaries.items(), key=lambda x: int(x[0])):
                title = unit_data.get("title", "")
                full_content = unit_data.get(
                    "full_content", "") or unit_data.get("summary", "")
                original_content_parts.append(
                    f"### 第{unit_num}{unit_label}：{title}\n{full_content}")
            original_content = "\n\n".join(original_content_parts)

            # 调用LLM修正（参照全局大纲的修正流程）
            revision_result = await generator.revise_unit_summaries_quality(
                unit_summaries=data.unit_summaries,
                quality_report=quality_report,
                global_outline=data.global_outline,
                content_type=data.content_type,
                temperature=data.temperature,
                user_id=current_user.id
            )

            revised_content = revision_result.get("revised_content")
            revised_parsed = revision_result.get("revised_parsed")
            changes = revision_result.get("changes", [])

            logger.info(f"[单元概述质控] LLM修正完成，修正前长度: {len(original_content)}, "
                        f"修正后长度: {len(revised_content) if revised_content else 0}")

        # 步骤3: 返回完整结果（用于前端对比显示）
        return ResponseModel(
            success=True,
            message="质控检测完成",
            data={
                "quality_report": quality_report,
                "revised_content": revised_content,
                "revised_parsed": revised_parsed,
                "changes": changes,
                "has_issues": len(all_issues) > 0,  # 修复1：改为has_issues
                "issues_count": len(all_issues),  # 修复1：改为issues_count
                "auto_revised": len(changes) > 0
            }
        )

    except Exception as e:
        logger.error(f"[单元概述质控] 失败: {str(e)}", exc_info=True)
        from app.core.exceptions import GenerationException
        raise GenerationException(f"质控失败: {str(e)}")


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
        raise ValidationException("大纲内容不能为空")

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
        raise ValidationException(str(e))
    except Exception as e:
        logger.error(f"逻辑检测失败: {str(e)}")
        raise GenerationException(f"检测失败: {str(e)}")


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


# ==================== 修订相关 API ====================

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
    from app.models.generation import GenerationRevisionHistory
    from sqlalchemy import select

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
    """
    最终确认生成内容,执行知识库修正和自反思优化
    """
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
        from app.models.generation import GenerationRevisionHistory
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
