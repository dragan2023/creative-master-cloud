"""
全能创意大师 - FastAPI 应用入口

# [2026-03-28] 多Agent重构: 添加WebSocket端点支持
"""
from app.services.writing_engine.websocket_manager import get_websocket_manager
from app.api.v1.router import api_router
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import time
import os
import json
import logging
import threading
import webbrowser
import traceback

from app.core.config import get_settings
from app.core.logger import init_logging, get_logger
from app.core.exceptions import AppException, ErrorCode
from app.core.error_responses import ErrorResponse
from app.api.deps import get_current_superuser


def _open_browser_delayed(frontend_url: str, delay: float = 3.0):
    """延迟打开浏览器的后台线程函数"""
    time.sleep(delay)  # 等待服务完全就绪
    try:
        print(f"\n[INFO] 正在打开浏览器访问前端: {frontend_url}")
        webbrowser.open(frontend_url)
    except Exception as e:
        print(f"[WARN] 打开浏览器失败: {e}")


def _start_browser_opener():
    """启动后台线程自动打开浏览器"""
    settings = get_settings()

    # 开发环境（DEBUG=True）不自动打开浏览器
    # 前端运行在 Vite 开发服务器上，由前端或启动脚本负责打开
    if settings.DEBUG:
        print("[INFO] 开发环境：跳过自动打开浏览器")
        print("[INFO] 请访问 Vite 开发服务器: http://localhost:3001")
        return

    # 生产环境：打开后端托管的静态文件
    frontend_url = f"http://localhost:{settings.PORT}"
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
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    # 启动安全校验：SECRET_KEY 必须已正确配置
    settings = get_settings()
    if not settings.SECRET_KEY:
        logger.critical(
            "【安全告警】SECRET_KEY 未配置！"
            "请在 .env 文件中设置 SECRET_KEY=<随机字符串>，"
            "否则 JWT 令牌签名将使用空密钥，存在严重安全风险。"
        )
        raise RuntimeError("SECRET_KEY 未配置，拒绝启动以保护系统安全")
    if len(settings.SECRET_KEY) < 32:
        logger.warning(
            f"【安全建议】SECRET_KEY 长度({len(settings.SECRET_KEY)}字符)不足32字符，"
            "建议使用 'openssl rand -hex 32' 生成足够强度的密钥"
        )

    # 初始化数据库表并运行迁移
    from app.core.database import init_db
    await init_db()
    logger.info("数据库表初始化完成")

    # 自动创建超级管理员账号（如果配置了环境变量）
    try:
        from app.core.database import async_session_maker
        from app.core.security import get_password_hash
        from app.models import User, UserRole
        from sqlalchemy import select

        admin_username = os.environ.get("ADMIN_USERNAME")
        admin_password = os.environ.get("ADMIN_PASSWORD")
        admin_email = os.environ.get("ADMIN_EMAIL")

        if admin_username and admin_password and admin_email:
            async with async_session_maker() as db:
                # 检查超级管理员是否已存在
                result = await db.execute(
                    select(User).where(User.role == UserRole.SUPER_ADMIN)
                )
                existing_super_admin = result.scalar_one_or_none()

                if not existing_super_admin:
                    # 检查用户名是否已存在
                    result = await db.execute(
                        select(User).where(User.username == admin_username)
                    )
                    existing_user = result.scalar_one_or_none()

                    if existing_user:
                        # 升级为超级管理员
                        existing_user.role = UserRole.SUPER_ADMIN
                        existing_user.is_active = True
                        await db.commit()
                        logger.info(f"用户 '{admin_username}' 已升级为超级管理员")
                    else:
                        # 创建新的超级管理员
                        super_admin = User(
                            username=admin_username,
                            email=admin_email,
                            hashed_password=get_password_hash(admin_password),
                            role=UserRole.SUPER_ADMIN,
                            is_active=True,
                            is_verified=True,
                            tenant_id=None  # 超级管理员不属于任何租户
                        )
                        db.add(super_admin)
                        await db.commit()
                        logger.info(f"超级管理员 '{admin_username}' 创建成功")
                else:
                    logger.info("超级管理员账号已存在，跳过自动创建")
    except Exception as e:
        logger.warning(f"自动创建超级管理员失败（不影响启动）: {e}")

    # 清理上次服务器退出时遗留的幽灵运行任务
    # 服务器重启后，内存中的任务状态丢失，数据库中残留 running 状态的任务已无法继续
    # 将其标记为 failed，避免前端页面刷新后误认为任务仍在运行
    # P0改造：改用WritingTask查询（不再依赖NovelProject的DEPRECATED字段）
    try:
        from app.repositories.writing_task import WritingTaskRepository
        from app.core.database import async_session_maker
        from app.services.task_manager_constants import TASK_STATUS_RUNNING, TASK_STATUS_FAILED
        async with async_session_maker() as db:
            repo = WritingTaskRepository(db)
            running_tasks = await repo.get_by_status(TASK_STATUS_RUNNING)
            for task in running_tasks:
                task.status = TASK_STATUS_FAILED
            if running_tasks:
                await db.commit()
                logger.info(f"已清理 {len(running_tasks)} 个遗留运行写作任务")
    except Exception as e:
        logger.warning(f"清理遗留运行任务失败（不影响启动）: {e}")

    # 注入 NovelProjectRepository 到 task_manager（支持依赖倒置）
    try:
        from app.core.database import async_session_maker
        from app.repositories.novel_project import NovelProjectRepository
        from app.services.task_manager import set_novel_project_repo

        # 创建独立 session（不作为 context manager，保持长连接）
        session = async_session_maker()
        repo = NovelProjectRepository(session)
        set_novel_project_repo(repo)
        logger.info("已注入 NovelProjectRepository 到 task_manager")
    except Exception as e:
        logger.warning(f"注入 Repository 失败（不影响启动）: {e}")

    # 初始化 LLM 能力报告
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

    # 清理幽灵状态：将所有RUNNING状态的任务标记为INTERRUPTED
    # 因为后端重启意味着之前的运行进程已终止
    try:
        from app.core.database import async_session_maker
        from app.models import WritingTask
        from app.models.writing_task import TaskStatus
        from sqlalchemy import update
        from datetime import datetime

        async with async_session_maker() as db:
            result = await db.execute(
                update(WritingTask)
                .where(WritingTask.status == TaskStatus.RUNNING)
                .values(
                    status=TaskStatus.INTERRUPTED,
                    end_time=datetime.now(),
                    error_message="后端服务重启，任务自动中断"
                )
            )
            await db.commit()
            cleaned_count = result.rowcount
            if cleaned_count > 0:
                logger.info(
                    f"【幽灵状态清理】已清理 {cleaned_count} 个残留的RUNNING状态任务"
                )
    except Exception as e:
        logger.warning(f"清理幽灵状态失败（不影响启动）: {e}")

    yield

    # 关闭时清理
    logger.info("应用关闭")

    # 清理活跃Pipeline的RUNNING状态
    try:
        from app.core.database import async_session_maker
        from app.models import WritingTask
        from app.models.writing_task import TaskStatus
        from app.services.writing_engine.pipeline import WritingPipeline
        from sqlalchemy import update
        from datetime import datetime

        active_pipelines = WritingPipeline.get_all_active_pipelines()
        if active_pipelines:
            # 将不在活跃列表中的RUNNING任务标记为INTERRUPTED
            async with async_session_maker() as db:
                result = await db.execute(
                    update(WritingTask)
                    .where(WritingTask.status == TaskStatus.RUNNING)
                    .values(
                        status=TaskStatus.INTERRUPTED,
                        end_time=datetime.now(),
                        error_message="后端服务关闭，任务自动中断"
                    )
                )
                await db.commit()
                cleaned_count = result.rowcount
                if cleaned_count > 0:
                    logger.info(
                        f"【关闭清理】已将 {cleaned_count} 个RUNNING任务标记为INTERRUPTED"
                    )
    except Exception as e:
        logger.warning(f"关闭时清理任务状态失败: {e}")


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

