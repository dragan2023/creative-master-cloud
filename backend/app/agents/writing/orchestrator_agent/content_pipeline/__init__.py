"""
content_pipeline/ 包 - 内容生成流水线

将原 content_pipeline.py 拆分为多个功能模块，通过 Mixin 多重继承组合。

包结构:
    __init__.py: 统一导出 ContentPipelineMixin（从子 Mixin 组合）
    _core_execution.py: 核心执行流程 (execute)
    _process_unit.py: 单元处理方法 (_process_unit)
    _unit_direct.py: 直接生成模式 (_process_unit_direct)
    _concurrent_writer.py: 并发写作 (_concurrent_write_scenes)
    _review_pipeline.py: 审阅流水线 (_run_review_pipeline_for_unit)
    _db_operations.py: 单元/场景数据库操作

@date: 2026-04-24
@version: v3.0.0
"""
from ._core_execution import CoreExecutionMixin
from ._process_unit import ProcessUnitMixin
from ._unit_direct import UnitDirectMixin
from ._concurrent_writer import ConcurrentWriterMixin
from ._review_pipeline import ReviewPipelineMixin
from ._db_operations import DBOperationsMixin


class ContentPipelineMixin(
    CoreExecutionMixin,
    ProcessUnitMixin,
    UnitDirectMixin,
    ConcurrentWriterMixin,
    ReviewPipelineMixin,
    DBOperationsMixin,
):
    """内容生成流水线 Mixin

    通过多重继承组合各功能子模块，提供：
    - 核心执行流程 (execute)
    - 单元处理 (_process_unit)
    - 直接生成模式 (_process_unit_direct)
    - 并发写作 (_concurrent_write_scenes)
    - 审阅流水线 (_run_review_pipeline_for_unit)
    - 单元/场景数据库操作
    """
    pass


__all__ = ["ContentPipelineMixin"]
