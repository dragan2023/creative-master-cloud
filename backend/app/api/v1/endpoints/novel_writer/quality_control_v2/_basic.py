"""质量管控 v2.0 - 基础质控端点（apply-fix, generate-fix, re-analyze, cancel, feedback）

v2.5: 新增视觉内容智能同步机制，质控修正正文后自动同步更新拍摄脚本和AI视觉资源提示词
"""
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


# ========== v2.4: 视觉内容完整性保护函数 ==========

# 视觉内容段落标记关键词（用于识别拍摄脚本和AI视觉资源部分）
_VISUAL_SECTION_MARKERS = [
    "拍摄脚本参考", "运镜设计", "光影方案", "演出指导", "剪辑思路", "连续性衔接",
    "AI视觉资源生成", "Seedance", "人物参考图生成提示词", "场景参考图生成提示词",
    "物品参考图生成提示词", "视频生成提示词", "参考模式", "人物参考图",
    "场景参考图", "物品参考图", "镜头类型", "主体动作", "环境描述",
    "运镜方式", "风格要求", "首帧描述", "尾帧描述", "负面提示词",
    "AI生成提示词", "六要素", "主视觉提示词", "备选方案提示词",
]


def _ensure_visual_content_integrity(old_content: str, new_content: str) -> str:
    """
    视觉内容完整性保护（安全网）

    检测LLM修正后的内容是否丢失了拍摄脚本和AI视觉资源部分，
    如果丢失则从原始内容中恢复。

    Args:
        old_content: 原始内容
        new_content: LLM修正后的内容

    Returns:
        修正后的内容（如视觉部分丢失则已恢复）
    """
    if not old_content or not new_content:
        return new_content

    # 检测原始内容中是否存在视觉段落
    has_visual_in_old = any(
        marker in old_content for marker in _VISUAL_SECTION_MARKERS
    )
    if not has_visual_in_old:
        return new_content  # 原始内容无视觉段落，无需保护

    # 检测修正后内容中视觉段落是否丢失
    markers_in_old = [m for m in _VISUAL_SECTION_MARKERS if m in old_content]
    markers_in_new = [m for m in markers_in_old if m in new_content]

    # 如果丢失了50%以上的标记，认为视觉部分被删除
    loss_ratio = 1.0 - (len(markers_in_new) / max(len(markers_in_old), 1))
    if loss_ratio > 0.5:
        logger.warning(
            f"[视觉内容保护] 检测到修正后视觉内容大量丢失 "
            f"(原始标记:{len(markers_in_old)}个 -> 修正后:{len(markers_in_new)}个, "
            f"丢失率:{loss_ratio:.0%})，触发安全网恢复"
        )

        # 策略：尝试定位视觉内容起始位置，将原始内容的视觉部分追加回去
        # 寻找视觉段落的起始标记
        visual_start_markers = [
            "### AI视觉资源生成", "## AI视觉资源生成",
            "### 拍摄脚本参考", "## 拍摄脚本参考",
            "### 四、AI生成提示词", "## 四、AI生成提示词",
            "### AI视觉资源", "## AI视觉资源",
            "# AI视觉资源生成", "# 拍摄脚本参考",
        ]

        for marker in visual_start_markers:
            idx = old_content.find(marker)
            if idx > 0:
                # 找到视觉内容起始位置，追加到修正后内容
                visual_section = old_content[idx:]
                # 确保正文和视觉内容之间有换行分隔
                separator = "\n\n" if not new_content.endswith("\n\n") else ""
                restored = new_content.rstrip() + separator + visual_section
                logger.info(
                    f"[视觉内容保护] 已从原始内容恢复视觉段落 "
                    f"(标记: {marker}, 视觉内容长度: {len(visual_section)}字符)"
                )
                return restored

        # 如果找不到明确的起始标记，尝试从最后一个视觉关键词之前提取
        # 取最后一个匹配标记的位置，从此处开始保留
        last_marker_idx = -1
        for marker in markers_in_old:
            idx = old_content.rfind(marker)
            if idx > last_marker_idx:
                last_marker_idx = idx

        if last_marker_idx > 0:
            # 向前搜索最近的段落标题或章节分隔符
            search_start = max(0, last_marker_idx - 500)
            prefix = old_content[search_start:last_marker_idx]
            # 找最后一个 ## 或 ### 标题
            for heading_pattern in ["\n### ", "\n## ", "\n# "]:
                heading_idx = prefix.rfind(heading_pattern)
                if heading_idx >= 0:
                    visual_section = old_content[search_start + heading_idx:]
                    separator = "\n\n" if not new_content.endswith("\n\n") else ""
                    restored = new_content.rstrip() + separator + visual_section.lstrip()
                    logger.info(
                        f"[视觉内容保护] 已从原始内容恢复视觉段落 "
                        f"(视觉内容长度: {len(visual_section)}字符)"
                    )
                    return restored

        logger.warning("[视觉内容保护] 无法定位视觉段落起始位置，返回修正后内容")

    return new_content


