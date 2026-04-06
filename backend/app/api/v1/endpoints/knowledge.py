"""
知识库 API 端点

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from app.tools.graph_rag import DualTrackGraphRAG
import os
import uuid
import json
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.redis_client import redis_manager
from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    AuthorizationException,
    KnowledgeBaseException,
)
from app.api.deps import get_current_user
from app.models import User, KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory
from app.models.base import get_local_now
from app.tools import get_file_parser, get_knowledge_retrieval_tool
from app.schemas.common import ResponseModel
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUploadResponse,
    KnowledgeBaseUpdate,
    DualTrackRetrieveRequest,
    DualTrackRetrieveResponse,
    KnowledgeGraphData
)
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor


router = APIRouter(prefix="/knowledge", tags=["知识库"])
settings = get_settings()

# 模块级别默认logger
logger = get_logger(__name__)

# 知识库处理进度状态存储
kb_processing_progress: Dict[int, Dict[str, Any]] = {}

# Redis 进度存储配置
KB_PROGRESS_PREFIX = "kb_progress:"
KB_PROGRESS_EXPIRE = 3600  # 1小时过期


def _sync_update_kb_progress(kb_id: int, progress_data: Dict[str, Any]):
    """
    同步更新知识库进度到 Redis（用于后台线程）

    由于 RedisManager 方法是异步的，在后台线程中需要通过事件循环调用
    """
    key = f"{KB_PROGRESS_PREFIX}{kb_id}"
    data = json.dumps(progress_data, ensure_ascii=False)
    try:
        # 尝试在现有事件循环中运行
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用线程安全方式
                future = asyncio.run_coroutine_threadsafe(
                    redis_manager.set(key, data, expire=KB_PROGRESS_EXPIRE),
                    loop
                )
                future.result(timeout=5)  # 等待最多5秒
            else:
                # 事件循环存在但未运行
                loop.run_until_complete(redis_manager.set(
                    key, data, expire=KB_PROGRESS_EXPIRE))
        except RuntimeError:
            # 没有事件循环，创建一个新的
            asyncio.run(redis_manager.set(
                key, data, expire=KB_PROGRESS_EXPIRE))
    except Exception as e:
        logger.debug(f"Redis 进度更新失败，降级到内存: {e}")


async def _async_get_kb_progress(kb_id: int) -> Dict[str, Any]:
    """异步获取知识库进度（用于 API 端点）"""
    key = f"{KB_PROGRESS_PREFIX}{kb_id}"
    try:
        data = await redis_manager.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.debug(f"Redis 进度获取失败，降级到内存: {e}")
    # 降级到内存存储
    return kb_processing_progress.get(kb_id, {
        "kb_id": kb_id,
        "current_step": "",
        "progress": 0,
        "total_steps": 6,
        "current_step_index": 0,
        "error": None,
        "is_processing": False,
        "updated_at": None
    })


async def _async_delete_kb_progress(kb_id: int):
    """异步删除知识库进度"""
    key = f"{KB_PROGRESS_PREFIX}{kb_id}"
    try:
        await redis_manager.delete(key)
    except Exception as e:
        logger.debug(f"Redis 进度删除失败: {e}")
    # 同时从内存中删除
    kb_processing_progress.pop(kb_id, None)


async def _async_get_all_kb_progress() -> List[Dict[str, Any]]:
    """异步获取所有正在处理的知识库进度"""
    # 使用内存字典作为索引（记录哪些KB正在处理）
    result = []
    for kb_id in list(kb_processing_progress.keys()):
        progress = await _async_get_kb_progress(kb_id)
        if progress.get("is_processing", False):
            result.append(progress)
    return result

# 存储正在运行的处理任务（用于终止）
kb_processing_tasks: Dict[int, Dict[str, Any]] = {}

# 知识库处理线程池，限制最大并发数
KB_MAX_CONCURRENT = 5
kb_thread_pool = ThreadPoolExecutor(
    max_workers=KB_MAX_CONCURRENT, thread_name_prefix="kb_process")


def update_kb_progress(kb_id: int, step: str, progress: int, step_index: int, error: str = None, total_steps: int = 6):
    """更新知识库处理进度（同时写入内存和 Redis）"""
    progress_data = {
        "kb_id": kb_id,
        "current_step": step,
        "progress": progress,
        "total_steps": total_steps,
        "current_step_index": step_index,
        "error": error,
        "is_processing": error is None and progress < 100,
        "updated_at": get_local_now().isoformat()
    }
    # 写入内存（作为索引和后备）
    kb_processing_progress[kb_id] = progress_data
    # 同步写入 Redis
    _sync_update_kb_progress(kb_id, progress_data)


def get_kb_progress(kb_id: int) -> Dict[str, Any]:
    """获取知识库处理进度"""
    return kb_processing_progress.get(kb_id, {
        "kb_id": kb_id,
        "current_step": "",
        "progress": 0,
        "total_steps": 6,
        "current_step_index": 0,
        "error": None,
        "is_processing": False,
        "updated_at": None
    })


def get_all_processing_progress() -> List[Dict[str, Any]]:
    """获取所有正在处理的知识库进度"""
    processing_list = []
    for kb_id, progress in kb_processing_progress.items():
        if progress.get("is_processing", False):
            processing_list.append(progress)
    return processing_list


def register_kb_task(kb_id: int, future=None, stop_event=None):
    """注册知识库处理任务"""
    kb_processing_tasks[kb_id] = {
        "future": future,
        "stop_event": stop_event,
        "started_at": get_local_now().isoformat()
    }


def unregister_kb_task(kb_id: int):
    """注销知识库处理任务"""
    if kb_id in kb_processing_tasks:
        del kb_processing_tasks[kb_id]


def stop_kb_processing(kb_id: int) -> bool:
    """终止知识库处理进程"""
    if kb_id in kb_processing_tasks:
        task_info = kb_processing_tasks[kb_id]
        stop_event = task_info.get("stop_event")
        if stop_event:
            stop_event.set()
            logger.info(f"已设置停止信号: kb_id={kb_id}")
        # 更新进度状态为已终止
        update_kb_progress(kb_id, "处理已终止", 0, 0, error="用户手动终止")
        # 注意：不在此处注销任务，让线程完成时自行注销
        return True

    # 即使任务不在列表中，也检查进度状态
    progress = get_kb_progress(kb_id)
    if progress.get("is_processing", False):
        # 更新进度状态为已终止
        update_kb_progress(kb_id, "处理已终止", 0, 0, error="用户手动终止")
        return True

    return False


@router.post("/upload", response_model=ResponseModel[KnowledgeBaseUploadResponse])
async def upload_knowledge_base(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    file: UploadFile = File(...),
    description: str = Form(None),
    category: str = Form("general"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传用户知识库（支持LLM知识图谱生成）

    Args:
        name: 知识库名称
        file: 上传的文件
        description: 描述
        category: 业务板块分类 (short-video/script/novel/print-ad/tvc/general)
        current_user: 当前用户
        db: 数据库会话

    Returns:
        知识库信息
    """
    logger = get_logger(str(current_user.id))

    # 检查当前处理中的任务数
    active_tasks = len([t for t in kb_processing_tasks.values()
                       if t.get("future") and not t["future"].done()])
    if active_tasks >= KB_MAX_CONCURRENT:
        raise ValidationException(
            message=f"当前有{active_tasks}个知识库正在处理中，请稍后再试（最大并发{KB_MAX_CONCURRENT}）",
            status_code=429
        )

    # 检查文件类型
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise ValidationException(
            message=f"不支持的文件类型: {file_ext}"
        )

    # 检查文件大小（使用 file.size 属性，避免读取整个文件到内存）
    # 注意：file.size 可能在某些情况下不可用，此时使用 content-length
    file_size = file.size if hasattr(file, 'size') and file.size else 0
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise ValidationException(
            message=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB)"
        )

    # 保存文件
    upload_dir = os.path.join(settings.get_chroma_dir(), "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = os.path.join(upload_dir, f"{file_id}{file_ext}")

    # 使用流式写入，避免大文件占用内存
    import shutil
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 获取实际文件大小
    file_size = os.path.getsize(file_path)
    if file_size > settings.MAX_UPLOAD_SIZE:
        os.remove(file_path)
        raise ValidationException(
            message=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB)"
        )

    # 解析category
    try:
        kb_category = KnowledgeBaseCategory(category)
    except ValueError:
        kb_category = KnowledgeBaseCategory.GENERAL

    # 创建知识库记录（用户知识库不设置过期时间）
    kb = KnowledgeBase(
        user_id=current_user.id,
        name=name,
        description=description,
        type=KnowledgeBaseType.TEMP,
        category=kb_category,
        status=KnowledgeBaseStatus.PROCESSING,
        file_path=file_path,
        file_type=file_ext[1:],
        file_size=file_size,
        collection_name=f"kb_{file_id}",
        expires_at=None  # 用户知识库不设置过期时间
    )

    db.add(kb)
    await db.commit()
    await db.refresh(kb)

    # 后台处理知识库（包括LLM知识图谱生成）
    # 使用 run_in_executor 来运行异步任务
    import asyncio
    import threading

    # 创建停止事件
    stop_event = threading.Event()

    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(process_knowledge_with_llm(
                kb.id,
                file_path,
                current_user.id,
                db,
                stop_event
            ))
        except RuntimeError as e:
            # 忽略事件循环关闭后的清理错误
            if "Event loop is closed" not in str(e):
                raise
        finally:
            # 清理待处理的任务
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(
                        *pending, return_exceptions=True))
            except Exception as e:
                logger.debug(f"清理待处理任务时出错: {e}")
            # 关闭事件循环
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception as e:
                logger.debug(f"关闭事件循环时出错: {e}")
            loop.close()
            # 处理完成后注销任务并清理进度
            unregister_kb_task(kb.id)
            # 清理 Redis 中的进度数据
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_async_delete_kb_progress(kb.id))
                loop.close()
            except Exception as e:
                logger.debug(f"清理进度数据时出错: {e}")
            # 清理内存中的进度数据
            kb_processing_progress.pop(kb.id, None)

    # 使用线程池提交任务
    future = kb_thread_pool.submit(run_async_task)

    # 注册任务（在任务提交后注册，确保停止功能可用）
    register_kb_task(kb.id, future, stop_event)

    logger.info(f"知识库上传成功: {name}, 开始后台处理")

    return ResponseModel(data=KnowledgeBaseUploadResponse(
        id=kb.id,
        name=kb.name,
        status=kb.status,
        message="知识库创建成功，正在处理中...",
        document_count=0
    ))


