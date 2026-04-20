"""
质量管控 v2.0 API 端点

提供:
1. 应用自动修正方案
2. 用户反馈记录
3. SSE实时推送质控进度 (v1.1新增)

@date: 2026-04-14
@version: v2.1.0
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_user_from_query_or_header
from app.models import User
from app.schemas.common import ResponseModel

from .utils import router, logger


# ==================== 辅助函数 ====================

async def _generate_fixes_for_issues(
    issues: list,
    chapters_data: list,
    project: Any,
    db: Any,
    user_id: int
) -> list:
    """
    为检测结果中的每个问题自动生成修正建议

    Args:
        issues: 问题列表
        chapters_data: 章节数据
        project: 项目对象
        db: 数据库会话
        user_id: 用户ID

    Returns:
        包含修正建议的问题列表
    """
    from app.services.quality_control.fix_generator import QualityFixGenerator

    fix_generator = QualityFixGenerator()
    issues_with_fixes = []

    for issue in issues:
        # 获取章节号
        chapter_number = issue.get('location', {}).get('chapter_number', 0)
        if not chapter_number:
            issues_with_fixes.append(issue)
            continue

        # 查找对应章节内容和单元概述
        chapter_content = ""
        chapter_summary = ""  # 新增：单元概述
        for ch in chapters_data:
            if ch.get('chapter_number') == chapter_number:
                chapter_content = ch.get('content', '')
                chapter_summary = ch.get('summary', '') or ch.get(
                    'unit_summary', '')  # 新增：获取单元概述
                break

        if not chapter_content:
            issues_with_fixes.append(issue)
            continue

        try:
            # 新增：查询知识图谱上下文
            from app.services.quality_control.kg_helper import get_kg_helper
            kg_helper = get_kg_helper()

            issue_category = issue.get('category', '')
            kg_data = kg_helper.query_relevant_entities(
                project_id=getattr(project, 'id', 0),
                unit_index=chapter_number,
                issue_category=issue_category,
                max_entities=15
            )
            knowledge_graph_context = kg_helper.format_kg_context(kg_data)

            logger.info(
                f"[修正建议] 知识图谱查询完成: issue={issue.get('id')}, "
                f"人物={len(kg_data.get('characters', []))}, "
                f"事件={len(kg_data.get('events', []))}"
            )

            # 调用LLM生成修正建议
            fix_result = await fix_generator.generate_fix(
                issue=issue,
                chapter_content=chapter_content,
                unit_summary=chapter_summary,
                knowledge_graph_context=knowledge_graph_context,
                character_profiles=getattr(
                    project, 'character_profiles', []) or [],
                worldview_settings=getattr(
                    project, 'worldview_settings', {}) or {},
                db=db,
                user_id=user_id
            )

            # 将修正建议添加到问题中
            issue['auto_fix'] = fix_result
            issues_with_fixes.append(issue)

            logger.debug(
                f"[修正建议] 为问题 {issue.get('id')} 生成修正建议成功, "
                f"confidence={fix_result.get('confidence', 0):.2f}"
            )
        except Exception as e:
            logger.warning(f"[修正建议] 为问题 {issue.get('id')} 生成修正建议失败: {e}")
            issues_with_fixes.append(issue)

    return issues_with_fixes


# ==================== 请求/响应模型 ====================

class ApplyFixRequest(BaseModel):
    """应用修正请求"""
    issue_id: str                    # 问题ID
    auto_fix: Optional[Dict[str, Any]] = None  # 自动修正方案(可选,如果不提供则调用LLM生成)
    chapter_number: int              # 单元号
    project_id: Optional[int] = None  # 项目ID(用于获取上下文)


class GenerateFixRequest(BaseModel):
    """生成修正方案请求"""
    issue_id: str                    # 问题ID
    chapter_number: int              # 单元号
    category: str                    # 问题分类
    description: str                 # 问题描述
    project_id: int = 0              # 项目ID(可选，默认为0表示大纲阶段)
    chapter_content: str = ""        # 单元内容(大纲阶段前端传递)
    global_outline: str = ""         # 全局大纲(大纲阶段前端传递)


class ReAnalyzeRequest(BaseModel):
    """重新分析请求"""
    project_id: int                  # 项目ID
    chapter_number: Optional[int] = None  # 单元号(可选,不指定则分析所有)
    dimensions: Optional[List[str]] = None  # 分析维度(可选)
    depth: str = "standard"          # 分析深度


class CancelQCRequest(BaseModel):
    """取消质控检测请求"""
    project_id: int                  # 项目ID


class FeedbackRequest(BaseModel):
    """用户反馈请求"""
    issue_id: str                    # 问题ID
    dimension: str                   # 维度
    category: str                    # 分类
    feedback_type: str               # 反馈类型 (accepted/ignored/false_positive)
    comment: str = ""                # 用户备注


class ImportedOutlineAutoReviseRequest(BaseModel):
    """导入大纲自动质控修正请求（v2.3新增）"""
    outline_content: str             # 导入的大纲内容
    dimensions: Optional[List[str]] = None  # 分析维度（可选，默认四维度）
    depth: str = "standard"          # 分析深度（默认standard以确保LLM深度分析）


class UnitQualityControlRequest(BaseModel):
    """单单元质控检测请求（v2.0新增 - 实时质控）"""
    project_id: int                  # 项目ID
    unit_index: int                  # 单元序号
    content: str                     # 单元内容
    dimensions: Optional[List[str]] = None  # 分析维度（可选）
    depth: str = "standard"          # 分析深度
    auto_fix: bool = True            # 是否自动修正
    auto_fix_threshold: float = 0.8  # 自动修正置信度阈值


# ==================== API端点 ====================

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
    """
    使用LLM生成智能修正方案

    根据问题描述、全局大纲、人物设定、世界观生成修正内容

    Args:
        issue_id: 问题ID
        chapter_number: 单元号
        category: 问题分类
        description: 问题描述
        project_id: 项目ID

    Returns:
        修正方案(包含original, fixed, description, confidence等)
    """
    try:
        from app.services.quality_control.fix_generator import QualityFixGenerator
        from app.models import NovelChapter, NovelProject
        from sqlalchemy import select

        logger.info(
            f"用户 {current_user.id} 请求生成修正方案: "
            f"issue={request.issue_id}, chapter={request.chapter_number}, project={request.project_id}"
        )

        # 查找对应的章节（如果project_id>0）
        chapter = None
        if request.project_id > 0:
            query = select(NovelChapter).where(
                NovelChapter.chapter_number == request.chapter_number,
                NovelChapter.project_id == request.project_id
            )
            result = await db.execute(query)
            chapter = result.scalar_one_or_none()

        # 构建上下文信息
        chapter_content = ""
        global_outline = ""
        unit_summary = ""  # 新增：单元概述
        character_profiles = []
        worldview_settings = {}

        if chapter:
            # 从数据库获取章节内容和项目信息
            chapter_content = chapter.final_content or chapter.draft_content or ""
            unit_summary = getattr(
                chapter, 'unit_summary', '') or ""  # 新增：获取单元概述

            project_query = select(NovelProject).where(
                NovelProject.id == request.project_id
            )
            project_result = await db.execute(project_query)
            project = project_result.scalar_one_or_none()

            if project:
                global_outline = getattr(
                    project, 'global_outline_content', '') or ""
                character_profiles = getattr(
                    project, 'character_profiles', []) or []
                worldview_settings = getattr(
                    project, 'worldview_settings', {}) or {}
        else:
            # 大纲阶段：使用前端传递的内容
            chapter_content = request.chapter_content or request.description
            global_outline = request.global_outline or ""
            # 大纲阶段可能没有unit_summary
            logger.info(
                f"大纲阶段修正: 使用前端传递的单元内容({len(chapter_content)}字) "
                f"和全局大纲({len(global_outline)}字)"
            )

        # 新增：查询知识图谱上下文
        knowledge_graph_context = ""
        if request.project_id > 0:  # 只在有项目ID时查询知识图谱
            try:
                from app.services.quality_control.kg_helper import get_kg_helper
                kg_helper = get_kg_helper()

                kg_data = kg_helper.query_relevant_entities(
                    project_id=request.project_id,
                    unit_index=request.chapter_number,
                    issue_category=request.category,
                    max_entities=15
                )
                knowledge_graph_context = kg_helper.format_kg_context(kg_data)

                logger.info(
                    f"[生成修正方案] 知识图谱查询完成: project={request.project_id}, "
                    f"人物={len(kg_data.get('characters', []))}, "
                    f"事件={len(kg_data.get('events', []))}"
                )
            except Exception as kg_error:
                logger.warning(f"[生成修正方案] 知识图谱查询失败: {kg_error}")
                knowledge_graph_context = ""

        # 调用LLM生成修正方案
        fix_generator = QualityFixGenerator()
        fix_result = await fix_generator.generate_fix(
            issue={
                "id": request.issue_id,
                "category": request.category,
                "description": request.description,
                "location": {"chapter_number": request.chapter_number}
            },
            chapter_content=chapter_content,
            unit_summary=unit_summary,
            knowledge_graph_context=knowledge_graph_context,
            character_profiles=character_profiles,
            worldview_settings=worldview_settings,
            db=db,
            user_id=current_user.id
        )

        logger.info(
            f"修正方案生成成功: confidence={fix_result.get('confidence', 0):.2f}, "
            f"tokens={fix_result.get('tokens_used', 0)}"
        )

        return ResponseModel(
            success=True,
            message="修正方案生成成功",
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
    """
    重新执行质量分析

    应用修正后,重新分析质量并计算得分变化

    Args:
        project_id: 项目ID
        chapter_number: 单元号(可选)
        dimensions: 分析维度(可选)
        depth: 分析深度

    Returns:
        新的质量报告和得分变化
    """
    try:
        from app.services.outline_generator import OutlineGenerator
        from app.models import NovelProject, NovelChapter
        from sqlalchemy import select

        # 确保project_id是整数
        project_id = int(request.project_id)

        logger.info(
            f"用户 {current_user.id} 请求重新分析: "
            f"project={project_id}, chapter={request.chapter_number}, "
            f"dimensions={request.dimensions}"
        )

        # 获取项目
        project_query = select(NovelProject).where(
            NovelProject.id == project_id
        )
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()

        if not project:
            logger.error(f"[质控检测] 项目不存在: project_id={project_id}")
            return ResponseModel(
                success=False,
                message=f"未找到项目 {project_id}"
            )

        # 获取单元概述数据
        # 尝试从 NovelChapter 表获取
        chapters_query = select(NovelChapter).where(
            NovelChapter.project_id == project_id
        )
        if request.chapter_number:
            chapters_query = chapters_query.where(
                NovelChapter.chapter_number == request.chapter_number
            )

        # 按章节号排序
        chapters_query = chapters_query.order_by(NovelChapter.chapter_number)

        chapters_result = await db.execute(chapters_query)
        chapters = chapters_result.scalars().all()

        logger.info(
            f"[质控检测] 从 NovelChapter 查询到章节数: {len(chapters)}, project_id={project_id}")

        # 如果 NovelChapter 表没有数据，尝试从 WritingUnit 表获取（写作工作台生成的内容）
        if not chapters:
            from app.models.writing_unit import WritingUnit
            from app.models.writing_task import WritingTask

            logger.info(f"[质控检测] NovelChapter 表无数据，尝试从 WritingUnit 获取...")

            # 查找该项目的所有写作任务
            tasks_query = select(WritingTask).where(
                WritingTask.project_id == project_id
            )
            tasks_result = await db.execute(tasks_query)
            tasks = tasks_result.scalars().all()

            if tasks:
                task_ids = [task.id for task in tasks]
                logger.info(f"[质控检测] 找到 {len(tasks)} 个写作任务")

                # 获取这些任务的所有单元
                units_query = select(WritingUnit).where(
                    WritingUnit.task_id.in_(task_ids)
                ).order_by(WritingUnit.unit_index)

                units_result = await db.execute(units_query)
                units = units_result.scalars().all()

                logger.info(f"[质控检测] 从 WritingUnit 获取到 {len(units)} 个单元")

                # 转换为 chapters_data 格式
                chapters_data = []
                for unit in units:
                    content = unit.final_content or unit.draft_content or ""
                    if content:  # 只包含有内容的单元
                        chapters_data.append({
                            "id": unit.id,
                            "chapter_number": unit.unit_index,
                            "unit_id": unit.id,
                            "content": content,
                            "summary": content[:500] if content else "",
                            "title": unit.unit_title or f"第{unit.unit_index}章"
                        })

                if not chapters_data:
                    logger.warning(
                        f"[质控检测] 未找到章节数据: project_id={project_id}, "
                        f"project.unit_summaries={bool(project.unit_summaries)}, "
                        f"project.global_outline_content={bool(getattr(project, 'global_outline_content', ''))}"
                    )
                    return ResponseModel(
                        success=False,
                        message=f"未找到章节数据（项目ID: {project_id}）。请确认已生成单元概述或正文内容。"
                    )

                logger.info(
                    f"[质控检测] 构建章节数据完成: {len(chapters_data)}章（来自WritingUnit）")
            else:
                logger.warning(
                    f"[质控检测] 未找到章节数据: project_id={project_id}, "
                    f"project.unit_summaries={bool(project.unit_summaries)}, "
                    f"project.global_outline_content={bool(getattr(project, 'global_outline_content', ''))}"
                )
                return ResponseModel(
                    success=False,
                    message=f"未找到章节数据（项目ID: {project_id}）。请确认已生成单元概述或正文内容。"
                )
        else:
            # 从 NovelChapter 构建章节数据
            chapters_data = []
            for chapter in chapters:
                content = chapter.final_content or chapter.draft_content or ""
                chapters_data.append({
                    "id": chapter.id,
                    "chapter_number": chapter.chapter_number,
                    "unit_id": getattr(chapter, 'unit_id', ''),  # 添加unit_id字段
                    "content": content,
                    "summary": content[:500] if content else ""  # 摘要
                })

            logger.info(
                f"[质控检测] 构建章节数据完成: {len(chapters_data)}章（来自NovelChapter）")

        # 执行质量分析
        from app.services.quality_control import QualityControlService

        qc_service = QualityControlService(db=db)
        outline_generator = OutlineGenerator(db=db)

        # 使用请求中的维度，如果没有则使用默认的五维度
        dimensions = request.dimensions or [
            "unit_structure",
            "unit_character",
            "unit_consistency",
            "unit_timeline_space",
            "unit_ooc"
        ]

        new_report = await outline_generator._analyze_unit_summaries_quality(
            qc_service=qc_service,
            chapters_data=chapters_data,
            dimensions=dimensions,
            depth=request.depth or "deep",
            global_outline=getattr(
                project, 'global_outline_content', '') or "",
            character_profiles=getattr(
                project, 'character_profiles', []) or [],  # 新增：传递人物设定
            worldview_settings=getattr(
                project, 'worldview_settings', {}) or {},  # 新增：传递世界观
            user_id=current_user.id,
            project_id=project_id
        )

        # 计算得分变化(从请求中获取旧报告)
        # 注意: 实际应该从缓存或数据库中获取旧报告
        # 这里简化处理,由前端传递旧报告
        score_changes = {
            "overall": {
                "previous": 0,  # 由前端填充
                "current": new_report.get("overall_score", 0),
                "delta": 0
            },
            "dimensions": {}
        }

        # 计算各维度得分
        old_dims = {}  # 由前端填充
        new_dims = new_report.get("dimension_scores", {})

        for dim, score in new_dims.items():
            old_score = old_dims.get(dim, 0)
            score_changes["dimensions"][dim] = {
                "previous": old_score,
                "current": score,
                "delta": score - old_score
            }

        logger.info(
            f"重新分析完成: overall_score={new_report.get('overall_score', 0)}, "
            f"issues={len(new_report.get('issues', []))}"
        )

        # 自动为每个问题生成修正建议
        issues_with_fixes = await _generate_fixes_for_issues(
            issues=new_report.get('issues', []),
            chapters_data=chapters_data,
            project=project,
            db=db,
            user_id=current_user.id
        )

        # 更新报告中的问题列表
        new_report['issues'] = issues_with_fixes

        return ResponseModel(
            success=True,
            message="重新分析完成",
            data={
                "new_report": new_report,
                "score_changes": score_changes
            }
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
    """
    取消正在执行的质控检测任务

    Args:
        project_id: 项目ID

    Returns:
        取消结果
    """
    try:
        # 查找该用户在此项目上的活跃质控任务
        task_id_prefix = f"qc_{current_user.id}_"

        # 从SSE订阅管理器中查找并取消相关任务
        from .quality_control_v2 import get_qc_subscriber
        subscriber = get_qc_subscriber()

        # 标记任务为已取消（通过发布取消事件）
        # 注意：这里采用标记方式，实际任务会在下一批次检查时自动停止
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
    """
    提交质量检测反馈

    记录用户对检测结果的反馈,用于优化后续检测

    Args:
        issue_id: 问题ID
        dimension: 维度 (unit_structure/unit_character/unit_consistency)
        category: 问题分类
        feedback_type: 反馈类型 (accepted/ignored/false_positive)
        comment: 用户备注

    Returns:
        提交结果
    """
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


# ==================== 全局大纲质控 API ====================

class GlobalOutlineQCRequest(BaseModel):
    """全局大纲质量检测请求"""
    dimensions: Optional[List[str]] = None  # 分析维度(可选,默认全部四维度)
    depth: str = "standard"          # 分析深度(quick/standard/deep)
    existing_outline: Optional[str] = ""  # 全局大纲内容(两阶段模式由前端传递)


class GlobalOutlineReviseRequest(BaseModel):
    """全局大纲修正请求"""
    quality_report: Dict[str, Any]   # 质控报告
    issues_to_fix: List[str]         # 需要修正的问题ID列表


@router.post("/quality-control/global-outline/{project_id}")
async def analyze_global_outline_quality(
    project_id: int,
    request: GlobalOutlineQCRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    对全局大纲执行质量检测(用户手动触发)

    注意:
    - project_id=0 表示两阶段大纲模式的全局大纲阶段(无项目)
    - project_id>0 表示普通模式或单元概述阶段(有项目)

    LLM分析可能需要10-20分钟,前端需设置足够超时时间(1200000ms)

    v1.1新增: 支持SSE实时进度推送
    """
    try:
        # v1.1新增: 生成task_id用于SSE推送
        task_id = f"qc_{current_user.id}_{uuid.uuid4().hex[:8]}"

        logger.info(
            f"[全局大纲质控API] 开始检测: project_id={project_id}, "
            f"user_id={current_user.id}, dimensions={request.dimensions}, task_id={task_id}"
        )

        # 1. 获取全局大纲内容
        global_outline_content = None
        project = None  # 初始化project变量,避免作用域问题

        if project_id == 0:
            # 两阶段大纲模式: 全局大纲内容由前端传递
            logger.info("[全局大纲质控API] 两阶段模式,使用前端传递的内容")
            global_outline_content = request.existing_outline or ''
        else:
            # 普通模式: 从数据库获取项目
            from sqlalchemy import select
            from app.models import NovelProject

            query = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                logger.error(f"[全局大纲质控API] 项目不存在: {project_id}")
                return ResponseModel(
                    success=False,
                    message=f"项目不存在: {project_id}"
                )

            global_outline_content = getattr(
                project, 'global_outline_content', None) or ''
            logger.info(f"[全局大纲质控API] 从数据库获取项目: {project_id}")

        if not global_outline_content:
            logger.error("[全局大纲质控API] 全局大纲内容为空")
            return ResponseModel(
                success=False,
                message="全局大纲内容为空,请先生成全局大纲"
            )

        logger.info(f"[全局大纲质控API] 大纲内容长度: {len(global_outline_content)} 字")

        # 3. 调用质控分析
        from app.services.outline_generator import get_outline_generator
        outline_generator = get_outline_generator(db)

        quality_report = await outline_generator.analyze_global_outline_quality(
            global_outline_content=global_outline_content,
            project=project,  # 两阶段模式下为None,普通模式下为项目对象
            user_id=current_user.id,
            dimensions=request.dimensions,
            depth=request.depth,
            task_id=task_id  # v1.1新增: 传递task_id以支持SSE推送
        )

        # 4. 保存质控报告到项目(仅普通模式)
        if project is not None:
            project.global_outline_quality_report = quality_report
            await db.commit()
            logger.info(f"[全局大纲质控API] 已保存质控报告到项目: {project_id}")
        else:
            logger.info("[全局大纲质控API] 两阶段模式,跳过数据库保存")

        logger.info(
            f"[全局大纲质控API] 检测完成: project_id={project_id}, "
            f"overall_score={quality_report.get('overall_score', 0)}"
        )

        return ResponseModel(
            success=True,
            message="质量检测完成",
            data=quality_report,
            task_id=task_id  # v1.1新增: 返回task_id供前端订阅SSE
        )

    except Exception as e:
        logger.error(f"[全局大纲质控API] 检测失败: {str(e)}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"质量检测失败: {str(e)}"
        )