# 添加输入消毒中间件（防止XSS和SQL注入）
# Vibe Coding模拟检测 - 异常输入注入防护
from app.middleware.input_sanitization import InputSanitizationMiddleware
print("[INFO] 启用输入消毒中间件")
app.add_middleware(InputSanitizationMiddleware)


# CORS 中间件配置
# 【修复】allow_credentials=True 时 allow_origins 不能为 ["*"]，违反 W3C CORS 规范
# 当 CORS_ORIGINS="*" 时自动展开为开发环境常用源列表
cors_origins = settings.get_cors_origins()
if "*" in cors_origins:
    # 通配符模式：不能使用 allow_credentials，否则浏览器拒绝请求
    cors_credentials = False
else:
    cors_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_credentials,
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
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """统一应用异常处理"""
    from datetime import datetime, timezone
    logger = get_logger("system")

    if exc.status_code >= 500:
        logger.error(
            f"应用异常 - 追踪ID: {exc.trace_id}, "
            f"错误代码: {exc.error_code.value}, "
            f"消息: {exc.message}",
            exc_info=True
        )
    else:
        logger.warning(
            f"应用异常 - 追踪ID: {exc.trace_id}, "
            f"错误代码: {exc.error_code.value}, "
            f"消息: {exc.message}"
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.error_code.value,
            message=exc.message,
            trace_id=exc.trace_id,
            details=exc.details if settings.DEBUG else None,
            timestamp=datetime.now(timezone.utc).isoformat()
        ).model_dump()
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = get_logger("system")
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


