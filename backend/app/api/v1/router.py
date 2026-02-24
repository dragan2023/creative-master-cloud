"""
API V1 路由聚合
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, generate, knowledge, update


api_router = APIRouter()

# 注册各模块路由
api_router.include_router(auth.router)
api_router.include_router(generate.router)
api_router.include_router(knowledge.router)
api_router.include_router(update.router)
