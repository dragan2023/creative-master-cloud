# -*- coding: utf-8 -*-
"""语法验证脚本"""
import py_compile
import os
import sys

backend = r'f:\python_project\全能创意大师（开发版）\backend'
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
ok = True
for f in files:
    path = os.path.join(backend, f)
    if not os.path.exists(path):
        print(f'[SKIP] 文件不存在: {f}')
        continue
    try:
        py_compile.compile(path, doraise=True)
        print(f'[OK] {f}')
    except py_compile.PyCompileError as e:
        print(f'[FAIL] {f}: {e}')
        ok = False
if ok:
    print('ALL CHECKS PASSED')
else:
    sys.exit(1)
