"""ProjectKnowledgeBase - get_kb_statsMixin"""
from typing import Dict
from typing import Any
import re
import os


class GetKbStatsMixin:
    """get_kb_stats功能域"""

    def get_kb_stats(self, project_id: int) -> Dict[str, Any]:
        """
        获取知识库统计信息

        Args:
            project_id: 项目ID

        Returns:
            统计信息
        """
        try:
            collection_name = self.get_collection_name(project_id)
            doc_count = self.vector_store.count_documents(collection_name)

            # 检查图谱文件
            global_graph_exists = os.path.exists(
                self.get_graph_path(project_id, unit_number=None))

            return {
                "collection_name": collection_name,
                "document_count": doc_count,
                "global_graph_exists": global_graph_exists,
                "status": "ready" if doc_count > 0 else "empty"
            }

        except Exception as e:
            return {
                "collection_name": self.get_collection_name(project_id),
                "document_count": 0,
                "status": "error",
                "error": str(e)
            }


