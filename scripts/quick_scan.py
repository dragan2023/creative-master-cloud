"""Quick scan: identify remaining violations"""
import os

root = r'f:\python_project\全能创意大师（开发版）'

# 1. Root directory check
print("=" * 70)
print("1. 根目录内容")
print("=" * 70)
allowed = {'.devcontainer', '.env', '.env.example', '.env.cloud', 
           '.gitignore', '.pytest_cache', '.qoder', 'README.md',
           'backend', 'dist', 'docs', 'frontend', 'nginx', 
           'output_files', 'scripts', 'tests', 'version.json',
           'docker-compose.cloud.yml', 'docker-compose.prod.yml',
           'CHANGELOG.md', 'Dockerfile'}
# check for violations
for f in sorted(os.listdir(root)):
    if f.startswith('.git'):
        continue
    status = "⚠️" if f not in allowed and os.path.isfile(os.path.join(root, f)) else "✅"
    print(f"  {status} {f}")

# 2. Large Python files
print("\n" + "=" * 70)
print("2. 后端大文件 (>20KB / >400行)")
print("=" * 70)
for dirpath, _, fns in os.walk(os.path.join(root, r'backend\app')):
    for fn in fns:
        fp = os.path.join(dirpath, fn)
        size = os.path.getsize(fp)
        if fn.endswith('.py') and size > 20000:
            rel = fp[len(root)+1:]
            print(f"  {rel:<65s} {size//1024}KB")

# 3. Check line counts
print("\n" + "=" * 70)
print("3. 估算大文件行数")
print("=" * 70)
for dirpath, _, fns in os.walk(os.path.join(root, r'backend\app')):
    for fn in fns:
        fp = os.path.join(dirpath, fn)
        size = os.path.getsize(fp)
        if fn.endswith('.py') and size > 20000:
            rel = fp[len(root)+1:]
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                print(f"  {rel:<60s} {size//1024:>3}KB  ~{len(lines):>4}行")
            except:
                pass

# 4. Direct async_session_maker usage (architecture violation)
print("\n" + "=" * 70)
print("4. 架构违规：直接使用 async_session_maker")
print("=" * 70)
import re
for dirpath, _, fns in os.walk(os.path.join(root, r'backend\app')):
    for fn in fns:
        fp = os.path.join(dirpath, fn)
        if fn.endswith('.py') and not fn.startswith('base'):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                if 'async_session_maker' in content and 'repository' not in content.lower() or True:
                    if 'async_session_maker' in content and 'repository' not in fp.lower():
                        rel = fp[len(root)+1:]
                        # count occurrences
                        cnt = content.count('async_session_maker')
                        print(f"  {rel:<55s} x{cnt}")
            except:
                pass

# Also show session maker in all files (including with repo mention)
print("\n   (全部) ")
for dirpath, _, fns in os.walk(os.path.join(root, r'backend\app')):
    for fn in fns:
        fp = os.path.join(dirpath, fn)
        if fn.endswith('.py'):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                if 'async_session_maker' in content:
                    rel = fp[len(root)+1:]
                    cnt = content.count('async_session_maker')
                    print(f"  {rel:<55s} x{cnt}")
            except:
                pass

# 5. Check naming violations (data/info/temp/flag)
print("\n" + "=" * 70)
print("5. 命名规范违规 (data/info/temp/flag 在函数/方法名中)")
print("=" * 70)
bad_names = ['data', 'info', 'temp', 'flag', 'process', 'handle']
for dirpath, _, fns in os.walk(os.path.join(root, r'backend\app')):
    for fn in fns:
        fp = os.path.join(dirpath, fn)
        if fn.endswith('.py'):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        stripped = line.strip()
                        # Check for def xxx where xxx contains bad names
                        if stripped.startswith('def '):
                            name = stripped[4:].split('(')[0].strip()
                            for bn in bad_names:
                                if bn in name.lower() and len(name) < 20:
                                    rel = fp[len(root)+1:]
                                    print(f"  {rel:<55s}:{i}  {stripped}")
                                    break
            except:
                pass

print("\nDone!")
