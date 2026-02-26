"""
API V1 路由聚合
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, generate, knowledge, update


api_router = APIRouter()

# 健康检查端点（兼容旧版启动脚本）


@api_router.get("/health", tags=["系统"])
async def api_health_check():
    """API健康检查接口"""
    return {"status": "healthy", "endpoint": "api/v1/health"}

# 注册各模块路由
api_router.include_router(auth.router)
api_router.include_router(generate.router)
api_router.include_router(knowledge.router)
api_router.include_router(update.router)
