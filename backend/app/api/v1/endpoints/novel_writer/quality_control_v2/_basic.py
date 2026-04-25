"""质量管控 v2.0 - 基础质控端点（apply-fix, generate-fix, re-analyze, cancel, feedback）"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import json
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_user_from_query_or_header
from app.models import User
from app.schemas.common import ResponseModel

from ..utils import router, logger
from ._common import (
    ApplyFixRequest, GenerateFixRequest, ReAnalyzeRequest,
    CancelQCRequest, FeedbackRequest,
    _generate_fixes_for_issues, get_qc_subscriber
)


@router.post("/quality-control/apply-fix", response_model=ResponseModel)
async def apply_quality_fix(
    request: ApplyFixRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    应用质量修正方案

    将自动修正方案应用到指定的单元概述中
    如果没有提供auto_fix,则调用LLM动态生成

    Args:
        issue_id: 问题ID
        auto_fix: 自动修正方案(包含original和fixed,可选)
        chapter_number: 单元号
        project_id: 项目ID(用于LLM生成时获取上下文)

    Returns:
        应用结果
    """
    try:
        from app.models import NovelChapter, NovelProject
        from app.services.quality_control.fix_generator import QualityFixGenerator
        from sqlalchemy import select

        logger.info(
            f"用户 {current_user.id} 应用修正: "
            f"issue={request.issue_id}, chapter={request.chapter_number}"
        )

        # 查找对应的章节
        query = select(NovelChapter).where(
            NovelChapter.chapter_number == request.chapter_number,
            NovelChapter.project_id == request.project_id
        )

        result = await db.execute(query)
        chapter = result.scalar_one_or_none()

        if not chapter:
            return ResponseModel(
                success=False,
                message=f"未找到第{request.chapter_number}单元"
            )

        # 获取章节内容
        old_content = chapter.final_content or chapter.draft_content or ""

        # 如果没有提供auto_fix,调用LLM生成
        auto_fix = request.auto_fix
        if not auto_fix or not auto_fix.get("fixed"):
            logger.info("未提供auto_fix,调用LLM动态生成修正方案")

            # 获取项目信息
            if not request.project_id:
                return ResponseModel(
                    success=False,
                    message="未提供project_id,无法生成修正方案"
                )

            project_query = select(NovelProject).where(
                NovelProject.id == request.project_id
            )
            project_result = await db.execute(project_query)
            project = project_result.scalar_one_or_none()

            if not project:
                return ResponseModel(
                    success=False,
                    message=f"未找到项目 {request.project_id}"
                )

            # 调用LLM生成修正方案
            fix_generator = QualityFixGenerator()
            auto_fix = await fix_generator.generate_fix(
                issue={
                    "id": request.issue_id,
                    "location": {"chapter_number": request.chapter_number}
                },
                chapter_content=old_content,
                global_outline=getattr(
                    project, 'global_outline_content', '') or "",
                character_profiles=getattr(
                    project, 'character_profiles', []) or [],
                worldview_settings=getattr(
                    project, 'worldview_settings', {}) or {},
                db=db,
                user_id=current_user.id
            )

        # 应用修正: 替换内容
        new_content = auto_fix.get("fixed", old_content)

        # 更新章节内容
        if chapter.final_content:
            chapter.final_content = new_content
        else:
            chapter.draft_content = new_content

        await db.commit()

        # ========== 一致性联动更新 ==========
        # 修正后的内容需要同步更新摘要、角色状态和向量库
        consistency_results = {"summary_updated": False,
                               "characters_updated": False, "vector_updated": False}
        try:
            # 获取项目信息（如果之前没有获取）
            if 'project' not in dir() or project is None:
                project_query = select(NovelProject).where(
                    NovelProject.id == request.project_id
                )
                project_result = await db.execute(project_query)
                project = project_result.scalar_one_or_none()

            if project:
                # 1. 更新前文摘要和角色状态
                from app.services.novel_writer.consistency import ConsistencyManager
                from app.core.security import api_key_encryption
                from app.models.writing_model_config import WritingModelConfig as WMC

                # 尝试获取用户的LLM配置
                llm_provider = None
                try:
                    wmc_result = await db.execute(
                        select(WMC).where(
                            WMC.user_id == current_user.id,
                            WMC.is_active == True
                        ).order_by(WMC.updated_at.desc()).limit(1)
                    )
                    wmc = wmc_result.scalar_one_or_none()
                    if wmc:
                        from app.services.llm_provider import LLMProvider
                        api_key = api_key_encryption.decrypt(wmc.encrypted_key)
                        llm_provider = LLMProvider(
                            provider=wmc.provider,
                            api_key=api_key,
                            model_name=wmc.model_id,
                            api_base=wmc.api_base
                        )
                except Exception as llm_err:
                    logger.warning(f"获取LLM配置失败，一致性更新将使用简单模式: {llm_err}")

                consistency_mgr = ConsistencyManager(llm_provider=llm_provider)
                chapter_title = chapter.chapter_title or f"第{request.chapter_number}章"

                # 更新摘要
                try:
                    await consistency_mgr.update_summary(
                        project=project,
                        chapter_number=request.chapter_number,
                        chapter_title=chapter_title,
                        chapter_content=new_content
                    )
                    consistency_results["summary_updated"] = True
                except Exception as e:
                    logger.warning(f"修正后摘要更新失败: {e}")

                # 更新角色状态
                try:
                    await consistency_mgr.update_character_state(
                        project=project,
                        chapter_number=request.chapter_number,
                        chapter_title=chapter_title,
                        chapter_content=new_content
                    )
                    consistency_results["characters_updated"] = True
                except Exception as e:
                    logger.warning(f"修正后角色状态更新失败: {e}")

                # 2. 更新向量库中的章节分段
                try:
                    from app.services.novel_writer.vector_store import ProjectVectorStore
                    vector_store = ProjectVectorStore()
                    await vector_store.add_chapter(
                        project_id=project.id,
                        chapter_number=request.chapter_number,
                        content=new_content
                    )
                    consistency_results["vector_updated"] = True
                except Exception as e:
                    logger.warning(f"修正后向量库更新失败: {e}")

        except Exception as consistency_err:
            logger.error(f"一致性联动更新异常: {consistency_err}")
            # 一致性更新失败不影响修正应用的成功响应

        logger.info(
            f"修正应用成功: chapter={request.chapter_number}, "
            f"old_length={len(old_content)}, new_length={len(new_content)}"
        )

        return ResponseModel(
            success=True,
            message="修正已成功应用",
            data={
                "chapter_number": request.chapter_number,
                "old_content_length": len(old_content),
                "new_content_length": len(new_content),
                "fix_type": auto_fix.get("type", "unknown"),
                "confidence": auto_fix.get("confidence", 0),
                "tokens_used": auto_fix.get("tokens_used", 0),
                "consistency_update": consistency_results  # 联动更新结果
            }
        )

    except Exception as e:
        logger.error(f"应用修正失败: {str(e)}", exc_info=True)
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"应用修正失败: {str(e)}"
        )


