"""ProjectKnowledgeBase - retrieve_global_onlyMixin"""
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
import re
import os
import time


class RetrieveGlobalOnlyMixin:
    """retrieve_global_only功能域"""

    async def retrieve_global_only(
        self,
        project_id: int,
        query_text: str,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        仅检索全局大纲图谱内容

        用于获取世界观、人物设定等基础信息

        Args:
            project_id: 项目ID
            query_text: 查询文本
            n_results: 返回结果数量

        Returns:
            检索结果
        """
        result = {
            "entities": [],
            "relations": [],
            "combined_context": ""
        }

        try:
            collection_name = self.get_collection_name(project_id)

            query_result = self.vector_store.query(
                collection_name=collection_name,
                query_texts=[query_text],
                n_results=n_results,
                where={"doc_type": self.DOC_TYPE_GLOBAL}
            )

            if query_result and query_result.get("documents"):
                for i, doc in enumerate(query_result["documents"][0]):
                    metadata = query_result.get("metadatas", [[]])[
                        0][i] if query_result.get("metadatas") else {}
                    entity_type = metadata.get("entity_type", "unknown")

                    if entity_type == "relationship":
                        result["relations"].append(
                            {"content": doc, "metadata": metadata})
                    else:
                        result["entities"].append(
                            {"content": doc, "metadata": metadata})

            # 构建上下文
            context_parts = []
            if result["entities"]:
                context_parts.append("【人物与实体】")
                context_parts.extend([e["content"]
                                     for e in result["entities"]])
            if result["relations"]:
                context_parts.append("\n【关系网络】")
                context_parts.extend([r["content"]
                                     for r in result["relations"]])

            result["combined_context"] = "\n".join(context_parts)

            return result

        except Exception as e:
            self.logger.error(
                f"全局图谱检索失败: project_id={project_id}, error={str(e)}")
            return result


    def _retrieve_from_graph_files(
        self,
        project_id: int,
        current_unit: int,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        从图谱文件直接读取数据（向量库为空时的备选方案）

        Args:
            project_id: 项目ID
            current_unit: 当前单元号
            result: 已有的结果字典

        Returns:
            填充后的结果字典
        """
        try:
            context_parts = []

            # 1. 读取全局图谱
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            if os.path.exists(global_graph_path):
                global_graph = NovelKnowledgeGraph(
                    persist_path=global_graph_path)
                if global_graph.load():
                    self.logger.info(
                        f"从全局图谱文件读取成功: {global_graph_path}, "
                        f"nodes={global_graph.graph.number_of_nodes()}")

                    # 提取实体
                    for node_id, node_data in global_graph.graph.nodes(data=True):
                        node_type = node_data.get("type", "未知")
                        node_text = node_data.get("text", "")
                        node_desc = node_data.get("description", "")

                        if node_type == "relationship":
                            continue

                        doc_content = f"【{node_type}】{node_text}"
                        if node_desc:
                            doc_content += f"\n{node_desc}"

                        result["global_entities"].append({
                            "content": doc_content,
                            "metadata": {"entity_type": node_type, "entity_name": node_text}
                        })

                    # 提取关系
                    for source, target, edge_data in global_graph.graph.edges(data=True):
                        source_data = global_graph.graph.nodes.get(source, {})
                        target_data = global_graph.graph.nodes.get(target, {})
                        source_text = source_data.get("text", source)
                        target_text = target_data.get("text", target)
                        rel_type = edge_data.get("relation", "关联")

                        doc_content = f"【关系】{source_text} --[{rel_type}]--> {target_text}"
                        result["global_relations"].append({
                            "content": doc_content,
                            "metadata": {"entity_type": "relationship"}
                        })

                    # 构建上下文
                    if result["global_entities"]:
                        context_parts.append("【全局设定 - 人物与实体】")
                        context_parts.extend(
                            [e["content"] for e in result["global_entities"][:10]])

                    if result["global_relations"]:
                        context_parts.append("\n【全局设定 - 关系网络】")
                        context_parts.extend(
                            [r["content"] for r in result["global_relations"][:5]])

            # 2. 读取当前单元图谱
            unit_graph_path = self.get_graph_path(project_id, current_unit)
            if os.path.exists(unit_graph_path):
                unit_graph = NovelKnowledgeGraph(persist_path=unit_graph_path)
                if unit_graph.load():
                    self.logger.info(
                        f"从单元图谱文件读取成功: {unit_graph_path}, "
                        f"nodes={unit_graph.graph.number_of_nodes()}")

                    # 提取实体
                    for node_id, node_data in unit_graph.graph.nodes(data=True):
                        node_type = node_data.get("type", "未知")
                        node_text = node_data.get("text", "")
                        node_desc = node_data.get("description", "")

                        if node_type == "relationship":
                            continue

                        doc_content = f"【{node_type}】{node_text}"
                        if node_desc:
                            doc_content += f"\n{node_desc}"

                        result["unit_entities"].append({
                            "content": doc_content,
                            "metadata": {"entity_type": node_type, "entity_name": node_text}
                        })

                    # 提取关系
                    for source, target, edge_data in unit_graph.graph.edges(data=True):
                        source_data = unit_graph.graph.nodes.get(source, {})
                        target_data = unit_graph.graph.nodes.get(target, {})
                        source_text = source_data.get("text", source)
                        target_text = target_data.get("text", target)
                        rel_type = edge_data.get("relation", "关联")

                        doc_content = f"【关系】{source_text} --[{rel_type}]--> {target_text}"
                        result["unit_relations"].append({
                            "content": doc_content,
                            "metadata": {"entity_type": "relationship"}
                        })

                    # 构建上下文
                    if result["unit_entities"]:
                        context_parts.append("\n【本单元 - 人物与实体】")
                        context_parts.extend(
                            [e["content"] for e in result["unit_entities"][:10]])

                    if result["unit_relations"]:
                        context_parts.append("\n【本单元 - 关系动态】")
                        context_parts.extend(
                            [r["content"] for r in result["unit_relations"][:5]])

            # 3. 获取时间线
            timeline_context = self._get_event_timeline(
                project_id, current_unit)
            if timeline_context:
                context_parts.append("\n【事件时间线】")
                context_parts.append(timeline_context)

            result["combined_context"] = "\n".join(context_parts)

            self.logger.info(
                f"图谱文件读取完成: project_id={project_id}, unit={current_unit}, "
                f"global_entities={len(result['global_entities'])}, "
                f"unit_entities={len(result['unit_entities'])}, "
                f"has_context={bool(result['combined_context'])}"
            )

        except Exception as e:
            self.logger.error(
                f"从图谱文件读取失败: project_id={project_id}, error={str(e)}")

        return result


    def _get_event_timeline(
        self,
        project_id: int,
        current_unit: int
    ) -> Optional[str]:
        """
        获取事件时间线（通过图关系查询）

        通过"前序"和"导致"关系获取当前单元前后的事件，确保情节连贯性。

        查询逻辑：
        1. 从当前单元图谱中查找详细事件节点
        2. 通过"前序"关系获取前序事件
        3. 通过"导致"关系获取后序事件
        4. 跨单元查询：获取前一个单元的结尾事件

        Args:
            project_id: 项目ID
            current_unit: 当前单元号

        Returns:
            时间线上下文文本，或 None
        """
        try:
            timeline_parts = []

            # 1. 跨单元查询：获取前一个单元的结尾事件
            if current_unit > 1:
                prev_unit_events = self._get_unit_ending_events(
                    project_id, current_unit - 1)
                if prev_unit_events:
                    timeline_parts.append("【前序单元结尾事件】")
                    for evt in prev_unit_events[:3]:
                        timeline_parts.append(f"  - {evt}")

            # 2. 加载当前单元图谱
            graph_path = self.get_graph_path(project_id, current_unit)
            if not os.path.exists(graph_path):
                self.logger.info(f"当前单元图谱不存在，跳过时间线")
                return "\n".join(timeline_parts) if timeline_parts else None

            knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
            knowledge_graph.load()

            # 时间线关系类型
            timeline_relations = {"前序", "导致"}

            # 存储时间线事件
            prev_events = []  # 前序事件
            next_events = []  # 后序事件
            current_events = []  # 当前事件

            # 遍历所有边，查找时间线关系
            for source, target, edge_data in knowledge_graph.graph.edges(data=True):
                relation_type = edge_data.get("type", "")

                if relation_type not in timeline_relations:
                    continue

                # 获取源节点和目标节点信息
                source_data = knowledge_graph.graph.nodes.get(source, {})
                target_data = knowledge_graph.graph.nodes.get(target, {})

                source_type = source_data.get("type", "")
                target_type = target_data.get("type", "")

                # 只处理详细事件节点（使用中文类型名，与存储一致）
                if source_type != "详细事件" and target_type != "详细事件":
                    continue

                source_text = source_data.get("text", source)
                target_text = target_data.get("text", target)

                if relation_type == "前序":
                    # source -> target 表示 source 是 target 的前序事件
                    prev_events.append({
                        "event": source_text,
                        "leads_to": target_text
                    })
                elif relation_type == "导致":
                    # source -> target 表示 source 导致 target
                    next_events.append({
                        "event": source_text,
                        "causes": target_text
                    })

            # 收集当前单元的所有详细事件
            for node_id, node_data in knowledge_graph.graph.nodes(data=True):
                if node_data.get("type") == "详细事件":
                    current_events.append(node_data.get("text", node_id))

            # 构建时间线上下文
            if prev_events:
                timeline_parts.append("\n【前序事件关系】")
                for evt in prev_events[:3]:  # 最多3个
                    timeline_parts.append(
                        f"  - {evt['event']} → {evt['leads_to']}")

            if current_events:
                timeline_parts.append("\n【当前单元事件列表】")
                for evt in current_events[:5]:  # 最多5个
                    timeline_parts.append(f"  - {evt}")

            if next_events:
                timeline_parts.append("\n【后续事件关系】")
                for evt in next_events[:3]:  # 最多3个
                    timeline_parts.append(
                        f"  - {evt['event']} → {evt['causes']}")

            if not timeline_parts:
                self.logger.info(
                    f"未找到时间线信息: project_id={project_id}, unit={current_unit}")
                return None

            result = "\n".join(timeline_parts)
            self.logger.info(
                f"获取时间线成功: project_id={project_id}, unit={current_unit}")

            return result

        except Exception as e:
            self.logger.error(f"获取事件时间线失败: {str(e)}")
            return None


    def _get_unit_ending_events(
        self,
        project_id: int,
        unit_number: int,
        max_events: int = 3
    ) -> List[str]:
        """
        获取指定单元的结尾事件

        用于跨单元时间线，获取前一个单元的结尾事件作为当前单元的前序上下文。

        Args:
            project_id: 项目ID
            unit_number: 单元号
            max_events: 最多返回的事件数

        Returns:
            事件文本列表
        """
        events = []

        try:
            graph_path = self.get_graph_path(project_id, unit_number)
            if not os.path.exists(graph_path):
                return events

            knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
            knowledge_graph.load()

            # 查找没有后继节点的详细事件（结尾事件）
            for node_id, node_data in knowledge_graph.graph.nodes(data=True):
                if node_data.get("type") != "详细事件":
                    continue

                # 检查是否有"导致"或"前序"出边
                has_outgoing = False
                for _, target, edge_data in knowledge_graph.graph.edges(node_id, data=True):
                    if edge_data.get("type") in {"导致", "前序"}:
                        has_outgoing = True
                        break

                # 如果没有出边，这是一个结尾事件
                if not has_outgoing:
                    events.append(node_data.get("text", node_id))
                    if len(events) >= max_events:
                        break

            self.logger.info(
                f"获取单元结尾事件: project_id={project_id}, unit={unit_number}, "
                f"events={len(events)}"
            )

        except Exception as e:
            self.logger.error(f"获取单元结尾事件失败: {str(e)}")

        return events


