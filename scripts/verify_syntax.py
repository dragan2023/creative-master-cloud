# -*- coding: utf-8 -*-
"""语法验证脚本：基于脚本位置定位项目根目录，未检查到任何文件时失败"""
import py_compile
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
backend = project_root / "backend"
files = [
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
    'app/services/writing_engine/pipeline/_control.py',
    'app/services/writing_engine/pipeline/_execute.py',
    'app/agents/orchestrator/api/__init__.py',
    'app/agents/orchestrator/__init__.py',
    'app/services/outline_generator/impl/mixins/global_outline.py',
    'app/agents/orchestrator/impl/mixins/context_utils.py',
    'app/agents/orchestrator/impl/mixins/generate_sync.py',
]
ok = True
checked = 0
for f in files:
    path = backend / f
    if not path.exists():
        print(f'[SKIP] 文件不存在: {f}')
        continue
    checked += 1
    try:
        py_compile.compile(str(path), doraise=True)
        print(f'[OK] {f}')
    except py_compile.PyCompileError as e:
        print(f'[FAIL] {f}: {e}')
        ok = False

if checked == 0:
    print('[FAIL] 未检查任何文件')
    sys.exit(1)

if ok:
    print(f'ALL CHECKS PASSED ({checked} files)')
else:
    sys.exit(1)
