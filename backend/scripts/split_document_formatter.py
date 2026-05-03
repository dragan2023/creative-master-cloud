"""
拆分 document_formatter/__init__.py 为 Mixin 模块

遵循与 outline_generator/impl/mixins/ 相同的 Mixin 多重继承模式。
将 DocumentFormatter 类中的方法按功能域分组到独立 Mixin 文件中。

用法:
    python split_document_formatter.py
"""
import re
from pathlib import Path
from typing import Dict, List, Tuple

BASE_DIR = Path(r"f:\python_project\全能创意大师（开发版）")
SOURCE_FILE = BASE_DIR / "backend" / "app" / "services" / "proofread" / "document_formatter" / "__init__.py"
OUTPUT_DIR = BASE_DIR / "backend" / "app" / "services" / "proofread" / "document_formatter"


def parse_methods(content: str, class_name: str = "DocumentFormatter") -> Dict[str, Tuple[int, int]]:
    """解析指定类的所有方法及其行号范围"""
    lines = content.split('\n')
    methods = {}
    pattern = re.compile(r'^    (async )?def (\w+)\(')
    
    in_class = False
    method_starts = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f'class {class_name}'):
            in_class = True
            continue
        if in_class:
            m = pattern.match(line)
            if m:
                method_starts.append((i + 1, m.group(2)))  # 1-based
            # 类结束检查
            if i > 0 and stripped and not line.startswith(' ' * 4):
                if not stripped.startswith('def ') and not stripped.startswith('async def ') and not stripped.startswith('#'):
                    break
    
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


def get_content_lines(lines: list, start: int, end: int) -> str:
    """获取指定行范围的内容（1-based行号）"""
    content_lines = lines[start - 1:end]
    while content_lines and not content_lines[-1].strip():
        content_lines.pop()
    return '\n'.join(content_lines)


def get_lines_for_group(lines: list, method_ranges: Dict[str, Tuple[int, int]], 
                         method_names: list) -> List[str]:
    """获取一组方法的内容列表"""
    contents = []
    for mname in method_names:
        if mname in method_ranges:
            start, end = method_ranges[mname]
            contents.append(get_content_lines(lines, start, end))
    return contents


def analyze_needed_imports(content: str, existing_imports: List[str]) -> str:
    """分析方法内容中使用的符号，返回必要的import语句"""
    keyword_import_map = {
        're': 'import re',
        'typing.List': 'from typing import List',
        'List': 'from typing import List',
        'Dict': 'from typing import Dict',
        'Any': 'from typing import Any',
        'Optional': 'from typing import Optional',
        'Tuple': 'from typing import Tuple',
        'FormattingStats': 'from app.services.proofread.document_formatter._schemas import FormattingStats',
        'get_logger': 'from app.core.logger import get_logger',
    }
    
    needed = []
    for keyword, import_line in keyword_import_map.items():
        if keyword in content:
            # 检查是否在已有导入中
            already_has = any(import_line in ei for ei in existing_imports)
            if not already_has and import_line not in needed:
                needed.append(import_line)
    
    return '\n'.join(needed)


