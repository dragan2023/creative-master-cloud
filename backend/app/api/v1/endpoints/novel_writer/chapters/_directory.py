import os
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import (
    ResourceNotFoundException, ValidationException, AuthorizationException,
    AppException, ErrorCode
)
from app.models import User, NovelProject, NovelChapter, ProjectStatus, ChapterStatus
from app.schemas.common import ResponseModel
from app.schemas.novel_writer import (
    DirectoryGenerateRequest, DirectoryResponse,
    DirectoryUpdateRequest, ChapterMetadata,
    ChapterContentResponse, ChapterContentUpdate, ChapterListResponse,
    ExportRequest,
    CharacterInfo, CharacterListResponse,
    EpisodeOutlineUpdate, EpisodeOutlineResponse, EpisodeOutlineListResponse, EpisodeOutlineScene
)
from app.services.novel_writer.exporter import NovelExporter
from ..utils import settings, logger, get_project_data_dir, extract_chapter_count


async def get_directory(
    project_id: int,
    current_user: User,
    db: AsyncSession
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




async def generate_directory(
    project_id: int,
    request: DirectoryGenerateRequest,
    current_user: User,
    db: AsyncSession
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
                    outline_content=project.outline_content  # 不再截断大纲
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




async def update_chapter_title(
    project_id: int,
    chapter_num: int,
    title: str,
    current_user: User,
    db: AsyncSession
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
