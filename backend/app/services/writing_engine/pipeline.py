"""
多Agent协作文学作品生成系统 - 写作流水线

模块: services.writing_engine
文件: pipeline.py
功能: 连接TaskManager和OrchestratorAgent，管理写作任务的执行生命周期

依赖关系:
    - 依赖: task_manager.py, app.agents.writing.orchestrator_agent, 
            app.agents.writing.base_agent, app.agents.writing.agent_config
    - 被依赖: API层

创建时间: 2026-03-27
最后修改: 2026-03-27
版本: 1.0.0
作者: AI Assistant
"""
import asyncio
from typing import Dict, Optional, TYPE_CHECKING
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.writing_task import WritingTask, TaskStatus
from app.agents.writing.orchestrator_agent import OrchestratorAgent
from app.agents.writing.base_agent import AgentContext, AgentResult
from app.agents.writing.agent_config import AgentConfig
from app.core.database import async_session_maker

if TYPE_CHECKING:
    from app.services.writing_engine.websocket_manager import WebSocketManager
    from app.agents.writing.stats_interceptor import StatsInterceptor


logger = get_logger("writing_engine.pipeline")


class WritingPipeline:
    """写作流水线 - 管理单个写作任务的执行

    职责：
    1. 连接TaskManager和OrchestratorAgent
    2. 管理活跃流水线的生命周期
    3. 处理任务的中断和续传
    4. 协调WebSocket消息推送

    使用模式：
    - 每个活跃任务对应一个WritingPipeline实例
    - 通过类变量_active_pipelines跟踪所有活跃实例
    - 支持通过task_id获取活跃流水线
    - Pipeline自己管理数据库会话生命周期，不依赖外部传入的会话
    """

    # 类变量：存储所有活跃的流水线实例
    _active_pipelines: Dict[int, "WritingPipeline"] = {}

    def __init__(
        self,
        task_id: int,
        config: Optional[AgentConfig] = None
    ):
        """初始化写作流水线

        Args:
            task_id: 写作任务ID
            config: Agent配置（可选，使用默认配置）
        """
        self.task_id = task_id
        self.config = config or AgentConfig()

        # 数据库会话（在_execute中动态创建）
        self.db: Optional[AsyncSession] = None

        # 任务对象（在_execute中加载）
        self.task: Optional[WritingTask] = None

        # OrchestratorAgent实例
        self._orchestrator: Optional[OrchestratorAgent] = None

        # WebSocket管理器
        self._ws_manager: Optional["WebSocketManager"] = None

        # 统计拦截器
        self._stats_interceptor: Optional["StatsInterceptor"] = None

        # 执行任务
        self._execution_task: Optional[asyncio.Task] = None

        # 执行结果
        self._result: Optional[AgentResult] = None

    @classmethod
    def get_active_pipeline(cls, task_id: int) -> Optional["WritingPipeline"]:
        """获取指定任务的活跃流水线

        Args:
            task_id: 任务ID

        Returns:
            WritingPipeline或None
        """
        return cls._active_pipelines.get(task_id)

    @classmethod
    def remove_active_pipeline(cls, task_id: int) -> None:
        """从活跃列表中移除流水线

        Args:
            task_id: 任务ID
        """
        if task_id in cls._active_pipelines:
            del cls._active_pipelines[task_id]
            logger.info(f"流水线已从活跃列表移除: task_id={task_id}")

    @classmethod
    def get_all_active_pipelines(cls) -> Dict[int, "WritingPipeline"]:
        """获取所有活跃流水线

        Returns:
            Dict[task_id, WritingPipeline]
        """
        return cls._active_pipelines.copy()

    def set_ws_manager(self, ws_manager: "WebSocketManager") -> None:
        """注入WebSocket管理器

        Args:
            ws_manager: WebSocket管理器实例
        """
        self._ws_manager = ws_manager
        logger.debug(f"WebSocket管理器已设置: task_id={self.task_id}")

    def set_stats_interceptor(self, interceptor: "StatsInterceptor") -> None:
        """注入统计拦截器

        Args:
            interceptor: 统计拦截器实例
        """
        self._stats_interceptor = interceptor
        logger.debug(f"统计拦截器已设置: task_id={self.task_id}")

    async def _reload_api_keys(self, db: AsyncSession) -> None:
        """从数据库重新加载API Key

        续传时根据config_id从数据库重新加载API Key，确保续传后能正常调用LLM。

        Args:
            db: 数据库会话
        """
        from app.models.writing_model_config import WritingModelConfig as WMC
        from app.core.security import api_key_encryption
        from app.agents.writing.agent_config import AgentModelConfig
        from app.agents.writing.base_agent import AgentRole

        if not self.config:
            return

        for role_str, model_config in self.config.configs.items():
            try:
                # 如果有config_id，从数据库重新加载API Key
                if model_config.config_id:
                    result = await db.execute(
                        select(WMC).where(
                            WMC.id == model_config.config_id).limit(1)
                    )
                    saved_config = result.scalar_one_or_none()
                    if saved_config:
                        api_key = api_key_encryption.decrypt(
                            saved_config.encrypted_key)
                        # 更新配置中的API Key
                        role = AgentRole(role_str)
                        self.config.update_config(role, AgentModelConfig(
                            model_id=saved_config.model_id,
                            provider=saved_config.provider,
                            api_base=saved_config.api_base,
                            api_key=api_key,
                            temperature=model_config.temperature,
                            max_tokens=model_config.max_tokens,
                            config_id=saved_config.id
                        ))
                        logger.info(
                            f"从数据库重新加载API Key: role={role_str}, config_id={saved_config.id}")
                    else:
                        logger.warning(
                            f"未找到模型配置: role={role_str}, config_id={model_config.config_id}")
            except Exception as e:
                logger.warning(f"重新加载API Key失败: role={role_str}, error={e}")

    async def _auto_load_default_config(self, db: AsyncSession) -> None:
        """自动加载用户的默认模型配置

        当续传时 task.config 中没有 agent_configs 时，尝试自动加载用户的默认模型配置。

        Args:
            db: 数据库会话
        """
        from app.models.writing_model_config import WritingModelConfig as WMC
        from app.core.security import api_key_encryption
        from app.agents.writing.agent_config import AgentConfig, AgentModelConfig
        from app.agents.writing.base_agent import AgentRole

        if not self.task:
            return

        try:
            # 查询用户的第一个活跃模型配置
            result = await db.execute(
                select(WMC).where(
                    WMC.user_id == self.task.user_id,
                    WMC.is_active == True
                ).order_by(WMC.updated_at.desc()).limit(1)
            )
            default_config = result.scalar_one_or_none()

            if default_config:
                api_key = api_key_encryption.decrypt(
                    default_config.encrypted_key)
                # 为所有可配置角色设置同一模型
                configurable_roles = [
                    AgentRole.ORCHESTRATOR, AgentRole.STRUCTURAL, AgentRole.WRITER,
                    AgentRole.LOGIC_EDITOR, AgentRole.STYLE_EDITOR, AgentRole.COMPLIANCE,
                    AgentRole.KNOWLEDGE
                ]
                for role in configurable_roles:
                    self.config.update_config(role, AgentModelConfig(
                        model_id=default_config.model_id,
                        provider=default_config.provider,
                        api_base=default_config.api_base,
                        api_key=api_key,
                        temperature=0.7,
                        max_tokens=4096,
                        config_id=default_config.id
                    ))
                logger.info(
                    f"[续传] 自动加载用户默认模型配置: user_id={self.task.user_id}, config_id={default_config.id}, model={default_config.model_id}")
            else:
                logger.error(f"[续传] 用户没有可用的模型配置: user_id={self.task.user_id}")
        except Exception as e:
            logger.error(f"[续传] 自动加载默认模型配置失败: {e}")

    async def start(self) -> None:
        """启动流水线执行（异步，非阻塞）

        创建OrchestratorAgent实例并启动后台执行任务。
        执行结果通过WebSocket推送或存储在任务记录中。

        注意：此方法只负责启动后台任务，数据库会话在_execute中创建和管理
        """
        # 注册到活跃列表（使用task_id）
        WritingPipeline._active_pipelines[self.task_id] = self

        # 如果没有注入WebSocket管理器，尝试获取全局实例
        if not self._ws_manager:
            try:
                from app.services.writing_engine.websocket_manager import get_websocket_manager
                self._ws_manager = get_websocket_manager()
                logger.debug(f"WebSocket管理器已自动获取: task_id={self.task_id}")
            except Exception as e:
                logger.warning(
                    f"获取WebSocket管理器失败: task_id={self.task_id}, error={e}")

        # 启动后台执行任务（数据库会话在_execute中创建）
        self._execution_task = asyncio.create_task(self._execute())

        logger.info(f"写作流水线已启动: task_id={self.task_id}")

    async def _execute(self) -> None:
        """执行写作任务（内部方法）

        在自己的数据库会话中调用OrchestratorAgent.execute，
        处理执行结果和异常，更新任务状态并通过WebSocket推送进度。
        """
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            self.db = db
            try:
                # 加载任务对象
                from sqlalchemy import select
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                self.task = result.scalar_one_or_none()

                if not self.task:
                    logger.error(f"任务不存在: task_id={self.task_id}")
                    return

                # 安全检查：如果 total_units 为 0 或 None，尝试从数据库查询实际单元数并更新
                if not self.task.total_units or self.task.total_units == 0:
                    logger.warning(f"任务 total_units 为 0 或 None，尝试从数据库查询实际单元数")

                    from app.models.novel_project import NovelProject
                    from app.models.novel_chapter import NovelChapter
                    from sqlalchemy import func

                    # 获取项目信息
                    project_result = await db.execute(
                        select(NovelProject).where(
                            NovelProject.id == self.task.project_id).limit(1)
                    )
                    project = project_result.scalar_one_or_none()

                    actual_unit_count = 0
                    if project:
                        # 优先从 unit_summaries (JSON字段) 获取
                        if project.unit_summaries and isinstance(project.unit_summaries, dict):
                            actual_unit_count = len(project.unit_summaries)

                        if actual_unit_count == 0:
                            # 从 NovelChapter 表查询章节数
                            chapter_count_result = await db.execute(
                                select(func.count(NovelChapter.id)).where(
                                    NovelChapter.project_id == self.task.project_id
                                )
                            )
                            actual_unit_count = chapter_count_result.scalar() or 0

                        if actual_unit_count == 0:
                            # 兜底：使用项目的 total_chapters 字段
                            actual_unit_count = project.total_chapters or 0

                    # 根据 start_from 和 unit_count 计算实际要生成的单元数
                    start_from = self.task.start_from or 1
                    unit_count = self.task.unit_count
                    available_units = max(
                        0, actual_unit_count - start_from + 1)

                    if unit_count is not None:
                        total_units = min(unit_count, available_units)
                    else:
                        total_units = available_units

                    if total_units > 0:
                        self.task.total_units = total_units
                        await db.commit()
                        logger.info(
                            f"已更新任务 total_units: task_id={self.task_id}, total_units={total_units}")
                    else:
                        logger.error(
                            f"无法获取有效的 total_units: task_id={self.task_id}, project_id={self.task.project_id}")
                        self.task.status = TaskStatus.FAILED
                        self.task.error_message = "项目没有可生成的单元"
                        await db.commit()
                        return

                # 检查任务状态
                if self.task.status == TaskStatus.RUNNING:
                    logger.warning(f"任务已在运行中: task_id={self.task_id}")
                    return

                # 创建OrchestratorAgent
                self._orchestrator = OrchestratorAgent(
                    db=db, config=self.config)

                # 设置统计拦截器
                if self._stats_interceptor:
                    self._orchestrator.set_stats_interceptor(
                        self._stats_interceptor)

                # 设置WebSocket管理器
                if self._ws_manager:
                    self._orchestrator.set_ws_manager(self._ws_manager)

                # 更新任务状态为运行中
                self.task.status = TaskStatus.RUNNING
                self.task.start_time = datetime.now()
                await db.commit()

                # 通知状态变更
                await self._notify_status_change(TaskStatus.PENDING, TaskStatus.RUNNING)

                # 构建执行上下文
                context = await self._build_context()

                # 执行Orchestrator
                self._result = await self._orchestrator.execute(context)

                # 处理执行结果
                if self._result.success:
                    self.task.status = TaskStatus.COMPLETED
                    self.task.end_time = datetime.now()
                    logger.info(f"写作任务完成: task_id={self.task.id}")
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.COMPLETED)
                else:
                    self.task.status = TaskStatus.FAILED
                    self.task.error_message = self._result.errors[0] if self._result.errors else "未知错误"
                    self.task.end_time = datetime.now()
                    logger.error(
                        f"写作任务失败: task_id={self.task.id}, error={self.task.error_message}")
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.FAILED)

                await db.commit()

            except asyncio.CancelledError:
                # 任务被取消（中断）
                if self.task:
                    logger.info(f"写作任务被中断: task_id={self.task.id}")
                    self.task.status = TaskStatus.INTERRUPTED
                    self.task.end_time = datetime.now()
                    await db.commit()
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.INTERRUPTED)
                else:
                    logger.info(f"写作任务被中断: task_id={self.task_id}")

            except Exception as e:
                # 执行异常
                logger.exception(
                    f"写作任务执行异常: task_id={self.task_id}, error={str(e)}")
                if self.task:
                    self.task.status = TaskStatus.FAILED
                    self.task.error_message = str(e)
                    self.task.end_time = datetime.now()
                    await db.commit()
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.FAILED)

            finally:
                # 从活跃列表移除
                WritingPipeline.remove_active_pipeline(self.task_id)
                self.db = None

    async def _build_context(self) -> AgentContext:
        """构建Orchestrator执行上下文

        Returns:
            AgentContext: 执行上下文
        """
        import json
        import os
        task_config = self.task.config or {}

        # 初始化变量
        project = None
        outline = task_config.get("outline", {})
        character_profiles = task_config.get("character_profiles", [])
        world_settings = task_config.get("world_settings", {})

        # 从数据库加载项目数据
        from app.models.novel_project import NovelProject
        from sqlalchemy import select
        from app.core.database import async_session_maker

        # 如果没有数据库会话，创建临时会话
        db_session = self.db
        temp_session = False
        if not db_session:
            db_session = async_session_maker()
            temp_session = True

        if db_session:
            project_result = await db_session.execute(
                select(NovelProject).where(
                    NovelProject.id == self.task.project_id).limit(1)
            )
            project = project_result.scalar_one_or_none()

        if project:
            # 1. 加载大纲
            if not outline or not isinstance(outline, dict) or not outline.get("chapters"):
                if project.outline_content:
                    try:
                        outline_data = json.loads(project.outline_content) if project.outline_content.strip(
                        ).startswith('{') else {"raw_content": project.outline_content}
                        if outline_data.get("chapters"):
                            outline = outline_data
                            logger.info(
                                f"[上下文构建] 从项目加载大纲，章节数: {len(outline_data.get('chapters', []))}")
                    except (json.JSONDecodeError, AttributeError):
                        pass

            # 2. 加载单元概述
            if not task_config.get("unit_summaries") and project.unit_summaries:
                task_config["unit_summaries"] = project.unit_summaries
                logger.info(
                    f"[上下文构建] 从项目加载 unit_summaries，单元数: {len(project.unit_summaries) if isinstance(project.unit_summaries, dict) else 0}")

            # 3. 从知识图谱加载人物设定和世界观（如果未在配置中提供）
            if not character_profiles and project.global_outline_graph_path:
                try:
                    from app.tools.novel_graph_rag import NovelKnowledgeGraph

                    graph_path = project.global_outline_graph_path
                    if os.path.exists(graph_path):
                        knowledge_graph = NovelKnowledgeGraph(
                            persist_path=graph_path)
                        if knowledge_graph.load():
                            # 提取人物设定
                            character_profiles = knowledge_graph.get_character_profiles()
                            logger.info(
                                f"[上下文构建] 从知识图谱加载人物设定: {len(character_profiles)} 个角色")

                            # 提取世界观设定
                            world_settings = knowledge_graph.get_world_settings()
                            logger.info(
                                f"[上下文构建] 从知识图谱加载世界观设定: {len(world_settings.get('rules', []))} 条规则, {len(world_settings.get('locations', []))} 个地点")
                    else:
                        logger.warning(f"[上下文构建] 知识图谱文件不存在: {graph_path}")
                except Exception as e:
                    logger.warning(f"[上下文构建] 加载知识图谱失败: {e}")

            # 4. 尝试从大纲内容中提取人物设定（备选方案）
            if not character_profiles and outline:
                character_profiles = self._extract_characters_from_outline(
                    outline)
                if character_profiles:
                    logger.info(
                        f"[上下文构建] 从大纲内容提取人物设定: {len(character_profiles)} 个角色")

        # 获取字数配置
        words_per_unit = task_config.get("words_per_chapter", 3000)

        # 获取项目类型
        content_type = "novel"  # 默认值
        if project and hasattr(project, 'content_type') and project.content_type:
            content_type = project.content_type

        # 架构优化：统一使用 direct 模式（基于全局大纲+单元概述的直接生成）
        # 移除了根据项目类型选择生成模式的逻辑，简化写作流程
        generation_mode = "direct"  # 固定使用直接生成模式
        logger.info(
            f"[上下文构建] 项目类型: {content_type}, 生成模式: {generation_mode} (架构优化版)")

        # 记录上下文构建详情
        unit_summaries = task_config.get("unit_summaries", {})
        logger.info(
            f"[上下文构建] 最终配置: unit_summaries数量={len(unit_summaries)}, outline章节={len(outline.get('chapters', []))}, 人物数={len(character_profiles)}")

        # 记录 unit_summaries 的详细内容（前3个单元的标题）
        if unit_summaries:
            sample_keys = list(unit_summaries.keys())[:3]
            for key in sample_keys:
                unit_data = unit_summaries.get(key, {})
                logger.debug(
                    f"[上下文构建] 单元{key}: title={unit_data.get('title', 'N/A')}, summary_len={len(unit_data.get('summary', ''))}")

        # 记录人物设定详情
        if character_profiles:
            for char in character_profiles[:3]:
                logger.info(
                    f"[上下文构建] 人物: {char.get('name', '未知')} - {char.get('role', '')} - {char.get('personality', '')[:50]}")

        # 加载风格文档相关设置
        ai_elimination_enabled = True
        ai_elimination_threshold = 50
        style_document_features = ""

        if project:
            # AI文风消除设置
            ai_elimination_enabled = project.ai_elimination_enabled if project.ai_elimination_enabled is not None else True
            ai_elimination_threshold = project.ai_elimination_threshold if project.ai_elimination_threshold is not None else 50

            # 风格文档特征 - 整合完整的风格分析结果
            if project.style_config:
                style_config = project.style_config if isinstance(
                    project.style_config, dict) else {}

                # 构建完整的风格文档特征字符串
                style_parts = []

                # 1. 写作风格指南（核心）
                style_guide = style_config.get("style_guide_for_writing", "")
                if style_guide:
                    style_parts.append(f"【写作风格指南】\n{style_guide}")

                # 2. 模仿要点
                key_points = style_config.get("key_imitation_points", [])
                if key_points:
                    points_text = "\n".join([f"- {p}" for p in key_points])
                    style_parts.append(f"【模仿要点】\n{points_text}")

                # 3. 风格画像摘要（提取关键维度）
                style_profile = style_config.get("style_profile", {})
                if style_profile:
                    profile_parts = []
                    # 词汇特征
                    vocab = style_profile.get("vocabulary", {})
                    if vocab:
                        word_pref = vocab.get("word_preference", "")
                        sig_words = vocab.get("signature_words", [])
                        if word_pref:
                            profile_parts.append(f"用词偏好: {word_pref}")
                        if sig_words:
                            profile_parts.append(
                                f"标志性词汇: {', '.join(sig_words[:5])}")

                    # 句式特征
                    sentence = style_profile.get("sentence_structure", {})
                    if sentence:
                        avg_len = sentence.get("average_length", "")
                        patterns = sentence.get("preferred_patterns", [])
                        if avg_len:
                            profile_parts.append(f"句式特点: {avg_len}")
                        if patterns:
                            profile_parts.append(
                                f"偏好句式: {'; '.join(patterns[:2])}")

                    # 叙事特征
                    narrative = style_profile.get("narrative_style", {})
                    if narrative:
                        perspective = narrative.get("perspective", "")
                        pacing = narrative.get("pacing", "")
                        if perspective:
                            profile_parts.append(f"叙事视角: {perspective}")
                        if pacing:
                            profile_parts.append(f"叙事节奏: {pacing}")

                    # 对话特征
                    dialogue = style_profile.get("dialogue_style", {})
                    if dialogue:
                        dial_style = dialogue.get("overall_style", "")
                        if dial_style:
                            profile_parts.append(f"对话风格: {dial_style}")

                    # 情感表达
                    emotional = style_profile.get("emotional_expression", {})
                    if emotional:
                        tone = emotional.get("tone", "")
                        if tone:
                            profile_parts.append(f"情感基调: {tone}")

                    if profile_parts:
                        style_parts.append(
                            f"【风格画像摘要】\n" + "\n".join(profile_parts))

                # 4. 示例转换
                examples = style_config.get("example_transformations", [])
                if examples:
                    example_texts = []
                    for i, ex in enumerate(examples[:2], 1):  # 最多取2个示例
                        orig = ex.get("original", "")
                        styled = ex.get("styled", "")
                        if orig and styled:
                            example_texts.append(
                                f"示例{i}: \"{orig}\" → \"{styled}\"")
                    if example_texts:
                        style_parts.append(
                            f"【风格转换示例】\n" + "\n".join(example_texts))

                # 5. 避免模式
                avoid_patterns = style_config.get("avoid_patterns", [])
                if avoid_patterns:
                    avoid_text = "\n".join([f"- {p}" for p in avoid_patterns])
                    style_parts.append(f"【应避免的模式】\n{avoid_text}")

                # 合并为完整特征
                style_document_features = "\n\n".join(style_parts)
                logger.info(
                    f"[上下文构建] 加载完整风格文档特征，长度: {len(style_document_features)}，包含{len(style_parts)}个部分")

            logger.info(
                f"[上下文构建] AI文风消除: enabled={ai_elimination_enabled}, threshold={ai_elimination_threshold}")

        # 如果使用了临时会话，需要关闭
        if temp_session:
            await db_session.close()

        return AgentContext(
            task_id=self.task.uuid,
            unit_index=0,  # Orchestrator会处理所有单元
            project_id=self.task.project_id,
            user_id=self.task.user_id,
            outline=outline,
            previous_content=task_config.get("previous_content", ""),
            global_context=task_config.get("global_context", ""),
            character_profiles=character_profiles,
            world_settings=world_settings,
            style_guide=task_config.get("style_guide", {}),
            config={
                "total_units": self.task.total_units,
                "start_from": self.task.start_from,
                "unit_count": self.task.unit_count,
                "words_per_unit": words_per_unit,
                "max_concurrent_writers": task_config.get("max_concurrent_writers", 3),
                "stop_on_error": task_config.get("stop_on_error", True),
                "unit_summaries": unit_summaries,
                "generation_mode": generation_mode,  # 添加生成模式配置
                "content_type": content_type,  # 添加项目类型配置
                "ai_elimination_enabled": ai_elimination_enabled,  # AI文风消除开关
                "ai_elimination_threshold": ai_elimination_threshold,  # AI文风消除阈值
                "style_document_features": style_document_features,  # 风格文档特征
                **task_config.get("agent_config", {})
            }
        )

    def _extract_characters_from_outline(self, outline: dict) -> list:
        """从大纲内容中提取人物设定

        作为备选方案，从大纲JSON结构中提取人物信息。

        Args:
            outline: 大纲字典

        Returns:
            人物设定列表
        """
        characters = []

        # 尝试从多种可能的结构中提取
        # 结构1: outline.characters
        if outline.get("characters"):
            for char in outline.get("characters", []):
                if isinstance(char, dict):
                    characters.append({
                        "name": char.get("name", ""),
                        "role": char.get("role", char.get("身份", "")),
                        "personality": char.get("personality", char.get("性格", "")),
                        "background": char.get("background", char.get("背景", "")),
                        "description": char.get("description", "")
                    })
                elif isinstance(char, str):
                    characters.append({"name": char})

        # 结构2: outline.人物设定
        if not characters and outline.get("人物设定"):
            for char in outline.get("人物设定", []):
                if isinstance(char, dict):
                    characters.append({
                        "name": char.get("name", char.get("姓名", "")),
                        "role": char.get("role", char.get("身份", "")),
                        "personality": char.get("personality", char.get("性格", "")),
                        "background": char.get("background", char.get("背景", "")),
                        "description": char.get("description", "")
                    })

        # 结构3: outline.main_characters
        if not characters and outline.get("main_characters"):
            for char in outline.get("main_characters", []):
                if isinstance(char, dict):
                    characters.append({
                        "name": char.get("name", ""),
                        "role": char.get("role", "主角"),
                        "personality": char.get("personality", ""),
                        "background": char.get("background", ""),
                        "description": char.get("description", "")
                    })
                elif isinstance(char, str):
                    characters.append({"name": char, "role": "角色"})

        return characters

    async def interrupt(self) -> bool:
        """中断当前任务

        向Orchestrator发送中断信号，Orchestrator会在下一个检查点检测到中断并更新状态。

        Returns:
            bool: 是否成功触发中断
        """
        if not self._orchestrator:
            logger.warning(f"Orchestrator未初始化，无法中断: task_id={self.task_id}")
            # 尝试直接更新任务状态
            await self._update_task_status_interrupted()
            return False

        # 检查任务状态（使用task属性或从数据库加载）
        task_status = None
        if self.task:
            task_status = self.task.status
        else:
            # 尝试从数据库加载任务状态
            from sqlalchemy import select
            async with async_session_maker() as db:
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                task = result.scalar_one_or_none()
                if task:
                    task_status = task.status
                    self.task = task

        if task_status != TaskStatus.RUNNING:
            logger.warning(
                f"任务不在运行状态，无法中断: task_id={self.task_id}, status={task_status}")
            return False

        try:
            # 发送中断信号给Orchestrator
            await self._orchestrator.interrupt()
            logger.info(f"中断信号已发送到Orchestrator: task_id={self.task_id}")

            # 发送WebSocket通知
            if self._ws_manager:
                try:
                    await self._ws_manager.send_status_change(
                        task_id=self.task_id,
                        old_status=TaskStatus.RUNNING,
                        new_status=TaskStatus.INTERRUPTED
                    )
                except Exception as ws_error:
                    logger.warning(
                        f"发送中断WebSocket通知失败: task_id={self.task_id}, error={ws_error}")

            return True
        except Exception as e:
            logger.error(f"发送中断信号失败: task_id={self.task_id}, error={str(e)}")
            # 尝试直接更新任务状态
            await self._update_task_status_interrupted()
            return False

    async def _update_task_status_interrupted(self) -> None:
        """直接更新任务状态为中断（降级处理）"""
        try:
            from sqlalchemy import update
            async with async_session_maker() as db:
                await db.execute(
                    update(WritingTask)
                    .where(WritingTask.id == self.task_id)
                    .values(status=TaskStatus.INTERRUPTED, end_time=datetime.now())
                )
                await db.commit()
                logger.info(f"已直接更新任务状态为中断: task_id={self.task_id}")
        except Exception as e:
            logger.error(f"更新任务状态失败: task_id={self.task_id}, error={e}")

    async def resume(self) -> bool:
        """从检查点续传任务

        注意：resume需要在_execute中或有自己的数据库会话中调用

        Returns:
            bool: 是否成功触发续传
        """
        # 如果任务未加载，先尝试加载
        if not self.task:
            logger.info(f"任务未加载，尝试加载任务: task_id={self.task_id}")
            from app.core.database import async_session_maker

            async with async_session_maker() as db:
                self.db = db
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                self.task = result.scalar_one_or_none()

                if not self.task:
                    logger.error(f"任务不存在: task_id={self.task_id}")
                    return False

                # 验证任务状态
                if self.task.status not in (TaskStatus.INTERRUPTED, TaskStatus.FAILED):
                    logger.warning(
                        f"任务不在可续传状态: task_id={self.task.id}, status={self.task.status}")
                    return False

                # 保存任务信息后关闭会话（后续会在_resume_execute中创建新会话）
                self.db = None

            logger.info(
                f"任务已加载: task_id={self.task.id}, status={self.task.status}")
        else:
            # 任务已加载，验证状态
            if self.task.status not in (TaskStatus.INTERRUPTED, TaskStatus.FAILED):
                logger.warning(
                    f"任务不在可续传状态: task_id={self.task.id}, status={self.task.status}")
                return False

        # 注册到活跃列表
        WritingPipeline._active_pipelines[self.task.id] = self

        # 启动续传任务（在_resume_execute中创建新的数据库会话）
        context = await self._build_context()
        self._execution_task = asyncio.create_task(
            self._resume_execute(context))

        logger.info(f"续传任务已启动: task_id={self.task.id}")
        return True

    async def continue_from(self, start_from: int, unit_count: int) -> bool:
        """从指定位置继续生成

        与resume不同，continue_from是在任务完成后追加新单元。

        Args:
            start_from: 起始单元索引
            unit_count: 要生成的单元数

        Returns:
            bool: 是否成功触发
        """
        # 如果任务未加载，先尝试加载
        if not self.task:
            logger.info(f"任务未加载，尝试加载任务: task_id={self.task_id}")
            async with async_session_maker() as db:
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                self.task = result.scalar_one_or_none()

                if not self.task:
                    logger.error(f"任务不存在: task_id={self.task_id}")
                    return False

        # 注册到活跃列表
        WritingPipeline._active_pipelines[self.task.id] = self

        # 启动继续生成任务
        self._execution_task = asyncio.create_task(
            self._continue_execute(start_from, unit_count)
        )

        logger.info(
            f"继续生成任务已启动: task_id={self.task.id}, start_from={start_from}, unit_count={unit_count}")
        return True

    async def _continue_execute(self, start_from: int, unit_count: int) -> None:
        """执行继续生成任务（内部方法）

        Args:
            start_from: 起始单元索引
            unit_count: 要生成的单元数
        """
        async with async_session_maker() as db:
            self.db = db
            try:
                # 加载任务对象
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                self.task = result.scalar_one_or_none()

                if not self.task:
                    logger.error(f"任务不存在: task_id={self.task_id}")
                    return

                # 从任务记录恢复模型配置
                if self.task.config:
                    task_config_data = self.task.config if isinstance(
                        self.task.config, dict) else {}
                    agent_configs = task_config_data.get("agent_configs", {})
                    if agent_configs:
                        self.config = AgentConfig.from_dict(
                            {"configs": agent_configs})
                        await self._reload_api_keys(db)
                    else:
                        await self._auto_load_default_config(db)
                else:
                    await self._auto_load_default_config(db)

                # 创建OrchestratorAgent
                self._orchestrator = OrchestratorAgent(
                    db=db, config=self.config)

                if self._stats_interceptor:
                    self._orchestrator.set_stats_interceptor(
                        self._stats_interceptor)

                if self._ws_manager:
                    self._orchestrator.set_ws_manager(self._ws_manager)

                # 更新状态为运行中
                self.task.status = TaskStatus.RUNNING
                await db.commit()
                await self._notify_status_change(TaskStatus.COMPLETED, TaskStatus.RUNNING)

                # 构建上下文，设置继续生成的参数
                context = await self._build_context()
                # 覆盖上下文中的起始位置和数量
                context.config["start_from"] = start_from
                context.config["unit_count"] = unit_count
                context.config["total_units"] = self.task.total_units

                # 执行Orchestrator（使用continue模式）
                self._result = await self._orchestrator.continue_from(context, start_from, unit_count)

                # 处理执行结果
                if self._result.success:
                    self.task.status = TaskStatus.COMPLETED
                    self.task.completed_units = self.task.total_units
                    self.task.end_time = datetime.now()
                    logger.info(f"继续生成任务完成: task_id={self.task.id}")
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.COMPLETED)
                else:
                    self.task.status = TaskStatus.FAILED
                    self.task.error_message = self._result.errors[0] if self._result.errors else "未知错误"
                    self.task.end_time = datetime.now()
                    logger.error(
                        f"继续生成任务失败: task_id={self.task.id}, error={self.task.error_message}")
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.FAILED)

                await db.commit()

            except asyncio.CancelledError:
                if self.task:
                    logger.info(f"继续生成任务被中断: task_id={self.task.id}")
                    self.task.status = TaskStatus.INTERRUPTED
                    self.task.end_time = datetime.now()
                    await db.commit()
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.INTERRUPTED)

            except Exception as e:
                logger.exception(
                    f"继续生成任务执行异常: task_id={self.task_id}, error={str(e)}")
                if self.task:
                    self.task.status = TaskStatus.FAILED
                    self.task.error_message = str(e)
                    self.task.end_time = datetime.now()
                    await db.commit()
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.FAILED)

            finally:
                WritingPipeline.remove_active_pipeline(self.task_id)
                self.db = None

    async def _resume_execute(self, context: AgentContext) -> None:
        """执行续传任务（内部方法）

        在自己的数据库会话中执行续传任务。

        Args:
            context: 执行上下文
        """
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            self.db = db
            try:
                # 加载任务对象
                from sqlalchemy import select
                result = await db.execute(
                    select(WritingTask).where(
                        WritingTask.id == self.task_id).limit(1)
                )
                self.task = result.scalar_one_or_none()

                if not self.task:
                    logger.error(f"任务不存在: task_id={self.task_id}")
                    return

                # 从任务记录恢复模型配置
                if self.task.config:
                    task_config_data = self.task.config if isinstance(
                        self.task.config, dict) else {}
                    logger.info(
                        f"[续传] task.config 存在，类型: {type(self.task.config)}, keys: {list(task_config_data.keys()) if task_config_data else 'empty'}")
                    # 提取 agent_configs 部分
                    agent_configs = task_config_data.get("agent_configs", {})
                    logger.info(
                        f"[续传] agent_configs: {list(agent_configs.keys()) if agent_configs else 'empty'}")
                    if agent_configs:
                        self.config = AgentConfig.from_dict(
                            {"configs": agent_configs})
                        logger.info(
                            f"从任务记录恢复模型配置: task_id={self.task_id}, agents={list(agent_configs.keys())}")
                        # 从数据库重新加载API Key
                        await self._reload_api_keys(db)
                    else:
                        # 兼容旧格式：整个 config 就是 agent_configs
                        if any(k in task_config_data for k in ["writer", "structural", "editor", "stylist", "compliance"]):
                            self.config = AgentConfig.from_dict(
                                {"configs": task_config_data})
                            logger.info(
                                f"从任务记录恢复模型配置(兼容格式): task_id={self.task_id}")
                            # 从数据库重新加载API Key
                            await self._reload_api_keys(db)
                        else:
                            logger.warning(
                                f"[续传] 未找到 agent_configs 且不匹配兼容格式，尝试自动加载用户默认模型配置")
                            # 尝试自动加载用户默认模型配置
                            await self._auto_load_default_config(db)
                else:
                    logger.warning(f"[续传] task.config 为空，尝试自动加载用户默认模型配置")
                    await self._auto_load_default_config(db)

                # 创建OrchestratorAgent
                self._orchestrator = OrchestratorAgent(
                    db=db, config=self.config)

                if self._stats_interceptor:
                    self._orchestrator.set_stats_interceptor(
                        self._stats_interceptor)

                # 设置WebSocket管理器
                if self._ws_manager:
                    self._orchestrator.set_ws_manager(self._ws_manager)

                # 更新状态
                self.task.status = TaskStatus.RUNNING
                await db.commit()
                await self._notify_status_change(TaskStatus.INTERRUPTED, TaskStatus.RUNNING)

                # 调用Orchestrator的resume方法
                self._result = await self._orchestrator.resume(context)

                # 处理执行结果
                if self._result.success:
                    self.task.status = TaskStatus.COMPLETED
                    self.task.end_time = datetime.now()
                    logger.info(f"续传任务完成: task_id={self.task.id}")
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.COMPLETED)
                else:
                    self.task.status = TaskStatus.FAILED
                    self.task.error_message = self._result.errors[0] if self._result.errors else "未知错误"
                    self.task.end_time = datetime.now()
                    logger.error(
                        f"续传任务失败: task_id={self.task.id}, error={self.task.error_message}")
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.FAILED)

                await db.commit()

            except asyncio.CancelledError:
                if self.task:
                    logger.info(f"续传任务被中断: task_id={self.task.id}")
                    self.task.status = TaskStatus.INTERRUPTED
                    self.task.end_time = datetime.now()
                    await db.commit()
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.INTERRUPTED)
                else:
                    logger.info(f"续传任务被中断: task_id={self.task_id}")

            except Exception as e:
                logger.exception(
                    f"续传任务执行异常: task_id={self.task_id}, error={str(e)}")
                if self.task:
                    self.task.status = TaskStatus.FAILED
                    self.task.error_message = str(e)
                    self.task.end_time = datetime.now()
                    await db.commit()
                    await self._notify_status_change(TaskStatus.RUNNING, TaskStatus.FAILED)

            finally:
                WritingPipeline.remove_active_pipeline(self.task_id)
                self.db = None

    async def _notify_status_change(
        self,
        old_status: TaskStatus,
        new_status: TaskStatus
    ) -> None:
        """通知任务状态变更

        Args:
            old_status: 旧状态
            new_status: 新状态
        """
        if self._ws_manager:
            try:
                await self._ws_manager.send_status_change(
                    task_id=self.task.id if self.task else self.task_id,
                    old_status=old_status,
                    new_status=new_status
                )
            except Exception as e:
                logger.error(
                    f"发送状态变更通知失败: task_id={self.task_id}, error={str(e)}")

    async def wait_for_completion(self, timeout: Optional[float] = None) -> Optional[AgentResult]:
        """等待任务完成

        Args:
            timeout: 超时时间（秒），None表示无限等待

        Returns:
            AgentResult或None（超时）
        """
        if not self._execution_task:
            return self._result

        try:
            await asyncio.wait_for(self._execution_task, timeout=timeout)
            return self._result
        except asyncio.TimeoutError:
            logger.warning(
                f"等待任务完成超时: task_id={self.task.id}, timeout={timeout}")
            return None

    @property
    def is_running(self) -> bool:
        """检查流水线是否在运行"""
        return (self.task is not None and
                self.task.status == TaskStatus.RUNNING and
                self._execution_task is not None)

    @property
    def result(self) -> Optional[AgentResult]:
        """获取执行结果"""
        return self._result
