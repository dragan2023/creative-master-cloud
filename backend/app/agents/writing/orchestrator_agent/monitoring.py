"""
多Agent协作文学作品生成系统 - 监控与错误处理模块

模块: agents.writing.orchestrator_agent
文件: monitoring.py
功能: 中断控制、WebSocket通信、检查点管理、人物状态追踪

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from collections import OrderedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.writing.base_agent import AgentContext, AgentResult, AgentRole
from app.models.writing_checkpoint import WritingCheckpoint
from app.core.logger import get_logger

if TYPE_CHECKING:
    from app.services.writing_engine.websocket_manager import WebSocketManager
    from app.agents.writing.character_state_tracker import CharacterStateTracker
    from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
    from app.tools.novel_graph_rag import NovelKnowledgeGraph


# ============================================================================
# 图谱缓存管理器 - 避免重复加载图谱文件
# ============================================================================

class GraphCache:
    """知识图谱缓存管理器

    使用LRU策略缓存已加载的图谱实例，避免重复I/O和解析开销。
    特别优化：对全局图谱使用长期缓存，单元图谱使用LRU淘汰。

    Attributes:
        max_unit_cache_size: 单元图谱最大缓存数量
        _global_cache: 全局图谱缓存（持久缓存）
        _unit_cache: 单元图谱缓存（LRU淘汰）
    """

    def __init__(self, max_unit_cache_size: int = 30):
        """
        初始化图谱缓存

        Args:
            max_unit_cache_size: 单元图谱最大缓存数量，默认30个
        """
        self.max_unit_cache_size = max_unit_cache_size
        # 全局图谱缓存：持久缓存，不淘汰
        self._global_cache: Dict[str, Tuple["NovelKnowledgeGraph", float]] = {}
        # 单元图谱缓存：使用OrderedDict实现LRU
        self._unit_cache: OrderedDict[str,
                                      Tuple["NovelKnowledgeGraph", float]] = OrderedDict()
        self._logger = get_logger("graph_cache")

        # 统计信息
        self._hit_count = 0
        self._miss_count = 0

    def get_or_load(self, graph_path: str, is_global: bool = False) -> Optional["NovelKnowledgeGraph"]:
        """
        获取或加载图谱

        优先从缓存获取，缓存未命中则加载并缓存。

        Args:
            graph_path: 图谱文件路径
            is_global: 是否为全局图谱

        Returns:
            图谱实例，加载失败返回None
        """
        from app.tools.novel_graph_rag import NovelKnowledgeGraph

        # 判断缓存类型
        cache = self._global_cache if is_global else self._unit_cache

        # 检查缓存命中
        if graph_path in cache:
            self._hit_count += 1
            graph, _ = cache[graph_path]
            # 更新LRU顺序（仅单元图谱）
            if not is_global and isinstance(cache, OrderedDict):
                cache.move_to_end(graph_path)
            self._logger.debug(f"图谱缓存命中: {os.path.basename(graph_path)}")
            return graph

        # 缓存未命中，加载图谱
        self._miss_count += 1
        if not os.path.exists(graph_path):
            self._logger.debug(f"图谱文件不存在: {graph_path}")
            return None

        graph = NovelKnowledgeGraph(persist_path=graph_path)
        if not graph.load():
            return None

        # 存入缓存
        if is_global:
            self._global_cache[graph_path] = (graph, time.time())
            self._logger.debug(f"全局图谱已缓存: {os.path.basename(graph_path)}")
        else:
            # LRU淘汰
            if len(self._unit_cache) >= self.max_unit_cache_size:
                oldest_path = next(iter(self._unit_cache))
                del self._unit_cache[oldest_path]
                self._logger.debug(f"LRU淘汰图谱: {os.path.basename(oldest_path)}")
            self._unit_cache[graph_path] = (graph, time.time())
            self._logger.debug(f"单元图谱已缓存: {os.path.basename(graph_path)}")

        return graph

    def invalidate(self, graph_path: str) -> None:
        """
        使指定图谱缓存失效

        当图谱被修改后调用，确保下次获取最新数据。

        Args:
            graph_path: 图谱文件路径
        """
        if graph_path in self._global_cache:
            del self._global_cache[graph_path]
            self._logger.debug(f"全局图谱缓存已失效: {os.path.basename(graph_path)}")
        if graph_path in self._unit_cache:
            del self._unit_cache[graph_path]
            self._logger.debug(f"单元图谱缓存已失效: {os.path.basename(graph_path)}")

    def invalidate_all(self) -> None:
        """使所有缓存失效"""
        self._global_cache.clear()
        self._unit_cache.clear()
        self._logger.info("所有图谱缓存已清除")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            包含命中率、缓存数量等统计信息
        """
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0
        return {
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": f"{hit_rate:.1%}",
            "global_cache_size": len(self._global_cache),
            "unit_cache_size": len(self._unit_cache)
        }


# ============================================================================
# 扩展上下文累积器 - 增量维护实体信息
# ============================================================================

