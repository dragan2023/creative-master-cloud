"""知识库上传与后台处理

包含 upload_knowledge_base 和 analyze_knowledge_with_llm 的实现
"""

import os
import uuid
import shutil
import threading
import asyncio

from fastapi import UploadFile, BackgroundTasks, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import SYNC_DATABASE_URL, get_db
from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.exceptions import ValidationException
from app.models import (
    KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus,
    KnowledgeBaseCategory, User
)
from app.tools import get_file_parser, get_knowledge_retrieval_tool
from app.schemas.knowledge import KnowledgeBaseUploadResponse

from ._state import (
    update_kb_progress, register_kb_task, unregister_kb_task,
    kb_thread_pool, KB_MAX_CONCURRENT, kb_processing_progress,
    _async_delete_kb_progress, logger as state_logger
)

settings = get_settings()


async def upload_knowledge_base_handler(
    background_tasks: BackgroundTasks,
    name: str,
    file: UploadFile,
    description: str,
    category: str,
    current_user: User,
    db
):
    """上传知识库处理"""
    logger = get_logger(str(current_user.id))

    # 检查当前处理中的任务数
    active_tasks = len([t for t in kb_processing_progress.values()
                       if t.get("is_processing", False)])
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

    # 检查文件大小
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

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

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

    # 创建知识库记录
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
        expires_at=None
    )

    db.add(kb)
    await db.commit()
    await db.refresh(kb)

    # 后台处理知识库
    stop_event = threading.Event()

    def run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(analyze_knowledge_with_llm(
                kb.id, file_path, current_user.id, db, stop_event
            ))
        except RuntimeError as e:
            if "Event loop is closed" not in str(e):
                raise
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(
                        *pending, return_exceptions=True))
            except Exception as e:
                logger.debug(f"清理待处理任务时出错: {e}")
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception as e:
                logger.debug(f"关闭事件循环时出错: {e}")
            loop.close()
            unregister_kb_task(kb.id)
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_async_delete_kb_progress(kb.id))
                loop.close()
            except Exception as e:
                logger.debug(f"清理进度数据时出错: {e}")
            kb_processing_progress.pop(kb.id, None)

    future = kb_thread_pool.submit(run_async_task)
    register_kb_task(kb.id, future, stop_event)

    logger.info(f"知识库上传成功: {name}, 开始后台处理")

    return KnowledgeBaseUploadResponse(
        id=kb.id,
        name=kb.name,
        status=kb.status,
        message="知识库创建成功，正在处理中...",
        document_count=0
    )


async def analyze_knowledge_with_llm(kb_id: int, file_path: str, user_id: int, db_session, stop_event=None):
    """后台处理知识库（预处理流水线 + 向量化 + LLM知识图谱生成）"""
    import threading
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import SYNC_DATABASE_URL

    logger = get_logger(str(user_id))

    def check_stopped():
        if stop_event and stop_event.is_set():
            return True
        return False

    engine = create_engine(SYNC_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        kb = session.query(KnowledgeBase).filter(
            KnowledgeBase.id == kb_id).first()
        if not kb:
            logger.error(f"知识库不存在: {kb_id}")
            return

        def progress_callback(step_name: str, progress: int, step_index: int):
            if check_stopped():
                raise InterruptedError("处理被用户终止")
            update_kb_progress(kb_id, step_name, progress, step_index)
            logger.info(f"知识库 {kb_id} 进度: {step_name} ({progress}%)")

        # 获取 LLM 提供者
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

        # 获取 GraphRAG 配置
        graphrag_enabled = True
        user_preprocessor_config = {}
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
                user_preprocessor_config = {
                    "semantic_chunk_enabled": config_data.get("semantic_chunk_enabled", True),
                    "semantic_chunk_size": config_data.get("semantic_chunk_size", 1024),
                    "semantic_threshold": config_data.get("semantic_threshold", 0.7),
                    "marker_enabled": config_data.get("marker_enabled", True),
                    "summarization_enabled": config_data.get("summarization_enabled", False),
                }
        except Exception as e:
            logger.warning(f"获取 GraphRAG 配置失败: {str(e)}")

        # 步骤1-3：预处理流水线
        parser = get_file_parser()
        parse_result = await parser.parse_and_split(
            file_path,
            chunk_size=1000,
            overlap=100,
            progress_callback=progress_callback,
            llm_provider=llm_provider,
            config=user_preprocessor_config
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

        # 步骤5：LLM知识图谱生成
        if kb.category != KnowledgeBaseCategory.MANUAL and graphrag_enabled:
            update_kb_progress(kb_id, "正在生成知识图谱...", 70, 5)
            try:
                if llm_provider:
                    from app.tools.graph_rag import LLMEntityExtractor, graph_rag

                    logger.info(f"开始LLM知识图谱生成，chunk数量: {len(chunks)}")
                    full_content = "\n\n".join(chunks)
                    llm_extractor = LLMEntityExtractor(llm_provider)
                    extraction_result = await llm_extractor.extract_with_llm(full_content)

                    entities = extraction_result.get("entities", [])
                    relations = extraction_result.get("relations", [])

                    logger.info(f"LLM提取结果: {len(entities)}个实体, {len(relations)}个关系")

                    if entities:
                        graph_rag.add_llm_entities_to_graph(
                            entities=entities,
                            relations=relations,
                            kb_id=kb_id,
                            doc_id=str(kb_id)
                        )
                    logger.info(f"知识图谱生成完成: {len(entities)}个实体, {len(relations)}个关系")
                else:
                    logger.warning("未配置 LLM 提供者，跳过知识图谱生成")
            except Exception as e:
                logger.error(f"LLM知识图谱生成失败: {str(e)}", exc_info=True)
        else:
            if kb.category == KnowledgeBaseCategory.MANUAL:
                logger.info(f"知识库类型为官方手册(MANUAL)，跳过GraphRAG知识图谱生成")

        # 步骤6：完成
        update_kb_progress(kb_id, "处理完成", 100, 6)
        session.expire_all()
        kb = session.query(KnowledgeBase).filter(
            KnowledgeBase.id == kb_id).first()
        if kb:
            kb.status = KnowledgeBaseStatus.READY
            kb.document_count = len(chunks)
            session.commit()

        logger.info(f"知识库处理完成: {kb.name if kb else kb_id}, 文档数: {len(chunks)}")

    except InterruptedError as e:
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
