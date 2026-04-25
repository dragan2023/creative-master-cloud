"""UnitQualityAnalyzer - 主类（组合所有Mixin）"""
from app.core.logger import get_logger


class UnitQualityAnalyzer:
    """UnitQualityAnalyzer - 组合Mixin实现"""

    def __init__(self):
        pass


# 全局实例
_instance = None


def get_unit_quality_analyzer() -> "UnitQualityAnalyzer":
    """获取UnitQualityAnalyzer实例"""
    global _instance
    if _instance is None:
        _instance = UnitQualityAnalyzer()
    return _instance
