"""
通用Python大文件Mixin拆分工具

用法：
  python split_large_file.py <源文件路径> <输出目录> [--max-lines 500] [--module-name 自定义名]

功能：
  1. 解析源文件中的类和独立函数
  2. 按功能域将方法分组到Mixin中
  3. 每个Mixin ≤ max-lines 行
  4. 生成 __init__.py, generator.py (主类), api/ 子目录
  5. 保持向后兼容导入
"""
import ast
import re
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def parse_class_methods(content: str, class_name: str) -> Dict[str, Tuple[int, int]]:
    """解析指定类的所有方法及其行号范围"""
    lines = content.split('\n')
    methods = {}
    pattern = re.compile(r'^    (async )?def (\w+)\(')
    
    # 找到类定义
    in_class = False
    class_indent = 0
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
            # 检查类是否结束（遇到非空且缩进<=class缩进的行）
            if i > 0 and stripped and not line.startswith(' ' * 4) and not stripped.startswith('#'):
                if not stripped.startswith('def ') and not stripped.startswith('async def '):
                    break
    
    for idx, (start_line, name) in enumerate(method_starts):
        if idx + 1 < len(method_starts):
            end_line = method_starts[idx + 1][0] - 1
        else:
            # 找类末尾
            end_line = len(lines)
            for i in range(len(lines) - 1, start_line - 1, -1):
                if lines[i - 1].strip():
                    end_line = i
                    break
        methods[name] = (start_line, end_line)
    
    return methods


def parse_module_functions(content: str) -> Dict[str, Tuple[int, int]]:
    """解析模块级函数"""
    lines = content.split('\n')
    functions = {}
    pattern = re.compile(r'^(async )?def (\w+)\(')
    
    func_starts = []
    for i, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            func_starts.append((i + 1, m.group(2)))
    
    for idx, (start_line, name) in enumerate(func_starts):
        if idx + 1 < len(func_starts):
            end_line = func_starts[idx + 1][0] - 1
        else:
            # 找到类定义或文件末尾
            end_line = len(lines)
            for i in range(start_line, len(lines)):
                if lines[i].startswith('class '):
                    end_line = i
                    break
    
    functions[name] = (start_line, end_line)
    
    return functions


def parse_dataclasses(content: str) -> Dict[str, Tuple[int, int]]:
    """解析数据类定义"""
    lines = content.split('\n')
    dataclasses = {}
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('@dataclass') or stripped.startswith('class ') and 'dataclass' in line:
            # 找到类定义
            if stripped.startswith('@dataclass'):
                # 下一行是class定义
                if i + 1 < len(lines):
                    class_line = lines[i + 1].strip()
                    m = re.match(r'class (\w+)', class_line)
                    if m:
                        name = m.group(1)
                        start = i + 1  # 1-based
                        # 找类结束
                        end = start
                        for j in range(i + 2, len(lines)):
                            if lines[j].strip() and not lines[j].startswith(' ') and not lines[j].startswith('@'):
                                end = j  # 0-based
                                break
                        else:
                            end = len(lines)
                        dataclasses[name] = (start, end)
    
    return dataclasses


def auto_group_methods(methods: Dict[str, Tuple[int, int]], max_lines: int = 500) -> Dict[str, List[str]]:
    """
    自动将方法按功能域分组，每组 ≤ max_lines
    
    策略：
    1. 以 public 方法（无下划线前缀）作为组起点
    2. 将紧跟其后的 private 方法（_前缀）归入同一组
    3. 如果组超过 max_lines，拆分出部分 private 方法到新组
    """
    if not methods:
        return {}
    
    # 按行号排序
    sorted_methods = sorted(methods.items(), key=lambda x: x[1][0])
    
    groups = {}
    current_group = None
    current_lines = 0
    
    for name, (start, end) in sorted_methods:
        method_lines = end - start + 1
        
        # public 方法开始新组
        if not name.startswith('_'):
            if current_group and current_lines > 0:
                pass  # 保留当前组
            current_group = name
            current_lines = method_lines
            if current_group not in groups:
                groups[current_group] = []
            groups[current_group].append(name)
        else:
            # private 方法
            if current_group is None:
                current_group = "_utilities"
                groups[current_group] = []
            
            if current_lines + method_lines > max_lines:
                # 当前组已满，开始新组
                current_group = f"{current_group}_helpers"
                if current_group not in groups:
                    groups[current_group] = []
                current_lines = 0
            
            groups[current_group].append(name)
            current_lines += method_lines
    
    return groups


