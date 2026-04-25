"""
Final version: Split templates.py properly handling key prefixes
"""
import os
import shutil
import ast

TEMPLATES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'backend', 'app', 'agents', 'prompt_manager', 'templates.py')
TEMPLATES_DIR = os.path.join(os.path.dirname(TEMPLATES_FILE), 'templates')

# Restore original if backup exists
bak = TEMPLATES_FILE + '.bak'
if os.path.exists(TEMPLATES_DIR):
    shutil.rmtree(TEMPLATES_DIR)
if os.path.exists(bak) and not os.path.exists(TEMPLATES_FILE):
    shutil.copy2(bak, TEMPLATES_FILE)
    print('Restored templates.py from backup')

with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
    source = f.read()
lines = source.split('\n')
tree = ast.parse(source)

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
                        v_start = v.lineno - 1  # 0-indexed
                        v_end = v.end_lineno     # 1-indexed, exclusive for slicing

                        # First line: find the { position
                        first_line = lines[v_start]
                        brace_pos = first_line.index('{')
                        first_part = first_line[brace_pos:]  # from { onwards

                        # Build value lines with proper dedenting
                        value_lines = [first_part]
                        for i in range(v_start + 1, v_end):
                            line = lines[i]
                            if line.startswith('        '):  # 8 spaces -> 4 spaces
                                value_lines.append(line[4:])
                            elif line.startswith('    '):     # 4 spaces -> 0 spaces
                                value_lines.append(line[4:])
                            else:
                                value_lines.append(line)

                        entries.append({
                            'key': key,
                            'value_text': '\n'.join(value_lines),
                        })

                print(f'Found {len(entries)} entries')

                os.makedirs(TEMPLATES_DIR, exist_ok=True)

                for entry in entries:
                    key = entry['key']
                    fn = key.replace('-', '_')
                    fp = os.path.join(TEMPLATES_DIR, f'{fn}.py')

                    # Find comment
                    comment = key
                    for i, ln in enumerate(lines):
                        stripped = ln.strip()
                        if stripped.startswith('#') and not stripped.startswith('# ='):
                            for j in range(i + 1, min(i + 4, len(lines))):
                                if entry['key'] in lines[j]:
                                    comment = stripped.lstrip('# ').strip()
                                    break

                    content = (
                        f'# -*- coding: utf-8 -*-\n'
                        f'"""\n'
                        f'提示词模板 - {comment}\n'
                        f'"""\n'
                        f'\n'
                        f'TEMPLATE = {entry["value_text"]}\n'
                        f'\n'
                    )
                    with open(fp, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f'  {key:30s} -> {fn}.py')

                # __init__.py
                init_lines = [
                    '# -*- coding: utf-8 -*-',
                    '"""',
                    '提示词模板包 - 合并所有子模块模板',
                    '"""',
                    '',
                ]
                for e in entries:
                    fn = e['key'].replace('-', '_')
                    init_lines.append(f'from .{fn} import TEMPLATE as _{fn}_TEMPLATE')
                init_lines.extend(['', '', 'DEFAULT_PROMPTS = {'])
                for e in entries:
                    fn = e['key'].replace('-', '_')
                    init_lines.append(f'    "{e["key"]}": _{fn}_TEMPLATE,')
                init_lines.append('}')
                init_lines.append('')

                init_fp = os.path.join(TEMPLATES_DIR, '__init__.py')
                with open(init_fp, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(init_lines) + '\n')
                print('  Created: __init__.py')

                # Move original to backup
                shutil.move(TEMPLATES_FILE, TEMPLATES_FILE + '.bak')
                print('Done!')
                break
