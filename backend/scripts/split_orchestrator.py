"""
拆分 agents/orchestrator.py (2566行) → 包结构
使用AST精确解析方法边界
"""
import ast
import re
from pathlib import Path

BASE = Path(r"f:\python_project\全能创意大师（开发版）\backend\app\agents")
SOURCE = BASE / "orchestrator.py"
TARGET = BASE / "orchestrator"


def get_class_methods_with_ast(content, class_name):
    """用AST精确解析类方法及行号"""
    tree = ast.parse(content)
    methods = {}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods[item.name] = (item.lineno, item.end_lineno)
    
    return methods


def get_module_level_items(content):
    """获取模块级函数和数据类"""
    tree = ast.parse(content)
    functions = {}
    dataclasses = []
    
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = (node.lineno, node.end_lineno)
        elif isinstance(node, ast.ClassDef):
            # 检查是否有dataclass装饰器
            has_dataclass = False
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name) and dec.id == 'dataclass':
                    has_dataclass = True
                elif isinstance(dec, ast.Attribute) and dec.attr == 'dataclass':
                    has_dataclass = True
            if has_dataclass or not any(isinstance(b, ast.FunctionDef) for b in node.body):
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
        'get_memory_manager': 'from app.agents.memory_manager import get_memory_manager, MemoryManager',
        'get_prompt_manager': 'from app.agents.prompt_manager import get_prompt_manager, PromptManager',
        'get_web_search_tool': 'from app.tools.web_search import get_web_search_tool, WebSearchTool',
        'get_knowledge_retrieval_tool': 'from app.tools.knowledge_retrieval import get_knowledge_retrieval_tool, KnowledgeRetrievalTool',
        'get_webpage_reader': 'from app.tools.webpage_reader import get_webpage_reader, WebpageReader',
        'get_file_parser': 'from app.tools.file_parser import get_file_parser, FileParser',
        'get_mcp_client': 'from app.tools.mcp.mcp_client import get_mcp_client, MCPClient',
        'get_creative_search': 'from app.tools.creative_search import get_creative_search, OptimizedCreativeSearch',
        'get_logger': 'from app.core.logger import get_logger, LoggerAdapter',
        'get_settings': 'from app.core.config import get_settings',
        'PRESET_MODELS': 'from app.core.config import PRESET_MODELS, get_settings',
        'Generation': 'from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory',
        'GenerationModule': 'from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory',
        'GenerationStatus': 'from app.models.generation import Generation, GenerationModule, GenerationStatus, GenerationRevisionHistory',
        'KnowledgeBase': 'from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory',
        'KnowledgeBaseType': 'from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory',
    }
    needed = []
    for kw, imp in mapping.items():
        if kw in content and imp not in needed:
            needed.append(imp)
    return '\n'.join(needed)


METHOD_GROUPS = {
    "context_utils": {
        "desc": "输入参数处理与上下文构建",
        "methods": ["_prepare_input_params", "_gather_context", "_get_user_graphrag_config"],
    },
    "generation_core": {
        "desc": "生成核心流程（加载LLM、初稿、评估修正、保存）",
        "methods": ["_load_llm_provider", "_generate_first_draft", "_evaluate_and_revise", "_save_and_complete"],
    },
    "generate_sync": {
        "desc": "同步生成入口",
        "methods": ["generate"],
    },
    "generate_stream_mixin": {
        "desc": "流式生成入口",
        "methods": ["generate_stream"],
    },
    "knowledge_retrieval": {
        "desc": "知识库检索与分类",
        "methods": [
            "_sort_knowledge_bases_by_priority",
            "_get_static_knowledge_bases",
            "_get_user_knowledge_bases",
            "_retrieve_classified_knowledge",
            "_retrieve_single_kb",
        ],
    },
    "evaluation": {
        "desc": "评估与自洽检查",
        "methods": ["_evaluate_result", "_check_self_consistency", "_auto_fix_issues", "_reflect_and_retry"],
    },
    "revision": {
        "desc": "LLM修正与版本差异",
        "methods": ["_evaluate_with_llm", "_generate_revised_content", "generate_revision_diff", "_build_revision_prompt", "_compress_revision_history"],
    },
    "session": {
        "desc": "会话管理与SSE工具",
        "methods": ["create_session", "get_session_messages", "_format_sse"],
    },
    "reflection": {
        "desc": "反思生成与完成",
        "methods": ["generate_with_reflection", "finalize_generation"],
    },
}


