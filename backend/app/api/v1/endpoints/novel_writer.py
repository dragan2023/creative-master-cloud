"""
小说/剧本正文生成 API 端点
提供项目管理、大纲上传、章节生成、导出等功能
"""
import os
import uuid
import json
import re
import tempfile
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.config import get_settings
from app.core.logger import get_logger
from app.api.deps import get_current_user, get_current_user_from_query_or_header
from app.models import (
    User, NovelProject, NovelChapter,
    ProjectType, ProjectStatus, ChapterStatus
)
from app.schemas.common import ResponseModel

from app.schemas.novel_writer import (
    NovelProjectCreate, NovelProjectUpdate, NovelProjectResponse, NovelProjectListResponse,
    OutlineUploadResponse, DirectoryGenerateRequest, DirectoryResponse,
    DirectoryUpdateRequest, ChapterMetadata,
    ChapterGenerateRequest, ChapterGenerateResponse, ChapterContentResponse,
    ChapterContentUpdate, ChapterListResponse,
    ExportRequest, ExportResponse, GenerationProgress,
    BatchGenerateRequest, BatchGenerateResponse,
    # 剧本专用
    ScriptProjectCreate, SceneGenerateRequest, SceneGenerateResponse,
    ScriptDirectoryRequest, ScriptDirectoryResponse, EpisodeDirectory,
    CharacterInfo, CharacterListResponse,
    # 新增类型
    ContentType, NovelConfig, SeriesScriptConfig, MovieScriptConfig,
    # 分集详细大纲
    EpisodeOutlineBase, EpisodeOutlineCreate, EpisodeOutlineUpdate, EpisodeOutlineResponse,
    EpisodeOutlineListResponse, EpisodeOutlineGenerateRequest, EpisodeOutlineScene,
    # 章节详细大纲（小说专用）
    ChapterOutlineBase, ChapterOutlineCreate, ChapterOutlineUpdate, ChapterOutlineResponse,
    ChapterOutlineListResponse, ChapterOutlineGenerateRequest,
    # 场景详细大纲（电影剧本专用）
    SceneOutlineBase, SceneOutlineCreate, SceneOutlineUpdate, SceneOutlineResponse,
    SceneOutlineListResponse, SceneOutlineGenerateRequest
)
from app.services.novel_writer.generator import NovelChapterGenerator
from app.services.novel_writer.exporter import NovelExporter
from app.services.task_manager import (
    task_manager, set_memory_cancel_token, clear_memory_cancel_token,
    trigger_memory_cancel, is_memory_cancelled
)


router = APIRouter(prefix="/novel-writer", tags=["小说/剧本生成"])
settings = get_settings()
logger = get_logger("novel_writer")

# 内存取消令牌字典（用于即时取消批量生成任务）
# 当 Redis 连接失败时，使用内存令牌作为后备方案
cancel_tokens: Dict[int, asyncio.Event] = {}


def set_cancel_token(project_id: int) -> asyncio.Event:
    """为项目创建取消令牌（同时设置内存令牌）"""
    # 设置 task_manager 中的内存令牌
    return set_memory_cancel_token(project_id)


def get_cancel_token(project_id: int) -> Optional[asyncio.Event]:
    """获取项目的取消令牌"""
    from app.services.task_manager import get_memory_cancel_token
    return get_memory_cancel_token(project_id)


def clear_cancel_token(project_id: int):
    """清除项目的取消令牌"""
    clear_memory_cancel_token(project_id)


def is_cancelled(project_id: int) -> bool:
    """检查项目是否被取消"""
    return is_memory_cancelled(project_id)


# ==================== 工具函数 ====================

def generate_project_code() -> str:
    """生成项目代码 NW_{timestamp}_{random_id}"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_id = uuid.uuid4().hex[:6]
    return f"NW_{timestamp}_{random_id}"


def get_project_data_dir(project_code: str) -> str:
    """获取项目数据目录"""
    base_dir = settings.CHROMA_PERSIST_DIR.replace(
        "/chroma", "/novel_projects")
    project_dir = os.path.join(base_dir, project_code)
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(os.path.join(project_dir, "chapters"), exist_ok=True)
    return project_dir


def _build_project_response(project: NovelProject) -> NovelProjectResponse:
    """构建项目响应对象（统一处理新版和旧版字段）"""
    # 获取content_type
    content_type = None
    if hasattr(project, 'content_type') and project.content_type:
        try:
            content_type = ContentType(project.content_type)
        except ValueError:
            pass

    # 兼容旧版：如果没有content_type，根据project_type推断
    if not content_type:
        if project.project_type == ProjectType.NOVEL:
            content_type = ContentType.NOVEL
        else:
            content_type = ContentType.SERIES_SCRIPT  # 默认为剧集剧本

    # 构建配置对象
    novel_config = None
    series_script_config = None
    movie_script_config = None

    # 从数据库字段获取配置
    if hasattr(project, 'novel_config') and project.novel_config:
        novel_config = NovelConfig(**project.novel_config) if isinstance(
            project.novel_config, dict) else project.novel_config
    if hasattr(project, 'series_script_config') and project.series_script_config:
        series_script_config = SeriesScriptConfig(**project.series_script_config) if isinstance(
            project.series_script_config, dict) else project.series_script_config
    if hasattr(project, 'movie_script_config') and project.movie_script_config:
        movie_script_config = MovieScriptConfig(**project.movie_script_config) if isinstance(
            project.movie_script_config, dict) else project.movie_script_config

    return NovelProjectResponse(
        id=project.id,
        title=project.title,
        project_type=project.project_type,
        content_type=content_type,
        genre=project.genre,
        target_platform=project.target_platform,
        status=project.status,
        total_chapters=project.total_chapters,
        completed_chapters=project.completed_chapters,
        current_chapter=project.current_chapter,
        progress_percentage=project.get_progress_percentage(),
        novel_config=novel_config,
        series_script_config=series_script_config,
        movie_script_config=movie_script_config,
        generation_config=project.generation_config,
        knowledge_base_config=project.knowledge_base_config,
        script_config=project.script_config,
        project_code=project.project_code,
        total_tokens=project.total_tokens,
        total_duration_ms=project.total_duration_ms,
        outline_content=project.outline_content[:500] + "..." if project.outline_content and len(
            project.outline_content) > 500 else project.outline_content,
        created_at=project.created_at,
        updated_at=project.updated_at
    )


# ==================== 项目管理 API ====================

@router.post("/projects", response_model=ResponseModel[NovelProjectResponse])
async def create_project(
    request: NovelProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新项目

    支持三种内容类型：
    - novel: 小说（生成单位：章节）
    - series_script: 剧集剧本（生成单位：分集）
    - movie_script: 电影剧本（生成单位：场景）
    """
    try:
        # 生成项目代码和目录
        project_code = generate_project_code()
        project_dir = get_project_data_dir(project_code)

        # 根据content_type确定project_type（兼容数据库模型）
        content_type = request.content_type
        if content_type == ContentType.NOVEL:
            project_type = ProjectType.NOVEL
        else:
            project_type = ProjectType.SCRIPT

        # 构建generation_config
        generation_config = {
            "temperature": 0.8,
            "words_per_chapter": 3000,
            "max_context_tokens": 4096,
            "recent_chapters_count": 3
        }

        # 根据content_type处理配置
        if content_type == ContentType.NOVEL:
            novel_config = request.novel_config or NovelConfig()
            generation_config.update({
                "words_per_chapter": novel_config.words_per_chapter,
                "temperature": novel_config.temperature,
                "narrative_perspective": novel_config.narrative_perspective,
                "tone": novel_config.tone,
                "total_words": novel_config.total_words,
                "style_reference": novel_config.style_reference
            })
            target_platform = novel_config.target_platform
            script_config = {}
            novel_config_dict = novel_config.model_dump()
            series_script_config_dict = None
            movie_script_config_dict = None

        elif content_type == ContentType.SERIES_SCRIPT:
            series_config = request.series_script_config or SeriesScriptConfig()
            generation_config["temperature"] = series_config.temperature if hasattr(
                series_config, 'temperature') else 0.8
            script_config = series_config.model_dump()
            target_platform = series_config.target_broadcast
            novel_config_dict = None
            series_script_config_dict = series_config.model_dump()
            movie_script_config_dict = None

        else:  # movie_script
            movie_config = request.movie_script_config or MovieScriptConfig()
            generation_config["temperature"] = movie_config.temperature if hasattr(
                movie_config, 'temperature') else 0.8
            script_config = movie_config.model_dump()
            target_platform = movie_config.target_platform
            novel_config_dict = None
            series_script_config_dict = None
            movie_script_config_dict = movie_config.model_dump()

        # 兼容旧版请求
        if request.generation_config:
            generation_config.update(request.generation_config)
        if not target_platform and request.target_platform:
            target_platform = request.target_platform
        if not script_config and request.script_config:
            script_config = request.script_config

        # 创建项目
        project = NovelProject(
            user_id=current_user.id,
            title=request.title,
            project_type=project_type,
            content_type=content_type.value,  # 新增字段
            genre=request.genre,
            target_platform=target_platform,
            generation_config=generation_config,
            knowledge_base_config=request.knowledge_base_config or {},
            script_config=script_config,
            # 新增配置字段（JSON存储）
            novel_config=novel_config_dict,
            series_script_config=series_script_config_dict,
            movie_script_config=movie_script_config_dict,
            project_code=project_code,
            architecture_file=os.path.join(
                project_dir, f"{project_code}_architecture.txt"),
            directory_file=os.path.join(
                project_dir, f"{project_code}_directory.json"),
            summary_file=os.path.join(
                project_dir, f"{project_code}_summary.txt"),
            characters_file=os.path.join(
                project_dir, f"{project_code}_characters.json"),
            vectorstore_path=os.path.join(
                project_dir, f"{project_code}_vectorstore"),
            chapters_dir=os.path.join(project_dir, "chapters"),
            status=ProjectStatus.INIT
        )

        db.add(project)
        await db.commit()
        await db.refresh(project)

        logger.info(
            f"创建项目成功: {project.title} ({project.project_code}), 类型: {content_type.value}")

        return ResponseModel(
            success=True,
            data=_build_project_response(project)
        )

    except Exception as e:
        logger.error(f"创建项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects", response_model=ResponseModel[NovelProjectListResponse])
