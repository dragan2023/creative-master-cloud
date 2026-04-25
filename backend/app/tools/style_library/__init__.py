"""小说文风知识库

此包替代原 style_library.py 单文件，保持完全向后兼容。

使用方式不变：
    from app.tools.style_library import STYLE_LIBRARY, get_style_by_id
"""
import os
from typing import Dict, List, Optional

# 数据目录
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_style_library() -> Dict:
    """懒加载文风库数据"""
    import json
    meta_path = os.path.join(_DATA_DIR, "_meta.json")
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    
    categories = {}
    if os.path.isdir(_DATA_DIR):
        for cat_file in os.listdir(_DATA_DIR):
            if cat_file.endswith('.json') and cat_file != '_meta.json':
                cat_key = cat_file[:-5]
                with open(os.path.join(_DATA_DIR, cat_file), 'r', encoding='utf-8') as f:
                    categories[cat_key] = json.load(f)
    
    return {**meta, "categories": categories}


# 兼容原模块的STYLE_LIBRARY变量
# 首次访问时自动加载
_STYLE_LIBRARY_CACHE = None


def _get_style_library():
    global _STYLE_LIBRARY_CACHE
    if _STYLE_LIBRARY_CACHE is None:
        _STYLE_LIBRARY_CACHE = _load_style_library()
    return _STYLE_LIBRARY_CACHE


class _StyleLibraryProxy(dict):
    """代理dict，首次访问时自动加载"""
    def __init__(self):
        super().__init__()
        self._loaded = False
    
    def _ensure_loaded(self):
        if not self._loaded:
            self.update(_get_style_library())
            self._loaded = True
    
    def __getitem__(self, key):
        self._ensure_loaded()
        return super().__getitem__(key)
    
    def __contains__(self, key):
        self._ensure_loaded()
        return super().__contains__(key)
    
    def keys(self):
        self._ensure_loaded()
        return super().keys()
    
    def values(self):
        self._ensure_loaded()
        return super().values()
    
    def items(self):
        self._ensure_loaded()
        return super().items()
    
    def get(self, key, default=None):
        self._ensure_loaded()
        return super().get(key, default)


STYLE_LIBRARY = _StyleLibraryProxy()


# 导出工具函数
from app.tools.style_library.query import get_style_by_id, get_styles_by_category, get_all_categories
from app.tools.style_library.fusion import build_style_guide, _check_style_compatibility
from app.tools.style_library.apply import apply_style_to_project_metadata, get_style_guide_from_project
from app.tools.style_library.format import format_style_for_prompt, get_style_list_for_api

__all__ = [
    "STYLE_LIBRARY",
    "get_style_by_id", "get_styles_by_category", "get_all_categories",
    "build_style_guide", "_check_style_compatibility",
    "apply_style_to_project_metadata", "get_style_guide_from_project",
    "format_style_for_prompt", "get_style_list_for_api",
]
