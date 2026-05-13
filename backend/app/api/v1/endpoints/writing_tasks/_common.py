"""
写作任务 API - 公共辅助函数

@date: 2026-04-24
@version: v3.1.0 (从writing_tasks.py拆分)
"""
from app.models.writing_task import WritingTask, TaskStatus
from app.models.writing_unit import WritingUnit
from app.models.writing_scene import WritingScene
from app.schemas.writing_task import (
    WritingTaskResponse, WritingUnitResponse, WritingSceneResponse,
)


def _build_task_response(task: WritingTask) -> WritingTaskResponse:
    """构建任务响应对象"""
    return WritingTaskResponse(
        id=task.id,
        uuid=task.uuid,
        project_id=task.project_id,
        user_id=task.user_id,
        status=task.status.value if isinstance(
            task.status, TaskStatus) else task.status,
        total_units=task.total_units,
        completed_units=task.completed_units,
        config=task.config or {},
        total_tokens=task.total_tokens,
        total_cost=task.total_cost,
        error_message=task.error_message,
        start_time=task.start_time,
        end_time=task.end_time,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


def _build_unit_response(unit: WritingUnit) -> WritingUnitResponse:
    """构建单元响应对象"""
    # 构建质控信息
    qc_status = unit.quality_control_status
    qc_score = unit.quality_control_score
    qc_report = unit.quality_control_report
    qc_fixes = unit.quality_control_fixes

    return WritingUnitResponse(
        id=unit.id,
        task_id=unit.task_id,
        unit_index=unit.unit_index,
        unit_title=unit.unit_title,
        unit_summary=unit.unit_summary,
        status=unit.status.value if hasattr(
            unit.status, 'value') else unit.status,
        word_count=unit.word_count,
        token_count=unit.token_count,
        duration_ms=unit.duration_ms,
        quality_control_status=qc_status if qc_status and qc_status != 'pending' else None,
        quality_control_score=qc_score if qc_score and qc_score > 0 else None,
        quality_control_report=qc_report if qc_report else None,
        quality_control_fixes=qc_fixes if qc_fixes else None,
        original_content_before_fix=unit.original_content_before_fix,
        final_content=unit.final_content,
        content_after_generation=unit.content_after_generation,
        content_after_qc_fix=unit.content_after_qc_fix,
        created_at=unit.created_at,
        updated_at=unit.updated_at
    )


def _build_scene_response(scene: WritingScene) -> WritingSceneResponse:
    """构建场景响应对象"""
    return WritingSceneResponse(
        id=scene.id,
        unit_id=scene.unit_id,
        scene_index=scene.scene_index,
        scene_title=scene.scene_title,
        scene_outline=scene.scene_outline or {},
        status=scene.status.value if hasattr(
            scene.status, 'value') else scene.status,
        final_content=scene.final_content,
        word_count=scene.word_count,
        token_count=scene.token_count,
        duration_ms=scene.duration_ms,
        created_at=scene.created_at,
        updated_at=scene.updated_at
    )
