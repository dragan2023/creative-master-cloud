"""NovelKnowledgeGraph - saveMixin"""
import json
import re
import os


class SaveMixin:
    """save功能域"""

    def save(self) -> bool:
        """保存图谱"""
        if not self.persist_path:
            return False

        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)

            data = {
                "nodes": [
                    {"id": node_id, **data}
                    for node_id, data in self.graph.nodes(data=True)
                ],
                "edges": [
                    {"source": source, "target": target, **data}
                    for source, target, data in self.graph.edges(data=True)
                ]
            }

            with open(self.persist_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.debug(
                f"正文板块图谱已保存: {os.path.basename(self.persist_path)}, 节点数: {self.graph.number_of_nodes()}, 边数: {self.graph.number_of_edges()}")
            return True

        except Exception as e:
            self.logger.error(f"保存正文板块图谱失败: {e}")
            return False


