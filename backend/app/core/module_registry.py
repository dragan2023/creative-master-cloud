"""
创意模块配置注册表

统一管理所有创意模块的配置信息，新增模块只需在此注册。

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Optional, List
from pydantic import BaseModel


class ModuleConfig(BaseModel):
    """创意模块配置"""
    module_id: str           # 模块标识（与 GenerationModule 枚举值一致）
    display_name: str        # 前端显示名称
    api_path: str            # API流式生成路径
    kb_category: str         # 知识库分类键
    supports_knowledge: bool = True
    supports_search: bool = True
    supports_trending: bool = True
    supports_mcp: bool = False
    supports_images: bool = False
    supports_videos: bool = False


# 创意模块配置注册表
# 根据 GenerationModule 枚举值和 KnowledgeBaseCategory 填充
MODULE_REGISTRY: Dict[str, ModuleConfig] = {
    # 短视频脚本
    "short_video": ModuleConfig(
        module_id="short_video",
        display_name="短视频脚本",
        api_path="/api/v1/generate/short-video/stream",
        kb_category="short-video",
        supports_knowledge=True,
        supports_search=True,
        supports_trending=True,
        supports_mcp=True,
        supports_images=False,
        supports_videos=True,  # 支持参考视频
    ),
    # 电影大纲
    "movie_outline": ModuleConfig(
        module_id="movie_outline",
        display_name="电影大纲",
        api_path="/api/v1/generate/movie-outline/stream",
        kb_category="movie-outline",
        supports_knowledge=True,
        supports_search=True,
        supports_trending=True,
        supports_mcp=True,
        supports_images=False,
        supports_videos=False,
    ),
    # 剧集大纲
    "series_outline": ModuleConfig(
        module_id="series_outline",
        display_name="剧集大纲",
        api_path="/api/v1/generate/series-outline/stream",
        kb_category="series-outline",
        supports_knowledge=True,
        supports_search=True,
        supports_trending=True,
        supports_mcp=True,
        supports_images=False,
        supports_videos=False,
    ),
    # 小说大纲
    "novel": ModuleConfig(
        module_id="novel",
        display_name="小说大纲",
        api_path="/api/v1/generate/novel/stream",
        kb_category="novel",
        supports_knowledge=True,
        supports_search=True,
        supports_trending=True,
        supports_mcp=True,
        supports_images=False,
        supports_videos=False,
    ),
    # 平面广告
    "print_ad": ModuleConfig(
        module_id="print_ad",
        display_name="平面广告",
        api_path="/api/v1/generate/print-ad/stream",
        kb_category="print-ad",
        supports_knowledge=True,
        supports_search=True,
        supports_trending=True,
        supports_mcp=True,
        supports_images=True,  # 支持参考图片
        supports_videos=False,
    ),
    # TVC广告脚本
    "tvc": ModuleConfig(
        module_id="tvc",
        display_name="TVC广告脚本",
        api_path="/api/v1/generate/tvc/stream",
        kb_category="tvc",
        supports_knowledge=True,
        supports_search=True,
        supports_trending=True,
        supports_mcp=True,
        supports_images=False,
        supports_videos=True,  # 支持参考视频
    ),
    # 原创IP计划
    "original_ip": ModuleConfig(
        module_id="original_ip",
        display_name="原创IP计划",
        api_path="/api/v1/generate/original-ip/stream",
        kb_category="general",  # IP计划使用通用知识库
        supports_knowledge=True,
        supports_search=True,
        supports_trending=False,
        supports_mcp=False,
        supports_images=False,
        supports_videos=False,
    ),
}


def get_module_config(module_id: str) -> ModuleConfig:
    """
    获取模块配置
    
    Args:
        module_id: 模块标识符
        
    Returns:
        ModuleConfig: 模块配置对象
        
    Raises:
        ValueError: 如果模块不存在
    """
    if module_id not in MODULE_REGISTRY:
        raise ValueError(f"未知的创意模块: {module_id}")
    return MODULE_REGISTRY[module_id]


def get_all_module_ids() -> List[str]:
    """
    获取所有已注册的模块ID
    
    Returns:
        List[str]: 模块ID列表
    """
    return list(MODULE_REGISTRY.keys())


def get_module_display_name(module_id: str) -> str:
    """
    获取模块显示名称
    
    Args:
        module_id: 模块标识符
        
    Returns:
        str: 模块显示名称
        
    Raises:
        ValueError: 如果模块不存在
    """
    config = get_module_config(module_id)
    return config.display_name


def get_module_by_kb_category(kb_category: str) -> Optional[ModuleConfig]:
    """
    根据知识库分类获取模块配置
    
    Args:
        kb_category: 知识库分类键
        
    Returns:
        Optional[ModuleConfig]: 模块配置对象，未找到返回 None
    """
    for config in MODULE_REGISTRY.values():
        if config.kb_category == kb_category:
            return config
    return None


def get_modules_by_feature(feature: str) -> List[ModuleConfig]:
    """
    根据功能特性获取支持的模块列表
    
    Args:
        feature: 功能特性名称 (supports_knowledge, supports_search, 
                supports_trending, supports_mcp, supports_images, supports_videos)
                
    Returns:
        List[ModuleConfig]: 支持该特性的模块列表
    """
    feature_map = {
        "knowledge": "supports_knowledge",
        "search": "supports_search",
        "trending": "supports_trending",
        "mcp": "supports_mcp",
        "images": "supports_images",
        "videos": "supports_videos",
    }
    
    attr_name = feature_map.get(feature, feature)
    return [
        config for config in MODULE_REGISTRY.values()
        if getattr(config, attr_name, False)
    ]


# 向后兼容的常量定义（用于硬编码场景）
# 推荐使用 get_module_config() 函数获取配置
MODULE_SHORT_VIDEO = "short_video"
MODULE_SCRIPT = "script"  # [DEPRECATED] 剧本大纲已移除，保留用于向后兼容
MODULE_NOVEL = "novel"
MODULE_PRINT_AD = "print_ad"
MODULE_TVC = "tvc"
MODULE_ORIGINAL_IP = "original_ip"
MODULE_MOVIE_OUTLINE = "movie_outline"
MODULE_SERIES_OUTLINE = "series_outline"
