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

            # 3. 删除一致性状态文件（v6.1 修复：使用项目级文件名）
            consistency_state_path = os.path.join(
                self.persist_dir, f"consistency_state_project_{project_id}.json")
            if os.path.exists(consistency_state_path):
                os.remove(consistency_state_path)
                self.logger.info(f"已删除项目一致性状态文件: project_id={project_id}")

            # 3.1 清理旧版共享一致性状态文件（向后兼容，v6.1 之前版本遗留的污染文件）
            legacy_consistency_path = os.path.join(self.persist_dir, "consistency_state.json")
            if os.path.exists(legacy_consistency_path):
                self.logger.warning(
                    f"发现旧版共享一致性状态文件，正在清理: {legacy_consistency_path}")
                os.remove(legacy_consistency_path)

            # 4. 删除旧版事件状态索引（兼容）
            old_event_path = os.path.join(self.persist_dir, "event_status_index.json")
            if os.path.exists(old_event_path):
                os.remove(old_event_path)

            self.logger.info(f"项目知识库已删除: project_id={project_id}")
            return True

        except Exception as e:
            self.logger.error(
                f"删除项目知识库失败: project_id={project_id}, error={str(e)}")
            return False


