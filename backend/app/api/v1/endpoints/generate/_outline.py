"""
创意生成 API - 两阶段大纲生成

包含全局大纲生成/修订/流式生成、单元概述生成/流式生成/质控/下载/逻辑检测

@date: 2026-04-24
@version: v3.1.0 (从generate.py拆分)
"""
import re
import json
import asyncio
from typing import Dict, Any, Optional, List

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import (
    ValidationException,
    GenerationException,
)
from app.core.logger import get_logger
from app.models import User
from app.schemas.generation import UnitSummariesQCRequest
from app.schemas.common import ResponseModel
from app.services.outline_generator import get_outline_generator

from ._common import cancel_tokens

logger = get_logger(__name__)


# ==================== 请求模型 ====================

class GlobalOutlineRequest(BaseModel):
    """全局大纲生成请求"""
    content_type: str  # novel/script
    input_params: Dict[str, Any]
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    enable_knowledge: bool = False  # 是否启用知识库修正（默认False，由用户主动控制）
    enable_auto_qc: bool = False  # v2.3新增：是否启用自动质控修正（默认False，由用户主动控制）

    # 文风参数（可选）
    style_ids: Optional[List[str]] = []
    style_names: Optional[List[str]] = []
    style_intensity: Optional[float] = 0.7
    style_guide: Optional[Dict[str, Any]] = None

    # 标题风格参数（可选，新增）
    title_style: Optional[str] = None
    title_style_name: Optional[str] = None


class UnitSummariesRequest(BaseModel):
    """单元概述生成请求"""
    content_type: str  # novel/script
    global_outline: str
    unit_count: int
    series_type: Optional[str] = None  # 剧本类型专用
    episode_duration_range: Optional[str] = None  # 剧本类型专用
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    enable_quality_control: bool = True  # 是否启用质量管控

    # 新增: 质控模式 (manual=手动模式, auto=自动模式)
    qc_mode: str = "manual"  # 默认手动模式

    # 续生成参数（可选）
    existing_content: Optional[str] = None  # 已生成的内容
    existing_parsed: Optional[Dict[str, Any]] = None  # 已解析的单元数据
    start_from_unit: int = 1  # 从第几章开始续生成（默认1表示全新生成）

    # 标题风格参数（可选，新增）
    title_style: Optional[str] = None
    title_style_name: Optional[str] = None


class LogicCheckRequest(BaseModel):
    """逻辑检测请求"""
    content_type: str  # novel/script
    global_outline: str
    unit_summaries: Dict[str, Any]  # 单元概述字典
    provider: Optional[str] = None
    temperature: float = 0.7


class GlobalOutlineReviseRequest(BaseModel):
    """全局大纲流式修订请求"""
    content_type: str  # novel/script
    current_content: str  # 当前大纲内容
    user_feedback: str  # 用户修改意见
    revision_history: Optional[List[Dict[str, Any]]] = []  # 修订历史
    input_params: Optional[Dict[str, Any]] = {}
    provider: Optional[str] = None
    temperature: float = 0.7


