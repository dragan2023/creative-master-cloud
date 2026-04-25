"""ProjectKnowledgeBase - initialize_project_kbMixin"""
import re
import os


class InitializeProjectKbMixin:
    """initialize_project_kb功能域"""

    async def initialize_project_kb(self, project_id: int) -> bool:
        """
        初始化项目专属知识库

        Args:
            project_id: 项目ID

        Returns:
            是否成功
        """
        try:
            collection_name = self.get_collection_name(project_id)

            # 创建向量集合
            self.vector_store.get_or_create_collection(collection_name)

            # 确保持久化目录存在
            os.makedirs(self.persist_dir, exist_ok=True)

            self.logger.info(
                f"项目知识库初始化完成: project_id={project_id}, collection={collection_name}")
            return True

        except Exception as e:
            self.logger.error(
                f"初始化项目知识库失败: project_id={project_id}, error={str(e)}")
            return False


