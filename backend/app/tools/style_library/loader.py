"""文风库 - 数据加载器"""
import json
import os
from typing import Dict, List, Optional

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_style_library() -> Dict:
    """加载完整的文风库数据"""
    meta_path = os.path.join(_DATA_DIR, "_meta.json")
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    
    categories = {}
    for cat_file in os.listdir(_DATA_DIR):
        if cat_file.endswith('.json') and cat_file != '_meta.json':
            cat_key = cat_file[:-5]  # 去掉.json
            with open(os.path.join(_DATA_DIR, cat_file), 'r', encoding='utf-8') as f:
                categories[cat_key] = json.load(f)
    
    return {
        **meta,
        "categories": categories
    }


# 模块级缓存
_STYLE_LIBRARY = None


def get_style_library() -> Dict:
    """获取文风库数据（带缓存）"""
    global _STYLE_LIBRARY
    if _STYLE_LIBRARY is None:
        _STYLE_LIBRARY = _load_style_library()
    return _STYLE_LIBRARY


# 兼容性：保持STYLE_LIBRARY可导入
STYLE_LIBRARY = property(lambda self: get_style_library())
