"""
monitoring/_character_tracker.py - 人物状态追踪 Mixin

包含 MonitoringCharacterMixin，提供人物状态追踪器初始化和更新方法。

@date: 2026-04-24
@version: v3.0.0
"""
import os
from typing import Any, Dict, List, Optional


class MonitoringCharacterMixin:
    """人物状态追踪 Mixin

    提供：
    - _initialize_character_tracker: 初始化人物状态追踪器
    - _update_character_states: 更新人物状态追踪
    - _sync_extraction_to_tracker: 将提取结果同步到追踪器
    """

    # 由主类提供的属性
    db: Any
    logger: Any
    _character_tracker: Optional[Any]
    _project_knowledge_base: Optional[Any]
    _graph_cache: Optional[Any] = None
    _context_accumulator: Optional[Any] = None

    # 从其他 Mixin 继承的方法
    _get_llm_provider_for_extraction: callable
    _sync_extended_states_to_knowledge_graph: callable

    async def _initialize_character_tracker(
        self,
        project_id: int,
        character_profiles: List[Dict[str, Any]],
        world_settings: Optional[Dict[str, Any]] = None,
        persist_dir: Optional[str] = None,
        narrative_mode: str = "serialized"
    ) -> None:
        """初始化人物状态追踪器

        Args:
            project_id: 项目ID
            character_profiles: 角色设定列表
            world_settings: 世界观设定
            persist_dir: 持久化目录
            narrative_mode: 叙事模式（serialized=连续剧，episodic=纯单元剧，episodic_with_arc=主线串联单元剧）
        """
        _is_pure_episodic = narrative_mode == "episodic"

        # 纯单元剧模式：轻量初始化，仅记录角色基础设定，不追踪状态变化
        if _is_pure_episodic:
            try:
                from app.agents.writing.character_state_tracker import CharacterStateTracker

                if persist_dir is None:
                    from app.core.config import get_settings
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
                # 轻量初始化：仅注册角色名称和基础身份，不启动状态追踪
                await self._character_tracker.initialize(
                    character_profiles=character_profiles,
                    world_settings=world_settings
                )
                self.logger.info(
                    f"[纯单元剧] 人物追踪器轻量初始化完成（仅记录角色设定，不追踪状态变化），"
                    f"项目ID: {project_id}，角色数: {len(character_profiles)}"
                )
            except Exception as e:
                self.logger.warning(f"[纯单元剧] 轻量初始化人物追踪器失败: {e}")
                self._character_tracker = None
            return

        try:
            from app.core.config import get_settings
            from app.agents.writing.character_state_tracker import CharacterStateTracker
            from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
            from app.tools.novel_graph_rag import NovelKnowledgeGraph

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

            loaded = await self._character_tracker.load()
            if loaded:
                char_count = len(self._character_tracker._character_states)
                snapshot_count = len(self._character_tracker._chapter_snapshots)
                rel_count = len(self._character_tracker._relationship_history)
                foreshadowing_count = len(getattr(self._character_tracker, '_foreshadowing_items', {}))
                self.logger.info(
                    f"[持久化恢复] 从持久化恢复追踪器状态: "
                    f"{char_count}个角色, {snapshot_count}个章节快照, "
                    f"{rel_count}个关系变化"
                    + (f", {foreshadowing_count}个伏笔" if foreshadowing_count > 0 else "")
                )
            else:
                await self._character_tracker.initialize(
                    character_profiles=character_profiles,
                    world_settings=world_settings
                )

                # 主线串联单元剧模式：标记"仅追踪常驻角色"
                if narrative_mode == "episodic_with_arc":
                    self.logger.info(
                        f"[主线串联单元剧] 完整初始化人物追踪器，仅追踪常驻角色，"
                        f"项目ID: {project_id}，角色数: {len(character_profiles)}"
                    )

            self._project_knowledge_base = ProjectKnowledgeBase(db=self.db)

            try:
                global_graph_path = self._project_knowledge_base.get_graph_path(
                    project_id, unit_number=None)
                if os.path.exists(global_graph_path):
                    global_graph = NovelKnowledgeGraph(persist_path=global_graph_path)
                    if global_graph.load():
                        self._character_tracker.sync_from_knowledge_graph(global_graph)
                        self.logger.info(f"从全局图谱同步人物状态完成")
            except Exception as kg_error:
                self.logger.warning(f"从知识图谱同步人物状态失败: {kg_error}")

            try:
                global_graph_path = self._project_knowledge_base.get_graph_path(
                    project_id, unit_number=None)
                graph_dir = os.path.dirname(global_graph_path)
                if graph_dir and not os.path.exists(graph_dir):
                    os.makedirs(graph_dir, exist_ok=True)

                global_graph = NovelKnowledgeGraph(persist_path=global_graph_path)
                global_graph.load()
                self._character_tracker.export_character_profiles_to_knowledge_graph(
                    global_graph, character_profiles)
                self.logger.info(f"人物设定已导出到全局知识图谱")
            except Exception as export_error:
                self.logger.warning(f"导出人物设定到全局图谱失败: {export_error}")

            self.logger.info(f"人物状态追踪器初始化完成，项目ID: {project_id}")

        except Exception as e:
            self.logger.warning(f"初始化人物状态追踪器失败: {e}")
            self._character_tracker = None

    async def _update_character_states(
        self,
        chapter_num: int,
        chapter_title: str,
        content: str,
        character_updates: Optional[List[Dict[str, Any]]] = None,
        new_characters: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[int] = None,
        llm_provider=None,
        narrative_mode: str = "serialized"
    ) -> None:
        """更新人物状态追踪

        Args:
            narrative_mode: 叙事模式（纯单元剧时跳过状态更新，防御性二次检查）
        """
        if not self._character_tracker:
            return

        # 纯单元剧模式：防御性跳过（上游 _unit_direct.py 已做判断，此处二次保障）
        if narrative_mode == "episodic":
            self.logger.debug(f"[纯单元剧] 跳过人物状态更新: 章节{chapter_num}")
            return

        # 初始化 extraction_result，避免后续访问未定义变量
        extraction_result = None

        try:
            if llm_provider is None:
                llm_provider = await self._get_llm_provider_for_extraction()
                if llm_provider:
                    self.logger.info(f"章节{chapter_num}: 已自动创建LLM Provider用于人物状态提取")
                else:
                    self.logger.warning(f"章节{chapter_num}: 无法创建LLM Provider，将使用规则回退方案")

            character_updates_dict = {}
            if character_updates:
                for update in character_updates:
                    char_name = update.get("character")
                    if char_name:
                        character_updates_dict[char_name] = update.get("updates", {})

            snapshot = self._character_tracker.record_chapter_snapshot(
                chapter_num=chapter_num,
                chapter_title=chapter_title,
                content=content,
                character_updates=character_updates_dict
            )

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

            detected_new_chars = self._character_tracker.detect_new_characters(content)
            if detected_new_chars and llm_provider:
                try:
                    verified_chars = await self._character_tracker.verify_new_characters_with_llm(
                        character_names=detected_new_chars,
                        content=content,
                        llm_provider=llm_provider
                    )
                    self.logger.info(f"LLM验证新人物: 检测{len(detected_new_chars)}个, 确认{len(verified_chars)}个")
                except Exception as e:
                    self.logger.warning(f"LLM验证新人物失败: {e}")
                    verified_chars = detected_new_chars

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

            await self._character_tracker.save()

            if project_id and self._project_knowledge_base:
                try:
                    from app.tools.novel_graph_rag import NovelKnowledgeGraph, NovelEntityExtractor

                    if llm_provider:
                        try:
                            extractor = NovelEntityExtractor(llm_provider=llm_provider)
                            present_characters = self._character_tracker._detect_present_characters(content)
                            newly_detected = self._character_tracker.detect_new_characters(content)
                            characters_to_extract = list(set(present_characters) | set(newly_detected))

                            self.logger.info(f"章节{chapter_num} 实际出场人物: {characters_to_extract}")

                            extraction_result = await extractor.extract_character_states(
                                chapter_content=content,
                                chapter_num=chapter_num,
                                known_characters=characters_to_extract
                            )

                            if extraction_result:
                                entity_count = len(extraction_result.get("entities", []))
                                relation_count = len(extraction_result.get("relations", []))
                                self.logger.info(f"人物状态实体提取成功: 章节{chapter_num}, 实体数={entity_count}, 关系数={relation_count}")
                                self._sync_extraction_to_tracker(extraction_result, chapter_num)
                        except Exception as extract_error:
                            self.logger.warning(f"提取人物状态实体失败: {extract_error}")

                    unit_graph_path = self._project_knowledge_base.get_graph_path(project_id, chapter_num)
                    graph_dir = os.path.dirname(unit_graph_path)
                    if graph_dir and not os.path.exists(graph_dir):
                        os.makedirs(graph_dir, exist_ok=True)
                        self.logger.info(f"创建知识图谱目录: {graph_dir}")

                    unit_graph = NovelKnowledgeGraph(persist_path=unit_graph_path)
                    loaded = unit_graph.load()
                    if loaded:
                        self.logger.info(f"加载已有单元图谱: 章节{chapter_num}, 已有节点={unit_graph.graph.number_of_nodes()}, 已有边={unit_graph.graph.number_of_edges()}")
                    else:
                        self.logger.info(f"创建新单元图谱: 章节{chapter_num}")

                    self._character_tracker.export_to_knowledge_graph(unit_graph, chapter_num=chapter_num)

                    if extraction_result:
                        extracted_entities = extraction_result.get("entities", [])
                        extracted_relations = extraction_result.get("relations", [])
                        for entity in extracted_entities:
                            unit_graph.add_entity(entity, doc_id=f"chapter_{chapter_num}")
                        for relation in extracted_relations:
                            unit_graph.add_relation(relation, doc_id=f"chapter_{chapter_num}")

                    save_success = unit_graph.save()

                    if save_success:
                        self.logger.info(f"人物状态已同步到知识图谱: 章节{chapter_num}, 节点数={unit_graph.graph.number_of_nodes()}, 边数={unit_graph.graph.number_of_edges()}")

                        # 🆕 [知识图谱优化 v3.1] 禁用单元图谱同步到全局图谱
                        # 原因: 持续同步导致全局图谱无限膨胀 (100章可达3550实体)
                        # 优化: 全局图谱仅保留全局大纲实体 (~50个),跨章检索通过向量库实现
                        try:
                            self.logger.info(
                                f"[知识图谱优化] 跳过单元图谱同步到全局图谱: 章节{chapter_num}, "
                                f"单元图谱节点={unit_graph.graph.number_of_nodes()}, "
                                f"边={unit_graph.graph.number_of_edges()}"
                            )
                            self.logger.info(
                                f"[知识图谱优化] 全局图谱将仅保留全局大纲实体,跨章检索通过向量库实现"
                            )
                            
                            # 保留人物设定更新 (仅同步人物状态变化,不同步所有实体)
                            try:
                                global_graph_path = self._project_knowledge_base.get_graph_path(project_id, unit_number=None)
                                global_graph = NovelKnowledgeGraph(persist_path=global_graph_path)
                                global_graph.load()
                                
                                # 仅更新人物设定到全局图谱
                                # get_all_characters()返回Dict[str, CharacterState]，需要转换为列表格式
                                all_chars = self._character_tracker.get_all_characters()
                                character_profiles_list = [
                                    {
                                        "name": name,
                                        "identity": state.identity,
                                        "location": state.location,
                                        **state.attributes
                                    }
                                    for name, state in all_chars.items()
                                ]
                                self._character_tracker.export_character_profiles_to_knowledge_graph(
                                    global_graph, 
                                    character_profiles_list
                                )
                                global_graph.save()
                                self.logger.info(
                                    f"[知识图谱优化] 仅更新人物设定到全局图谱: "
                                    f"章节{chapter_num}, 人物数={len(self._character_tracker.get_all_characters())}"
                                )
                            except Exception as profile_update_error:
                                self.logger.warning(f"[知识图谱优化] 更新人物设定失败: {profile_update_error}")

                        except Exception as global_sync_error:
                            self.logger.warning(f"[知识图谱优化] 跳过同步失败: {global_sync_error}")

                        if self._context_accumulator is not None:
                            try:
                                self._context_accumulator.update_from_graph(unit_graph, chapter_num)
                                if self._graph_cache:
                                    self._graph_cache.invalidate(global_graph_path)
                            except Exception as acc_error:
                                self.logger.debug(f"累积器更新失败: {acc_error}")
                    else:
                        self.logger.warning(f"知识图谱保存失败: 章节{chapter_num}")
                except Exception as kg_error:
                    self.logger.warning(f"同步人物状态到知识图谱失败: {kg_error}")

            self.logger.info(f"人物状态已更新: 第{chapter_num}章, {len(snapshot.characters)}个出场人物, {len(new_characters or [])}个新人物")

            if project_id:
                try:
                    extended_result = await self._sync_extended_states_to_knowledge_graph(
                        chapter_num=chapter_num,
                        content=content,
                        project_id=project_id,
                        llm_provider=llm_provider,
                        narrative_mode=narrative_mode
                    )
                    if extended_result.get("success"):
                        self.logger.info(f"扩展实体提取完成: 章节{chapter_num}, 设施={extended_result['facilities']}, 事件={extended_result['events']}, 群体={extended_result['groups']}, 道具={extended_result['items']}, 伏笔={extended_result['foreshadows']}")
                except Exception as extended_error:
                    self.logger.warning(f"扩展实体提取失败: {extended_error}")

        except Exception as e:
            self.logger.warning(f"更新人物状态追踪失败: {e}")

    def _sync_extraction_to_tracker(
        self,
        extraction_result: Dict[str, Any],
        chapter_num: int
    ) -> None:
        """将人物状态提取结果同步到追踪器"""
        try:
            entities = extraction_result.get("entities", [])

            for entity in entities:
                entity_type = entity.get("type", "")
                character = entity.get("character", "")
                text = entity.get("text", "")
                description = entity.get("description", "")

                if not character:
                    continue

                if entity_type == "身份变化":
                    self._character_tracker.update_character_state(
                        character,
                        {"identity": text, "status_change": description},
                        chapter_num=chapter_num
                    )
                elif entity_type == "位置变化":
                    self._character_tracker.update_character_state(
                        character,
                        {"location": text},
                        chapter_num=chapter_num
                    )
                elif entity_type == "关系变化":
                    existing_state = self._character_tracker.get_character_state(character)
                    if existing_state:
                        relationships = existing_state.relationships.copy()
                        relationships[text] = description
                        self._character_tracker.update_character_state(
                            character,
                            {"relationships": relationships},
                            chapter_num=chapter_num
                        )
                elif entity_type in ["性格发展", "心理状态", "能力成长", "行为模式"]:
                    self._character_tracker.update_character_state(
                        character,
                        {"attributes": {entity_type.lower(): description}},
                        chapter_num=chapter_num
                    )

            self.logger.debug(f"同步提取结果到追踪器完成: 章节{chapter_num}, 处理了{len(entities)}个实体")

        except Exception as e:
            self.logger.warning(f"同步提取结果失败: {e}")
