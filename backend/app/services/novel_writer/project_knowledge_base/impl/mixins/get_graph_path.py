"""ProjectKnowledgeBase - get_graph_pathMixin"""
from typing import Optional
import json
import re
import os


class GetGraphPathMixin:
    """get_graph_path功能域"""

    def get_graph_path(self, project_id: int, unit_number: Optional[int] = None) -> str:
        """
        获取知识图谱文件路径

        Args:
            project_id: 项目ID
            unit_number: 单元号，None表示全局大纲图谱

        Returns:
            图谱文件路径
        """
        if unit_number is None:
            filename = f"project_{project_id}_global_graph.json"
        else:
            filename = f"project_{project_id}_unit_{unit_number}_graph.json"
        return os.path.join(self.persist_dir, filename)