def analyze_needed_imports(method_content: str) -> str:
    """分析方法内容中使用的符号，返回必要的import语句"""
    all_imports = {
        'AsyncSession': 'from sqlalchemy.ext.asyncio import AsyncSession',
        'select': 'from sqlalchemy import select',
        'AsyncGenerator': 'from typing import AsyncGenerator',
        'Dict': 'from typing import Dict',
        'List': 'from typing import List',
        'Optional': 'from typing import Optional',
        'Any': 'from typing import Any',
        'Tuple': 'from typing import Tuple',
        'datetime': 'from datetime import datetime',
        'dataclass': 'from dataclasses import dataclass, field',
        'json': 'import json',
        're': 'import re',
        'os': 'import os',
        'time': 'import time',
        'random': 'import random',
        'asyncio': 'import asyncio',
        'base64': 'import base64',
        'mimetypes': 'import mimetypes',
        'get_llm_manager': 'from app.agents.llm_manager import get_llm_manager, LLMManager',
        'LLMManager': 'from app.agents.llm_manager import get_llm_manager, LLMManager',
        'get_memory_manager': 'from app.agents.memory_manager import get_memory_manager, MemoryManager',
        'MemoryManager': 'from app.agents.memory_manager import get_memory_manager, MemoryManager',
        'get_prompt_manager': 'from app.agents.prompt_manager import get_prompt_manager, PromptManager',
        'PromptManager': 'from app.agents.prompt_manager import get_prompt_manager, PromptManager',
        'get_logger': 'from app.core.logger import get_logger',
        'LoggerAdapter': 'from app.core.logger import get_logger, LoggerAdapter',
        'get_settings': 'from app.core.config import get_settings',
        'PRESET_MODELS': 'from app.core.config import PRESET_MODELS, get_settings',
        'get_web_search_tool': 'from app.tools.web_search import get_web_search_tool, WebSearchTool',
        'WebSearchTool': 'from app.tools.web_search import get_web_search_tool, WebSearchTool',
        'get_knowledge_retrieval_tool': 'from app.tools.knowledge_retrieval import get_knowledge_retrieval_tool, KnowledgeRetrievalTool',
        'KnowledgeRetrievalTool': 'from app.tools.knowledge_retrieval import get_knowledge_retrieval_tool, KnowledgeRetrievalTool',
        'get_webpage_reader': 'from app.tools.webpage_reader import get_webpage_reader, WebpageReader',
        'WebpageReader': 'from app.tools.webpage_reader import get_webpage_reader, WebpageReader',
        'get_file_parser': 'from app.tools.file_parser import get_file_parser, FileParser',
        'FileParser': 'from app.tools.file_parser import get_file_parser, FileParser',
        'get_mcp_client': 'from app.tools.mcp.mcp_client import get_mcp_client, MCPClient',
        'MCPClient': 'from app.tools.mcp.mcp_client import get_mcp_client, MCPClient',
        'get_creative_search': 'from app.tools.creative_search import get_creative_search, OptimizedCreativeSearch',
        'OptimizedCreativeSearch': 'from app.tools.creative_search import get_creative_search, OptimizedCreativeSearch',
        'Generation': 'from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory',
        'GenerationModule': 'from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory',
        'GenerationStatus': 'from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory',
        'GenerationRevisionHistory': 'from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory',
        'KnowledgeBase': 'from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory',
        'KnowledgeBaseType': 'from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory',
        'KnowledgeBaseStatus': 'from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory',
        'KnowledgeBaseCategory': 'from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory',
        'QualityControlService': 'from app.services.quality_control import QualityControlService',
        'ENABLE_QUALITY_CONTROL': 'from app.services.outline_generator.api.constants import ENABLE_QUALITY_CONTROL',
        'MIN_REVISION_LENGTH': 'from app.services.outline_generator.api.constants import MIN_REVISION_LENGTH',
        'OUTLINE_REVISION_PROMPT': 'from app.services.outline_generator.api.constants import OUTLINE_REVISION_PROMPT',
        'LOGIC_CHECK_PROMPT': 'from app.services.outline_generator.api.constants import LOGIC_CHECK_PROMPT',
    }
    
    needed = []
    for keyword, import_line in all_imports.items():
        if keyword in method_content and import_line not in needed:
            needed.append(import_line)
    return '\n'.join(needed)


