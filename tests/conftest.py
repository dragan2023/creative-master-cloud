"""
根级测试基础设施配置

将 backend 目录加入 Python 路径，使根 tests/ 下的用例可独立导入 app 包，
避免仅在与 backend/tests 合并收集时才能解析 app 的隐式依赖。
"""
import os
import sys

# 确保 backend 目录在 Python 路径中（根 tests/ 目录无 backend/tests/conftest 的路径副作用）
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
_BACKEND_DIR = os.path.abspath(_BACKEND_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
