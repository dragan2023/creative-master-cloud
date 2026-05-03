"""大纲管理 - CRUD端点（章节大纲/场景大纲 获取/更新/删除）+ 生成端点"""
import re
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import (
    ResourceNotFoundException, ValidationException, AppException, ErrorCode
)
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, NovelProject
from app.schemas.common import ResponseModel
from app.schemas.novel_writer import (
    ChapterOutlineBase, ChapterOutlineCreate, ChapterOutlineUpdate, ChapterOutlineResponse,
    ChapterOutlineListResponse, ChapterOutlineGenerateRequest,
    SceneOutlineBase, SceneOutlineCreate, SceneOutlineUpdate, SceneOutlineResponse,
    SceneOutlineListResponse, SceneOutlineGenerateRequest
)

from ..utils import router, logger
from ._models import (
    UnitSummariesQualityControlRequest, UnitSummariesQualityControlResponse,
    OutlineInterventionRequest
)
from ._upload import extract_chapter_count


# ==================== 章节详细大纲 API（小说专用） ====================

@router.get("/projects/{project_id}/chapter-outlines", response_model=ResponseModel[ChapterOutlineListResponse])
async def get_chapter_outlines(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取所有章节详细大纲（小说专用）"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        chapter_outlines = project.chapter_outlines or {}
        total_chapters = project.total_chapters or 0

        if total_chapters == 0 and project.outline_content:
            total_chapters = extract_chapter_count(project.outline_content, "novel")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取章节大纲列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/chapter-outlines/{chapter_num}", response_model=ResponseModel[ChapterOutlineResponse])
async def get_chapter_outline(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个章节详细大纲（小说专用）"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        chapter_outlines = project.chapter_outlines or {}
        ch_outline = chapter_outlines.get(str(chapter_num))

        if not ch_outline:
            raise ResourceNotFoundException(f"第{chapter_num}章的详细大纲尚未生成")

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
                original_content=ch_outline.get("original_content"),
                revision_info=ch_outline.get("revision_info")
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取章节大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.put("/projects/{project_id}/chapter-outlines/{chapter_num}")
async def update_chapter_outline(
    project_id: int,
    chapter_num: int,
    request: ChapterOutlineUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新章节详细大纲（小说专用）"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

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

        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                ch_outline[key] = value

        ch_outline["status"] = "edited"
        ch_outline["updated_at"] = datetime.now().isoformat()

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新章节大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/projects/{project_id}/chapter-outlines/{chapter_num}")
async def delete_chapter_outline(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除章节详细大纲（小说专用）"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        chapter_outlines = project.chapter_outlines or {}
        if str(chapter_num) in chapter_outlines:
            del chapter_outlines[str(chapter_num)]
            project.chapter_outlines = chapter_outlines
            flag_modified(project, 'chapter_outlines')
            await db.commit()
            logger.info(f"第{chapter_num}章详细大纲已删除: {project.title}")
            return ResponseModel(success=True, message=f"第{chapter_num}章详细大纲已删除")
        else:
            raise ResourceNotFoundException(f"第{chapter_num}章的详细大纲不存在")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除章节大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 场景详细大纲 API（电影剧本专用） ====================

@router.get("/projects/{project_id}/scene-outlines", response_model=ResponseModel[SceneOutlineListResponse])
async def get_scene_outlines(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取所有场景详细大纲（电影剧本专用）"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        scene_outlines = project.scene_outlines or {}
        total_scenes = project.total_chapters or 0

        if total_scenes == 0 and project.outline_content:
            total_scenes = extract_chapter_count(project.outline_content, "movie_script")

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

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取场景大纲列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 章节大纲生成提示词 ====================

CHAPTER_OUTLINE_GENERATE_PROMPT = """你是一位专业的小说大纲撰写专家。请根据以下信息，为指定章节生成详细的章节大纲。

## 项目信息
- 书名：{title}
- 类型：{genre}
- 基调：{tone}

## 全局大纲摘要
{global_outline_summary}

## 章节简要概述
- 章节：第{chapter_num}章
- 标题：{chapter_title}
- 概要：{chapter_summary}

## 输出要求

请为第{chapter_num}章生成一份详细的章节大纲，包含以下内容：

1. **章节标题**：保持原标题或优化
2. **章节概要**（200-300字）：完整描述本章的情节发展，包含开端、发展、转折、结尾
3. **详细大纲**（500-800字）：按场景或情节节点展开，描写具体的情节发展、人物互动、场景转换
4. **关键事件**（3-5个）：列出本章的关键情节点
5. **角色发展**：描述本章中主要角色的成长或变化
6. **悬念设置**：本章的悬念或钩子，引出下一章
7. **情感基调**：本章的情感氛围

## 输出格式（JSON）

请严格按照以下JSON格式输出：

```json
{{
    "chapter_number": {chapter_num},
    "chapter_title": "章节标题",
    "chapter_summary": "200-300字的章节概要",
    "detailed_outline": "500-800字的详细大纲",
    "key_events": ["事件1", "事件2", "事件3"],
    "character_arcs": "角色发展描述",
    "suspense_points": "悬念设置",
    "emotional_tone": "情感基调"
}}
```

请直接输出JSON内容，不要包含markdown代码块标记。
"""


# ==================== 章节大纲生成 API ====================

_chapter_outline_tasks: Dict[int, Dict[str, Any]] = {}


@router.post("/projects/{project_id}/generate-chapter-outlines")
async def generate_chapter_outlines(
    project_id: int,
    request: ChapterOutlineGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成章节详细大纲（小说专用）"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        if project.content_type and project.content_type != "novel":
            raise ValidationException("此功能仅适用于小说类型项目")

        global_outline = project.outline_content or ""
        unit_summaries = project.unit_summaries or {}
        if not unit_summaries:
            raise ValidationException("请先生成单元概述（第二阶段大纲）")

        total_chapters = project.total_chapters or len(unit_summaries)
        existing_outlines = project.chapter_outlines or {}

        if request.chapter_numbers:
            chapters_to_generate = request.chapter_numbers
        elif request.start_unit is not None:
            start = request.start_unit
            if request.unit_count is not None:
                end = min(start + request.unit_count - 1, total_chapters)
            else:
                end = total_chapters
            chapters_to_generate = list(range(start, end + 1))

            if request.skip_existing:
                chapters_to_generate = [
                    ch for ch in chapters_to_generate
                    if str(ch) not in existing_outlines or
                    existing_outlines[str(ch)].get("status") == "pending"
                ]
        else:
            chapters_to_generate = [
                i for i in range(1, total_chapters + 1)
                if str(i) not in existing_outlines or
                existing_outlines[str(i)].get("status") == "pending"
            ]

        if not chapters_to_generate:
            return ResponseModel(
                success=True,
                message="所有章节的详细大纲已存在",
                data={
                    "generated": [],
                    "failed": [],
                    "total_chapters": total_chapters,
                    "generated_count": len(existing_outlines)
                }
            )

        # 获取LLM配置
        from app.agents.llm_manager import get_llm_manager
        from app.models.writing_model_config import WritingModelConfig
        from app.models.api_key import UserAPIKey
        from app.core.security import api_key_encryption
        from app.core.config import PRESET_MODELS

        llm_manager = get_llm_manager()
        provider_name = None
        model_name = None
        api_key = None
        api_base = None

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
            try:
                api_key = api_key_encryption.decrypt(wmc_config.encrypted_key)
                logger.info(f"使用 WritingModelConfig: provider={provider_name}, model={model_name}")
            except Exception as decrypt_error:
                logger.warning(f"WritingModelConfig API密钥解密失败: {decrypt_error}")
                provider_name = None
                model_name = None
                api_key = None
                api_base = None

        if not provider_name:
            api_key_stmt = select(UserAPIKey).where(
                UserAPIKey.user_id == current_user.id,
                UserAPIKey.is_valid == True
            ).order_by(UserAPIKey.is_default.desc())
            api_key_result = await db.execute(api_key_stmt)
            api_key_record = api_key_result.scalar_one_or_none()

            if api_key_record:
                provider_name = api_key_record.provider
                model_name = api_key_record.model_name
                api_base = api_key_record.api_base
                try:
                    api_key = api_key_encryption.decrypt(api_key_record.encrypted_key)
                except Exception as decrypt_error:
                    logger.warning(f"UserAPIKey 解密失败: {decrypt_error}")
                    api_key_record.is_valid = False
                    await db.commit()
                    raise ValidationException("API密钥解密失败，SECRET_KEY可能已变更，请重新配置API密钥")

                preset = PRESET_MODELS.get(provider_name, {})
                if not model_name:
                    model_name = preset.get("default_model")
                if not api_base:
                    api_base = preset.get("api_base")

        if not provider_name or not api_key:
            raise ValidationException("请先配置API密钥")

        try:
            provider = llm_manager.create_provider(
                provider_name=provider_name,
                api_key=api_key,
                model_name=model_name,
                api_base=api_base
            )
        except ValueError as e:
            raise ValidationException(str(e))

        global_outline_summary = global_outline  # 不再截断大纲，LLM 上下文由模型自行处理

        generated = []
        failed = []
        updated_outlines = dict(existing_outlines)

        for chapter_num in chapters_to_generate:
            try:
                unit_key = str(chapter_num)
                unit_data = unit_summaries.get(unit_key, {})
                chapter_title = unit_data.get("title", f"第{chapter_num}章")
                chapter_summary = unit_data.get("summary", "")

                if not chapter_summary:
                    logger.warning(f"章节 {chapter_num} 没有简要概述，跳过")
                    continue

                novel_config = project.novel_config or {}
                prompt = CHAPTER_OUTLINE_GENERATE_PROMPT.format(
                    title=project.title or "未命名",
                    genre=project.genre or "未指定",
                    tone=novel_config.get("tone", "正剧"),
                    global_outline_summary=global_outline_summary,
                    chapter_num=chapter_num,
                    chapter_title=chapter_title,
                    chapter_summary=chapter_summary
                )

                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=None,
                    temperature=0.7,
                    max_tokens=2000
                )
                response_text = response.content.strip()

                if response_text.startswith("```"):
                    response_text = re.sub(r'^```\w*\n?', '', response_text)
                    response_text = re.sub(r'\n?```$', '', response_text)

                outline_data = json.loads(response_text)
                outline_data["chapter_number"] = chapter_num
                outline_data["status"] = "generated"
                outline_data["created_at"] = datetime.now().isoformat()
                outline_data["updated_at"] = datetime.now().isoformat()

                updated_outlines[str(chapter_num)] = outline_data
                generated.append(chapter_num)
                logger.info(f"章节 {chapter_num} 详细大纲生成成功")

            except json.JSONDecodeError as e:
                logger.error(f"章节 {chapter_num} JSON解析失败: {str(e)}")
                failed.append({"chapter": chapter_num, "error": "JSON解析失败"})
                if request.stop_on_error:
                    break
            except Exception as e:
                logger.error(f"章节 {chapter_num} 生成失败: {str(e)}")
                failed.append({"chapter": chapter_num, "error": str(e)})
                if request.stop_on_error:
                    break

        if generated:
            project.chapter_outlines = updated_outlines
            flag_modified(project, 'chapter_outlines')
            await db.commit()

        return ResponseModel(
            success=len(generated) > 0,
            message=f"成功生成 {len(generated)} 个章节详细大纲",
            data={
                "generated": generated,
                "failed": failed,
                "total_chapters": total_chapters,
                "generated_count": len(updated_outlines)
            }
        )

    except AppException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e) if str(e) else repr(e)
        logger.error(f"生成章节详细大纲失败: {error_detail}\n{traceback.format_exc()}")
        raise AppException(ErrorCode.INTERNAL_ERROR, error_detail or "内部服务器错误")


# ==================== 单元概述质控触发 API ====================

@router.post("/projects/{project_id}/unit-summaries/quality-control",
             response_model=ResponseModel[UnitSummariesQualityControlResponse])
async def trigger_unit_summaries_quality_control(
    project_id: int,
    request: UnitSummariesQualityControlRequest = UnitSummariesQualityControlRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """手动触发单元概述质控检测"""
    try:
        from app.services.outline_generator import OutlineGenerator
        from app.services.quality_control import QualityControlService
        from app.agents.llm_manager import get_llm_manager

        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        if project.unit_summaries_status == 'quality_control_running':
            raise ValidationException("质控检测正在进行中,请勿重复触发")

        unit_summaries = project.unit_summaries or {}
        global_outline = project.global_outline_content or project.outline_content or ""
        content_type = project.content_type or "novel"

        if not unit_summaries:
            raise ValidationException("项目暂无单元概述数据")

        logger.info(
            f"[单元概述质控] 开始质控检测: "
            f"project_id={project_id}, units={len(unit_summaries)}, content_type={content_type}"
        )

        original_status = project.unit_summaries_status
        project.unit_summaries_status = 'quality_control_running'
        await db.commit()

        try:
            chapters_data = []
            for unit_num, unit_data in unit_summaries.items():
                chapters_data.append({
                    "id": int(unit_num),
                    "unit_id": unit_data.get("unit_id", f"unit-{unit_num}"),
                    "chapter_number": int(unit_num),
                    "content": unit_data.get("full_content", "") or unit_data.get("summary", ""),
                    "summary": unit_data.get("summary", ""),
                    "full_content": unit_data.get("full_content", ""),
                    "title": unit_data.get("title", ""),
                    "status": "completed"
                })

            qc_service = QualityControlService(db=db)
            outline_generator = OutlineGenerator(db=db)

            quality_report = await outline_generator._analyze_unit_summaries_quality(
                qc_service=qc_service,
                chapters_data=chapters_data,
                dimensions=["unit_structure", "unit_character", "unit_consistency", "unit_timeline_space", "unit_ooc"],
                depth="deep",
                global_outline=global_outline,
                user_id=current_user.id
            )

            logger.info(f"[单元概述质控] 质控分析完成: 发现{len(quality_report.get('issues', []))}个问题")

            revision_summary = []
            revised_count = 0

            if request.enable_auto_revision:
                critical_issues = [
                    issue for issue in quality_report.get("issues", [])
                    if issue.get("severity") == "critical"
                ]

                if critical_issues:
                    logger.info(f"[单元概述质控] 发现{len(critical_issues)}个严重问题,开始自动修正")

                    revision_prompt = outline_generator._build_quality_revision_prompt(
                        unit_summaries=unit_summaries,
                        quality_report_dict=quality_report,
                        global_outline=global_outline,
                        content_type=content_type
                    )

                    llm_manager = get_llm_manager()
                    llm_provider = await llm_manager.get_provider_from_db(db, current_user.id)

                    if llm_provider:
                        revision_response = await llm_provider.generate(
                            prompt=revision_prompt, temperature=0.7
                        )

                        revised_parsed = outline_generator._parse_quality_revision_result(
                            revision_response.content, unit_summaries
                        )

                        if revised_parsed:
                            for unit_num, revised_data in revised_parsed.items():
                                if unit_num in unit_summaries:
                                    original = unit_summaries[unit_num].get("summary", "")
                                    revised = revised_data.get("summary", original)

                                    if original != revised:
                                        revision_summary.append({
                                            "unit_number": int(unit_num),
                                            "unit_title": unit_summaries[unit_num].get("title", ""),
                                            "original_summary": original,
                                            "revised_summary": revised,
                                            "revision_reason": revised_data.get("revision_reason", "")
                                        })

                            updated_summaries = {**unit_summaries}
                            for unit_num, revised_data in revised_parsed.items():
                                if unit_num in updated_summaries:
                                    original_unit = updated_summaries[unit_num]
                                    updated_summaries[unit_num] = {
                                        **original_unit,
                                        "summary": revised_data.get("summary", original_unit.get("summary", "")),
                                        "quality_revised": True,
                                        "revision_reason": revised_data.get("revision_reason", ""),
                                        "revised_at": datetime.now().isoformat()
                                    }

                            project.unit_summaries = updated_summaries
                            flag_modified(project, 'unit_summaries')
                            await db.commit()

                            revised_count = len(revision_summary)
                            logger.info(f"[单元概述质控] 自动修正完成: 修正{revised_count}个单元")
                    else:
                        logger.warning("[单元概述质控] 无法获取LLM提供商,跳过自动修正")
                else:
                    logger.info("[单元概述质控] 无严重问题,无需修正")
            else:
                logger.info("[单元概述质控] 用户禁用自动修正")

            message = f"质控完成,发现{len(quality_report.get('issues', []))}个问题"
            if revised_count > 0:
                message += f",自动修正{revised_count}个单元"

            return ResponseModel(
                success=True,
                data=UnitSummariesQualityControlResponse(
                    success=True,
                    quality_report=quality_report,
                    revision_summary=revision_summary,
                    revised_count=revised_count,
                    message=message
                )
            )

        finally:
            project.unit_summaries_status = original_status if original_status != 'quality_control_running' else 'completed'
            await db.commit()

    except ResourceNotFoundException:
        raise
    except ValidationException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e) if str(e) else repr(e)
        logger.error(f"[单元概述质控] 质控检测失败: {error_detail}\n{traceback.format_exc()}")
        raise AppException(ErrorCode.INTERNAL_ERROR, f"质控检测失败: {error_detail}")