@router.post("/quality-control/global-outline/{project_id}/revise")
async def revise_global_outline(
    project_id: int,
    request: GlobalOutlineReviseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    根据质控报告修正全局大纲

    注意: LLM修正可能需要10-20分钟,前端需设置足够超时时间(1200000ms)
    修正后直接更新 project.global_outline_content 字段
    """
    try:
        logger.info(
            f"[全局大纲修正API] 开始修正: project_id={project_id}, "
            f"user_id={current_user.id}, issues_count={len(request.issues_to_fix)}"
        )

        # 1. 获取项目和大纲内容
        project = None
        original_outline = None

        if project_id == 0:
            # 两阶段大纲模式: 从质控报告中获取原始大纲
            logger.info("[全局大纲修正API] 两阶段模式,从质控报告获取原始大纲")
            original_outline = request.quality_report.get(
                'original_outline', '')
            if not original_outline:
                return ResponseModel(
                    success=False,
                    message="质控报告中缺少原始大纲内容"
                )
        else:
            # 普通模式: 从数据库获取项目
            from sqlalchemy import select
            from app.models import NovelProject

            query = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                return ResponseModel(
                    success=False,
                    message=f"项目不存在: {project_id}"
                )

            original_outline = getattr(
                project, 'global_outline_content', None) or ''

        if not original_outline:
            return ResponseModel(
                success=False,
                message="全局大纲内容为空"
            )

        # 3. 调用修正方法
        from app.services.outline_generator import get_outline_generator
        outline_generator = get_outline_generator(db)

        revision_result = await outline_generator.revise_global_outline_by_quality(
            original_outline=original_outline,
            quality_report=request.quality_report,
            issues_to_fix=request.issues_to_fix,
            project=project,  # 两阶段模式下为None
            user_id=current_user.id
        )

        if not revision_result.get("success"):
            return ResponseModel(
                success=False,
                message=f"修正失败: {revision_result.get('error', '未知错误')}"
            )

        # 4. 保存修正后的大纲
        revised_content = revision_result.get("revised_content")

        if project is not None:
            # 普通模式: 保存到数据库
            project.global_outline_content = revised_content
            project.global_outline_quality_report = {
                **request.quality_report,
                "revised": True,
                "revised_at": datetime.now().isoformat(),
                "revised_issues": request.issues_to_fix
            }
            await db.commit()
            logger.info(f"[全局大纲修正API] 已保存修正内容到项目: {project_id}")
        else:
            # 两阶段模式: 返回修正内容,由前端处理
            logger.info("[全局大纲修正API] 两阶段模式,返回修正内容给前端")

        logger.info(
            f"[全局大纲修正API] 修正完成: project_id={project_id}, "
            f"original_length={len(original_outline)}, "
            f"revised_length={len(revised_content)}"
        )

        return ResponseModel(
            success=True,
            message="全局大纲修正完成",
            data={
                "revised_content": revised_content,
                "changes": revision_result.get("changes", []),
                "original_length": len(original_outline),
                "revised_length": len(revised_content)
            }
        )

    except Exception as e:
        logger.error(f"[全局大纲修正API] 修正失败: {str(e)}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"修正失败: {str(e)}"
        )


# ==================== 导入大纲自动质控修正API (v2.3新增) ====================

@router.post("/quality-control/imported-outline/auto-revise", response_model=ResponseModel)
async def auto_revise_imported_outline(
    request: ImportedOutlineAutoReviseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    对导入的大纲自动执行质控修正（v2.3新增）

    用于"导入已有大纲"场景，用户点击"重新检测"按钮时调用。
    自动执行质量检测并修正所有问题。

    Args:
        outline_content: 导入的大纲内容
        dimensions: 分析维度（可选，默认四维度）
        depth: 分析深度（默认quick）

    Returns:
        {
            success: bool,
            revised_content: str,  # 修正后的内容
            issues_fixed: int,     # 修正的问题数
            qc_report: dict        # 质控报告
        }
    """
    try:
        logger.info(
            f"[导入大纲自动质控] 用户 {current_user.id} 请求自动质控修正, "
            f"内容长度: {len(request.outline_content)}"
        )

        if not request.outline_content or len(request.outline_content.strip()) < 100:
            return ResponseModel(
                success=False,
                message="大纲内容过短，无法进行质量检测"
            )

        # 获取大纲生成器
        from app.services.outline_generator import get_outline_generator
        outline_generator = get_outline_generator(db)

        # 执行自动质控修正
        qc_result = await outline_generator._auto_qc_and_revise(
            content=request.outline_content,
            user_id=current_user.id,
            llm_provider=None,  # 会在方法内部获取
            dimensions=request.dimensions,
            depth=request.depth
        )

        if qc_result.get("success"):
            revised_content = qc_result.get("revised_content")
            issues_fixed = qc_result.get("issues_fixed", 0)
            qc_report = qc_result.get("qc_report")

            # 更新质控报告标记
            if qc_report:
                qc_report["source"] = "imported_outline"
                qc_report["auto_applied"] = True
                qc_report["applied_at"] = datetime.now().isoformat()

            logger.info(
                f"[导入大纲自动质控] 完成，修正 {issues_fixed} 个问题"
            )

            return ResponseModel(
                success=True,
                message=f"质量检测完成，已修正 {issues_fixed} 个问题" if issues_fixed > 0 else "质量检测完成，未发现需要修正的问题",
                data={
                    "revised_content": revised_content,
                    "issues_fixed": issues_fixed,
                    "qc_report": qc_report,
                    "original_length": len(request.outline_content),
                    "revised_length": len(revised_content) if revised_content else len(request.outline_content)
                }
            )
        else:
            error_msg = qc_result.get("error", "未知错误")
            logger.warning(f"[导入大纲自动质控] 执行失败: {error_msg}")
            return ResponseModel(
                success=False,
                message=f"质量检测失败: {error_msg}",
                data={
                    "qc_report": qc_result.get("qc_report")
                }
            )

    except Exception as e:
        logger.error(f"[导入大纲自动质控] 执行失败: {str(e)}", exc_info=True)
        return ResponseModel(
            success=False,
            message=f"质量检测失败: {str(e)}"
        )


# ==================== SSE实时推送 (v1.1新增) ====================

# 全局SSE订阅管理器
class QCProgressSubscriber:
    """质控进度SSE订阅管理器

    v1.1新增: 资源清理机制
    - 订阅数上限: 每个任务最多5个订阅者
    - 任务超时: 1小时后自动清理
    """

    MAX_SUBSCRIBERS_PER_TASK = 5  # 每个任务最多5个订阅者
    TASK_TIMEOUT = 3600  # 1小时后自动清理

    def __init__(self):
        # task_id -> {"queues": list, "created_at": datetime}
        self._subscribers: Dict[str, dict] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """订阅任务进度

        Raises:
            ValueError: 订阅数已达上限
        """
        # 清理过期任务
        self._cleanup_expired_tasks()

        if task_id not in self._subscribers:
            self._subscribers[task_id] = {
                "queues": [],
                "created_at": datetime.now()
            }

        # 检查订阅数上限
        if len(self._subscribers[task_id]["queues"]) >= self.MAX_SUBSCRIBERS_PER_TASK:
            logger.warning(f"[SSE订阅] 任务 {task_id} 订阅数已达上限")
            raise ValueError(f"任务 {task_id} 订阅数已达上限")

        queue = asyncio.Queue()
        self._subscribers[task_id]["queues"].append(queue)
        logger.info(
            f"[SSE订阅] task_id={task_id}, 当前订阅数: {len(self._subscribers[task_id]['queues'])}")
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue):
        """取消订阅"""
        if task_id in self._subscribers:
            if queue in self._subscribers[task_id]["queues"]:
                self._subscribers[task_id]["queues"].remove(queue)
            if not self._subscribers[task_id]["queues"]:
                del self._subscribers[task_id]
                logger.info(f"[SSE取消订阅] 任务 {task_id} 已清理")
            else:
                logger.info(
                    f"[SSE取消订阅] task_id={task_id}, 剩余订阅数: {len(self._subscribers[task_id]['queues'])}")

    async def publish(self, task_id: str, event: Dict):
        """发布进度事件"""
        # 触发清理过期任务(防止内存泄漏)
        self._cleanup_expired_tasks()

        if task_id in self._subscribers:
            for queue in self._subscribers[task_id]["queues"]:
                try:
                    await queue.put(event)
                except Exception as e:
                    logger.warning(f"[SSE发布] 队列推送失败: {e}")

    def _cleanup_expired_tasks(self):
        """清理过期任务"""
        now = datetime.now()
        expired_tasks = []

        for task_id, data in list(self._subscribers.items()):
            created_at = data.get("created_at", now)
            if (now - created_at).total_seconds() > self.TASK_TIMEOUT:
                expired_tasks.append(task_id)

        for task_id in expired_tasks:
            del self._subscribers[task_id]
            logger.info(f"[SSE清理] 过期任务已清理: {task_id}")

    def get_task_count(self) -> int:
        """获取当前任务数"""
        return len(self._subscribers)

    def get_total_subscribers(self) -> int:
        """获取总订阅者数"""
        return sum(len(data["queues"]) for data in self._subscribers.values())


