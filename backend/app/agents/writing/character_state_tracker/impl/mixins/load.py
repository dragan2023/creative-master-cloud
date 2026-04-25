"""CharacterStateTracker - loadMixin"""
from __future__ import annotations
from typing import Optional
import json
import re
import os


class LoadMixin:
    """load功能域"""

    async def load(self, file_path: Optional[str] = None) -> bool:
        """从文件加载追踪器状态

        Args:
            file_path: 加载路径（可选，默认使用persist_dir）

        Returns:
            是否加载成功
        """
        if file_path is None:
            if self.persist_dir is None:
                self.logger.warning("未指定加载路径，无法加载追踪器状态")
                return False
            file_path = os.path.join(
                self.persist_dir,
                f"character_state_tracker_{self.project_id}.json"
            )

        if not os.path.exists(file_path):
            self.logger.info(f"追踪器状态文件不存在: {file_path}")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.import_from_dict(data)
            self.logger.info(f"追踪器状态已加载: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"加载追踪器状态失败: {e}")
            return False


