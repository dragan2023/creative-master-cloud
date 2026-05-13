"""质量管控 v2.0 - 正文内容批量质控端点

提供正文写作的批量质控和选择性修正功能：
1. 批量质控检测（所有单元）
2. 选择性应用修正
3. 修正预览

与单元概述质控API(_unit.py)的区别：
- 本模块针对已生成的正文内容(final_content)
- 单元概述质控针对大纲阶段的单元概述

@date: 2026-04-28
@version: v2.2.0
"""
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import Depends, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, NovelProject
from app.models.writing_unit import WritingUnit
from app.models.writing_task import WritingTask
from app.schemas.common import ResponseModel
from pydantic import BaseModel

from ..utils import router, logger
from ._common import (
    UnitQualityControlRequest,
    _generate_fixes_for_issues,
    publish_qc_progress,
    _sync_writing_unit_to_novel_chapter
)
from ._unit import analyze_single_unit_quality


# ==================== 请求模型 ====================

class BatchQCRequest(BaseModel):
    """批量质控请求"""
    project_id: int
    dimensions: Optional[List[str]] = None  # 分析维度
    depth: str = "standard"  # 分析深度
    auto_fix: bool = True  # 是否自动修正
    auto_fix_threshold: float = 0.8  # 自动修正置信度阈值


class ApplySelectedFixesRequest(BaseModel):
    """选择性应用修正请求"""
    fix_ids: List[str]  # 要应用的修正ID列表


# ==================== 批量质控进度管理 ====================

# 全局批量质控任务状态存储
_batch_qc_tasks: Dict[str, Dict] = {}


def get_batch_task_status(project_id: int) -> Dict:
    """获取批量质控任务状态"""
    key = f"batch_qc_{project_id}"
    return _batch_qc_tasks.get(key, {
        "status": "idle",
        "current": 0,
        "total": 0,
        "current_unit": None,
        "completed_units": [],
        "failed_units": [],
        "started_at": None
    })


def update_batch_task_status(project_id: int, status: Dict):
    """更新批量质控任务状态"""
    key = f"batch_qc_{project_id}"
    _batch_qc_tasks[key] = status


# ==================== API端点 ====================