def main():
    print("=" * 60)
    print("DocumentFormatter Mixin 拆分工具")
    print("=" * 60)
    
    content = SOURCE_FILE.read_text(encoding='utf-8')
    lines = content.split('\n')
    print(f"源文件: {SOURCE_FILE.name} ({len(lines)}行)")
    
    methods = parse_methods(content)
    print(f"发现方法: {len(methods)}个")
    for name, (s, e) in sorted(methods.items(), key=lambda x: x[1][0]):
        print(f"  {name}: L{s}-L{e} ({e-s+1}行)")
    
    # 提取原始文件的导入语句（L1-L33）
    import_section = '\n'.join(lines[0:33])
    existing_imports = [l.strip() for l in lines[0:33] if l.strip().startswith(('import ', 'from '))]
    
    # ========== 定义方法分组 ==========
    METHOD_GROUPS = {
        "number_utils": {
            "description": "数字工具（中文数字转换）",
            "class_data": {
                "CHINESE_NUMS": (47, 51),
                "NUM_TO_CHINESE": (54, 75),
            },
            "methods": [
                "_get_unit_name", "_number_to_chinese", "_chinese_to_number"
            ]
        },
        "pattern_compiler": {
            "description": "模式编译（章节标题正则）",
            "class_data": {
                "chapter_patterns": None,  # 在方法内构建
            },
            "methods": [
                "_compile_patterns", "_compile_novel_patterns",
                "_compile_series_patterns", "_compile_movie_patterns"
            ]
        },
        "noise_and_encoding": {
            "description": "干扰内容清理与编码修复",
            "class_data": {
                "NOISE_PATTERNS": (78, 105),
                "TOC_PATTERNS": (108, 116),
            },
            "methods": [
                "_fix_encoding", "_remove_noise_content", "_remove_table_of_contents"
            ]
        },
        "section_titles": {
            "description": "小节标题处理",
            "class_data": {
                "NON_CHAPTER_KEYWORDS": (120, 128),
                "SECTION_TITLE_PATTERNS": (132, 139),
                "EXTENDED_SECTION_PATTERNS": (142, 149),
            },
            "methods": [
                "_process_section_titles", "_is_chapter_title",
                "_is_section_title_with_context", "_is_section_title"
            ]
        },
        "title_processing": {
            "description": "标题标准化与重复处理",
            "methods": [
                "_process_markdown_headers", "_normalize_chapter_titles",
                "_is_valid_chapter_title", "_remove_duplicate_titles"
            ]
        },
        "cleanup_and_validate": {
            "description": "空白清理与验证",
            "methods": [
                "_cleanup_whitespace", "_validate_and_fix", "_count_chapters"
            ]
        },
        "format_execution": {
            "description": "格式执行主流程",
            "methods": [
                "__init__", "format"
            ]
        },
    }
    
    created_files = []
    all_mixin_classes = []
    violations = []
    all_assigned = set()
    
    # 备份原始文件
    backup_path = SOURCE_FILE.with_suffix(".py.bak")
    if not backup_path.exists():
        SOURCE_FILE.rename(backup_path)
        print(f"\n备份: {backup_path.name}")
    
    # 生成Mixin文件
    for group_name, group_info in METHOD_GROUPS.items():
        method_names = group_info["methods"]
        valid_methods = [m for m in method_names if m in methods]
        if not valid_methods:
            print(f"  ⚠️ 跳过 {group_name}: 无有效方法")
            continue
        
        method_contents = get_lines_for_group(lines, methods, valid_methods)
        for mname in valid_methods:
            all_assigned.add(mname)
        
        combined = '\n'.join(method_contents)
        needed_imports = analyze_needed_imports(combined, existing_imports)
        
        class_part = "".join(p.capitalize() for p in group_name.split('_'))
        mixin_class_name = f"{class_part}Mixin"
        
        # 构建Mixin内容
        mixin_content = f'"""DocumentFormatter - {group_info["description"]}Mixin"""\n'
        mixin_content += f'from __future__ import annotations\n'
        if needed_imports:
            mixin_content += needed_imports + '\n'
        mixin_content += '\n\n'
        mixin_content += f'class {mixin_class_name}:\n'
        mixin_content += f'    """{group_info["description"]}"""\n\n'
        
        # 添加类数据常量（如果有）
        class_data = group_info.get("class_data", {})
        for data_name, data_range in class_data.items():
            if data_range:
                data_content = get_content_lines(lines, data_range[0], data_range[1])
                mixin_content += data_content + '\n\n'
        
        # 添加方法
        for mc in method_contents:
            mc_lines = mc.split('\n')
            while mc_lines and not mc_lines[-1].strip():
                mc_lines.pop()
            mixin_content += '\n'.join(mc_lines) + '\n\n\n'
        
        total_lines = len(mixin_content.split('\n'))
        
        mixin_file = OUTPUT_DIR / f"_{group_name}.py"
        mixin_file.write_text(mixin_content, encoding='utf-8')
        created_files.append(mixin_file)
        all_mixin_classes.append(mixin_class_name)
        
        status = "OK" if total_lines <= 500 else "WARN"
        if total_lines > 500:
            violations.append((group_name, total_lines))
        
        print(f"\n  [{status}] _{group_name}.py ({total_lines}行, {len(valid_methods)}方法)")
        for mname in valid_methods:
            s, e = methods[mname]
            print(f"     - {mname}: L{s}-L{e} ({e-s+1}行)")
    
    # 检查未分配的方法
    unassigned = set(methods.keys()) - all_assigned
    if unassigned:
        print(f"\n  WARN: 未分配的方法: {unassigned}")
    
    # ========== 生成新的 __init__.py ==========
    init_content = f'"""DocumentFormatter 包 - 组合Mixin实现"""\n'
    init_content += 'from __future__ import annotations\n'
    init_content += 'from typing import Tuple, List, Dict, Any\n\n'
    init_content += 'from app.core.logger import get_logger\n'
    init_content += 'from ._schemas import FormattingStats\n\n'
    
    for gn in METHOD_GROUPS.keys():
        cn = "".join(p.capitalize() for p in gn.split('_')) + "Mixin"
        init_content += f'from ._{gn} import {cn}\n'
    
    init_content += '\n'
    init_content += f'class DocumentFormatter(\n'
    for gn in METHOD_GROUPS.keys():
        cn = "".join(p.capitalize() for p in gn.split('_')) + "Mixin"
        init_content += f'    {cn},\n'
    init_content += '):\n'
    init_content += '    """文档格式化器 - 组合Mixin实现\n\n'
    init_content += '    通过多重继承组合各功能子模块，提供：\n'
    init_content += '    - 数字工具（中文数字转换）\n'
    init_content += '    - 模式编译（章节标题正则）\n'
    init_content += '    - 干扰内容清理与编码修复\n'
    init_content += '    - 小节标题处理\n'
    init_content += '    - 标题标准化与重复处理\n'
    init_content += '    - 空白清理与验证\n'
    init_content += '    - 格式执行主流程\n'
    init_content += '    """\n'
    init_content += '    pass\n\n\n'
    
    # 添加 format_document 函数
    format_func = get_content_lines(lines, 961, 975)
    init_content += format_func + '\n'
    
    (SOURCE_FILE).write_text(init_content, encoding='utf-8')
    print(f"\n  [OK] __init__.py ({len(init_content.split(chr(10)))}行)")
    
    # ========== 总结 ==========
    print("\n" + "=" * 60)
    print("拆分总结:")
    print("=" * 60)
    print(f"原始: __init__.py ({len(lines)}行)")
    print(f"拆分后: {len(created_files)}个Mixin + init.py")
    if violations:
        print(f"\n  仍超标 (>500行):")
        for n, l in violations:
            print(f"     - _{n}.py: {l}行")
    else:
        print("\n  所有新文件均在500行以内")
    
    print(f"\n备份文件: __init__.py.bak")


if __name__ == '__main__':
    main()
