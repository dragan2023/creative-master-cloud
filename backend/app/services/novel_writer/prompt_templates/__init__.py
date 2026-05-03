"""
提示词模板定义 - 包入口

将原 prompt_templates.py 拆分为多个功能模块，按内容类型组织。

包结构:
    __init__.py: 统一导出所有提示词常量和函数
    _novel.py: 小说相关模板
    _series.py: 剧集剧本相关模板
    _movie.py: 电影剧本相关模板
    _virtual.py: 虚拟模式（AI视频生成优化）模板
    _utility.py: 通用工具类模板
    _storyboard.py: 分镜设计模板及函数
    _functions.py: 格式化函数 (get_chapter_prompt, get_episode_prompt, get_scene_script_prompt)

@date: 2026-04-24
@version: v2.0.0
"""

from ._novel import (
    NOVEL_CHAPTER_PROMPT,
    DIRECTORY_GENERATE_PROMPT,
    CHAPTER_NAMES_GENERATE_PROMPT,
    CHAPTER_DETAILED_OUTLINE_PROMPT,
)
from ._series import (
    SERIES_SCRIPT_SCENE_PROMPT,
    SERIES_SCRIPT_EPISODE_PROMPT,
    EPISODE_NAMES_GENERATE_PROMPT,
    SCRIPT_DIRECTORY_PROMPT,
    EPISODE_DETAILED_OUTLINE_PROMPT,
)
from ._movie import (
    MOVIE_SCRIPT_SCENE_PROMPT,
    MOVIE_DIRECTORY_PROMPT,
    MOVIE_SCENE_NAMES_PROMPT,
    SCENE_DETAILED_OUTLINE_PROMPT,
)
from ._virtual import (
    SERIES_SCRIPT_VIRTUAL_PROMPT,
    MOVIE_SCRIPT_VIRTUAL_PROMPT,
)
from ._utility import (
    SUMMARY_UPDATE_PROMPT,
    CHARACTER_UPDATE_PROMPT,
    CONSISTENCY_CHECK_PROMPT,
    KNOWLEDGE_FILTER_PROMPT,
    SEARCH_KEYWORD_PROMPT,
)
from ._storyboard import (
    STORYBOARD_REAL_MODE_PROMPT,
    STORYBOARD_VIRTUAL_MODE_PROMPT,
    get_storyboard_prompt,
)
from ._functions import (
    get_chapter_prompt,
    get_episode_prompt,
    get_scene_script_prompt,
)

# 兼容旧版别名
from ._series import SERIES_SCRIPT_SCENE_PROMPT as SCRIPT_SCENE_PROMPT

__all__ = [
    "NOVEL_CHAPTER_PROMPT",
    "DIRECTORY_GENERATE_PROMPT",
    "CHAPTER_NAMES_GENERATE_PROMPT",
    "CHAPTER_DETAILED_OUTLINE_PROMPT",
    "SERIES_SCRIPT_SCENE_PROMPT",
    "SERIES_SCRIPT_EPISODE_PROMPT",
    "EPISODE_NAMES_GENERATE_PROMPT",
    "SCRIPT_DIRECTORY_PROMPT",
    "EPISODE_DETAILED_OUTLINE_PROMPT",
    "MOVIE_SCRIPT_SCENE_PROMPT",
    "MOVIE_DIRECTORY_PROMPT",
    "MOVIE_SCENE_NAMES_PROMPT",
    "SCENE_DETAILED_OUTLINE_PROMPT",
    "SERIES_SCRIPT_VIRTUAL_PROMPT",
    "MOVIE_SCRIPT_VIRTUAL_PROMPT",
    "SUMMARY_UPDATE_PROMPT",
    "CHARACTER_UPDATE_PROMPT",
    "CONSISTENCY_CHECK_PROMPT",
    "KNOWLEDGE_FILTER_PROMPT",
    "SEARCH_KEYWORD_PROMPT",
    "STORYBOARD_REAL_MODE_PROMPT",
    "STORYBOARD_VIRTUAL_MODE_PROMPT",
    "SCRIPT_SCENE_PROMPT",
    "get_chapter_prompt",
    "get_episode_prompt",
    "get_scene_script_prompt",
    "get_storyboard_prompt",
]
