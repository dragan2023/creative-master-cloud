"""
创意生成 API - 公共常量、工具函数与流式端点工厂

@date: 2026-04-24
@version: v3.1.0 (从generate.py拆分)
"""
from typing import Dict, Optional, List
import asyncio

from fastapi import Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logger import get_logger
from app.core.redis_client import redis_manager
from app.models import User

logger = get_logger(__name__)

# 取消令牌的 Redis 键前缀
CANCEL_KEY_PREFIX = "generate:cancel:"
# 取消令牌过期时间（秒）
CANCEL_EXPIRE_SECONDS = 3600  # 1小时
# 内存取消令牌存储（用于流式生成的取消控制）
# TODO: 考虑完全迁移到Redis后移除内存级取消令牌
cancel_tokens: Dict[str, asyncio.Event] = {}


def parse_kb_ids(ids_str: Optional[str]) -> Optional[List[int]]:
    """
    安全解析知识库ID列表字符串
    过滤掉 'null', 'undefined', 空字符串等无效值

    Args:
        ids_str: 逗号分隔的ID字符串，如 "1,2,3" 或 "null" 或 None

    Returns:
        整数ID列表或None
    """
    if not ids_str:
        return None
    # 过滤无效值
    invalid_values = {'null', 'undefined', 'none', ''}
    try:
        ids = [int(x.strip()) for x in ids_str.split(",")
               if x.strip().lower() not in invalid_values and x.strip()]
        return ids if ids else None
    except ValueError:
        logger.warning(f"无效的知识库ID字符串: {ids_str}")
        return None


async def is_cancelled(session_id: str) -> bool:
    """
    检查生成任务是否被取消
    使用 Redis 存储取消状态，支持多 worker 环境

    Args:
        session_id: 会话ID

    Returns:
        是否被取消
    """
    if not session_id:
        return False
    cancel_key = f"{CANCEL_KEY_PREFIX}{session_id}"
    try:
        result = await redis_manager.exists(cancel_key)
        if result:
            logger.info(f"检测到取消请求: session_id={session_id}")
        return result
    except Exception as e:
        logger.error(f"检查取消状态失败: {e}")
        return False


