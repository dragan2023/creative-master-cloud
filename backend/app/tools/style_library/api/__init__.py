"""StyleLibrary - API层"""
from app.tools.style_library import STYLE_LIBRARY

def get_style_by_id(style_id: str) -> Optional[Dict]:
    """根据ID获取文风详情"""
    for category in STYLE_LIBRARY["categories"].values():
        for style in category["styles"]:
            if style["id"] == style_id:
                return style
    return None

def get_styles_by_category(category: str) -> List[Dict]:
    """获取分类下的所有文风"""
    if category in STYLE_LIBRARY["categories"]:
        return STYLE_LIBRARY["categories"][category]["styles"]
    return []

def get_all_categories() -> Dict:
    """获取所有分类信息（不含具体风格数据）"""
    result = {}
    for cat_id, cat_data in STYLE_LIBRARY["categories"].items():
        result[cat_id] = {
            "name": cat_data["name"],
            "description": cat_data["description"],
            "count": len(cat_data["styles"])
        }
    return result

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

def apply_style_to_project_metadata(project_metadata: Dict, style_ids: List[str], intensity: float = 0.7) -> Dict:
    """将文风配置应用到项目元数据中

    Args:
        project_metadata: 项目元数据字典
        style_ids: 文风ID列表
        intensity: 风格强度(0.0-1.0)

    Returns:
        更新后的项目元数据
    """
    if not style_ids:
        return project_metadata

    # 构建风格指南
    style_guide = build_style_guide(style_ids, intensity)
    if not style_guide:
        return project_metadata

    # 保存到项目元数据
    project_metadata["writing_styles"] = style_ids
    project_metadata["style_intensity"] = intensity
    project_metadata["style_library_guide"] = style_guide

    return project_metadata

def get_style_guide_from_project(project_metadata: Dict) -> Optional[Dict]:
    """从项目元数据中获取文风配置

    Args:
        project_metadata: 项目元数据字典

    Returns:
        style_library_guide字典,如果没有则返回None
    """
    return project_metadata.get("style_library_guide")

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

    intensity = style_guide.get("intensity", 0.7)
    intensity_desc = "淡入" if intensity < 0.4 else (
        "强烈" if intensity > 0.8 else "适中")
    parts.append(f"**风格强度**: {intensity_desc}({int(intensity * 100)}%)")

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

