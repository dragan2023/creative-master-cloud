"""扫描所有 .py 文件，找出需要 from __future__ import annotations 的文件"""
import os, sys

missing = []

for dirpath, dirnames, filenames in os.walk('app'):
    dirnames[:] = [d for d in dirnames if d not in ('__pycache__', '.git')]
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'from __future__ import annotations' in content:
                continue
            # Check if file has argument type annotations (not in comments/strings)
            lines = content.split('\n')
            has_annot = False
            for line in lines:
                s = line.strip()
                if s.startswith(('#', 'import ', 'from ')):
                    continue
                # def func(param: Type) -> ReturnType:
                if ('def ' in s and (': ' in s or '->' in s)):
                    has_annot = True
                    break
                # var: Type = value (class level)
                if ('def ' not in s and s.startswith(('self.', '_')) and ':' in s):
                    has_annot = True
                    break
            if has_annot:
                missing.append(fp)
        except Exception as e:
            pass

print(f'\n缺少 from __future__ import annotations: {len(missing)} 个')
for fp in sorted(missing):
    print(f'  {fp}')
