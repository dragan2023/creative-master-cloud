"""
monitoring/_knowledge_graph.py - 知识图谱操作 Mixin

包含 MonitoringKnowledgeGraphMixin，提供知识图谱同步方法。

@date: 2026-04-24
@version: v3.0.0
"""
import os
from typing import Any, Dict, Optional

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
