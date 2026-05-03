# -*- coding: utf-8 -*-
"""
提示词模板包 - 合并所有子模块模板
"""

from .short_video import TEMPLATE as _short_video_TEMPLATE
from .novel import TEMPLATE as _novel_TEMPLATE
from .novel_global_outline import TEMPLATE as _novel_global_outline_TEMPLATE
from .novel_unit_summaries import TEMPLATE as _novel_unit_summaries_TEMPLATE
from .movie_outline import TEMPLATE as _movie_outline_TEMPLATE
from .movie_outline_global_outline import TEMPLATE as _movie_outline_global_outline_TEMPLATE
from .movie_outline_unit_summaries import TEMPLATE as _movie_outline_unit_summaries_TEMPLATE
from .series_outline import TEMPLATE as _series_outline_TEMPLATE
from .series_outline_global_outline import TEMPLATE as _series_outline_global_outline_TEMPLATE
from .series_outline_unit_summaries import TEMPLATE as _series_outline_unit_summaries_TEMPLATE
from .print_ad import TEMPLATE as _print_ad_TEMPLATE
from .tvc import TEMPLATE as _tvc_TEMPLATE
from .original_ip import TEMPLATE as _original_ip_TEMPLATE


DEFAULT_PROMPTS = {
    "short_video": _short_video_TEMPLATE,
    "novel": _novel_TEMPLATE,
    "novel_global_outline": _novel_global_outline_TEMPLATE,
    "novel_unit_summaries": _novel_unit_summaries_TEMPLATE,
    "movie_outline": _movie_outline_TEMPLATE,
    "movie_outline_global_outline": _movie_outline_global_outline_TEMPLATE,
    "movie_outline_unit_summaries": _movie_outline_unit_summaries_TEMPLATE,
    "series_outline": _series_outline_TEMPLATE,
    "series_outline_global_outline": _series_outline_global_outline_TEMPLATE,
    "series_outline_unit_summaries": _series_outline_unit_summaries_TEMPLATE,
    "print_ad": _print_ad_TEMPLATE,
    "tvc": _tvc_TEMPLATE,
    "original_ip": _original_ip_TEMPLATE,
}