async def process_knowledge_with_llm(kb_id: int, file_path: str, user_id: int, db_session, stop_event=None):
    """
    后台处理知识库（包括预处理流水线 + 向量化 + LLM知识图谱生成）

    流程：
    1. Cleaner - 文档格式转换 (Marker)
    2. Filter - 内容过滤
    3. Refiner - 语义切片
    4. 存入向量数据库
    5. LLM知识图谱生成
    6. 完成
    """
    import threading
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import SYNC_DATABASE_URL

    logger = get_logger(str(user_id))

    # 检查是否被终止
    def check_stopped():
        if stop_event and stop_event.is_set():
            return True
        return False

    # 创建同步数据库会话
    engine = create_engine(SYNC_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 获取知识库记录
        kb = session.query(KnowledgeBase).filter(
            KnowledgeBase.id == kb_id).first()
        if not kb:
            logger.error(f"知识库不存在: {kb_id}")
            return

        # 定义进度回调函数（用于预处理流水线）
        def progress_callback(step_name: str, progress: int, step_index: int):
            # 检查是否被终止
            if check_stopped():
                raise InterruptedError("处理被用户终止")
            update_kb_progress(kb_id, step_name, progress, step_index)
            logger.info(f"知识库 {kb_id} 进度: {step_name} ({progress}%)")

        # 提前获取 LLM 提供者（用于摘要压缩和知识图谱）
        llm_provider = None
        try:
            from app.models import UserAPIKey
            from app.core.security import api_key_encryption
            from app.agents.llm_manager import llm_manager

            api_key_record = session.query(UserAPIKey).filter(
                UserAPIKey.user_id == user_id,
                UserAPIKey.is_default == True
            ).first()

            if api_key_record:
                decrypted_key = api_key_encryption.decrypt(
                    api_key_record.encrypted_key)
                llm_provider = llm_manager.create_provider(
                    provider_name=api_key_record.provider,
                    api_key=decrypted_key,
                    model_name=api_key_record.model_name,
                    api_base=api_key_record.api_base
                )
        except Exception as e:
            logger.warning(f"获取 LLM 提供者失败: {str(e)}")

        # 获取用户的 GraphRAG 配置
        graphrag_enabled = True  # 默认启用
        try:
            from app.models import SystemConfig
            import json
            config_key = f"user_preprocessor_config_{user_id}"
            config_record = session.query(SystemConfig).filter(
                SystemConfig.id == config_key
            ).first()
            if config_record and config_record.config_value:
                config_data = json.loads(config_record.config_value)
                graphrag_enabled = config_data.get("graphrag_enabled", True)
            logger.info(f"用户 {user_id} GraphRAG 配置: {graphrag_enabled}")
        except Exception as e:
            logger.warning(f"获取 GraphRAG 配置失败: {str(e)}")

        # 步骤1-3：预处理流水线（Cleaner -> Filter -> Refiner）
        parser = get_file_parser()
        parse_result = await parser.parse_and_split(
            file_path,
            chunk_size=1000,
            overlap=100,
            progress_callback=progress_callback,
            llm_provider=llm_provider
        )

        if "error" in parse_result:
            kb.status = KnowledgeBaseStatus.FAILED
            session.commit()
            update_kb_progress(
                kb_id, f"预处理失败: {parse_result['error']}", 0, 1, error=parse_result['error'])
            logger.error(f"文档预处理失败: {parse_result['error']}")
            return

        # 步骤4：存入向量数据库
        update_kb_progress(kb_id, "正在存入向量数据库...", 50, 4)
        retrieval_tool = get_knowledge_retrieval_tool()
        chunks = parse_result["chunks"]

        metadatas = [
            {
                "source": file_path,
                "chunk_index": i,
                "knowledge_base_id": kb_id,
                "category": kb.category.value if kb.category else "general",
                "preprocessor_used": parse_result.get("metadata", {}).get("preprocessor_enabled", False)
            }
            for i in range(len(chunks))
        ]

        await retrieval_tool.add_documents_batch(
            collection_name=kb.collection_name,
            documents=chunks,
            metadatas=metadatas
        )

        kb.document_count = len(chunks)

        # 保存预处理元数据
        kb.preprocessor_metadata = {
            "preprocessor_enabled": parse_result.get("metadata", {}).get("preprocessor_enabled", False),
            "marker_used": parse_result.get("metadata", {}).get("marker_used", False),
            "semantic_chunk_used": parse_result.get("metadata", {}).get("semantic_chunk_used", False),
            "summarization_used": parse_result.get("metadata", {}).get("summarization_used", False),
            "original_size": parse_result.get("stats", {}).get("original_size", 0),
            "filtered_size": parse_result.get("stats", {}).get("filtered_size", 0),
            "chunk_count": len(chunks)
        }

        # 步骤5：使用LLM生成知识图谱（官方手册类型或用户关闭GraphRAG时跳过）
        if kb.category != KnowledgeBaseCategory.MANUAL and graphrag_enabled:
            update_kb_progress(kb_id, "正在生成知识图谱...", 70, 5)
            try:
                if llm_provider:
                    from app.tools.graph_rag import LLMEntityExtractor, graph_rag

                    logger.info(f"开始LLM知识图谱生成，chunk数量: {len(chunks)}")

                    # 合并所有chunk作为完整内容
                    full_content = "\n\n".join(chunks)
                    logger.info(f"合并后文本长度: {len(full_content)} 字符")

                    # 使用LLM提取实体和关系
                    llm_extractor = LLMEntityExtractor(llm_provider)
                    extraction_result = await llm_extractor.extract_with_llm(full_content)

                    # 将提取的实体和关系添加到知识图谱（自动保存）
                    entities = extraction_result.get("entities", [])
                    relations = extraction_result.get("relations", [])

                    logger.info(
                        f"LLM提取结果: {len(entities)}个实体, {len(relations)}个关系")

                    if entities:
                        logger.info(f"实体示例: {entities[:3]}")
                    if relations:
                        logger.info(f"关系示例: {relations[:3]}")

                    graph_rag.add_llm_entities_to_graph(
                        entities=entities,
                        relations=relations,
                        kb_id=kb_id,
                        doc_id=str(kb_id)
                    )

                    logger.info(
                        f"知识图谱生成完成: {len(entities)}个实体, {len(relations)}个关系")
                else:
                    logger.warning("未配置 LLM 提供者，跳过知识图谱生成")

            except Exception as e:
                # 知识图谱生成失败不影响主流程
                logger.error(f"LLM知识图谱生成失败: {str(e)}", exc_info=True)
        else:
            # 记录跳过原因
            if kb.category == KnowledgeBaseCategory.MANUAL:
                logger.info(f"知识库类型为官方手册(MANUAL)，跳过GraphRAG知识图谱生成")
            elif not graphrag_enabled:
                logger.info(f"用户已关闭GraphRAG功能，使用传统RAG模式")

        # 步骤6：更新状态完成
        update_kb_progress(kb_id, "处理完成", 100, 6)

        # 重新查询确保状态同步（解决并发竞争条件）
        session.expire_all()
        kb = session.query(KnowledgeBase).filter(
            KnowledgeBase.id == kb_id).first()
        if kb:
            kb.status = KnowledgeBaseStatus.READY
            kb.document_count = len(chunks)
            session.commit()

        logger.info(f"知识库处理完成: {kb.name if kb else kb_id}, 文档数: {len(chunks)}")

    except InterruptedError as e:
        # 用户手动终止
        logger.warning(f"知识库处理被终止: {kb_id}, 原因: {str(e)}")
        try:
            kb = session.query(KnowledgeBase).filter(
                KnowledgeBase.id == kb_id).first()
            if kb:
                kb.status = KnowledgeBaseStatus.FAILED
                session.commit()
        except Exception as commit_err:
            logger.warning(f"更新知识库状态失败（终止）: {commit_err}")
        update_kb_progress(kb_id, "处理已终止", 0, 0, error="用户手动终止")
    except Exception as e:
        logger.error(f"知识库处理失败: {str(e)}", exc_info=True)
        update_kb_progress(kb_id, f"处理失败: {str(e)}", 0, 0, error=str(e))
        try:
            kb = session.query(KnowledgeBase).filter(
                KnowledgeBase.id == kb_id).first()
            if kb:
                kb.status = KnowledgeBaseStatus.FAILED
                session.commit()
        except Exception as commit_err:
            logger.warning(f"更新知识库状态失败（异常）: {commit_err}")
    finally:
        session.close()


@router.get("", response_model=ResponseModel[list])
async def list_knowledge_bases(
    category: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的知识库列表（支持按业务模块筛选）"""
    query = select(KnowledgeBase).where(
        KnowledgeBase.user_id == current_user.id)

    # 按业务模块筛选
    if category and category != "all":
        try:
            cat_enum = KnowledgeBaseCategory(category)
            query = query.where(KnowledgeBase.category == cat_enum)
        except ValueError:
            pass

    query = query.order_by(KnowledgeBase.created_at.desc())
    result = await db.execute(query)
    kbs = result.scalars().all()

    data = [
        KnowledgeBaseResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            type=kb.type,
            category=kb.category,
            status=kb.status,
            file_type=kb.file_type,
            file_size=kb.file_size,
            document_count=kb.document_count,
            preprocessor_metadata=kb.preprocessor_metadata,
            created_at=kb.created_at.isoformat()
        )
        for kb in kbs
    ]

    return ResponseModel(data=data)


@router.get("/{kb_id}", response_model=ResponseModel[KnowledgeBaseResponse])
async def get_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取知识库详情"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    return ResponseModel(data=KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        type=kb.type,
        category=kb.category,
        status=kb.status,
        file_type=kb.file_type,
        file_size=kb.file_size,
        document_count=kb.document_count,
        preprocessor_metadata=kb.preprocessor_metadata,
        created_at=kb.created_at.isoformat()
    ))


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除知识库（保留记录，清除向量和文件）"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    # 删除向量集合
    from app.core.vector_store import vector_store
    try:
        vector_store.delete_collection(kb.collection_name)
    except Exception as e:
        logger.warning(f"删除向量集合失败 {kb.collection_name}: {e}")

    # 删除文件
    if kb.file_path and os.path.exists(kb.file_path):
        os.remove(kb.file_path)

    # 完全删除记录
    await db.delete(kb)
    await db.commit()

    return ResponseModel(message="删除成功")


@router.put("/{kb_id}", response_model=ResponseModel[KnowledgeBaseResponse])
async def update_knowledge_base(
    kb_id: int,
    update_data: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新知识库信息（名称、描述、业务模块分类）"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    # 更新字段
    if update_data.name is not None:
        kb.name = update_data.name
    if update_data.description is not None:
        kb.description = update_data.description
    if update_data.category is not None:
        kb.category = update_data.category

    await db.commit()
    await db.refresh(kb)

    return ResponseModel(data=KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        type=kb.type,
        category=kb.category,
        status=kb.status,
        file_type=kb.file_type,
        file_size=kb.file_size,
        document_count=kb.document_count,
        created_at=kb.created_at.isoformat()
    ))


@router.post("/{kb_id}/search")
async def search_knowledge_base(
    kb_id: int,
    query: str,
    n_results: int = 5,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """搜索知识库"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    if kb.status != KnowledgeBaseStatus.READY:
        raise ValidationException("知识库未就绪")

    retrieval_tool = get_knowledge_retrieval_tool()
    results = await retrieval_tool.retrieve(
        collection_name=kb.collection_name,
        query=query,
        n_results=n_results
    )

    return ResponseModel(data=results)


@router.get("/graph/global")
async def get_global_knowledge_graph(
    max_nodes: int = 100,
    current_user: User = Depends(get_current_user)
):
    """获取全局知识图谱数据（用于可视化）"""
    from app.tools.graph_rag import graph_rag
    graph_data = graph_rag.get_graph_data(max_nodes=max_nodes)

    return ResponseModel(data=graph_data)


@router.get("/{kb_id}/progress")
async def get_processing_progress(
    kb_id: int,
    current_user: User = Depends(get_current_user)
):
    """获取知识库处理进度"""
    progress = await _async_get_kb_progress(kb_id)
    return ResponseModel(data=progress)


@router.get("/processing/all")
async def get_all_processing_progress_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取所有正在处理的知识库进度（管理员可查看所有，普通用户只能查看自己的）"""
    from app.models import UserRole

    all_progress = await _async_get_all_kb_progress()

    # 如果不是管理员，只返回自己的知识库进度
    if current_user.role != UserRole.ADMIN:
        # 获取当前用户的知识库ID列表
        result = await db.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.user_id == current_user.id)
        )
        user_kb_ids = {row[0] for row in result.all()}
        all_progress = [p for p in all_progress if p.get(
            "kb_id") in user_kb_ids]

    return ResponseModel(data=all_progress)


@router.post("/{kb_id}/stop")
async def stop_knowledge_processing(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """终止知识库处理进程"""
    from app.models import UserRole

    # 检查权限
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    # 只有管理员或知识库所有者可以终止
    if current_user.role != UserRole.ADMIN and kb.user_id != current_user.id:
        raise AuthorizationException("无权终止此知识库的处理")

    # 检查是否正在处理
    if kb.status != KnowledgeBaseStatus.PROCESSING:
        raise ValidationException("知识库未在处理中")

    # 终止处理
    success = stop_kb_processing(kb_id)

    if success:
        # 更新数据库状态
        kb.status = KnowledgeBaseStatus.FAILED
        await db.commit()
        return ResponseModel(message="处理已终止")
    else:
        return ResponseModel(code=400, message="无法终止处理，任务可能已完成或不存在")


# ==================== GraphRAG 双轨知识库检索 ====================


# 全局双轨 GraphRAG 实例
dual_track_graph_rag = DualTrackGraphRAG()


@router.get("/general/all", response_model=ResponseModel[List[KnowledgeBaseResponse]])
async def get_all_general_knowledge_bases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取所有通用类型的知识库（管理员维护的通用创意理论库）

    用于创意生成时自动调用所有通用知识库
    """
    try:
        result = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.category == KnowledgeBaseCategory.GENERAL)
            .where(KnowledgeBase.status == KnowledgeBaseStatus.READY)
            .order_by(KnowledgeBase.created_at.desc())
        )
        knowledge_bases = result.scalars().all()

        return ResponseModel(data=[
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "type": kb.type,
                "category": kb.category,
                "status": kb.status,
                "file_type": kb.file_type,
                "file_size": kb.file_size,
                "document_count": kb.document_count,
                "preprocessor_metadata": kb.preprocessor_metadata,
                "created_at": kb.created_at.isoformat() if kb.created_at else None
            }
            for kb in knowledge_bases
        ])
    except Exception as e:
        logger.error(f"获取通用知识库失败: {e}")
        raise KnowledgeBaseException(f"获取失败: {str(e)}")


