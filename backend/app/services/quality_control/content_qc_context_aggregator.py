"""
正文质控综合信息聚合器

在正文质控执行前，聚合所有关键信息源，构建综合上下文：
- 全局知识图谱（实体/关系网络）
- 人物设定（角色档案、性格、行为模式）
- 前文摘要（已生成内容的上下文）
- 一致性报告（与全局大纲的一致性检测结果）
- 时间线与空间逻辑（位置、时间、因果关系连续性）
- 人物OOC检测（角色是否违背人设）

@date: 2026-05-13
@version: v1.0.0
"""
import os
import json
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.logger import get_logger

logger = get_logger("quality_control.context_aggregator")


class ContentQCContextAggregator:
    """正文质控综合信息聚合器"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def aggregate(
        self,
        project_id: int,
        unit_index: int,
        current_content: str = ""
    ) -> Dict[str, str]:
        """
        聚合所有信息源，构建综合质控上下文

        Args:
            project_id: 项目ID
            unit_index: 当前单元序号
            current_content: 当前单元正文内容

        Returns:
            {
                "knowledge_graph_context": "知识图谱上下文文本",
                "character_context": "人物设定上下文文本",
                "previous_content_summary": "前文摘要文本",
                "consistency_context": "一致性报告文本",
                "timeline_spatial_context": "时间线与空间逻辑文本",
                "ooc_constraints": "人物OOC约束文本"
            }
        """
        result = {
            "knowledge_graph_context": "",
            "character_context": "",
            "previous_content_summary": "",
            "consistency_context": "",
            "timeline_spatial_context": "",
            "ooc_constraints": ""
        }

        try:
            # 并行聚合各项信息源（独立容错，互不影响）
            result["knowledge_graph_context"] = await self._get_knowledge_graph_context(project_id)
        except Exception as e:
            logger.warning(f"[聚合器] 知识图谱聚合失败: {e}")

        try:
            result["character_context"] = await self._get_character_context(project_id)
        except Exception as e:
            logger.warning(f"[聚合器] 人物设定聚合失败: {e}")

        try:
            result["previous_content_summary"] = await self._get_previous_content_summary(project_id, unit_index)
        except Exception as e:
            logger.warning(f"[聚合器] 前文摘要聚合失败: {e}")

        try:
            result["consistency_context"] = await self._get_consistency_context(project_id)
        except Exception as e:
            logger.warning(f"[聚合器] 一致性报告聚合失败: {e}")

        try:
            result["timeline_spatial_context"] = await self._get_timeline_spatial_context(project_id, unit_index)
        except Exception as e:
            logger.warning(f"[聚合器] 时间线空间逻辑聚合失败: {e}")

        try:
            result["ooc_constraints"] = await self._get_ooc_constraints(project_id)
        except Exception as e:
            logger.warning(f"[聚合器] OOC约束聚合失败: {e}")

        logger.info(
            f"[聚合器] 完成: project={project_id}, unit={unit_index}, "
            f"kg={len(result['knowledge_graph_context'])}chars, "
            f"char={len(result['character_context'])}chars, "
            f"prev={len(result['previous_content_summary'])}chars"
        )
        return result

    async def _get_knowledge_graph_context(self, project_id: int) -> str:
        """从全局知识图谱提取实体和关系"""
        from app.services.quality_control.kg_helper import get_kg_helper

        kg_helper = get_kg_helper()
        kg_path = kg_helper.get_global_graph_path(project_id)

        if not os.path.exists(kg_path):
            return ""

        try:
            from app.tools.graph_rag import KnowledgeGraph
            kg = KnowledgeGraph(persist_path=kg_path)
            if not kg.load():
                return ""

            lines = []
            entity_count = 0
            relation_count = 0

            for node_id, node_data in kg.graph.nodes(data=True):
                if entity_count >= 30:
                    break
                node_type = node_data.get("type", "未知")
                node_text = node_data.get("text", "")
                node_desc = node_data.get("description", "")
                node_status = node_data.get("status", "")

                if not node_text or not node_text.strip():
                    continue

                line = f"【{node_type}】{node_text}"
                if node_desc:
                    line += f": {node_desc}"
                if node_status:
                    line += f" (状态: {node_status})"
                lines.append(line)
                entity_count += 1

            for source, target, edge_data in kg.graph.edges(data=True):
                if relation_count >= 20:
                    break
                relation = edge_data.get("relation", "相关关系")
                context = edge_data.get("context", "")
                source_text = kg.graph.nodes.get(source, {}).get("text", source)
                target_text = kg.graph.nodes.get(target, {}).get("text", target)
                line = f"- {source_text} --[{relation}]--> {target_text}"
                if context:
                    line += f" ({context})"
                lines.append(line)
                relation_count += 1

            logger.info(
                f"[聚合器] 知识图谱: {entity_count}个实体, {relation_count}个关系")
            return "\n".join(lines) if lines else ""
        except Exception as e:
            logger.warning(f"[聚合器] 知识图谱解析失败: {e}")
            return ""

    async def _get_character_context(self, project_id: int) -> str:
        """从项目设置提取人物设定"""
        from app.models import NovelProject

        query = select(NovelProject).where(NovelProject.id == project_id)
        result = await self.db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            return ""

        profiles = getattr(project, 'character_profiles', None)
        if not profiles:
            return ""

        lines = []
        if isinstance(profiles, list):
            for char in profiles:
                if isinstance(char, dict):
                    name = char.get("name", char.get("姓名", ""))
                    role = char.get("role", char.get("角色定位", ""))
                    personality = char.get("personality", char.get("性格特征", ""))
                    behavior = char.get("behavior", char.get("行为模式", ""))

                    if name:
                        line = f"【{name}】"
                        if role:
                            line += f" 角色: {role}"
                        if personality:
                            line += f" 性格: {personality}"
                        if behavior:
                            line += f" 行为: {behavior}"
                        lines.append(line)
        elif isinstance(profiles, dict):
            for name, info in profiles.items():
                if isinstance(info, dict):
                    personality = info.get("personality", info.get("性格", ""))
                    role = info.get("role", info.get("角色", ""))
                    line = f"【{name}】"
                    if role:
                        line += f" 角色: {role}"
                    if personality:
                        line += f" 性格: {personality}"
                    lines.append(line)

        return "\n".join(lines) if lines else ""

    async def _get_previous_content_summary(
        self, project_id: int, unit_index: int
    ) -> str:
        """获取前文摘要（前文各单元内容的尾部摘要）"""
        from app.models.writing_unit import WritingUnit
        from app.models.writing_task import WritingTask

        # 查询该项目的所有任务
        task_query = select(WritingTask).where(
            WritingTask.project_id == project_id
        )
        task_result = await self.db.execute(task_query)
        tasks = task_result.scalars().all()

        if not tasks:
            return ""

        task_ids = [t.id for t in tasks]

        # 查询当前单元之前的已完成单元
        unit_query = select(WritingUnit).where(
            WritingUnit.task_id.in_(task_ids),
            WritingUnit.unit_index < unit_index,
            WritingUnit.status == 'completed'
        ).order_by(WritingUnit.unit_index.asc()).limit(10)

        unit_result = await self.db.execute(unit_query)
        units = unit_result.scalars().all()

        if not units:
            return ""

        lines = []
        for u in units:
            title = u.unit_title or f"第{u.unit_index}章"
            content = u.final_content or ""
            # 取每章末尾500字作为摘要
            summary = content[-500:] if len(content) > 500 else content
            lines.append(f"--- {title} 结尾 ---\n{summary}")

        return "\n\n".join(lines)

    async def _get_consistency_context(self, project_id: int) -> str:
        """获取一致性报告"""
        from app.models import QualityReport as QualityReportModel

        query = select(QualityReportModel).where(
            QualityReportModel.project_id == project_id
        ).order_by(QualityReportModel.created_at.desc()).limit(1)

        result = await self.db.execute(query)
        report = result.scalar_one_or_none()

        if not report:
            return ""

        report_data = report.report_data or {}
        issues = report_data.get("issues", [])
        score = report_data.get("overall_score", 0)

        lines = [f"一致性得分: {score}"]
        for issue in issues[:10]:
            severity = issue.get("severity", "info")
            desc = issue.get("description", "")
            suggestion = issue.get("suggestion", "")
            line = f"[{severity}] {desc}"
            if suggestion:
                line += f" → 建议: {suggestion}"
            lines.append(line)

        return "\n".join(lines)

    async def _get_timeline_spatial_context(
        self, project_id: int, unit_index: int
    ) -> str:
        """从知识图谱提取时间线和空间逻辑"""
        from app.services.quality_control.kg_helper import get_kg_helper

        kg_helper = get_kg_helper()
        kg_path = kg_helper.get_global_graph_path(project_id)

        if not os.path.exists(kg_path):
            return ""

        try:
            from app.tools.graph_rag import KnowledgeGraph
            kg = KnowledgeGraph(persist_path=kg_path)
            if not kg.load():
                return ""

            timeline_entities = []
            location_entities = []
            causal_entities = []

            for node_id, node_data in kg.graph.nodes(data=True):
                node_type = node_data.get("type", "")
                node_text = node_data.get("text", "")
                if not node_text:
                    continue

                if node_type in ("时间", "时间点", "时间段", "事件", "大事件"):
                    timeline_entities.append(node_text)
                elif node_type in ("地点", "场景", "位置", "空间"):
                    location_entities.append(node_text)
                elif node_type in ("因果关系", "前置事件", "后果", "伏笔"):
                    causal_entities.append(node_text)

            lines = []
            if timeline_entities:
                lines.append("【时间线】" + " → ".join(timeline_entities[:15]))
            if location_entities:
                lines.append("【空间位置】" + ", ".join(location_entities[:10]))
            if causal_entities:
                lines.append("【因果关系】" + ", ".join(causal_entities[:10]))

            return "\n".join(lines) if lines else ""
        except Exception as e:
            logger.warning(f"[聚合器] 时间线提取失败: {e}")
            return ""

    async def _get_ooc_constraints(self, project_id: int) -> str:
        """从知识图谱提取人物行为约束，用于OOC检测"""
        from app.services.quality_control.kg_helper import get_kg_helper

        kg_helper = get_kg_helper()
        kg_path = kg_helper.get_global_graph_path(project_id)

        if not os.path.exists(kg_path):
            return ""

        try:
            from app.tools.graph_rag import KnowledgeGraph
            kg = KnowledgeGraph(persist_path=kg_path)
            if not kg.load():
                return ""

            lines = []
            for node_id, node_data in kg.graph.nodes(data=True):
                node_type = node_data.get("type", "")
                node_text = node_data.get("text", "")

                if node_type in ("人物", "角色", "Character") and node_text:
                    node_status = node_data.get("status", "")
                    node_desc = node_data.get("description", "")
                    node_traits = node_data.get("traits", node_data.get("attributes", ""))

                    constraint = f"【{node_text}】"
                    parts = []
                    if node_status:
                        parts.append(f"当前状态: {node_status}")
                    if node_traits:
                        parts.append(f"特征: {node_traits}")
                    if node_desc:
                        parts.append(f"描述: {node_desc}")
                    if parts:
                        constraint += " " + "; ".join(parts)
                    lines.append(constraint)

            return "\n".join(lines) if lines else ""
        except Exception as e:
            logger.warning(f"[聚合器] OOC约束提取失败: {e}")
            return ""


def get_context_aggregator(db: AsyncSession) -> ContentQCContextAggregator:
    """获取正文质控上下文聚合器实例"""
    return ContentQCContextAggregator(db)