def get_method_content(lines: list, start: int, end: int) -> str:
    """获取指定行范围的内容（1-based行号）"""
    content_lines = lines[start - 1:end]
    # 去掉末尾空行
    while content_lines and not content_lines[-1].strip():
        content_lines.pop()
    return '\n'.join(content_lines)


def split_file(source_path: str, output_dir: str, max_lines: int = 500, 
               module_name: str = None, class_name: str = None,
               manual_groups: Dict[str, List[str]] = None) -> List[str]:
    """
    拆分一个大Python文件为Mixin模块
    
    Args:
        source_path: 源文件路径
        output_dir: 输出目录
        max_lines: 每个文件最大行数
        module_name: 模块名（默认从文件名提取）
        class_name: 主类名（自动检测）
        manual_groups: 手动方法分组（可选）
    
    Returns:
        创建的文件列表
    """
    source = Path(source_path)
    output = Path(output_dir)
    
    if module_name is None:
        module_name = source.stem
    
    # 读取源文件
    content = source.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    print(f"源文件: {source.name} ({len(lines)}行)")
    
    # 自动检测类名
    if class_name is None:
        for line in lines:
            m = re.match(r'^class (\w+)', line)
            if m:
                class_name = m.group(1)
                break
    
    if class_name is None:
        print("❌ 未找到类定义，无法拆分")
        return []
    
    print(f"主类: {class_name}")
    
    # 解析方法
    methods = parse_class_methods(content, class_name)
    print(f"发现方法: {len(methods)}个")
    
    # 解析模块级函数
    module_functions = parse_module_functions(content)
    print(f"发现模块函数: {len(module_functions)}个")
    
    # 解析数据类
    dataclasses = parse_dataclasses(content)
    print(f"发现数据类: {len(dataclasses)}个")
    
    # 分组
    if manual_groups:
        groups = manual_groups
    else:
        groups = auto_group_methods(methods, max_lines)
    
    print(f"\n方法分组: {len(groups)}组")
    
    # 创建目录结构
    impl_dir = output / "impl"
    mixins_dir = impl_dir / "mixins"
    api_dir = output / "api"
    
    for d in [output, impl_dir, mixins_dir, api_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    created_files = []
    all_mixin_classes = []
    violations = []
    all_assigned = set()
    
    # 生成Mixin文件
    for group_name, method_names in groups.items():
        valid_methods = [m for m in method_names if m in methods]
        if not valid_methods:
            continue
        
        method_contents = []
        for mname in valid_methods:
            start, end = methods[mname]
            method_contents.append(get_method_content(lines, start, end))
            all_assigned.add(mname)
        
        combined = '\n'.join(method_contents)
        needed_imports = analyze_needed_imports(combined)
        
        # 生成Mixin类名
        parts = group_name.split('_')
        class_part = "".join(p.capitalize() for p in parts)
        mixin_class_name = f"{class_part}Mixin"
        
        # 生成文件内容
        mixin_content = f'"""{module_name} - {group_name}Mixin"""\n'
        mixin_content += needed_imports + '\n\n\n'
        mixin_content += f'class {mixin_class_name}:\n'
        mixin_content += f'    """{group_name} 功能域"""\n\n'
        
        for mc in method_contents:
            mixin_content += mc + '\n\n\n'
        
        total_lines = len(mixin_content.split('\n'))
        
        mixin_file = mixins_dir / f"{group_name}.py"
        mixin_file.write_text(mixin_content, encoding='utf-8')
        created_files.append(str(mixin_file))
        all_mixin_classes.append(mixin_class_name)
        
        status = "✅" if total_lines <= max_lines else "⚠️ "
        if total_lines > max_lines:
            violations.append((group_name, total_lines))
        
        print(f"  {status} {group_name}.py ({total_lines}行, {len(valid_methods)}方法)")
    
    # 检查未分配的方法
    unassigned = set(methods.keys()) - all_assigned - {'__init__'}
    if unassigned:
        print(f"\n⚠️ 未分配的方法: {unassigned}")
        # 将未分配的方法放入misc mixin
        if unassigned:
            method_contents = []
            for mname in sorted(unassigned):
                if mname in methods:
                    start, end = methods[mname]
                    method_contents.append(get_method_content(lines, start, end))
                    all_assigned.add(mname)
            
            if method_contents:
                combined = '\n'.join(method_contents)
                needed_imports = analyze_needed_imports(combined)
                mixin_content = f'"""{module_name} - 辅助方法Mixin"""\n'
                mixin_content += needed_imports + '\n\n\n'
                mixin_content += 'class MiscMixin:\n'
                mixin_content += '    """辅助方法"""\n\n'
                for mc in method_contents:
                    mixin_content += mc + '\n\n\n'
                
                mixin_file = mixins_dir / "_misc.py"
                mixin_file.write_text(mixin_content, encoding='utf-8')
                created_files.append(str(mixin_file))
                all_mixin_classes.append("MiscMixin")
                total_lines = len(mixin_content.split('\n'))
                print(f"  ⚠️ _misc.py ({total_lines}行, {len(unassigned)}方法)")
    
    # 生成 mixins/__init__.py
    init_content = f'"""{module_name} - Mixin模块"""\n'
    for cls_name in all_mixin_classes:
        # 找到对应的文件名
        for group_name, method_names in groups.items():
            parts = group_name.split('_')
            cn = "".join(p.capitalize() for p in parts) + "Mixin"
            if cn == cls_name:
                init_content += f'from .{group_name} import {cls_name}\n'
                break
        else:
            if cls_name == "MiscMixin":
                init_content += f'from ._misc import MiscMixin\n'
    
    (mixins_dir / "__init__.py").write_text(init_content, encoding='utf-8')
    created_files.append(str(mixins_dir / "__init__.py"))
    
    # 生成 impl/generator.py (主类)
    gen_content = f'"""{module_name} - 主类（组合所有Mixin）"""\n'
    gen_content += 'from sqlalchemy.ext.asyncio import AsyncSession\n\n'
    gen_content += 'from app.core.logger import get_logger\n'
    gen_content += f'from {module_name_to_import_path(str(output))}.impl.mixins import (\n'
    for cls_name in all_mixin_classes:
        gen_content += f'    {cls_name},\n'
    gen_content += ')\n\n\n'
    
    gen_content += f'class {class_name}(\n'
    for cls_name in all_mixin_classes:
        gen_content += f'    {cls_name},\n'
    gen_content += '):\n'
    gen_content += f'    """{class_name} - 组合Mixin实现"""\n\n'
    
    # 从原文件提取__init__方法
    if '__init__' in methods:
        init_start, init_end = methods['__init__']
        init_content = get_method_content(lines, init_start, init_end)
        gen_content += init_content + '\n\n'
    
    gen_content += '\n\n'
    
    # 添加工厂函数
    factory_func_name = f"get_{re.sub(r'([A-Z])', r'_\1', class_name).lower().lstrip('_')}"
    gen_content += f'# 全局实例\n_{module_name} = None\n\n\n'
    gen_content += f'def {factory_func_name}() -> "{class_name}":\n'
    gen_content += f'    """获取{class_name}实例"""\n'
    gen_content += f'    global _{module_name}\n'
    gen_content += f'    if _{module_name} is None:\n'
    gen_content += f'        _{module_name} = {class_name}()\n'
    gen_content += f'    return _{module_name}\n'
    
    (impl_dir / "generator.py").write_text(gen_content, encoding='utf-8')
    created_files.append(str(impl_dir / "generator.py"))
    print(f"\n  ✅ generator.py")
    
    # 生成 impl/__init__.py
    impl_init = f'"""{module_name} - 实现层"""\nfrom {module_name_to_import_path(str(output))}.impl.generator import {class_name}\n\n__all__ = ["{class_name}"]\n'
    (impl_dir / "__init__.py").write_text(impl_init, encoding='utf-8')
    created_files.append(str(impl_dir / "__init__.py"))
    
    # 生成 api/ 层
    # 将数据类和模块函数放到api/层
    api_content = f'"""{module_name} - API层（数据类、常量、模块函数）"""\n'
    
    # 添加数据类
    for dc_name, (start, end) in dataclasses.items():
        dc_content = get_method_content(lines, start, end)
        # 去掉4空格缩进
        dc_lines = dc_content.split('\n')
        # 找到dataclass装饰器位置
        for i, line in enumerate(lines):
            if '@dataclass' in line:
                dc_content = '\n'.join(lines[i:end])
                break
        api_content += '\n\n' + dc_content + '\n'
    
    # 添加模块级函数
    for func_name, (start, end) in module_functions.items():
        func_content = get_method_content(lines, start, end)
        api_content += '\n\n' + func_content + '\n'
    
    (api_dir / "__init__.py").write_text(api_content, encoding='utf-8')
    created_files.append(str(api_dir / "__init__.py"))
    print(f"  ✅ api/__init__.py")
    
    # 生成顶层 __init__.py
    top_init = f'"""{module_name} 包"""\n'
    top_init += f'from {module_name_to_import_path(str(output))}.impl import {class_name}\n'
    top_init += f'from {module_name_to_import_path(str(output))}.api import *\n'
    
    # 添加工厂函数导出
    gen_lines = (impl_dir / "generator.py").read_text(encoding='utf-8').split('\n')
    for line in gen_lines:
        m = re.match(r'^def (get_\w+)\(', line)
        if m:
            func_name = m.group(1)
            top_init += f'from {module_name_to_import_path(str(output))}.impl.generator import {func_name}\n'
    
    (output / "__init__.py").write_text(top_init, encoding='utf-8')
    created_files.append(str(output / "__init__.py"))
    print(f"  ✅ __init__.py")
    
    # 总结
    print(f"\n拆分总结:")
    print(f"  原始: {source.name} ({len(lines)}行)")
    print(f"  拆分后: {len(all_mixin_classes)}个Mixin + generator.py + api/")
    if violations:
        print(f"  ⚠️ 超标文件:")
        for name, line_count in violations:
            print(f"    - {name}.py: {line_count}行")
    
    return created_files


def module_name_to_import_path(dir_path: str) -> str:
    """将目录路径转为Python导入路径"""
    # 找到app目录的相对路径
    path = Path(dir_path)
    parts = []
    for p in reversed(path.parents):
        if p.name == 'app':
            parts.insert(0, 'app')
            break
        if p.name and p.name != 'backend':
            parts.insert(0, p.name)
    parts.append(path.name)
    
    # 从app开始
    try:
        idx = parts.index('app')
        return '.'.join(parts[idx:])
    except ValueError:
        return '.'.join(parts)


def main():
    parser = argparse.ArgumentParser(description='通用Python大文件Mixin拆分工具')
    parser.add_argument('source', help='源文件路径')
    parser.add_argument('--output', '-o', help='输出目录', default=None)
    parser.add_argument('--max-lines', type=int, default=500, help='每个文件最大行数')
    parser.add_argument('--class-name', help='主类名（自动检测）')
    parser.add_argument('--module-name', help='模块名')
    
    args = parser.parse_args()
    
    source = Path(args.source)
    if not source.exists():
        print(f"❌ 文件不存在: {source}")
        sys.exit(1)
    
    if args.output:
        output = Path(args.output)
    else:
        # 默认：将文件转为目录结构
        output = source.parent / source.stem
    
    split_file(
        str(source),
        str(output),
        max_lines=args.max_lines,
        module_name=args.module_name,
        class_name=args.class_name,
    )


if __name__ == '__main__':
    main()