@router.post("/retrieve/dual-track", response_model=ResponseModel[DualTrackRetrieveResponse])
async def dual_track_retrieve(
    request: DualTrackRetrieveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    三层知识库检索策略

    检索顺序：
    1. 通用知识库（创意理论）- 固定调用
    2. 垂直领域知识库（应用案例）- 根据业务板块调用
    3. 官方手册（如有需要）- 按需查询，不使用GraphRAG

    如果未指定 general_kb_id，则自动检索所有通用知识库
    """
    try:
        # ========== 第一层：通用知识库检索 ==========
        general_kb_ids = []
        if request.general_kb_id:
            general_kb_ids = [request.general_kb_id]
        else:
            # 自动获取所有通用知识库
            result = await db.execute(
                select(KnowledgeBase)
                .where(KnowledgeBase.category == KnowledgeBaseCategory.GENERAL)
                .where(KnowledgeBase.status == KnowledgeBaseStatus.READY)
            )
            general_kbs = result.scalars().all()
            general_kb_ids = [kb.id for kb in general_kbs]
            logger.info(f"[第一层] 自动检索 {len(general_kb_ids)} 个通用知识库")

        # 合并所有通用知识库的结果
        all_general_results = []
        for general_kb_id in general_kb_ids[:3]:  # 最多3个通用知识库
            try:
                result = await dual_track_graph_rag.retrieve_dual_track(
                    query=request.query,
                    general_kb_id=general_kb_id,
                    vertical_kb_id=None,  # 不检索垂直库
                    vertical_category=None,
                    n_results=request.n_results
                )
                if result.get("general_results"):
                    all_general_results.append(result["general_results"])
            except Exception as e:
                logger.warning(f"检索通用知识库 {general_kb_id} 失败: {e}")
                continue

        # ========== 第二层：垂直领域知识库检索 ==========
        vertical_results = None
        if request.vertical_kb_id and request.vertical_category:
            try:
                logger.info(f"[第二层] 检索垂直领域知识库: {request.vertical_category}")
                result = await dual_track_graph_rag.retrieve_dual_track(
                    query=request.query,
                    general_kb_id=None,
                    vertical_kb_id=request.vertical_kb_id,
                    vertical_category=request.vertical_category.value,
                    n_results=request.n_results
                )
                vertical_results = result.get("vertical_results")
            except Exception as e:
                logger.warning(f"检索垂直知识库失败: {e}")

        # ========== 第三层：官方手册检索（如有需要）==========
        manual_results = None
        # 判断是否需要查询官方手册（这里可以根据业务逻辑调整判断条件）
        # 示例：如果通用库和垂直库结果不足，或者查询包含特定关键词
        should_query_manual = False
        if all_general_results or vertical_results:
            # 如果前两层有结果，检查是否需要补充官方手册
            total_results = len(all_general_results) + \
                (1 if vertical_results else 0)
            if total_results < 2:  # 结果较少时补充官方手册
                should_query_manual = True

        # 或者，如果查询包含特定关键词（API、配置、使用说明等）
        manual_keywords = ["api", "配置", "使用", "教程", "文档", "说明", "指南", "手册"]
        if any(keyword in request.query.lower() for keyword in manual_keywords):
            should_query_manual = True

        if should_query_manual:
            try:
                logger.info(f"[第三层] 查询官方手册知识库")
                # 查询所有官方手册类型的知识库
                manual_result = await db.execute(
                    select(KnowledgeBase)
                    .where(KnowledgeBase.category == KnowledgeBaseCategory.MANUAL)
                    .where(KnowledgeBase.status == KnowledgeBaseStatus.READY)
                )
                manual_kbs = manual_result.scalars().all()

                if manual_kbs:
                    # 使用普通向量检索（不用GraphRAG）
                    retrieval_tool = get_knowledge_retrieval_tool()
                    manual_chunks = []
                    for manual_kb in manual_kbs[:2]:  # 最多查询2个官方手册
                        try:
                            kb_results = await retrieval_tool.retrieve(
                                collection_name=manual_kb.collection_name,
                                query=request.query,
                                n_results=request.n_results
                            )
                            if kb_results:
                                manual_chunks.extend(kb_results)
                        except Exception as e:
                            logger.warning(f"查询官方手册 {manual_kb.id} 失败: {e}")

                    if manual_chunks:
                        manual_results = {
                            "chunks": manual_chunks[:request.n_results],
                            "kb_count": len(manual_kbs),
                            "source": "manual"
                        }
                        logger.info(f"官方手册检索到 {len(manual_chunks)} 条结果")
            except Exception as e:
                logger.warning(f"官方手册检索失败: {e}")

        # 分析理论连接
        connections = []
        if all_general_results and vertical_results:
            # 简化版连接分析
            connections = dual_track_graph_rag._analyze_connections({
                "general_results": all_general_results[0] if all_general_results else None,
                "vertical_results": vertical_results
            })

        # 构建增强上下文（包含官方手册）
        context_data = {
            "general_results": all_general_results[0] if all_general_results else None,
            "vertical_results": vertical_results,
            "connections": connections
        }
        enhanced_context = dual_track_graph_rag._format_dual_track_context(
            context_data)

        # 如果有官方手册结果，追加到上下文
        if manual_results:
            manual_context = "\n\n## 官方手册参考：\n"
            for i, chunk in enumerate(manual_results["chunks"][:3], 1):
                manual_context += f"\n{i}. {chunk}\n"
            enhanced_context += manual_context

        return ResponseModel(
            data={
                "query": request.query,
                "general_results": all_general_results[0] if all_general_results else None,
                "vertical_results": vertical_results,
                "manual_results": manual_results,  # 新增官方手册结果
                "connections": connections,
                "enhanced_context": enhanced_context
            }
        )
    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        raise KnowledgeBaseException(f"检索失败: {str(e)}")


@router.get("/{kb_id}/graph", response_model=ResponseModel[KnowledgeGraphData])
async def get_knowledge_graph(
    kb_id: int,
    max_nodes: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取知识库的知识图谱数据（用于可视化）"""
    # 查询知识库
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    # 检查权限
    if kb.user_id and kb.user_id != current_user.id and not current_user.is_admin:
        raise AuthorizationException("无权访问此知识库")

    try:
        # 获取图谱数据
        from app.tools.graph_rag import GraphRAG
        graph_rag = GraphRAG(
            kb_category=kb.category.value if kb.category else "general")
        graph_data = graph_rag.get_graph_data(kb_id=kb_id, max_nodes=max_nodes)

        return ResponseModel(data=graph_data)
    except Exception as e:
        logger.error(f"获取知识图谱失败: {e}")
        raise KnowledgeBaseException(f"获取图谱失败: {str(e)}")


@router.post("/{kb_id}/extract-entities", response_model=ResponseModel[Dict[str, Any]])
async def extract_entities_from_kb(
    kb_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    使用 LLM 从知识库文档中提取实体和关系

    根据知识库类别使用对应的提示词工程：
    - general: 通用创意理论提取
    - vertical: 垂直领域案例提取 + 理论连接
    """
    # 查询知识库
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise ResourceNotFoundException("知识库不存在")

    # 检查权限
    if kb.user_id and kb.user_id != current_user.id and not current_user.is_admin:
        raise AuthorizationException("无权访问此知识库")

    # 检查状态
    if kb.status != KnowledgeBaseStatus.READY:
        raise ValidationException("知识库尚未就绪")

    # 异步执行实体提取
    background_tasks.add_task(
        _extract_entities_task,
        kb_id=kb_id,
        category=kb.category.value if kb.category else "general"
    )

    return ResponseModel(message="实体提取任务已启动，请稍后查看结果")


async def _extract_entities_task(kb_id: int, category: str):
    """后台执行实体提取任务"""
    try:
        from app.agents.llm_manager import llm_manager
        from app.tools.graph_rag import GraphRAG, LLMEntityExtractor
        from app.core.vector_store import get_vector_store

        # 初始化
        llm_provider = llm_manager.get_default_provider()
        llm_extractor = LLMEntityExtractor(
            llm_provider=llm_provider,
            kb_category=category
        )
        vector_store = get_vector_store()

        # 获取知识库文档
        collection_name = f"kb_{kb_id}"
        # 这里需要获取所有文档内容，实际实现可能需要调整

        logger.info(f"开始提取知识库 {kb_id} 的实体和关系")

        # TODO: 实现完整的文档获取和实体提取逻辑

    except Exception as e:
        logger.error(f"实体提取任务失败: {e}")
