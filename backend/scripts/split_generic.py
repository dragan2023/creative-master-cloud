"""
通用AST精确拆分脚本 - 可复用于所有大型Python文件

用法: python split_generic.py <源文件相对路径> <主类名> [--groups 分组JSON]
"""
import ast
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"f:\python_project\全能创意大师（开发版）\backend\app")


def get_class_methods(content, class_name):
    tree = ast.parse(content)
    methods = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods[item.name] = (item.lineno, item.end_lineno)
    return methods


def get_module_level_items(content):
    tree = ast.parse(content)
    functions = {}
    dataclasses = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = (node.lineno, node.end_lineno)
        elif isinstance(node, ast.ClassDef):
            has_dc = any(
                (isinstance(d, ast.Name) and d.id == 'dataclass') or
                (isinstance(d, ast.Attribute) and d.attr == 'dataclass')
                for d in node.decorator_list
            )
            if has_dc:
                dataclasses.append((node.name, node.lineno, node.end_lineno))
    return functions, dataclasses


def analyze_imports(content):
    mapping = {
        'AsyncSession': 'from sqlalchemy.ext.asyncio import AsyncSession',
        'select': 'from sqlalchemy import select',
        'AsyncGenerator': 'from typing import AsyncGenerator',
        'Dict': 'from typing import Dict',
        'List': 'from typing import List',
        'Optional': 'from typing import Optional',
        'Any': 'from typing import Any',
        'Tuple': 'from typing import Tuple',
        'Union': 'from typing import Union',
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
        'copy': 'import copy',
        'math': 'import math',
        'collections': 'from collections import defaultdict, Counter',
        'defaultdict': 'from collections import defaultdict',
        'Counter': 'from collections import Counter',
        'get_llm_manager': 'from app.agents.llm_manager import get_llm_manager, LLMManager',
        'LLMManager': 'from app.agents.llm_manager import get_llm_manager, LLMManager',
        'get_memory_manager': 'from app.agents.memory_manager import get_memory_manager, MemoryManager',
        'get_prompt_manager': 'from app.agents.prompt_manager import get_prompt_manager, PromptManager',
        'get_logger': 'from app.core.logger import get_logger',
        'LoggerAdapter': 'from app.core.logger import get_logger, LoggerAdapter',
        'get_settings': 'from app.core.config import get_settings',
        'PRESET_MODELS': 'from app.core.config import PRESET_MODELS, get_settings',
        'Generation': 'from app.models.generation import Generation',
        'KnowledgeBase': 'from app.models.knowledge_base import KnowledgeBase',
        'QualityControlService': 'from app.services.quality_control import QualityControlService',
        'ENABLE_QUALITY_CONTROL': 'from app.services.outline_generator.api.constants import ENABLE_QUALITY_CONTROL',
    }
    needed = []
    for kw, imp in mapping.items():
        if kw in content and imp not in needed:
            needed.append(imp)
    return '\n'.join(needed)


def auto_group_methods(methods, max_lines=500):
    """按public→private方法自动分组"""
    sorted_m = sorted(methods.items(), key=lambda x: x[1][0])
    groups = {}
    current_group = None
    current_lines = 0
    
    for name, (s, e) in sorted_m:
        if name == '__init__':
            continue
        mlines = e - s + 1
        
        if not name.startswith('_'):
            if current_group and current_lines > max_lines:
                pass
            current_group = name
            current_lines = mlines
            groups[current_group] = [name]
        else:
            if current_group is None:
                current_group = "_utilities"
                groups[current_group] = []
            if current_lines + mlines > max_lines and mlines > 50:
                current_group = f"{current_group}_extra"
                groups[current_group] = []
                current_lines = 0
            groups[current_group].append(name)
            current_lines += mlines
    
    return groups