@router.post("/quality-control/generate-fix", response_model=ResponseModel)
async def generate_quality_fix(
    request: GenerateFixRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成修正方案（不自动应用，返回建议供用户确认）"""
    try:
        from app.services.quality_control.fix_generator import QualityFixGenerator
        from sqlalchemy import select
        from app.models import NovelProject

        logger.info(
            f"用户 {current_user.id} 请求生成修正: "
            f"issue={request.issue_id}, chapter={request.chapter_number}"
        )

        # 获取上下文
        chapter_content = request.chapter_content
        global_outline = request.global_outline

        if request.project_id > 0 and (not chapter_content or not global_outline):
            project_query = select(NovelProject).where(
                NovelProject.id == request.project_id
            )
            project_result = await db.execute(project_query)
            project = project_result.scalar_one_or_none()

            if project:
                if not chapter_content:
                    from app.models import NovelChapter
                    chapter_query = select(NovelChapter).where(
                        NovelChapter.chapter_number == request.chapter_number,
                        NovelChapter.project_id == request.project_id
                    )
                    chapter_result = await db.execute(chapter_query)
                    chapter = chapter_result.scalar_one_or_none()
                    if chapter:
                        chapter_content = chapter.final_content or chapter.draft_content or ""

                if not global_outline:
                    global_outline = getattr(project, 'global_outline_content', '') or ""

        # 生成修正方案
        fix_generator = QualityFixGenerator()
        fix_result = await fix_generator.generate_fix(
            issue={
                "id": request.issue_id,
                "category": request.category,
                "description": request.description,
                "location": {"chapter_number": request.chapter_number}
            },
            chapter_content=chapter_content or "",
            global_outline=global_outline or "",
            db=db,
            user_id=current_user.id
        )

        return ResponseModel(
            success=True,
            message="修正方案已生成",
            data=fix_result
        )

    except Exception as e:
        logger.error(f"生成修正方案失败: {str(e)}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"生成修正方案失败: {str(e)}"
        )


@router.post("/quality-control/re-analyze", response_model=ResponseModel)
async def re_analyze_quality(
    request: ReAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """重新分析质量（指定单元或全部）"""
    try:
        from sqlalchemy import select
        from app.models import NovelProject, NovelChapter

        logger.info(
            f"用户 {current_user.id} 请求重新分析: "
            f"project={request.project_id}, chapter={request.chapter_number}"
        )

        # 获取项目
        project_query = select(NovelProject).where(
            NovelProject.id == request.project_id
        )
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()

        if not project:
            return ResponseModel(
                success=False,
                message=f"项目不存在: {request.project_id}"
            )

        # 获取章节数据
        if request.chapter_number:
            chapters_query = select(NovelChapter).where(
                NovelChapter.project_id == request.project_id,
                NovelChapter.chapter_number == request.chapter_number
            )
        else:
            chapters_query = select(NovelChapter).where(
                NovelChapter.project_id == request.project_id
            ).order_by(NovelChapter.chapter_number)

        chapters_result = await db.execute(chapters_query)
        chapters = chapters_result.scalars().all()

        chapters_data = []
        for chapter in chapters:
            chapters_data.append({
                "chapter_number": chapter.chapter_number,
                "content": chapter.final_content or chapter.draft_content or "",
                "summary": chapter.chapter_summary or "",
                "title": chapter.chapter_title or f"第{chapter.chapter_number}章"
            })

        if not chapters_data:
            return ResponseModel(
                success=False,
                message="没有可分析的章节内容"
            )

        # 调用质控服务
        from app.services.quality_control import QualityControlService

        qc_service = QualityControlService(db=db)

        dimensions = request.dimensions or [
            "unit_structure", "unit_character", "unit_consistency"
        ]

        qc_report = await qc_service.analyze_chapters(
            chapters_data=chapters_data,
            dimensions=dimensions,
            depth=request.depth,
            global_outline=getattr(project, 'global_outline_content', '') or "",
            character_profiles=getattr(project, 'character_profiles', []) or [],
            worldview_settings=getattr(project, 'worldview_settings', {}) or {},
            user_id=current_user.id
        )

        # 保存报告
        if request.chapter_number:
            # 只更新特定章节的报告
            chapter = chapters[0]
            if hasattr(chapter, 'quality_report'):
                chapter.quality_report = qc_report
        else:
            # 更新项目整体报告
            project.quality_report = qc_report

        await db.commit()

        return ResponseModel(
            success=True,
            message="重新分析完成",
            data=qc_report
        )

    except Exception as e:
        logger.error(f"重新分析失败: {str(e)}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"重新分析失败: {str(e)}"
        )


@router.post("/quality-control/cancel", response_model=ResponseModel)
async def cancel_quality_control(
    request: CancelQCRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """取消正在执行的质控检测任务"""
    try:
        # 查找该用户在此项目上的活跃质控任务
        task_id_prefix = f"qc_{current_user.id}_"

        # 从SSE订阅管理器中查找并取消相关任务
        subscriber = get_qc_subscriber()

        # 标记任务为已取消（通过发布取消事件）
        cancel_flag = {
            "type": "cancelled",
            "timestamp": datetime.now().isoformat(),
            "project_id": request.project_id,
            "user_id": current_user.id
        }

        # 发布取消事件到所有相关订阅者
        for task_id in list(subscriber._subscribers.keys()):
            if task_id.startswith(task_id_prefix):
                await subscriber.publish(task_id, cancel_flag)
                logger.info(f"[取消质控] 已标记任务 {task_id} 为取消状态")

        logger.info(
            f"用户 {current_user.id} 取消质控检测: "
            f"project_id={request.project_id}"
        )

        return ResponseModel(
            success=True,
            message="质控检测已取消"
        )

    except Exception as e:
        logger.error(f"取消质控检测失败: {str(e)}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"取消失败: {str(e)}"
        )


@router.post("/quality-control/feedback", response_model=ResponseModel)
async def submit_quality_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交质量检测反馈"""
    try:
        from app.services.quality_control.analyzers.feedback_learning import get_feedback_manager

        logger.info(
            f"用户 {current_user.id} 提交反馈: "
            f"issue={request.issue_id}, type={request.feedback_type}"
        )

        # 获取反馈学习管理器
        feedback_manager = get_feedback_manager()

        # 记录反馈
        feedback = feedback_manager.record_feedback(
            user_id=current_user.id,
            project_id=0,  # 暂时使用0,实际应该从上下文获取
            issue_id=request.issue_id,
            dimension=request.dimension,
            category=request.category,
            feedback_type=request.feedback_type,
            comment=request.comment
        )

        logger.info(f"反馈记录成功: feedback_id={feedback.feedback_id}")

        return ResponseModel(
            success=True,
            message="反馈已记录,系统将自动优化检测结果",
            data={
                "feedback_id": feedback.feedback_id,
                "feedback_type": request.feedback_type,
                "issue_id": request.issue_id
            }
        )

    except Exception as e:
        logger.error(f"提交反馈失败: {str(e)}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"提交反馈失败: {str(e)}"
        )
