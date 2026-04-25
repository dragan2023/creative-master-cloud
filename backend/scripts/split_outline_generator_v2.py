"""
第二轮拆分：将超标Mixin进一步拆分，并合理分配_misc中的方法

最终目标：每个文件 ≤500行（有效代码≤400行）
"""
import re
from pathlib import Path

BASE_DIR = Path(r"f:\python_project\全能创意大师（开发版）\backend\app\services\outline_generator")
FULL_FILE = BASE_DIR / "impl" / "_full.py"
MIXINS_DIR = BASE_DIR / "impl" / "mixins"

# 重新定义方法分组 - 更细粒度的拆分
METHOD_GROUPS = {
    "parser": {
        "description": "大纲解析与格式化工具",
        "methods": [
            "parse_unit_summaries",
            "_parse_novel_chapters",
            "_parse_script_episodes",
            "get_expected_unit_count",
            "_parse_unit_count_from_outline",
            "detect_truncated_units",
            "_check_unit_completeness",
            "save_outline_to_file",  # from _misc
        ]
    },
    "global_outline": {
        "description": "全局大纲生成",
        "methods": [
            "generate_global_outline",
            "generate_global_outline_stream",
        ]
    },
    "unit_summary_core": {
        "description": "单元概述生成（主要API方法）",
        "methods": [
            "generate_unit_summaries",
            "generate_unit_summaries_stream",
        ]
    },
    "unit_summary_resume": {
        "description": "单元概述续生成与缺失单元补全",
        "methods": [
            "continue_unit_summaries_generation",
            "_generate_missing_units",
            "_generate_units_batch",
            "_build_previous_units_reference",
        ]
    },
    "unit_summary_helpers": {
        "description": "单元概述续生成辅助方法",
        "methods": [
            "_continue_single_unit",
            "_validate_continuation_quality",
            "_build_resume_context",
            "_build_resume_prompt",
            "_extract_structured_context",  # from _misc
        ]
    },
    "revision": {
        "description": "知识库修正与逻辑性修正",
        "methods": [
            "_revise_with_knowledge_base",
            "check_and_fix_logic_issues",
            "_format_unit_summaries_for_check",  # from _misc
            "_parse_logic_check_response",
        ]
    },
    "revision_auto": {
        "description": "自动质控修正与质量修正辅助",
        "methods": [
            "_auto_qc_and_revise",
            "_build_quality_revision_prompt",
            "_parse_quality_revision_result",
            "_build_revised_content",
        ]
    },
    "qc_unit_analysis": {
        "description": "单元概述质量分析",
        "methods": [
            "_analyze_unit_summaries_quality",
            "_format_all_units",  # from _misc
        ]
    },
    "qc_layered": {
        "description": "分层质量管控与一致性检测",
        "methods": [
            "_perform_layered_quality_control",
            "_check_resume_boundary",
            "_check_global_consistency_incremental",
        ]
    },
    "qc_global_analysis": {
        "description": "全局大纲质量分析",
        "methods": [
            "analyze_global_outline_quality",
            "_analyze_global_outline_dimensions",  # from _misc
            "_generate_global_outline_smart_suggestions",  # from _misc
        ]
    },
    "qc_global_revision": {
        "description": "全局大纲质量修正",
        "methods": [
            "revise_global_outline_by_quality",
            "_build_global_outline_revision_prompt",  # from _misc
            "_clean_revised_content",
        ]
    },
    "qc_unit_manual": {
        "description": "手动模式单元概述质控与修正",
        "methods": [
            "analyze_unit_summaries_quality_manual",
            "revise_unit_summaries_quality",
        ]
    },
}


def parse_methods(content: str) -> dict:
    """解析文件中所有方法定义及其行号范围"""
    lines = content.split('\n')
    methods = {}
    pattern = re.compile(r'^    (async )?def (\w+)\(')
    method_starts = []
    for i, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            method_name = m.group(2)
            method_starts.append((i + 1, method_name))
    for idx, (start_line, name) in enumerate(method_starts):
        if idx + 1 < len(method_starts):
            end_line = method_starts[idx + 1][0] - 1
        else:
            end_line = len(lines)
            for i in range(len(lines) - 1, start_line - 1, -1):
                if lines[i - 1].strip():
                    end_line = i
                    break
        methods[name] = (start_line, end_line)
    return methods


