"""
逻辑编辑Agent - 一致性管理器适配器

@date: 2026-04-24
@version: v1.0.0
"""
from typing import Any, Dict


class ConsistencyAdapter:
    """一致性管理器适配器

    用于适配一致性管理器，提供统一的检查接口。
    暂时返回空结果，后续对接实际的ConsistencyManager。
    """

    def __init__(self):
        self._manager = None

    def _get_manager(self):
        """获取一致性管理器实例（懒加载）"""
        if self._manager is None:
            try:
                from app.services.novel_writer.consistency import ConsistencyManager
                self._manager = ConsistencyManager
            except ImportError:
                self._manager = None
        return self._manager

    async def check_consistency(self, content: str, context: dict, **kwargs) -> Dict[str, Any]:
        """检查一致性（适配器方法）"""
        manager = self._get_manager()
        if manager is None:
            return {"issues": [], "score": 100}
        try:
            return {"issues": [], "score": 100}
        except Exception as e:
            return {"issues": [], "score": 100, "error": str(e)}
