"""
自动拆分 outline_generator/_full.py 为 Mixin 模块的脚本

功能：
1. 读取 _full.py 全部内容
2. 解析 OutlineGenerator 类的所有方法及其行号范围
3. 按功能域分组方法
4. 生成 mixin 文件和主 generator.py
"""
import re
import os
from pathlib import Path

# 文件路径
BASE_DIR = Path(r"f:\python_project\全能创意大师（开发版）\backend\app\services\outline_generator")
FULL_FILE = BASE_DIR / "impl" / "_full.py"
MIXINS_DIR = BASE_DIR / "impl" / "mixins"

# 方法到Mixin的分组映射
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
        ]
    },
    "global_outline": {
        "description": "全局大纲生成",
        "methods": [
            "generate_global_outline",
            "generate_global_outline_stream",
        ]
    },
    "unit_summary": {
        "description": "单元概述生成与续生成",
        "methods": [
            "generate_unit_summaries",
            "generate_unit_summaries_stream",
            "continue_unit_summaries_generation",
            "_generate_missing_units",
            "_generate_units_batch",
            "_continue_single_unit",
            "_validate_continuation_quality",
            "_build_previous_units_reference",
            "_build_resume_context",
            "_build_resume_prompt",
        ]
    },
    "revision": {
        "description": "知识库修正与逻辑性修正",
        "methods": [
            "_revise_with_knowledge_base",
            "check_and_fix_logic_issues",
            "_parse_logic_check_response",
            "_auto_qc_and_revise",
            "_build_quality_revision_prompt",
            "_parse_quality_revision_result",
            "_build_revised_content",
        ]
    },
    "quality_control": {
        "description": "质量管控（分层质控、全局一致性检测）",
        "methods": [
            "_analyze_unit_summaries_quality",
            "_perform_layered_quality_control",
            "_check_resume_boundary",
            "_check_global_consistency_incremental",
            "analyze_global_outline_quality",
            "revise_global_outline_by_quality",
            "analyze_unit_summaries_quality_manual",
            "revise_unit_summaries_quality",
            "_clean_revised_content",
        ]
    },
}


def parse_methods(content: str) -> dict:
    """解析文件中所有方法定义及其行号范围"""
    lines = content.split('\n')
    methods = {}
    
    # 匹配类方法定义 (4空格缩进的def/async def)
    pattern = re.compile(r'^    (async )?def (\w+)\(')
    
    method_starts = []
    for i, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            method_name = m.group(2)
            method_starts.append((i + 1, method_name))  # 1-based line number
    
    # 计算每个方法的结束行（下一个方法的开始行-1，或文件末尾）
    for idx, (start_line, name) in enumerate(method_starts):
        if idx + 1 < len(method_starts):
            end_line = method_starts[idx + 1][0] - 1
        else:
            # 最后一个方法：找到类结束位置
            # 查找从方法开始到文件末尾中最后一个非空行
            end_line = len(lines)
            for i in range(len(lines) - 1, start_line - 1, -1):
                if lines[i - 1].strip():  # lines is 0-based
                    end_line = i
                    break
        
        methods[name] = (start_line, end_line)
    
    return methods


def get_method_content(lines: list, start: int, end: int) -> str:
    """获取指定行范围的内容（1-based行号）"""
    return '\n'.join(lines[start - 1:end])


def find_method_end(lines: list, start_line_1based: int) -> int:
    """
    找到方法的实际结束行。
    从方法定义开始，找到下一个同级缩进或更少缩进的非空行之前的最后一行。
    """
    # 方法体至少缩进8空格（4空格class + 4空格method body）
    # 同级方法定义是4空格缩进
    for i in range(start_line_1based, len(lines)):
        line = lines[i]  # 0-based
        if i > start_line_1based and line.strip() and not line.startswith(' ' * 8) and not line.strip().startswith('#') and not line.strip().startswith('"""') and not line.strip().startswith("'''"):
            # 找到非方法体的行（缩进少于8空格的非空行）
            if line.startswith(' ' * 4) and not line.startswith(' ' * 8):
                # 可能是下一个方法定义
                if re.match(r'^    (async )?def \w+\(', line):
                    return i  # 0-based, 即 (i+1)-1 1-based的前一行
            elif not line.startswith(' '):
                # 类外代码
                return i
    return len(lines)