def register_outline_routes(router: APIRouter):
    """注册两阶段大纲生成路由"""

    @router.post("/outline/global")
    async def generate_global_outline(
        data: GlobalOutlineRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        生成全局大纲（第一阶段）

        生成详细的全局大纲，包含世界观、人物谱系、故事结构等完整维度。
        这是两阶段生成流程的第一阶段。
        支持知识库修正，修正后的内容直接替换原始内容。
        """
        try:
            generator = get_outline_generator(db)
            result = await generator.generate_global_outline(
                content_type=data.content_type,
                input_params=data.input_params,
                provider=data.provider,
                model=data.model,
                temperature=data.temperature,
                user_id=current_user.id,
                enable_knowledge=data.enable_knowledge,
                # 文风参数
                style_ids=data.style_ids or [],
                style_names=data.style_names or [],
                style_intensity=data.style_intensity or 0.7,
                style_guide=data.style_guide
            )

            if result["success"]:
                logger.info(
                    f"用户 {current_user.id} 生成全局大纲成功 - "
                    f"类型: {data.content_type}, "
                    f"耗时: {result['duration_ms']}ms"
                )
                return ResponseModel(
                    success=True,
                    data=result
                )
            else:
                raise GenerationException(result.get("error", "生成失败"))

        except ValueError as e:
            logger.warning(f"全局大纲参数错误: {str(e)}")
            raise ValidationException(str(e))
        except Exception as e:
            logger.error(f"全局大纲生成失败: {str(e)}")
            raise GenerationException(f"生成失败: {str(e)}")

    @router.post("/outline/global/revise")
    async def revise_global_outline_with_knowledge(
        data: GlobalOutlineRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        对全局大纲执行知识库修正（用户确认后调用）

        此API在全局大纲生成完成后，由用户审核确认后再执行知识库修正。
        这样可以确保知识库修正是基于用户最终确认的大纲内容进行的。
        已集成状态持久化：自动保存修正后的大纲内容
        """
        from app.models.generation import Generation, GenerationModule, GenerationStatus
        from app.utils.generation_state_manager import GenerationStateManager

        try:
            # 1. 查找最近的generation记录
            module_enum = GenerationModule.NOVEL if data.content_type == 'novel' else GenerationModule.SCRIPT
            state = await GenerationStateManager.get_latest_generation(
                db, current_user.id, module_enum.value, days=7
            )

            state_manager = None
            if state:
                state_manager = GenerationStateManager(db, state['id'])

            generator = get_outline_generator(db)

            # 2. 获取LLM provider
            llm_provider = await generator.llm_manager.get_provider_from_db(
                db, current_user.id, data.provider
            )
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {data.provider}")

            # 3. 执行知识库修正
            revised_content = await generator._revise_with_knowledge_base(
                llm_provider=llm_provider,
                original_content=data.input_params.get('existing_outline', ''),
                input_params=data.input_params,
                temperature=data.temperature,
                db=db,
                user_id=current_user.id,
                content_type=data.content_type
            )

            # 4. 更新状态
            if state_manager and revised_content:
                try:
                    stage_data = state.get('stage_data', {})
                    stage_data['global_outline'] = revised_content

                    await state_manager.save_stage(
                        stage='knowledge_revising',
                        stage_data=stage_data,
                        status=GenerationStatus.PROCESSING
                    )
                except Exception as save_err:
                    logger.error(f"保存知识库修正状态失败: {save_err}")

            if revised_content:
                logger.info(f"用户 {current_user.id} 全局大纲知识库修正完成")
                return ResponseModel(
                    success=True,
                    data={
                        "revised_content": revised_content,
                        "message": "知识库优化完成"
                    }
                )
            else:
                return ResponseModel(
                    success=True,
                    data={
                        "revised_content": data.input_params.get('existing_outline', ''),
                        "message": "知识库验证通过，无需修正"
                    }
                )

        except Exception as e:
            logger.error(f"全局大纲知识库修正失败: {str(e)}")
            raise GenerationException(f"知识库修正失败: {str(e)}")

    @router.post("/outline/global/revise-stream")
    async def revise_global_outline_stream(
        data: GlobalOutlineReviseRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        流式修订全局大纲（多轮对话）

        用户可以对全局大纲进行多轮对话修正，LLM流式输出修订后的内容。
        """
        from app.utils.generation_state_manager import GenerationStateManager

        # 获取最近的generation记录
        state = await GenerationStateManager.get_latest_generation(
            db, current_user.id, data.content_type, days=7
        )

        if not state:
            # 如果没有找到，创建一个新的
            from app.models.generation import Generation, GenerationModule, GenerationStatus
            module_enum = GenerationModule.NOVEL if data.content_type == 'novel' else GenerationModule.SCRIPT
            generation = Generation(
                user_id=current_user.id,
                module=module_enum,
                status=GenerationStatus.PROCESSING,
                input_params=data.input_params,
                title='大纲修订',
                current_stage='revising_global'
            )
            db.add(generation)
            await db.commit()
            await db.refresh(generation)
            state_manager = GenerationStateManager(db, generation.id)
        else:
            state_manager = GenerationStateManager(db, state['id'])

        async def generate():
            try:
                generator = get_outline_generator(db)

                # 保存"修订中"状态
                await state_manager.save_stage(
                    stage='revising_global',
                    stage_data=state.get('stage_data', {}) if state else {},
                    session_context={
                        'revising': True,
                        'current_feedback': data.user_feedback
                    }
                )

                # 获取LLM provider
                llm_provider = await generator.llm_manager.get_provider_from_db(
                    db, current_user.id, data.provider
                )
                if not llm_provider:
                    raise ValueError(f"未找到LLM提供商: {data.provider}")

                # 构建修订提示词
                history_text = ""
                if data.revision_history:
                    history_text = "\n\n## 修订历史\n"
                    for rev in data.revision_history[-3:]:  # 只保留最近3轮
                        history_text += f"- 第{rev.get('round', '?')}轮: {rev.get('feedback', '')}\n"

                revise_prompt = f"""您是一位专业的大纲修订助手。

## 当前大纲内容
{data.current_content}

## 用户修改意见
{data.user_feedback}
{history_text}
## 任务
请根据用户的修改意见，对大纲进行修订。

**修订规则**：
1. 保持大纲的整体结构和核心设定
2. 只修改用户提到的部分
3. 确保修改后的内容逻辑自洽
4. 输出完整的修订后大纲内容

请直接输出修订后的大纲内容：
"""

                # 流式生成修订内容
                full_content = []
                async for chunk in llm_provider.generate_stream(prompt=revise_prompt, temperature=data.temperature):
                    content = chunk.content if hasattr(chunk, 'content') else chunk
                    if isinstance(content, str):
                        full_content.append(content)
                        yield generator._format_sse("content", {"text": content})

                revised_content = ''.join(full_content)

                # 追加修订消息
                await state_manager.append_revision_message({
                    'role': 'user',
                    'content': data.user_feedback
                })

                # 保存修订后状态
                stage_data = state.get('stage_data', {}) if state else {}
                stage_data['global_outline'] = revised_content

                await state_manager.save_stage(
                    stage='global_completed',
                    stage_data=stage_data,
                    session_context={'revising': False}
                )

                # 发送修订完成事件
                yield generator._format_sse("diff_complete", {
                    "summary": f"已根据'{data.user_feedback}'完成修订",
                    "content_length": len(revised_content)
                })

            except Exception as e:
                logger.error(f"全局大纲修订失败: {e!r}")
                yield generator._format_sse("error", {"data": str(e)[:200]})

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )

    @router.post("/outline/global/stream")
    async def generate_global_outline_stream(
        data: GlobalOutlineRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        流式生成全局大纲（第一阶段）

        支持知识库修正：生成完成后，自动调用知识库进行内容优化。
        修正后的内容会以分隔线标识，前端可识别并替换显示。
        """
        from app.models.generation import Generation, GenerationModule, GenerationStatus
        from app.utils.generation_state_manager import GenerationStateManager

        # 创建generation记录
        module_enum = GenerationModule.NOVEL if data.content_type == 'novel' else GenerationModule.SCRIPT
        generation = Generation(
            user_id=current_user.id,
            module=module_enum,
            status=GenerationStatus.PROCESSING,
            input_params=data.input_params,
            title=data.input_params.get('title', '未命名大纲'),
            current_stage='global_generating'
        )
        db.add(generation)
        await db.commit()
        await db.refresh(generation)

        state_manager = GenerationStateManager(db, generation.id)

        async def generate():
            generator = get_outline_generator(db)
            full_content = []

            try:
                # 保存"生成中"状态
                await state_manager.save_stage(
                    stage='global_generating',
                    stage_data={'progress': 0},
                    status=GenerationStatus.PROCESSING
                )

                async for chunk in generator.generate_global_outline_stream(
                    content_type=data.content_type,
                    input_params=data.input_params,
                    provider=data.provider,
                    model=data.model,
                    temperature=data.temperature,
                    user_id=current_user.id,
                    enable_knowledge=data.enable_knowledge,
                    enable_auto_qc=data.enable_auto_qc,  # v2.3新增：传递自动质控参数
                    # 文风参数
                    style_ids=data.style_ids or [],
                    style_names=data.style_names or [],
                    style_intensity=data.style_intensity or 0.7,
                    style_guide=data.style_guide
                ):
                    yield chunk

                    # 累积内容
                    if chunk.startswith('event: content\ndata: '):
                        try:
                            json_str = chunk.split('data: ', 2)[1].strip()
                            if json_str:
                                content_data = json.loads(json_str)
                                full_content.append(content_data.get('text', ''))
                        except Exception as parse_err:
                            logger.debug(f"解析SSE chunk内容失败: {parse_err}")

                # 生成完成，保存状态
                complete_content = ''.join(full_content)
                await state_manager.save_stage(
                    stage='global_completed',
                    stage_data={
                        'global_outline': complete_content,
                        'progress': 1.0
                    },
                    status=GenerationStatus.COMPLETED
                )

            except Exception as e:
                # 保存错误状态
                try:
                    await state_manager.save_stage(
                        stage='global_generating',
                        stage_data={'error': str(e)[:500]},
                        status=GenerationStatus.FAILED
                    )
                except Exception as save_err:
                    logger.error(f"保存全局大纲生成错误状态失败: {save_err}")
                raise

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )

    @router.post("/outline/units")
    async def generate_unit_summaries(
        data: UnitSummariesRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        生成单元简要概述（第二阶段）

        基于全局大纲生成各单元的简要概述（章节概要/分集概要/分场概要）。
        这是两阶段生成流程的第二阶段。
        支持质量管控系统，自动检测和修正结构、人物、技术性等问题。
        """
        try:
            generator = get_outline_generator(db)
            result = await generator.generate_unit_summaries(
                global_outline=data.global_outline,
                unit_count=data.unit_count,
                content_type=data.content_type,
                series_type=data.series_type,
                episode_duration_range=data.episode_duration_range,
                provider=data.provider,
                model=data.model,
                temperature=data.temperature,
                user_id=current_user.id,
                enable_quality_control=data.enable_quality_control,
                title_style=data.title_style,
                title_style_name=data.title_style_name
            )

            if result["success"]:
                logger.info(
                    f"用户 {current_user.id} 生成单元概述成功 - "
                    f"类型: {data.content_type}, "
                    f"单元数: {data.unit_count}, "
                    f"耗时: {result['duration_ms']}ms"
                )
                return ResponseModel(
                    success=True,
                    data=result
                )
            else:
                raise GenerationException(result.get("error", "生成失败"))

        except ValueError as e:
            logger.warning(f"单元概述参数错误: {str(e)}")
            raise ValidationException(str(e))
        except Exception as e:
            logger.error(f"单元概述生成失败: {str(e)}")
            raise GenerationException(f"生成失败: {str(e)}")

    @router.post("/outline/units/stream")
    async def generate_unit_summaries_stream(
        data: UnitSummariesRequest,
        session_id: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        流式生成单元简要概述（第二阶段）

        支持中断机制：通过 session_id 可以调用 /cancel/{session_id} 取消生成
        已集成状态持久化：自动保存生成状态到数据库
        """
        from app.models.generation import Generation, GenerationModule, GenerationStatus
        from app.utils.generation_state_manager import GenerationStateManager

        # 1. 查找最近的generation记录
        module_enum = GenerationModule.NOVEL if data.content_type == 'novel' else GenerationModule.SCRIPT
        state = await GenerationStateManager.get_latest_generation(
            db, current_user.id, module_enum.value, days=7
        )

        if not state:
            # 创建新记录
            generation = Generation(
                user_id=current_user.id,
                module=module_enum,
                status=GenerationStatus.PROCESSING,
                input_params={'content_type': data.content_type},
                title='单元概述生成',
                current_stage='units_generating'
            )
            db.add(generation)
            await db.commit()
            await db.refresh(generation)
            state_manager = GenerationStateManager(db, generation.id)
        else:
            state_manager = GenerationStateManager(db, state['id'])

        # 2. 保存"单元概述生成中"状态
        await state_manager.save_stage(
            stage='units_generating',
            stage_data={
                'global_outline': data.global_outline,  # 保留全局大纲
                'progress': 0
            },
            status=GenerationStatus.PROCESSING
        )

        # 3. 创建取消令牌
        cancel_event = asyncio.Event()
        if session_id:
            cancel_tokens[session_id] = cancel_event

        content_buffer = []

        async def generate():
            try:
                generator = get_outline_generator(db)

                logger.info(
                    f"[单元概述] 开始生成: 从第{data.start_from_unit}章开始, 共{data.unit_count}章"
                )

                async for chunk in generator.generate_unit_summaries_stream(
                    global_outline=data.global_outline,
                    unit_count=data.unit_count,
                    content_type=data.content_type,
                    series_type=data.series_type,
                    episode_duration_range=data.episode_duration_range,
                    provider=data.provider,
                    model=data.model,
                    temperature=data.temperature,
                    user_id=current_user.id,
                    enable_quality_control=data.enable_quality_control,
                    qc_mode=data.qc_mode,  # 新增: 传递质控模式
                    cancel_event=cancel_event,
                    # 续生成参数
                    existing_content=data.existing_content or "",
                    existing_parsed=data.existing_parsed,
                    start_from_unit=data.start_from_unit,
                    # 标题风格参数
                    title_style=data.title_style,
                    title_style_name=data.title_style_name
                ):
                    # 检查是否被取消
                    if cancel_event.is_set():
                        logger.info(f"单元概述生成被取消: {session_id}")
                        # 保存取消状态
                        try:
                            await state_manager.save_stage(
                                stage='units_generating',
                                stage_data={
                                    'global_outline': data.global_outline,
                                    'partial_unit_summaries': ''.join(content_buffer),
                                    'cancelled': True
                                },
                                status=GenerationStatus.CANCELLED
                            )
                        except Exception as save_err:
                            logger.error(f"保存取消状态失败: {save_err}")
                        break

                    yield chunk

                    # 累积内容
                    try:
                        if chunk.startswith('event: content\ndata: '):
                            json_str = chunk.split('data: ', 2)[1].strip()
                            if json_str:
                                content_data = json.loads(json_str)
                                content_buffer.append(content_data.get('text', ''))
                    except Exception as parse_err:
                        logger.debug(f"解析chunk失败: {parse_err}")

                # 生成完成,保存状态
                if content_buffer:
                    try:
                        await state_manager.save_stage(
                            stage='units_completed',
                            stage_data={
                                'global_outline': data.global_outline,
                                'unit_summaries': ''.join(content_buffer),
                                'progress': 1.0
                            },
                            status=GenerationStatus.COMPLETED
                        )
                    except Exception as save_err:
                        logger.error(f"保存完成状态失败: {save_err}")

            except Exception as e:
                logger.error(f"单元概述生成失败: {e}")
                # 保存失败状态
                try:
                    await state_manager.save_stage(
                        stage='units_generating',
                        stage_data={
                            'global_outline': data.global_outline,
                            'partial_unit_summaries': ''.join(content_buffer),
                            'error': str(e)[:500]
                        },
                        status=GenerationStatus.FAILED
                    )
                except Exception as save_err:
                    logger.error(f"保存失败状态失败: {save_err}")
            finally:
                # 清理取消令牌
                if session_id and session_id in cancel_tokens:
                    del cancel_tokens[session_id]

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )

    @router.post("/outline/units/continue")
    async def continue_unit_summaries_stream(
        data: UnitSummariesRequest,
        session_id: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        接续生成单元简要概述（断点续生成）

        【修复 #2】前端调用 /api/v1/generate/outline/units/continue，此前端点缺失导致404。
        此端点复用 units/stream 的完整逻辑（含中断/状态持久化/质控），
        语义上等同于调用 units/stream 并传入 start_from_unit、existing_content 等续生成参数。
        """
        # 直接委托给 generate_unit_summaries_stream（闭包内函数，共享 cancel_tokens 上下文）
        return await generate_unit_summaries_stream(
            data=data,
            session_id=session_id,
            current_user=current_user,
            db=db
        )
        
    @router.get("/outline/units/resume-info/{project_id}")
    async def get_unit_summaries_resume_info(
        project_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        获取单元概述断点续生成信息

        根据项目ID自动识别当前生成状态和断点位置，返回续生成所需的全部信息：
        - existing_parsed: 已解析的单元数据
        - existing_content: 已生成的原始文本内容
        - existing_count: 已生成章节数
        - expected_count: 预期总章节数（来自全局大纲/项目设置）
        - start_from_unit: 建议续生成的起始章节号
        - global_outline: 全局大纲内容
        """
        from app.models.novel_project import NovelProject
        from app.core.exceptions import NotFoundException
        from sqlalchemy import select

        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise NotFoundException(f"项目不存在: {project_id}")

        # 获取已有的单元概述数据
        existing_parsed = project.unit_summaries or {}
        existing_count = len(existing_parsed)

        # 获取预期总章节数
        expected_count = project.total_chapters or 0

        # 如果 unit_summaries 中有更多数据，以实际数量为准
        if existing_count > expected_count:
            expected_count = existing_count

        # 如果预期数仍为0，尝试从全局大纲推断
        if expected_count == 0 and project.global_outline_content:
            # 从全局大纲中尝试提取章节数
            chapter_matches = re.findall(
                r'第[一二三四五六七八九十百千万\d]+章',
                project.global_outline_content
            )
            if chapter_matches:
                expected_count = len(set(chapter_matches))

        # 获取全局大纲内容
        global_outline = project.global_outline_content or ""

        # 计算续生成起始位置
        start_from_unit = existing_count + 1 if existing_count > 0 else 1

        # 重建 existing_content 文本
        existing_content_parts = []
        content_type = getattr(project, 'content_type', 'novel')
        unit_label = '章' if content_type == 'novel' else '集' if content_type in (
            'series_script', 'script') else '场'

        for unit_num, unit_data in sorted(existing_parsed.items(), key=lambda x: int(x[0])):
            title = unit_data.get("title", "")
            summary = unit_data.get("summary", "")
            full_content = unit_data.get("full_content", "") or summary
            existing_content_parts.append(
                f"### 第{unit_num}{unit_label}：{title}\n{full_content}"
            )
        existing_content = "\n\n".join(existing_content_parts)

        # 判断是否可以续生成
        can_resume = existing_count > 0 and existing_count < expected_count

        return ResponseModel(
            success=True,
            message="断点信息获取成功",
            data={
                "project_id": project_id,
                "project_title": project.title or "未命名项目",
                "content_type": content_type,
                "existing_count": existing_count,
                "expected_count": expected_count,
                "start_from_unit": start_from_unit,
                "can_resume": can_resume,
                "remaining_count": max(0, expected_count - existing_count),
                "global_outline": global_outline,
                "existing_parsed": existing_parsed,
                "existing_content": existing_content
            }
        )

    @router.post("/outline/units/quality-control")
    async def quality_control_unit_summaries(
        data: UnitSummariesQCRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        对单元概述执行质量检测和修正（手动触发）

        流程（参照全局大纲质控）：
        1. 如果传入了issue_id：直接针对该问题进行修正（不重新检测）
        2. 否则：调用LLM检测质量问题
        3. 如果发现critical问题且enable_auto_revise=True，自动调用LLM修正
        4. 返回质控报告 + 修正后内容 + 变更列表（用于前端高亮对比）
        """
        try:
            # 参数验证
            if not data.unit_summaries:
                from app.core.exceptions import ValidationException
                raise ValidationException("单元概述数据不能为空")

            if not isinstance(data.unit_summaries, dict):
                from app.core.exceptions import ValidationException
                raise ValidationException("单元概述数据格式错误，应为字典类型")

            if len(data.unit_summaries) == 0:
                from app.core.exceptions import ValidationException
                raise ValidationException("单元概述数据为空，至少需要一个单元")

            from app.services.outline_generator import get_outline_generator

            generator = get_outline_generator(db)

            # 检查是否传入了issue_id（直接修正模式）
            issue_id = getattr(data, 'issue_id', None)
            quality_report = None

            if issue_id:
                # v2.4新增：直接修正模式，不重新检测
                logger.info(f"[单元概述质控] 直接修正模式，问题ID: {issue_id}")
                if not hasattr(data, 'quality_report') or not data.quality_report:
                    from app.core.exceptions import ValidationException
                    raise ValidationException("直接修正模式需要提供quality_report参数")

                quality_report = data.quality_report
                # 筛选出要修正的问题
                all_issues = [issue for issue in quality_report.get(
                    "issues", []) if issue.get("id") == issue_id]

                if not all_issues:
                    from app.core.exceptions import ValidationException
                    raise ValidationException(f"未找到问题ID: {issue_id}")

                # v2.4新增: 在quality_report中添加issue_id标记,供提示词构建时识别
                quality_report["issue_id"] = issue_id

                logger.info(
                    f"[单元概述质控] 找到问题: {all_issues[0].get('description', '')[:100]}...")
            else:
                # 原有逻辑：完整质控检测
                logger.info(f"[单元概述质控] 开始LLM质量检测，单元数: {len(data.unit_summaries)}")

                quality_report = await generator.analyze_unit_summaries_quality_manual(
                    unit_summaries=data.unit_summaries,
                    global_outline=data.global_outline,
                    content_type=data.content_type,
                    user_id=current_user.id
                )

                logger.info(f"[单元概述质控] 检测完成，总分: {quality_report.get('overall_score', 0)}, "
                            f"问题数: {len(quality_report.get('issues', []))}")

                # 步骤2: 检查是否有问题需要修正（所有级别：critical + major + minor）
                all_issues = quality_report.get("issues", [])

            revised_content = None
            revised_parsed = None
            changes = []

            if all_issues and data.enable_auto_revise:
                logger.info(f"[单元概述质控] 发现{len(all_issues)}个问题，执行LLM自动修正...")

                # 构建完整的单元概述文本（修正前）
                unit_label = "章" if data.content_type == "novel" else "集"
                original_content_parts = []
                for unit_num, unit_data in sorted(data.unit_summaries.items(), key=lambda x: int(x[0])):
                    title = unit_data.get("title", "")
                    full_content = unit_data.get(
                        "full_content", "") or unit_data.get("summary", "")
                    original_content_parts.append(
                        f"### 第{unit_num}{unit_label}：{title}\n{full_content}")
                original_content = "\n\n".join(original_content_parts)

                # v2.4新增：直接修正模式下，只传递要修正的问题
                targeted_quality_report = quality_report.copy()
                if issue_id:
                    targeted_quality_report["issues"] = all_issues
                    logger.info(f"[单元概述质控] 直接修正模式，只修正问题: {issue_id}")

                # 调用LLM修正（参照全局大纲的修正流程）
                revision_result = await generator.revise_unit_summaries_quality(
                    unit_summaries=data.unit_summaries,
                    quality_report=targeted_quality_report,
                    global_outline=data.global_outline,
                    content_type=data.content_type,
                    temperature=data.temperature,
                    user_id=current_user.id
                )

                revised_content = revision_result.get("revised_content")
                revised_parsed = revision_result.get("revised_parsed")
                changes = revision_result.get("changes", [])

                logger.info(f"[单元概述质控] LLM修正完成，修正前长度: {len(original_content)}, "
                            f"修正后长度: {len(revised_content) if revised_content else 0}")

            # 步骤3: 返回完整结果（用于前端对比显示）
            return ResponseModel(
                success=True,
                message="质控检测完成",
                data={
                    "quality_report": quality_report,
                    "revised_content": revised_content,
                    "revised_parsed": revised_parsed,
                    "changes": changes,
                    "has_issues": len(all_issues) > 0,
                    "issues_count": len(all_issues),
                    "auto_revised": len(changes) > 0
                }
            )

        except Exception as e:
            logger.error(f"[单元概述质控] 失败: {str(e)}", exc_info=True)
            from app.core.exceptions import GenerationException
            raise GenerationException(f"质控失败: {str(e)}")

    @router.post("/outline/download")
    async def download_outline(
        content: str = "",
        filename: str = "outline.md",
        current_user: User = Depends(get_current_user)
    ):
        """下载大纲文件"""
        from fastapi.responses import Response

        if not content:
            raise ValidationException("大纲内容不能为空")

        # 确保文件名以 .md 结尾
        if not filename.endswith('.md'):
            filename += '.md'

        return Response(
            content=content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
            }
        )

    @router.post("/outline/logic-check")
    async def check_outline_logic(
        data: LogicCheckRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        独立的逻辑检测API

        检测单元概述中的逻辑问题，包括：
        - 设定冲突：人物设定、世界观设定与单元概述内容的矛盾
        - 剧情衔接跳脱：单元概述之间的情节连贯性问题
        - 人物成长过快：人物性格变化、能力提升的合理性
        - 时间线矛盾：事件发生顺序的逻辑性
        - 核心线索断裂：重要情节线索的连续性
        """
        try:
            generator = get_outline_generator(db)
            result = await generator.check_and_fix_logic_issues(
                global_outline=data.global_outline,
                unit_summaries=data.unit_summaries,
                content_type=data.content_type,
                provider=data.provider,
                temperature=data.temperature,
                user_id=current_user.id
            )

            logger.info(
                f"用户 {current_user.id} 逻辑检测完成 - "
                f"类型: {data.content_type}, "
                f"检测到问题: {result.get('has_issues', False)}"
            )

            return ResponseModel(
                success=True,
                data=result
            )

        except ValueError as e:
            logger.warning(f"逻辑检测参数错误: {str(e)}")
            raise ValidationException(str(e))
        except Exception as e:
            logger.error(f"逻辑检测失败: {str(e)}")
            raise GenerationException(f"检测失败: {str(e)}")
