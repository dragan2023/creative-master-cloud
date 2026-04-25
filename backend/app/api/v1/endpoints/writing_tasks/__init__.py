"""
写作任务 API 端点包

提供写作任务的RESTful API接口，包括创建、查询、控制、删除、导出等操作

从原始 writing_tasks.py (1527行) 拆分为以下模块：
- _common.py: 公共辅助函数（构建响应对象）
- _crud.py: 任务CRUD端点（创建、列表、详情、删除）
- _control.py: 任务控制端点（中断、续传、继续生成）
- _query.py: 查询统计端点（统计、单元列表、场景列表）
- _pipeline.py: 后台Pipeline启动函数
- _export.py: 导出端点（任务导出、单元导出）

@date: 2026-04-24
@version: v3.1.0 (从writing_tasks.py拆分)
"""
from fastapi import APIRouter

from ._common import _build_task_response, _build_unit_response, _build_scene_response
from ._crud import register_crud_routes
from ._control import register_control_routes
from ._query import register_query_routes
from ._export import register_export_routes

# 创建主路由器
router = APIRouter(prefix="/writing-tasks", tags=["多Agent写作任务"])

# 注册各子模块路由
register_crud_routes(router)
register_control_routes(router)
register_query_routes(router)
register_export_routes(router)
