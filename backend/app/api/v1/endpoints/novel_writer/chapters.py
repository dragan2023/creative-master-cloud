"""
小说/剧本正文生成 API 端点 - 章节管理模块

包含章节目录、章节内容、场景管理、分集大纲、导出等功能

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
import json
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import (
    ResourceNotFoundException, ValidationException, AuthorizationException,
    AppException, ErrorCode
)

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, NovelProject, NovelChapter, ProjectStatus, ChapterStatus
from app.schemas.common import ResponseModel
from app.schemas.novel_writer import (
    DirectoryGenerateRequest, DirectoryResponse,
    DirectoryUpdateRequest, ChapterMetadata,
    ChapterContentResponse, ChapterContentUpdate, ChapterListResponse,
    ExportRequest,
    # 剧本专用
    CharacterInfo, CharacterListResponse,
    # 分集详细大纲
    EpisodeOutlineUpdate, EpisodeOutlineResponse, EpisodeOutlineListResponse, EpisodeOutlineScene
)
from app.services.novel_writer.exporter import NovelExporter

from .utils import router, settings, logger, get_project_data_dir, extract_chapter_count


# ==================== 章节目录 API ====================

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
            raise ResourceNotFoundException("项目不存在")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取目录失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/projects/{project_id}/generate-directory", response_model=ResponseModel[DirectoryResponse])
async def generate_directory(
    project_id: int,
    request: DirectoryGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成章节目录

    根据请求参数创建章节记录，可选择使用LLM预生成章节名称
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
            raise ResourceNotFoundException("项目不存在")

        if not project.outline_content:
            raise ValidationException("项目未上传大纲，无法生成目录")

        # 删除现有章节（如果存在）
        delete_query = delete(NovelChapter).where(
            NovelChapter.project_id == project_id
        )
        await db.execute(delete_query)
        await db.commit()

        # 更新项目总章节数
        project.total_chapters = request.total_chapters
        project.status = ProjectStatus.DIRECTORY
        await db.commit()

        chapters_data = []

        # 如果使用LLM预生成章节名称
        if request.generate_names and project.outline_content:
            try:
                from app.agents.llm_manager import get_llm_manager
                from app.services.novel_writer import DIRECTORY_GENERATE_PROMPT
                from app.core.config import PRESET_MODELS
                from app.models.writing_model_config import WritingModelConfig
                from app.models.api_key import UserAPIKey
                from app.core.security import api_key_encryption

                # 获取LLM管理器
                llm_manager = get_llm_manager()
                
                # 初始化变量
                provider_name = None
                model_name = None
                api_key = None
                api_base = None
                
                # 优先级1：从 WritingModelConfig 获取用户配置的模型
                wmc_stmt = select(WritingModelConfig).where(
                    WritingModelConfig.user_id == current_user.id,
                    WritingModelConfig.is_active == True
                ).order_by(WritingModelConfig.updated_at.desc())
                wmc_result = await db.execute(wmc_stmt)
                wmc_config = wmc_result.scalar_one_or_none()
                
                if wmc_config:
                    provider_name = wmc_config.provider
                    model_name = wmc_config.model_id
                    api_base = wmc_config.api_base
                    api_key = api_key_encryption.decrypt(wmc_config.encrypted_key)
                    logger.info(f"使用 WritingModelConfig 配置: provider={provider_name}, model={model_name}")
                
                # 优先级2：从 UserAPIKey 获取配置
                if not provider_name:
                    api_key_stmt = select(UserAPIKey).where(
                        UserAPIKey.user_id == current_user.id,
                        UserAPIKey.is_valid == True
                    ).order_by(UserAPIKey.is_default.desc())
                    api_key_result = await db.execute(api_key_stmt)
                    api_key_record = api_key_result.scalar_one_or_none()
                    
                    if api_key_record:
                        provider_name = api_key_record.provider
                        api_key = api_key_encryption.decrypt(api_key_record.encrypted_key)
                        model_name = api_key_record.model_name
                        api_base = api_key_record.api_base
                        
                        # 获取预设配置补充信息
                        preset = PRESET_MODELS.get(provider_name, {})
                        if not model_name:
                            model_name = preset.get("default_model")
                        if not api_base:
                            api_base = preset.get("api_base")
                        logger.info(f"使用 UserAPIKey 配置: provider={provider_name}, model={model_name}")
                
                # 优先级3：检查是否获取到配置
                if not provider_name or not api_key:
                    raise ValueError("未找到可用的模型配置，请先在正文项目的'模型配置'中添加模型，或在系统设置中配置API Key")
                
                # 创建provider
                provider = llm_manager.create_provider(
                    provider_name=provider_name,
                    api_key=api_key,
                    model_name=model_name,
                    api_base=api_base
                )
                
                # 构建提示词
                prompt = DIRECTORY_GENERATE_PROMPT.format(
                    project_type=project.content_type or "小说",
                    total_chapters=request.total_chapters,
                    genre=project.genre or "未指定",
                    target_platform=project.target_platform or "未指定",
                    outline_content=project.outline_content[:5000]  # 限制大纲长度
                )

                # 调用LLM生成章节信息
                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=None,
                    temperature=0.7,
                    max_tokens=4000
                )
                response_text = response.content

                # 解析JSON响应
                import re

                # 提取JSON内容
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    generated_chapters = json.loads(json_match.group())
                else:
                    generated_chapters = []

                # 创建章节记录
                for i, ch_info in enumerate(generated_chapters[:request.total_chapters], 1):
                    chapter = NovelChapter(
                        project_id=project_id,
                        chapter_number=i,
                        chapter_title=ch_info.get("chapter_title", f"第{i}章"),
                        chapter_metadata={
                            "chapter_role": ch_info.get("chapter_role"),
                            "chapter_purpose": ch_info.get("chapter_purpose"),
                            "suspense_level": ch_info.get("suspense_level"),
                            "foreshadowing": ch_info.get("foreshadowing"),
                            "plot_twist_level": ch_info.get("plot_twist_level"),
                            "chapter_summary": ch_info.get("chapter_summary")
                        },
                        status=ChapterStatus.PENDING
                    )
                    db.add(chapter)

                    chapters_data.append(ChapterMetadata(
                        chapter_number=i,
                        chapter_title=chapter.chapter_title,
                        chapter_role=ch_info.get("chapter_role"),
                        chapter_purpose=ch_info.get("chapter_purpose"),
                        suspense_level=ch_info.get("suspense_level"),
                        foreshadowing=ch_info.get("foreshadowing"),
                        plot_twist_level=ch_info.get("plot_twist_level"),
                        chapter_summary=ch_info.get("chapter_summary")
                    ))

                # 补充剩余章节（如果LLM生成的章节数不足）
                for i in range(len(chapters_data) + 1, request.total_chapters + 1):
                    chapter = NovelChapter(
                        project_id=project_id,
                        chapter_number=i,
                        chapter_title=f"第{i}章",
                        status=ChapterStatus.PENDING
                    )
                    db.add(chapter)

                    chapters_data.append(ChapterMetadata(
                        chapter_number=i,
                        chapter_title=f"第{i}章"
                    ))

            except Exception as e:
                logger.warning(f"LLM生成章节名称失败: {str(e)}，使用默认章节名")
                # 回退到默认章节名
                chapters_data = []
                for i in range(1, request.total_chapters + 1):
                    chapter = NovelChapter(
                        project_id=project_id,
                        chapter_number=i,
                        chapter_title=f"第{i}章",
                        status=ChapterStatus.PENDING
                    )
                    db.add(chapter)

                    chapters_data.append(ChapterMetadata(
                        chapter_number=i,
                        chapter_title=f"第{i}章"
                    ))
        else:
            # 不使用LLM，创建默认章节
            for i in range(1, request.total_chapters + 1):
                chapter = NovelChapter(
                    project_id=project_id,
                    chapter_number=i,
                    chapter_title=f"第{i}章",
                    status=ChapterStatus.PENDING
                )
                db.add(chapter)

                chapters_data.append(ChapterMetadata(
                    chapter_number=i,
                    chapter_title=f"第{i}章"
                ))

        await db.commit()

        logger.info(f"目录生成成功: 项目{project_id}, 共{request.total_chapters}章")

        return ResponseModel(
            success=True,
            data=DirectoryResponse(
                project_id=project.id,
                total_chapters=request.total_chapters,
                chapters=chapters_data
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"生成目录失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, f"生成目录失败: {str(e)}")


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
            raise ResourceNotFoundException("章节不存在")

        # 验证用户权限
        project_query = select(NovelProject).where(
            NovelProject.id == project_id)
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()

        if not project or project.user_id != current_user.id:
            raise AuthorizationException(message="无权访问此章节")

        # 更新标题
        chapter.chapter_title = title
        await db.commit()

        logger.info(f"章节标题更新: 第{chapter_num}章 -> {title}")

        return ResponseModel(
            success=True,
            message="章节标题已更新"
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新章节标题失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("项目不存在")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取章节列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("章节不存在")

        # 验证用户权限
        project_query = select(NovelProject).where(
            NovelProject.id == project_id)
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()

        if not project or project.user_id != current_user.id:
            raise AuthorizationException(message="无权访问此章节")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取章节内容失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("章节不存在")

        # 更新内容
        chapter.final_content = request.content
        chapter.word_count = len(request.content)
        chapter.user_edited = 1

        await db.commit()

        logger.info(f"章节内容更新: 第{chapter_num}章")

        return ResponseModel(success=True, message="章节内容已更新")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新章节失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("项目不存在")

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
            raise AppException(ErrorCode.INTERNAL_ERROR, export_result.get("error_message", "导出失败"))

        # 返回文件
        return FileResponse(
            path=export_result["file_path"],
            filename=export_result["file_name"],
            media_type="application/octet-stream"
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"导出失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 剧本场景 API ====================

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
            raise ResourceNotFoundException("项目不存在")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取场景列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("项目不存在")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取角色列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 分集详细大纲 API ====================

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
            raise ResourceNotFoundException("项目不存在")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取分集大纲列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("项目不存在")

        # 获取分集大纲
        episode_outlines = project.episode_outlines or {}
        ep_outline = episode_outlines.get(str(episode))

        if not ep_outline:
            raise ResourceNotFoundException(f"第{episode}集的详细大纲尚未生成")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取分集大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("项目不存在")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新分集大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("项目不存在")

        # 删除大纲
        episode_outlines = project.episode_outlines or {}
        if str(episode) in episode_outlines:
            del episode_outlines[str(episode)]
            project.episode_outlines = episode_outlines
            await db.commit()
            logger.info(f"第{episode}集详细大纲已删除: {project.title}")
            return ResponseModel(success=True, message=f"第{episode}集详细大纲已删除")
        else:
            raise ResourceNotFoundException(f"第{episode}集的详细大纲不存在")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除分集大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


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
            raise ResourceNotFoundException("项目不存在")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"同步正文状态失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


