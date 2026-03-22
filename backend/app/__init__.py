# 全能创意大师后端应用
# 支持 .pyd 编译模块加载

import sys
import os
import glob
from pathlib import Path


def _setup_pyd_loader():
    """
    设置 .pyd 模块加载器
    使 Python 能够正确导入 Nuitka 编译的 .pyd 模块
    """
    # 获取当前 app 目录
    app_dir = Path(__file__).parent

    # 确保当前目录在 Python 路径中
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    # 检查是否存在编译后的 .pyd 模块（文件名包含Python版本）
    # Nuitka 输出格式: {module}.cp{version}-win_amd64.pyd
    pyd_patterns = ['agents.cp*.pyd', 'tools.cp*.pyd', 'services.cp*.pyd']

    for pattern in pyd_patterns:
        pyd_files = list(app_dir.glob(pattern))
        if pyd_files:
            # .pyd 文件存在，Python 会自动处理
            pass


def _import_compiled_modules():
    """
    导入编译后的模块（如果存在）
    优先使用 .pyd 模块，否则回退到源码
    """
    import importlib.util

    app_dir = Path(__file__).parent

    # 定义模块映射：模块名 -> Python模块路径
    module_mapping = {
        'agents': 'app.agents',
        'tools': 'app.tools',
        'services': 'app.services',
    }

    for module_name, module_path in module_mapping.items():
        # 查找带版本号的 .pyd 文件
        pyd_pattern = f"{module_name}.cp*.pyd"
        pyd_files = list(app_dir.glob(pyd_pattern))

        if pyd_files:
            # 存在编译后的 .pyd 文件，使用第一个匹配的
            pyd_file = pyd_files[0]
            try:
                # 使用 importlib 加载 .pyd
                spec = importlib.util.spec_from_file_location(
                    module_path,
                    str(pyd_file)
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_path] = module
                    spec.loader.exec_module(module)
            except Exception as e:
                # 加载失败，回退到源码
                pass


# 在模块导入时执行设置
_setup_pyd_loader()

# 尝试导入编译后的模块（可选，通常由各模块自行导入）
# _import_compiled_modules()
