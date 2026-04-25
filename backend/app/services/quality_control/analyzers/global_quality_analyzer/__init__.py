"""
全局大纲专用质量管控分析器 v1.1

专门针对全局大纲的特点设计，与单元概述质控模块完全独立。

从原始 global_quality_analyzer.py (1495行) 拆分为以下模块：
- _common.py: 公共工具函数（JSON清理、LLM调用）
- _structure.py: GlobalStructureAnalyzer - 宏观结构层分析
- _character.py: GlobalCharacterWorldviewAnalyzer - 人物与世界观层分析
- _plot.py: GlobalPlotConsistencyAnalyzer - 剧情线一致性分析
- _storyline.py: GlobalStorylineIntegrityAnalyzer - 故事线完整性分析

@date: 2026-04-24
@version: v1.1.0
"""
from ._common import clean_json_string, parse_llm_json_response, call_llm_with_retry
from ._structure import GlobalStructureAnalyzer
from ._character import GlobalCharacterWorldviewAnalyzer
from ._plot import GlobalPlotConsistencyAnalyzer
from ._storyline import GlobalStorylineIntegrityAnalyzer

__all__ = [
    "clean_json_string",
    "parse_llm_json_response",
    "call_llm_with_retry",
    "GlobalStructureAnalyzer",
    "GlobalCharacterWorldviewAnalyzer",
    "GlobalPlotConsistencyAnalyzer",
    "GlobalStorylineIntegrityAnalyzer",
]
