"""
创意生成 API - 两阶段大纲生成

包含全局大纲生成/修订/流式生成、单元概述生成/流式生成/质控/下载/逻辑检测

@date: 2026-04-24
@version: v3.1.0 (从generate.py拆分)
"""
import re
import json
import os
import asyncio
from typing import Dict, Any, Optional, List

from pydantic import BaseModel
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import (
    ValidationException,
    GenerationException,
    ResourceNotFoundException,
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
    content_type: str  # novel/movie_outline/series_outline
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
    content_type: str  # novel/movie_outline/series_outline
    global_outline: str
    unit_count: int
    series_type: Optional[str] = None  # 剧本类型专用
    episode_duration_range: Optional[str] = None  # 剧本类型专用
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.5  # 调整为0.5,平衡创造性与遵循性（v2.6）
    enable_quality_control: bool = True  # 是否启用质量管控

    # 质控模式（v3.0：仅自动模式）
    qc_mode: str = "auto"

    # 续生成参数（可选）
    existing_content: Optional[str] = None  # 已生成的内容
    existing_parsed: Optional[Dict[str, Any]] = None  # 已解析的单元数据
    start_from_unit: int = 1  # 从第几章开始续生成（默认1表示全新生成）

    # 标题风格参数（可选，新增）
    title_style: Optional[str] = None
    title_style_name: Optional[str] = None

    # GraphRAG知识库增强（可选，v4.1新增）
    project_id: Optional[int] = None  # 项目ID，用于知识图谱检索增强


class BuildKnowledgeGraphRequest(BaseModel):
    """构建知识图谱请求（v4.2：二阶段流程内建）"""
    global_outline: str  # 全局大纲内容
    content_type: str  # novel / movie_outline / series_outline
    title: str  # 项目标题
    genre: str = "玄幻"  # 题材标签


class LogicCheckRequest(BaseModel):
    """逻辑检测请求"""
    content_type: str  # novel/movie_outline/series_outline
    global_outline: str
    unit_summaries: Dict[str, Any]  # 单元概述字典
    provider: Optional[str] = None
    temperature: float = 0.7


class GlobalOutlineReviseRequest(BaseModel):
    """全局大纲流式修订请求"""
    content_type: str  # novel/movie_outline/series_outline
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
            if data.content_type == 'novel':
                module_enum = GenerationModule.NOVEL
            elif data.content_type == 'movie_outline':
                module_enum = GenerationModule.MOVIE_OUTLINE
            elif data.content_type == 'series_outline':
                module_enum = GenerationModule.SERIES_OUTLINE
            else:
                raise ValueError(f"不支持的内容类型: {data.content_type}")
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
            if data.content_type == 'novel':
                module_enum = GenerationModule.NOVEL
            elif data.content_type == 'movie_outline':
                module_enum = GenerationModule.MOVIE_OUTLINE
            elif data.content_type == 'series_outline':
                module_enum = GenerationModule.SERIES_OUTLINE
            else:
                raise ValueError(f"不支持的内容类型: {data.content_type}")
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
        if data.content_type == 'novel':
            module_enum = GenerationModule.NOVEL
        elif data.content_type == 'movie_outline':
            module_enum = GenerationModule.MOVIE_OUTLINE
        elif data.content_type == 'series_outline':
            module_enum = GenerationModule.SERIES_OUTLINE
        else:
            raise ValueError(f"不支持的内容类型: {data.content_type}")
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
                "Connection": "keep-alive",
                "X-Generation-ID": str(generation.id),  # [2026-05-05] 返回generation_id供前端获取
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
                title_style_name=data.title_style_name,
                project_id=data.project_id,
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

    @router.post("/outline/build-knowledge-graph")
    async def build_knowledge_graph(
        data: BuildKnowledgeGraphRequest,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        构建知识图谱（v4.2：二阶段流程内建）

        在全局大纲确认后、单元概述生成前调用。
        创建Stub项目并后台构建全局大纲知识图谱，返回项目ID。
        构建进度可通过 GET /projects/{project_id}/knowledge-base-status 查询。
        """
        from app.models.novel_project import NovelProject
        from app.models.novel_project import ProjectType, ProjectStatus
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
        from ..novel_writer.utils import generate_project_code, get_project_data_dir
        from datetime import datetime

        try:
            # 1. 创建Stub项目
            content_type_map = {
                "novel": "novel",
                "movie_outline": "movie_script",
                "series_outline": "series_script",
            }
            ct_value = content_type_map.get(data.content_type, "novel")

            project_code = generate_project_code()
            project_dir = get_project_data_dir(project_code)

            project = NovelProject(
                user_id=current_user.id,
                title=data.title,
                project_type=ProjectType.NOVEL if ct_value == "novel" else ProjectType.SCRIPT,
                content_type=ct_value,
                genre=data.genre,
                outline_content=data.global_outline,  # 填充大纲内容
                global_outline_content=data.global_outline,  # 两阶段大纲
                generation_config={"temperature": 0.8},
                knowledge_base_config={},
                project_code=project_code,
                architecture_file=os.path.join(project_dir, f"{project_code}_architecture.txt"),
                directory_file=os.path.join(project_dir, f"{project_code}_directory.json"),
                summary_file=os.path.join(project_dir, f"{project_code}_summary.txt"),
                characters_file=os.path.join(project_dir, f"{project_code}_characters.json"),
                vectorstore_path=os.path.join(project_dir, f"{project_code}_vectorstore"),
                chapters_dir=os.path.join(project_dir, "chapters"),
                status=ProjectStatus.INIT,
                kb_status="building",
                kb_build_progress={
                    "stage": "initializing",
                    "progress": 0,
                    "message": "正在初始化知识库...",
                    "started_at": datetime.now().isoformat()
                },
            )

            db.add(project)
            await db.commit()
            await db.refresh(project)

            logger.info(
                f"[知识图谱构建] Stub项目创建成功: project_id={project.id}, "
                f"title={data.title}")

            # 2. 启动后台构建任务
            background_tasks.add_task(
                _build_kb_from_outline_task,
                project_id=project.id,
                outline_content=data.global_outline,
            )

            return ResponseModel(
                success=True,
                message="知识图谱构建任务已启动",
                data={
                    "project_id": project.id,
                    "kb_status": "building"
                }
            )

        except Exception as e:
            logger.error(f"启动知识图谱构建失败: {str(e)}")
            raise GenerationException(f"构建失败: {str(e)}")

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
        if data.content_type == 'novel':
            module_enum = GenerationModule.NOVEL
        elif data.content_type == 'movie_outline':
            module_enum = GenerationModule.MOVIE_OUTLINE
        elif data.content_type == 'series_outline':
            module_enum = GenerationModule.SERIES_OUTLINE
        else:
            raise ValueError(f"不支持的内容类型: {data.content_type}")
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
                    title_style_name=data.title_style_name,
                    # GraphRAG知识库增强（v4.1新增）
                    project_id=data.project_id,
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
                "Connection": "keep-alive",
                "X-Generation-ID": str(state_manager.generation_id),  # [2026-05-05] 返回generation_id供前端获取
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
        
    @router.get("/outline/units/resume-info/{generation_id_or_project_id}")
    async def get_unit_summaries_resume_info(
        generation_id_or_project_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        获取单元概述断点续生成信息

        支持两种方式：
        1. generation_id：从 Generation 记录读取（单元概述生成阶段）
        2. project_id：从 NovelProject 记录读取（写作工作台阶段）
        
        返回续生成所需的全部信息：
        - existing_parsed: 已解析的单元数据
        - existing_content: 已生成的原始文本内容
        - existing_count: 已生成章节数
        - expected_count: 预期总章节数（来自全局大纲/项目设置）
        - start_from_unit: 建议续生成的起始章节号
        - global_outline: 全局大纲内容
        """
        from app.models.novel_project import NovelProject
        from app.models.generation import Generation
        from app.core.exceptions import ResourceNotFoundException
        from sqlalchemy import select

        # 先尝试从 Generation 记录读取
        gen_query = select(Generation).where(
            Generation.id == generation_id_or_project_id,
            Generation.user_id == current_user.id
        )
        gen_result = await db.execute(gen_query)
        generation = gen_result.scalar_one_or_none()

        global_outline = ""
        existing_parsed = {}
        content_type = "novel"
        expected_count = 0

        if generation:
            # 方式1：从 Generation 记录读取
            stage_data = generation.stage_data or {}
            global_outline = stage_data.get('global_outline', '')
            
            # 从 stage_data 中提取单元概述（如果已完成）
            if generation.current_stage == 'units_completed':
                unit_summaries_content = stage_data.get('unit_summaries', '')
                if unit_summaries_content:
                    # 解析内容
                    from app.services.outline_generator import OutlineGenerator
                    generator = OutlineGenerator(db)
                    parse_result = generator.parse_unit_summaries(
                        unit_summaries_content, 100, content_type
                    )
                    existing_parsed = parse_result
            
            # 从 input_params 获取 content_type
            input_params = generation.input_params or {}
            content_type = input_params.get('content_type', 'novel')
            
            # [2026-05-05] 修复：章节数提取支持章/集/场三种单元类型
            if global_outline:
                chapter_matches = re.findall(
                    r'第[一二三四五六七八九十百千万\d]+[章节集场]',
                    global_outline
                )
                if chapter_matches:
                    expected_count = len(set(chapter_matches))
        else:
            # 方式2：从 NovelProject 记录读取
            query = select(NovelProject).where(
                NovelProject.id == generation_id_or_project_id,
                NovelProject.user_id == current_user.id
            )
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                raise ResourceNotFoundException(
                    f"记录不存在: {generation_id_or_project_id}"
                )

            # 获取已有的单元概述数据
            existing_parsed = project.unit_summaries or {}
            global_outline = project.global_outline_content or ""
            content_type = getattr(project, 'content_type', 'novel')
            expected_count = project.total_chapters or 0

            # 如果 unit_summaries 中有更多数据，以实际数量为准
            if len(existing_parsed) > expected_count:
                expected_count = len(existing_parsed)

            # 如果预期数仍为0，尝试从全局大纲推断
            if expected_count == 0 and global_outline:
                # [2026-05-05] 修复：支持章/集/场三种单元类型
                chapter_matches = re.findall(
                    r'第[一二三四五六七八九十百千万\d]+[章节集场]',
                    global_outline
                )
                if chapter_matches:
                    expected_count = len(set(chapter_matches))

        existing_count = len(existing_parsed)

        # 计算续生成起始位置
        start_from_unit = existing_count + 1 if existing_count > 0 else 1

        # 重建 existing_content 文本
        existing_content_parts = []
        unit_label = '章' if content_type == 'novel' else '集' if content_type in (
            'series_script', 'series_outline') else '场'

        for unit_num, unit_data in sorted(existing_parsed.items(), key=lambda x: int(x[0])):
            title = unit_data.get("title", "")
            summary = unit_data.get("summary", "")
            full_content = unit_data.get("full_content", "") or summary
            # [2026-05-05] 修复：根据content_type使用正确的标题格式，与_build_revised_content保持一致
            # novel: ### 第N章：标题 / series: **第N集：标题** / movie: **第N场：标题**
            if content_type == 'novel':
                existing_content_parts.append(
                    f"### 第{unit_num}章：{title}\n\n{full_content}"
                )
            elif content_type in ('movie_script', 'movie_outline'):
                existing_content_parts.append(
                    f"**第{unit_num}场：{title}**\n\n{full_content}"
                )
            else:
                existing_content_parts.append(
                    f"**第{unit_num}集：{title}**\n\n{full_content}"
                )
        existing_content = "\n\n".join(existing_content_parts)

        # 判断是否可以续生成
        can_resume = existing_count > 0 and existing_count < expected_count

        return ResponseModel(
            success=True,
            message="断点信息获取成功",
            data={
                "generation_id_or_project_id": generation_id_or_project_id,
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
        对单元概述执行自动质量检测和修正（v3.0重构）

        一体化流程：
        1. 五维度质控分析（unit_structure / unit_character / unit_consistency / unit_timeline_space / unit_ooc）
        2. 发现问题后自动调用LLM进行整体修正
        3. 返回质控报告 + 修正后内容 + 变更列表
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

            logger.info(
                f"[单元概述自动质控] 开始一体化质控检测与修正，单元数: {len(data.unit_summaries)}")

            # 调用一体化自动质控修正方法
            result = await generator._auto_qc_and_revise_unit_summaries(
                unit_summaries=data.unit_summaries,
                global_outline=data.global_outline,
                content_type=data.content_type,
                user_id=current_user.id,
                temperature=data.temperature if hasattr(data, 'temperature') else 0.7
            )

            logger.info(
                f"[单元概述自动质控] 完成，得分: {result['quality_report'].get('overall_score', 0) if result['quality_report'] else 'N/A'}, "
                f"修正单元数: {len(result.get('changes', []))}, "
                f"问题数: {result.get('issues_count', 0)}"
            )

            # 返回完整结果
            return ResponseModel(
                success=True,
                message="质控检测与修正完成",
                data={
                    "quality_report": result.get("quality_report"),
                    "revised_content": result.get("revised_content"),
                    "revised_parsed": result.get("revised_parsed"),
                    "original_content": result.get("original_content"),
                    "original_parsed": result.get("original_parsed"),
                    "changes": result.get("changes", []),
                    "has_issues": result.get("has_issues", False),
                    "issues_count": result.get("issues_count", 0),
                    "auto_revised": result.get("auto_revised", False)
                }
            )

        except Exception as e:
            logger.error(f"[单元概述自动质控] 失败: {str(e)}", exc_info=True)
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

    @router.post("/outline/repair-kb-collection/{project_id}")
    async def repair_kb_vector_collection(
        project_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """
        修复知识图谱向量库（v4.3：HNSW索引损坏自动修复）

        当 ChromaDB HNSW 索引因异常关闭而损坏（Nothing found on disk），
        从知识图谱 JSON 文件重建向量库。也支持手动触发修复。
        """
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
        from app.models.novel_project import NovelProject
        from sqlalchemy import select

        try:
            # 校验项目归属
            query = select(NovelProject).where(
                NovelProject.id == project_id,
                NovelProject.user_id == current_user.id
            )
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                raise ResourceNotFoundException(f"项目不存在: {project_id}")

            kb_manager = ProjectKnowledgeBase(db=db)
            repair_result = await kb_manager.repair_kb_vector_store(project_id)

            if repair_result["success"]:
                logger.info(
                    f"用户 {current_user.id} 修复向量库成功: "
                    f"project_id={project_id}, "
                    f"entities={repair_result['entity_count']}, "
                    f"relations={repair_result['relation_count']}"
                )
                return ResponseModel(
                    success=True,
                    data=repair_result,
                    message=repair_result["message"]
                )
            else:
                return ResponseModel(
                    success=False,
                    data=repair_result,
                    message=repair_result["message"]
                )

        except ResourceNotFoundException:
            raise
        except Exception as e:
            logger.error(f"修复向量库失败: {str(e)}")
            raise GenerationException(f"修复失败: {str(e)}")


# ==================== 后台任务 ====================

async def _build_kb_from_outline_task(project_id: int, outline_content: str):
    """后台构建知识图谱任务（v4.2：二阶段流程内建）

    从全局大纲构建知识图谱，更新项目状态。
    复用 ProjectKnowledgeBase.build_global_outline_graph()。
    """
    from app.models.novel_project import NovelProject
    from sqlalchemy import select
    from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
    from app.agents.llm_manager import llm_manager
    from app.core.database import async_session_maker
    from datetime import datetime
    import time

    async with async_session_maker() as db:
        try:
            query = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()

            if not project:
                logger.error(f"[KB构建任务] 项目不存在: project_id={project_id}")
                return

            kb_manager = ProjectKnowledgeBase(db=db)

            # 获取LLM提供者（用于实体提取）
            llm_provider = None
            try:
                llm_provider = await llm_manager.get_provider_from_db(
                    db, project.user_id)
            except Exception as e:
                logger.warning(f"[KB构建任务] 获取LLM提供者失败: {e}")

            # 构建全局大纲图谱
            build_result = await kb_manager.build_global_outline_graph(
                project_id=project_id,
                outline_content=outline_content,
                llm_provider=llm_provider,
                project=project,
            )

            if build_result.get("success"):
                project.kb_status = "ready"
                project.project_kb_collection = kb_manager.get_collection_name(
                    project_id)
                project.global_outline_graph_path = build_result.get("graph_path")
                project.kb_build_progress = {
                    "stage": "completed",
                    "progress": 100,
                    "message": "知识图谱构建完成",
                    "entity_count": build_result.get("entity_count", 0),
                    "relation_count": build_result.get("relation_count", 0),
                    "completed_at": datetime.now().isoformat(),
                }
                logger.info(
                    f"[KB构建任务] 完成: project_id={project_id}, "
                    f"entities={build_result.get('entity_count')}, "
                    f"relations={build_result.get('relation_count')}")
            else:
                project.kb_status = "failed"
                project.kb_build_progress = {
                    "stage": "failed",
                    "progress": 0,
                    "message": f"构建失败: {build_result.get('error', '未知错误')}",
                }
                logger.error(
                    f"[KB构建任务] 失败: project_id={project_id}, "
                    f"error={build_result.get('error')}")

            await db.commit()

        except Exception as e:
            logger.error(f"[KB构建任务] 异常: project_id={project_id}, error={e!r}")
            try:
                project.kb_status = "failed"
                project.kb_build_progress = {
                    "stage": "failed",
                    "progress": 0,
                    "message": f"构建异常: {str(e)}",
                }
                await db.commit()
            except Exception:
                pass