def main():
    print("=" * 60)
    print("拆分 agents/orchestrator.py (AST精确解析)")
    print("=" * 60)
    
    content = SOURCE.read_text(encoding='utf-8')
    lines = content.split('\n')
    print(f"源文件: {len(lines)}行")
    
    methods = get_class_methods_with_ast(content, "AgentOrchestrator")
    module_funcs, dataclasses = get_module_level_items(content)
    
    print(f"类方法数: {len(methods)}")
    for name, (s, e) in sorted(methods.items(), key=lambda x: x[1][0]):
        print(f"  {name}: L{s}-L{e} ({e-s+1}行)")
    
    print(f"\n模块函数数: {len(module_funcs)}")
    for name, (s, e) in module_funcs.items():
        print(f"  {name}: L{s}-L{e}")
    
    # 创建目录结构
    impl_dir = TARGET / "impl"
    mixins_dir = impl_dir / "mixins"
    api_dir = TARGET / "api"
    for d in [TARGET, impl_dir, mixins_dir, api_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # 备份原文件
    (impl_dir / "_full.py").write_text(content, encoding='utf-8')
    
    # 生成api/__init__.py
    api_content = '"""Agent编排器 - API层（数据类、常量、模块函数）"""\n'
    # 提取import语句（从原文件头部）
    import_lines = []
    for line in lines:
        if line.startswith('import ') or line.startswith('from '):
            import_lines.append(line)
        elif line.strip() and not line.startswith('#') and not line.startswith('"""') and not line.startswith("'''"):
            if import_lines:
                break
    
    api_imports = set()
    for line in import_lines:
        stripped = line.strip()
        if any(kw in stripped for kw in ['dataclass', 'base64', 'mimetypes', 'Optional', 'List', 'os']):
            api_imports.add(stripped)
    
    api_content += '\n'.join(sorted(api_imports)) + '\n\n'
    
    # 添加数据类
    for dc_name, dc_start, dc_end in dataclasses:
        # 包含装饰器
        start_idx = dc_start - 2 if dc_start > 1 and '@' in lines[dc_start - 2] else dc_start - 1
        dc_content = '\n'.join(lines[start_idx:dc_end])
        api_content += dc_content + '\n\n'
    
    # 添加模块函数
    for fname, (fs, fe) in module_funcs.items():
        func_content = '\n'.join(lines[fs - 1:fe])
        api_content += func_content + '\n\n'
    
    (api_dir / "__init__.py").write_text(api_content, encoding='utf-8')
    print(f"\n✅ api/__init__.py")
    
    # 生成Mixin文件
    all_mixin_classes = []
    all_assigned = set()
    violations = []
    
    for group_name, group_info in METHOD_GROUPS.items():
        valid_methods = [m for m in group_info["methods"] if m in methods]
        if not valid_methods:
            continue
        
        method_contents = []
        for mname in valid_methods:
            s, e = methods[mname]
            mc = '\n'.join(lines[s - 1:e])
            method_contents.append(mc)
            all_assigned.add(mname)
        
        combined = '\n'.join(method_contents)
        needed_imports = analyze_imports(combined)
        
        class_name = "".join(p.capitalize() for p in group_name.split('_')) + "Mixin"
        
        mixin_content = f'"""Agent编排器 - {group_info["desc"]}Mixin"""\n'
        mixin_content += needed_imports + '\n\n\n'
        mixin_content += f'class {class_name}:\n'
        mixin_content += f'    """{group_info["desc"]}"""\n\n'
        for mc in method_contents:
            mixin_content += mc + '\n\n\n'
        
        total_lines = len(mixin_content.split('\n'))
        mixin_file = mixins_dir / f"{group_name}.py"
        mixin_file.write_text(mixin_content, encoding='utf-8')
        all_mixin_classes.append(class_name)
        
        status = "✅" if total_lines <= 500 else "⚠️ "
        if total_lines > 500:
            violations.append((group_name, total_lines))
        print(f"{status} {group_name}.py ({total_lines}行, {len(valid_methods)}方法)")
    
    # 未分配
    unassigned = set(methods.keys()) - all_assigned - {'__init__'}
    if unassigned:
        print(f"\n⚠️ 未分配方法: {unassigned}")
        # 创建misc mixin
        misc_methods = [m for m in unassigned if m in methods]
        if misc_methods:
            mc_list = []
            for mname in misc_methods:
                s, e = methods[mname]
                mc_list.append('\n'.join(lines[s - 1:e]))
                all_assigned.add(mname)
            
            combined = '\n'.join(mc_list)
            needed = analyze_imports(combined)
            mixin_content = f'"""Agent编排器 - 辅助方法Mixin"""\n{needed}\n\n\nclass MiscMixin:\n    """辅助方法"""\n\n'
            for mc in mc_list:
                mixin_content += mc + '\n\n\n'
            
            total_lines = len(mixin_content.split('\n'))
            (mixins_dir / "_misc.py").write_text(mixin_content, encoding='utf-8')
            all_mixin_classes.append("MiscMixin")
            print(f"  ⚠️ _misc.py ({total_lines}行)")
    
    # mixins/__init__.py
    init = '"""Agent编排器 - Mixin模块"""\n'
    for gn in METHOD_GROUPS.keys():
        cn = "".join(p.capitalize() for p in gn.split('_')) + "Mixin"
        init += f'from .{gn} import {cn}\n'
    if "MiscMixin" in all_mixin_classes:
        init += 'from ._misc import MiscMixin\n'
    (mixins_dir / "__init__.py").write_text(init, encoding='utf-8')
    
    # impl/generator.py
    gen = '"""Agent编排器 - 主类（组合所有Mixin）"""\n\n'
    gen += 'from app.core.logger import get_logger, LoggerAdapter\n'
    gen += 'from app.core.config import PRESET_MODELS, get_settings\n'
    gen += 'from app.agents.llm_manager import get_llm_manager, LLMManager\n'
    gen += 'from app.agents.memory_manager import get_memory_manager, MemoryManager\n'
    gen += 'from app.agents.prompt_manager import get_prompt_manager, PromptManager\n'
    gen += 'from app.agents.orchestrator.impl.mixins import (\n'
    for cn in all_mixin_classes:
        gen += f'    {cn},\n'
    gen += ')\n\n'
    
    # __init__方法
    if '__init__' in methods:
        s, e = methods['__init__']
        init_method = '\n'.join(lines[s - 1:e])
    else:
        init_method = '    def __init__(self):\n        pass'
    
    gen += 'class AgentOrchestrator(\n'
    for cn in all_mixin_classes:
        gen += f'    {cn},\n'
    gen += '):\n'
    gen += '    """Agent编排器 - 组合Mixin实现"""\n\n'
    gen += init_method + '\n\n\n'
    
    gen += '# 全局实例\n_orchestrator = None\n\n\ndef get_agent_orchestrator() -> "AgentOrchestrator":\n'
    gen += '    """获取Agent编排器实例"""\n'
    gen += '    global _orchestrator\n'
    gen += '    if _orchestrator is None:\n'
    gen += '        _orchestrator = AgentOrchestrator()\n'
    gen += '    return _orchestrator\n'
    
    (impl_dir / "generator.py").write_text(gen, encoding='utf-8')
    print(f"\n✅ generator.py")
    
    # impl/__init__.py
    (impl_dir / "__init__.py").write_text(
        '"""Agent编排器 - 实现层"""\nfrom app.agents.orchestrator.impl.generator import AgentOrchestrator\n\n__all__ = ["AgentOrchestrator"]\n',
        encoding='utf-8'
    )
    
    # 顶层 __init__.py
    top = '"""Agent编排器包\n\n协调 LLM、工具和记忆系统完成创意生成任务。\n此包替代原 orchestrator.py 单文件，保持完全向后兼容。\n"""\n'
    top += 'from app.agents.orchestrator.impl import AgentOrchestrator\n'
    top += 'from app.agents.orchestrator.impl.generator import get_agent_orchestrator\n'
    top += 'from app.agents.orchestrator.api import (\n'
    for fname in module_funcs:
        top += f'    {fname},\n'
    for dc_name, _, _ in dataclasses:
        top += f'    {dc_name},\n'
    top += ')\n\n__all__ = [\n'
    top += '    "AgentOrchestrator", "get_agent_orchestrator",\n'
    for fname in module_funcs:
        top += f'    "{fname}",\n'
    for dc_name, _, _ in dataclasses:
        top += f'    "{dc_name}",\n'
    top += ']\n'
    
    (TARGET / "__init__.py").write_text(top, encoding='utf-8')
    print(f"✅ __init__.py")
    
    if violations:
        print(f"\n⚠️ 超标文件:")
        for n, l in violations:
            print(f"  - {n}.py: {l}行")
    
    # 语法验证
    import ast as _ast
    try:
        _ast.parse((impl_dir / "generator.py").read_text(encoding='utf-8'))
        _ast.parse((TARGET / "__init__.py").read_text(encoding='utf-8'))
        print(f"\n✅ 语法验证通过")
    except SyntaxError as e:
        print(f"\n❌ 语法错误: {e}")


if __name__ == '__main__':
    main()
