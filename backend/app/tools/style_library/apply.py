"""文风库 - apply工具函数"""
from typing import Dict, List, Optional
import json
import os

# 从数据目录加载文风数据
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


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