@router.post("/quality-control/content/batch", response_model=ResponseModel)
async def trigger_batch_content_qc(
    request: BatchQCRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量正文质控检测（异步后台任务）
    
    在后台异步执行所有单元的质控检测，通过WebSocket推送进度。
    
    Args:
        request: 批量质控请求（包含项目ID、维度、深度、修正选项）
        
    Returns:
        任务启动确认
    """
    try:
        project_id = request.project_id
        
        # 检查是否已有批量任务在运行
        current_status = get_batch_task_status(project_id)
        if current_status["status"] == "running":
            return ResponseModel(
                success=False,
                message="已有批量质控任务在运行，请等待完成或取消"
            )
        
        # 获取项目任务
        task_query = select(WritingTask).where(
            WritingTask.project_id == project_id,
            WritingTask.user_id == current_user.id
        )
        task_result = await db.execute(task_query)
        tasks = task_result.scalars().all()
        
        if not tasks:
            return ResponseModel(
                success=False,
                message=f"未找到项目 {project_id} 的写作任务"
            )
        
        task_ids = [task.id for task in tasks]
        
        # 获取所有需要质控的单元
        unit_query = select(WritingUnit).where(
            WritingUnit.task_id.in_(task_ids),
            WritingUnit.final_content.isnot(None),  # 有内容
            WritingUnit.final_content != ''
        ).order_by(WritingUnit.unit_index)
        unit_result = await db.execute(unit_query)
        units = unit_result.scalars().all()
        
        if not units:
            return ResponseModel(
                success=False,
                message="没有需要质控的单元（所有单元内容为空或已完成质控）"
            )
        
        # 过滤出需要质控的单元（pending或failed状态）
        units_to_check = [
            u for u in units 
            if u.quality_control_status in ['pending', 'failed', None]
        ]
        
        if not units_to_check:
            return ResponseModel(
                success=True,
                message="所有单元已完成质控",
                data={
                    "total": len(units),
                    "pending": 0,
                    "completed": len(units)
                }
            )
        
        # 初始化任务状态
        task_key = f"batch_qc_{project_id}"
        update_batch_task_status(project_id, {
            "status": "running",
            "current": 0,
            "total": len(units_to_check),
            "current_unit": None,
            "completed_units": [],
            "failed_units": [],
            "started_at": datetime.now().isoformat()
        })
        
        logger.info(
            f"[批量质控] 启动: project_id={project_id}, "
            f"units={len(units_to_check)}, user={current_user.id}"
        )
        
        # 在后台执行批量质控
        background_tasks.add_task(
            _execute_batch_qc_task,
            project_id=project_id,
            units=units_to_check,
            request=request,
            user_id=current_user.id,
            db=db
        )
        
        return ResponseModel(
            success=True,
            message=f"批量质控任务已启动，共{len(units_to_check)}个单元",
            data={
                "task_key": task_key,
                "total": len(units_to_check),
                "status": "running"
            }
        )
        
    except Exception as e:
        logger.error(f"[批量质控] 启动失败: {e}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"批量质控启动失败: {str(e)}"
        )


async def _execute_batch_qc_task(
    project_id: int,
    units: List[WritingUnit],
    request: BatchQCRequest,
    user_id: int,
    db: AsyncSession
):
    """
    执行批量质控任务（后台任务）
    
    注意：这是一个异步后台任务，不直接返回结果，
    通过WebSocket推送进度和完成通知。
    """
    try:
        from app.core.database import async_session_maker
        
        # 创建新的数据库会话（后台任务需要独立的会话）
        async with async_session_maker() as task_db:
            completed_units = []
            failed_units = []
            
            # 发布开始事件
            await publish_qc_progress(
                task_id=f"batch_qc_{project_id}",
                event_type="content_qc_started",
                data={
                    "total": len(units),
                    "project_id": project_id
                }
            )
            
            for idx, unit in enumerate(units):
                unit_index = unit.unit_index
                
                # 更新任务状态
                status = get_batch_task_status(project_id)
                status["current"] = idx + 1
                status["current_unit"] = unit_index
                update_batch_task_status(project_id, status)
                
                # 发布进度事件
                await publish_qc_progress(
                    task_id=f"batch_qc_{project_id}",
                    event_type="content_qc_progress",
                    progress=round((idx + 1) / len(units) * 100, 1),
                    data={
                        "current": idx + 1,
                        "total": len(units),
                        "current_unit": unit_index,
                        "unit_title": unit.unit_title
                    }
                )
                
                try:
                    # 获取单元内容
                    content = unit.final_content
                    if not content or len(content) < 100:
                        logger.warning(
                            f"[批量质控] 单元 {unit_index} 内容不足，跳过"
                        )
                        failed_units.append({
                            "unit_index": unit_index,
                            "reason": "内容不足"
                        })
                        continue
                    
                    # 调用单单元质控API的逻辑
                    from app.services.quality_control import QualityControlService
                    from app.services.outline_generator import OutlineGenerator
                    
                    # 获取项目信息
                    project_query = select(NovelProject).where(
                        NovelProject.id == project_id
                    )
                    project_result = await task_db.execute(project_query)
                    project = project_result.scalar_one_or_none()
                    
                    if not project:
                        failed_units.append({
                            "unit_index": unit_index,
                            "reason": "项目不存在"
                        })
                        continue
                    
                    # 构建章节数据
                    chapters_data = [{
                        "chapter_number": unit_index,
                        "content": content,
                        "summary": content[:500],  # 截取摘要
                        "unit_summary": getattr(unit, 'unit_summary', '') or "",
                        "title": unit.unit_title or f"第{unit_index}章"
                    }]
                    
                    # 执行质控
                    qc_service = QualityControlService(db=task_db)
                    outline_generator = OutlineGenerator(db=task_db)
                    
                    dimensions = request.dimensions or [
                        "unit_structure",
                        "unit_character",
                        "unit_consistency",
                        "unit_timeline_space",
                        "unit_ooc"
                    ]
                    
                    qc_report = await outline_generator._analyze_unit_summaries_quality(
                        qc_service=qc_service,
                        chapters_data=chapters_data,
                        dimensions=dimensions,
                        depth=request.depth,
                        global_outline=getattr(
                            project, 'global_outline_content', '') or "",
                        character_profiles=getattr(
                            project, 'character_profiles', []) or [],
                        worldview_settings=getattr(
                            project, 'worldview_settings', {}) or {},
                        db=task_db,
                        user_id=user_id
                    )
                    
                    issues = qc_report.get("issues", [])
                    score = qc_report.get("overall_score", 0)
                    
                    # 自动修正（如果启用）
                    auto_fix_applied = []
                    fixed_content = content
                    
                    if request.auto_fix and issues:
                        issues_with_fixes = await _generate_fixes_for_issues(
                            issues=issues,
                            chapters_data=chapters_data,
                            project=project,
                            db=task_db,
                            user_id=user_id
                        )
                        
                        for issue in issues_with_fixes:
                            auto_fix = issue.get('auto_fix')
                            if auto_fix and auto_fix.get('confidence', 0) >= request.auto_fix_threshold:
                                new_content = auto_fix.get('fixed', fixed_content)
                                if new_content != fixed_content:
                                    fixed_content = new_content
                                    auto_fix_applied.append({
                                        "issue_id": issue.get('id'),
                                        "category": issue.get('category'),
                                        "confidence": auto_fix.get('confidence'),
                                        "description": auto_fix.get('description')
                                    })
                    
                    # 更新单元质控结果
                    unit.quality_control_status = 'completed'
                    unit.quality_control_report = qc_report
                    unit.quality_control_fixes = auto_fix_applied
                    unit.quality_control_score = score
                    unit.quality_control_completed_at = datetime.now()
                    
                    if auto_fix_applied:
                        unit.original_content_before_fix = content
                        unit.final_content = fixed_content
                        unit.word_count = len(fixed_content)
                    
                    await task_db.commit()
                    
                    # 同步更新 NovelChapter 表（正文表单显示依赖此表）
                    if auto_fix_applied and fixed_content != content:
                        await _sync_writing_unit_to_novel_chapter(
                            db=task_db,
                            project_id=project_id,
                            unit_index=unit_index,
                            final_content=fixed_content,
                            unit_title=getattr(unit, 'unit_title', '') or f"第{unit_index}章"
                        )
                    
                    completed_units.append({
                        "unit_index": unit_index,
                        "score": score,
                        "issues_count": len(issues),
                        "fixed_count": len(auto_fix_applied)
                    })
                    
                    # 发布单元完成事件
                    await publish_qc_progress(
                        task_id=f"batch_qc_{project_id}",
                        event_type="content_qc_unit_complete",
                        dimension="unit",
                        status="success",
                        data={
                            "unit_index": unit_index,
                            "score": score,
                            "issues_count": len(issues),
                            "fixed_count": len(auto_fix_applied)
                        }
                    )
                    
                    logger.info(
                        f"[批量质控] 单元完成: unit={unit_index}, "
                        f"score={score}, issues={len(issues)}"
                    )
                    
                except Exception as unit_error:
                    logger.error(
                        f"[批量质控] 单元失败: unit={unit_index}, "
                        f"error={unit_error}"
                    )
                    failed_units.append({
                        "unit_index": unit_index,
                        "reason": str(unit_error)
                    })
                    
                    # 更新单元状态为failed
                    unit.quality_control_status = 'failed'
                    await task_db.commit()
                    
                    # 发布单元失败事件
                    await publish_qc_progress(
                        task_id=f"batch_qc_{project_id}",
                        event_type="content_qc_unit_complete",
                        dimension="unit",
                        status="failed",
                        data={
                            "unit_index": unit_index,
                            "error": str(unit_error)
                        }
                    )
            
            # 更新任务状态为完成
            final_status = {
                "status": "completed",
                "current": len(units),
                "total": len(units),
                "current_unit": None,
                "completed_units": completed_units,
                "failed_units": failed_units,
                "started_at": get_batch_task_status(project_id).get("started_at"),
                "completed_at": datetime.now().isoformat()
            }
            update_batch_task_status(project_id, final_status)
            
            # 计算平均得分
            avg_score = 0
            if completed_units:
                total_score = sum(u["score"] for u in completed_units)
                avg_score = round(total_score / len(completed_units), 1)
            
            # 发布批量完成事件
            await publish_qc_progress(
                task_id=f"batch_qc_{project_id}",
                event_type="content_qc_batch_complete",
                status="success",
                data={
                    "total": len(units),
                    "completed": len(completed_units),
                    "failed": len(failed_units),
                    "avg_score": avg_score,
                    "completed_units": completed_units,
                    "failed_units": failed_units
                }
            )
            
            logger.info(
                f"[批量质控] 任务完成: project_id={project_id}, "
                f"completed={len(completed_units)}, failed={len(failed_units)}, "
                f"avg_score={avg_score}"
            )
            
    except Exception as e:
        logger.error(f"[批量质控] 任务执行失败: {e}", exc_info=True)
        
        # 更新任务状态为失败
        update_batch_task_status(project_id, {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })
        
        # 发布失败事件
        await publish_qc_progress(
            task_id=f"batch_qc_{project_id}",
            event_type="content_qc_batch_complete",
            status="failed",
            data={"error": str(e)}
        )


@router.get("/quality-control/content/batch/status/{project_id}", response_model=ResponseModel)
async def get_batch_qc_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取批量质控任务状态
    
    Args:
        project_id: 项目ID
        
    Returns:
        任务状态信息
    """
    status = get_batch_task_status(project_id)
    
    return ResponseModel(
        success=True,
        message="批量质控任务状态",
        data=status
    )


@router.post("/quality-control/content/unit/{unit_index}/apply-selected", response_model=ResponseModel)
async def apply_selected_fixes_for_unit(
    unit_index: int,
    request: ApplySelectedFixesRequest,
    project_id: int = Query(..., description="项目ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    选择性应用修正
    
    用户可以选择应用特定的修正，而不是全部自动修正。
    
    Args:
        unit_index: 单元序号
        project_id: 项目ID（通过query参数传递）
        request: 选择性修正请求
        
    Returns:
        应用结果
    """
    try:
        from sqlalchemy import select
        
        logger.info(
            f"[选择性修正] 开始: unit={unit_index}, fixes={request.fix_ids}, "
            f"user={current_user.id}"
        )
        
        # 获取单元
        task_query = select(WritingTask).where(
            WritingTask.project_id == project_id,
            WritingTask.user_id == current_user.id
        )
        task_result = await db.execute(task_query)
        tasks = task_result.scalars().all()
        
        if not tasks:
            return ResponseModel(
                success=False,
                message=f"未找到项目 {project_id} 的写作任务"
            )
        
        task_ids = [task.id for task in tasks]
        unit_query = select(WritingUnit).where(
            WritingUnit.unit_index == unit_index,
            WritingUnit.task_id.in_(task_ids)
        ).order_by(WritingUnit.id.desc())  # 取最新记录（已完成QC的那条）
        unit_result = await db.execute(unit_query)
        unit = unit_result.scalars().first()
        
        if not unit:
            return ResponseModel(
                success=False,
                message=f"未找到单元 {unit_index}"
            )
        
        # 获取质控报告中的问题
        report = unit.quality_control_report or {}
        issues = report.get("issues", [])
        
        # 过滤要应用的修正
        selected_issues = [
            i for i in issues 
            if i.get("id") in request.fix_ids
        ]
        
        if not selected_issues:
            return ResponseModel(
                success=False,
                message="未找到指定的修正项"
            )
        
        # 保存原始内容
        original_content = unit.final_content
        if not unit.original_content_before_fix:
            unit.original_content_before_fix = original_content
        
        # 获取项目和上下文
        project_query = select(NovelProject).where(NovelProject.id == project_id)
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()
        
        # 分离已有 auto_fix 的问题和需要重新生成修正的问题
        issues_with_existing_fix = []
        issues_needing_fix = []
        for issue in selected_issues:
            existing_fix = issue.get("auto_fix")
            if existing_fix and existing_fix.get("fixed"):
                issues_with_existing_fix.append(issue)
            else:
                issues_needing_fix.append(issue)
        
        logger.info(
            f"[选择性修正] 已有修正: {len(issues_with_existing_fix)}个, "
            f"需生成修正: {len(issues_needing_fix)}个"
        )
        
        # 为需要生成修正的问题调用LLM生成
        if issues_needing_fix:
            chapters_data = [{
                "chapter_number": unit_index,
                "content": original_content,
                "summary": original_content[:500],
                "title": unit.unit_title or f"第{unit_index}章"
            }]
            
            generated_issues = await _generate_fixes_for_issues(
                issues=issues_needing_fix,
                chapters_data=chapters_data,
                project=project,
                db=db,
                user_id=current_user.id
            )
            # 合并：已有修正的保持原样，新生成的加入
            all_issues = issues_with_existing_fix + generated_issues
        else:
            all_issues = issues_with_existing_fix
        
        # 应用修正
        applied_fixes = []
        fixed_content = original_content
        
        for issue in all_issues:
            auto_fix = issue.get("auto_fix")
            if auto_fix and auto_fix.get("fixed"):
                new_content = auto_fix.get("fixed", fixed_content)
                if new_content != fixed_content:
                    fixed_content = new_content
                    applied_fixes.append({
                        "issue_id": issue.get("id"),
                        "category": issue.get("category"),
                        "confidence": auto_fix.get("confidence"),
                        "description": auto_fix.get("description")
                    })
        
        # 如果没有新应用的修正，检查是否已在生成时自动应用
        if not applied_fixes:
            # 检查所有选中的问题：修正内容是否已与当前内容一致（即实时QC已自动应用）
            already_applied_ids = []
            for issue in all_issues:
                af = issue.get("auto_fix")
                if af and af.get("fixed") and af.get("fixed") == original_content:
                    already_applied_ids.append(issue.get("id"))
            
            if already_applied_ids:
                logger.info(
                    f"[选择性修正] 修正已在生成时自动应用: "
                    f"issues={already_applied_ids}"
                )
                
                # 同步更新 NovelChapter 表，确保正文表单显示修正后的内容
                # （QC自动修正时已更新WritingUnit，但NovelChapter可能未同步）
                await _sync_writing_unit_to_novel_chapter(
                    db=db,
                    project_id=project_id,
                    unit_index=unit_index,
                    final_content=original_content,
                    unit_title=unit.unit_title or ""
                )
                
                return ResponseModel(
                    success=True,
                    message=f"选中的 {len(already_applied_ids)} 个修正已在生成时自动应用，无需重复操作",
                    data={
                        "unit_index": unit_index,
                        "applied_count": 0,
                        "already_applied": True,
                        "already_applied_ids": already_applied_ids,
                        "fixed_content": original_content
                    }
                )
            else:
                return ResponseModel(
                    success=False,
                    message="未能生成有效的修正内容"
                )
        
        # 更新单元
        unit.final_content = fixed_content
        unit.word_count = len(fixed_content)
        
        # 更新修正列表
        existing_fixes = unit.quality_control_fixes or []
        unit.quality_control_fixes = existing_fixes + applied_fixes
        
        await db.commit()
        
        # 同步更新 NovelChapter 表（正文表单显示依赖此表）
        await _sync_writing_unit_to_novel_chapter(
            db=db,
            project_id=project_id,
            unit_index=unit_index,
            final_content=fixed_content,
            unit_title=unit.unit_title or ""
        )
        
        logger.info(
            f"[选择性修正] 完成: unit={unit_index}, "
            f"applied={len(applied_fixes)}, "
            f"原文{len(original_content)}字符 -> 修正后{len(fixed_content)}字符"
        )
        
        return ResponseModel(
            success=True,
            message=f"已应用 {len(applied_fixes)} 个修正",
            data={
                "unit_index": unit_index,
                "applied_count": len(applied_fixes),
                "applied_fixes": applied_fixes,
                "original_content": original_content,
                "fixed_content": fixed_content
            }
        )
        
    except Exception as e:
        logger.error(f"[选择性修正] 失败: {e}", exc_info=True)
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"应用修正失败: {str(e)}"
        )


@router.get("/quality-control/content/unit/{unit_index}/preview-fix", response_model=ResponseModel)
async def preview_unit_fix(
    unit_index: int,
    fix_id: str = Query(..., description="修正ID"),
    project_id: int = Query(..., description="项目ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    预览单个修正效果
    
    返回修正前后的内容对比，供用户确认是否应用。
    
    Args:
        unit_index: 单元序号
        fix_id: 修正ID（query参数）
        project_id: 项目ID（query参数）
        
    Returns:
        修正预览数据（原文、修正后、diff）
    """
    try:
        from sqlalchemy import select
        
        # 获取单元
        task_query = select(WritingTask).where(
            WritingTask.project_id == project_id,
            WritingTask.user_id == current_user.id
        )
        task_result = await db.execute(task_query)
        tasks = task_result.scalars().all()
        
        if not tasks:
            return ResponseModel(
                success=False,
                message=f"未找到项目 {project_id} 的写作任务"
            )
        
        task_ids = [task.id for task in tasks]
        unit_query = select(WritingUnit).where(
            WritingUnit.unit_index == unit_index,
            WritingUnit.task_id.in_(task_ids)
        ).order_by(WritingUnit.id.desc())  # 取最新记录（已完成QC的那条）
        unit_result = await db.execute(unit_query)
        unit = unit_result.scalars().first()
        
        if not unit:
            return ResponseModel(
                success=False,
                message=f"未找到单元 {unit_index}"
            )
        
        # 获取质控报告中的问题
        report = unit.quality_control_report or {}
        issues = report.get("issues", [])
        
        # 找到指定的问题
        target_issue = None
        for issue in issues:
            if issue.get("id") == fix_id:
                target_issue = issue
                break
        
        if not target_issue:
            return ResponseModel(
                success=False,
                message=f"未找到修正项 {fix_id}"
            )
        
        # 获取修正建议（如果没有则生成）
        auto_fix = target_issue.get("auto_fix")
        if not auto_fix:
            # 需要生成修正
            project_query = select(NovelProject).where(NovelProject.id == project_id)
            project_result = await db.execute(project_query)
            project = project_result.scalar_one_or_none()
            
            original_content = unit.final_content
            
            chapters_data = [{
                "chapter_number": unit_index,
                "content": original_content,
                "summary": original_content[:500],
                "title": unit.unit_title or f"第{unit_index}章"
            }]
            
            issues_with_fixes = await _generate_fixes_for_issues(
                issues=[target_issue],
                chapters_data=chapters_data,
                project=project,
                db=db,
                user_id=current_user.id
            )
            
            if issues_with_fixes:
                auto_fix = issues_with_fixes[0].get("auto_fix")
        
        if not auto_fix:
            return ResponseModel(
                success=False,
                message="无法生成修正预览"
            )
        
        # 构建预览数据
        original_content = unit.original_content_before_fix or unit.final_content
        fixed_content = auto_fix.get("fixed", original_content)
        
        return ResponseModel(
            success=True,
            message="修正预览",
            data={
                "unit_index": unit_index,
                "fix_id": fix_id,
                "issue": {
                    "id": target_issue.get("id"),
                    "category": target_issue.get("category"),
                    "severity": target_issue.get("severity"),
                    "description": target_issue.get("description")
                },
                "original_content": original_content,
                "fixed_content": fixed_content,
                "confidence": auto_fix.get("confidence"),
                "fix_description": auto_fix.get("description"),
                "change_ratio": abs(len(fixed_content) - len(original_content)) / len(original_content) if original_content else 0
            }
        )
        
    except Exception as e:
        logger.error(f"[修正预览] 失败: {e}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"获取修正预览失败: {str(e)}"
        )