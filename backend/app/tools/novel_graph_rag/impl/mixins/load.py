"""NovelKnowledgeGraph - loadMixin"""
import json
import re
import os


class LoadMixin:
    """load功能域"""

    def load(self) -> bool:
        """加载图谱"""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return False

        try:
            with open(self.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.graph.clear()
            self.entity_index.clear()

            # 加载节点
            for node in data.get("nodes", []):
                node_id = node.get("id")
                self.graph.add_node(
                    node_id, **{k: v for k, v in node.items() if k != "id"})
                # 建立索引
                text = node.get("text", "")
                if text:
                    self.entity_index[text] = node_id

            # 加载边
            for edge in data.get("edges", []):
                source = edge.get("source")
                target = edge.get("target")
                if source and target:
                    self.graph.add_edge(
                        source, target, **{k: v for k, v in edge.items() if k not in ["source", "target"]})

            self.logger.debug(
                f"正文板块图谱已加载: {os.path.basename(self.persist_path)}, 节点数: {self.graph.number_of_nodes()}, 边数: {self.graph.number_of_edges()}")
            return True

        except Exception as e:
            self.logger.error(f"加载正文板块图谱失败: {e}")
            return False


