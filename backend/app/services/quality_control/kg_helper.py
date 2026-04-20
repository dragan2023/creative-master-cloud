"""
知识图谱查询辅助模块 - 用于质控修正流程

在质控修正时查询项目知识图谱，提供上下文参考。

@date: 2026-04-20
@version: v1.0.0
"""
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

from app.core.logger import get_logger

logger = get_logger("quality_control.kg_helper")


class KGQueryHelper:
    """知识图谱查询辅助类"""

    def __init__(self):
        self.logger = logger

    def get_global_graph_path(self, project_id: int) -> str:
        """
        获取全局知识图谱文件路径

        Args:
            project_id: 项目ID

        Returns:
            知识图谱文件路径
        """
        from app.core.config import get_settings
        settings = get_settings()
        kg_dir = settings.get_knowledge_graph_dir()
        return os.path.join(kg_dir, f"project_{project_id}_global_graph.json")

    def query_relevant_entities(
        self,
        project_id: int,
        unit_index: int,
        issue_category: str = "",
        max_entities: int = 20
    ) -> Dict[str, Any]:
        """
        查询与当前单元和问题相关的知识图谱实体

        Args:
            project_id: 项目ID
            unit_index: 单元序号
            issue_category: 问题类别（如"人物OOC"、"单元衔接"等）
            max_entities: 最大返回实体数

        Returns:
            知识图谱上下文字典
        """
        import json
        from app.tools.graph_rag import KnowledgeGraph

        result = {
            "characters": [],  # 相关人物
            "events": [],      # 相关事件
            "foreshadows": [],  # 伏笔
            "relationships": [],  # 人物关系
            "world_rules": [],  # 世界规则
            "items": [],       # 重要物品
            "locations": [],   # 场景地点
        }

        # 1. 加载知识图谱
        kg_path = self.get_global_graph_path(project_id)
        if not os.path.exists(kg_path):
            self.logger.warning(f"[知识图谱查询] 全局图谱不存在: {kg_path}")
            return result

        kg = KnowledgeGraph(persist_path=kg_path)
        if not kg.load():
            self.logger.warning(f"[知识图谱查询] 知识图谱加载失败: {kg_path}")
            return result

        self.logger.info(
            f"[知识图谱查询] 加载成功: project={project_id}, "
            f"节点数={kg.graph.number_of_nodes()}, 边数={kg.graph.number_of_edges()}"
        )

        # 2. 提取相关实体
        nodes_data = []
        for node_id, node_data in kg.graph.nodes(data=True):
            node_info = {
                "id": node_id,
                "type": node_data.get("type", "未知"),
                "text": node_data.get("text", ""),
                "chapter": node_data.get("chapter", 0),
                "status": node_data.get("status", ""),
                "description": node_data.get("description", ""),
            }
            nodes_data.append(node_info)

        # 3. 根据问题类别筛选相关实体
        if issue_category in ["人物OOC", "人物状态不一致", "人物关系矛盾"]:
            # 人物相关问题：提取所有人物实体
            result["characters"] = [
                n for n in nodes_data
                if n["type"] in ["人物", "角色", "character"]
            ][:max_entities]

        elif issue_category in ["单元衔接", "情节断裂", "逻辑矛盾"]:
            # 情节相关问题：提取事件和伏笔
            result["events"] = [
                n for n in nodes_data
                if n["type"] in ["事件", "情节", "event", "plot"]
            ][:max_entities]

            result["foreshadows"] = [
                n for n in nodes_data
                if n["type"] in ["伏笔", "foreshadow"]
            ][:max_entities]

        elif issue_category in ["世界观不一致", "设定冲突"]:
            # 世界观问题：提取世界规则和场景
            result["world_rules"] = [
                n for n in nodes_data
                if n["type"] in ["世界规则", "设定", "world_rule", "setting"]
            ][:max_entities]

            result["locations"] = [
                n for n in nodes_data
                if n["type"] in ["场景", "地点", "location"]
            ][:max_entities]

        else:
            # 通用查询：提取所有类型的关键实体
            # 按章节过滤（当前单元及前后单元）
            relevant_chapters = [unit_index - 1, unit_index, unit_index + 1]

            for node in nodes_data:
                node_chapter = node.get("chapter", 0)
                entity_type = node["type"]

                # 优先提取当前单元相关的实体
                if node_chapter in relevant_chapters:
                    if entity_type in ["人物", "角色", "character"]:
                        result["characters"].append(node)
                    elif entity_type in ["事件", "情节", "event", "plot"]:
                        result["events"].append(node)
                    elif entity_type in ["伏笔", "foreshadow"]:
                        result["foreshadows"].append(node)
                    elif entity_type in ["重要物品", "物品", "item"]:
                        result["items"].append(node)
                    elif entity_type in ["场景", "地点", "location"]:
                        result["locations"].append(node)

            # 限制数量
            for key in result:
                result[key] = result[key][:max_entities]

        # 4. 提取人物关系
        edges_data = []
        for source, target, edge_data in kg.graph.edges(data=True):
            source_node = kg.graph.nodes.get(source, {})
            target_node = kg.graph.nodes.get(target, {})

            # 只提取人物之间的关系
            if (source_node.get("type") in ["人物", "角色", "character"] and
                    target_node.get("type") in ["人物", "角色", "character"]):
                edges_data.append({
                    "source": source_node.get("text", ""),
                    "target": target_node.get("text", ""),
                    "relation": edge_data.get("relation", "关联"),
                    "description": edge_data.get("description", ""),
                })

        result["relationships"] = edges_data[:max_entities]

        self.logger.info(
            f"[知识图谱查询] 查询完成: "
            f"人物={len(result['characters'])}, 事件={len(result['events'])}, "
            f"伏笔={len(result['foreshadows'])}, 关系={len(result['relationships'])}"
        )

        return result

    def format_kg_context(self, kg_data: Dict[str, Any]) -> str:
        """
        格式化知识图谱数据为提示词文本

        Args:
            kg_data: 知识图谱查询结果

        Returns:
            格式化的上下文文本
        """
        lines = []

        # 1. 人物信息
        if kg_data.get("characters"):
            lines.append("【当前人物状态】")
            for char in kg_data["characters"][:10]:  # 最多显示10个
                status_text = f"- {char['text']}"
                if char.get("status"):
                    status_text += f"（状态：{char['status']}）"
                if char.get("description"):
                    status_text += f" - {char['description']}"
                lines.append(status_text)
            lines.append("")

        # 2. 人物关系
        if kg_data.get("relationships"):
            lines.append("【人物关系】")
            for rel in kg_data["relationships"][:10]:
                lines.append(
                    f"- {rel['source']} {rel['relation']} {rel['target']}")
            lines.append("")

        # 3. 重要事件
        if kg_data.get("events"):
            lines.append("【已发生事件】")
            for event in kg_data["events"][:10]:
                lines.append(f"- {event['text']}")
            lines.append("")

        # 4. 伏笔
        if kg_data.get("foreshadows"):
            lines.append("【未回收伏笔】")
            for foreshadow in kg_data["foreshadows"][:10]:
                lines.append(f"- {foreshadow['text']}")
            lines.append("")

        # 5. 世界规则
        if kg_data.get("world_rules"):
            lines.append("【世界规则】")
            for rule in kg_data["world_rules"][:10]:
                lines.append(f"- {rule['text']}")
            lines.append("")

        # 6. 重要物品
        if kg_data.get("items"):
            lines.append("【重要物品】")
            for item in kg_data["items"][:10]:
                lines.append(f"- {item['text']}")
            lines.append("")

        # 7. 场景地点
        if kg_data.get("locations"):
            lines.append("【场景地点】")
            for loc in kg_data["locations"][:10]:
                lines.append(f"- {loc['text']}")
            lines.append("")

        if not lines:
            return "暂无知识图谱数据"

        return "\n".join(lines)


# 全局单例
_kg_helper_instance = None


def get_kg_helper() -> KGQueryHelper:
    """获取知识图谱查询辅助器单例"""
    global _kg_helper_instance
    if _kg_helper_instance is None:
        _kg_helper_instance = KGQueryHelper()
    return _kg_helper_instance
