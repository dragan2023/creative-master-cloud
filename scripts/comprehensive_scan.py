# -*- coding: utf-8 -*-
"""综合扫描脚本 - 检查项目当前状态"""
import py_compile
import os
import sys
from datetime import datetime

REPORT = []

def log(msg):
    REPORT.append(msg)
    print(msg)

backend = r'f:\python_project\全能创意大师（开发版）\backend'

log(f"=== 项目综合扫描报告 ===")
log(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log(f"")

# === Phase 5-1: 语法验证 ===
log("=" * 60)
log("Phase 5-1: 修改文件语法验证")
log("=" * 60)

verify_files = [
    'app/services/quality_control/__init__.py',
    'app/services/quality_control/service.py',
    'app/core/config.py',
    'app/core/config_presets.py',
    'app/services/task_manager.py',
    'app/services/task_manager_constants.py',
    'app/services/task_manager_cancel.py',
    'app/services/S04_split_suggestions.py',
    'app/main.py',
    'app/agents/writing/orchestrator_agent/quality_control_trigger.py',
    'app/agents/writing/orchestrator_agent/content_pipeline.py',
    'app/services/writing_engine/pipeline/_control.py',
    'app/services/writing_engine/pipeline/_execute.py',
    'app/agents/orchestrator/api/__init__.py',
    'app/agents/orchestrator/__init__.py',
    'app/services/outline_generator/impl/mixins/global_outline.py',
    'app/agents/orchestrator/impl/mixins/context_utils.py',
    'app/agents/orchestrator/impl/mixins/generate_sync.py',
    'app/api/v1/endpoints/knowledge.py',
]

all_ok = True
for f in verify_files:
    path = os.path.join(backend, f)
    if not os.path.exists(path):
        log(f'  [SKIP] 文件不存在: {f}')
        continue
    try:
        py_compile.compile(path, doraise=True)
        log(f'  [OK] {f}')
    except py_compile.PyCompileError as e:
        log(f'  [FAIL] {f}: {e}')
        all_ok = False

if all_ok:
    log(f'\n>>> 语法验证: ALL PASSED')
else:
    log(f'\n>>> 语法验证: FAILED')

# === Phase 5-2: 架构验证 - async_session_maker ===
log(f"\n" + "=" * 60)
log("Phase 5-2: async_session_maker 引用扫描")
log("=" * 60)

# 模块级导入（非缩进）
module_level = []
# 局部导入（缩进）
local_level = []
# 脚本文件
scripts_level = []

for dirpath, dirnames, filenames in os.walk(backend):
    # 排除 venv
    dirnames[:] = [d for d in dirnames if d not in ('venv', '__pycache__', '.git')]
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        rel = os.path.relpath(fp, backend)
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                if 'from app.core.database import async_session_maker' in line:
                    if line.startswith((' ', '\t')):
                        local_level.append(f'  [LOCAL] {rel}:{i}')
                    else:
                        module_level.append(f'  [MODULE] {rel}:{i}')

log(f"模块级引用 ({len(module_level)} 处):")
for r in module_level:
    log(r)
log(f"\n局部级引用 ({len(local_level)} 处):")
for r in local_level:
    log(r)

# === 扫描命名规范 ===
log(f"\n" + "=" * 60)
log("Phase 4 验证: 命名规范 N-01 扫描")
log("=" * 60)

bad_prefixes = ['def process_', 'def do_', 'def handle_', 'def get_data', 'def temp_']
violations = []
for dirpath, dirnames, filenames in os.walk(os.path.join(backend, 'app')):
    dirnames[:] = [d for d in dirnames if d not in ('venv', '__pycache__', '.git')]
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        rel = os.path.relpath(fp, backend)
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                for prefix in bad_prefixes:
                    if stripped.startswith(prefix) and '#' not in stripped.split(prefix)[0]:
                        violations.append(f'  {rel}:{i}  {stripped}')

if violations:
    log(f"发现 {len(violations)} 处命名违规:")
    for v in violations:
        log(v)
else:
    log("未发现命名违规 ✓")

# === 大文件扫描 ===
log(f"\n" + "=" * 60)
log("文件大小扫描 (app/ 目录)")
log("=" * 60)

large_files = []
for dirpath, dirnames, filenames in os.walk(os.path.join(backend, 'app')):
    dirnames[:] = [d for d in dirnames if d not in ('venv', '__pycache__', '.git')]
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        size = os.path.getsize(fp)
        lines = 0
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            lines = sum(1 for _ in f)
        rel = os.path.relpath(fp, backend)
        if lines > 500:
            large_files.append((rel, lines, size))

large_files.sort(key=lambda x: -x[1])
log(f"文件 > 500 行 ({len(large_files)} 个):")
for rel, lines, size in large_files:
    log(f"  {rel:<65s} {lines:>5}行  {size//1024:>4}KB")

# === 文件完整性检查 ===
log(f"\n" + "=" * 60)
log("修改文件完整性检查")
log("=" * 60)

check_files = {
    'app/services/quality_control/service.py': 'QualityControlService',
    'app/core/config_presets.py': 'PRESET_MODELS',
    'app/services/task_manager_constants.py': 'TASK_STATUS',
    'app/services/task_manager_cancel.py': 'set_memory_cancel_token',
    'app/services/S04_split_suggestions.py': 'SPLIT_SUGGESTIONS',
    'app/services/quality_control/__init__.py': 'get_quality_control_service',
}

for rel, marker in check_files.items():
    path = os.path.join(backend, rel)
    if not os.path.exists(path):
        log(f'  [MISSING] {rel}')
        continue
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if marker in content:
        log(f'  [OK] {rel} (contains {marker})')
    else:
        log(f'  [WARN] {rel} (missing {marker})')

# === 总结 ===
log(f"\n" + "=" * 60)
log("扫描完成")
log("=" * 60)
if all_ok and not module_level and not violations:
    log("状态: 所有检查通过 ✓")
else:
    log(f"状态: 存在待处理问题")

# 写入报告文件
report_path = os.path.join(os.path.dirname(backend), 'scan_report.txt')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(REPORT))
print(f"\n报告已保存至: {report_path}")