async def _create_streaming_endpoint(
    module: str,
    input_params: dict,
    user_id: int,
    db: AsyncSession,
    session_id: Optional[str] = None,
    enable_search: bool = False,
    enable_knowledge: bool = False,
    enable_mcp: bool = False,
    enable_trending: bool = False,
    provider: Optional[str] = None,
    temperature: float = 0.7,
    search_keywords: Optional[List[str]] = None,
    kb_vertical: bool = False,
    kb_user_specific: bool = False,
    kb_manual: bool = False,
    kb_vertical_ids: Optional[List[int]] = None,
    kb_user_specific_ids: Optional[List[int]] = None,
    kb_manual_ids: Optional[List[int]] = None,
    **kwargs
) -> StreamingResponse:
    """
    通用流式生成端点工厂 - 消除8个端点的重复代码

    已集成状态持久化: 自动保存生成状态到数据库

    Args:
        module: 模块名称 (short_video, script, novel, print_ad, tvc, original_ip)
        input_params: 输入参数字典
        user_id: 用户ID
        db: 数据库会话
        session_id: 会话ID
        enable_search: 是否启用搜索
        enable_knowledge: 是否启用知识库
        enable_mcp: 是否启用MCP
        enable_trending: 是否启用趋势
        provider: 模型提供者
        temperature: 温度参数
        search_keywords: 搜索关键词列表
        kb_vertical: 是否启用垂直知识库
        kb_user_specific: 是否启用用户专属知识库
        kb_manual: 是否启用手动知识库
        kb_vertical_ids: 垂直知识库ID列表
        kb_user_specific_ids: 用户专属知识库ID列表
        kb_manual_ids: 手动知识库ID列表
        **kwargs: 额外参数（videos, images等）

    Returns:
        StreamingResponse: 流式响应
    """
    from app.models.generation import Generation, GenerationModule, GenerationStatus
    from app.utils.generation_state_manager import GenerationStateManager
    from app.agents.orchestrator import get_agent_orchestrator

    # 映射模块名称到枚举
    module_map = {
        'short_video': GenerationModule.SHORT_VIDEO,
        'novel': GenerationModule.NOVEL,
        'movie_outline': GenerationModule.MOVIE_OUTLINE,
        'series_outline': GenerationModule.SERIES_OUTLINE,
        'print_ad': GenerationModule.PRINT_AD,
        'tvc': GenerationModule.TVC,
        'original_ip': GenerationModule.ORIGINAL_IP,
        'practical_writing': GenerationModule.PRACTICAL_WRITING
    }

    module_enum = module_map.get(module, GenerationModule.SHORT_VIDEO)

    # 创建Generation记录
    generation = Generation(
        user_id=user_id,
        module=module_enum,
        status=GenerationStatus.PROCESSING,
        input_params=input_params,
        title=input_params.get('title', input_params.get(
            'ip_description', '未命名生成'))[:100],
        current_stage='generating'
    )
    db.add(generation)
    await db.commit()
    await db.refresh(generation)

    state_manager = GenerationStateManager(db, generation.id)

    orchestrator = get_agent_orchestrator()

    # 创建内存取消事件（实现立即中断）
    cancel_event = asyncio.Event()
    if session_id:
        cancel_tokens[session_id] = cancel_event

    # 用于收集完整内容
    content_buffer = []
    has_error = False  # 标记是否有异常发生

    async def event_generator():
        nonlocal has_error  # [修复] 必须在闭包内声明 nonlocal，否则 except 块中的
        # has_error = True 会创建局部变量，导致 finally 块读取外层变量（始终为 False）

        # [修复] 创建独立的数据库会话，因为依赖注入的 db 会话在视图函数
        # 返回 StreamingResponse 后就会被关闭，而流式生成器还需要使用数据库。
        # 见：get_db() 的 finally 块在 yield 之后立即关闭会话。
        from app.core.database import async_session_maker
        stream_db = async_session_maker()
        try:
            # 使用独立会话重建 state_manager（原 state_manager 绑定了已关闭的 db）
            stream_state_manager = GenerationStateManager(stream_db, generation.id)

            # 保存"生成中"状态
            await stream_state_manager.save_stage(
                stage='generating',
                stage_data={'progress': 0},
                status=GenerationStatus.PROCESSING
            )

            async for chunk in orchestrator.generate_stream(
                db=stream_db,
                module=module,
                user_id=user_id,
                input_params=input_params,
                session_id=session_id,
                enable_search=enable_search,
                search_keywords=search_keywords,
                enable_knowledge=enable_knowledge,
                enable_mcp=enable_mcp or enable_trending,
                reference_urls=input_params.get("reference_urls"),
                provider=provider,
                temperature=temperature,
                cancel_event=cancel_event,  # 传入内存事件
                kb_vertical=kb_vertical,
                kb_user_specific=kb_user_specific,
                kb_manual=kb_manual,
                kb_vertical_ids=kb_vertical_ids,
                kb_user_specific_ids=kb_user_specific_ids,
                kb_manual_ids=kb_manual_ids,
                **kwargs
            ):
                # 优先检查内存事件（立即中断）
                if cancel_event.is_set():
                    logger.info(f"生成任务被立即取消: {session_id}")
                    # 保存"已取消"状态
                    try:
                        await stream_state_manager.save_stage(
                            stage='generating',
                            stage_data={
                                'partial_content': ''.join(content_buffer),
                                'cancelled': True
                            },
                            status=GenerationStatus.CANCELLED
                        )
                    except Exception as e:
                        logger.error(f"保存取消状态失败: {e}")
                    break
                # 同时检查 Redis（多 worker 兼容）
                if await is_cancelled(session_id):
                    logger.info(f"生成任务被取消(Redis): {session_id}")
                    # 保存"已取消"状态
                    try:
                        await stream_state_manager.save_stage(
                            stage='generating',
                            stage_data={
                                'partial_content': ''.join(content_buffer),
                                'cancelled': True
                            },
                            status=GenerationStatus.CANCELLED
                        )
                    except Exception as e:
                        logger.error(f"保存取消状态失败: {e}")
                    break

                yield chunk

                # 累积内容
                try:
                    if chunk.startswith('event: content\ndata: '):
                        import json
                        json_str = chunk.split('data: ', 2)[1].strip()
                        if json_str:
                            content_data = json.loads(json_str)
                            text = content_data.get('text', '')
                            content_buffer.append(text)

                            # 定期保存进度和内容(每500字符保存一次)
                            total_length = sum(len(t) for t in content_buffer)
                            if total_length > 0 and total_length % 500 < len(text):
                                try:
                                    await stream_state_manager.save_stage(
                                        stage='generating',
                                        stage_data={
                                            # 假设5000字符完成
                                            'progress': min(total_length / 5000, 1.0),
                                            'partial_content': ''.join(content_buffer)
                                        },
                                        status=GenerationStatus.PROCESSING
                                    )
                                except Exception as save_err:
                                    # 保存失败不影响生成
                                    pass
                except Exception as parse_err:
                    logger.debug(f"解析chunk失败: {parse_err}")

        except asyncio.CancelledError:
            logger.info(f"生成任务被取消: {session_id}")
            has_error = True  # 标记有异常
            raise
        except Exception as e:
            logger.error(f"生成任务失败: {e}")
            has_error = True  # 标记有异常
            # 保存"失败"状态
            try:
                await stream_state_manager.save_stage(
                    stage='generating',
                    stage_data={
                        'partial_content': ''.join(content_buffer),
                        'error': str(e)[:500]
                    },
                    status=GenerationStatus.FAILED
                )
            except Exception as save_error:
                logger.error(f"保存失败状态失败: {save_error}")
        finally:
            # 清理取消令牌
            if session_id and session_id in cancel_tokens:
                del cancel_tokens[session_id]
            # 清理 Redis 标记
            if session_id:
                cancel_key = f"{CANCEL_KEY_PREFIX}{session_id}"
                await redis_manager.delete(cancel_key)

            # 如果内容完整且没有异常，保存"完成"状态
            if content_buffer and not has_error:
                try:
                    await stream_state_manager.save_stage(
                        stage='completed',
                        stage_data={
                            'content': ''.join(content_buffer),
                            'progress': 1.0
                        },
                        status=GenerationStatus.COMPLETED
                    )
                except Exception as e:
                    logger.error(f"保存完成状态失败: {e}")

            # 关闭独立的数据库会话
            try:
                await stream_db.close()
            except Exception as close_err:
                logger.debug(f"关闭流式数据库会话异常(可忽略): {close_err}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )
