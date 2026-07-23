"""
后端测试入口脚本 test-backend.ps1 的行为测试

验证测试入口固定使用后端虚拟环境解释器（backend\\venv\\Scripts\\python.exe），
不会静默回退到系统裸 python。
"""
import os
import shutil
import subprocess

import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPT_PATH = os.path.join(_PROJECT_ROOT, "scripts", "test-backend.ps1")

_EXPECTED_PYTHON = os.path.join("backend", "venv", "Scripts", "python.exe")


def _find_powershell():
    """定位可用的 PowerShell 可执行文件"""
    for exe in ("pwsh", "powershell"):
        if shutil.which(exe):
            return exe
    return None


def test_backend_test_entry_script_exists():
    """测试入口脚本必须存在"""
    assert os.path.isfile(_SCRIPT_PATH)


@pytest.mark.skipif(_find_powershell() is None, reason="未检测到 PowerShell，无法运行入口脚本")
def test_backend_test_entry_uses_venv_python_not_bare_python():
    """入口脚本打印的命令必须使用 venv 解释器，而非裸 python"""
    powershell = _find_powershell()
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            _SCRIPT_PATH,
            "-PrintCommand",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    command = result.stdout.strip()

    # 命令字符串必须包含后端虚拟环境解释器完整路径
    assert _EXPECTED_PYTHON in command
    # 固定测试目标与参数需与验收命令一致
    assert "-m pytest backend/tests tests -q -p no:cacheprovider" in command