async def list_projects(
    project_type: Optional[str] = None,
    content_type: Optional[str] = None,  # 新增：按内容类型筛选
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目列表

    支持按content_type筛选：novel, series_script, movie_script
    """
    try:
        # 构建查询
        query = select(NovelProject).where(
            NovelProject.user_id == current_user.id)

        # 按内容类型筛选（新版）
        if content_type:
            query = query.where(NovelProject.content_type == content_type)
        # 兼容旧版按project_type筛选
        elif project_type:
            query = query.where(NovelProject.project_type ==
                                ProjectType(project_type))
        if status:
            query = query.where(NovelProject.status == ProjectStatus(status))

        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # 分页
        query = query.order_by(NovelProject.updated_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        projects = result.scalars().all()

        items = [_build_project_response(p) for p in projects]

        return ResponseModel(
            success=True,
            data=NovelProjectListResponse(items=items, total=total)
        )

    except Exception as e:
        logger.error(f"获取项目列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}", response_model=ResponseModel[NovelProjectResponse])
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目详情
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        return ResponseModel(
            success=True,
            data=_build_project_response(project)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}", response_model=ResponseModel[NovelProjectResponse])
async def update_project(
    project_id: int,
    request: NovelProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新项目配置

    支持更新三种类型的独立配置：
    - novel_config: 小说配置
    - series_script_config: 剧集剧本配置
    - movie_script_config: 电影剧本配置
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 更新基本字段
        if request.title:
            project.title = request.title
        if request.genre:
            project.genre = request.genre

        # 更新新版配置字段
        if request.novel_config:
            project.novel_config = request.novel_config.model_dump()
            # 同步更新generation_config（兼容旧版）
            project.generation_config = {
                **(project.generation_config or {}),
                "words_per_chapter": request.novel_config.words_per_chapter,
                "temperature": request.novel_config.temperature,
            }
            if request.novel_config.target_platform:
                project.target_platform = request.novel_config.target_platform

        if request.series_script_config:
            project.series_script_config = request.series_script_config.model_dump()
            # 同步更新script_config（兼容旧版）
            project.script_config = request.series_script_config.model_dump()
            if request.series_script_config.target_broadcast:
                project.target_platform = request.series_script_config.target_broadcast

        if request.movie_script_config:
            project.movie_script_config = request.movie_script_config.model_dump()
            # 同步更新script_config（兼容旧版）
            project.script_config = request.movie_script_config.model_dump()
            if request.movie_script_config.target_platform:
                project.target_platform = request.movie_script_config.target_platform

        # 兼容旧版字段
        if request.target_platform:
            project.target_platform = request.target_platform
        if request.generation_config:
            project.generation_config = request.generation_config
        if request.knowledge_base_config:
            project.knowledge_base_config = request.knowledge_base_config
        if request.script_config:
            project.script_config = request.script_config

        await db.commit()
        await db.refresh(project)

        logger.info(f"更新项目成功: {project.title}")

        return ResponseModel(
            success=True,
            data=_build_project_response(project)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除项目
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 删除项目文件
        if project.project_code:
            project_dir = get_project_data_dir(project.project_code)
            if os.path.exists(project_dir):
                import shutil
                shutil.rmtree(project_dir)

        # 删除数据库记录（级联删除章节）
        await db.delete(project)
        await db.commit()

        logger.info(f"删除项目成功: {project.title}")

        return ResponseModel(success=True, message="项目已删除")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 大纲上传 API ====================

@router.post("/projects/{project_id}/upload-outline", response_model=ResponseModel[OutlineUploadResponse])
async def upload_outline(
    project_id: int,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传大纲文件

    根据项目类型自动识别：
    - 小说：识别章节数
    - 剧集剧本：识别分集数
    - 电影剧本：识别场景数

    上传后自动触发知识库构建（如果启用GraphRAG）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取文件扩展名
        file_ext = os.path.splitext(file.filename)[1].lower()
        logger.info(f"[大纲上传] 文件名: {file.filename}, 扩展名: {file_ext}")

        # 根据文件类型选择解析方式
        outline_content = None

        if file_ext in ['.txt', '.md']:
            # 文本文件直接读取
            content = await file.read()
            try:
                outline_content = content.decode('utf-8')
            except UnicodeDecodeError:
                outline_content = content.decode('gbk', errors='ignore')
            logger.info(f"[大纲上传] 文本文件直接解码成功，长度: {len(outline_content)}字")

        elif file_ext in ['.docx', '.doc']:
            # Word文件需要使用file_parser正确解析
            from app.tools.file_parser import get_file_parser

            # 保存临时文件
            temp_file = os.path.join(
                tempfile.gettempdir(), f"outline_{project_id}_{file.filename}")
            content = await file.read()
            with open(temp_file, 'wb') as f:
                f.write(content)

            # 使用file_parser解析
            file_parser = get_file_parser()
            parse_result = await file_parser.parse(temp_file)

            # 清理临时文件
            try:
                os.remove(temp_file)
            except:
                pass

            if "error" in parse_result:
                raise HTTPException(
                    status_code=400, detail=f"文件解析失败: {parse_result['error']}")

            outline_content = parse_result.get("content", "")
            char_count = parse_result.get("metadata", {}).get(
                "char_count", len(outline_content))
            logger.info(f"[大纲上传] Word文件解析成功，实际字符数: {char_count}")

        else:
            raise HTTPException(
                status_code=400, detail=f"不支持的文件格式: {file_ext}")

        if not outline_content or not outline_content.strip():
            raise HTTPException(status_code=400, detail="大纲内容为空")

        # 计算实际字数（去除空白字符后的字符数）
        actual_char_count = len(outline_content.strip())
        logger.info(f"[大纲上传] 大纲实际字数: {actual_char_count}字")

        # 保存大纲到文件
        project_dir = get_project_data_dir(project.project_code)
        outline_file = os.path.join(
            project_dir, f"{project.project_code}_outline.txt")

        with open(outline_file, 'w', encoding='utf-8') as f:
            f.write(outline_content)
        logger.info(f"[大纲上传] 文件已保存: {outline_file}")

        # 更新项目的大纲字段
        project.outline_file_path = outline_file
        project.outline_content = outline_content
        logger.info(
            f"[大纲上传] 项目字段已更新: outline_content长度={len(outline_content)}")

        # 获取项目的content_type
        content_type = getattr(project, 'content_type', None)
        if not content_type:
            # 兼容旧版：根据project_type推断
            if project.project_type == ProjectType.NOVEL:
                content_type = "novel"
            else:
                content_type = "series_script"

        # 根据内容类型提取单元数
        extracted_count = extract_chapter_count(outline_content, content_type)

        # 提交数据库更改
        await db.commit()
        logger.info(f"[大纲上传] 数据库已提交, 提取{content_type}单元数: {extracted_count}")

        # 获取单元标签
        unit_labels = {
            "novel": "章节",
            "series_script": "分集",
            "movie_script": "场景"
        }
        unit_label = unit_labels.get(content_type, "章节")

        logger.info(
            f"大纲上传成功: {project.title}, 提取{unit_label}数: {extracted_count}")

        # 知识库构建改为手动触发，不再自动构建
        # 用户需要在项目详情页点击"构建知识库"按钮来启动

        return ResponseModel(
            success=True,
            data=OutlineUploadResponse(
                project_id=project.id,
                outline_content=outline_content[:1000] + "..." if len(
                    outline_content) > 1000 else outline_content,
                extracted_chapters=extracted_count,
                message=f"大纲上传成功，共{actual_char_count}字，识别到{extracted_count}个{unit_label}"
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 单元概述上传 API ====================

class UnitSummariesUploadRequest(BaseModel):
    """单元概述上传请求"""
    unit_summaries: Dict[str, Any]  # 单元概述字典
    global_outline: Optional[str] = None  # 可选的全局大纲


class UnitSummariesUploadResponse(BaseModel):
    """单元概述上传响应"""
    project_id: int
    unit_count: int
    message: str


@router.post("/projects/{project_id}/upload-unit-summaries", response_model=ResponseModel[UnitSummariesUploadResponse])
async def upload_unit_summaries(
    project_id: int,
    request: UnitSummariesUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传单元概述

    用于正文生成板块，支持用户手动上传单元概述数据。
    单元概述用于指导单元详细大纲的生成。

    Args:
        project_id: 项目ID
        request: 包含 unit_summaries 字典和可选的 global_outline

    Returns:
        上传结果
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 验证单元概述格式
        unit_summaries = request.unit_summaries
        if not unit_summaries or not isinstance(unit_summaries, dict):
            raise HTTPException(status_code=400, detail="单元概述格式无效")

        # 验证每个单元的结构
        valid_keys = {'unit_number', 'title', 'summary', 'status'}
        for key, unit in unit_summaries.items():
            if not isinstance(unit, dict):
                raise HTTPException(status_code=400, detail=f"单元 {key} 格式无效")
            # 确保有必要的字段
            if 'summary' not in unit:
                raise HTTPException(
                    status_code=400, detail=f"单元 {key} 缺少 summary 字段")

        # 更新项目的单元概述字段
        project.unit_summaries = unit_summaries
        project.unit_summaries_status = 'completed'
        project.unit_summaries_created_at = datetime.now().isoformat()

        # 如果提供了全局大纲，也一并更新
        if request.global_outline:
            project.global_outline_content = request.global_outline
            project.global_outline_status = 'completed'
            project.global_outline_created_at = datetime.now().isoformat()

        # 更新项目的总单元数
        project.total_chapters = len(unit_summaries)

        await db.commit()

        logger.info(
            f"单元概述上传成功: project_id={project_id}, unit_count={len(unit_summaries)}")

        return ResponseModel(
            success=True,
            data=UnitSummariesUploadResponse(
                project_id=project.id,
                unit_count=len(unit_summaries),
                message=f"单元概述上传成功，共 {len(unit_summaries)} 个单元"
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传单元概述失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/upload-unit-summaries-file", response_model=ResponseModel[UnitSummariesUploadResponse])
async def upload_unit_summaries_file(
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传单元概述文件

    支持与全局大纲相同的文件格式：.txt, .md, .docx, .doc
    自动解析文件内容并提取单元概述结构

    文件格式要求：
    - 小说：包含章节标题（如 ### 第1章：xxx）和梗概内容
    - 剧集剧本：包含分集标题（如 ### 第1集：xxx）和梗概内容
    - 电影剧本：包含场景标题（如 **第1场：xxx）和梗概内容
    """
    import tempfile
    import os

    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取文件扩展名
        file_ext = os.path.splitext(file.filename)[1].lower()
        logger.info(f"[单元概述上传] 文件名: {file.filename}, 扩展名: {file_ext}")

        # 根据文件类型选择解析方式（复用大纲上传的逻辑）
        file_content = None

        if file_ext in ['.txt', '.md']:
            # 文本文件直接读取
            content = await file.read()
            try:
                file_content = content.decode('utf-8')
            except UnicodeDecodeError:
                file_content = content.decode('gbk', errors='ignore')
            logger.info(f"[单元概述上传] 文本文件直接解码成功，长度: {len(file_content)}字")

        elif file_ext in ['.docx', '.doc']:
            # Word文件需要使用file_parser正确解析
            from app.tools.file_parser import get_file_parser

            # 保存临时文件
            temp_file = os.path.join(
                tempfile.gettempdir(), f"unit_summaries_{project_id}_{file.filename}")
            content = await file.read()
            with open(temp_file, 'wb') as f:
                f.write(content)

            # 使用file_parser解析
            file_parser = get_file_parser()
            parse_result = await file_parser.parse(temp_file)

            # 清理临时文件
            try:
                os.remove(temp_file)
            except:
                pass

            if "error" in parse_result:
                raise HTTPException(
                    status_code=400, detail=f"文件解析失败: {parse_result['error']}")

            file_content = parse_result.get("content", "")
            logger.info(f"[单元概述上传] Word文件解析成功，长度: {len(file_content)}字")

        else:
            raise HTTPException(
                status_code=400, detail=f"不支持的文件格式: {file_ext}，支持 .txt, .md, .docx, .doc")

        if not file_content or not file_content.strip():
            raise HTTPException(status_code=400, detail="文件内容为空")

        # 获取项目的content_type
        content_type = getattr(project, 'content_type', None)
        if not content_type:
            # 兼容旧版：根据project_type推断
            if project.project_type == ProjectType.NOVEL:
                content_type = "novel"
            else:
                content_type = "series_script"

        # 解析单元概述内容
        unit_summaries = parse_unit_summaries_from_content(
            file_content, content_type)

        if not unit_summaries:
            raise HTTPException(
                status_code=400,
                detail="无法从文件中解析出单元概述，请检查文件格式是否正确")

        # 更新项目的单元概述字段
        project.unit_summaries = unit_summaries
        project.unit_summaries_status = 'completed'
        project.unit_summaries_created_at = datetime.now().isoformat()
        project.total_chapters = len(unit_summaries)

        await db.commit()

        logger.info(
            f"单元概述文件上传成功: project_id={project_id}, unit_count={len(unit_summaries)}")

        return ResponseModel(
            success=True,
            data=UnitSummariesUploadResponse(
                project_id=project.id,
                unit_count=len(unit_summaries),
                message=f"单元概述上传成功，共解析出 {len(unit_summaries)} 个单元"
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传单元概述文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def parse_unit_summaries_from_content(content: str, content_type: str) -> Dict[str, Any]:
    """
    从文件内容中解析单元概述

    支持的格式：
    - 小说：### 第X章：标题 后跟 **本章梗概**：内容
    - 剧集：### 第X集：标题 后跟 **本集梗概**：内容
    - 电影：**第X场：标题** 后跟 **本场梗概**：内容

    Args:
        content: 文件内容
        content_type: 内容类型（novel/series_script/movie_script）

    Returns:
        单元概述字典 {"1": {"unit_number": 1, "title": "...", "summary": "..."}, ...}
    """
    import re

    result = {}

    if content_type == "movie_script":
        # 电影剧本：匹配 **第X场：标题** 格式
        pattern = r'\*\*第(\d+)场[：:]\s*(.+?)\*\*'
        matches = re.findall(pattern, content)

        for match in matches:
            unit_num = int(match[0])
            title = match[1].strip()

            # 提取本场梗概
            summary_pattern = re.compile(
                rf'\*\*第{unit_num}场.*?\*\*.*?\*\*本场梗概\*\*[：:]\s*(.+?)(?=\*\*第\d+场|$)',
                re.DOTALL
            )
            summary_match = summary_pattern.search(content)
            summary = summary_match.group(1).strip() if summary_match else ""

            result[str(unit_num)] = {
                "unit_number": unit_num,
                "title": title,
                "summary": summary,
                "status": "completed"
            }
    else:
        # 小说/剧集：匹配 ### 第X章/集：标题 格式
        if content_type == "novel":
            pattern = r'###\s*第(\d+)章[：:]\s*(.+?)(?:\n|$)'
        else:  # series_script
            pattern = r'###\s*第(\d+)集[：:]\s*(.+?)(?:\n|$)'

        matches = re.findall(pattern, content)

        for match in matches:
            unit_num = int(match[0])
            title = match[1].strip()

            # 提取本章/本集梗概
            summary_pattern = re.compile(
                rf'第{unit_num}(章|集).*?\*\*本(章|集)梗概\*\*[：:]\s*(.+?)(?=###\s*第\d+|$)',
                re.DOTALL
            )
            summary_match = summary_pattern.search(content)
            summary = summary_match.group(3).strip() if summary_match else ""

            result[str(unit_num)] = {
                "unit_number": unit_num,
                "title": title,
                "summary": summary,
                "status": "completed"
            }

    return result


def extract_chapter_count(content: str, content_type: str = "novel") -> int:
    """从大纲内容中提取章节数/集数/场景数

    使用统一的 ChapterRecognizer 进行识别，确保与校对功能一致

    根据内容类型使用不同的识别规则：
    - novel: 识别章节（第X章、Chapter X等）
    - series_script: 识别分集（第X集、Episode X等）
    - movie_script: 识别场景（第X场、Scene X等）

    Args:
        content: 大纲内容
        content_type: 内容类型（novel/series_script/movie_script）

    Returns:
        识别到的章节数/集数/场景数
    """
    from app.services.proofread.chapter_recognizer import count_chapters

    return count_chapters(content, content_type)


def extract_outline_units(content: str, content_type: str = "novel") -> List[Dict[str, Any]]:
    """从大纲内容中提取结构化单元（章节/分集/场景）

    使用统一的 ChapterRecognizer 进行识别，确保与校对功能一致

    返回每个单元的序号和标题，供前端确认和调整

    Args:
        content: 大纲内容
        content_type: 内容类型

    Returns:
        单元列表，每个单元包含 number, title, content
    """
    from app.services.proofread.chapter_recognizer import recognize_chapters

    matches = recognize_chapters(content, content_type)

    # 确定单元类型名称
    unit_type_map = {
        "novel": "章",
        "series_script": "集",
        "movie_script": "场"
    }
    unit_type = unit_type_map.get(content_type, "章")

    units = []
    for match in matches:
        units.append({
            "number": match["number"],
            "title": match["title"] or f"第{match['number']}{unit_type}",
            "line": match.get("original_line", ""),
            "confidence": match.get("confidence", 1.0)
        })

    return units


def _chinese_to_number(chinese: str) -> int:
    """将中文数字转换为阿拉伯数字

    保留此函数以兼容旧代码，委托给统一的 ChapterRecognizer 处理
    """
    from app.services.proofread.chapter_recognizer import ChapterRecognizer

    recognizer = ChapterRecognizer()
    return recognizer._chinese_to_number(chinese)


# ==================== 章节目录 API ====================

@router.post("/projects/{project_id}/generate-directory")
async def generate_directory(
    project_id: int,
    request: DirectoryGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成章节目录

    可选择是否预先生成章节名称：
    - 如果 generate_names=True，会调用LLM为每个章节生成标题
    - 生成的标题会保存到章节数据库记录中

    剧本类型特殊处理：
    - 自动从项目配置获取集数和场景配置
    - 为每个场景正确设置 episode_number 和 scene_number
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        if not project.outline_content:
            raise HTTPException(status_code=400, detail="请先上传大纲文件")

        # 获取内容类型
        content_type = getattr(project, 'content_type', None)
        if not content_type:
            content_type = project.project_type.value if hasattr(
                project, 'project_type') else 'novel'

        # 更新状态
        project.status = ProjectStatus.DIRECTORY
        project.total_chapters = request.total_chapters
        await db.commit()

        # 先删除现有章节（避免重复创建）
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(NovelChapter).where(NovelChapter.project_id == project.id))
        await db.commit()
        logger.info(f"已清空项目 {project.id} 的现有章节")

        # 创建章节记录
        chapters_to_create = []

        # 根据内容类型进行不同处理
        if content_type in ('series_script', 'script'):
            # 剧集类型：连续剧一集一章
            # 从项目配置获取集数
            script_config = project.series_script_config or project.script_config or {}
            episode_count = script_config.get(
                'episode_count', request.total_chapters)

            logger.info(
                f"连续剧目录生成: 集数={episode_count}（一集对应一章）")

            # 获取已有的分集大纲
            episode_outlines = project.episode_outlines or {}

            # 为每集创建一章（不是场景）
            for ep in range(1, episode_count + 1):
                # 尝试从分集大纲获取标题
                ep_outline = episode_outlines.get(str(ep), {})
                episode_title = ep_outline.get('episode_title', '')

                if episode_title:
                    chapter_title = f"第{ep}集 {episode_title}"
                else:
                    chapter_title = f"第{ep}集"

                chapter = NovelChapter(
                    project_id=project.id,
                    chapter_number=ep,  # 章节号等于集数
                    chapter_title=chapter_title,
                    episode_number=ep,   # 集数
                    scene_number=None,   # 不再使用场景号
                    status=ChapterStatus.PENDING
                )
                chapters_to_create.append(chapter)

            # 更新总章节数为集数
            project.total_chapters = episode_count
            logger.info(
                f"连续剧目录创建完成: 共{episode_count}集")

        elif content_type == 'movie_script':
            # 电影类型：一场戏一章
            # 从项目配置获取场景数
            movie_config = project.movie_script_config or {}
            total_scenes = movie_config.get(
                'total_scenes', request.total_chapters)

            logger.info(
                f"电影剧本目录生成: 场景数={total_scenes}（一场对应一章）")

            # 获取已有的场景大纲
            scene_outlines = project.scene_outlines or {}

            # 为每场戏创建一章
            for sc in range(1, total_scenes + 1):
                # 尝试从场景大纲获取标题
                sc_outline = scene_outlines.get(str(sc), {})
                scene_title = sc_outline.get('scene_title', '')

                if scene_title:
                    chapter_title = f"第{sc}场 {scene_title}"
                else:
                    chapter_title = f"第{sc}场"

                chapter = NovelChapter(
                    project_id=project.id,
                    chapter_number=sc,  # 章节号等于场号
                    chapter_title=chapter_title,
                    episode_number=None,  # 电影没有集数
                    scene_number=sc,      # 场号
                    status=ChapterStatus.PENDING
                )
                chapters_to_create.append(chapter)

            # 更新总章节数为场景数
            project.total_chapters = total_scenes
            logger.info(
                f"电影剧本目录创建完成: 共{total_scenes}场")

        else:
            # 小说类型：直接创建章节
            for i in range(1, request.total_chapters + 1):
                chapter = NovelChapter(
                    project_id=project.id,
                    chapter_number=i,
                    chapter_title=f"第{i}章",
                    status=ChapterStatus.PENDING
                )
                chapters_to_create.append(chapter)

        db.add_all(chapters_to_create)
        await db.commit()

        # 如果请求预生成章节名称
        if request.generate_names:
            try:
                # 获取LLM提供者
                from app.agents.llm_manager import llm_manager
                llm_provider = await llm_manager.get_provider_from_db(
                    db, project.user_id
                )

                if llm_provider:
                    # 获取内容类型
                    content_type = getattr(project, 'content_type', 'novel')

                    # 获取单元标签
                    unit_labels = {
                        "novel": "章节",
                        "series_script": "分集",
                        "movie_script": "场景"
                    }
                    unit_label = unit_labels.get(content_type, "章节")

                    # 构建提示词
                    from app.services.novel_writer.prompt_templates import (
                        CHAPTER_NAMES_GENERATE_PROMPT, EPISODE_NAMES_GENERATE_PROMPT,
                        MOVIE_SCENE_NAMES_PROMPT
                    )

                    if content_type == "series_script":
                        # 剧集使用分集标题提示词
                        prompt = EPISODE_NAMES_GENERATE_PROMPT.format(
                            series_type=project.script_config.get(
                                "series_type", "电视剧") if project.script_config else "电视剧",
                            total_episodes=request.total_chapters,
                            genre=project.genre or "",
                            outline_content=project.outline_content[:
                                                                    6000] if project.outline_content else ""
                        )
                    elif content_type == "movie_script":
                        # 电影使用场景标题提示词
                        movie_config = project.movie_script_config or {}
                        prompt = MOVIE_SCENE_NAMES_PROMPT.format(
                            movie_type=movie_config.get("movie_type", "院线电影"),
                            total_scenes=request.total_chapters,
                            total_duration=movie_config.get(
                                "total_duration", 90),
                            genre=project.genre or "",
                            outline_content=project.outline_content[:
                                                                    6000] if project.outline_content else ""
                        )
                    else:
                        # 小说使用章节标题提示词
                        project_type_label = "小说"
                        prompt = CHAPTER_NAMES_GENERATE_PROMPT.format(
                            project_type=project_type_label,
                            unit_label=unit_label,
                            total_units=request.total_chapters,
                            genre=project.genre or "",
                            target_platform=project.target_platform or "",
                            outline_content=project.outline_content[:
                                                                    6000] if project.outline_content else ""
                        )

                    # 调用LLM生成标题
                    llm_response = await llm_provider.generate(prompt, temperature=0.7, max_tokens=4096)

                    response_content = llm_response.content if hasattr(
                        llm_response, 'content') else str(llm_response)

                    # 解析JSON响应
                    import re
                    json_match = re.search(
                        r'```json\s*([\s\S]*?)\s*```', response_content)
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        json_str = response_content

                    try:
                        names_data = json.loads(json_str)

                        # 更新章节标题
                        for item in names_data:
                            num = item.get("number") or item.get(
                                "episode") or item.get("scene_number")
                            title = item.get("title", "")
                            if num and title:
                                for chapter in chapters_to_create:
                                    if chapter.chapter_number == num:
                                        chapter.chapter_title = title
                                        break

                        await db.commit()
                        logger.info(
                            f"章节名称预生成成功: {project.title}, 共{len(names_data)}个")

                    except json.JSONDecodeError as e:
                        logger.warning(f"解析LLM响应失败: {str(e)}，使用默认标题")

            except Exception as e:
                logger.warning(f"章节名称预生成失败: {str(e)}，使用默认标题")

        # 更新项目状态
        project.status = ProjectStatus.GENERATING
        await db.commit()

        logger.info(f"章节目录生成成功: {project.title}, 共{request.total_chapters}章")

        # 返回创建的章节列表
        chapters_data = [
            ChapterMetadata(
                chapter_number=c.chapter_number,
                chapter_title=c.chapter_title,
                chapter_role=None,
                chapter_purpose=None,
                suspense_level=None,
                foreshadowing=None,
                plot_twist_level=None,
                chapter_summary=None
            )
            for c in chapters_to_create
        ]

        return ResponseModel(
            success=True,
            data=DirectoryResponse(
                project_id=project.id,
                total_chapters=project.total_chapters,
                chapters=chapters_data
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成目录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/directory", response_model=ResponseModel[DirectoryResponse])
async def get_directory(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取章节目录
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取章节列表
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id
        ).order_by(NovelChapter.chapter_number)

        result = await db.execute(query)
        chapters = result.scalars().all()

        chapters_data = [
            ChapterMetadata(
                chapter_number=c.chapter_number,
                chapter_title=c.chapter_title,
                chapter_role=c.chapter_metadata.get(
                    "chapter_role") if c.chapter_metadata else None,
                chapter_purpose=c.chapter_metadata.get(
                    "chapter_purpose") if c.chapter_metadata else None,
                suspense_level=c.chapter_metadata.get(
                    "suspense_level") if c.chapter_metadata else None,
                foreshadowing=c.chapter_metadata.get(
                    "foreshadowing") if c.chapter_metadata else None,
                plot_twist_level=c.chapter_metadata.get(
                    "plot_twist_level") if c.chapter_metadata else None,
                chapter_summary=c.chapter_metadata.get(
                    "chapter_summary") if c.chapter_metadata else None
            )
            for c in chapters
        ]

        return ResponseModel(
            success=True,
            data=DirectoryResponse(
                project_id=project.id,
                total_chapters=project.total_chapters,
                chapters=chapters_data
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取目录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/regenerate-chapter-names")
async def regenerate_chapter_names(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    重新生成章节名称

    所有类型都采用从详细大纲提取标题的方案：
    - 剧集类型：从 episode_outlines 获取 episode_title
    - 电影类型：从 scene_outlines 获取 scene_title
    - 小说类型：从 chapter_outlines 获取 chapter_title
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        if not project.outline_content:
            raise HTTPException(status_code=400, detail="请先上传大纲文件")

        # 获取现有章节
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id
        ).order_by(NovelChapter.chapter_number)
        chapter_result = await db.execute(chapter_query)
        chapters = list(chapter_result.scalars().all())

        if not chapters:
            raise HTTPException(status_code=400, detail="请先生成章节目录")

        total_chapters = len(chapters)

        # 获取内容类型
        content_type = getattr(project, 'content_type', 'novel')

        # ==================== 剧集类型：从 episode_outlines 获取标题 ====================
        if content_type in ("series_script", "script"):
            episode_outlines = project.episode_outlines or {}
            updated_count = 0

            for chapter in chapters:
                # 获取该场景所属的集数和场景号
                episode_num = chapter.episode_number
                scene_num = chapter.scene_number

                if not episode_num:
                    # 如果没有 episode_number，跳过或使用默认逻辑
                    continue

                # 从分集大纲获取集标题
                ep_outline = episode_outlines.get(str(episode_num), {})
                episode_title = ep_outline.get('episode_title', '')

                # 生成场景标题：第X集 第Y场 集标题
                if episode_title:
                    new_title = f"第{episode_num}集 第{scene_num}场 {episode_title}"
                else:
                    new_title = f"第{episode_num}集 第{scene_num}场"

                if chapter.chapter_title != new_title:
                    chapter.chapter_title = new_title
                    updated_count += 1
                    logger.info(f"[场景标题] {new_title}")

            await db.commit()
            logger.info(f"分集标题从大纲同步完成: {project.title}, 更新{updated_count}个")

            # 返回更新后的章节列表
            chapters_data = [
                {
                    "chapter_number": c.chapter_number,
                    "chapter_title": c.chapter_title,
                    "episode_number": c.episode_number,
                    "scene_number": c.scene_number
                }
                for c in chapters
            ]

            return ResponseModel(
                success=True,
                data={
                    "updated_count": updated_count,
                    "chapters": chapters_data,
                    "source": "episode_outlines"  # 标识标题来源
                }
            )

        # ==================== 电影类型：从 scene_outlines 获取标题 ====================
        if content_type == "movie_script":
            scene_outlines = project.scene_outlines or {}
            updated_count = 0

            for chapter in chapters:
                scene_num = chapter.chapter_number  # 电影类型的 chapter_number 对应场景号

                # 从场景大纲获取场景标题
                scene_outline = scene_outlines.get(str(scene_num), {})
                scene_title = scene_outline.get('scene_title', '')

                # 生成场景标题：第X场 场景标题
                if scene_title:
                    new_title = f"第{scene_num}场 {scene_title}"
                else:
                    new_title = f"第{scene_num}场"

                if chapter.chapter_title != new_title:
                    chapter.chapter_title = new_title
                    updated_count += 1
                    logger.info(f"[场景标题] {new_title}")

            await db.commit()
            logger.info(f"场景标题从大纲同步完成: {project.title}, 更新{updated_count}个")

            # 返回更新后的章节列表
            chapters_data = [
                {
                    "chapter_number": c.chapter_number,
                    "chapter_title": c.chapter_title
                }
                for c in chapters
            ]

            return ResponseModel(
                success=True,
                data={
                    "updated_count": updated_count,
                    "chapters": chapters_data,
                    "source": "scene_outlines"  # 标识标题来源
                }
            )

        # ==================== 小说类型：从 chapter_outlines 获取标题 ====================
        if content_type == "novel":
            chapter_outlines = project.chapter_outlines or {}
            updated_count = 0

            for chapter in chapters:
                chapter_num = chapter.chapter_number

                # 从章节大纲获取章节标题
                ch_outline = chapter_outlines.get(str(chapter_num), {})
                chapter_title = ch_outline.get('chapter_title', '')

                # 生成章节标题：第X章 章节标题
                if chapter_title:
                    new_title = f"第{chapter_num}章 {chapter_title}"
                else:
                    new_title = f"第{chapter_num}章"

                if chapter.chapter_title != new_title:
                    chapter.chapter_title = new_title
                    updated_count += 1
                    logger.info(f"[章节标题] {new_title}")

            await db.commit()
            logger.info(f"章节标题从大纲同步完成: {project.title}, 更新{updated_count}个")

            # 返回更新后的章节列表
            chapters_data = [
                {
                    "chapter_number": c.chapter_number,
                    "chapter_title": c.chapter_title
                }
                for c in chapters
            ]

            return ResponseModel(
                success=True,
                data={
                    "updated_count": updated_count,
                    "chapters": chapters_data,
                    "source": "chapter_outlines"  # 标识标题来源
                }
            )

        # ==================== 其他类型：返回错误 ====================
        raise HTTPException(
            status_code=400, detail=f"不支持的内容类型: {content_type}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新生成章节名称失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/chapters/{chapter_num}/title")
async def update_chapter_title(
    project_id: int,
    chapter_num: int,
    title: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新单个章节标题

    用户可以手动编辑章节名称
    """
    try:
        # 获取章节
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number == chapter_num
        )
        result = await db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            raise HTTPException(status_code=404, detail="章节不存在")

        # 验证用户权限
        project_query = select(NovelProject).where(
            NovelProject.id == project_id)
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()

        if not project or project.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此章节")

        # 更新标题
        chapter.chapter_title = title
        await db.commit()

        logger.info(f"章节标题更新: 第{chapter_num}章 -> {title}")

        return ResponseModel(
            success=True,
            message="章节标题已更新"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新章节标题失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 章节生成 API ====================

@router.post("/projects/{project_id}/generate-chapter/{chapter_num}", response_model=ResponseModel[ChapterGenerateResponse])
async def generate_chapter(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成指定章节
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        if chapter_num < 1 or chapter_num > project.total_chapters:
            raise HTTPException(
                status_code=400, detail=f"章节号无效，应在1-{project.total_chapters}之间")

        # 调试日志：检查大纲状态
        logger.info(
            f"[章节生成API] 项目: {project.title}, 大纲状态: outline_content={bool(project.outline_content)}, 长度={len(project.outline_content) if project.outline_content else 0}")

        # 生成章节
        generator = NovelChapterGenerator(db)
        result = await generator.generate_chapter(project, chapter_num)

        return ResponseModel(
            success=result["success"],
            data=ChapterGenerateResponse(
                project_id=project_id,
                chapter_number=chapter_num,
                chapter_title=None,
                status=ChapterStatus.COMPLETED if result["success"] else ChapterStatus.FAILED,
                content=result.get("content"),
                word_count=result.get("word_count", 0),
                token_count=result.get("token_count", 0),
                duration_ms=result.get("duration_ms", 0),
                error_message=result.get("error_message")
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成章节失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/generate-all", response_model=ResponseModel[BatchGenerateResponse])
async def generate_all_chapters(
    project_id: int,
    request: BatchGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量生成章节
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 调试日志：检查大纲状态
        logger.info(
            f"[批量生成API] 项目: {project.title}, 大纲状态: outline_content={bool(project.outline_content)}, 长度={len(project.outline_content) if project.outline_content else 0}")

        # 生成章节
        generator = NovelChapterGenerator(db)
        result = await generator.generate_all_chapters(
            project,
            start_chapter=request.start_chapter,
            stop_on_error=request.stop_on_error
        )

        return ResponseModel(success=True, data=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 章节内容 API ====================

@router.get("/projects/{project_id}/chapters", response_model=ResponseModel[ChapterListResponse])
async def list_chapters(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取章节列表
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取章节列表
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id
        ).order_by(NovelChapter.chapter_number)

        result = await db.execute(query)
        chapters = result.scalars().all()

        chapters_data = [c.to_summary_dict() for c in chapters]

        return ResponseModel(
            success=True,
            data=ChapterListResponse(
                project_id=project.id,
                total_chapters=project.total_chapters,
                completed_chapters=project.completed_chapters,
                chapters=chapters_data
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取章节列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/chapters/{chapter_num}", response_model=ResponseModel[ChapterContentResponse])
async def get_chapter(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取章节内容
    """
    try:
        # 获取章节
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number == chapter_num
        )
        result = await db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            raise HTTPException(status_code=404, detail="章节不存在")

        # 验证用户权限
        project_query = select(NovelProject).where(
            NovelProject.id == project_id)
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()

        if not project or project.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此章节")

        return ResponseModel(
            success=True,
            data=ChapterContentResponse(
                id=chapter.id,
                project_id=chapter.project_id,
                chapter_number=chapter.chapter_number,
                chapter_title=chapter.chapter_title,
                chapter_metadata=chapter.chapter_metadata,
                status=chapter.status,
                draft_content=chapter.draft_content,  # 返回原始草稿
                final_content=chapter.final_content,
                word_count=chapter.word_count,
                token_count=chapter.token_count,
                created_at=chapter.created_at,
                updated_at=chapter.updated_at
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取章节内容失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/chapters/{chapter_num}")
async def update_chapter(
    project_id: int,
    chapter_num: int,
    request: ChapterContentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新章节内容
    """
    try:
        # 获取章节
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number == chapter_num
        )
        result = await db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            raise HTTPException(status_code=404, detail="章节不存在")

        # 更新内容
        chapter.final_content = request.content
        chapter.word_count = len(request.content)
        chapter.user_edited = 1

        await db.commit()

        logger.info(f"章节内容更新: 第{chapter_num}章")

        return ResponseModel(success=True, message="章节内容已更新")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新章节失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 导出 API ====================

@router.post("/projects/{project_id}/export")
async def export_project(
    project_id: int,
    request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    导出项目
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取章节
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id
        ).order_by(NovelChapter.chapter_number)

        result = await db.execute(query)
        chapters = list(result.scalars().all())

        # 导出
        exporter = NovelExporter()
        export_result = await exporter.export_project(
            project=project,
            chapters=chapters,
            format=request.format,
            include_metadata=request.include_metadata,
            chapter_range=request.chapter_range
        )

        if not export_result["success"]:
            raise HTTPException(
                status_code=500, detail=export_result.get("error_message", "导出失败"))

        # 返回文件
        return FileResponse(
            path=export_result["file_path"],
            filename=export_result["file_name"],
            media_type="application/octet-stream"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 进度 API ====================

@router.get("/projects/{project_id}/progress", response_model=ResponseModel[GenerationProgress])
async def get_progress(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取生成进度
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取当前章节状态
        current_chapter_status = None
        if project.current_chapter > 0:
            chapter_query = select(NovelChapter).where(
                NovelChapter.project_id == project_id,
                NovelChapter.chapter_number == project.current_chapter
            )
            chapter_result = await db.execute(chapter_query)
            current_chapter = chapter_result.scalar_one_or_none()
            if current_chapter:
                current_chapter_status = current_chapter.status

        # 计算预计剩余时间
        estimated_time = None
        if project.completed_chapters > 0 and project.total_duration_ms > 0:
            avg_time_per_chapter = project.total_duration_ms / project.completed_chapters
            remaining_chapters = project.total_chapters - project.completed_chapters
            estimated_time = int(avg_time_per_chapter *
                                 remaining_chapters / 1000)

        return ResponseModel(
            success=True,
            data=GenerationProgress(
                project_id=project.id,
                status=project.status,
                total_chapters=project.total_chapters,
                completed_chapters=project.completed_chapters,
                current_chapter=project.current_chapter,
                progress_percentage=project.get_progress_percentage(),
                current_chapter_status=current_chapter_status,
                estimated_remaining_time=estimated_time,
                error_message=project.error_message
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取进度失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 剧本专用 API ====================

@router.post("/projects/{project_id}/generate-script-directory", response_model=ResponseModel[ScriptDirectoryResponse])
async def generate_script_directory(
    project_id: int,
    request: ScriptDirectoryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成剧本分集分场目录
    场景数可由用户指定或AI根据时长自动估算
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        if not project.outline_content:
            raise HTTPException(status_code=400, detail="请先上传大纲文件")

        if project.project_type != ProjectType.SCRIPT:
            raise HTTPException(status_code=400, detail="此接口仅适用于剧本项目")

        # 获取剧本配置
        script_config = project.script_config or {}

        # 获取时长区间配置（优先使用请求中的配置，其次使用项目配置）
        duration_range = request.episode_duration_range or script_config.get(
            "episode_duration_range", [30, 45])

        # 获取场景数范围配置
        scenes_range = request.scenes_per_episode_range or script_config.get(
            "scenes_per_episode_range")

        # 获取格式标准和对白比例
        format_standard = request.format_standard or script_config.get(
            "format_standard", "标准格式")
        dialogue_ratio = request.dialogue_narration_ratio or script_config.get(
            "dialogue_narration_ratio", "均衡")

        # AI自动估算场景数（基于时长区间，每3-5分钟一个场景）
        avg_duration = sum(duration_range) / 2

        # 如果用户指定了场景数范围，使用用户指定的
        if scenes_range and len(scenes_range) == 2:
            estimated_scenes_per_episode = (
                scenes_range[0] + scenes_range[1]) // 2
            scenes_info = f"{scenes_range[0]}-{scenes_range[1]}场/集（用户指定）"
        else:
            # AI自动估算
            estimated_scenes_per_episode = int(avg_duration / 4)  # 平均每4分钟一个场景
            estimated_scenes_per_episode = max(
                5, min(30, estimated_scenes_per_episode))
            scenes_info = f"{estimated_scenes_per_episode}场/集（AI自动估算）"

        # 更新项目配置
        project.script_config = {
            **script_config,
            "series_type": script_config.get("series_type", "电视剧"),
            "episode_count": request.total_episodes,
            "scenes_per_episode": estimated_scenes_per_episode,
            "episode_duration_range": duration_range,
            "scenes_per_episode_range": scenes_range,
            "format_standard": format_standard,
            "dialogue_narration_ratio": dialogue_ratio,
            "auto_designed_scenes": scenes_range is None  # 标记是否为AI自动设计
        }
        project.total_chapters = request.total_episodes * estimated_scenes_per_episode
        project.status = ProjectStatus.DIRECTORY
        await db.commit()

        # 创建章节/场景记录
        chapter_num = 1
        for ep in range(1, request.total_episodes + 1):
            for sc in range(1, estimated_scenes_per_episode + 1):
                chapter = NovelChapter(
                    project_id=project.id,
                    chapter_number=chapter_num,
                    chapter_title=f"第{ep}集 第{sc}场",
                    episode_number=ep,
                    scene_number=sc,
                    status=ChapterStatus.PENDING
                )
                db.add(chapter)
                chapter_num += 1

        await db.commit()
        project.status = ProjectStatus.GENERATING
        await db.commit()

        logger.info(
            f"剧本目录生成成功: {project.title}, 共{request.total_episodes}集{project.total_chapters}场, 场景配置: {scenes_info}")

        # 构建响应
        episodes = []
        for ep in range(1, request.total_episodes + 1):
            episodes.append(EpisodeDirectory(
                episode_number=ep,
                episode_title=f"第{ep}集",
                episode_summary="待生成",
                scenes=[]
            ))

        return ResponseModel(
            success=True,
            data=ScriptDirectoryResponse(
                project_id=project.id,
                total_episodes=request.total_episodes,
                episodes=episodes
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成剧本目录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/generate-scene/{episode}/{scene}", response_model=ResponseModel[SceneGenerateResponse])
async def generate_scene(
    project_id: int,
    episode: int,
    scene: int,
    request: Optional[SceneGenerateRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成单个剧本场景
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 查找章节
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.episode_number == episode,
            NovelChapter.scene_number == scene
        )
        chapter_result = await db.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        if not chapter:
            raise HTTPException(status_code=404, detail="场景不存在")

        # 更新场景元数据
        if request and request.scene_metadata:
            chapter.chapter_metadata = {
                "scene_metadata": request.scene_metadata.model_dump()
            }
            if request.scene_purpose:
                chapter.chapter_metadata["chapter_summary"] = request.scene_purpose

        await db.commit()

        # 使用生成器生成场景
        generator = NovelChapterGenerator(db)
        gen_result = await generator.generate_chapter(project, chapter.chapter_number)

        return ResponseModel(
            success=gen_result["success"],
            data=SceneGenerateResponse(
                project_id=project_id,
                episode_number=episode,
                scene_number=scene,
                scene_title=chapter.chapter_title,
                status=ChapterStatus.COMPLETED if gen_result["success"] else ChapterStatus.FAILED,
                content=gen_result.get("content"),
                word_count=gen_result.get("word_count", 0),
                duration_ms=gen_result.get("duration_ms", 0),
                error_message=gen_result.get("error_message")
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成场景失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/scenes", response_model=ResponseModel[ChapterListResponse])
async def list_scenes(
    project_id: int,
    episode: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取剧本场景列表
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取场景列表
        query = select(NovelChapter).where(
            NovelChapter.project_id == project_id
        )
        if episode:
            query = query.where(NovelChapter.episode_number == episode)

        query = query.order_by(NovelChapter.episode_number,
                               NovelChapter.scene_number)

        result = await db.execute(query)
        chapters = result.scalars().all()

        scenes_data = []
        for c in chapters:
            scene_dict = c.to_summary_dict()
            scene_dict["episode_number"] = c.episode_number
            scene_dict["scene_number"] = c.scene_number
            scenes_data.append(scene_dict)

        return ResponseModel(
            success=True,
            data=ChapterListResponse(
                project_id=project.id,
                total_chapters=project.total_chapters,
                completed_chapters=project.completed_chapters,
                chapters=scenes_data
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取场景列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/characters", response_model=ResponseModel[CharacterListResponse])
async def list_characters(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取剧本角色列表（从已完成章节中提取）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 从角色状态文件中读取角色信息
        characters = []
        total_dialogues = 0

        if project.characters_file and os.path.exists(project.characters_file):
            try:
                with open(project.characters_file, 'r', encoding='utf-8') as f:
                    character_state = json.load(f)
                    for name, info in character_state.items():
                        char_info = CharacterInfo(
                            character_name=name,
                            character_type="配角",  # 默认
                            first_appearance=None,
                            character_description=str(info.get("状态", "")),
                            dialogue_count=0
                        )
                        characters.append(char_info)
            except Exception as e:
                logger.warning(f"读取角色状态文件失败: {str(e)}")

        return ResponseModel(
            success=True,
            data=CharacterListResponse(
                project_id=project.id,
                characters=characters,
                total_dialogues=total_dialogues
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取角色列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/generate-episode/{episode}")
async def generate_episode(
    project_id: int,
    episode: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成整集剧本
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取该集所有场景
        scene_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.episode_number == episode
        ).order_by(NovelChapter.scene_number)

        scene_result = await db.execute(scene_query)
        scenes = scene_result.scalars().all()

        if not scenes:
            raise HTTPException(status_code=404, detail=f"第{episode}集没有场景")

        # 逐场生成
        generator = NovelChapterGenerator(db)
        results = {
            "episode_number": episode,
            "total_scenes": len(scenes),
            "completed_count": 0,
            "failed_count": 0,
            "scenes": []
        }

        for scene in scenes:
            gen_result = await generator.generate_chapter(project, scene.chapter_number)

            results["scenes"].append({
                "scene_number": scene.scene_number,
                "success": gen_result["success"],
                "word_count": gen_result.get("word_count", 0)
            })

            if gen_result["success"]:
                results["completed_count"] += 1
            else:
                results["failed_count"] += 1

        return ResponseModel(
            success=True,
            data=results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成整集失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 分集详细大纲 API ====================

@router.post("/projects/{project_id}/generate-episode-outline/{episode}")
async def generate_episode_outline(
    project_id: int,
    episode: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成单集详细大纲

    基于基础大纲中的分集概要，生成该集的详细大纲。
    详细大纲包含：剧情展开、场景规划、关键对话等。
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 检查项目类型
        content_type = getattr(project, 'content_type', None)
        if content_type not in ('series_script', 'script') and project.project_type != ProjectType.SCRIPT:
            raise HTTPException(status_code=400, detail="此接口仅适用于剧本项目")

        # 检查基础大纲
        if not project.outline_content:
            raise HTTPException(status_code=400, detail="请先上传基础大纲")

        # 调用生成器生成分集详细大纲
        generator = NovelChapterGenerator(db)
        gen_result = await generator.generate_episode_outline(project, episode)

        if not gen_result["success"]:
            raise HTTPException(
                status_code=500, detail=gen_result.get("error_message", "生成失败"))

        logger.info(f"第{episode}集详细大纲生成成功: {project.title}")

        return ResponseModel(
            success=True,
            data={
                "episode_number": episode,
                "content": gen_result.get("content"),
                "parsed": gen_result.get("parsed"),
                "duration_ms": gen_result.get("duration_ms", 0)
            }
        )

    except asyncio.CancelledError:
        # 请求被取消（客户端断开连接或超时）
        logger.warning(f"第{episode}集详细大纲生成被取消: project_id={project_id}")
        # 确保数据库事务回滚
        await db.rollback()
        raise HTTPException(status_code=499, detail="请求被取消")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成分集大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/generate-all-episode-outlines")
async def generate_all_episode_outlines(
    project_id: int,
    request: EpisodeOutlineGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量生成多集详细大纲

    可指定要生成的集数列表，或生成全部集数的详细大纲。
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 检查项目类型
        content_type = getattr(project, 'content_type', None)
        if content_type not in ('series_script', 'script') and project.project_type != ProjectType.SCRIPT:
            raise HTTPException(status_code=400, detail="此接口仅适用于剧本项目")

        # 检查基础大纲
        if not project.outline_content:
            raise HTTPException(status_code=400, detail="请先上传基础大纲")

        # 创建内存取消令牌（用于即时取消，不依赖 Redis）
        cancel_event = set_cancel_token(project_id)

        try:
            # 调用生成器批量生成
            generator = NovelChapterGenerator(db)
            gen_result = await generator.generate_all_episode_outlines(
                project,
                episode_numbers=request.episode_numbers,
                stop_on_error=request.stop_on_error
            )

            logger.info(
                f"批量生成分集大纲完成: {project.title}, 成功{gen_result['completed_count']}集")

            return ResponseModel(
                success=True,
                data=gen_result
            )
        finally:
            # 清理取消令牌
            clear_cancel_token(project_id)

    except asyncio.CancelledError:
        # 请求被取消（客户端断开连接或超时）
        logger.warning(f"批量生成分集大纲被取消: project_id={project_id}")
        clear_cancel_token(project_id)  # 清理取消令牌
        await db.rollback()
        raise HTTPException(status_code=499, detail="请求被取消")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量生成分集大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/episode-outlines", response_model=ResponseModel[EpisodeOutlineListResponse])
async def get_episode_outlines(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取所有分集详细大纲

    返回项目下所有已生成的分集详细大纲列表，供用户查看和管理。
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取分集大纲
        episode_outlines = project.episode_outlines or {}

        # 获取总集数
        script_config = project.series_script_config or project.script_config or {}
        total_episodes = script_config.get("episode_count", 0)

        # 如果没有配置总集数，尝试从大纲中提取
        if total_episodes == 0 and project.outline_content:
            total_episodes = extract_chapter_count(
                project.outline_content, "series_script")

        # 构建响应列表
        episodes = []
        generated_count = 0

        for ep_num in range(1, total_episodes + 1):
            ep_outline = episode_outlines.get(str(ep_num), {})
            if ep_outline:
                generated_count += 1
                episodes.append(EpisodeOutlineResponse(
                    episode_number=ep_outline.get("episode_number", ep_num),
                    episode_title=ep_outline.get("episode_title"),
                    episode_summary=ep_outline.get("episode_summary"),
                    detailed_outline=ep_outline.get("detailed_outline", ""),
                    estimated_duration=ep_outline.get("estimated_duration"),
                    scenes=[EpisodeOutlineScene(
                        **s) for s in ep_outline.get("scenes", [])] if ep_outline.get("scenes") else None,
                    core_conflict=ep_outline.get("core_conflict"),
                    emotional_curve=ep_outline.get("emotional_curve"),
                    key_dialogues=ep_outline.get("key_dialogues"),
                    visual_highlights=ep_outline.get("visual_highlights"),
                    status=ep_outline.get("status", "generated"),
                    content_status=ep_outline.get("content_status"),
                    content_word_count=ep_outline.get("content_word_count"),
                    created_at=ep_outline.get("created_at"),
                    updated_at=ep_outline.get("updated_at")
                ))
            else:
                # 未生成的大纲
                episodes.append(EpisodeOutlineResponse(
                    episode_number=ep_num,
                    episode_title=f"第{ep_num}集",
                    episode_summary=None,
                    detailed_outline="",
                    status="pending"
                ))

        return ResponseModel(
            success=True,
            data=EpisodeOutlineListResponse(
                project_id=project.id,
                total_episodes=total_episodes,
                generated_count=generated_count,
                episodes=episodes
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分集大纲列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/episode-outlines/{episode}", response_model=ResponseModel[EpisodeOutlineResponse])
async def get_episode_outline(
    project_id: int,
    episode: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取单个分集详细大纲
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取分集大纲
        episode_outlines = project.episode_outlines or {}
        ep_outline = episode_outlines.get(str(episode))

        if not ep_outline:
            raise HTTPException(
                status_code=404, detail=f"第{episode}集的详细大纲尚未生成")

        return ResponseModel(
            success=True,
            data=EpisodeOutlineResponse(
                episode_number=ep_outline.get("episode_number", episode),
                episode_title=ep_outline.get("episode_title"),
                episode_summary=ep_outline.get("episode_summary"),
                detailed_outline=ep_outline.get("detailed_outline", ""),
                estimated_duration=ep_outline.get("estimated_duration"),
                scenes=[EpisodeOutlineScene(
                    **s) for s in ep_outline.get("scenes", [])] if ep_outline.get("scenes") else None,
                core_conflict=ep_outline.get("core_conflict"),
                emotional_curve=ep_outline.get("emotional_curve"),
                key_dialogues=ep_outline.get("key_dialogues"),
                visual_highlights=ep_outline.get("visual_highlights"),
                status=ep_outline.get("status", "generated"),
                created_at=ep_outline.get("created_at"),
                updated_at=ep_outline.get("updated_at")
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分集大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/episode-outlines/{episode}")
async def update_episode_outline(
    project_id: int,
    episode: int,
    request: EpisodeOutlineUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新分集详细大纲

    用户可以手动编辑已生成的详细大纲，修改后的状态将标记为"edited"。
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取现有大纲
        episode_outlines = project.episode_outlines or {}
        ep_outline = episode_outlines.get(str(episode), {})

        if not ep_outline:
            # 如果不存在，创建新的
            ep_outline = {
                "episode_number": episode,
                "episode_title": f"第{episode}集",
                "episode_summary": "",
                "detailed_outline": "",
                "status": "pending"
            }

        # 更新字段
        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                if key == "scenes" and value:
                    ep_outline[key] = [s.model_dump() if hasattr(
                        s, 'model_dump') else s for s in value]
                else:
                    ep_outline[key] = value

        # 更新状态和时间
        ep_outline["status"] = "edited"
        ep_outline["updated_at"] = datetime.now().isoformat()

        # 保存
        if not project.episode_outlines:
            project.episode_outlines = {}

        # 创建新字典触发 SQLAlchemy 变更检测
        updated_outlines = dict(project.episode_outlines)
        updated_outlines[str(episode)] = ep_outline
        project.episode_outlines = updated_outlines

        # 标记字段已修改（确保 JSON 字段变更被检测）
        flag_modified(project, 'episode_outlines')

        await db.commit()
        await db.refresh(project)

        logger.info(f"第{episode}集详细大纲已更新: {project.title}")

        return ResponseModel(
            success=True,
            data=EpisodeOutlineResponse(
                episode_number=ep_outline.get("episode_number", episode),
                episode_title=ep_outline.get("episode_title"),
                episode_summary=ep_outline.get("episode_summary"),
                detailed_outline=ep_outline.get("detailed_outline", ""),
                estimated_duration=ep_outline.get("estimated_duration"),
                scenes=[EpisodeOutlineScene(
                    **s) for s in ep_outline.get("scenes", [])] if ep_outline.get("scenes") else None,
                core_conflict=ep_outline.get("core_conflict"),
                emotional_curve=ep_outline.get("emotional_curve"),
                key_dialogues=ep_outline.get("key_dialogues"),
                visual_highlights=ep_outline.get("visual_highlights"),
                status=ep_outline.get("status", "edited"),
                created_at=ep_outline.get("created_at"),
                updated_at=ep_outline.get("updated_at")
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新分集大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/episode-outlines/{episode}")
async def delete_episode_outline(
    project_id: int,
    episode: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除分集详细大纲

    删除后可以重新生成。
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 删除大纲
        episode_outlines = project.episode_outlines or {}
        if str(episode) in episode_outlines:
            del episode_outlines[str(episode)]
            project.episode_outlines = episode_outlines
            await db.commit()
            logger.info(f"第{episode}集详细大纲已删除: {project.title}")
            return ResponseModel(success=True, message=f"第{episode}集详细大纲已删除")
        else:
            raise HTTPException(status_code=404, detail=f"第{episode}集的详细大纲不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除分集大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 单集正文生成 API ====================

@router.post("/projects/{project_id}/generate-episode-content/{episode}")
async def generate_episode_content_endpoint(
    project_id: int,
    episode: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成单集正文（完整单集，包含所有场景）

    这是连续剧剧本的专用接口，用于生成单集完整正文。

    前置条件：
    1. 项目类型必须是 series_script 或 script
    2. 该集必须有详细大纲（episode_outlines）

    与旧版场景生成模式的区别：
    - 旧版：一集拆分为多个场景，每个场景生成一条记录
    - 新版：一集生成一条完整的正文记录，场景作为正文内部结构
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 检查项目类型
        content_type = getattr(project, 'content_type', None)
        if content_type not in ('series_script', 'script') and project.project_type != ProjectType.SCRIPT:
            raise HTTPException(status_code=400, detail="此接口仅适用于连续剧剧本项目")

        # 检查该集是否有详细大纲
        episode_outlines = project.episode_outlines or {}
        episode_outline = episode_outlines.get(str(episode))

        if not episode_outline:
            raise HTTPException(
                status_code=400,
                detail=f"第{episode}集的详细大纲未生成，请先生成分集详细大纲"
            )

        logger.info(f"[单集正文生成] 开始生成第{episode}集正文: {project.title}")

        # 调用生成器生成单集正文
        generator = NovelChapterGenerator(db)
        gen_result = await generator.generate_episode_content(project, episode)

        if not gen_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=gen_result.get("error_message", "生成失败")
            )

        # 获取生成的章节记录
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.episode_number == episode
        )
        chapter_result = await db.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        logger.info(
            f"[单集正文生成] 第{episode}集正文生成成功: {project.title}, 字数: {gen_result.get('word_count', 0)}")

        return ResponseModel(
            success=True,
            data={
                "episode_number": episode,
                "chapter_number": chapter.chapter_number if chapter else episode,
                "chapter_title": chapter.chapter_title if chapter else f"第{episode}集",
                "content": gen_result.get("content"),
                "word_count": gen_result.get("word_count", 0),
                "token_count": gen_result.get("token_count", 0),
                "duration_ms": gen_result.get("duration_ms", 0),
                "chapter": {
                    "id": chapter.id if chapter else None,
                    "chapter_number": chapter.chapter_number if chapter else episode,
                    "chapter_title": chapter.chapter_title if chapter else f"第{episode}集",
                    "episode_number": chapter.episode_number if chapter else episode,
                    "status": chapter.status if chapter else "completed",
                    "word_count": chapter.word_count if chapter else gen_result.get("word_count", 0)
                } if chapter else None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成单集正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 章节详细大纲 API（小说专用） ====================

@router.post("/projects/{project_id}/generate-chapter-outline/{chapter_num}")
async def generate_chapter_outline(
    project_id: int,
    chapter_num: int,
    force_regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成单章详细大纲（小说专用）

    基于基础大纲中的章节概要，生成该章的详细大纲。

    Args:
        project_id: 项目ID
        chapter_num: 章节号
        force_regenerate: 是否强制重新生成（即使已存在详细大纲）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 检查项目类型
        content_type = getattr(project, 'content_type', None)
        if content_type != 'novel':
            raise HTTPException(status_code=400, detail="此接口仅适用于小说项目")

        # 检查大纲数据（支持两阶段大纲：基础大纲、全局大纲或单元概述）
        has_outline = bool(project.outline_content)
        has_global_outline = bool(
            getattr(project, 'global_outline_content', None))
        unit_summaries = getattr(project, 'unit_summaries', None) or {}
        has_unit_summaries = bool(unit_summaries)

        # 调试日志：记录单元概述状态
        logger.info(
            f"[单章大纲API] project_id={project_id}, chapter_num={chapter_num}, "
            f"has_outline={has_outline}, has_global_outline={has_global_outline}, "
            f"has_unit_summaries={has_unit_summaries}, unit_summaries_count={len(unit_summaries)}"
        )

        # 检查目标章节是否在 unit_summaries 中
        if unit_summaries and str(chapter_num) in unit_summaries:
            unit_data = unit_summaries[str(chapter_num)]
            logger.info(
                f"[单章大纲API] 第{chapter_num}章在unit_summaries中找到: "
                f"title={unit_data.get('title', 'N/A')}, summary_len={len(unit_data.get('summary', ''))}"
            )
        elif unit_summaries:
            logger.warning(
                f"[单章大纲API] 第{chapter_num}章不在unit_summaries中，可用keys: {list(unit_summaries.keys())[:5]}..."
            )

        if not has_outline and not has_global_outline and not has_unit_summaries:
            raise HTTPException(
                status_code=400, detail="请先上传基础大纲、生成全局大纲或上传单元概述")

        # 调用生成器生成章节详细大纲
        generator = NovelChapterGenerator(db)
        gen_result = await generator.generate_chapter_outline(project, chapter_num, force_regenerate=force_regenerate)

        if not gen_result["success"]:
            raise HTTPException(
                status_code=500, detail=gen_result.get("error_message", "生成失败"))

        # 处理跳过的情况
        if gen_result.get("skipped"):
            logger.info(f"第{chapter_num}章已存在详细大纲，跳过生成: {project.title}")
            return ResponseModel(
                success=True,
                data={
                    "chapter_number": chapter_num,
                    "content": gen_result.get("content"),
                    "parsed": gen_result.get("parsed"),
                    "skipped": True,
                    "message": gen_result.get("message", "已存在详细大纲，跳过生成")
                }
            )

        logger.info(f"第{chapter_num}章详细大纲生成成功: {project.title}")

        return ResponseModel(
            success=True,
            data={
                "chapter_number": chapter_num,
                "content": gen_result.get("content"),
                "parsed": gen_result.get("parsed"),
                "duration_ms": gen_result.get("duration_ms", 0)
            }
        )

    except asyncio.CancelledError:
        logger.warning(f"第{chapter_num}章详细大纲生成被取消: project_id={project_id}")
        await db.rollback()
        raise HTTPException(status_code=499, detail="请求被取消")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成章节大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 用户干预机制 API ====================

class OutlineInterventionRequest(BaseModel):
    """详细大纲生成干预请求"""
    content_type: str = Field(
        default="novel", description="内容类型: novel/series_script/movie_script")
    user_choice: Optional[str] = Field(
        default=None, description="用户选择: accept/provide/reference/skip")
    user_guidance: Optional[str] = Field(default=None, description="用户提供的概要内容")
    force_regenerate: bool = Field(
        default=False, description="是否强制重新生成（即使已存在详细大纲）")


@router.post("/projects/{project_id}/outline-intervention/{unit_number}")
async def outline_intervention(
    project_id: int,
    unit_number: int,
    request: OutlineInterventionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    带用户干预选项的详细大纲生成

    当推断置信度过低时，提供用户干预选项：
    1. accept - 接受推断生成
    2. provide - 提供章节概要
    3. reference - 参考相邻章节重新生成
    4. skip - 跳过此章节

    返回值说明：
    - status == "need_intervention": 需要用户干预，显示选项
    - status == "success": 生成成功
    - status == "skipped": 用户跳过
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 调用生成器的干预方法
        generator = NovelChapterGenerator(db)
        intervention_result = await generator.generate_outline_with_intervention(
            project=project,
            unit_number=unit_number,
            content_type=request.content_type,
            user_choice=request.user_choice,
            user_guidance=request.user_guidance,
            force_regenerate=request.force_regenerate
        )

        status = intervention_result.get("status")

        if status == "need_intervention":
            # 需要用户干预
            return ResponseModel(
                success=True,
                data=intervention_result,
                message=intervention_result.get("message", "需要用户干预")
            )
        elif status == "already_exists":
            # 已存在详细大纲
            return ResponseModel(
                success=True,
                data=intervention_result,
                message=intervention_result.get("message", "已存在详细大纲")
            )
        elif status == "success" or status == "completed":
            # 生成成功
            logger.info(
                f"第{unit_number}单元详细大纲生成成功（用户干预）: project_id={project_id}")
            return ResponseModel(
                success=True,
                data=intervention_result,
                message="生成成功"
            )
        elif status == "skipped":
            return ResponseModel(
                success=True,
                data=intervention_result,
                message=intervention_result.get("message", "已跳过")
            )
        elif status == "need_guidance":
            return ResponseModel(
                success=False,
                data=intervention_result,
                message="请提供章节概要内容"
            )
        else:
            return ResponseModel(
                success=False,
                data=intervention_result,
                message=intervention_result.get("message", "未知状态")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"详细大纲干预生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/validate-outline-consistency/{unit_number}")
async def validate_outline_consistency(
    project_id: int,
    unit_number: int,
    request: OutlineInterventionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    校验生成的详细大纲与已有内容的一致性

    检查维度：
    1. 人物行为是否符合设定
    2. 剧情发展是否与前文矛盾
    3. 世界观设定是否被违反
    4. 时间线是否连贯

    返回一致性分数和建议
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取已生成的详细大纲
        existing_outlines = (
            project.chapter_outlines or
            project.episode_outlines or
            project.scene_outlines or
            {}
        )

        unit_outline = existing_outlines.get(str(unit_number), {})
        if not unit_outline:
            raise HTTPException(status_code=404, detail="该单元详细大纲不存在")

        # 调用校验方法
        generator = NovelChapterGenerator(db)
        validation_result = await generator._validate_outline_consistency(
            project=project,
            unit_number=unit_number,
            generated_outline=unit_outline,
            content_type=request.content_type
        )

        return ResponseModel(
            success=True,
            data=validation_result,
            message=validation_result.get("recommendation", "校验完成")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"一致性校验失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/position-aware-context/{unit_number}")
async def get_position_aware_context(
    project_id: int,
    unit_number: int,
    content_type: str = "novel",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取位置感知的上下文信息

    根据当前单元在整体故事中的位置，返回动态调整的上下文内容：
    - 开端阶段：优先返回世界观和人物设定
    - 发展阶段：平衡返回前文摘要和设定
    - 高潮阶段：优先返回冲突和情感信息
    - 结局阶段：优先返回伏笔回收和未解决冲突
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 调用位置感知上下文方法
        generator = NovelChapterGenerator(db)
        context = generator._build_position_aware_context(
            project=project,
            unit_number=unit_number,
            content_type=content_type
        )

        return ResponseModel(
            success=True,
            data=context,
            message=f"当前位置阶段: {context.get('position_phase', '未知')}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取位置感知上下文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/generate-all-chapter-outlines")
async def generate_all_chapter_outlines(
    project_id: int,
    request: ChapterOutlineGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量生成多章详细大纲（小说专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 检查项目类型
        content_type = getattr(project, 'content_type', None)
        if content_type != 'novel':
            raise HTTPException(status_code=400, detail="此接口仅适用于小说项目")

        # 检查基础大纲
        if not project.outline_content:
            raise HTTPException(status_code=400, detail="请先上传基础大纲")

        # 创建内存取消令牌
        cancel_event = set_cancel_token(project_id)

        try:
            # 调用生成器批量生成
            generator = NovelChapterGenerator(db)
            gen_result = await generator.generate_all_chapter_outlines(
                project,
                chapter_numbers=request.chapter_numbers,
                stop_on_error=request.stop_on_error
            )

            logger.info(
                f"批量生成章节大纲完成: {project.title}, 成功{gen_result['completed_count']}章")

            return ResponseModel(
                success=True,
                data=gen_result
            )
        finally:
            clear_cancel_token(project_id)

    except asyncio.CancelledError:
        logger.warning(f"批量生成章节大纲被取消: project_id={project_id}")
        clear_cancel_token(project_id)
        await db.rollback()
        raise HTTPException(status_code=499, detail="请求被取消")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量生成章节大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/chapter-outlines", response_model=ResponseModel[ChapterOutlineListResponse])
async def get_chapter_outlines(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取所有章节详细大纲（小说专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取章节大纲
        chapter_outlines = project.chapter_outlines or {}

        # 获取总章节数
        total_chapters = project.total_chapters or 0

        # 如果没有配置总章节数，尝试从大纲中提取
        if total_chapters == 0 and project.outline_content:
            total_chapters = extract_chapter_count(
                project.outline_content, "novel")

        # 构建响应列表
        chapters = []
        generated_count = 0

        for ch_num in range(1, total_chapters + 1):
            ch_outline = chapter_outlines.get(str(ch_num), {})
            if ch_outline:
                generated_count += 1
                chapters.append(ChapterOutlineResponse(
                    chapter_number=ch_outline.get("chapter_number", ch_num),
                    chapter_title=ch_outline.get("chapter_title"),
                    chapter_summary=ch_outline.get("chapter_summary"),
                    detailed_outline=ch_outline.get("detailed_outline", ""),
                    key_events=ch_outline.get("key_events"),
                    character_arcs=ch_outline.get("character_arcs"),
                    suspense_points=ch_outline.get("suspense_points"),
                    emotional_tone=ch_outline.get("emotional_tone"),
                    status=ch_outline.get("status", "generated"),
                    content_status=ch_outline.get("content_status"),
                    content_word_count=ch_outline.get("content_word_count"),
                    created_at=ch_outline.get("created_at"),
                    updated_at=ch_outline.get("updated_at")
                ))
            else:
                chapters.append(ChapterOutlineResponse(
                    chapter_number=ch_num,
                    chapter_title=f"第{ch_num}章",
                    chapter_summary=None,
                    detailed_outline="",
                    status="pending"
                ))

        return ResponseModel(
            success=True,
            data=ChapterOutlineListResponse(
                project_id=project.id,
                total_chapters=total_chapters,
                generated_count=generated_count,
                chapters=chapters
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取章节大纲列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/chapter-outlines/{chapter_num}", response_model=ResponseModel[ChapterOutlineResponse])
async def get_chapter_outline(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取单个章节详细大纲（小说专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取章节大纲
        chapter_outlines = project.chapter_outlines or {}
        ch_outline = chapter_outlines.get(str(chapter_num))

        if not ch_outline:
            raise HTTPException(
                status_code=404, detail=f"第{chapter_num}章的详细大纲尚未生成")

        return ResponseModel(
            success=True,
            data=ChapterOutlineResponse(
                chapter_number=ch_outline.get("chapter_number", chapter_num),
                chapter_title=ch_outline.get("chapter_title"),
                chapter_summary=ch_outline.get("chapter_summary"),
                detailed_outline=ch_outline.get("detailed_outline", ""),
                key_events=ch_outline.get("key_events"),
                character_arcs=ch_outline.get("character_arcs"),
                suspense_points=ch_outline.get("suspense_points"),
                emotional_tone=ch_outline.get("emotional_tone"),
                status=ch_outline.get("status", "generated"),
                created_at=ch_outline.get("created_at"),
                updated_at=ch_outline.get("updated_at"),
                # 修正信息
                original_content=ch_outline.get("original_content"),
                revision_info=ch_outline.get("revision_info")
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取章节大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/chapter-outlines/{chapter_num}")
async def update_chapter_outline(
    project_id: int,
    chapter_num: int,
    request: ChapterOutlineUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新章节详细大纲（小说专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取现有大纲
        chapter_outlines = project.chapter_outlines or {}
        ch_outline = chapter_outlines.get(str(chapter_num), {})

        if not ch_outline:
            ch_outline = {
                "chapter_number": chapter_num,
                "chapter_title": f"第{chapter_num}章",
                "chapter_summary": "",
                "detailed_outline": "",
                "status": "pending"
            }

        # 更新字段
        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                ch_outline[key] = value

        # 更新状态和时间
        ch_outline["status"] = "edited"
        ch_outline["updated_at"] = datetime.now().isoformat()

        # 保存
        if not project.chapter_outlines:
            project.chapter_outlines = {}

        updated_outlines = dict(project.chapter_outlines)
        updated_outlines[str(chapter_num)] = ch_outline
        project.chapter_outlines = updated_outlines

        flag_modified(project, 'chapter_outlines')

        await db.commit()
        await db.refresh(project)

        logger.info(f"第{chapter_num}章详细大纲已更新: {project.title}")

        return ResponseModel(
            success=True,
            data=ChapterOutlineResponse(
                chapter_number=ch_outline.get("chapter_number", chapter_num),
                chapter_title=ch_outline.get("chapter_title"),
                chapter_summary=ch_outline.get("chapter_summary"),
                detailed_outline=ch_outline.get("detailed_outline", ""),
                key_events=ch_outline.get("key_events"),
                character_arcs=ch_outline.get("character_arcs"),
                suspense_points=ch_outline.get("suspense_points"),
                emotional_tone=ch_outline.get("emotional_tone"),
                status=ch_outline.get("status", "edited"),
                created_at=ch_outline.get("created_at"),
                updated_at=ch_outline.get("updated_at")
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新章节大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/chapter-outlines/{chapter_num}")
async def delete_chapter_outline(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除章节详细大纲（小说专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 删除大纲
        chapter_outlines = project.chapter_outlines or {}
        if str(chapter_num) in chapter_outlines:
            del chapter_outlines[str(chapter_num)]
            project.chapter_outlines = chapter_outlines
            flag_modified(project, 'chapter_outlines')
            await db.commit()
            logger.info(f"第{chapter_num}章详细大纲已删除: {project.title}")
            return ResponseModel(success=True, message=f"第{chapter_num}章详细大纲已删除")
        else:
            raise HTTPException(
                status_code=404, detail=f"第{chapter_num}章的详细大纲不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除章节大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 场景详细大纲 API（电影剧本专用） ====================

@router.post("/projects/{project_id}/generate-scene-outline/{scene_num}")
async def generate_scene_outline(
    project_id: int,
    scene_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成单场景详细大纲（电影剧本专用）

    基于基础大纲中的场景概要，生成该场景的详细大纲。
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 检查项目类型
        content_type = getattr(project, 'content_type', None)
        if content_type != 'movie_script':
            raise HTTPException(status_code=400, detail="此接口仅适用于电影剧本项目")

        # 检查基础大纲
        if not project.outline_content:
            raise HTTPException(status_code=400, detail="请先上传基础大纲")

        # 调用生成器生成场景详细大纲
        generator = NovelChapterGenerator(db)
        gen_result = await generator.generate_scene_outline(project, scene_num)

        if not gen_result["success"]:
            raise HTTPException(
                status_code=500, detail=gen_result.get("error_message", "生成失败"))

        logger.info(f"第{scene_num}场详细大纲生成成功: {project.title}")

        return ResponseModel(
            success=True,
            data={
                "scene_number": scene_num,
                "content": gen_result.get("content"),
                "parsed": gen_result.get("parsed"),
                "duration_ms": gen_result.get("duration_ms", 0)
            }
        )

    except asyncio.CancelledError:
        logger.warning(f"第{scene_num}场详细大纲生成被取消: project_id={project_id}")
        await db.rollback()
        raise HTTPException(status_code=499, detail="请求被取消")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成场景大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/generate-all-scene-outlines")
async def generate_all_scene_outlines(
    project_id: int,
    request: SceneOutlineGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量生成多场景详细大纲（电影剧本专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 检查项目类型
        content_type = getattr(project, 'content_type', None)
        if content_type != 'movie_script':
            raise HTTPException(status_code=400, detail="此接口仅适用于电影剧本项目")

        # 检查基础大纲
        if not project.outline_content:
            raise HTTPException(status_code=400, detail="请先上传基础大纲")

        # 创建内存取消令牌
        cancel_event = set_cancel_token(project_id)

        try:
            # 调用生成器批量生成
            generator = NovelChapterGenerator(db)
            gen_result = await generator.generate_all_scene_outlines(
                project,
                scene_numbers=request.scene_numbers,
                stop_on_error=request.stop_on_error
            )

            logger.info(
                f"批量生成场景大纲完成: {project.title}, 成功{gen_result['completed_count']}场")

            return ResponseModel(
                success=True,
                data=gen_result
            )
        finally:
            clear_cancel_token(project_id)

    except asyncio.CancelledError:
        logger.warning(f"批量生成场景大纲被取消: project_id={project_id}")
        clear_cancel_token(project_id)
        await db.rollback()
        raise HTTPException(status_code=499, detail="请求被取消")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量生成场景大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 批量正文生成端点 ====================

class BatchContentGenerateRequest(BaseModel):
    """批量正文生成请求"""
    unit_numbers: Optional[List[int]] = None  # 要生成的单元号列表，None表示生成全部
    stop_on_error: bool = True


@router.post("/projects/{project_id}/generate-all-episode-content")
async def generate_all_episode_content(
    project_id: int,
    request: BatchContentGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量生成多集正文（剧集专用）
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        content_type = getattr(project, 'content_type', None)
        if content_type not in ('series_script', 'script'):
            raise HTTPException(status_code=400, detail="此接口仅适用于剧集项目")

        # 创建内存取消令牌
        cancel_event = set_cancel_token(project_id)

        try:
            generator = NovelChapterGenerator(db)
            gen_result = await generator.generate_all_episode_content(
                project,
                episode_numbers=request.unit_numbers,
                stop_on_error=request.stop_on_error
            )

            logger.info(
                f"批量生成剧集正文完成: {project.title}, 成功{gen_result['completed_count']}集")

            return ResponseModel(success=True, data=gen_result)
        finally:
            clear_cancel_token(project_id)

    except asyncio.CancelledError:
        logger.warning(f"批量生成剧集正文被取消: project_id={project_id}")
        clear_cancel_token(project_id)
        await db.rollback()
        raise HTTPException(status_code=499, detail="请求被取消")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量生成剧集正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/generate-all-chapter-content")
async def generate_all_chapter_content(
    project_id: int,
    request: BatchContentGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量生成多章正文（小说专用）"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        content_type = getattr(project, 'content_type', None)
        if content_type != 'novel':
            raise HTTPException(status_code=400, detail="此接口仅适用于小说项目")

        # 创建内存取消令牌
        cancel_event = set_cancel_token(project_id)

        try:
            generator = NovelChapterGenerator(db)
            gen_result = await generator.generate_all_chapter_content(
                project,
                chapter_numbers=request.unit_numbers,
                stop_on_error=request.stop_on_error
            )

            logger.info(
                f"批量生成小说正文完成: {project.title}, 成功{gen_result['completed_count']}章")

            return ResponseModel(success=True, data=gen_result)
        finally:
            clear_cancel_token(project_id)

    except asyncio.CancelledError:
        logger.warning(f"批量生成小说正文被取消: project_id={project_id}")
        clear_cancel_token(project_id)
        await db.rollback()
        raise HTTPException(status_code=499, detail="请求被取消")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量生成小说正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/generate-all-scene-content")
async def generate_all_scene_content(
    project_id: int,
    request: BatchContentGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量生成多场景正文（电影剧本专用）"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        content_type = getattr(project, 'content_type', None)
        if content_type != 'movie_script':
            raise HTTPException(status_code=400, detail="此接口仅适用于电影剧本项目")

        # 创建内存取消令牌
        cancel_event = set_cancel_token(project_id)

        try:
            generator = NovelChapterGenerator(db)
            gen_result = await generator.generate_all_scene_content(
                project,
                scene_numbers=request.unit_numbers,
                stop_on_error=request.stop_on_error
            )

            logger.info(
                f"批量生成电影正文完成: {project.title}, 成功{gen_result['completed_count']}场")

            return ResponseModel(success=True, data=gen_result)
        finally:
            clear_cancel_token(project_id)

    except asyncio.CancelledError:
        logger.warning(f"批量生成电影正文被取消: project_id={project_id}")
        clear_cancel_token(project_id)
        await db.rollback()
        raise HTTPException(status_code=499, detail="请求被取消")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量生成电影正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/scene-outlines", response_model=ResponseModel[SceneOutlineListResponse])
async def get_scene_outlines(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取所有场景详细大纲（电影剧本专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取场景大纲
        scene_outlines = project.scene_outlines or {}

        # 获取总场景数
        total_scenes = project.total_chapters or 0

        # 如果没有配置总场景数，尝试从大纲中提取
        if total_scenes == 0 and project.outline_content:
            total_scenes = extract_chapter_count(
                project.outline_content, "movie_script")

        # 构建响应列表
        scenes = []
        generated_count = 0

        for sc_num in range(1, total_scenes + 1):
            sc_outline = scene_outlines.get(str(sc_num), {})
            if sc_outline:
                generated_count += 1
                scenes.append(SceneOutlineResponse(
                    scene_number=sc_outline.get("scene_number", sc_num),
                    scene_title=sc_outline.get("scene_title"),
                    location=sc_outline.get("location"),
                    scene_summary=sc_outline.get("scene_summary"),
                    detailed_outline=sc_outline.get("detailed_outline", ""),
                    characters=sc_outline.get("characters"),
                    estimated_duration=sc_outline.get("estimated_duration"),
                    key_action=sc_outline.get("key_action"),
                    dialogue_focus=sc_outline.get("dialogue_focus"),
                    status=sc_outline.get("status", "generated"),
                    content_status=sc_outline.get("content_status"),
                    content_word_count=sc_outline.get("content_word_count"),
                    created_at=sc_outline.get("created_at"),
                    updated_at=sc_outline.get("updated_at")
                ))
            else:
                scenes.append(SceneOutlineResponse(
                    scene_number=sc_num,
                    scene_title=f"第{sc_num}场",
                    location=None,
                    scene_summary=None,
                    detailed_outline="",
                    status="pending"
                ))

        return ResponseModel(
            success=True,
            data=SceneOutlineListResponse(
                project_id=project.id,
                total_scenes=total_scenes,
                generated_count=generated_count,
                scenes=scenes
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取场景大纲列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/scene-outlines/{scene_num}", response_model=ResponseModel[SceneOutlineResponse])
async def get_scene_outline(
    project_id: int,
    scene_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取单个场景详细大纲（电影剧本专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取场景大纲
        scene_outlines = project.scene_outlines or {}
        sc_outline = scene_outlines.get(str(scene_num))

        if not sc_outline:
            raise HTTPException(
                status_code=404, detail=f"第{scene_num}场的详细大纲尚未生成")

        return ResponseModel(
            success=True,
            data=SceneOutlineResponse(
                scene_number=sc_outline.get("scene_number", scene_num),
                scene_title=sc_outline.get("scene_title"),
                location=sc_outline.get("location"),
                scene_summary=sc_outline.get("scene_summary"),
                detailed_outline=sc_outline.get("detailed_outline", ""),
                characters=sc_outline.get("characters"),
                estimated_duration=sc_outline.get("estimated_duration"),
                key_action=sc_outline.get("key_action"),
                dialogue_focus=sc_outline.get("dialogue_focus"),
                status=sc_outline.get("status", "generated"),
                created_at=sc_outline.get("created_at"),
                updated_at=sc_outline.get("updated_at")
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取场景大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/scene-outlines/{scene_num}")
async def update_scene_outline(
    project_id: int,
    scene_num: int,
    request: SceneOutlineUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新场景详细大纲（电影剧本专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取现有大纲
        scene_outlines = project.scene_outlines or {}
        sc_outline = scene_outlines.get(str(scene_num), {})

        if not sc_outline:
            sc_outline = {
                "scene_number": scene_num,
                "scene_title": f"第{scene_num}场",
                "location": None,
                "scene_summary": "",
                "detailed_outline": "",
                "status": "pending"
            }

        # 更新字段
        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                sc_outline[key] = value

        # 更新状态和时间
        sc_outline["status"] = "edited"
        sc_outline["updated_at"] = datetime.now().isoformat()

        # 保存
        if not project.scene_outlines:
            project.scene_outlines = {}

        updated_outlines = dict(project.scene_outlines)
        updated_outlines[str(scene_num)] = sc_outline
        project.scene_outlines = updated_outlines

        flag_modified(project, 'scene_outlines')

        await db.commit()
        await db.refresh(project)

        logger.info(f"第{scene_num}场详细大纲已更新: {project.title}")

        return ResponseModel(
            success=True,
            data=SceneOutlineResponse(
                scene_number=sc_outline.get("scene_number", scene_num),
                scene_title=sc_outline.get("scene_title"),
                location=sc_outline.get("location"),
                scene_summary=sc_outline.get("scene_summary"),
                detailed_outline=sc_outline.get("detailed_outline", ""),
                characters=sc_outline.get("characters"),
                estimated_duration=sc_outline.get("estimated_duration"),
                key_action=sc_outline.get("key_action"),
                dialogue_focus=sc_outline.get("dialogue_focus"),
                status=sc_outline.get("status", "edited"),
                created_at=sc_outline.get("created_at"),
                updated_at=sc_outline.get("updated_at")
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新场景大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/scene-outlines/{scene_num}")
async def delete_scene_outline(
    project_id: int,
    scene_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除场景详细大纲（电影剧本专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 删除大纲
        scene_outlines = project.scene_outlines or {}
        if str(scene_num) in scene_outlines:
            del scene_outlines[str(scene_num)]
            project.scene_outlines = scene_outlines
            flag_modified(project, 'scene_outlines')
            await db.commit()
            logger.info(f"第{scene_num}场详细大纲已删除: {project.title}")
            return ResponseModel(success=True, message=f"第{scene_num}场详细大纲已删除")
        else:
            raise HTTPException(
                status_code=404, detail=f"第{scene_num}场的详细大纲不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除场景大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 小说章节正文生成 API ====================

@router.post("/projects/{project_id}/generate-chapter-content/{chapter_num}")
async def generate_chapter_content_endpoint(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成小说章节正文（需要先有章节详细大纲）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 检查项目类型
        content_type = getattr(project, 'content_type', None)
        if content_type != 'novel':
            raise HTTPException(status_code=400, detail="此接口仅适用于小说项目")

        # 检查该章是否有详细大纲
        chapter_outlines = project.chapter_outlines or {}
        chapter_outline = chapter_outlines.get(str(chapter_num))

        if not chapter_outline:
            raise HTTPException(
                status_code=400,
                detail=f"第{chapter_num}章的详细大纲未生成，请先生成章节详细大纲"
            )

        logger.info(f"[章节正文生成] 开始生成第{chapter_num}章正文: {project.title}")

        # 调用生成器生成章节正文
        generator = NovelChapterGenerator(db)
        gen_result = await generator.generate_chapter(project, chapter_num)

        if not gen_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=gen_result.get("error_message", "生成失败")
            )

        # 更新章节大纲的正文生成状态
        chapter_outline["content_status"] = "generated"
        chapter_outline["content_generated_at"] = datetime.now().isoformat()
        chapter_outline["content_word_count"] = gen_result.get("word_count", 0)
        chapter_outlines[str(chapter_num)] = chapter_outline
        project.chapter_outlines = chapter_outlines
        flag_modified(project, 'chapter_outlines')

        await db.commit()

        # 获取生成的章节记录
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number == chapter_num
        )
        chapter_result = await db.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        logger.info(
            f"[章节正文生成] 第{chapter_num}章正文生成成功: {project.title}, 字数: {gen_result.get('word_count', 0)}")

        return ResponseModel(
            success=True,
            data={
                "chapter_number": chapter_num,
                "chapter_title": chapter.chapter_title if chapter else f"第{chapter_num}章",
                "content": gen_result.get("content"),
                "word_count": gen_result.get("word_count", 0),
                "token_count": gen_result.get("token_count", 0),
                "duration_ms": gen_result.get("duration_ms", 0),
                "chapter": {
                    "id": chapter.id if chapter else None,
                    "chapter_number": chapter.chapter_number if chapter else chapter_num,
                    "chapter_title": chapter.chapter_title if chapter else f"第{chapter_num}章",
                    "status": chapter.status if chapter else "completed",
                    "word_count": chapter.word_count if chapter else gen_result.get("word_count", 0)
                } if chapter else None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成章节正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 电影场景正文生成 API ====================

@router.post("/projects/{project_id}/generate-scene-content/{scene_num}")
async def generate_scene_content_endpoint(
    project_id: int,
    scene_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成电影场景正文（需要先有场景详细大纲）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 检查项目类型
        content_type = getattr(project, 'content_type', None)
        if content_type != 'movie_script':
            raise HTTPException(status_code=400, detail="此接口仅适用于电影剧本项目")

        # 检查该场景是否有详细大纲
        scene_outlines = project.scene_outlines or {}
        scene_outline = scene_outlines.get(str(scene_num))

        if not scene_outline:
            raise HTTPException(
                status_code=400,
                detail=f"第{scene_num}场的详细大纲未生成，请先生成场景详细大纲"
            )

        logger.info(f"[场景正文生成] 开始生成第{scene_num}场正文: {project.title}")

        # 调用生成器生成场景正文
        generator = NovelChapterGenerator(db)
        gen_result = await generator.generate_scene_content(project, scene_num)

        if not gen_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=gen_result.get("error_message", "生成失败")
            )

        # 更新场景大纲的正文生成状态
        scene_outline["content_status"] = "generated"
        scene_outline["content_generated_at"] = datetime.now().isoformat()
        scene_outline["content_word_count"] = gen_result.get("word_count", 0)
        scene_outlines[str(scene_num)] = scene_outline
        project.scene_outlines = scene_outlines
        flag_modified(project, 'scene_outlines')

        await db.commit()

        # 获取生成的章节记录
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number == scene_num
        )
        chapter_result = await db.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        logger.info(
            f"[场景正文生成] 第{scene_num}场正文生成成功: {project.title}, 字数: {gen_result.get('word_count', 0)}")

        return ResponseModel(
            success=True,
            data={
                "scene_number": scene_num,
                "scene_title": chapter.chapter_title if chapter else f"第{scene_num}场",
                "content": gen_result.get("content"),
                "word_count": gen_result.get("word_count", 0),
                "token_count": gen_result.get("token_count", 0),
                "duration_ms": gen_result.get("duration_ms", 0),
                "chapter": {
                    "id": chapter.id if chapter else None,
                    "chapter_number": chapter.chapter_number if chapter else scene_num,
                    "chapter_title": chapter.chapter_title if chapter else f"第{scene_num}场",
                    "status": chapter.status if chapter else "completed",
                    "word_count": chapter.word_count if chapter else gen_result.get("word_count", 0)
                } if chapter else None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成场景正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 批量获取正文内容 API ====================

@router.get("/projects/{project_id}/all-episode-content")
async def get_all_episode_content(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取全部剧集正文内容

    返回所有已生成的剧集正文，用于批量下载
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取所有有正文的章节记录（按 episode_number 筛选）
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.episode_number != None,
            NovelChapter.final_content != None
        ).order_by(NovelChapter.episode_number)

        chapter_result = await db.execute(chapter_query)
        chapters = chapter_result.scalars().all()

        # 构建返回数据
        contents = []
        for chapter in chapters:
            contents.append({
                "episode_number": chapter.episode_number,
                "chapter_title": chapter.chapter_title or f"第{chapter.episode_number}集",
                "content": chapter.final_content,
                "word_count": chapter.word_count
            })

        return ResponseModel(
            success=True,
            data={
                "project_title": project.title,
                "content_type": "episode",
                "total_count": len(contents),
                "contents": contents
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取全部剧集正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/all-chapter-content")
async def get_all_chapter_content(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取全部小说章节正文内容

    返回所有已生成的章节正文，用于批量下载
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取所有有正文的章节记录（小说类型：episode_number 为空，scene_number 为空）
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.episode_number == None,
            NovelChapter.scene_number == None,
            NovelChapter.final_content != None
        ).order_by(NovelChapter.chapter_number)

        chapter_result = await db.execute(chapter_query)
        chapters = chapter_result.scalars().all()

        # 构建返回数据
        contents = []
        for chapter in chapters:
            contents.append({
                "chapter_number": chapter.chapter_number,
                "chapter_title": chapter.chapter_title or f"第{chapter.chapter_number}章",
                "content": chapter.final_content,
                "word_count": chapter.word_count
            })

        return ResponseModel(
            success=True,
            data={
                "project_title": project.title,
                "content_type": "chapter",
                "total_count": len(contents),
                "contents": contents
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取全部章节正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/all-scene-content")
async def get_all_scene_content(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取全部电影场景正文内容

    返回所有已生成的场景正文，用于批量下载
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取所有有正文的章节记录（电影类型：scene_number 不为空）
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.scene_number != None,
            NovelChapter.final_content != None
        ).order_by(NovelChapter.scene_number)

        chapter_result = await db.execute(chapter_query)
        chapters = chapter_result.scalars().all()

        # 构建返回数据
        contents = []
        for chapter in chapters:
            contents.append({
                "scene_number": chapter.scene_number,
                "chapter_title": chapter.chapter_title or f"第{chapter.scene_number}场",
                "content": chapter.final_content,
                "word_count": chapter.word_count
            })

        return ResponseModel(
            success=True,
            data={
                "project_title": project.title,
                "content_type": "scene",
                "total_count": len(contents),
                "contents": contents
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取全部场景正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 任务状态管理 API ====================

@router.get("/projects/{project_id}/task-status")
async def get_task_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目的当前生成任务状态

    用于页面刷新后恢复生成状态UI，检查是否有正在进行的批量生成任务
    """
    # 验证项目权限
    query = select(NovelProject).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    task = await task_manager.get_task(project_id)

    return ResponseModel(
        success=True,
        data=task  # 无任务时返回None
    )


@router.post("/projects/{project_id}/cancel-task")
async def cancel_generation_task(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    取消当前生成任务

    无论前端是否保持连接，都可以通过此API取消任务。
    后端会在每次循环迭代时检查任务状态，发现被取消后停止生成。
    """
    # 验证项目权限
    query = select(NovelProject).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 检查是否有运行中的任务
    task = await task_manager.get_task(project_id)
    if not task or task.get("status") != "running":
        return ResponseModel(
            success=False,
            message="没有正在运行的任务"
        )

    # 取消任务
    cancelled_task = await task_manager.cancel_task(project_id)

    # 同时触发内存取消令牌（立即生效，不依赖 Redis）
    trigger_memory_cancel(project_id)

    logger.info(f"用户 {current_user.username} 取消了项目 {project.title} 的生成任务")

    return ResponseModel(
        success=True,
        data=cancelled_task,
        message="任务已取消，正在生成的内容将在当前项完成后停止"
    )


@router.get("/projects/{project_id}/task-events")
async def stream_task_events(
    project_id: int,
    current_user: User = Depends(get_current_user_from_query_or_header),
    db: AsyncSession = Depends(get_db)
):
    """
    SSE 端点：实时推送任务状态更新

    客户端连接后，会收到实时的任务进度更新。
    支持自动重连，断线后重新连接可继续接收更新。
    """
    # 验证项目权限
    query = select(NovelProject).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    async def event_generator():
        """SSE 事件生成器"""
        from app.services.task_manager import (
            subscribe_task_events,
            unsubscribe_task_events,
            task_manager
        )

        queue = None
        try:
            # 订阅任务事件
            queue = subscribe_task_events(project_id)

            # 首先发送当前任务状态（如果存在）
            current_task = await task_manager.get_task(project_id)
            if current_task:
                yield f"data: {json.dumps(current_task, ensure_ascii=False)}\n\n"
            else:
                # 无任务时发送空状态
                yield f"data: null\n\n"

            # 持续监听任务更新
            while True:
                try:
                    # 等待事件，设置超时以发送心跳
                    event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {event_data}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳注释，防止连接超时
                    yield ": heartbeat\n\n"
                except asyncio.CancelledError:
                    # 客户端断开连接
                    break
        finally:
            # 清理订阅
            if queue:
                unsubscribe_task_events(project_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )


# ==================== 删除正文内容 API ====================

@router.delete("/projects/{project_id}/chapter-content/{chapter_num}")
async def delete_chapter_content(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除小说章节正文内容（保留大纲）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 删除章节正文记录
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.chapter_number == chapter_num
        )
        chapter_result = await db.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        if chapter:
            # 清空正文内容，保留章节记录
            chapter.final_content = None
            chapter.draft_content = None
            chapter.word_count = 0
            chapter.status = ChapterStatus.PENDING

        # 更新章节大纲的正文生成状态
        chapter_outlines = project.chapter_outlines or {}
        if str(chapter_num) in chapter_outlines:
            chapter_outlines[str(chapter_num)]["content_status"] = None
            chapter_outlines[str(chapter_num)]["content_generated_at"] = None
            chapter_outlines[str(chapter_num)]["content_word_count"] = 0
            project.chapter_outlines = chapter_outlines
            flag_modified(project, 'chapter_outlines')

        await db.commit()
        logger.info(f"第{chapter_num}章正文已删除: {project.title}")
        return ResponseModel(success=True, message=f"第{chapter_num}章正文已删除")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除章节正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/episode-content/{episode_num}")
async def delete_episode_content(
    project_id: int,
    episode_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除剧集正文内容（保留大纲）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 删除剧集正文记录（通过episode_number查找）
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.episode_number == episode_num
        )
        chapter_result = await db.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        if chapter:
            # 清空正文内容，保留章节记录
            chapter.final_content = None
            chapter.draft_content = None
            chapter.word_count = 0
            chapter.status = ChapterStatus.PENDING

        # 更新分集大纲的正文生成状态
        episode_outlines = project.episode_outlines or {}
        if str(episode_num) in episode_outlines:
            episode_outlines[str(episode_num)]["content_status"] = None
            episode_outlines[str(episode_num)]["content_generated_at"] = None
            episode_outlines[str(episode_num)]["content_word_count"] = 0
            project.episode_outlines = episode_outlines
            flag_modified(project, 'episode_outlines')

        await db.commit()
        logger.info(f"第{episode_num}集正文已删除: {project.title}")
        return ResponseModel(success=True, message=f"第{episode_num}集正文已删除")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除剧集正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/scene-content/{scene_num}")
async def delete_scene_content(
    project_id: int,
    scene_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除电影场景正文内容（保留大纲）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 删除场景正文记录（通过scene_number查找）
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.scene_number == scene_num
        )
        chapter_result = await db.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        if chapter:
            # 清空正文内容，保留章节记录
            chapter.final_content = None
            chapter.draft_content = None
            chapter.word_count = 0
            chapter.status = ChapterStatus.PENDING

        # 更新场景大纲的正文生成状态
        scene_outlines = project.scene_outlines or {}
        if str(scene_num) in scene_outlines:
            scene_outlines[str(scene_num)]["content_status"] = None
            scene_outlines[str(scene_num)]["content_generated_at"] = None
            scene_outlines[str(scene_num)]["content_word_count"] = 0
            project.scene_outlines = scene_outlines
            flag_modified(project, 'scene_outlines')

        await db.commit()
        logger.info(f"第{scene_num}场正文已删除: {project.title}")
        return ResponseModel(success=True, message=f"第{scene_num}场正文已删除")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除场景正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/all-content")
async def delete_all_content(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    一键清空所有大纲和正文内容
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 清空所有大纲
        project.episode_outlines = None
        project.chapter_outlines = None
        project.scene_outlines = None
        flag_modified(project, 'episode_outlines')
        flag_modified(project, 'chapter_outlines')
        flag_modified(project, 'scene_outlines')

        # 删除所有章节记录
        delete_query = delete(NovelChapter).where(
            NovelChapter.project_id == project_id
        )
        await db.execute(delete_query)

        # 重置项目进度
        project.completed_chapters = 0
        project.current_chapter = 0
        project.status = ProjectStatus.INIT

        await db.commit()
        logger.info(f"已清空所有大纲和正文: {project.title}")
        return ResponseModel(success=True, message="已清空所有大纲和正文内容")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清空内容失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/all-outlines")
async def delete_all_outlines(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    一键清空所有大纲（保留正文）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 清空所有大纲
        project.episode_outlines = None
        project.chapter_outlines = None
        project.scene_outlines = None
        flag_modified(project, 'episode_outlines')
        flag_modified(project, 'chapter_outlines')
        flag_modified(project, 'scene_outlines')

        await db.commit()
        logger.info(f"已清空所有大纲: {project.title}")
        return ResponseModel(success=True, message="已清空所有大纲")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清空大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/all-chapter-content")
async def delete_all_chapter_content(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    一键清空所有正文（保留大纲）

    注意：此操作不会影响知识库
    - 保留知识库状态 (kb_status)
    - 保留知识库向量数据 (project_kb_collection)
    - 保留知识图谱文件 (global_outline_graph_path)
    - 仅清空正文内容和生成状态
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 清空所有章节正文记录
        delete_query = delete(NovelChapter).where(
            NovelChapter.project_id == project_id
        )
        await db.execute(delete_query)

        # 清空大纲中的正文状态
        content_type = project.content_type
        if content_type == 'novel':
            chapter_outlines = project.chapter_outlines or {}
            for key in chapter_outlines:
                chapter_outlines[key]["content_status"] = None
                chapter_outlines[key]["content_generated_at"] = None
                chapter_outlines[key]["content_word_count"] = 0
            project.chapter_outlines = chapter_outlines
            flag_modified(project, 'chapter_outlines')
        elif content_type == 'series_script':
            episode_outlines = project.episode_outlines or {}
            for key in episode_outlines:
                episode_outlines[key]["content_status"] = None
                episode_outlines[key]["content_generated_at"] = None
                episode_outlines[key]["content_word_count"] = 0
            project.episode_outlines = episode_outlines
            flag_modified(project, 'episode_outlines')
        elif content_type == 'movie_script':
            scene_outlines = project.scene_outlines or {}
            for key in scene_outlines:
                scene_outlines[key]["content_status"] = None
                scene_outlines[key]["content_generated_at"] = None
                scene_outlines[key]["content_word_count"] = 0
            project.scene_outlines = scene_outlines
            flag_modified(project, 'scene_outlines')

        # 重置项目进度
        project.completed_chapters = 0
        project.current_chapter = 0

        await db.commit()
        logger.info(f"已清空所有正文: {project.title}")
        return ResponseModel(success=True, message="已清空所有正文内容")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清空正文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 数据修复端点 ====================

@router.post("/projects/{project_id}/sync-content-status")
async def sync_content_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    同步章节正文状态（修复历史数据）

    将已生成正文的章节在 xxx_outlines 中的 content_status 设置为 'generated'
    用于修复之前批量生成时未正确更新状态的问题
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        content_type = getattr(project, 'content_type', 'novel')
        updated_count = 0

        # 获取所有已生成正文的章节记录
        chapter_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id,
            NovelChapter.final_content != None
        )
        chapter_result = await db.execute(chapter_query)
        chapters = chapter_result.scalars().all()

        if content_type == 'novel':
            chapter_outlines = project.chapter_outlines or {}
            for chapter in chapters:
                if chapter.chapter_number:
                    ch_num = str(chapter.chapter_number)
                    if ch_num in chapter_outlines:
                        chapter_outlines[ch_num]["content_status"] = "generated"
                        chapter_outlines[ch_num]["content_word_count"] = chapter.word_count or len(
                            chapter.final_content or "")
                        chapter_outlines[ch_num]["content_generated_at"] = chapter.updated_at.isoformat(
                        ) if chapter.updated_at else datetime.now().isoformat()
                        updated_count += 1
            project.chapter_outlines = chapter_outlines
            flag_modified(project, 'chapter_outlines')

        elif content_type == 'series_script':
            episode_outlines = project.episode_outlines or {}
            for chapter in chapters:
                if chapter.episode_number:
                    ep_num = str(chapter.episode_number)
                    if ep_num in episode_outlines:
                        episode_outlines[ep_num]["content_status"] = "generated"
                        episode_outlines[ep_num]["content_word_count"] = chapter.word_count or len(
                            chapter.final_content or "")
                        episode_outlines[ep_num]["content_generated_at"] = chapter.updated_at.isoformat(
                        ) if chapter.updated_at else datetime.now().isoformat()
                        updated_count += 1
            project.episode_outlines = episode_outlines
            flag_modified(project, 'episode_outlines')

        elif content_type == 'movie_script':
            scene_outlines = project.scene_outlines or {}
            for chapter in chapters:
                if chapter.scene_number:
                    sc_num = str(chapter.scene_number)
                    if sc_num in scene_outlines:
                        scene_outlines[sc_num]["content_status"] = "generated"
                        scene_outlines[sc_num]["content_word_count"] = chapter.word_count or len(
                            chapter.final_content or "")
                        scene_outlines[sc_num]["content_generated_at"] = chapter.updated_at.isoformat(
                        ) if chapter.updated_at else datetime.now().isoformat()
                        updated_count += 1
            project.scene_outlines = scene_outlines
            flag_modified(project, 'scene_outlines')

        await db.commit()
        logger.info(f"已同步 {updated_count} 个章节的正文状态: {project.title}")
        return ResponseModel(
            success=True,
            message=f"已同步 {updated_count} 个章节的正文状态",
            data={"updated_count": updated_count}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"同步正文状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 项目专属知识库端点 ====================

@router.post("/projects/{project_id}/build-knowledge-base")
async def build_project_knowledge_base(
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    构建项目专属知识库

    执行流程：
    1. 解析全局大纲内容
    2. 使用GraphRAG生成知识图谱
    3. 存入项目专属向量数据库

    该操作在后台异步执行，可通过 get-knowledge-base-status 查询进度
    """
    try:
        # 查询项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 检查是否有大纲内容
        if not project.outline_content:
            raise HTTPException(status_code=400, detail="项目没有大纲内容，无法构建知识库")

        # 检查是否正在构建中
        if project.kb_status == "building":
            raise HTTPException(status_code=400, detail="知识库正在构建中，请稍后再试")

        # 更新状态为构建中
        project.kb_status = "building"
        project.kb_build_progress = {
            "stage": "initializing",
            "progress": 0,
            "message": "正在初始化知识库...",
            "started_at": datetime.now().isoformat()
        }
        await db.commit()

        # 添加后台任务
        background_tasks.add_task(
            _build_knowledge_base_task,
            project_id=project_id,
            outline_content=project.outline_content,
            graphrag_enabled=project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True
        )

        return ResponseModel(
            success=True,
            message="知识库构建任务已启动，请稍后查询进度",
            data={
                "project_id": project_id,
                "status": "building"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动知识库构建失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _build_knowledge_base_task(
    project_id: int,
    outline_content: str,
    graphrag_enabled: bool
):
    """后台执行知识库构建任务"""
    from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
    from app.agents.llm_manager import llm_manager
    from app.core.database import async_session_maker

    async with async_session_maker() as db:
        try:
            # 获取项目
            query = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                logger.error(f"知识库构建失败: 项目不存在 project_id={project_id}")
                return

            # 更新进度
            project.kb_build_progress = {
                "stage": "initializing",
                "progress": 10,
                "message": "正在初始化知识库...",
                "started_at": datetime.now().isoformat()
            }
            await db.commit()

            # 初始化知识库管理器
            kb_manager = ProjectKnowledgeBase(db=db)

            # 获取LLM提供者
            llm_provider = None
            if graphrag_enabled:
                try:
                    llm_provider = await llm_manager.get_provider_from_db(db, project.user_id)
                except Exception as e:
                    logger.warning(f"获取LLM提供者失败，将使用规则提取: {str(e)}")

            # 更新进度
            project.kb_build_progress = {
                "stage": "extracting_entities",
                "progress": 30,
                "message": "正在提取实体和关系...",
                "started_at": project.kb_build_progress.get("started_at")
            }
            await db.commit()

            # 构建全局大纲图谱
            build_result = await kb_manager.build_global_outline_graph(
                project_id=project_id,
                outline_content=outline_content,
                llm_provider=llm_provider
            )

            if build_result["success"]:
                # 更新项目状态
                project.kb_status = "ready"
                project.project_kb_collection = kb_manager.get_collection_name(
                    project_id)
                project.global_outline_graph_path = build_result["graph_path"]
                project.kb_build_progress = {
                    "stage": "completed",
                    "progress": 100,
                    "message": "知识库构建完成",
                    "entity_count": build_result["entity_count"],
                    "relation_count": build_result["relation_count"],
                    "started_at": project.kb_build_progress.get("started_at"),
                    "completed_at": datetime.now().isoformat()
                }

                logger.info(
                    f"知识库构建完成: project_id={project_id}, "
                    f"entities={build_result['entity_count']}, relations={build_result['relation_count']}"
                )
            else:
                raise Exception(build_result.get("error", "未知错误"))

            await db.commit()

        except Exception as e:
            logger.error(f"知识库构建任务失败: project_id={project_id}, error={str(e)}")

            # 更新失败状态
            try:
                query = select(NovelProject).where(
                    NovelProject.id == project_id)
                result = await db.execute(query)
                project = result.scalar_one_or_none()
                if project:
                    project.kb_status = "failed"
                    project.kb_build_progress = {
                        "stage": "failed",
                        "progress": 0,
                        "message": f"构建失败: {str(e)}",
                        "error": str(e),
                        "started_at": project.kb_build_progress.get("started_at") if project.kb_build_progress else None,
                        "failed_at": datetime.now().isoformat()
                    }
                    await db.commit()
            except Exception as update_error:
                logger.error(f"更新失败状态时出错: {str(update_error)}")


@router.get("/projects/{project_id}/knowledge-base-status")
async def get_knowledge_base_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目知识库构建状态

    返回：
    - status: pending/building/ready/failed
    - progress: 构建进度信息
    - stats: 知识库统计信息
    - is_stale: 状态是否过时（幽灵状态检测）
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        stats = kb_manager.get_kb_stats(project_id)

        # 幽灵状态检测：检查构建任务是否真正在运行
        is_stale = False
        current_status = project.kb_status or "pending"

        if current_status == "building":
            # 检查进度更新时间，判断是否为幽灵状态
            progress_info = project.kb_build_progress or {}
            updated_at_str = progress_info.get(
                "updated_at") or progress_info.get("started_at")

            if updated_at_str:
                try:
                    from datetime import datetime, timedelta
                    updated_at = datetime.fromisoformat(updated_at_str)
                    # 如果超过30分钟没有更新，认为是幽灵状态
                    stale_threshold = timedelta(minutes=30)
                    if datetime.now() - updated_at > stale_threshold:
                        is_stale = True
                        logger.warning(
                            f"检测到知识库构建幽灵状态: project_id={project_id}, last_update={updated_at_str}")
                except Exception as e:
                    logger.warning(f"解析进度时间戳失败: {e}")
            else:
                # 没有时间戳信息，检查是否超过1小时（从项目更新时间判断）
                if project.updated_at:
                    from datetime import datetime, timedelta
                    stale_threshold = timedelta(hours=1)
                    if datetime.now() - project.updated_at > stale_threshold:
                        is_stale = True
                        logger.warning(
                            f"检测到知识库构建幽灵状态（无进度时间戳）: project_id={project_id}")

        return ResponseModel(
            success=True,
            data={
                "status": current_status,
                "progress": project.kb_build_progress,
                "graphrag_enabled": project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True,
                "collection_name": project.project_kb_collection,
                "stats": stats,
                "is_stale": is_stale  # 前端可用于判断是否需要重置
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识库状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/knowledge-graph")
async def get_project_knowledge_graph(
    project_id: int,
    unit_number: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目知识图谱数据（用于可视化）

    参数：
    - unit_number: 单元号，不传则返回全局大纲图谱

    返回：
    - nodes: 节点列表
    - edges: 边列表
    - stats: 统计信息
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_data = kb_manager.get_knowledge_graph_data(
            project_id, unit_number)

        return ResponseModel(
            success=True,
            data=graph_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识图谱失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/build-unit-knowledge-graph")
async def build_unit_knowledge_graph(
    project_id: int,
    unit_number: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    构建单元大纲的知识图谱

    在单元大纲生成完成后调用，将该单元的大纲内容存入知识库

    参数：
    - unit_number: 单元号（章节号/集数/场景号）
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取单元大纲内容
        content_type = project.content_type or "novel"
        unit_outline_content = None

        if content_type == "novel":
            chapter_outlines = project.chapter_outlines or {}
            unit_outline = chapter_outlines.get(str(unit_number), {})
            unit_outline_content = unit_outline.get(
                "detailed_outline") or unit_outline.get("chapter_summary")
        elif content_type == "series_script":
            episode_outlines = project.episode_outlines or {}
            unit_outline = episode_outlines.get(str(unit_number), {})
            unit_outline_content = unit_outline.get(
                "detailed_outline") or unit_outline.get("episode_summary")
        elif content_type == "movie_script":
            scene_outlines = project.scene_outlines or {}
            unit_outline = scene_outlines.get(str(unit_number), {})
            unit_outline_content = unit_outline.get(
                "detailed_outline") or unit_outline.get("scene_summary")

        if not unit_outline_content:
            raise HTTPException(
                status_code=400, detail=f"单元 {unit_number} 没有详细大纲内容")

        # 添加后台任务
        background_tasks.add_task(
            _build_unit_knowledge_graph_task,
            project_id=project_id,
            unit_number=unit_number,
            unit_outline_content=unit_outline_content,
            graphrag_enabled=project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True,
            user_id=project.user_id
        )

        return ResponseModel(
            success=True,
            message=f"单元 {unit_number} 知识图谱构建任务已启动",
            data={
                "project_id": project_id,
                "unit_number": unit_number,
                "status": "building"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动单元知识图谱构建失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _build_unit_knowledge_graph_task(
    project_id: int,
    unit_number: int,
    unit_outline_content: str,
    graphrag_enabled: bool,
    user_id: int
):
    """后台执行单元知识图谱构建任务"""
    from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
    from app.agents.llm_manager import llm_manager
    from app.core.database import async_session_maker

    async with async_session_maker() as db:
        try:
            # 初始化知识库管理器
            kb_manager = ProjectKnowledgeBase(db=db)

            # 获取LLM提供者
            llm_provider = None
            if graphrag_enabled:
                try:
                    llm_provider = await llm_manager.get_provider_from_db(db, user_id)
                except Exception as e:
                    logger.warning(f"获取LLM提供者失败，将使用规则提取: {str(e)}")

            # 构建单元图谱
            build_result = await kb_manager.build_unit_outline_graph(
                project_id=project_id,
                unit_number=unit_number,
                unit_outline_content=unit_outline_content,
                llm_provider=llm_provider
            )

            if build_result["success"]:
                logger.info(
                    f"单元知识图谱构建完成: project_id={project_id}, unit={unit_number}, "
                    f"entities={build_result['entity_count']}, relations={build_result['relation_count']}"
                )
            else:
                logger.error(
                    f"单元知识图谱构建失败: project_id={project_id}, unit={unit_number}, "
                    f"error={build_result.get('error')}"
                )

        except Exception as e:
            logger.error(
                f"单元知识图谱构建任务失败: project_id={project_id}, unit={unit_number}, error={str(e)}")


@router.post("/projects/{project_id}/build-all-unit-graphs")
async def build_all_unit_knowledge_graphs(
    project_id: int,
    unit_numbers: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量构建单元大纲的知识图谱

    参数：
    - unit_numbers: 可选，要构建的单元号列表，逗号分隔（如 "1,2,3"）。不传则构建所有单元。

    返回：
    - 启动的任务信息和待构建单元列表
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        if project.kb_status != "ready":
            raise HTTPException(
                status_code=400, detail="请先构建全局知识库")

        # 获取单元大纲列表
        content_type = project.content_type or "novel"
        unit_outlines = {}
        if content_type == "novel":
            unit_outlines = project.chapter_outlines or {}
        elif content_type == "series_script":
            unit_outlines = project.episode_outlines or {}
        elif content_type == "movie_script":
            unit_outlines = project.scene_outlines or {}

        # 确定要构建的单元
        if unit_numbers:
            # 解析用户指定的单元号
            target_units = [int(u.strip())
                            for u in unit_numbers.split(",") if u.strip().isdigit()]
        else:
            # 构建所有有详细大纲的单元
            target_units = []
            for unit_num, outline in unit_outlines.items():
                detailed = outline.get("detailed_outline") or outline.get(
                    "chapter_summary") or outline.get("episode_summary") or outline.get("scene_summary")
                if detailed:
                    target_units.append(int(unit_num))

        target_units.sort()

        if not target_units:
            return ResponseModel(
                success=False,
                message="没有找到可构建的单元大纲",
                data={"units_to_build": []}
            )

        # 添加后台任务
        background_tasks.add_task(
            _build_all_unit_graphs_task,
            project_id=project_id,
            unit_numbers=target_units,
            unit_outlines=unit_outlines,
            graphrag_enabled=project.kb_graphrag_enabled if project.kb_graphrag_enabled is not None else True,
            user_id=project.user_id
        )

        return ResponseModel(
            success=True,
            message=f"已启动 {len(target_units)} 个单元图谱构建任务",
            data={
                "project_id": project_id,
                "units_to_build": target_units,
                "total_count": len(target_units),
                "status": "building"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动批量单元图谱构建失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _build_all_unit_graphs_task(
    project_id: int,
    unit_numbers: List[int],
    unit_outlines: Dict[str, Any],
    graphrag_enabled: bool,
    user_id: int
):
    """后台执行批量单元知识图谱构建任务"""
    from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
    from app.agents.llm_manager import llm_manager
    from app.core.database import async_session_maker
    from app.services.task_manager import task_manager

    async with async_session_maker() as db:
        try:
            # 初始化知识库管理器
            kb_manager = ProjectKnowledgeBase(db=db)

            # 获取LLM提供者
            llm_provider = None
            if graphrag_enabled:
                try:
                    llm_provider = await llm_manager.get_provider_from_db(db, user_id)
                except Exception as e:
                    logger.warning(f"获取LLM提供者失败: {str(e)}")

            # 创建任务追踪
            await task_manager.create_task(
                project_id, "unit_graph_build",
                total_count=len(unit_numbers)
            )

            success_count = 0
            failed_count = 0

            for i, unit_number in enumerate(unit_numbers):
                # 更新任务进度
                await task_manager.update_task_progress(
                    project_id, "unit_graph_build",
                    completed=i,
                    current_item=f"第{unit_number}单元"
                )

                # 获取单元大纲内容
                outline = unit_outlines.get(str(unit_number), {})
                unit_content = outline.get("detailed_outline") or \
                    outline.get("chapter_summary") or \
                    outline.get("episode_summary") or \
                    outline.get("scene_summary")

                if not unit_content:
                    logger.warning(
                        f"单元 {unit_number} 没有大纲内容，跳过")
                    failed_count += 1
                    continue

                try:
                    build_result = await kb_manager.build_unit_outline_graph(
                        project_id=project_id,
                        unit_number=unit_number,
                        unit_outline_content=unit_content,
                        llm_provider=llm_provider
                    )

                    if build_result["success"]:
                        logger.info(
                            f"单元图谱构建完成: project_id={project_id}, unit={unit_number}, "
                            f"entities={build_result['entity_count']}, relations={build_result['relation_count']}"
                        )
                        success_count += 1
                    else:
                        logger.error(
                            f"单元图谱构建失败: project_id={project_id}, unit={unit_number}, "
                            f"error={build_result.get('error')}"
                        )
                        failed_count += 1

                except Exception as e:
                    logger.error(
                        f"单元图谱构建异常: project_id={project_id}, unit={unit_number}, error={str(e)}")
                    failed_count += 1

                # 每个单元之间稍作等待，避免API限流
                await asyncio.sleep(1)

            # 任务完成
            await task_manager.complete_task(project_id, "unit_graph_build")

            logger.info(
                f"批量单元图谱构建完成: project_id={project_id}, "
                f"success={success_count}, failed={failed_count}"
            )

        except Exception as e:
            logger.error(
                f"批量单元图谱构建任务失败: project_id={project_id}, error={str(e)}")


@router.get("/projects/{project_id}/unit-graphs-status")
async def get_unit_graphs_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目单元图谱状态

    返回所有单元的图谱构建状态，包括：
    - 已构建的单元列表
    - 未构建的单元列表
    - 各单元图谱的统计信息
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
        import os

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_dir = kb_manager.settings.get_knowledge_graph_dir()

        # 获取单元大纲列表
        content_type = project.content_type or "novel"
        unit_outlines = {}
        if content_type == "novel":
            unit_outlines = project.chapter_outlines or {}
        elif content_type == "series_script":
            unit_outlines = project.episode_outlines or {}
        elif content_type == "movie_script":
            unit_outlines = project.scene_outlines or {}

        # 检查各单元图谱状态
        built_units = []
        unbuilt_units = []

        for unit_num, outline in unit_outlines.items():
            unit_number = int(unit_num)
            has_outline = bool(
                outline.get("detailed_outline") or
                outline.get("chapter_summary") or
                outline.get("episode_summary") or
                outline.get("scene_summary")
            )

            graph_path = kb_manager.get_graph_path(project_id, unit_number)
            has_graph = os.path.exists(graph_path)

            unit_info = {
                "unit_number": unit_number,
                "has_outline": has_outline,
                "has_graph": has_graph
            }

            if has_graph:
                # 获取图谱统计
                try:
                    graph_data = kb_manager.get_knowledge_graph_data(
                        project_id, unit_number)
                    unit_info["node_count"] = graph_data.get(
                        "stats", {}).get("node_count", 0)
                    unit_info["edge_count"] = graph_data.get(
                        "stats", {}).get("edge_count", 0)
                except:
                    unit_info["node_count"] = 0
                    unit_info["edge_count"] = 0
                built_units.append(unit_info)
            elif has_outline:
                unbuilt_units.append(unit_info)

        # 排序
        built_units.sort(key=lambda x: x["unit_number"])
        unbuilt_units.sort(key=lambda x: x["unit_number"])

        return ResponseModel(
            success=True,
            data={
                "project_id": project_id,
                "total_units": len(unit_outlines),
                "built_count": len(built_units),
                "unbuilt_count": len(unbuilt_units),
                "built_units": built_units,
                "unbuilt_units": unbuilt_units
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取单元图谱状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/knowledge-base-config")
async def update_knowledge_base_config(
    project_id: int,
    graphrag_enabled: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新项目知识库配置

    参数：
    - graphrag_enabled: 是否启用GraphRAG
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        if graphrag_enabled is not None:
            project.kb_graphrag_enabled = graphrag_enabled

        await db.commit()

        return ResponseModel(
            success=True,
            message="知识库配置已更新",
            data={
                "graphrag_enabled": project.kb_graphrag_enabled
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新知识库配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/knowledge-base")
async def delete_project_knowledge_base(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除项目知识库

    删除向量数据库和知识图谱文件，重置知识库状态
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        success = await kb_manager.delete_project_kb(project_id)

        if success:
            # 重置项目知识库状态
            project.kb_status = "pending"
            project.project_kb_collection = None
            project.global_outline_graph_path = None
            project.kb_build_progress = None
            await db.commit()

            return ResponseModel(
                success=True,
                message="知识库已删除"
            )
        else:
            raise HTTPException(status_code=500, detail="删除知识库失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除知识库失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/knowledge-base/reset-status")
async def reset_knowledge_base_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    重置知识库构建状态

    用于处理以下情况：
    1. 清除幽灵状态（状态显示构建中但实际无任务运行）
    2. 取消正在进行的构建任务
    3. 清除失败的构建状态

    注意：此操作不会删除已构建的知识库数据，仅重置状态
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        previous_status = project.kb_status
        previous_progress = project.kb_build_progress

        # 重置状态为 pending 或 ready（取决于是否有已构建的知识库）
        if project.project_kb_collection and project.global_outline_graph_path:
            # 如果有已构建的知识库数据，恢复为 ready 状态
            project.kb_status = "ready"
            new_status = "ready"
        else:
            # 否则重置为 pending
            project.kb_status = "pending"
            new_status = "pending"

        # 清除构建进度信息
        project.kb_build_progress = None
        await db.commit()

        logger.info(
            f"重置知识库状态: project_id={project_id}, {previous_status} -> {new_status}")

        return ResponseModel(
            success=True,
            message=f"知识库状态已重置",
            data={
                "previous_status": previous_status,
                "new_status": new_status,
                "previous_progress": previous_progress
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置知识库状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