# ========== v2.5: 视觉内容智能同步函数 ==========

async def _sync_visual_content(
    old_content: str,
    new_content: str,
    db: AsyncSession,
    user_id: int,
    content_type: str = "novel"
) -> dict:
    """
    视觉内容智能同步（v2.5新增）

    当质控修正了剧本正文后，调用LLM同步更新后续的拍摄脚本、
    分镜设计、AI视觉资源提示词等，确保视觉内容与修正后的正文保持一致。

    v2.6: 新增 content_type 参数，小说类型直接跳过视觉同步，节省token。

    与 _ensure_visual_content_integrity 的分工：
    - _ensure_visual_content_integrity: 安全网，防止视觉内容被删除（恢复丢失的章节）
    - _sync_visual_content: 智能同步，确保视觉内容与正文修改一致（更新描述字段）

    Args:
        old_content: 修正前的原始内容
        new_content: 修正后的内容（已通过完整性检查）
        db: 数据库会话
        user_id: 用户ID
        content_type: 内容类型 (novel/series_script/movie_script)，小说直接跳过

    Returns:
        {
            "synced_content": str,          # 同步后的完整内容
            "body_changes_detected": list,   # 检测到的正文修改
            "visual_updates_applied": list,  # 应用的视觉更新
            "tokens_used": int,              # 消耗的token数
            "skipped": bool,                 # 是否跳过（无视觉内容）
            "fallback": bool,                # 是否因错误回退
        }
    """
    try:
        from app.services.quality_control.fix_generator import QualityFixGenerator

        # v2.6: 小说类型直接跳过视觉同步，节省token
        if content_type == "novel":
            logger.debug("[视觉同步] 小说类型，跳过视觉内容同步")
            return {
                "synced_content": new_content,
                "skipped": True,
                "tokens_used": 0,
            }

        # 快速预检：无视觉标记则跳过
        has_visual = any(
            marker in new_content
            for marker in _VISUAL_SECTION_MARKERS
        )
        if not has_visual:
            logger.debug("[视觉同步] 内容中无视觉资源标记，跳过同步")
            return {
                "synced_content": new_content,
                "skipped": True,
                "tokens_used": 0,
            }

        # 内容无变化则跳过
        if old_content == new_content:
            logger.debug("[视觉同步] 内容无变化，跳过同步")
            return {
                "synced_content": new_content,
                "skipped": True,
                "tokens_used": 0,
            }

        logger.info(
            f"[视觉同步] 检测到视觉资源内容，启动智能同步 "
            f"(original={len(old_content)}chars, fixed={len(new_content)}chars)"
        )

        fix_generator = QualityFixGenerator()
        sync_result = await fix_generator.sync_visual_sections(
            original_content=old_content,
            fixed_content=new_content,
            db=db,
            user_id=user_id
        )

        if sync_result.get("fallback"):
            logger.warning(
                f"[视觉同步] LLM同步失败，回退到修正后内容: "
                f"{sync_result.get('error', 'unknown')}"
            )

        return sync_result

    except Exception as e:
        logger.error(f"[视觉同步] 同步异常: {str(e)}", exc_info=True)
        return {
            "synced_content": new_content,
            "skipped": False,
            "fallback": True,
            "error": str(e),
            "tokens_used": 0,
        }


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

        # ========== v2.4: 视觉内容完整性保护（安全网） ==========
        # 防止LLM修正时误删拍摄脚本和AI视觉资源部分
        new_content = _ensure_visual_content_integrity(old_content, new_content)

        # ========== v2.5: 视觉内容智能同步 ==========
        # 正文修正后，同步更新拍摄脚本、分镜设计、AI视觉资源提示词
        sync_info = {"skipped": True, "tokens_used": 0}
        if new_content != old_content:
            sync_result = await _sync_visual_content(
                old_content=old_content,
                new_content=new_content,
                content_type=getattr(project, 'content_type', None) or 'novel',
                db=db,
                user_id=current_user.id
            )
            if not sync_result.get("fallback"):
                new_content = sync_result.get("synced_content", new_content)
            sync_info = {
                "skipped": sync_result.get("skipped", True),
                "body_changes_detected": sync_result.get("body_changes_detected", []),
                "visual_updates_applied": sync_result.get("visual_updates_applied", []),
                "tokens_used": sync_result.get("tokens_used", 0),
            }
            logger.info(
                f"[视觉同步] 同步完成: skipped={sync_info['skipped']}, "
                f"visual_updates={len(sync_info.get('visual_updates_applied', []))}"
            )

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
                "consistency_update": consistency_results,  # 联动更新结果
                "visual_sync": sync_info  # v2.5: 视觉同步结果
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
