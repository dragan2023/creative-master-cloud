"""
content_pipeline/ 包 - 内容生成流水线

将原 content_pipeline.py 拆分为多个功能模块，通过 Mixin 多重继承组合。

包结构:
    __init__.py: 统一导出 ContentPipelineMixin（从子 Mixin 组合）
    _core_execution.py: 核心执行流程 (execute)
    _unit_direct.py: 整章直接生成模式 (_process_unit_direct)
    _db_operations.py: 单元/场景数据库操作

注意：场景拆解模式（_process_unit）及其依赖（_concurrent_writer, _review_pipeline）已废弃并移除，
系统统一使用整章直接生成模式（direct mode）。

@date: 2026-04-24
@version: v3.1.0 (清理废弃的场景拆解模式)
"""
from ._core_execution import CoreExecutionMixin
from ._unit_direct import UnitDirectMixin
from ._db_operations import DBOperationsMixin


class ContentPipelineMixin(
    CoreExecutionMixin,
    UnitDirectMixin,
    DBOperationsMixin,
):
    """内容生成流水线 Mixin

    通过多重继承组合各功能子模块，提供：
    - 核心执行流程 (execute)
    - 整章直接生成模式 (_process_unit_direct)
    - 单元/场景数据库操作
    """
    pass


__all__ = ["ContentPipelineMixin"]
