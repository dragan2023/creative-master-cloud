"""
Split templates.py using ast module for reliable parsing
"""
import os
import ast
import shutil

TEMPLATES_FILE = r'f:\python_project\全能创意大师（开发版）\backend\app\agents\prompt_manager\templates.py'
TEMPLATES_DIR = r'f:\python_project\全能创意大师（开发版）\backend\app\agents\prompt_manager\templates'

with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
    source = f.read()

# Parse with ast to get line numbers of each key in DEFAULT_PROMPTS
tree = ast.parse(source)

# Find the DEFAULT_PROMPTS assignment
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'DEFAULT_PROMPTS':
                dict_node = node.value
                if isinstance(dict_node, ast.Dict):
                    keys = []
                    for k in dict_node.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            keys.append((k.value, k.lineno))
                    print(f"Found {len(keys)} template keys:")
                    for name, lineno in keys:
                        print(f"  {name:30s} (line {lineno})")

# Now extract text sections using line numbers
lines = source.split('\n')

# Helper: find section boundaries by brace depth
def find_dict_end(start_line, source_lines):
    """Find the end line of a dict literal starting on start_line"""
    brace_depth = 0
    started = False
    for i in range(start_line, len(source_lines)):
        line = source_lines[i]
        if not started:
            if '{' in line:
                started = True
                brace_depth = line.count('{') - line.count('}')
        else:
            brace_depth += line.count('{') - line.count('}')
        if started and brace_depth == 0:
            return i + 1
    return len(source_lines)

# Find all top-level keys in DEFAULT_PROMPTS dict
# Strategy: find lines that match "    # comment" followed by '    "key":' pattern
sections = []
i = 0
lines_mod = len(lines)

while i < lines_mod:
    line = lines[i]
    # Match indent level of 4 spaces (top-level inside DEFAULT_PROMPTS dict)
    if line.startswith('    # ') or line.startswith('    #####'):
        # Look ahead for the key line
        for j in range(i + 1, min(i + 3, lines_mod)):
            key_line = lines[j]
            if key_line.strip().startswith('"'):
                # This is a key line
                key_end = key_line.index('"', 1)
                key_name = key_line[1:key_end]
                
                # Find where the dict value for this key starts and ends
                brace_start = None
                for k in range(j, lines_mod):
                    if '{' in lines[k]:
                        brace_start = k
                        break
                
                if brace_start is not None:
                    end = find_dict_end(brace_start, lines)
                    # Section is from the comment line to the end of the dict value
                    sections.append({
                        'key': key_name,
                        'comment': line.strip('# ').strip(),
                        'start_line': i,
                        'key_line': j,
                        'value_start': brace_start,
                        'end_line': end,
                        'original_lines': lines[i:end],
                        'value_lines': lines[brace_start:end],
                    })
                    i = end
                    break
                else:
                    i += 1
                    break
        else:
            i += 1
    else:
        i += 1

print(f"\nSplit into {len(sections)} files:")

# Create templates directory
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Write each section
for s in sections:
    key = s['key']
    filename = key.replace('-', '_')
    filepath = os.path.join(TEMPLATES_DIR, f'{filename}.py')
    
    # Dedent value lines by removing 4 leading spaces
    dedented_lines = []
    for vl in s['value_lines']:
        stripped = vl.rstrip('\n')
        if stripped.startswith('    '):
            dedented_lines.append(stripped[4:])
        else:
            dedented_lines.append(stripped)
    
    value_text = '\n'.join(dedented_lines)
    
    # Build file
    file_lines = []
    file_lines.append(f'# -*- coding: utf-8 -*-')
    file_lines.append('"""')
    file_lines.append(f'提示词模板 - {s["comment"]}')
    file_lines.append('"""')
    file_lines.append('')
    file_lines.append(f'TEMPLATE = {value_text}')
    file_lines.append('')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(file_lines))
    print(f"  {key:30s} -> {filename}.py  ({len(s['value_lines'])} lines)")

# Create __init__.py
init_lines = [
    '# -*- coding: utf-8 -*-',
    '"""',
    '提示词模板包 - 合并所有子模块模板',
    '"""',
    '',
]
for s in sections:
    filename = s['key'].replace('-', '_')
    init_lines.append(f'from .{filename} import TEMPLATE as _{filename}_TEMPLATE')

init_lines.extend([
    '',
    '',
    'DEFAULT_PROMPTS = {',
])
for s in sections:
    filename = s['key'].replace('-', '_')
    init_lines.append(f'    "{s["key"]}": _{filename}_TEMPLATE,')
init_lines.append('}')
init_lines.append('')

init_file = os.path.join(TEMPLATES_DIR, '__init__.py')
with open(init_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(init_lines))
print(f"  Created: __init__.py")

# Backup original
shutil.move(TEMPLATES_FILE, TEMPLATES_FILE + '.bak')
print(f"\nOriginal moved to: {TEMPLATES_FILE}.bak")
print("Done!")
