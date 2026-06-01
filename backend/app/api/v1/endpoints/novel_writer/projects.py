"""
小说/剧本生成模块 - 项目管理 API 端点

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
from typing import Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.exceptions import ResourceNotFoundException, ValidationException, AppException, ErrorCode

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, NovelProject, ProjectType, ProjectStatus
from app.schemas.common import ResponseModel
from app.schemas.novel_writer import (
    NovelProjectCreate, NovelProjectUpdate, NovelProjectResponse, NovelProjectListResponse,
    ContentType, NovelConfig, SeriesScriptConfig, MovieScriptConfig
)

from .utils import (
    router, logger, generate_project_code, get_project_data_dir, _build_project_response
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

        # [已废弃] 处理知识图谱继承（v4.2遗留功能：当前四阶段流程不再构建知识图谱，保留代码仅向后兼容）
        if request.inherit_kb_from_project_id:
            try:
                # 安全校验：确认源项目归属当前用户
                src_query = select(NovelProject).where(
                    NovelProject.id == request.inherit_kb_from_project_id,
                    NovelProject.user_id == current_user.id
                )
                src_result = await db.execute(src_query)
                src_project = src_result.scalar_one_or_none()
                if not src_project:
                    raise ValidationException("源项目不存在或无权访问")
                if src_project.kb_status != "ready":
                    raise ValidationException("源项目知识图谱未就绪，无法继承")

                from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
                kb_manager = ProjectKnowledgeBase(db=db)
                inherit_result = await kb_manager.inherit_knowledge_graph(
                    src_project_id=request.inherit_kb_from_project_id,
                    dst_project_id=project.id
                )
                if inherit_result.get("success"):
                    project.kb_status = "ready"
                    project.global_outline_graph_path = kb_manager.get_graph_path(project.id)
                    project.project_kb_collection = kb_manager.get_collection_name(project.id)
                    project.kb_build_progress = {
                        "stage": "inherited",
                        "progress": 100,
                        "message": "知识图谱已从源项目继承",
                        "entity_count": inherit_result.get("entity_count", 0),
                        "relation_count": inherit_result.get("relation_count", 0),
                    }
                    await db.commit()
                    logger.info(
                        f"[图谱继承] 项目 {project.id} 已继承源项目 "
                        f"{request.inherit_kb_from_project_id} 的知识图谱, "
                        f"entities={inherit_result.get('entity_count')}, "
                        f"relations={inherit_result.get('relation_count')}")
                else:
                    logger.error(
                        f"[图谱继承] 继承失败: src={request.inherit_kb_from_project_id}, "
                        f"dst={project.id}, error={inherit_result.get('error')}")
            except AppException:
                # 校验异常（如源项目不存在/未就绪）向上传播
                raise
            except Exception as inherit_error:
                logger.error(
                    f"[图谱继承] 异常: src={request.inherit_kb_from_project_id}, "
                    f"dst={project.id}, error={inherit_error!r}")
                # 技术性异常不影响项目创建（如文件不存在、向量库写入失败）

        logger.info(
            f"创建项目成功: {project.title} ({project.project_code}), 类型: {content_type.value}")

        return ResponseModel(
            success=True,
            data=_build_project_response(project)
        )

    except Exception as e:
        logger.error(f"创建项目失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("项目不存在")

        return ResponseModel(
            success=True,
            data=_build_project_response(project)
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取项目详情失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("项目不存在")

        # 更新基本字段
        if request.title:
            project.title = request.title
        if request.genre:
            project.genre = request.genre
        
        # 更新大纲内容
        if request.outline_content is not None:
            project.outline_content = request.outline_content

        # 更新单元概述
        if request.unit_summaries is not None:
            project.unit_summaries = request.unit_summaries
            project.unit_summaries_status = 'completed'
            # 同步更新总章节数
            project.total_chapters = len(request.unit_summaries)

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新项目失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("项目不存在")

        # 删除项目文件
        if project.project_code:
            project_dir = get_project_data_dir(project.project_code)
            if os.path.exists(project_dir):
                import shutil
                shutil.rmtree(project_dir)

        # 清理知识图谱文件和数据
        try:
            from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
            kb_manager = ProjectKnowledgeBase(db=db)
            await kb_manager.delete_project_kb(project_id)
            logger.info(f"知识图谱已清理: project_id={project_id}")
        except Exception as kb_error:
            logger.warning(f"清理知识图谱失败（继续删除项目）: {kb_error}")

        # 删除数据库记录（级联删除章节）
        await db.delete(project)
        await db.commit()

        logger.info(f"删除项目成功: {project.title}")

        return ResponseModel(success=True, message="项目已删除")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除项目失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))
