"""
多Agent协作文学作品生成系统 - 知识顾问Agent 执行模块

从 knowledge_agent.py 拆分，包含知识检索和上下文构建的核心逻辑。

@date: 2026-04-24
@version: v2.0.0
"""

import time
from typing import Dict, Any, List, Optional

from app.agents.writing.base_agent import AgentContext, AgentResult


class KnowledgeExecutionMixin:
    """知识顾问Agent执行逻辑 Mixin

    提供知识检索、上下文构建和一致性检查等核心功能。
    """

    async def execute(self, context: AgentContext) -> AgentResult:
        """检索相关知识并整合上下文

        Args:
            context: Agent执行上下文

        Returns:
            AgentResult: 包含整合后的上下文信息
        """
        start_time = time.time()

        try:
            # 提取参数
            query = context.extra.get("query", "")
            knowledge_types = context.extra.get("knowledge_types")
            top_k = context.extra.get("top_k", 10)
            project_id = context.project_id
            current_chapter = context.unit_index

            self.logger.info(
                f"开始知识检索 - 项目: {project_id}, "
                f"章节: {current_chapter}, 查询: {query[:50]}..."
            )

            # 并行检索各类知识
            relevant_passages = []
            character_relations = []
            plot_threads = []
            kb_results = {}

            # 1. 从上下文管理器检索相关内容
            if query:
                relevant_passages = await self.context_adapter.get_relevant_context(
                    query=query,
                    project_id=project_id,
                    top_k=top_k // 2
                )

            # 2. 从知识库检索
            kb_results = await self.kb_adapter.search_knowledge(
                query=query or f"第{current_chapter}章相关内容",
                project_id=project_id,
                knowledge_types=knowledge_types,
                top_k=top_k
            )

            # 3. 获取角色关系
            character_names = [
                char.get("name", "")
                for char in context.character_profiles
                if char.get("name")
            ]
            if character_names:
                character_relations = await self.kb_adapter.get_character_relations(
                    project_id=project_id,
                    character_names=character_names
                )

            # 4. 获取剧情线索
            plot_threads = await self.kb_adapter.get_plot_threads(
                project_id=project_id,
                current_chapter=current_chapter
            )

            # 5. 整合世界观事实
            world_facts = self._extract_world_facts(context.world_settings)

            # 6. 构建上下文摘要
            context_summary = self._build_context_summary(
                relevant_passages=relevant_passages,
                kb_results=kb_results,
                character_relations=character_relations,
                plot_threads=plot_threads,
                world_facts=world_facts
            )

            # 计算耗时
            duration_ms = int((time.time() - start_time) * 1000)

            self.logger.info(
                f"知识检索完成 - 相关片段: {len(relevant_passages)}, "
                f"角色关系: {len(character_relations)}, "
                f"剧情线索: {len(plot_threads)}, 耗时: {duration_ms}ms"
            )

            return self._build_success_result(
                content=context_summary,
                duration_ms=duration_ms,
                model_id="",
                relevant_passages=relevant_passages,
                character_relations=character_relations,
                plot_threads=plot_threads,
                world_facts=world_facts,
                kb_characters=kb_results.get("characters", []),
                kb_events=kb_results.get("events", []),
                kb_settings=kb_results.get("settings", [])
            )

        except Exception as e:
            self.logger.error(f"知识顾问Agent执行失败: {str(e)}", exc_info=True)
            return self._build_error_result(f"知识检索失败: {str(e)}")

    def _extract_world_facts(self, world_settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取世界观事实

        Args:
            world_settings: 世界观设定

        Returns:
            世界观事实列表
        """
        facts = []

        if not world_settings:
            return facts

        # 提取时间设定
        if "time_period" in world_settings:
            facts.append({
                "type": "time",
                "content": world_settings["time_period"],
                "importance": "high"
            })

        # 提取地点设定
        locations = world_settings.get("locations", [])
        for loc in locations[:5]:
            facts.append({
                "type": "location",
                "content": loc.get("description", ""),
                "name": loc.get("name", ""),
                "importance": loc.get("importance", "normal")
            })

        # 提取社会背景
        if "social_background" in world_settings:
            facts.append({
                "type": "social",
                "content": world_settings["social_background"],
                "importance": "high"
            })

        # 提取特殊规则
        rules = world_settings.get("special_rules", [])
        for rule in rules[:3]:
            facts.append({
                "type": "rule",
                "content": rule,
                "importance": "high"
            })

        return facts

    def _build_context_summary(
        self,
        relevant_passages: List[Dict[str, Any]],
        kb_results: Dict[str, Any],
        character_relations: List[Dict[str, Any]],
        plot_threads: List[Dict[str, Any]],
        world_facts: List[Dict[str, Any]]
    ) -> str:
        """构建上下文摘要

        Args:
            relevant_passages: 相关内容片段
            kb_results: 知识库检索结果
            character_relations: 角色关系
            plot_threads: 剧情线索
            world_facts: 世界观事实

        Returns:
            格式化的上下文摘要
        """
        sections = []

        # 世界观事实
        if world_facts:
            sections.append("【世界观参考】")
            for fact in world_facts[:5]:
                if fact.get("type") == "location":
                    sections.append(f"· {fact.get('name', '')}: {fact.get('content', '')}")
                else:
                    sections.append(f"· {fact.get('content', '')}")
            sections.append("")

        # 角色关系
        if character_relations:
            sections.append("【角色关系】")
            for rel in character_relations[:5]:
                source = rel.get("source", "")
                target = rel.get("target", "")
                relation = rel.get("relation", "")
                sections.append(f"· {source} —{relation}— {target}")
            sections.append("")

        # 剧情线索
        if plot_threads:
            sections.append("【剧情线索】")
            for thread in plot_threads[:3]:
                description = thread.get("description", "")
                status = thread.get("status", "进行中")
                sections.append(f"· [{status}] {description}")
            sections.append("")

        # 相关内容片段
        if relevant_passages:
            sections.append("【相关内容参考】")
            for i, passage in enumerate(relevant_passages[:3], 1):
                content = passage.get("content", "")
                source = passage.get("source", "未知来源")
                sections.append(f"{i}. [{source}] {content}")  # 不再截断知识库内容
            sections.append("")

        # 知识库事件
        kb_events = kb_results.get("events", [])
        if kb_events:
            sections.append("【相关事件】")
            for event in kb_events[:3]:
                name = event.get("name", "")
                description = event.get("description", "")
                sections.append(f"· {name}: {description}")
            sections.append("")

        if not sections:
            return "未检索到相关上下文信息"

        return "\n".join(sections)

    async def get_character_context(
        self,
        context: AgentContext,
        character_name: str
    ) -> AgentResult:
        """获取特定角色的上下文信息

        Args:
            context: 执行上下文
            character_name: 角色名称

        Returns:
            AgentResult: 包含角色相关的上下文信息
        """
        context.extra["query"] = character_name
        context.extra["knowledge_types"] = ["character"]
        context.extra["top_k"] = 5
        return await self.execute(context)

    async def check_consistency(
        self,
        context: AgentContext,
        content_to_check: str
    ) -> Dict[str, Any]:
        """检查内容一致性

        Args:
            context: 执行上下文
            content_to_check: 待检查的内容

        Returns:
            一致性检查结果
        """
        result = await self.execute(context)

        conflicts = []
        warnings = []

        # 检查角色名称拼写
        character_names = [
            char.get("name", "")
            for char in context.character_profiles
        ]
        for name in character_names:
            if name and name in content_to_check:
                pass

        # 检查地点一致性
        locations = context.world_settings.get("locations", [])
        for loc in locations:
            loc_name = loc.get("name", "")
            if loc_name and loc_name in content_to_check:
                pass

        return {
            "is_consistent": len(conflicts) == 0,
            "conflicts": conflicts,
            "warnings": warnings
        }
