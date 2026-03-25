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
import sys
import signal
import threading

from app.core.config import get_settings
from app.core.logger import init_logging, get_logger


def _open_browser_delayed(frontend_url: str, delay: float = 3.0):
    """延迟打开浏览器的后台线程函数"""
    import time
    import webbrowser
    time.sleep(delay)  # 等待服务完全就绪
    try:
        print(f"\n[INFO] 正在打开浏览器访问前端: {frontend_url}")
        webbrowser.open(frontend_url)
    except Exception as e:
        print(f"[WARN] 打开浏览器失败: {e}")


def _start_browser_opener():
    """启动后台线程自动打开浏览器"""
    frontend_url = "http://localhost:8000"
    thread = threading.Thread(
        target=_open_browser_delayed,
        args=(frontend_url, 3.0),
        daemon=True
    )
    thread.start()


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

    # 清理上次服务器退出时遗留的幽灵运行任务
    # 服务器重启后，内存中的任务状态丢失，数据库中残留 running 状态的任务已无法继续
    # 将其标记为 failed，避免前端页面刷新后误认为任务仍在运行
    try:
        from sqlalchemy import update
        from app.core.database import async_session_maker
        from app.models.novel_project import NovelProject
        async with async_session_maker() as db:
            result = await db.execute(
                update(NovelProject)
                .where(NovelProject.generation_task_status == 'running')
                .values(generation_task_status='failed')
            )
            await db.commit()
            if result.rowcount > 0:
                logger.warning(
                    f"清理了 {result.rowcount} 个遗留的幽灵运行任务（已标记为 failed）")
    except Exception as e:
        logger.warning(f"清理幽灵任务失败（不影响启动）: {e}")

    # ChromaDB 向量库健康检查和数据完整性验证
    try:
        from app.core.vector_store import get_vector_store
        vector_store = get_vector_store()
        health = vector_store.health_check()

        if health["healthy"]:
            logger.info(f"ChromaDB 健康检查通过，集合数: {len(health['collections'])}")

            # 检查数据完整性：对比向量库数据与图谱文件
            for coll_info in health["collections"]:
                coll_name = coll_info["name"]
                coll_count = coll_info.get("count", 0)

                # 只检查项目知识库集合
                if coll_name.startswith("project_") and coll_name.endswith("_kb"):
                    # 提取项目ID
                    try:
                        project_id = int(coll_name.replace(
                            "project_", "").replace("_kb", ""))

                        # 检查图谱文件是否存在
                        settings = get_settings()
                        graph_dir = settings.get_knowledge_graph_dir()
                        global_graph_path = os.path.join(
                            graph_dir, f"project_{project_id}_global_graph.json")

                        if os.path.exists(global_graph_path) and coll_count == 0:
                            logger.warning(
                                f"检测到向量库数据丢失: collection={coll_name}, "
                                f"图谱文件存在但向量库为空。数据将在下次知识库构建时恢复。"
                            )
                    except (ValueError, Exception) as e:
                        logger.debug(f"解析项目ID失败: {coll_name}, error={e}")
        else:
            logger.warning(f"ChromaDB 健康检查发现问题: {health['errors']}")
            # 尝试自动修复
            repair_report = vector_store.repair_all_collections()
            if repair_report["repaired"] > 0:
                logger.info(f"ChromaDB 自动修复完成: {repair_report}")
            elif repair_report["failed"] > 0:
                logger.warning(f"ChromaDB 自动修复部分失败: {repair_report}")
    except Exception as e:
        logger.warning(f"ChromaDB 健康检查失败（不影响启动）: {e}")

    # 启动后自动打开浏览器
    _start_browser_opener()

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
    # 记录完整的异常堆栈
    logger.error(f"未处理的异常: {error_detail}\n{full_traceback}")

    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": error_detail if settings.DEBUG else None,
            "traceback": full_traceback if settings.DEBUG else None
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


# 退出程序端点
@app.post("/api/v1/system/exit", tags=["系统"])
async def exit_application():
    """
    退出程序接口
    执行清理操作后关闭应用程序
    """
    logger = get_logger("system")
    logger.info("收到退出程序请求，开始执行清理操作...")

    try:
        # 1. 关闭数据库引擎（会自动关闭所有连接）
        try:
            from app.core.database import engine
            await engine.dispose()
            logger.info("数据库连接已关闭")
        except Exception as e:
            logger.warning(f"关闭数据库连接时出错: {e}")

        # 2. 关闭Redis连接（如果存在）
        try:
            from app.core.redis_client import redis_manager
            if redis_manager and hasattr(redis_manager, 'close'):
                await redis_manager.close()
                logger.info("Redis连接已关闭")
        except ImportError:
            pass  # Redis模块不存在
        except Exception as e:
            logger.warning(f"关闭Redis连接时出错: {e}")

        logger.info("清理操作完成，准备退出程序...")

    except Exception as e:
        logger.error(f"退出清理过程中发生错误: {e}")

    # 在后台线程中延迟退出，确保HTTP响应能够返回
    def do_exit():
        import time
        time.sleep(0.5)  # 等待HTTP响应发送完成
        logger.info("程序退出")
        os._exit(0)  # 强制退出，确保所有线程终止

    exit_thread = threading.Thread(target=do_exit, daemon=True)
    exit_thread.start()

    return {"code": 0, "message": "程序正在退出...", "success": True}


# 注册路由
app.include_router(api_router, prefix="/api/v1")


# 托管前端静态文件（生产环境）
# Docker 镜像中前端构建产物位于 /app/app/static
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.join(BACKEND_DIR, "app", "static")

if os.path.exists(FRONTEND_DIST) and os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
    print(f"[INFO] 前端静态文件目录：{FRONTEND_DIST}")

    # 挂载静态资源目录
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # 根路径处理
    @app.get("/", tags=["前端"])
    async def serve_index():
        """返回首页"""
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

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
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
else:
    print(f"[WARN] 前端静态文件未找到: {FRONTEND_DIST}")


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
