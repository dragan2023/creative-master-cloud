"""ProjectKnowledgeBase - delete_project_kbMixin"""
import json
import re
import os


class DeleteProjectKbMixin:
    """delete_project_kb功能域"""

    async def delete_project_kb(self, project_id: int) -> bool:
        """
        删除项目知识库

        Args:
            project_id: 项目ID

        Returns:
            是否成功
        """
        try:
            # 1. 删除向量集合
            collection_name = self.get_collection_name(project_id)
            self.vector_store.delete_collection(collection_name)

            # 2. 删除图谱文件
            # 删除全局图谱
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            if os.path.exists(global_graph_path):
                os.remove(global_graph_path)

            # 删除所有单元图谱
            for filename in os.listdir(self.persist_dir):
                if filename.startswith(f"project_{project_id}_unit_") and filename.endswith("_graph.json"):
                    os.remove(os.path.join(self.persist_dir, filename))

            self.logger.info(f"项目知识库已删除: project_id={project_id}")
            return True

        except Exception as e:
            self.logger.error(
                f"删除项目知识库失败: project_id={project_id}, error={str(e)}")
            return False


