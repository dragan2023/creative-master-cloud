"""
Split templates.py using ast node locations for exact extraction
"""
import os
import ast
import shutil

TEMPLATES_FILE = r'f:\python_project\全能创意大师（开发版）\backend\app\agents\prompt_manager\templates.py'
TEMPLATES_DIR = r'f:\python_project\全能创意大师（开发版）\backend\app\agents\prompt_manager\templates'

with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
    source = f.read()

lines = source.split('\n')
tree = ast.parse(source)

# Find DEFAULT_PROMPTS assignment
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'DEFAULT_PROMPTS':
                dict_node = node.value
                if not isinstance(dict_node, ast.Dict):
                    continue
                
                entries = []
                for k, v in zip(dict_node.keys, dict_node.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        key = k.value
                        # Get exact source lines of the value node
                        v_start = v.lineno - 1  # 0-indexed
                        v_end = v.end_lineno  # already 0-indexed? No, end_lineno is 1-indexed
                        # Extract source text for this value
                        value_lines = lines[v_start:v_end]
                        
                        entries.append({
                            'key': key,
                            'value_lines': value_lines,
                            'start_line': v_start,
                            'end_line': v_end,
                        })
                
                print(f"Found {len(entries)} template entries")
                
                # Create directory
                os.makedirs(TEMPLATES_DIR, exist_ok=True)
                
                # Write each template
                for entry in entries:
                    key = entry['key']
                    filename = key.replace('-', '_')
                    filepath = os.path.join(TEMPLATES_DIR, f'{filename}.py')
                    
                    # Dedent: remove leading 4 spaces from each line
                    dedented = []
                    for vl in entry['value_lines']:
                        if vl.startswith('    '):
                            dedented.append(vl[4:])
                        else:
                            dedented.append(vl)
                    
                    value_text = '\n'.join(dedented)
                    
                    comment_from_source = f"Template: {key}"
                    # Try to find comment above the key in original source
                    for check_line in range(max(0, v_start - 3), v_start):
                        stripped_line = lines[check_line].strip()
                        if stripped_line.startswith('#') and not stripped_line.startswith('# ='):
                            comment_from_source = stripped_line.lstrip('# ').strip()
                            break
                    
                    file_content = [
                        '# -*- coding: utf-8 -*-',
                        '"""',
                        f'提示词模板 - {comment_from_source}',
                        '"""',
                        '',
                        f'TEMPLATE = {value_text}',
                        '',
                    ]
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(file_content))
                    
                    print(f"  {key:30s} -> {filename}.py ({len(entry['value_lines'])} lines)")
                
                # Create __init__.py
                init_parts = [
                    '# -*- coding: utf-8 -*-',
                    '"""',
                    '提示词模板包 - 合并所有子模块模板',
                    '"""',
                    '',
                ]
                for entry in entries:
                    fn = entry['key'].replace('-', '_')
                    init_parts.append(f'from .{fn} import TEMPLATE as _{fn}_TEMPLATE')
                
                init_parts.extend(['', '', 'DEFAULT_PROMPTS = {'])
                for entry in entries:
                    fn = entry['key'].replace('-', '_')
                    init_parts.append(f'    "{entry["key"]}": _{fn}_TEMPLATE,')
                init_parts.append('}')
                init_parts.append('')
                
                init_file = os.path.join(TEMPLATES_DIR, '__init__.py')
                with open(init_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(init_parts))
                print(f"  Created: __init__.py")
                
                # Backup original
                shutil.move(TEMPLATES_FILE, TEMPLATES_FILE + '.bak')
                print(f"\nOriginal moved to backup: {TEMPLATES_FILE}.bak")
                print("Done!")