def analyze_needed_imports(method_content: str) -> str:
    """分析方法内容中使用的符号，返回必要的import语句"""
    keyword_import_map = {
        'AsyncSession': 'from sqlalchemy.ext.asyncio import AsyncSession',
        'AsyncGenerator': 'from typing import AsyncGenerator',
        'Dict': 'from typing import Dict',
        'List': 'from typing import List',
        'Optional': 'from typing import Optional',
        'Any': 'from typing import Any',
        'datetime': 'from datetime import datetime',
        'json': 'import json',
        're': 'import re',
        'os': 'import os',
        'get_llm_manager': 'from app.agents.llm_manager import get_llm_manager',
        'LLMManager': 'from app.agents.llm_manager import LLMManager',
        'get_prompt_manager': 'from app.agents.prompt_manager import get_prompt_manager',
        'PromptManager': 'from app.agents.prompt_manager import PromptManager',
        'process_input_params_files': 'from app.agents.orchestrator import process_input_params_files',
        'get_logger': 'from app.core.logger import get_logger',
        'get_settings': 'from app.core.config import get_settings',
        'get_knowledge_retrieval_tool': 'from app.tools.knowledge_retrieval import get_knowledge_retrieval_tool',
        'get_agent_orchestrator': 'from app.agents.orchestrator import get_agent_orchestrator',
        'ENABLE_QUALITY_CONTROL': 'from app.services.outline_generator.api.constants import ENABLE_QUALITY_CONTROL',
        'MIN_REVISION_LENGTH': 'from app.services.outline_generator.api.constants import MIN_REVISION_LENGTH',
        'OUTLINE_REVISION_PROMPT': 'from app.services.outline_generator.api.constants import OUTLINE_REVISION_PROMPT',
        'LOGIC_CHECK_PROMPT': 'from app.services.outline_generator.api.constants import LOGIC_CHECK_PROMPT',
        'QualityControlService': 'from app.services.quality_control import QualityControlService',
    }
    needed = []
    for keyword, import_line in keyword_import_map.items():
        if keyword in method_content:
            if import_line not in needed:
                needed.append(import_line)
    return '\n'.join(needed)


