"""
质量管控 API 端点

提供质量分析、报告查询等功能

@date: 2026-04-12
@version: v3.1.0
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, QualityReport
from app.schemas.common import ResponseModel
from app.core.exceptions import ResourceNotFoundException, ValidationException

from .utils import router, logger

# ==================== 请求/响应模型 ====================


class QualityAnalysisRequest(BaseModel):
    """质量分析请求"""
    project_id: int
    chapter_ids: Optional[List[int]] = None  # null表示全部
    dimensions: Optional[List[str]] = None  # null表示全部
    analysis_depth: str = "standard"  # quick/standard/deep


class QualityReportResponse(BaseModel):
    """质量报告响应"""
    report_id: Optional[int] = None
    project_id: int
    analysis_scope: str
    dimensions: List[str]
    overall_score: float
    dimension_scores: Dict[str, float]
    issues: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    is_cached: bool = False


# ==================== API端点 ====================

@router.post("/projects/{project_id}/quality-control/analyze", response_model=ResponseModel[QualityReportResponse])
async def analyze_quality(
    project_id: int,
    request: QualityAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    执行质量分析

    对指定项目/章节进行六维度质量分析

    分析维度:
    - structure: 宏观结构(情节节奏、伏笔回收)
    - character: 人物塑造(角色一致性、台词指纹)
    - scene: 场景感官(五感平衡、时空跳跃)
    - prose: 文笔修辞(高频词、被动语态)
    - experience: 阅读体验(章末悬念、金句密度)
    - technical: 技术排雷(视角越界、敏感内容)

    分析深度:
    - quick: 仅规则引擎,零Token,秒级返回
    - standard: 规则+轻量LLM,约2K tokens/章
    - deep: 全量分析,约5K tokens/章
    """
    try:
        from app.services.quality_control import get_quality_control_service

        service = get_quality_control_service(db)

        result = await service.analyze(
            user_id=current_user.id,
            project_id=project_id,
            chapter_ids=request.chapter_ids,
            dimensions=request.dimensions,
            analysis_depth=request.analysis_depth
        )

        logger.info(
            f"用户 {current_user.id} 质量分析完成 - "
            f"项目: {project_id}, "
            f"深度: {request.analysis_depth}, "
            f"评分: {result.get('overall_score')}"
        )

        return ResponseModel(
            success=True,
            data=QualityReportResponse(**result)
        )

    except ValueError as e:
        logger.warning(f"质量分析参数错误: {str(e)}")
        raise ValidationException(str(e))
    except Exception as e:
        logger.error(f"质量分析失败: {str(e)}", exc_info=True)
        raise ValidationException(f"分析失败: {str(e)}")


@router.get("/projects/{project_id}/quality-control/reports", response_model=ResponseModel[List[Dict]])
async def get_quality_reports(
    project_id: int,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取历史质量报告列表

    返回指定项目的最近N次分析报告摘要
    """
    try:
        query = select(QualityReport).where(
            QualityReport.project_id == project_id,
            QualityReport.user_id == current_user.id,
            QualityReport.status == "completed"
        ).order_by(
            QualityReport.created_at.desc()
        ).limit(limit)

        result = await db.execute(query)
        reports = result.scalars().all()

        reports_data = [report.to_summary_dict() for report in reports]

        return ResponseModel(
            success=True,
            data=reports_data
        )

    except Exception as e:
        logger.error(f"获取报告列表失败: {str(e)}")
        raise ValidationException(f"获取失败: {str(e)}")


@router.get("/quality-control/reports/{report_id}", response_model=ResponseModel[QualityReportResponse])
async def get_quality_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取详细质量报告

    根据报告ID获取完整的分析结果
    """
    try:
        query = select(QualityReport).where(
            QualityReport.id == report_id,
            QualityReport.user_id == current_user.id
        )

        result = await db.execute(query)
        report = result.scalar_one_or_none()

        if not report:
            raise ResourceNotFoundException("报告不存在")

        if report.status != "completed":
            raise ValidationException(f"报告尚未完成,当前状态: {report.status}")

        report_data = report.report_data
        report_data["report_id"] = report.id
        report_data["is_cached"] = report.is_cached

        return ResponseModel(
            success=True,
            data=QualityReportResponse(**report_data)
        )

    except ResourceNotFoundException:
        raise
    except Exception as e:
        logger.error(f"获取报告失败: {str(e)}")
        raise ValidationException(f"获取失败: {str(e)}")


@router.delete("/quality-control/reports/{report_id}", response_model=ResponseModel)
async def delete_quality_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除质量报告

    删除指定的历史分析报告
    """
    try:
        query = select(QualityReport).where(
            QualityReport.id == report_id,
            QualityReport.user_id == current_user.id
        )

        result = await db.execute(query)
        report = result.scalar_one_or_none()

        if not report:
            raise ResourceNotFoundException("报告不存在")

        await db.delete(report)
        await db.commit()

        logger.info(f"用户 {current_user.id} 删除报告: {report_id}")

        return ResponseModel(
            success=True,
            message="报告已删除"
        )

    except ResourceNotFoundException:
        raise
    except Exception as e:
        logger.error(f"删除报告失败: {str(e)}")
        raise ValidationException(f"删除失败: {str(e)}")