# 退出程序端点（需超级管理员权限）
@app.post("/api/v1/system/exit", tags=["系统"])
async def exit_application(current_user=Depends(get_current_superuser)):
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
    def _exit_with_delay():
        time.sleep(0.5)  # 等待HTTP响应发送完成
        logger.info("程序退出")
        os._exit(0)  # 强制退出，确保所有线程终止

    exit_thread = threading.Thread(target=_exit_with_delay, daemon=True)
    exit_thread.start()

    return {"code": 0, "message": "程序正在退出...", "success": True}


# 注册路由
app.include_router(api_router, prefix="/api/v1")


# ==================== WebSocket端点 ====================
# [2026-03-28] 多Agent重构: 写作任务WebSocket端点


# TODO: WebSocket 端点缺少认证，需要验证连接方身份
# 建议在 WebSocket 握手阶段通过查询参数传递 Token 进行验证
@app.websocket("/api/v1/writing-tasks/{task_id}/ws")
async def writing_task_websocket(websocket: WebSocket, task_id: int):
    """
    写作任务WebSocket端点

    提供实时进度推送、状态变更通知等功能。
    客户端连接后可接收任务生成进度、状态变更等消息。
    
    认证：通过查询参数传递token（?token=xxx）

    消息格式:
    - progress: 进度更新 {"type": "progress", "data": {"current_unit": 1, "total_units": 10, ...}}
    - status_change: 状态变更 {"type": "status_change", "data": {"old_status": "pending", "new_status": "running"}}
    - error: 错误通知 {"type": "error", "data": {"error_code": "...", "error_message": "..."}}
    - complete: 完成通知 {"type": "complete", "data": {"total_units": 10, "total_word_count": 50000}}
    """
    from app.api.deps import verify_token
    from app.core.database import get_db
    from app.models import WritingTask
    from sqlalchemy import select
    
    logger = get_logger("websocket")
    
    # 从查询参数获取token
    token = websocket.query_params.get("token")
    if not token:
        logger.warning(f"WebSocket连接被拒绝: 缺少token, task_id={task_id}")
        await websocket.close(code=4001, reason="Missing authentication token")
        return
    
    # 验证token
    try:
        payload = await verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token中缺少用户ID")
        user_id = int(user_id)
    except Exception as e:
        logger.warning(f"WebSocket连接被拒绝: token无效, task_id={task_id}, error={e}")
        await websocket.close(code=4001, reason="Invalid authentication token")
        return
    
    # 验证用户是否有权限访问该任务
    try:
        async for db in get_db():
            result = await db.execute(
                select(WritingTask).where(WritingTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            
            if not task:
                logger.warning(f"WebSocket连接被拒绝: 任务不存在, task_id={task_id}")
                await websocket.close(code=4004, reason="Task not found")
                return
            
            # 检查任务归属（防止越权访问）
            if task.user_id != user_id:
                logger.warning(f"WebSocket连接被拒绝: 无权访问任务, task_id={task_id}, user_id={user_id}")
                await websocket.close(code=4003, reason="Unauthorized access to task")
                return
            
            break
    except Exception as e:
        logger.error(f"WebSocket连接验证异常: task_id={task_id}, error={e}")
        await websocket.close(code=4000, reason="Authentication error")
        return
    
    # 认证通过，建立连接
    ws_manager = get_websocket_manager()
    await ws_manager.connect(task_id, websocket)
    logger.info(f"WebSocket连接建立: task_id={task_id}, user_id={user_id}")

    try:
        while True:
            # 接收客户端消息（如心跳、控制命令等）
            data = await websocket.receive_text()
            logger.debug(f"收到WebSocket消息: task_id={task_id}, data={data}")

            # 处理客户端消息（如心跳响应、控制命令等）
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif msg_type == "get_status":
                    # 返回当前任务状态
                    await websocket.send_text(json.dumps({"type": "status", "task_id": task_id}))
            except json.JSONDecodeError:
                logger.warning(f"无效的WebSocket消息格式: {data}")

    except WebSocketDisconnect:
        await ws_manager.disconnect(task_id, websocket)
        logger.info(f"WebSocket连接断开: task_id={task_id}")
    except Exception as e:
        logger.error(f"WebSocket异常: task_id={task_id}, error={e}")
        await ws_manager.disconnect(task_id, websocket)


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
