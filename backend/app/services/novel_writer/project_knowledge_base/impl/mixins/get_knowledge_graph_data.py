"""ProjectKnowledgeBase - get_knowledge_graph_dataMixin"""
from typing import Dict
from typing import Optional
from typing import Any
import re
import os


class GetKnowledgeGraphDataMixin:
    """get_knowledge_graph_data功能域"""

    def get_knowledge_graph_data(
        self,
        project_id: int,
        unit_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取知识图谱数据（用于可视化）

        Args:
            project_id: 项目ID
            unit_number: 单元号，None表示全局图谱

        Returns:
            图谱数据 {nodes: [], edges: [], stats: {}}
        """
        result = {
            "nodes": [],
            "edges": [],
            "stats": {
                "node_count": 0,
                "edge_count": 0,
                "entity_types": {}
            }
        }

        try:
            graph_path = self.get_graph_path(project_id, unit_number)

            if not os.path.exists(graph_path):
                self.logger.warning(f"图谱文件不存在: {graph_path}")
                return result

            knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
            knowledge_graph.load()

            # 提取节点数据（支持分层结构）
            entity_types = {}
            macro_count = 0
            micro_count = 0
            for node_id, node_data in knowledge_graph.graph.nodes(data=True):
                node_type = node_data.get("type", "未知")
                node_level = node_data.get("level", "macro")
                entity_types[node_type] = entity_types.get(node_type, 0) + 1

                if node_level == "macro":
                    macro_count += 1
                else:
                    micro_count += 1

                result["nodes"].append({
                    "id": node_id,
                    "name": node_data.get("text", ""),  # 前端使用 name
                    "label": node_data.get("text", ""),  # 兼容公共知识库格式
                    "type": node_type,
                    "level": node_level,  # 宏观层或微观层
                    "description": node_data.get("description", ""),
                    "attributes": node_data.get("attributes", {}),  # 额外属性
                    "doc_id": node_data.get("doc_id", "")
                })

            # 提取边数据
            for source, target, edge_data in knowledge_graph.graph.edges(data=True):
                result["edges"].append({
                    "source": source,
                    "target": target,
                    "relation": edge_data.get("relation", ""),
                    "context": edge_data.get("context", "")
                })

            result["stats"]["node_count"] = len(result["nodes"])
            result["stats"]["edge_count"] = len(result["edges"])
            result["stats"]["entity_types"] = list(
                entity_types.keys())  # 返回类型列表，前端用 join 显示
            result["stats"]["entity_type_counts"] = entity_types  # 同时保留类型数量统计
            # 添加分层统计
            result["stats"]["macro_count"] = macro_count  # 宏观层节点数
            result["stats"]["micro_count"] = micro_count  # 微观层节点数

            return result

        except Exception as e:
            self.logger.error(
                f"获取图谱数据失败: project_id={project_id}, error={str(e)}")
            return result


