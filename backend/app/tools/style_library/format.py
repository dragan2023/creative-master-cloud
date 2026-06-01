"""文风库 - format工具函数"""
from typing import Dict, List, Optional
import json
import os

from app.tools.style_library import STYLE_LIBRARY

# 从数据目录加载文风数据
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def format_style_for_prompt(style_guide: Dict) -> str:
    """将风格指南格式化为提示词文本"""
    if not style_guide:
        return ""

    parts = []

    style_names = style_guide.get("style_names", [])
    if style_names:
        parts.append(f"**写作风格**: {'、'.join(style_names)}")

    description = style_guide.get("description", "")
    if description:
        parts.append(f"**风格简介**: {description}")

    from app.utils.style_utils import intensity_to_description, intensity_to_percent
    intensity = style_guide.get("intensity", 0.7)
    intensity_desc = intensity_to_description(intensity)
    parts.append(f"**风格强度**: {intensity_desc}({intensity_to_percent(intensity)})")

    # 核心特征
    features = style_guide.get("style_features", {})
    if features:
        parts.append("\n**核心风格特征**:")

        vocab = features.get("vocabulary", {})
        if vocab.get("word_preference"):
            parts.append(f"- 用词偏好: {vocab['word_preference']}")
        if vocab.get("avoid"):
            avoids = vocab["avoid"] if isinstance(
                vocab["avoid"], list) else [vocab["avoid"]]
            parts.append(f"- 避免用词: {', '.join(avoids)}")

        sentence = features.get("sentence_structure", {})
        if sentence.get("preferred_patterns"):
            parts.append(
                f"- 句式偏好: {', '.join(sentence['preferred_patterns'])}")
        if sentence.get("avg_length"):
            parts.append(f"- 句子长度: {sentence['avg_length']}")

        narrative = features.get("narrative_style", {})
        if narrative.get("perspective"):
            parts.append(f"- 叙事视角: {narrative['perspective']}")
        if narrative.get("focus"):
            parts.append(f"- 叙事重点: {narrative['focus']}")

        if features.get("description_style"):
            parts.append(f"- 描写风格: {features['description_style']}")

        if features.get("dialogue_style"):
            parts.append(f"- 对话风格: {features['dialogue_style']}")

        if features.get("emotional_expression"):
            parts.append(f"- 情感表达: {features['emotional_expression']}")

    # 写作指南
    writing_guide = style_guide.get("writing_guide", "")
    if writing_guide:
        parts.append(f"\n**写作指导**:\n{writing_guide}")

    # 避免模式
    avoid_patterns = style_guide.get("avoid_patterns", [])
    if avoid_patterns:
        parts.append(f"\n**必须避免**:\n" +
                     "\n".join(f"- {p}" for p in avoid_patterns))

    # 兼容性警告
    warnings = style_guide.get("compatibility_warnings", [])
    if warnings:
        parts.append(f"\n**风格融合注意事项**:\n" +
                     "\n".join(f"⚠️ {w}" for w in warnings))

    return "\n".join(parts)


def _intensity_to_description(intensity: float) -> str:
    """将风格强度(0.0-1.0)转换为人类可读的描述

    与前端强度滑块阈值保持一致：
    - <=0.4 → 淡入-轻微体现
    - <=0.7 → 适中-明显但不突兀
    - >0.7  → 强烈-非常突出

    Args:
        intensity: 风格强度，范围 0.0-1.0

    Returns:
        中文描述字符串
    """
    if intensity <= 0.4:
        return "淡入-轻微体现"
    if intensity <= 0.7:
        return "适中-明显但不突兀"
    return "强烈-非常突出"


def get_style_list_for_api(category: Optional[str] = None) -> List[Dict]:
    """获取文风列表（用于API返回，简化版）"""
    result = []

    categories_to_fetch = [category] if category else list(
        STYLE_LIBRARY["categories"].keys())

    for cat_id in categories_to_fetch:
        if cat_id not in STYLE_LIBRARY["categories"]:
            continue
        cat_data = STYLE_LIBRARY["categories"][cat_id]
        for style in cat_data["styles"]:
            result.append({
                "id": style["id"],
                "name": style["name"],
                "description": style["description"],
                "category": cat_id,
                "category_name": cat_data["name"],
                "examples": style.get("examples", [])
            })

    return result

