"""文风库 - query工具函数"""
from typing import Dict, List, Optional
import json
import os

from app.tools.style_library import STYLE_LIBRARY

# 从数据目录加载文风数据
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


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


