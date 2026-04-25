"""CharacterStateTracker - saveMixin"""
from __future__ import annotations
from typing import Optional
import json
import re
import os


class SaveMixin:
    """save功能域"""

    async def save(self, file_path: Optional[str] = None) -> bool:
        """保存追踪器状态到文件

        Args:
            file_path: 保存路径（可选，默认使用persist_dir）

        Returns:
            是否保存成功
        """
        if file_path is None:
            if self.persist_dir is None:
                self.logger.warning("未指定保存路径，无法保存追踪器状态")
                return False
            file_path = os.path.join(
                self.persist_dir,
                f"character_state_tracker_{self.project_id}.json"
            )

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            data = self.export_to_dict()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"追踪器状态已保存: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"保存追踪器状态失败: {e}")
            return False


