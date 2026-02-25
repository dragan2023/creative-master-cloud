"""
全能创意大师 - FastAPI 应用入口
"""
from app.api.v1.router import api_router
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import time
import os

from app.core.config import get_settings
from app.core.logger import init_logging, get_logger


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """请求体大小限制中间件"""

    def __init__(self, app, max_content_length: int):
        super().__init__(app)
        self.max_content_length = max_content_length

    async def dispatch(self, request: Request, call_next):
        # 检查 Content-Length 头
        content_length = request.headers.get("content-length")
        if content_length:
            content_length = int(content_length)
            if content_length > self.max_content_length:
                return JSONResponse(
                    status_code=413,
                    content={
                        "code": 413, "message": f"请求体大小超过限制 ({self.max_content_length / 1024 / 1024}MB)"}
                )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    init_logging()
    logger = get_logger("startup")
    logger.info(
        f"应用启动: {get_settings().APP_NAME} v{get_settings().APP_VERSION}")

    # 关闭 uvicorn 访问日志
    import logging
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    # 初始化数据库表并运行迁移
    from app.core.database import init_db
    await init_db()
    logger.info("数据库表初始化完成")

    yield

    # 关闭时清理
    logger.info("应用关闭")


# 创建 FastAPI 应用实例
settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于大语言模型的智能创意辅助软件",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 添加请求体大小限制中间件
print(f"[INFO] 设置文件上传限制: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB")
app.add_middleware(RequestSizeLimitMiddleware,
                   max_content_length=settings.MAX_UPLOAD_SIZE)


# CORS 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),  # 从配置读取允许的源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求计时中间件
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = get_logger("system")
    import traceback
    error_detail = f"{type(exc).__name__}: {str(exc)}"
    full_traceback = traceback.format_exc()
    logger.error(f"未处理的异常: {error_detail}\n{full_traceback}")

    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": error_detail if settings.DEBUG else None
        }
    )


# 健康检查端点
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# 注册路由
app.include_router(api_router, prefix="/api/v1")


# 托管前端静态文件（生产环境）
# 获取前端构建目录 - backend 目录的兄弟目录 frontend/dist
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    # 挂载静态资源目录
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # 根路径处理
    @app.get("/", tags=["前端"])
    async def serve_index():
        """返回首页"""
        index_path = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return JSONResponse(status_code=404, content={"detail": "Frontend not built"})

    # SPA 路由处理 - 所有非 API 路由返回 index.html
    @app.get("/{full_path:path}", tags=["前端"])
    async def serve_spa(full_path: str):
        """处理 SPA 路由，返回 index.html"""
        # API 路由和文档路由不处理
        if full_path.startswith("api/") or full_path in ["docs", "redoc", "openapi.json", "health"]:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        # 检查是否是静态文件请求
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # 返回 index.html（SPA 路由）
        index_path = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)

        return JSONResponse(status_code=404, content={"detail": "Frontend not built"})


if __name__ == "__main__":
    import uvicorn
    import logging

    # 关闭 uvicorn 访问日志
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        access_log=False  # 关闭访问日志
    )