def main():
    print("=" * 60)
    print("大纲生成器 - 第二轮精细拆分")
    print("=" * 60)

    content = FULL_FILE.read_text(encoding='utf-8')
    lines = content.split('\n')
    methods = parse_methods(content)

    # 清空mixins目录中的旧文件
    for f in MIXINS_DIR.glob("*.py"):
        f.unlink()
    
    all_assigned = set()
    created_files = []
    violations = []

    for group_name, group_info in METHOD_GROUPS.items():
        method_names = group_info["methods"]
        valid_methods = [m for m in method_names if m in methods]
        
        if not valid_methods:
            continue

        method_contents = []
        for mname in valid_methods:
            start, end = methods[mname]
            method_contents.append('\n'.join(lines[start - 1:end]))
            all_assigned.add(mname)

        combined_content = '\n'.join(method_contents)
        needed_imports = analyze_needed_imports(combined_content)
        
        class_name = "".join(part.capitalize() for part in group_name.split('_')) + "Mixin"
        
        mixin_content = f'"""大纲生成器 - {group_info["description"]}Mixin"""\n'
        mixin_content += needed_imports + '\n\n\n'
        mixin_content += f'class {class_name}:\n'
        mixin_content += f'    """{group_info["description"]}"""\n\n'
        
        for mc in method_contents:
            lines_mc = mc.split('\n')
            while lines_mc and not lines_mc[-1].strip():
                lines_mc.pop()
            mixin_content += '\n'.join(lines_mc) + '\n\n\n'
        
        total_lines = len(mixin_content.split('\n'))
        status = "✅" if total_lines <= 500 else "⚠️ "
        if total_lines > 500:
            violations.append((group_name, total_lines))
        
        mixin_file = MIXINS_DIR / f"{group_name}.py"
        mixin_file.write_text(mixin_content, encoding='utf-8')
        created_files.append(mixin_file)
        print(f"\n{status} 创建: {mixin_file.name} ({total_lines}行, {len(valid_methods)}个方法)")
        for mname in valid_methods:
            start, end = methods[mname]
            print(f"   - {mname}: L{start}-L{end}")

    # 检查未分配的方法
    unassigned = set(methods.keys()) - all_assigned - {'__init__', '_format_sse'}
    if unassigned:
        print(f"\n⚠️ 未分配的方法: {unassigned}")

    # 创建 __init__.py
    init_content = '"""大纲生成器 - Mixin模块"""\n'
    for group_name in METHOD_GROUPS.keys():
        class_name = "".join(part.capitalize() for part in group_name.split('_')) + "Mixin"
        init_content += f'from app.services.outline_generator.impl.mixins.{group_name} import {class_name}\n'
    
    init_file = MIXINS_DIR / "__init__.py"
    init_file.write_text(init_content, encoding='utf-8')
    print(f"\n✅ 创建: __init__.py")

    # 更新 generator.py
    all_mixin_classes = []
    for group_name in METHOD_GROUPS.keys():
        class_name = "".join(part.capitalize() for part in group_name.split('_')) + "Mixin"
        all_mixin_classes.append(class_name)

    generator_content = '''"""大纲生成器 - 主类（组合所有Mixin）"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.agents.llm_manager import get_llm_manager, LLMManager
from app.agents.prompt_manager import get_prompt_manager, PromptManager
from app.services.outline_generator.impl.mixins import (
'''
    for cls in all_mixin_classes:
        generator_content += f'    {cls},\n'
    
    generator_content += ''')


class OutlineGenerator(
    ParserMixin,
    GlobalOutlineMixin,
    UnitSummaryCoreMixin,
    UnitSummaryResumeMixin,
    UnitSummaryHelpersMixin,
    RevisionMixin,
    RevisionAutoMixin,
    QcUnitAnalysisMixin,
    QcLayeredMixin,
    QcGlobalAnalysisMixin,
    QcGlobalRevisionMixin,
    QcUnitManualMixin,
):
    """大纲生成器（两阶段） - 组合Mixin实现"""

    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.logger = get_logger(__name__)
        self.prompt_manager = get_prompt_manager()
        self.llm_manager = get_llm_manager()

    def _format_sse(self, event_type: str, data: dict) -> str:
        """格式化 SSE 事件"""
        import json
        return f"event: {event_type}\\ndata: {json.dumps(data, ensure_ascii=False)}\\n\\n"


# 全局实例
_outline_generator = None


def get_outline_generator(db: AsyncSession = None) -> "OutlineGenerator":
    """获取大纲生成器实例"""
    global _outline_generator
    if _outline_generator is None:
        _outline_generator = OutlineGenerator(db)
    elif db is not None:
        _outline_generator.db = db
    return _outline_generator
'''
    
    generator_file = BASE_DIR / "impl" / "generator.py"
    generator_file.write_text(generator_content, encoding='utf-8')
    print(f"\n✅ 更新: generator.py")

    # 更新 impl/__init__.py
    init_impl = '''"""大纲生成器 - 实现层"""
from app.services.outline_generator.impl.generator import OutlineGenerator

__all__ = ["OutlineGenerator"]
'''
    init_impl_file = BASE_DIR / "impl" / "__init__.py"
    init_impl_file.write_text(init_impl, encoding='utf-8')
    print(f"\n✅ 更新: impl/__init__.py")

    # 输出总结
    print("\n" + "=" * 60)
    print("拆分总结:")
    print("=" * 60)
    print(f"原始: _full.py (5129行)")
    print(f"拆分后: {len(created_files)}个Mixin文件 + generator.py")
    if violations:
        print(f"\n⚠️ 仍超标文件 (>500行):")
        for name, lines in violations:
            print(f"   - {name}.py: {lines}行")
    else:
        print("\n✅ 所有文件均 ≤500行")


if __name__ == '__main__':
    main()