class ExtendedContextAccumulator:
    """扩展上下文累积器

    增量维护已知实体信息，避免每次重新遍历所有前文章节。
    章节完成后增量更新，获取时直接返回累积结果。

    Attributes:
        known_facilities: 已知设施集合
        known_groups: 已知群体集合
        known_items: 已知道具集合
        unfinished_events: 未完成事件集合
        pending_foreshadows: 待回收伏笔集合
    """

    def __init__(self):
        """初始化累积器"""
        # 使用集合保证唯一性
        self.known_facilities: Set[str] = set()
        self.known_groups: Set[str] = set()
        self.known_items: Set[str] = set()
        self.unfinished_events: Set[str] = set()
        self.pending_foreshadows: Set[str] = set()

        # 已处理的章节号，用于追踪同步状态
        self._processed_chapters: Set[int] = set()
        self._logger = get_logger("context_accumulator")

    def update_from_graph(self, graph: "NovelKnowledgeGraph", chapter_num: int) -> None:
        """
        从图谱增量更新累积器

        Args:
            graph: 知识图谱实例
            chapter_num: 章节号
        """
        if chapter_num in self._processed_chapters:
            self._logger.debug(f"章节{chapter_num}已处理，跳过更新")
            return

        try:
            extended_entities = graph.get_extended_state_entities()

            # 更新设施
            for facility in extended_entities.get("facilities", []):
                name = facility.get("text", "")
                if name:
                    self.known_facilities.add(name)

            # 更新群体
            for group in extended_entities.get("groups", []):
                name = group.get("text", "")
                if name:
                    self.known_groups.add(name)

            # 更新道具
            for item in extended_entities.get("items", []):
                name = item.get("text", "")
                if name:
                    self.known_items.add(name)

            # 更新未完成事件（需要检查状态）
            for event in extended_entities.get("events", []):
                name = event.get("text", "")
                status = event.get("attributes", {}).get("状态", "")
                if name:
                    if status in ["已完成", "已结束", "已取消"]:
                        # 事件已完成，从集合中移除
                        self.unfinished_events.discard(name)
                    else:
                        self.unfinished_events.add(name)

            # 更新伏笔
            for foreshadow in extended_entities.get("foreshadows", []):
                name = foreshadow.get("text", "")
                if name:
                    self.pending_foreshadows.add(name)

            self._processed_chapters.add(chapter_num)
            self._logger.debug(
                f"累积器更新完成: 章节{chapter_num}, "
                f"设施={len(self.known_facilities)}, "
                f"群体={len(self.known_groups)}, "
                f"道具={len(self.known_items)}"
            )

        except Exception as e:
            self._logger.warning(f"累积器更新失败: 章节{chapter_num}, 错误={e}")

    def sync_from_global_graph(self, graph: "NovelKnowledgeGraph") -> None:
        """
        从全局图谱同步所有已知实体

        用于任务开始时初始化累积器状态。

        Args:
            graph: 全局知识图谱实例
        """
        try:
            extended_entities = graph.get_extended_state_entities()

            # 批量更新
            self.known_facilities = {
                f.get("text", "") for f in extended_entities.get("facilities", [])
                if f.get("text")
            }
            self.known_groups = {
                g.get("text", "") for g in extended_entities.get("groups", [])
                if g.get("text")
            }
            self.known_items = {
                i.get("text", "") for i in extended_entities.get("items", [])
                if i.get("text")
            }

            # 事件需要过滤状态
            self.unfinished_events = set()
            for event in extended_entities.get("events", []):
                name = event.get("text", "")
                status = event.get("attributes", {}).get("状态", "")
                if name and status not in ["已完成", "已结束", "已取消"]:
                    self.unfinished_events.add(name)

            self.pending_foreshadows = {
                f.get("text", "") for f in extended_entities.get("foreshadows", [])
                if f.get("text")
            }

            self._logger.info(
                f"从全局图谱同步完成: 设施={len(self.known_facilities)}, "
                f"群体={len(self.known_groups)}, "
                f"道具={len(self.known_items)}, "
                f"事件={len(self.unfinished_events)}, "
                f"伏笔={len(self.pending_foreshadows)}"
            )

        except Exception as e:
            self._logger.warning(f"从全局图谱同步失败: {e}")

    def to_dict(self) -> Dict[str, List[str]]:
        """
        转换为字典格式

        Returns:
            包含所有实体列表的字典
        """
        return {
            "known_facilities": list(self.known_facilities),
            "known_groups": list(self.known_groups),
            "known_items": list(self.known_items),
            "unfinished_events": list(self.unfinished_events),
            "pending_foreshadows": list(self.pending_foreshadows)
        }

    def reset(self) -> None:
        """重置累积器状态"""
        self.known_facilities.clear()
        self.known_groups.clear()
        self.known_items.clear()
        self.unfinished_events.clear()
        self.pending_foreshadows.clear()
        self._processed_chapters.clear()
        self._logger.debug("累积器已重置")


