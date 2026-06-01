"""风格相关工具函数

提供风格强度阈值描述的统一转换函数。
阈值定义（与前端滑块保持一致）：
- <=0.4: 淡入-轻微体现
- <=0.7: 适中-明显但不突兀
- >0.7:  强烈-非常突出
"""


def intensity_to_description(intensity: float) -> str:
    """将风格强度(0.0-1.0)转换为人类可读的描述"""
    if intensity <= 0.4:
        return "淡入-轻微体现"
    if intensity <= 0.7:
        return "适中-明显但不突兀"
    return "强烈-非常突出"


def intensity_to_short_label(intensity: float) -> str:
    """将风格强度转换为简短标签"""
    if intensity <= 0.4:
        return "淡入"
    if intensity <= 0.7:
        return "适中"
    return "强烈"


def intensity_to_percent(intensity: float) -> str:
    """将风格强度转换为百分比字符串"""
    return f"{int(intensity * 100)}%"