def collect_imports(content: str) -> str:
    """从文件顶部收集所有import语句"""
    lines = content.split('\n')
    import_lines = []
    in_docstring = False
    
    for line in lines:
        stripped = line.strip()
        # 跳过模块docstring
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if in_docstring:
                in_docstring = False
                continue
            else:
                in_docstring = True
                continue
        if in_docstring:
            continue
        
        if stripped.startswith('import ') or stripped.startswith('from '):
            import_lines.append(line)
        elif stripped and not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith("'''"):
            # 遇到非import、非注释、非docstring的代码行，停止
            if not import_lines:
                continue
            break
    
    return '\n'.join(import_lines)


def main():
    """主拆分流程"""
    print("=" * 60)
    print("大纲生成器 _full.py → Mixin 拆分脚本")
    print("=" * 60)
    
    # 1. 读取源文件
    content = FULL_FILE.read_text(encoding='utf-8')
    lines = content.split('\n')
    print(f"\n源文件总行数: {len(lines)}")
    
    # 2. 解析方法
    methods = parse_methods(content)
    print(f"发现方法数: {len(methods)}")
    for name, (start, end) in methods.items():
        print(f"  {name}: L{start}-L{end} ({end-start+1}行)")
    
    # 3. 收集import
    imports = collect_imports(content)
    
    # 4. 收集模块级常量（class定义之前的非import代码）
    pre_class_lines = []
    class_start = None
    for i, line in enumerate(lines):
        if line.startswith('class OutlineGenerator:'):
            class_start = i + 1  # 1-based
            break
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith("'''") and not stripped.startswith('import ') and not stripped.startswith('from '):
            pre_class_lines.append(line)
    
    # 5. 收集模块级代码（class之后的代码，如全局实例和工厂函数）
    post_class_lines = []
    # 找到类结束位置
    class_end = None
    for i in range(len(lines) - 1, class_start - 1, -1):
        if lines[i].strip():
            # 找到类体最后一个非空行
            # 然后往后找第一个非类体行
            class_end = i + 1  # 0-based
            break
    
    # 找模块级代码（类之后的非空行，不以8+空格开头的）
    in_post_class = False
    for i in range(class_end, len(lines)):
        line = lines[i]
        if line.strip() and not line.startswith(' ' * 4):
            in_post_class = True
        if in_post_class:
            post_class_lines.append(line)
    
    print(f"\n类定义行: L{class_start}")
    print(f"类前常量行数: {len(pre_class_lines)}")
    print(f"类后模块代码行数: {len(post_class_lines)}")
    
    # 6. 创建mixins目录
    MIXINS_DIR.mkdir(exist_ok=True)
    print(f"\nMixin目录: {MIXINS_DIR}")
    
    # 7. 分配方法到各组，找出未分配的方法
    all_assigned = set()
    unassigned = set(methods.keys()) - {'__init__', '_format_sse'}
    
    for group_name, group_info in METHOD_GROUPS.items():
        for method_name in group_info["methods"]:
            if method_name in methods:
                all_assigned.add(method_name)
                unassigned.discard(method_name)
    
    if unassigned:
        print(f"\n⚠️ 未分配的方法: {unassigned}")
        # 将未分配的方法放入一个"misc" mixin
        if unassigned:
            METHOD_GROUPS["_misc"] = {
                "description": "未分类的辅助方法",
                "methods": list(unassigned)
            }
    
    # 8. 生成每个mixin文件
    # 需要确定每个mixin需要哪些import
    # 简单策略：每个mixin包含全部import（多余的import不会导致错误）
    
    # 但我们只包含必要的import
    # 分析每个方法体中使用的导入
    
    created_files = []
    
    for group_name, group_info in METHOD_GROUPS.items():
        method_names = group_info["methods"]
        valid_methods = [m for m in method_names if m in methods]
        
        if not valid_methods:
            print(f"\n跳过空组: {group_name}")
            continue
        
        # 收集方法内容
        method_contents = []
        for mname in valid_methods:
            start, end = methods[mname]
            method_contents.append(get_method_content(lines, start, end))
        
        # 分析方法中使用的符号来确定需要哪些import
        combined_content = '\n'.join(method_contents)
        needed_imports = analyze_needed_imports(combined_content, imports)
        
        # 生成Mixin类
        class_name = "".join(part.capitalize() for part in group_name.split('_')) + "Mixin"
        
        mixin_content = f'"""大纲生成器 - {group_info["description"]}Mixin"""\n'
        mixin_content += needed_imports + '\n\n\n'
        mixin_content += f'class {class_name}:\n'
        mixin_content += f'    """{group_info["description"]}"""\n\n'
        
        for mc in method_contents:
            # 方法内容已经是4空格缩进的，直接附加
            # 确保方法之间有空行分隔
            lines_mc = mc.split('\n')
            # 去掉方法末尾多余的空行
            while lines_mc and not lines_mc[-1].strip():
                lines_mc.pop()
            mixin_content += '\n'.join(lines_mc) + '\n\n\n'
        
        mixin_file = MIXINS_DIR / f"{group_name}.py"
        mixin_file.write_text(mixin_content, encoding='utf-8')
        created_files.append(mixin_file)
        total_lines = len(mixin_content.split('\n'))
        print(f"\n✅ 创建: {mixin_file.name} ({total_lines}行, {len(valid_methods)}个方法)")
        for mname in valid_methods:
            start, end = methods[mname]
            print(f"   - {mname}: L{start}-L{end}")
    
    # 9. 创建 __init__.py (mixins)
    init_content = '"""大纲生成器 - Mixin模块"""\n'
    for group_name in METHOD_GROUPS.keys():
        class_name = "".join(part.capitalize() for part in group_name.split('_')) + "Mixin"
        init_content += f'from app.services.outline_generator.impl.mixins.{group_name} import {class_name}\n'
    
    init_file = MIXINS_DIR / "__init__.py"
    init_file.write_text(init_content, encoding='utf-8')
    created_files.append(init_file)
    print(f"\n✅ 创建: {init_file.name}")
    
    # 10. 创建主 generator.py
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
    UnitSummaryMixin,
    RevisionMixin,
    QualityControlMixin,