class MonitoringMixin:
    """监控与错误处理 Mixin

    提供：
    - 中断检测与处理
    - WebSocket消息推送
    - 检查点保存与加载
    - 人物状态追踪初始化与更新
    - 图谱缓存与上下文累积（v3.0.1优化）
    """

    # 这些属性由主类提供，类型提示
    db: AsyncSession
    _interrupt_event: Any  # asyncio.Event
    _ws_manager: Optional["WebSocketManager"]
    _current_task: Any  # WritingTask
    _stats_interceptor: Any  # StatsInterceptor
    _character_tracker: Optional["CharacterStateTracker"]
    _project_knowledge_base: Optional["ProjectKnowledgeBase"]
    _agent_instances: Dict[AgentRole, Any]  # Agent实例缓存
    logger: Any

    # v3.0.1优化：图谱缓存和上下文累积器
    _graph_cache: Optional[GraphCache] = None
    _context_accumulator: Optional[ExtendedContextAccumulator] = None

    def _check_interrupted(self) -> bool:
        """检查是否被中断

        Returns:
            True表示已被中断
        """
        return not self._interrupt_event.is_set()

    async def interrupt(self) -> None:
        """中断当前任务

        设置中断标志，并通知所有子Agent停止。
        中断是协作式的，需要Agent在关键点检查中断状态。
        """
        self.logger.info("收到中断信号，正在停止任务...")
        self._interrupt_event.clear()

        # 通知所有子Agent中断
        for agent_role, agent in self._agent_instances.items():
            try:
                if hasattr(agent, 'interrupt'):
                    await agent.interrupt()
                    self.logger.debug(f"已通知 {agent_role} Agent 中断")
            except Exception as e:
                self.logger.warning(f"通知 {agent_role} Agent 中断失败: {e}")

        # 发送中断通知到前端
        if self._current_task:
            await self._send_ws_message("status_change", {
                "old_status": "running",
                "new_status": "interrupted",
                "message": "任务已被用户中断"
            })

    async def _send_ws_message(self, msg_type: str, data: dict) -> None:
        """发送WebSocket消息的辅助方法

        安全地发送WebSocket消息，失败不影响主流程。

        Args:
            msg_type: 消息类型（task_progress/unit_progress/scene_progress/statistics/workflow_step/unit_quality_control）
            data: 消息数据
        """
        if not self._ws_manager:
            self.logger.warning(
                f"[WS消息] 发送失败: _ws_manager未设置, msg_type={msg_type}")
            return
        if not self._current_task:
            self.logger.warning(
                f"[WS消息] 发送失败: _current_task未设置, msg_type={msg_type}")
            return

        try:
            task_id = self._current_task.id

            if msg_type == "task_progress":
                await self._ws_manager.send_task_progress(
                    task_id=task_id,
                    completed_units=data.get("completed_units", 0),
                    total_units=data.get("total_units", 0),
                    current_unit=data.get("current_unit"),
                    current_scene=data.get("current_scene")
                )
            elif msg_type == "unit_progress":
                await self._ws_manager.send_unit_progress(
                    task_id=task_id,
                    unit_index=data.get("unit_index", 0),
                    unit_title=data.get("unit_title", ""),
                    status=data.get("status", "processing"),
                    progress=data.get("progress", 0.0)
                )
            elif msg_type == "scene_progress":
                await self._ws_manager.send_scene_progress(
                    task_id=task_id,
                    unit_index=data.get("unit_index", 0),
                    scene_index=data.get("scene_index", 0),
                    scene_title=data.get("scene_title", ""),
                    status=data.get("status", "pending")
                )
            elif msg_type == "statistics":
                await self._ws_manager.send_statistics(
                    task_id=task_id,
                    stats=data
                )
            elif msg_type == "workflow_step":
                await self._ws_manager.send_workflow_step(
                    task_id=task_id,
                    step=data.get("step", ""),
                    status=data.get("status", "running"),
                    message=data.get("message", ""),
                    agent_name=data.get("agent_name"),
                    unit_index=data.get("unit_index"),
                    scene_index=data.get("scene_index"),
                    icon=data.get("icon"),
                    data=data.get("extra_data")
                )
            elif msg_type == "unit_quality_control":
                # v2.0新增: 单元质控状态推送
                result = await self._ws_manager.send_custom_message(
                    task_id=task_id,
                    msg_type="unit_quality_control",
                    data=data
                )
                self.logger.info(
                    f"[WS消息] unit_quality_control已发送: "
                    f"task_id={task_id}, unit_index={data.get('unit_index')}, "
                    f"status={data.get('status')}, 连接数={result}"
                )
        except Exception as e:
            # 推送失败不影响主流程，只记录警告
            self.logger.warning(
                f"WebSocket消息发送失败: type={msg_type}, error={str(e)}")

    # ==================== 检查点管理 ====================

    async def _load_checkpoint(self, task_id: int) -> Optional[WritingCheckpoint]:
        """加载任务的最新检查点"""
        result = await self.db.execute(
            select(WritingCheckpoint).where(
                WritingCheckpoint.task_id == task_id
            ).order_by(WritingCheckpoint.id.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def _save_checkpoint(
        self,
        task_uuid: str,
        last_unit: int,
        last_scene_id: Optional[int],
        operation: str
    ) -> None:
        """保存检查点

        Args:
            task_uuid: 任务UUID
            last_unit: 最后完成的单元序号
            last_scene_id: 最后完成的场景ID
            operation: 最后执行的操作
        """
        # 需要通过UUID加载任务获取ID
        from app.models.writing_task import WritingTask
        result = await self.db.execute(
            select(WritingTask).where(WritingTask.uuid == task_uuid).limit(1)
        )
        task = result.scalar_one_or_none()
        if not task:
            return

        checkpoint = WritingCheckpoint(
            task_id=task.id,
            last_completed_unit=last_unit,
            last_completed_scene_id=last_scene_id,
            last_operation=operation,
            agent_states={}
        )
        self.db.add(checkpoint)
        await self.db.commit()

        self.logger.info(f"检查点已保存: 单元 {last_unit}, 操作 {operation}")

    # ==================== 人物状态追踪方法 ====================

    async def _initialize_character_tracker(
        self,
        project_id: int,
        character_profiles: List[Dict[str, Any]],
        world_settings: Optional[Dict[str, Any]] = None,
        persist_dir: Optional[str] = None
    ) -> None:
        """初始化人物状态追踪器

        在任务开始时调用，加载初始人物设定和已有的追踪状态。
        支持从知识图谱同步已有的人物状态实体。

        Args:
            project_id: 项目ID
            character_profiles: 初始人物设定列表
            world_settings: 世界观设定
            persist_dir: 持久化目录（默认使用 ./data/character_states）
        """
        try:
            from app.core.config import get_settings
            from app.agents.writing.character_state_tracker import CharacterStateTracker
            from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
            from app.tools.novel_graph_rag import NovelKnowledgeGraph

            # 设置默认持久化目录
            if persist_dir is None:
                settings = get_settings()
                persist_dir = os.path.join(
                    settings.CHROMA_PERSIST_DIR.replace("/chroma", ""),
                    "character_states"
                )
                os.makedirs(persist_dir, exist_ok=True)

            self._character_tracker = CharacterStateTracker(
                project_id=project_id,
                persist_dir=persist_dir
            )

            # 尝试加载已有状态
            loaded = await self._character_tracker.load()
            if not loaded:
                # 没有已有状态，初始化新状态
                await self._character_tracker.initialize(
                    character_profiles=character_profiles,
                    world_settings=world_settings
                )

            # 初始化项目知识库管理器
            self._project_knowledge_base = ProjectKnowledgeBase(db=self.db)

            # 从全局知识图谱同步人物状态
            try:
                global_graph_path = self._project_knowledge_base.get_graph_path(
                    project_id, unit_number=None)
                if os.path.exists(global_graph_path):
                    global_graph = NovelKnowledgeGraph(
                        persist_path=global_graph_path)
                    if global_graph.load():
                        self._character_tracker.sync_from_knowledge_graph(
                            global_graph)
                        self.logger.info(f"从全局图谱同步人物状态完成")
            except Exception as kg_error:
                self.logger.warning(f"从知识图谱同步人物状态失败: {kg_error}")

            # 【新增】将初始人物设定导出到全局知识图谱
            try:
                global_graph_path = self._project_knowledge_base.get_graph_path(
                    project_id, unit_number=None)
                # 确保目录存在
                graph_dir = os.path.dirname(global_graph_path)
                if graph_dir and not os.path.exists(graph_dir):
                    os.makedirs(graph_dir, exist_ok=True)

                global_graph = NovelKnowledgeGraph(
                    persist_path=global_graph_path)
                global_graph.load()

                # 导出人物设定到全局图谱
                self._character_tracker.export_character_profiles_to_knowledge_graph(
                    global_graph, character_profiles)

                self.logger.info(f"人物设定已导出到全局知识图谱")
            except Exception as export_error:
                self.logger.warning(f"导出人物设定到全局图谱失败: {export_error}")

            self.logger.info(f"人物状态追踪器初始化完成，项目ID: {project_id}")

        except Exception as e:
            self.logger.warning(f"初始化人物状态追踪器失败: {e}")
            self._character_tracker = None

    async def _get_llm_provider_for_extraction(self) -> Optional[Any]:
        """获取用于人物状态提取的LLM Provider

        创建一个专门用于人物状态提取的LLM Provider实例。
        使用配置中的WRITER角色模型，因为提取任务需要较强的理解能力。

        Returns:
            LLM Provider实例，如果创建失败返回None
        """
        try:
            from app.agents.writing.base_agent import AgentRole
            from app.agents.llm_manager import get_llm_manager
            from app.core.config import PRESET_MODELS, get_settings

            # 优先使用WRITER角色的模型配置
            if hasattr(self, 'config') and self.config:
                writer_config = self.config.get_config(AgentRole.WRITER)
                if writer_config:
                    provider_name = writer_config.provider
                    model_id = writer_config.model_id
                    api_base = writer_config.api_base
                    api_key = writer_config.api_key

                    # 如果有完整的API配置，创建provider
                    if provider_name and model_id:
                        provider = await self._get_provider(
                            provider_name=provider_name,
                            model_id=model_id,
                            api_base=api_base,
                            api_key=api_key
                        )
                        self.logger.info(
                            f"创建人物状态提取LLM Provider: provider={provider_name}, model={model_id}"
                        )
                        return provider

            # 回退：尝试使用系统默认provider
            llm_manager = get_llm_manager()
            default_providers = ["siliconflow", "t8star", "qianwen", "doubao"]

            for provider_name in default_providers:
                try:
                    provider = llm_manager.get_default_provider(provider_name)
                    if provider:
                        self.logger.info(
                            f"使用系统默认Provider进行人物状态提取: {provider_name}"
                        )
                        return provider
                except Exception:
                    continue

            self.logger.warning("无法获取LLM Provider，人物状态提取将使用规则回退方案")
            return None

        except Exception as e:
            self.logger.warning(f"创建LLM Provider失败: {e}")
            return None

    async def _update_character_states(
        self,
        chapter_num: int,
        chapter_title: str,
        content: str,
        character_updates: Optional[List[Dict[str, Any]]] = None,
        new_characters: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[int] = None,
        llm_provider=None
    ) -> None:
        """更新人物状态追踪

        在单元完成后调用，记录本章人物状态变化，并同步到知识图谱。

        **修复说明**：现在会自动创建LLM Provider进行人物状态提取，
        不再依赖外部传入的llm_provider参数。

        Args:
            chapter_num: 章节/单元号
            chapter_title: 章节标题
            content: 章节内容
            character_updates: 人物状态更新列表（来自逻辑编辑Agent）
            new_characters: 新人物列表（来自逻辑编辑Agent）
            project_id: 项目ID（用于知识图谱集成）
            llm_provider: LLM提供者（可选，如不传入则自动创建）
        """
        if not self._character_tracker:
            return

        try:
            # ===== 核心修复：如果未传入llm_provider，自动创建 =====
            if llm_provider is None:
                llm_provider = await self._get_llm_provider_for_extraction()
                if llm_provider:
                    self.logger.info(
                        f"章节{chapter_num}: 已自动创建LLM Provider用于人物状态提取")
                else:
                    self.logger.warning(
                        f"章节{chapter_num}: 无法创建LLM Provider，将使用规则回退方案")

            # 将更新数据转换为字典格式
            character_updates_dict = {}
            if character_updates:
                for update in character_updates:
                    char_name = update.get("character")
                    if char_name:
                        character_updates_dict[char_name] = update.get(
                            "updates", {})

            # 记录章节快照
            snapshot = self._character_tracker.record_chapter_snapshot(
                chapter_num=chapter_num,
                chapter_title=chapter_title,
                content=content,
                character_updates=character_updates_dict
            )

            # 添加新人物
            if new_characters:
                for new_char in new_characters:
                    name = new_char.get("name")
                    if name:
                        self._character_tracker.update_character_state(
                            name=name,
                            updates={
                                "identity": new_char.get("identity", ""),
                                "location": new_char.get("initial_location", new_char.get("location", "")),
                                "status_change": "首次出场",
                                "attributes": new_char.get("attributes", {})
                            },
                            chapter_num=chapter_num
                        )

            # ===== 架构优化新增：检测并处理新人物 =====
            # 检测内容中新出现的人物
            detected_new_chars = self._character_tracker.detect_new_characters(
                content)

            if detected_new_chars and llm_provider:
                # 使用LLM验证新人物
                try:
                    verified_chars = await self._character_tracker.verify_new_characters_with_llm(
                        character_names=detected_new_chars,
                        content=content,
                        llm_provider=llm_provider
                    )
                    self.logger.info(
                        f"LLM验证新人物: 检测{len(detected_new_chars)}个, 确认{len(verified_chars)}个")
                except Exception as e:
                    self.logger.warning(f"LLM验证新人物失败: {e}")
                    verified_chars = detected_new_chars

                # 为确认的新人物生成设定
                for char_name in verified_chars:
                    if char_name not in self._character_tracker._character_states:
                        try:
                            profile = await self._character_tracker.generate_profile_for_new_character(
                                char_name=char_name,
                                content=content,
                                chapter_num=chapter_num,
                                llm_provider=llm_provider
                            )
                            if profile:
                                self.logger.info(f"为新人物生成设定: {char_name}")
                        except Exception as e:
                            self.logger.warning(f"生成新人物设定失败 {char_name}: {e}")

            # 保存追踪器状态
            await self._character_tracker.save()

            # ===== 确保人物状态提取并保存到知识图谱 =====
            if project_id and self._project_knowledge_base:
                try:
                    import os
                    from app.tools.novel_graph_rag import NovelKnowledgeGraph, NovelEntityExtractor

                    # 1. 使用LLM提取人物状态实体（核心修复点）
                    if llm_provider:
                        try:
                            # 创建人物状态提取器
                            extractor = NovelEntityExtractor(
                                llm_provider=llm_provider)

                            # 【修复】只获取本章实际出场的人物，而非所有已知人物
                            # 这样可以避免LLM为未出场人物幻觉生成状态
                            present_characters = self._character_tracker._detect_present_characters(
                                content)
                            # 同时获取新检测的人物（如果有的话）
                            newly_detected = self._character_tracker.detect_new_characters(
                                content)
                            # 合并：实际出场人物 + 新检测人物
                            characters_to_extract = list(
                                set(present_characters) | set(newly_detected))

                            self.logger.info(
                                f"章节{chapter_num} 实际出场人物: {characters_to_extract}")

                            # 使用专用的人物状态提取方法
                            extraction_result = await extractor.extract_character_states(
                                chapter_content=content,
                                chapter_num=chapter_num,
                                known_characters=characters_to_extract  # 只传实际出场人物
                            )

                            if extraction_result:
                                entity_count = len(
                                    extraction_result.get("entities", []))
                                relation_count = len(
                                    extraction_result.get("relations", []))
                                self.logger.info(
                                    f"人物状态实体提取成功: 章节{chapter_num}, "
                                    f"实体数={entity_count}, 关系数={relation_count}")

                                # 直接将提取结果同步到追踪器
                                self._sync_extraction_to_tracker(
                                    extraction_result, chapter_num)
                        except Exception as extract_error:
                            self.logger.warning(f"提取人物状态实体失败: {extract_error}")

                    # 2. 将追踪器状态导出到单元知识图谱
                    unit_graph_path = self._project_knowledge_base.get_graph_path(
                        project_id, chapter_num)

                    # 确保目录存在
                    graph_dir = os.path.dirname(unit_graph_path)
                    if graph_dir and not os.path.exists(graph_dir):
                        os.makedirs(graph_dir, exist_ok=True)
                        self.logger.info(f"创建知识图谱目录: {graph_dir}")

                    unit_graph = NovelKnowledgeGraph(
                        persist_path=unit_graph_path)

                    # 尝试加载已有图谱，失败则创建新图谱
                    loaded = unit_graph.load()
                    if loaded:
                        self.logger.info(
                            f"加载已有单元图谱: 章节{chapter_num}, "
                            f"已有节点={unit_graph.graph.number_of_nodes()}, "
                            f"已有边={unit_graph.graph.number_of_edges()}")
                    else:
                        self.logger.info(f"创建新单元图谱: 章节{chapter_num}")

                    # 先将追踪器基础状态导出到图谱
                    self._character_tracker.export_to_knowledge_graph(
                        unit_graph,
                        chapter_num=chapter_num
                    )

                    # 再直接将LLM提取的所有实体和关系写入图谱（确保完整性）
                    if extraction_result:
                        extracted_entities = extraction_result.get(
                            "entities", [])
                        extracted_relations = extraction_result.get(
                            "relations", [])
                        for entity in extracted_entities:
                            unit_graph.add_entity(
                                entity, doc_id=f"chapter_{chapter_num}")
                        for relation in extracted_relations:
                            unit_graph.add_relation(
                                relation, doc_id=f"chapter_{chapter_num}")
                        self.logger.info(
                            f"LLM提取结果已直接写入图谱: 章节{chapter_num}, "
                            f"实体数={len(extracted_entities)}, 关系数={len(extracted_relations)}")

                    save_success = unit_graph.save()

                    if save_success:
                        self.logger.info(
                            f"人物状态已同步到知识图谱: 章节{chapter_num}, "
                            f"节点数={unit_graph.graph.number_of_nodes()}, "
                            f"边数={unit_graph.graph.number_of_edges()}, "
                            f"路径={unit_graph_path}")

                        # ===== 【新增】同步单元图谱到全局知识图谱 =====
                        # 实现正文优先原则：以正文内容为准更新全局图谱
                        try:
                            global_graph_path = self._project_knowledge_base.get_graph_path(
                                project_id, unit_number=None)
                            global_graph = NovelKnowledgeGraph(
                                persist_path=global_graph_path)
                            global_graph.load()

                            sync_result = self._character_tracker.sync_unit_to_global_graph(
                                global_graph=global_graph,
                                unit_graph=unit_graph,
                                chapter_num=chapter_num,
                                sync_extended_entities=True  # 同步扩展实体
                            )

                            # 记录同步结果
                            if sync_result.get("new_entities"):
                                self.logger.info(
                                    f"检测到新实体: 章节{chapter_num}, "
                                    f"新实体={[e['text'] for e in sync_result['new_entities'][:5]]}")

                            if sync_result.get("conflicts"):
                                self.logger.info(
                                    f"全局图谱同步完成: 章节{chapter_num}, "
                                    f"冲突检测={len(sync_result['conflicts'])}个, "
                                    f"设定更新={sync_result['profiles_updated']}个")

                            # 记录扩展实体同步统计
                            extended_stats = sync_result.get(
                                "extended_entities_synced", {})
                            if any(v > 0 for v in extended_stats.values()):
                                self.logger.info(
                                    f"扩展实体同步统计: 设施={extended_stats.get('facilities', 0)}, "
                                    f"事件={extended_stats.get('events', 0)}, "
                                    f"群体={extended_stats.get('groups', 0)}, "
                                    f"道具={extended_stats.get('items', 0)}, "
                                    f"伏笔={extended_stats.get('foreshadows', 0)}")

                        except Exception as global_sync_error:
                            self.logger.warning(
                                f"同步到全局图谱失败: {global_sync_error}")

                        # ===== 【v3.0.1优化】增量更新上下文累积器 =====
                        if self._context_accumulator is not None:
                            try:
                                self._context_accumulator.update_from_graph(
                                    unit_graph, chapter_num)
                                # 使全局图谱缓存失效，确保下次获取最新数据
                                if self._graph_cache:
                                    self._graph_cache.invalidate(
                                        global_graph_path)
                                self.logger.debug(
                                    f"[优化] 累积器增量更新完成: 章节{chapter_num}")
                            except Exception as acc_error:
                                self.logger.debug(f"累积器更新失败: {acc_error}")
                    else:
                        self.logger.warning(
                            f"知识图谱保存失败: 章节{chapter_num}, 路径={unit_graph_path}")

                except Exception as kg_error:
                    self.logger.warning(f"同步人物状态到知识图谱失败: {kg_error}")

            self.logger.info(
                f"人物状态已更新: 第{chapter_num}章, "
                f"{len(snapshot.characters)}个出场人物, "
                f"{len(new_characters or [])}个新人物"
            )

            # ===== 提取扩展实体（设施、事件、群体、道具、世界规则、时间线、伏笔）=====
            if project_id:
                try:
                    extended_result = await self._sync_extended_states_to_knowledge_graph(
                        chapter_num=chapter_num,
                        content=content,
                        project_id=project_id,
                        llm_provider=llm_provider
                    )
                    if extended_result.get("success"):
                        self.logger.info(
                            f"扩展实体提取完成: 章节{chapter_num}, "
                            f"设施={extended_result['facilities']}, "
                            f"事件={extended_result['events']}, "
                            f"群体={extended_result['groups']}, "
                            f"道具={extended_result['items']}, "
                            f"伏笔={extended_result['foreshadows']}"
                        )
                except Exception as extended_error:
                    self.logger.warning(f"扩展实体提取失败: {extended_error}")

        except Exception as e:
            self.logger.warning(f"更新人物状态追踪失败: {e}")

    def _sync_extraction_to_tracker(
        self,
        extraction_result: Dict[str, Any],
        chapter_num: int
    ) -> None:
        """将人物状态提取结果同步到追踪器

        将NovelEntityExtractor.extract_character_states的结果
        同步到CharacterStateTracker中。

        Args:
            extraction_result: 提取结果，包含entities和relations
            chapter_num: 章节号
        """
        try:
            entities = extraction_result.get("entities", [])

            for entity in entities:
                entity_type = entity.get("type", "")
                character = entity.get("character", "")
                text = entity.get("text", "")
                description = entity.get("description", "")

                if not character:
                    continue

                # 根据实体类型更新人物状态
                if entity_type == "身份变化":
                    self._character_tracker.update_character_state(
                        character,
                        {
                            "identity": text,
                            "status_change": description
                        },
                        chapter_num=chapter_num
                    )
                elif entity_type == "位置变化":
                    self._character_tracker.update_character_state(
                        character,
                        {"location": text},
                        chapter_num=chapter_num
                    )
                elif entity_type == "关系变化":
                    # 关系变化存储在attributes中
                    existing_state = self._character_tracker.get_character_state(
                        character)
                    if existing_state:
                        relationships = existing_state.relationships.copy()
                        relationships[text] = description
                        self._character_tracker.update_character_state(
                            character,
                            {"relationships": relationships},
                            chapter_num=chapter_num
                        )
                elif entity_type in ["性格发展", "心理状态", "能力成长", "行为模式"]:
                    # 这些状态存储在attributes中
                    self._character_tracker.update_character_state(
                        character,
                        {"attributes": {entity_type.lower(): description}},
                        chapter_num=chapter_num
                    )

            self.logger.debug(
                f"同步提取结果到追踪器完成: 章节{chapter_num}, "
                f"处理了{len(entities)}个实体"
            )

        except Exception as e:
            self.logger.warning(f"同步提取结果失败: {e}")

    # ==================== 扩展实体同步方法 ====================

    async def _sync_extended_states_to_knowledge_graph(
        self,
        chapter_num: int,
        content: str,
        project_id: int,
        llm_provider=None
    ) -> Dict[str, Any]:
        """
        同步扩展状态实体到知识图谱

        提取并同步设施、事件、群体、道具、世界规则、时间线、伏笔等
        扩展实体到单元知识图谱。

        Args:
            chapter_num: 章节号
            content: 章节内容
            project_id: 项目ID
            llm_provider: LLM提供者（可选）

        Returns:
            同步结果摘要
        """
        result = {
            "chapter": chapter_num,
            "facilities": 0,
            "events": 0,
            "groups": 0,
            "items": 0,
            "foreshadows": 0,
            "total_entities": 0,
            "total_relations": 0,
            "success": False
        }

        if not self._project_knowledge_base:
            self.logger.warning("项目知识库未初始化，跳过扩展状态同步")
            return result

        try:
            from app.tools.novel_graph_rag import NovelKnowledgeGraph, NovelEntityExtractor
            import os

            # 获取LLM Provider
            if llm_provider is None:
                llm_provider = await self._get_llm_provider_for_extraction()

            if not llm_provider:
                self.logger.warning(
                    f"章节{chapter_num}: 无法获取LLM Provider，跳过扩展状态提取")
                return result

            # 创建提取器
            extractor = NovelEntityExtractor(llm_provider=llm_provider)

            # 获取上下文信息（已知的实体列表）
            context_info = await self._get_extended_context_info(project_id, chapter_num)

            # 提取扩展状态实体
            extraction_result = await extractor.extract_extended_states(
                chapter_content=content,
                chapter_num=chapter_num,
                context_info=context_info
            )

            if not extraction_result or extraction_result.get("_extraction_failed"):
                self.logger.warning(f"章节{chapter_num}: 扩展状态提取失败")
                return result

            # 获取单元知识图谱路径
            unit_graph_path = self._project_knowledge_base.get_graph_path(
                project_id, chapter_num)

            # 确保目录存在
            graph_dir = os.path.dirname(unit_graph_path)
            if graph_dir and not os.path.exists(graph_dir):
                os.makedirs(graph_dir, exist_ok=True)

            # 加载或创建知识图谱
            unit_graph = NovelKnowledgeGraph(persist_path=unit_graph_path)
            unit_graph.load()

            # 添加实体到图谱
            entities = extraction_result.get("entities", [])
            relations = extraction_result.get("relations", [])

            for entity in entities:
                unit_graph.add_entity(entity, doc_id=f"chapter_{chapter_num}")

            for relation in relations:
                unit_graph.add_relation(
                    relation, doc_id=f"chapter_{chapter_num}")

            # 保存图谱
            save_success = unit_graph.save()

            if save_success:
                # 统计各类实体
                for entity in entities:
                    entity_type = entity.get("type", "")
                    if entity_type in ["设施", "设施状态变化", "设施归属变更", "设施物理状态"]:
                        result["facilities"] += 1
                    elif entity_type in ["事件", "事件状态变化", "事件影响", "事件因果链"]:
                        result["events"] += 1
                    elif entity_type in ["群体组织", "群体状态变化", "群体成员变动", "群体关系变化"]:
                        result["groups"] += 1
                    elif entity_type in ["道具物品", "道具状态变化", "道具归属变更", "道具功能使用"]:
                        result["items"] += 1
                    elif entity_type in ["伏笔", "伏笔回收"]:
                        result["foreshadows"] += 1

                result["total_entities"] = len(entities)
                result["total_relations"] = len(relations)
                result["success"] = True

                self.logger.info(
                    f"扩展状态同步完成: 章节{chapter_num}, "
                    f"设施={result['facilities']}, 事件={result['events']}, "
                    f"群体={result['groups']}, 道具={result['items']}, "
                    f"伏笔={result['foreshadows']}, "
                    f"总实体={result['total_entities']}, 总关系={result['total_relations']}")

                # ===== 【新增】同步扩展实体到全局知识图谱 =====
                # 确保新出现的扩展实体也同步到全局图谱，保持知识体系完整
                try:
                    global_sync_result = await self._project_knowledge_base.sync_unit_entities_to_global(
                        project_id=project_id,
                        unit_number=chapter_num,
                        character_tracker=self._character_tracker
                    )
                    if global_sync_result.get("success"):
                        new_entities = global_sync_result.get(
                            "new_entities", [])
                        if new_entities:
                            self.logger.info(
                                f"扩展实体同步到全局图谱: 章节{chapter_num}, "
                                f"新实体={[e['text'] for e in new_entities[:5]]}"
                            )
                except Exception as global_sync_error:
                    self.logger.warning(
                        f"扩展实体同步到全局图谱失败: {global_sync_error}")

            else:
                self.logger.warning(f"扩展状态图谱保存失败: 章节{chapter_num}")

        except Exception as e:
            self.logger.warning(f"同步扩展状态失败: {e}")

        return result

    async def _get_extended_context_info(
        self,
        project_id: int,
        current_chapter: int
    ) -> Dict[str, Any]:
        """
        获取扩展实体的上下文信息（v3.0.1优化版）

        优化策略：
        1. 优先从累积器获取（O(1)时间复杂度）
        2. 累积器未初始化时从全局图谱同步
        3. 避免每次遍历所有前文章节图谱

        Args:
            project_id: 项目ID
            current_chapter: 当前章节号

        Returns:
            上下文信息字典
        """
        # 优化：使用累积器直接返回，避免重复遍历
        if self._context_accumulator is not None:
            context_info = self._context_accumulator.to_dict()
            self.logger.debug(
                f"[优化] 从累积器获取上下文: 设施={len(context_info['known_facilities'])}, "
                f"群体={len(context_info['known_groups'])}, "
                f"道具={len(context_info['known_items'])}, "
                f"事件={len(context_info['unfinished_events'])}, "
                f"伏笔={len(context_info['pending_foreshadows'])}"
            )
            return context_info

        # 累积器未初始化，从全局图谱同步
        context_info = {
            "known_facilities": [],
            "known_groups": [],
            "known_items": [],
            "unfinished_events": [],
            "pending_foreshadows": []
        }

        try:
            # 初始化缓存和累积器
            if self._graph_cache is None:
                self._graph_cache = GraphCache(max_unit_cache_size=30)
            if self._context_accumulator is None:
                self._context_accumulator = ExtendedContextAccumulator()

            # 从全局图谱获取所有扩展实体（O(1)操作）
            global_graph_path = self._project_knowledge_base.get_graph_path(
                project_id, unit_number=None)

            if os.path.exists(global_graph_path):
                global_graph = self._graph_cache.get_or_load(
                    global_graph_path, is_global=True)

                if global_graph:
                    # 从全局图谱同步到累积器
                    self._context_accumulator.sync_from_global_graph(
                        global_graph)
                    context_info = self._context_accumulator.to_dict()

                    self.logger.info(
                        f"[优化] 从全局图谱同步上下文完成: 设施={len(context_info['known_facilities'])}, "
                        f"群体={len(context_info['known_groups'])}, "
                        f"道具={len(context_info['known_items'])}"
                    )
            else:
                self.logger.debug(f"全局图谱不存在，返回空上下文: 项目{project_id}")

        except Exception as e:
            self.logger.warning(f"获取扩展上下文信息失败: {e}")

        return context_info

    def get_character_tracker(self):
        """获取人物状态追踪器实例

        Returns:
            CharacterStateTracker: 追踪器实例，如果未初始化则返回None
        """
        return self._character_tracker
