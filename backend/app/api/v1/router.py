"""
API V1 路由聚合

# [2026-03-28] 多Agent重构: 添加writing_tasks和agent_config路由
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, generate, knowledge, update, mcp, novel_writer, tenant_auth, admin, writing_tasks, agent_config, writing_model_config


api_router = APIRouter()

# 健康检查端点（兼容旧版启动脚本）


@api_router.get("/health", tags=["系统"])
async def api_health_check():
    """API健康检查接口"""
    return {"status": "healthy", "endpoint": "api/v1/health"}

# 注册各模块路由
api_router.include_router(auth.router)
api_router.include_router(tenant_auth.router)  # 租户认证路由
api_router.include_router(admin.router)  # 后台管理路由
api_router.include_router(generate.router)
api_router.include_router(knowledge.router)
api_router.include_router(update.router)
api_router.include_router(mcp.router)
api_router.include_router(novel_writer.router)
api_router.include_router(writing_tasks.router)  # 多Agent写作任务路由
api_router.include_router(agent_config.router)  # Agent配置路由
api_router.include_router(writing_model_config.router)  # 写作模型配置路由
