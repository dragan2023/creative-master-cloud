"""
拆分 unit_quality_analyzer.py (2594行) → 包结构
策略：文件包含8个独立类，每个类拆成独立文件
"""
import ast
from pathlib import Path

BASE = Path(r"f:\python_project\全能创意大师（开发版）\backend\app\services\quality_control\analyzers")
SOURCE = BASE / "unit_quality_analyzer.py"
TARGET = BASE / "unit_quality_analyzer"

content = SOURCE.read_text(encoding='utf-8')
lines = content.split('\n')
print(f"源文件: {len(lines)}行")

# 解析所有类
tree = ast.parse(content)
classes = []
for node in tree.body:
    if isinstance(node, ast.ClassDef):
        classes.append((node.name, node.lineno, node.end_lineno))

print(f"发现类: {len(classes)}个")

# 创建目标目录
TARGET.mkdir(parents=True, exist_ok=True)

# 提取模块级代码（import等）
module_code = []
for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        module_code.append(ast.get_source_segment(content, node))
    elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        module_code.append(ast.get_source_segment(content, node))

imports_str = '\n'.join(module_code) if module_code else '"""单元概述质量分析器"""'

# 为每个类生成文件
all_names = []
for class_name, start_line, end_line in classes:
    # 提取类代码（包含装饰器）
    actual_start = start_line - 1  # 0-based
    # 检查是否有装饰器
    if actual_start > 0 and lines[actual_start - 1].strip().startswith('@'):
        actual_start -= 1
    
    class_code = '\n'.join(lines[actual_start:end_line])
    
    file_content = f'"""单元概述质量分析器 - {class_name}"""\n{imports_str}\n\n\n{class_code}\n'
    
    file_name = class_name.replace('Analyzer', '_analyzer').lower()
    # 转换驼峰命名为下划线
    import re
    file_name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower() + '.py'
    
    file_path = TARGET / file_name
    file_path.write_text(file_content, encoding='utf-8')
    total_lines = len(file_content.split('\n'))
    all_names.append((class_name, file_name.replace('.py', '')))
    status = "✅" if total_lines <= 500 else "⚠️ "
    print(f"  {status} {file_name} ({total_lines}行)")

# 生成 __init__.py
init = '"""单元概述质量分析器包\n\n此包替代原 unit_quality_analyzer.py 单文件，保持完全向后兼容。\n"""\n'
for class_name, module_name in all_names:
    init += f'from .{module_name} import {class_name}\n'
init += '\n__all__ = [\n'
for class_name, _ in all_names:
    init += f'    "{class_name}",\n'
init += ']\n'

(TARGET / "__init__.py").write_text(init, encoding='utf-8')
print(f"  ✅ __init__.py")

# 验证
try:
    for f in TARGET.glob("*.py"):
        ast.parse(f.read_text(encoding='utf-8'))
    print(f"\n✅ 语法验证通过")
except SyntaxError as e:
    print(f"\n❌ 语法错误: {e}")
