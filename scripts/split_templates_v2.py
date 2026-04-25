"""
Split templates.py into package - v2 cleaner approach
Each subfile defines the template value only (not the key)
Uses exec to safely extract sections
"""
import os
import shutil
import sys

TEMPLATES_FILE = r'f:\python_project\全能创意大师（开发版）\backend\app\agents\prompt_manager\templates.py'
TEMPLATES_DIR = r'f:\python_project\全能创意大师（开发版）\backend\app\agents\prompt_manager\templates'

# Read the file
with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Parse to extract sections - find all top-level keys in DEFAULT_PROMPTS
lines = content.split('\n')

# Find where DEFAULT_PROMPTS starts
dict_start = None
for i, line in enumerate(lines):
    if 'DEFAULT_PROMPTS' in line and '{' in line:
        dict_start = i
        break

if dict_start is None:
    print("ERROR: Could not find DEFAULT_PROMPTS")
    sys.exit(1)

# Find brace positions to extract each top-level key
# Strategy: use the comment lines and key pattern to find boundaries
sections = []  # (comment, key, start_line, end_line)
in_dict = False
brace_depth = 0
current_section = None

for i in range(dict_start, len(lines)):
    line = lines[i]
    
    if not in_dict:
        if '{' in line:
            in_dict = True
            brace_depth = line.count('{') - line.count('}')
        continue
    
    if i > dict_start and not current_section:
        # Check if this is a comment line indicating a new section
        stripped = line.strip()
        if stripped.startswith('#') and not stripped.startswith('# ='):
            current_section = {
                'comment': stripped.lstrip('# '),
                'start': i,
                'brace_depth': 0
            }
    
    if current_section:
        brace_depth += line.count('{') - line.count('}')
        current_section['brace_depth'] = brace_depth
        
        if brace_depth == 0:
            # End of section
            current_section['end'] = i + 1
            
            # Extract the key from the second line of the section
            key_line = lines[current_section['start'] + 1]
            import re
            m = re.search(r'"([^"]+)"\s*:', key_line)
            if m:
                current_section['key'] = m.group(1)
                # Extract content: from the opening { to the closing },
                # but we need the content between braces
                brace_start = None
                for j in range(current_section['start'], current_section['end']):
                    if '{' in lines[j]:
                        brace_start = j
                        break
                
                if brace_start is not None:
                    # Extract raw section content (comment + key + value)
                    current_section['raw_lines'] = lines[current_section['start']:current_section['end']]
                    # Extract value only (from the key-value line to end)
                    current_section['value_lines'] = lines[brace_start:current_section['end']]
                    
                    # Dedent by removing 4 leading spaces from each non-empty line
                    dedented = []
                    for vl in current_section['value_lines']:
                        if vl.strip():
                            if vl.startswith('    '):
                                dedented.append(vl[4:])
                            else:
                                dedented.append(vl)
                        else:
                            dedented.append('')
                    
                    current_section['dedented_value'] = '\n'.join(dedented)
                    
                    sections.append(current_section)
            
            current_section = None

print(f"Found {len(sections)} template sections:")
for s in sections:
    print(f"  - {s['key']:30s} -> ({len(s['raw_lines'])} lines)")

# Create the templates directory
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Write each section to a separate file
for s in sections:
    key = s['key']
    key_to_file = key.replace('-', '_')
    
    # Clean filename - use the key directly
    filepath = os.path.join(TEMPLATES_DIR, f'{key_to_file}.py')
    
    # Build the file content
    file_lines = []
    file_lines.append('"""')
    file_lines.append(f'提示词模板 - {s["comment"]}')
    file_lines.append('"""')
    file_lines.append('')
    
    # Write the dedented value as TEMPLATE variable
    file_lines.append(f'# {s["comment"]}')
    file_lines.append(f'TEMPLATE = {s["dedented_value"]}')
    file_lines.append('')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(file_lines))
        f.write('\n')
    print(f"  Created: {filepath}")

# Now create __init__.py that assembles DEFAULT_PROMPTS
init_lines = []
init_lines.append('"""')
init_lines.append('提示词模板包 - 合并所有子模块模板')
init_lines.append('"""')
init_lines.append('')

# Import all template variables
for s in sections:
    key_to_file = s['key'].replace('-', '_')
    init_lines.append(f'from .{key_to_file} import TEMPLATE as _{key_to_file}_template')

init_lines.append('')
init_lines.append('')
init_lines.append('# 合并所有模板到 DEFAULT_PROMPTS')
init_lines.append('DEFAULT_PROMPTS = {')
for s in sections:
    key = s['key']
    key_to_file = key.replace('-', '_')
    init_lines.append(f'    "{key}": _{key_to_file}_template,')
init_lines.append('}')
init_lines.append('')

init_file = os.path.join(TEMPLATES_DIR, '__init__.py')
with open(init_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(init_lines))
    f.write('\n')
print(f"  Created: {init_file}")

# Rename original to .bak
backup_file = TEMPLATES_FILE + '.bak'
os.rename(TEMPLATES_FILE, backup_file)
print(f"  Renamed original to: {backup_file}")

print("\nDone! templates.py has been split into package.")