'''
    
    if '_misc' in METHOD_GROUPS:
        generator_content += '    _MiscMixin,\n'
    
    generator_content += '''):
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
    created_files.append(generator_file)
    print(f"\n✅ 创建: generator.py")
    
    # 11. 更新 impl/__init__.py
    init_impl = '''"""大纲生成器 - 实现层"""
from app.services.outline_generator.impl.generator import OutlineGenerator

__all__ = ["OutlineGenerator"]
'''
    init_impl_file = BASE_DIR / "impl" / "__init__.py"
    init_impl_file.write_text(init_impl, encoding='utf-8')
    print(f"\n✅ 更新: impl/__init__.py")
    
    # 12. 输出验证命令
    print("\n" + "=" * 60)
    print("拆分完成！请运行以下命令验证导入:")
    print("=" * 60)
    print("cd f:\\\\python_project\\\\全能创意大师（开发版）\\\\backend")
    print("python -c \"from app.services.outline_generator import OutlineGenerator, get_outline_generator; print('导入成功')\"")
    
    return created_files


def analyze_needed_imports(method_content: str, all_imports: str) -> str:
    """分析方法内容中使用的符号，返回必要的import语句"""
    import_lines = all_imports.split('\n')
    needed = []
    
    # 关键词到import的映射
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
    
    # 检查每个关键词是否在方法内容中使用
    for keyword, import_line in keyword_import_map.items():
        if keyword in method_content:
            # 避免重复添加
            if import_line not in needed:
                needed.append(import_line)
    
    return '\n'.join(needed)


if __name__ == '__main__':
    main()
