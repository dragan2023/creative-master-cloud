"""
monitoring/_knowledge_graph.py - 知识图谱操作 Mixin

包含 MonitoringKnowledgeGraphMixin，提供知识图谱同步方法。

@date: 2026-04-24
@version: v3.0.0
"""
import json
import os
from typing import Any, Dict, List, Optional

from app.agents.writing.base_agent import AgentRole


class MonitoringKnowledgeGraphMixin:
    """知识图谱操作 Mixin

    提供：
    - _get_llm_provider_for_extraction: 获取用于提取的LLM Provider
    - _sync_extended_states_to_knowledge_graph: 同步扩展状态实体到知识图谱
    - _get_extended_context_info: 获取扩展实体的上下文信息

    注意：
    - _get_provider 方法从父类 BaseWritingAgent 继承，不应在此定义属性覆盖
    """

    # 由主类提供的属性（类型注解，不设置默认值避免覆盖父类方法）
    logger: Any
    _project_knowledge_base: Optional[Any]
    _character_tracker: Optional[Any]
    _graph_cache: Optional[Any] = None
    _context_accumulator: Optional[Any] = None

    # 从主类继承的配置
    config: Optional[Any] = None

    # _get_provider 方法从父类继承，不需要在此定义

    async def _get_llm_provider_for_extraction(self) -> Optional[Any]:
        """获取用于人物状态提取的LLM Provider"""
        try:
            from app.agents.llm_manager import get_llm_manager

            if hasattr(self, 'config') and self.config:
                writer_config = self.config.get_config(AgentRole.WRITER)
                if writer_config:
                    provider_name = writer_config.provider
                    model_id = writer_config.model_id
                    api_base = writer_config.api_base
                    api_key = writer_config.api_key

                    if provider_name and model_id and self._get_provider:
                        provider = await self._get_provider(
                            provider_name=provider_name,
                            model_id=model_id,
                            api_base=api_base,
                            api_key=api_key
                        )
                        self.logger.info(f"创建人物状态提取LLM Provider: provider={provider_name}, model={model_id}")
                        return provider

            llm_manager = get_llm_manager()
            default_providers = ["siliconflow", "t8star", "qianwen", "doubao"]

            for provider_name in default_providers:
                try:
                    provider = llm_manager.get_default_provider(provider_name)
                    if provider:
                        self.logger.info(f"使用系统默认Provider进行人物状态提取: {provider_name}")
                        return provider
                except Exception:
                    continue

            self.logger.warning("无法获取LLM Provider，人物状态提取将使用规则回退方案")
            return None

        except Exception as e:
            self.logger.warning(f"创建LLM Provider失败: {e}")
            return None

    async def _sync_extended_states_to_knowledge_graph(
        self,
        chapter_num: int,
        content: str,
        project_id: int,
        llm_provider=None
    ) -> Dict[str, Any]:
        """同步扩展状态实体到知识图谱"""
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

            if llm_provider is None:
                llm_provider = await self._get_llm_provider_for_extraction()

            if not llm_provider:
                self.logger.warning(f"章节{chapter_num}: 无法获取LLM Provider，跳过扩展状态提取")
                return result

            extractor = NovelEntityExtractor(llm_provider=llm_provider)
            context_info = await self._get_extended_context_info(project_id, chapter_num)

            extraction_result = await extractor.extract_extended_states(
                chapter_content=content,
                chapter_num=chapter_num,
                context_info=context_info
            )

            if not extraction_result or extraction_result.get("_extraction_failed"):
                self.logger.warning(f"章节{chapter_num}: 扩展状态提取失败")
                return result

            unit_graph_path = self._project_knowledge_base.get_graph_path(project_id, chapter_num)
            graph_dir = os.path.dirname(unit_graph_path)
            if graph_dir and not os.path.exists(graph_dir):
                os.makedirs(graph_dir, exist_ok=True)

            unit_graph = NovelKnowledgeGraph(persist_path=unit_graph_path)
            unit_graph.load()

            entities = extraction_result.get("entities", [])
            relations = extraction_result.get("relations", [])

            for entity in entities:
                unit_graph.add_entity(entity, doc_id=f"chapter_{chapter_num}")
            for relation in relations:
                unit_graph.add_relation(relation, doc_id=f"chapter_{chapter_num}")

            save_success = unit_graph.save()

            if save_success:
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

                # 🆕 [统一状态存储 v5.0] 维护轻量级一致状态索引
                # 虽然单元实体不再同步到全局图谱（v3.2），但各维度状态需要跨章追踪
                # 此处将所有维度状态变化持久化到 project 目录下的 consistency_state.json
                unified_state = await self._persist_unified_state(
                    project_id=project_id,
                    chapter_num=chapter_num,
                    entities=entities,
                    graph_dir=graph_dir
                )

                # 🆕 [实时推送 v6.0] 将一致性状态变化推送到前端
                if unified_state:
                    try:
                        await self._send_ws_message("consistency_report_update", {
                            "chapter_num": chapter_num,
                            "project_id": project_id,
                            "events": unified_state.get("events", {}),
                            "items": unified_state.get("items", {}),
                            "facilities": unified_state.get("facilities", {}),
                            "groups": unified_state.get("groups", {}),
                            "foreshadows": unified_state.get("foreshadows", {}),
                            "world_rules": unified_state.get("world_rules", {}),
                            "time_context": unified_state.get("time_context", {}),
                        })
                    except Exception as ws_err:
                        self.logger.debug(f"推送一致性报告到前端失败（非关键）: {ws_err}")

                # 🆕 [事件生命周期 v4.0] 更新上下文累积器中的事件状态
                if self._context_accumulator and unit_graph:
                    try:
                        self._context_accumulator.update_from_graph(unit_graph, chapter_num)
                        self.logger.debug(f"事件状态累积器已更新: 章节{chapter_num}")
                    except Exception as acc_err:
                        self.logger.warning(f"更新事件状态累积器失败: {acc_err}")

                # 🆕 [知识图谱优化 v3.2] 彻底禁用单元实体同步到全局图谱
                # 原因：持续同步导致全局图谱无限膨胀（100章可达3550+实体）
                # 优化：全局图谱仅保留全局大纲实体（~50个），跨章检索通过向量库实现
                self.logger.info(
                    f"[知识图谱优化 v3.2] 跳过单元实体同步到全局图谱: 章节{chapter_num}, "
                    f"单元图谱节点={unit_graph.graph.number_of_nodes()}, "
                    f"边={unit_graph.graph.number_of_edges()}"
                )
                self.logger.info(
                    f"[知识图谱优化 v3.2] 全局图谱将仅保留全局大纲实体，跨章检索通过向量库实现"
                )
                
                # 旧代码（已禁用）：
                # try:
                #     global_sync_result = await self._project_knowledge_base.sync_unit_entities_to_global(
                #         project_id=project_id,
                #         unit_number=chapter_num,
                #         character_tracker=self._character_tracker
                #     )
                #     if global_sync_result.get("success"):
                #         new_entities = global_sync_result.get("new_entities", [])
                #         if new_entities:
                #             self.logger.info(f"扩展实体同步到全局图谱: 章节{chapter_num}, 新实体={[e['text'] for e in new_entities[:5]]}")
                # except Exception as global_sync_error:
                #     self.logger.warning(f"扩展实体同步到全局图谱失败: {global_sync_error}")
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
        """获取扩展实体的上下文信息（优化版）"""
        if self._context_accumulator is not None:
            context_info = self._context_accumulator.to_dict()
            self.logger.debug(f"[优化] 从累积器获取上下文: 设施={len(context_info['known_facilities'])}, 群体={len(context_info['known_groups'])}, 道具={len(context_info['known_items'])}, 事件={len(context_info['unfinished_events'])}, 伏笔={len(context_info['pending_foreshadows'])}")
            return context_info

        context_info = {
            "known_facilities": [],
            "known_groups": [],
            "known_items": [],
            "unfinished_events": [],
            "pending_foreshadows": []
        }

        try:
            if self._graph_cache is None:
                from ._graph_cache import GraphCache
                self._graph_cache = GraphCache(max_unit_cache_size=30)
            if self._context_accumulator is None:
                from ._context_accumulator import ExtendedContextAccumulator
                self._context_accumulator = ExtendedContextAccumulator()

            global_graph_path = self._project_knowledge_base.get_graph_path(project_id, unit_number=None)

            if os.path.exists(global_graph_path):
                global_graph = self._graph_cache.get_or_load(global_graph_path, is_global=True)

                if global_graph:
                    self._context_accumulator.sync_from_global_graph(global_graph)
                    context_info = self._context_accumulator.to_dict()
                    self.logger.info(f"[优化] 从全局图谱同步上下文完成: 设施={len(context_info['known_facilities'])}, 群体={len(context_info['known_groups'])}, 道具={len(context_info['known_items'])}")
            else:
                self.logger.debug(f"全局图谱不存在，返回空上下文: 项目{project_id}")

        except Exception as e:
            self.logger.warning(f"获取扩展上下文信息失败: {e}")

        return context_info

    async def _persist_unified_state(
        self,
        project_id: int,
        chapter_num: int,
        entities: List[Dict[str, Any]],
        graph_dir: str
    ) -> None:
        """持久化统一一致性状态

        从每章提取的扩展实体中抽取各维度状态信息，
        合并到轻量级 consistency_state.json 文件中。
        覆盖维度：事件、道具、设施、群体、伏笔、世界规则

        解决 v3.2 优化后单元实体无法跨章追踪的问题。

        Args:
            project_id: 项目ID
            chapter_num: 当前章节号
            entities: 本章提取的实体列表
            graph_dir: 图谱文件目录
        """
        try:
            # 1. 从 entities 中按维度抽取状态信息
            current_updates = {
                "events": {},
                "items": {},
                "facilities": {},
                "groups": {},
                "foreshadows": {},
                "world_rules": {},
                "time_context": {},
            }

            for entity in entities:
                entity_type = entity.get("type", "")
                attrs = entity.get("attributes", {})
                text = entity.get("text", "")

                # --- 事件维度 ---
                if entity_type == "事件":
                    if text:
                        current_updates["events"][text] = {
                            "name": text,
                            "type": attrs.get("事件类型", ""),
                            "status": attrs.get("状态", "进行中"),
                            "first_chapter": chapter_num,
                            "last_update_chapter": chapter_num,
                        }
                elif entity_type == "事件状态变化":
                    event_name = attrs.get("事件名称", "")
                    current_stage = attrs.get("当前阶段", "")
                    if event_name and current_stage:
                        if event_name not in current_updates["events"]:
                            current_updates["events"][event_name] = {
                                "name": event_name, "type": "",
                                "first_chapter": chapter_num,
                            }
                        current_updates["events"][event_name]["status"] = current_stage
                        current_updates["events"][event_name]["last_update_chapter"] = chapter_num

                # --- 道具维度 ---
                elif entity_type == "道具物品":
                    if text:
                        current_updates["items"][text] = {
                            "name": text,
                            "type": attrs.get("物品类型", ""),
                            "status": attrs.get("状态", attrs.get("当前状态", "已知")),
                            "first_chapter": chapter_num,
                            "last_update_chapter": chapter_num,
                        }
                elif entity_type in ("道具状态变化", "道具归属变更", "道具功能使用"):
                    item_name = attrs.get("物品名称", attrs.get("item", ""))
                    new_status = attrs.get("状态类型", attrs.get("新状态", "")) or text
                    if item_name and new_status:
                        if item_name not in current_updates["items"]:
                            current_updates["items"][item_name] = {
                                "name": item_name, "type": "",
                                "first_chapter": chapter_num,
                            }
                        current_updates["items"][item_name]["status"] = new_status
                        current_updates["items"][item_name]["last_update_chapter"] = chapter_num

                # --- 设施维度 ---
                elif entity_type == "设施":
                    if text:
                        current_updates["facilities"][text] = {
                            "name": text,
                            "type": attrs.get("功能类型", ""),
                            "status": attrs.get("状态", attrs.get("当前状态", "正常运营")),
                            "first_chapter": chapter_num,
                            "last_update_chapter": chapter_num,
                        }
                elif entity_type in ("设施状态变化", "设施归属变更", "设施物理状态"):
                    facility_name = attrs.get("设施名称", "")
                    new_status = attrs.get("状态类型", attrs.get("新状态", "")) or text
                    if facility_name and new_status:
                        if facility_name not in current_updates["facilities"]:
                            current_updates["facilities"][facility_name] = {
                                "name": facility_name, "type": "",
                                "first_chapter": chapter_num,
                            }
                        current_updates["facilities"][facility_name]["status"] = new_status
                        current_updates["facilities"][facility_name]["last_update_chapter"] = chapter_num

                # --- 群体维度 ---
                elif entity_type == "群体组织":
                    if text:
                        current_updates["groups"][text] = {
                            "name": text,
                            "type": attrs.get("性质", ""),
                            "status": attrs.get("状态", attrs.get("当前状态", "活跃")),
                            "first_chapter": chapter_num,
                            "last_update_chapter": chapter_num,
                        }
                elif entity_type in ("群体状态变化", "群体关系变化"):
                    group_name = attrs.get("群体名称", attrs.get("group", ""))
                    new_status = attrs.get("变化类型", attrs.get("新状态", "")) or text
                    if group_name and new_status:
                        if group_name not in current_updates["groups"]:
                            current_updates["groups"][group_name] = {
                                "name": group_name, "type": "",
                                "first_chapter": chapter_num,
                            }
                        current_updates["groups"][group_name]["status"] = new_status
                        current_updates["groups"][group_name]["last_update_chapter"] = chapter_num

                # --- 伏笔维度 ---
                elif entity_type == "伏笔":
                    if text:
                        current_updates["foreshadows"][text] = {
                            "name": text,
                            "type": attrs.get("重要程度", "普通"),
                            "status": attrs.get("状态", "已埋下"),
                            "first_chapter": chapter_num,
                            "last_update_chapter": chapter_num,
                        }
                elif entity_type == "伏笔回收":
                    foreshadow_name = attrs.get("伏笔名称", attrs.get("foreshadowing", "")) or text
                    if foreshadow_name:
                        if foreshadow_name not in current_updates["foreshadows"]:
                            current_updates["foreshadows"][foreshadow_name] = {
                                "name": foreshadow_name, "type": "",
                                "first_chapter": chapter_num,
                            }
                        current_updates["foreshadows"][foreshadow_name]["status"] = "已回收"
                        current_updates["foreshadows"][foreshadow_name]["last_update_chapter"] = chapter_num

                # --- 世界规则维度 ---
                elif entity_type == "世界规则":
                    if text:
                        current_updates["world_rules"][text] = {
                            "name": text,
                            "type": attrs.get("规则类型", ""),
                            "status": attrs.get("状态", attrs.get("当前状态", "生效")),
                            "first_chapter": chapter_num,
                            "last_update_chapter": chapter_num,
                        }

                # --- 时间线维度 ---
                elif entity_type == "时间节点":
                    if text:
                        current_updates["time_context"][text] = {
                            "name": text,
                            "type": attrs.get("时间类型", ""),
                            "first_chapter": chapter_num,
                            "last_update_chapter": chapter_num,
                        }
                elif entity_type == "时间流逝":
                    if text:
                        current_updates["time_context"][text] = {
                            "name": text,
                            "type": "时间流逝",
                            "description": attrs.get("流逝量", text),
                            "first_chapter": chapter_num,
                            "last_update_chapter": chapter_num,
                        }

            # 2. 确定统一状态文件路径
            project_graph_base = os.path.dirname(graph_dir)
            unified_path = os.path.join(project_graph_base, "consistency_state.json")

            # 3. 加载已有统一状态（含旧 event_status_index.json 迁移）
            existing_state = self._load_or_migrate_unified_state(unified_path, project_graph_base)

            # 4. 合并：逐维度合并更新
            for dim_key in current_updates:
                if dim_key not in existing_state:
                    existing_state[dim_key] = {}
                dim_existing = existing_state[dim_key]
                for entity_name, update in current_updates[dim_key].items():
                    if entity_name in dim_existing:
                        existing = dim_existing[entity_name]
                        if update.get("status"):
                            existing["status"] = update["status"]
                        if update.get("type") and not existing.get("type"):
                            existing["type"] = update["type"]
                        existing["last_update_chapter"] = max(
                            existing.get("last_update_chapter", 0),
                            update.get("last_update_chapter", chapter_num)
                        )
                    else:
                        dim_existing[entity_name] = update

            # 5. 写回统一状态文件
            with open(unified_path, "w", encoding="utf-8") as f:
                json.dump(existing_state, f, ensure_ascii=False, indent=2)

            # 6. 日志汇总
            summary_parts = []
            for dim_key in ["events", "items", "facilities", "groups", "foreshadows", "world_rules", "time_context"]:
                dim_data = existing_state.get(dim_key, {})
                total = len(dim_data)
                if dim_key == "events":
                    completed = sum(1 for v in dim_data.values() if v.get("status") in ["已完成", "已结束", "已取消"])
                    summary_parts.append(f"事件={total}(已完成{completed})")
                elif dim_key == "items":
                    inactive = sum(1 for v in dim_data.values() if v.get("status") in ["已使用", "已销毁", "已遗失", "已回收", "已损坏"])
                    summary_parts.append(f"道具={total}(离场{inactive})")
                elif dim_key == "facilities":
                    abnormal = sum(1 for v in dim_data.values() if v.get("status") in ["关闭", "损坏", "暂停营业", "已拆除"])
                    summary_parts.append(f"设施={total}(异常{abnormal})")
                elif dim_key == "groups":
                    inactive_g = sum(1 for v in dim_data.values() if v.get("status") in ["解散", "合并", "消亡"])
                    summary_parts.append(f"群体={total}(解散{inactive_g})")
                elif dim_key == "foreshadows":
                    resolved = sum(1 for v in dim_data.values() if v.get("status") == "已回收")
                    summary_parts.append(f"伏笔={total}(已回收{resolved})")
                elif dim_key == "time_context":
                    summary_parts.append(f"时间线={total}")
                else:
                    summary_parts.append(f"规则={total}")
            
            self.logger.info(
                f"[统一状态存储 v5.0] 一致性状态已更新: 章节{chapter_num}, "
                + ", ".join(summary_parts)
            )

            return existing_state

        except Exception as e:
            self.logger.warning(f"持久化统一一致性状态失败: {e}")
            return None

    @staticmethod
    def load_unified_state(project_graph_dir: str) -> Dict[str, Any]:
        """加载统一一致性状态

        供一致性报告等模块读取跨章各维度状态。
        自动兼容旧版 event_status_index.json → 迁移到 consistency_state.json。

        Args:
            project_graph_dir: 项目图谱数据目录路径

        Returns:
            统一状态字典
            {
                "events": {event_name: {name, type, status, first_chapter, last_update_chapter}},
                "items": {...}, "facilities": {...},
                "groups": {...}, "foreshadows": {...}, "world_rules": {...}
            }
        """
        unified_path = os.path.join(project_graph_dir, "consistency_state.json")
        old_events_path = os.path.join(project_graph_dir, "event_status_index.json")

        result = {
            "events": {}, "items": {}, "facilities": {},
            "groups": {}, "foreshadows": {}, "world_rules": {},
            "time_context": {},
        }

        # 优先读取新格式
        if os.path.exists(unified_path):
            try:
                with open(unified_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for dim_key in result:
                    if dim_key in data:
                        result[dim_key] = data[dim_key]
                return result
            except (json.JSONDecodeError, IOError):
                pass

        # 兼容旧版 event_status_index.json：迁移到新格式
        if os.path.exists(old_events_path):
            try:
                with open(old_events_path, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                if isinstance(old_data, dict) and old_data:
                    result["events"] = old_data
                    # 自动迁移写入新文件
                    try:
                        with open(unified_path, "w", encoding="utf-8") as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                    except IOError:
                        pass
                    return result
            except (json.JSONDecodeError, IOError):
                pass

        return result

    def _load_or_migrate_unified_state(
        self, unified_path: str, project_graph_base: str
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """加载或迁移统一状态文件

        内部方法：供 _persist_unified_state 调用，处理旧格式迁移
        """
        default = {
            "events": {}, "items": {}, "facilities": {},
            "groups": {}, "foreshadows": {}, "world_rules": {},
            "time_context": {},
        }

        # 新格式文件存在：直接加载
        if os.path.exists(unified_path):
            try:
                with open(unified_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for dim_key in default:
                    if dim_key in data:
                        default[dim_key] = data[dim_key]
                return default
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"统一状态文件读取失败，将重建: {e}")
                return default

        # 尝试从旧 event_status_index.json 迁移
        old_path = os.path.join(project_graph_base, "event_status_index.json")
        if os.path.exists(old_path):
            try:
                with open(old_path, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                if isinstance(old_data, dict) and old_data:
                    default["events"] = old_data
                    self.logger.info(
                        f"[统一状态存储 v5.0] 从 event_status_index.json 迁移 {len(old_data)} 条事件记录"
                    )
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"旧事件索引迁移失败: {e}")

        return default
