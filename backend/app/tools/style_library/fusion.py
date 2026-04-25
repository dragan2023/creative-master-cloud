"""文风库 - fusion工具函数"""
from typing import Dict, List, Optional
import json
import os

# 从数据目录加载文风数据
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def build_style_guide(style_ids: List[str], intensity: float = 0.7) -> Dict:
    """
    构建风格指南（支持多风格融合）

    Args:
        style_ids: 风格ID列表（最多3个）
        intensity: 风格强度(0.0-1.0)

    Returns:
        融合后的风格指南字典
    """
    if not style_ids:
        return {}

    # 限制最多3个风格
    style_ids = style_ids[:3]

    styles = []
    for sid in style_ids:
        style = get_style_by_id(sid)
        if style:
            styles.append(style)

    if not styles:
        return {}

    # 单风格
    if len(styles) == 1:
        style = styles[0]
        return {
            "style_names": [style["name"]],
            "style_ids": style_ids,
            "intensity": intensity,
            "writing_guide": style["writing_guide"],
            "style_features": style["features"],
            "avoid_patterns": style["avoid_patterns"],
            "examples": style["examples"],
            "description": style["description"]
        }

    # 多风格融合
    # 主风格占60%，其余各占20%（如有2个辅风格则各占20%）
    weights = [0.6] + [0.4 / (len(styles) - 1)] * (len(styles) - 1)

    style_names = [s["name"] for s in styles]

    # 合并写作指南
    combined_guide_parts = []
    for i, (style, weight) in enumerate(zip(styles, weights)):
        if i == 0:
            combined_guide_parts.append(
                f"**主风格 - {style['name']}**（权重{int(weight*100)}%）：\n{style['writing_guide']}")
        else:
            combined_guide_parts.append(
                f"**辅风格 - {style['name']}**（权重{int(weight*100)}%）：\n{style['writing_guide']}")

    combined_guide = "\n\n".join(combined_guide_parts)

    # 合并避免模式（去重）
    all_avoid = []
    for style in styles:
        for pattern in style.get("avoid_patterns", []):
            if pattern not in all_avoid:
                all_avoid.append(pattern)

    # 检查风格兼容性
    compatibility_warnings = _check_style_compatibility(styles)

    return {
        "style_names": style_names,
        "style_ids": style_ids,
        "intensity": intensity,
        "writing_guide": combined_guide,
        "style_features": styles[0]["features"],  # 主风格特征为主
        "avoid_patterns": all_avoid,
        "examples": styles[0]["examples"],
        "description": f"融合风格：{'、'.join(style_names)}",
        "compatibility_warnings": compatibility_warnings
    }



def _check_style_compatibility(styles: List[Dict]) -> List[str]:
    """检查风格兼容性"""
    warnings = []
    style_ids = [s["id"] for s in styles]

    # 已知不兼容的组合
    incompatible_pairs = [
        ("minimalism_lit", "romanticism", "极简主义与浪漫主义在语言密度上存在冲突，建议降低两者强度各50%"),
        ("stream_of_consciousness", "detective_classic", "意识流与古典侦探的逻辑性要求相互矛盾"),
        ("oral_storytelling", "modernism", "口语说书体与现代主义的破碎叙事难以融合"),
    ]

    for id1, id2, warning in incompatible_pairs:
        if id1 in style_ids and id2 in style_ids:
            warnings.append(warning)

    return warnings


