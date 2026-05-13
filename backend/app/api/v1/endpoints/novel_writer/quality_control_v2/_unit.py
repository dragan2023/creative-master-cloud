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
    _generate_fixes_for_issues,
    _sync_writing_unit_to_novel_chapter
)
from fastapi.responses import PlainTextResponse


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
        ).order_by(WritingUnit.id.desc())  # 按id降序取最新记录，避免随机返回空QC记录
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
        # 必须包含 "id" 字段，_execute_analysis 使用 ch["id"] 构建 chapters_analyzed
        chapters_data = [{
            "id": unit_index,       # Required by _execute_analysis
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

        # [v3.0] 正文质控使用六维度深度检测（区别于单元概述的五维度）
        dimensions = request.dimensions if request and request.dimensions else [
            "structure",           # 宏观结构层
            "character",           # 人物塑造层
            "scene",               # 场景与感官层
            "prose",               # 文笔与修辞层
            "experience",          # 阅读体验层
            "technical"            # 技术性排雷层
        ]

        depth = request.depth if request else "deep"  # [v3.0] 正文质控使用deep深度

        # [v3.0] 聚合综合信息上下文（知识图谱、人物设定、前文摘要、一致性报告等）
        from app.services.quality_control.content_qc_context_aggregator import get_context_aggregator
        context_aggregator = get_context_aggregator(db)
        qc_context = await context_aggregator.aggregate(
            project_id=project_id,
            unit_index=unit_index,
            current_content=content
        )

        # [v3.0] 使用正文质控专用的六维度深度分析方法，传入综合信息上下文
        qc_report = await qc_service.analyze_content_with_context(
            chapters_data=chapters_data,
            project=project,
            dimensions=dimensions,
            depth=depth,
            user_id=current_user.id,
            qc_context=qc_context
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

                # [v3.0] 双版本存储：在 commit 前设置所有字段，一次提交保证事务完整性
                if auto_fix_applied and fixed_content != original_content:
                    unit.content_after_qc_fix = fixed_content
                    logger.info(
                        f"[实时质控-版本] 修正稿已存储: unit={unit_index}, "
                        f"初稿={len(original_content)}字符, 修正稿={len(fixed_content)}字符"
                    )
                elif not auto_fix_applied and unit.content_after_generation:
                    # 无修正时，content_after_qc_fix 复制初稿内容
                    unit.content_after_qc_fix = unit.content_after_generation
                    logger.info(
                        f"[实时质控-版本] 无修正，修正稿复制初稿: unit={unit_index}"
                    )

                await db.commit()
                logger.info(f"[实时质控] WritingUnit 更新成功: unit={unit_index}")
        except Exception as db_error:
            logger.error(f"[实时质控] 数据库更新失败: {db_error}")
            await db.rollback()

        # NovelChapter 同步（后置操作，失败不影响质控主流程）
        if unit and auto_fix_applied and fixed_content != original_content:
            try:
                await _sync_writing_unit_to_novel_chapter(
                    db=db,
                    project_id=project_id,
                    unit_index=unit_index,
                    final_content=fixed_content,
                    unit_title=getattr(unit, 'unit_title', '') or f"第{unit_index}章"
                )
                logger.info(f"[实时质控] NovelChapter 同步成功: chapter_number={unit_index}")
            except Exception as sync_error:
                logger.error(
                    f"[实时质控] NovelChapter 同步失败: chapter_number={unit_index}, error={sync_error}"
                )

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
                "dimension_scores": qc_report.get("dimension_scores", {}),
                "context_summary": qc_report.get("context_summary", ""),
                "original_content": original_content if auto_fix_applied else None,
                "fixed_content": fixed_content if auto_fix_applied else None,
                "content_after_generation": getattr(unit, 'content_after_generation', None),
                "content_after_qc_fix": getattr(unit, 'content_after_qc_fix', None),
                "change_list": _build_change_list(original_content, fixed_content) if auto_fix_applied and fixed_content != original_content else []
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
        ).order_by(WritingUnit.id.desc())  # 取最新记录（已完成QC的那条）
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
        # [v3.0] 撤销时重置 content_after_qc_fix，避免下载到过期修正稿
        unit.content_after_qc_fix = None

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

        # 同步更新 NovelChapter 表（正文表单显示依赖此表）
        try:
            await _sync_writing_unit_to_novel_chapter(
                db=db,
                project_id=project_id,
                unit_index=unit_index,
                final_content=original_content,
                unit_title=getattr(unit, 'unit_title', '') or ""
            )
            logger.info(f"[撤销修正] NovelChapter 同步成功: chapter_number={unit_index}")
        except Exception as sync_error:
            logger.error(f"[撤销修正] NovelChapter 同步失败: chapter_number={unit_index}, error={sync_error}")

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


# ==================== 辅助函数 ====================


@router.get("/quality-control/unit/{project_id}/{unit_index}/download/{version}")
async def download_unit_content(
    project_id: int,
    unit_index: int,
    version: str,  # "draft" 或 "revised"
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """下载单元内容（v3.0: 初稿/修正稿双版本下载）
    
    Args:
        version: 'draft' 下载 LLM 初稿，'revised' 下载质控修正稿
    """
    from app.models.writing_unit import WritingUnit
    from app.models.writing_task import WritingTask
    from sqlalchemy import select

    if version not in ("draft", "revised"):
        return PlainTextResponse("无效的版本参数，请使用 draft 或 revised", status_code=400)

    try:
        # 查找任务（必须校验 user_id 权限）
        task_query = select(WritingTask).where(
            WritingTask.project_id == project_id,
            WritingTask.user_id == current_user.id
        )
        task_result = await db.execute(task_query)
        tasks = task_result.scalars().all()

        if not tasks:
            return PlainTextResponse("未找到项目写作任务", status_code=404)

        task_ids = [task.id for task in tasks]
        unit_query = select(WritingUnit).where(
            WritingUnit.unit_index == unit_index,
            WritingUnit.task_id.in_(task_ids)
        ).order_by(WritingUnit.id.desc())
        unit_result = await db.execute(unit_query)
        unit = unit_result.scalars().first()

        if not unit:
            return PlainTextResponse(f"未找到单元 {unit_index}", status_code=404)

        # 获取对应版本的内容
        if version == "draft":
            content = getattr(unit, 'content_after_generation', None) or unit.final_content or ""
        else:
            content = getattr(unit, 'content_after_qc_fix', None) or unit.final_content or ""

        if not content:
            return PlainTextResponse("暂无内容", status_code=404)

        # 生成文件名
        unit_title = getattr(unit, 'unit_title', '') or f"第{unit_index}章"
        safe_title = unit_title.replace('/', '_').replace('\\', '_')
        version_label = "初稿" if version == "draft" else "修正稿"
        filename = f"{safe_title}_{version_label}.txt"

        # 返回 BOM + UTF-8 编码的文本，确保 Windows 记事本正确显示中文
        bom = '\ufeff'
        return PlainTextResponse(
            bom + content,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
            media_type="text/plain; charset=utf-8"
        )

    except Exception as e:
        logger.error(f"[下载内容] 失败: {e}", exc_info=True)
        return PlainTextResponse(f"下载失败: {str(e)}", status_code=500)


def _build_change_list(original: str, fixed: str) -> list:
    """构建修正变更列表（简化版：长度变化+关键差异标记）"""
    if not original or not fixed:
        return []

    changes = []
    orig_len = len(original)
    fixed_len = len(fixed)

    if orig_len != fixed_len:
        delta = fixed_len - orig_len
        change_type = "新增" if delta > 0 else "删除"
        changes.append({
            "type": change_type,
            "description": f"内容{change_type}了 {abs(delta)} 字符"
        })
    else:
        changes.append({
            "type": "修改",
            "description": f"内容长度不变({fixed_len}字符)，已有修改"
        })

    return changes