def split_file(source_rel_path, class_name, manual_groups=None, max_lines=500):
    source = PROJECT_ROOT / source_rel_path
    if not source.exists():
        print(f"❌ 文件不存在: {source}")
        return
    
    # 确定目标目录：同名目录
    target = source.parent / source.stem
    
    content = source.read_text(encoding='utf-8')
    lines = content.split('\n')
    print(f"\n{'='*60}")
    print(f"拆分: {source_rel_path}")
    print(f"源文件: {len(lines)}行, 主类: {class_name}")
    print(f"{'='*60}")
    
    methods = get_class_methods(content, class_name)
    module_funcs, dataclasses = get_module_level_items(content)
    
    print(f"类方法: {len(methods)}个")
    for name, (s, e) in sorted(methods.items(), key=lambda x: x[1][0]):
        print(f"  {name}: L{s}-L{e} ({e-s+1}行)")
    
    # 确定分组
    if manual_groups:
        groups = manual_groups
    else:
        groups = auto_group_methods(methods, max_lines)
        print(f"\n自动分组结果:")
    
    print(f"\n分组: {len(groups)}组")
    
    # 创建目录
    impl_dir = target / "impl"
    mixins_dir = impl_dir / "mixins"
    api_dir = target / "api"
    for d in [target, impl_dir, mixins_dir, api_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # 备份
    (impl_dir / "_full.py").write_text(content, encoding='utf-8')
    
    # api/__init__.py
    api_content = f'"""{class_name} - API层"""\n'
    # 添加数据类
    for dc_name, dc_start, dc_end in dataclasses:
        start_idx = dc_start - 2 if dc_start > 1 and '@' in lines[dc_start - 2] else dc_start - 1
        api_content += '\n'.join(lines[start_idx:dc_end]) + '\n\n'
    # 添加模块函数
    for fname, (fs, fe) in module_funcs.items():
        api_content += '\n'.join(lines[fs - 1:fe]) + '\n\n'
    (api_dir / "__init__.py").write_text(api_content, encoding='utf-8')
    
    # Mixin文件
    all_mixin_classes = []
    all_assigned = set()
    violations = []
    
    for group_name, method_names in groups.items():
        valid = [m for m in method_names if m in methods]
        if not valid:
            continue
        
        mcs = []
        for mn in valid:
            s, e = methods[mn]
            mc = '\n'.join(lines[s - 1:e])
            mcs.append(mc)
            all_assigned.add(mn)
        
        combined = '\n'.join(mcs)
        imports = analyze_imports(combined)
        
        cn = "".join(p.capitalize() for p in group_name.split('_')) + "Mixin"
        
        mc_content = f'"""{class_name} - {group_name}Mixin"""\n{imports}\n\n\nclass {cn}:\n    """{group_name}功能域"""\n\n'
        for mc in mcs:
            mc_content += mc + '\n\n\n'
        
        total = len(mc_content.split('\n'))
        (mixins_dir / f"{group_name}.py").write_text(mc_content, encoding='utf-8')
        all_mixin_classes.append(cn)
        
        st = "✅" if total <= max_lines else "⚠️ "
        if total > max_lines:
            violations.append((group_name, total))
        print(f"  {st} {group_name}.py ({total}行, {len(valid)}方法)")
    
    # 未分配方法
    unassigned = set(methods.keys()) - all_assigned - {'__init__'}
    if unassigned:
        print(f"\n  ⚠️ 未分配方法: {unassigned}")
        valid = [m for m in unassigned if m in methods]
        if valid:
            mcs = []
            for mn in valid:
                s, e = methods[mn]
                mcs.append('\n'.join(lines[s - 1:e]))
                all_assigned.add(mn)
            combined = '\n'.join(mcs)
            imports = analyze_imports(combined)
            mc_content = f'"""{class_name} - 辅助方法Mixin"""\n{imports}\n\n\nclass MiscMixin:\n    """辅助方法"""\n\n'
            for mc in mcs:
                mc_content += mc + '\n\n\n'
            (mixins_dir / "_misc.py").write_text(mc_content, encoding='utf-8')
            all_mixin_classes.append("MiscMixin")
            total = len(mc_content.split('\n'))
            print(f"  ⚠️ _misc.py ({total}行)")
    
    # mixins/__init__.py
    init = f'"""{class_name} - Mixin模块"""\n'
    for gn in groups.keys():
        cn = "".join(p.capitalize() for p in gn.split('_')) + "Mixin"
        init += f'from .{gn} import {cn}\n'
    if "MiscMixin" in all_mixin_classes:
        init += 'from ._misc import MiscMixin\n'
    (mixins_dir / "__init__.py").write_text(init, encoding='utf-8')
    
    # 计算导入路径
    import_path = str(target.relative_to(PROJECT_ROOT.parent)).replace('\\', '.').replace('/', '.')
    # 找到 app. 开始的位置
    if 'app.' in import_path:
        idx = import_path.index('app.')
        import_path = import_path[idx:]
    
    # impl/generator.py
    gen = f'"""{class_name} - 主类（组合所有Mixin）"""\n'
    gen += 'from app.core.logger import get_logger\n'
    gen += f'from {import_path}.impl.mixins import (\n'
    for cn in all_mixin_classes:
        gen += f'    {cn},\n'
    gen += ')\n\n'
    
    # __init__方法
    if '__init__' in methods:
        s, e = methods['__init__']
        init_m = '\n'.join(lines[s - 1:e])
    else:
        init_m = '    def __init__(self):\n        pass'
    
    gen += f'class {class_name}(\n'
    for cn in all_mixin_classes:
        gen += f'    {cn},\n'
    gen += '):\n'
    gen += f'    """{class_name} - 组合Mixin实现"""\n\n'
    gen += init_m + '\n'
    
    # 工厂函数
    factory = f"get_{re.sub(r'([A-Z])', r'_\1', class_name).lower().lstrip('_')}"
    gen += f'\n\n# 全局实例\n_instance = None\n\n\ndef {factory}() -> "{class_name}":\n'
    gen += f'    """获取{class_name}实例"""\n'
    gen += f'    global _instance\n'
    gen += f'    if _instance is None:\n'
    gen += f'        _instance = {class_name}()\n'
    gen += f'    return _instance\n'
    
    (impl_dir / "generator.py").write_text(gen, encoding='utf-8')
    
    # impl/__init__.py
    (impl_dir / "__init__.py").write_text(
        f'"""{class_name} - 实现层"""\nfrom {import_path}.impl.generator import {class_name}\n\n__all__ = ["{class_name}"]\n',
        encoding='utf-8'
    )
    
    # 顶层 __init__.py
    top = f'"""{class_name}包 - 替代原单文件，保持向后兼容"""\n'
    top += f'from {import_path}.impl import {class_name}\n'
    top += f'from {import_path}.impl.generator import {factory}\n'
    # 导出api层
    exports = [class_name, factory]
    for fname in module_funcs:
        top += f'from {import_path}.api import {fname}\n'
        exports.append(fname)
    for dc_name, _, _ in dataclasses:
        top += f'from {import_path}.api import {dc_name}\n'
        exports.append(dc_name)
    top += f'\n__all__ = {exports}\n'
    
    (target / "__init__.py").write_text(top, encoding='utf-8')
    
    # 验证
    try:
        ast.parse((impl_dir / "generator.py").read_text(encoding='utf-8'))
        ast.parse((target / "__init__.py").read_text(encoding='utf-8'))
        for f in mixins_dir.glob("*.py"):
            ast.parse(f.read_text(encoding='utf-8'))
        print(f"\n  ✅ 语法验证通过")
    except SyntaxError as e:
        print(f"\n  ❌ 语法错误: {e}")
    
    if violations:
        print(f"  ⚠️ 超标文件:")
        for n, l in violations:
            print(f"    - {n}.py: {l}行")
    
    return True


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: python split_generic.py <源文件相对路径> <主类名>")
        print("示例: python split_generic.py tools/novel_graph_rag.py NovelGraphRAG")
        sys.exit(1)
    
    source_path = sys.argv[1]
    class_name = sys.argv[2]
    split_file(source_path, class_name)