# 全局订阅实例
_qc_subscriber = QCProgressSubscriber()


def get_qc_subscriber() -> QCProgressSubscriber:
    """获取质控SSE订阅器单例"""
    return _qc_subscriber


async def event_generator(task_id: str, queue: asyncio.Queue):
    """
    SSE事件生成器

    格式:
    event: progress
    data: {"dimension": "global_structure", "status": "started", "progress": 0}
    """
    try:
        # 发送连接成功事件
        yield f"event: connected\ndata: {json.dumps({'task_id': task_id, 'message': 'SSE连接成功'})}\n\n"

        # 持续推送进度事件
        while True:
            try:
                # 等待新事件(超时30秒发送心跳)
                event = await asyncio.wait_for(queue.get(), timeout=30.0)

                # 检查是否为结束事件
                if event.get("type") == "completed" or event.get("type") == "error":
                    # 发送最后的事件
                    yield f"event: {event.get('type', 'progress')}\ndata: {json.dumps(event)}\n\n"
                    logger.info(
                        f"[SSE推送] 任务结束: task_id={task_id}, type={event.get('type')}")
                    break

                # 推送进度事件
                yield f"event: progress\ndata: {json.dumps(event)}\n\n"

            except asyncio.TimeoutError:
                # 发送心跳保活
                yield f": heartbeat\n\n"

    except Exception as e:
        logger.error(f"[SSE推送] 事件生成器异常: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    finally:
        # 清理订阅
        _qc_subscriber.unsubscribe(task_id, queue)
        logger.info(f"[SSE推送] 连接关闭: task_id={task_id}")


@router.get("/quality-control/global-outline/{task_id}/events")
async def subscribe_qc_progress(
    task_id: str,
    current_user: User = Depends(
        get_current_user_from_query_or_header)  # 支持Query参数认证（SSE场景）
):
    """
    SSE端点: 订阅全局大纲质控进度

    使用方式:
    const eventSource = new EventSource(`/api/v1/novel-writer/quality-control/global-outline/${taskId}/events?token=xxx`)

    事件类型:
    - connected: 连接成功
    - progress: 进度更新
    - completed: 完成
    - error: 错误
    """
    logger.info(
        f"[SSE端点] 订阅质控进度: task_id={task_id}, user_id={current_user.id}")

    # 创建订阅队列
    queue = _qc_subscriber.subscribe(task_id)

    # 返回SSE流
    return StreamingResponse(
        event_generator(task_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
            "Access-Control-Allow-Origin": "*"
        }
    )


async def publish_qc_progress(
    task_id: str,
    event_type: str,
    dimension: str = None,
    status: str = None,
    progress: float = None,
    message: str = None,
    data: Dict = None
):
    """
    发布质控进度事件(供业务逻辑调用)

    Args:
        task_id: 任务ID
        event_type: 事件类型(started/progress/completed/error)
        dimension: 维度名称
        status: 状态(running/success/failed)
        progress: 进度(0-100)
        message: 消息
        data: 附加数据
    """
    event = {
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id
    }

    if dimension:
        event["dimension"] = dimension
    if status:
        event["status"] = status
    if progress is not None:
        event["progress"] = progress
    if message:
        event["message"] = message
    if data:
        event["data"] = data

    await _qc_subscriber.publish(task_id, event)
    logger.debug(
        f"[SSE发布] task_id={task_id}, type={event_type}, "
        f"dimension={dimension}, progress={progress}"
    )


# ==================== 实时质控 API端点 (v2.0新增) ====================

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
            WritingTask.project_id == project_id
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
        )
        unit_result = await db.execute(unit_query)
        unit = unit_result.scalar_one_or_none()

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
            "summary": content[:500],
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
            user_id=current_user.id
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
        # （注意：这里需要找到正确的WritingUnit记录并更新）
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
    """
    撤销单元的自动修正

    Args:
        project_id: 项目ID
        unit_index: 单元序号
        fix_id: 要撤销的修正ID（可选，为None则撤销所有修正）

    Returns:
        撤销结果
    """
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
        unit = unit_result.scalar_one_or_none()

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
