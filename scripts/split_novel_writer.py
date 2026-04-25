"""Split novel_writer.py into package"""
import os
import shutil
import ast

src = 'backend/app/schemas/novel_writer.py'
pkg = 'backend/app/schemas/novel_writer'

if os.path.exists(pkg):
    shutil.rmtree(pkg)
os.makedirs(pkg, exist_ok=True)

with open(src, 'r', encoding='utf-8') as f:
    source = f.read()
lines = source.split('\n')
tree = ast.parse(source)

classes = []
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef):
        classes.append((node.name, node.lineno - 1, node.end_lineno))

print(f'Found {len(classes)} classes')

# Group classes
groups = {
    'enums.py': ['ContentType', 'ProjectType', 'ProjectStatus', 'ChapterStatus'],
    'configs.py': ['NovelConfig', 'SeriesScriptConfig', 'MovieScriptConfig', 'ScriptConfig'],
    'requests.py': ['NovelProjectCreate', 'ScriptProjectCreate', 'NovelProjectUpdate', 'DirectoryGenerateRequest'],
    'responses.py': ['NovelProjectResponse', 'NovelProjectListResponse', 'OutlineUploadResponse'],
}

class_ranges = {n: (s, e) for n, s, e in classes}

for fn, class_names in groups.items():
    # Find the range
    ranges = [class_ranges[cn] for cn in class_names if cn in class_ranges]
    if not ranges:
        print(f'  WARNING: no classes for {fn}')
        continue
    
    start = min(r[0] for r in ranges)
    end = max(r[1] for r in ranges)
    
    # Expand to include section comments
    while start > 0:
        trimmed = lines[start-1].strip()
        if trimmed == '' or trimmed.startswith('#') or '"""' in trimmed:
            start -= 1
        else:
            break
    
    section_lines = lines[start:end]
    
    if fn == 'enums.py':
        section_lines = [
            'from typing import Optional, List, Dict, Any',
            'from datetime import datetime',
            'from pydantic import BaseModel, Field',
            'from enum import Enum',
            '',
        ] + section_lines
    
    with open(os.path.join(pkg, fn), 'w', encoding='utf-8') as f:
        f.write('\n'.join(section_lines) + '\n')
    print(f'  Created: {fn}')

# __init__.py
init_lines = [
    '# -*- coding: utf-8 -*-',
    '"""',
    'Novel/Script Writer Schemas - 合并导出',
    '"""',
    '',
]
all_classes = []
for fn, class_names in groups.items():
    mod = fn.replace('.py', '')
    found = [cn for cn in class_names if cn in class_ranges]
    all_classes.extend(found)
    init_lines.append(f'from .{mod} import {", ".join(found)}')

init_lines.extend(['', '', '__all__ = ['])
for cn in all_classes:
    init_lines.append(f"    '{cn}',")
init_lines.append(']')
init_lines.append('')

with open(os.path.join(pkg, '__init__.py'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(init_lines) + '\n')
print('  Created: __init__.py')

# Backup original
shutil.move(src, src + '.bak')
print(f'Original moved to {src}.bak')
print('Done!')
