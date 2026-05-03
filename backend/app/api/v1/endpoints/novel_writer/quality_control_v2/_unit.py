"""质量管控 v2.0 - 单元实时质控端点"""
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.schemas.common import ResponseModel

from ..utils import router, logger
from ._common import (
    UnitQualityControlRequest,
    _generate_fixes_for_issues
)


@router.post("/quality-control/unit/{project_id}/{unit_index}", response_model=ResponseModel)
async def analyze_single_unit_quality(
    project_id: int,
    unit_index: int,
    request: UnitQualityControlRequest = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    单个单元质控检测（实时自动触发）

    在单元正文生成完成后立即调用此接口进行质控检测和自动修正。

    Args:
        project_id: 项目ID
        unit_index: 单元序号
        request: 质控请求（包含内容、维度、深度等）

    Returns:
        质控结果报告
    """
    try:
        from app.models.writing_unit import WritingUnit
        from app.services.quality_control import QualityControlService
        from app.services.outline_generator import OutlineGenerator
        from sqlalchemy import select
        from datetime import datetime

        logger.info(
            f"[实时质控] 开始检测: project_id={project_id}, "
            f"unit_index={unit_index}, user={current_user.id}"
        )

        # 初始化unit变量(避免后续NameError)
        unit = None

        # 获取单元内容
        content = request.content if request else ""

        # 始终从数据库获取unit对象(即使请求中包含了content)
        # 因为后续需要更新unit的质控结果
        from app.models.writing_task import WritingTask
        task_query = select(WritingTask).where(
            WritingTask.project_id == project_id,
            WritingTask.user_id == current_user.id  # 添加用户权限过滤
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
        ).order_by(WritingUnit.created_at.desc())  # 按创建时间倒序，取最新的
        unit_result = await db.execute(unit_query)
        unit = unit_result.scalars().first()  # 使用first()避免Multiple rows错误

        if not unit:
            return ResponseModel(
                success=False,
                message=f"未找到项目 {project_id} 的单元 {unit_index}"
            )

        # 如果请求中没有content,从unit中获取
        if not content:
            content = unit.final_content or ""
            if not content:
                return ResponseModel(
                    success=False,
                    message=f"单元 {unit_index} 内容为空"
                )

        # 构建章节数据格式（兼容现有质控服务）
        chapters_data = [{
            "chapter_number": unit_index,
            "content": content,
            "summary": content,  # 不再截断，完整传递给质控服务
            # 新增：传递单元概述
            "unit_summary": getattr(unit, 'unit_summary', '') or "",
            "title": f"第{unit_index}章"
        }]

        # 获取项目信息（用于质控上下文）
        from app.models import NovelProject
        project_query = select(NovelProject).where(
            NovelProject.id == project_id)
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()

        if not project:
            return ResponseModel(
                success=False,
                message=f"未找到项目 {project_id}"
            )

        # 执行质控检测
        qc_service = QualityControlService(db=db)
        outline_generator = OutlineGenerator(db=db)

        dimensions = request.dimensions if request and request.dimensions else [
            "unit_structure",
            "unit_character",
            "unit_consistency",
            "unit_timeline_space",
            "unit_ooc"
        ]

        depth = request.depth if request else "standard"

        # 调用质控分析
        qc_report = await outline_generator._analyze_unit_summaries_quality(
            qc_service=qc_service,
            chapters_data=chapters_data,
            dimensions=dimensions,
            depth=depth,
            global_outline=getattr(
                project, 'global_outline_content', '') or "",
            character_profiles=getattr(
                project, 'character_profiles', []) or [],
            worldview_settings=getattr(
                project, 'worldview_settings', {}) or {},
            db=db,
            user_id=current_user.id,
            project_id=project_id
        )

        # 提取问题和得分
        issues = qc_report.get("issues", [])
        score = qc_report.get("overall_score", 0)

        logger.info(
            f"[实时质控] 检测完成: unit={unit_index}, "
            f"score={score}, issues={len(issues)}"
        )

        # 自动修正（如果启用）
        auto_fix_applied = []
        original_content = content  # 保存修正前的原始内容
        fixed_content = content     # 初始化为原始内容

        if request and request.auto_fix and issues:
            logger.info(f"[实时质控] 开始自动修正: {len(issues)}个问题")

            # 为每个问题生成修正建议
            issues_with_fixes = await _generate_fixes_for_issues(
                issues=issues,
                chapters_data=chapters_data,
                project=project,
                db=db,
                user_id=current_user.id
            )

            # 应用高置信度的修正
            threshold = request.auto_fix_threshold if request else 0.8
            for issue in issues_with_fixes:
                auto_fix = issue.get('auto_fix')
                if auto_fix and auto_fix.get('confidence', 0) >= threshold:
                    # 应用修正 - 注意：auto_fix['fixed']是修正后的完整正文
                    new_content = auto_fix.get('fixed', fixed_content)

                    # 检查内容是否真的被修改了
                    if new_content != fixed_content:
                        # 新增：计算修改幅度
                        original_len = len(fixed_content)
                        new_len = len(new_content)
                        change_ratio = abs(
                            new_len - original_len) / original_len if original_len > 0 else 0

                        logger.info(
                            f"[实时质控] 应用修正: {issue.get('category')}, "
                            f"原文{original_len}字符 -> 修正后{new_len}字符, "
                            f"变化幅度{change_ratio*100:.1f}%"
                        )

                        # 如果变化幅度超过30%，记录警告
                        if change_ratio > 0.3:
                            logger.warning(
                                f"[实时质控] ⚠️ 修改幅度较大({change_ratio*100:.1f}%)，"
                                f"请检查是否偏离大纲或单元概述"
                            )

                        fixed_content = new_content

                    auto_fix_applied.append({
                        "issue_id": issue.get('id'),
                        "category": issue.get('category'),
                        "confidence": auto_fix.get('confidence'),
                        "description": auto_fix.get('description')
                    })

            logger.info(f"[实时质控] 修正完成: 应用了{len(auto_fix_applied)}个修正")

            # 检查内容是否有实际变化
            if fixed_content == original_content and auto_fix_applied:
                logger.warning(
                    f"[实时质控] ⚠️ 修正列表有{len(auto_fix_applied)}项，但内容未变化！LLM可能只生成了修正说明而非实际修改内容。")

        # 更新数据库中的质控结果
        try:
            if unit:
                unit.quality_control_status = 'completed'
                unit.quality_control_report = qc_report
                unit.quality_control_fixes = auto_fix_applied
                unit.quality_control_score = score
                unit.quality_control_completed_at = datetime.now()

                # 如果有修正，保存原始内容并更新最终内容
                if auto_fix_applied:
                    unit.original_content_before_fix = original_content
                    unit.final_content = fixed_content
                    unit.word_count = len(fixed_content)

                    # 记录修正详情
                    if fixed_content != original_content:
                        logger.info(
                            f"[实时质控] 修正内容已保存: 原文{len(original_content)}字符 -> 修正后{len(fixed_content)}字符")
                    else:
                        logger.info(
                            f"[实时质控] 修正列表有{len(auto_fix_applied)}项，但正文未变化（LLM可能只生成了修正说明）")

                await db.commit()
                logger.info(f"[实时质控] 数据库更新成功: unit={unit_index}")
        except Exception as db_error:
            logger.error(f"[实时质控] 数据库更新失败: {db_error}")
            await db.rollback()

        # 返回质控结果
        return ResponseModel(
            success=True,
            message=f"单元 {unit_index} 质控完成",
            data={
                "unit_index": unit_index,
                "score": score,
                "issues_count": len(issues),
                "fixed_count": len(auto_fix_applied),
                "issues": issues,
                "fixes_applied": auto_fix_applied,
                "report": qc_report,
                "original_content": original_content if auto_fix_applied else None,
                "fixed_content": fixed_content if auto_fix_applied else None
            }
        )

    except Exception as e:
        logger.error(f"[实时质控] 检测失败: {e}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"质控检测失败: {str(e)}"
        )


@router.post("/quality-control/unit/{project_id}/{unit_index}/revert-fix", response_model=ResponseModel)
async def revert_unit_fix(
    project_id: int,
    unit_index: int,
    fix_id: Optional[str] = None,  # 要撤销的修正ID，如果为None则撤销所有修正
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """撤销单元的自动修正"""
    try:
        from app.models.writing_unit import WritingUnit
        from app.models.writing_task import WritingTask
        from sqlalchemy import select

        logger.info(
            f"[撤销修正] project_id={project_id}, unit_index={unit_index}, "
            f"fix_id={fix_id}"
        )

        # 查找单元
        task_query = select(WritingTask).where(
            WritingTask.project_id == project_id)
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
        )
        unit_result = await db.execute(unit_query)
        unit = unit_result.scalars().first()  # 使用first()避免Multiple rows错误

        if not unit:
            return ResponseModel(
                success=False,
                message=f"未找到单元 {unit_index}"
            )

        # 检查是否有原始内容
        if not unit.original_content_before_fix:
            return ResponseModel(
                success=False,
                message="没有可撤销的修正（未保存原始内容）"
            )

        # 撤销修正
        original_content = unit.original_content_before_fix
        unit.final_content = original_content
        unit.word_count = len(original_content)
        unit.original_content_before_fix = None

        # 更新质控状态
        if fix_id:
            # 撤销特定修正
            fixes = unit.quality_control_fixes or []
            fixes = [f for f in fixes if f.get('issue_id') != fix_id]
            unit.quality_control_fixes = fixes
        else:
            # 撤销所有修正
            unit.quality_control_fixes = []
            unit.quality_control_status = 'completed'

        await db.commit()

        logger.info(f"[撤销修正] 成功: unit={unit_index}")

        return ResponseModel(
            success=True,
            message="修正已撤销",
            data={
                "unit_index": unit_index,
                "reverted_content": original_content,
                "word_count": len(original_content)
            }
        )

    except Exception as e:
        logger.error(f"[撤销修正] 失败: {e}", exc_info=True)
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"撤销修正失败: {str(e)}"
        )
