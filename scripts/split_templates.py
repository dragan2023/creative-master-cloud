"""
Split agents/prompt_manager/templates.py into modular package structure
"""
import os
import re

TEMPLATES_FILE = r'f:\python_project\全能创意大师（开发版）\backend\app\agents\prompt_manager\templates.py'
TEMPLATES_DIR = r'f:\python_project\全能创意大师（开发版）\backend\app\agents\prompt_manager\templates'

with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract the docstring and DEFAULT_PROMPTS dict
lines = content.split('\n')

# Find all template sections by looking for comment markers and the key on next line
# Pattern: # comment line followed by "key": {
sections = []
i = 0
while i < len(lines):
    line = lines[i]
    # Match comment lines like:    # 短视频脚本
    comment_match = re.match(r'^\s{4}# (.+)$', line)
    if comment_match:
        comment = comment_match.group(1)
        # Next non-empty line should be "key": {
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        key_match = re.match(r'\s{4}"([^"]+)":\s*\{', lines[j])
        if key_match:
            key = key_match.group(1)
            section_start = i  # include the comment
            # Find the closing }, for this section
            brace_depth = 1
            for k in range(j + 1, len(lines)):
                brace_depth += lines[k].count('{') - lines[k].count('}')
                if brace_depth == 0:
                    section_end = k + 1  # include this line
                    sections.append({
                        'comment': comment,
                        'key': key,
                        'start': section_start,
                        'end': section_end,
                        'lines': lines[section_start:section_end]
                    })
                    i = section_end
                    break
            else:
                i += 1
        else:
            i += 1
    else:
        i += 1

print(f"Found {len(sections)} template sections:")
for s in sections:
    key_to_file = s['key'].replace('-', '_')
    print(f"  - {s['comment']:20s} -> {key_to_file}.py ({s['end']-s['start']} lines)")

# Create the templates directory
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Write each section to a separate file
for s in sections:
    key_to_file = s['key'].replace('-', '_')
    filepath = os.path.join(TEMPLATES_DIR, f'{key_to_file}.py')
    
    # For files other than the first one, the first line may be blank or a comment
    # We'll create clean module files
    module_lines = []
    module_lines.append('"""')
    module_lines.append(f'提示词模板 - {s["comment"]}')
    module_lines.append('"""')
    module_lines.append('')
    
    # Extract the dictionary entry including the comment and the key-value pair
    section_content = '\n'.join(s['lines'])
    
    # Wrap in a proper variable assignment
    module_lines.append(f'# {s["comment"]}')
    module_lines.append(f'TEMPLATE_{key_to_file.upper()} = {section_content[4:] if section_content.startswith("    ") else section_content}')
    # The section_content starts with the comment line (indented 4 spaces), then the key
    # We need to create a valid Python dict
    # Actually, let me just write the raw content as a dict value in a function
    
    # Better approach: each file defines a function that returns the template
    module_lines = []
    module_lines.append('"""')
    module_lines.append(f'提示词模板 - {s["comment"]}')
    module_lines.append('"""')
    module_lines.append('')
    module_lines.append(f'def get_template():')
    module_lines.append(f'    """返回 {s["key"]} 模板字典"""')
    
    # The section content already has proper indentation
    for sl in s['lines']:
        if sl.strip():  # non-empty
            if sl.strip().startswith('#'):
                # Comment line, indent under function
                module_lines.append(f'    {sl}')
            else:
                module_lines.append(f'    {sl}')
        else:
            module_lines.append('')
    
    # Add the dictionary value
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(module_lines))
        f.write('\n')
    print(f"  Created: {filepath}")

# Now create __init__.py that merges all templates
init_lines = []
init_lines.append('"""')
init_lines.append('提示词模板包 - 合并所有子模块模板')
init_lines.append('"""')
init_lines.append('')

# Import all template getters
for s in sections:
    key_to_file = s['key'].replace('-', '_')
    init_lines.append(f'from .{key_to_file} import get_template as _get_{key_to_file}')

init_lines.append('')
init_lines.append('')
init_lines.append('# 合并所有模板到 DEFAULT_PROMPTS')
init_lines.append('DEFAULT_PROMPTS = {')
for s in sections:
    key_to_file = s['key'].replace('-', '_')
    init_lines.append(f'    "{s["key"]}": _get_{key_to_file}(),')
init_lines.append('}')
init_lines.append('')

init_file = os.path.join(TEMPLATES_DIR, '__init__.py')
with open(init_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(init_lines))
    f.write('\n')
print(f"  Created: {init_file}")

# Create a placeholder to replace the original file
backup_file = TEMPLATES_FILE + '.bak'
os.rename(TEMPLATES_FILE, backup_file)
print(f"  Renamed original to: {backup_file}")

print("\nDone! templates.py has been split into package.")
print(f"Update imports in __init__.py and utils.py to use: from app.agents.prompt_manager.templates import DEFAULT_PROMPTS")
print(f"Verify the original file is imported from.")
