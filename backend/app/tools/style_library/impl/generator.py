"""StyleLibrary - 主类（组合所有Mixin）"""
from app.core.logger import get_logger


class StyleLibrary:
    """StyleLibrary - 组合Mixin实现"""

    def __init__(self):
        pass


# 全局实例
_instance = None


def get_style_library() -> "StyleLibrary":
    """获取StyleLibrary实例"""
    global _instance
    if _instance is None:
        _instance = StyleLibrary()
    return _instance
