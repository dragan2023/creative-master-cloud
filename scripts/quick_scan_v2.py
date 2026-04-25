"""Quick scan: identify remaining violations - output to file"""
import os

root = r'f:\python_project\全能创意大师（开发版）'
out = []

# 1. Root directory check
out.append("=" * 70)
out.append("1. 根目录内容")
out.append("=" * 70)
for f in sorted(os.listdir(root)):
    if f.startswith('.git'):
        continue
    is_file = os.path.isfile(os.path.join(root, f))
    marker = "⚠️FILE" if is_file else "  DIR "
    out.append(f"  {marker} {f}")

# 2. Large Python files
out.append("")
out.append("=" * 70)
out.append("2. 后端大文件 (>20KB)")
out.append("=" * 70)
for dirpath, _, fns in os.walk(os.path.join(root, r'backend\app')):
    for fn in fns:
        fp = os.path.join(dirpath, fn)
        size = os.path.getsize(fp)
        if fn.endswith('.py') and size > 20000:
            rel = fp[len(root)+1:]
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                out.append(f"  {rel:<65s} {size//1024:>3}KB  {len(lines):>4}lines")
            except:
                out.append(f"  {rel:<65s} {size//1024:>3}KB")

# 3. Architecture violations - async_session_maker
out.append("")
out.append("=" * 70)
out.append("3. 架构违规：直接使用 async_session_maker (应使用Repository)")
out.append("=" * 70)
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
                    out.append(f"  {rel:<55s} x{cnt}")
            except:
                pass

# 4. Naming violations
out.append("")
out.append("=" * 70)
out.append("4. 命名规范违规 (def xxx 中含 data/info/temp/flag/process/handle)")
out.append("=" * 70)
bad_names = ['data', 'info', 'temp', 'flag', 'process', 'handle']
for dirpath, _, fns in os.walk(os.path.join(root, r'backend\app')):
    for fn in fns:
        fp = os.path.join(dirpath, fn)
        if fn.endswith('.py'):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        stripped = line.strip()
                        if stripped.startswith('def '):
                            name = stripped[4:].split('(')[0].strip()
                            for bn in bad_names:
                                if bn in name.lower() and len(name) < 25:
                                    rel = fp[len(root)+1:]
                                    out.append(f"  {rel:<55s}:{i}  {stripped}")
                                    break
            except:
                pass

# Write output
with open(os.path.join(root, 'scripts', 'scan_result.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))

print(f"Scan complete. {len(out)} lines written to scripts/scan_result.txt")
