# -*- coding: utf-8 -*-
"""
Nuitka 编译配置
用于将核心Python模块编译为.pyd二进制文件，防止源码泄露

使用方法:
    python nuitka-config.py build        # 执行编译
    python nuitka-config.py build --clean  # 清理后重新编译
    python nuitka-config.py verify       # 验证编译产物
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Optional


# ==================== 编译配置 ====================

# 需要编译的核心模块（按优先级排序）
COMPILE_MODULES: Dict[str, Dict] = {
    # AI代理核心模块（最高优先级）
    "agents": {
        "path": "app/agents",
        "description": "AI代理核心逻辑",
        "priority": 1,
        "essential": True,  # 核心必需模块
    },
    # 工具类模块
    "tools": {
        "path": "app/tools",
        "description": "核心工具类（GraphRAG、文档处理等）",
        "priority": 2,
        "essential": True,
    },
    # 核心服务模块
    "services": {
        "path": "app/services",
        "description": "核心业务服务",
        "priority": 3,
        "essential": True,
    },
    # API端点模块
    "api_endpoints": {
        "path": "app/api/v1/endpoints",
        "description": "API端点处理",
        "priority": 4,
        "essential": False,  # 可选编译
    },
}

# 不编译的模块（需要保持Python格式以便动态配置）
EXCLUDE_MODULES: List[str] = [
    "app/main.py",           # FastAPI入口
    "app/core/",             # 配置和数据库连接
    "app/models/",           # SQLAlchemy模型
    "app/schemas/",          # Pydantic模型
    "app/static/",           # 静态资源
    "app/data/",             # 数据目录
]

# Nuitka编译选项
NUITKA_OPTIONS: List[str] = [
    "--mode=package",          # 编译为包模块
    "--assume-yes-for-downloads",  # 自动下载依赖
    "--remove-output",             # 编译成功后删除构建目录
    "--output-dir=.",              # 输出到当前目录
]

# 需要完整包含的包（确保编译所有子模块）
NUITKA_INCLUDE_PACKAGES: Dict[str, str] = {
    "agents": "--include-package=app.agents",
    "tools": "--include-package=app.tools",
    "services": "--include-package=app.services",
}


# ==================== 编译器类 ====================

class NuitkaCompiler:
    """Nuitka编译器管理类"""

    def __init__(self, backend_dir: str):
        self.backend_dir = Path(backend_dir).resolve()
        self.build_log: List[str] = []
        self.compiled_modules: List[str] = []

    def check_nuitka_installed(self) -> bool:
        """检查Nuitka是否已安装"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "nuitka", "--version"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"[OK] Nuitka已安装: {version}")
                return True
        except Exception as e:
            print(f"[ERROR] 检查Nuitka失败: {e}")
        return False

    def install_nuitka(self) -> bool:
        """安装Nuitka"""
        print("[INFO] 正在安装Nuitka...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "nuitka>=2.0.0", "-q"],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                print("[OK] Nuitka安装成功")
                return True
            else:
                print(f"[ERROR] Nuitka安装失败: {result.stderr}")
        except Exception as e:
            print(f"[ERROR] Nuitka安装异常: {e}")
        return False

    def clean_build_artifacts(self, module_name: str) -> None:
        """清理编译产物"""
        # 清理构建目录
        build_dir = self.backend_dir / f"{module_name}.build"
        if build_dir.exists():
            shutil.rmtree(build_dir, ignore_errors=True)
            print(f"[CLEAN] 已删除构建目录: {build_dir}")

        # 清理.dist目录
        dist_dir = self.backend_dir / f"{module_name}.dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir, ignore_errors=True)
            print(f"[CLEAN] 已删除分发目录: {dist_dir}")

    def compile_module(self, module_name: str, module_config: Dict, clean: bool = False) -> bool:
        """
        编译单个模块

        Args:
            module_name: 模块名称
            module_config: 模块配置
            clean: 是否清理后重新编译

        Returns:
            编译是否成功
        """
        module_path = self.backend_dir / module_config["path"]

        if not module_path.exists():
            print(f"[WARN] 模块路径不存在，跳过: {module_path}")
            return False

        print(f"\n{'='*60}")
        print(f"[COMPILE] 开始编译模块: {module_name}")
        print(f"  路径: {module_path}")
        print(f"  描述: {module_config['description']}")
        print(f"{'='*60}")

        # 清理旧的编译产物
        if clean:
            self.clean_build_artifacts(module_name)

        # 构建编译命令
        cmd = [sys.executable, "-m", "nuitka"]
        cmd.extend(NUITKA_OPTIONS)

        # 添加包包含参数（确保编译所有子模块）
        if module_name in NUITKA_INCLUDE_PACKAGES:
            cmd.append(NUITKA_INCLUDE_PACKAGES[module_name])

        # 添加模块路径
        cmd.append(str(module_path))

        print(f"[CMD] {' '.join(cmd)}")

        try:
            # 执行编译
            result = subprocess.run(
                cmd,
                cwd=str(self.backend_dir),
                capture_output=True,
                text=True,
                timeout=1800  # 30分钟超时
            )

            if result.returncode == 0:
                print(f"[OK] 模块 {module_name} 编译成功")

                # 查找生成的.pyd文件（文件名包含Python版本）
                import glob
                pyd_pattern = str(self.backend_dir / f"{module_name}.cp*.pyd")
                pyd_files = glob.glob(pyd_pattern)

                if pyd_files:
                    pyd_file = Path(pyd_files[0])
                    size_kb = pyd_file.stat().st_size / 1024
                    print(f"[INFO] 生成文件: {pyd_file.name} ({size_kb:.1f} KB)")
                    self.compiled_modules.append(module_name)
                    return True
                else:
                    print(f"[WARN] 编译成功但未找到.pyd文件")
            else:
                print(f"[ERROR] 编译失败:")
                print(result.stderr)

        except subprocess.TimeoutExpired:
            print(f"[ERROR] 编译超时（超过30分钟）")
        except Exception as e:
            print(f"[ERROR] 编译异常: {e}")

        return False

    def build_all(self, clean: bool = False) -> Dict[str, bool]:
        """
        编译所有模块

        Args:
            clean: 是否清理后重新编译

        Returns:
            各模块编译结果
        """
        print("\n" + "="*60)
        print("  Nuitka 代码保护编译器")
        print("="*60)

        # 检查Nuitka
        if not self.check_nuitka_installed():
            if not self.install_nuitka():
                return {}

        # 按优先级排序
        sorted_modules = sorted(
            COMPILE_MODULES.items(),
            key=lambda x: x[1]["priority"]
        )

        results = {}
        for module_name, module_config in sorted_modules:
            success = self.compile_module(module_name, module_config, clean)
            results[module_name] = success

            # 如果核心模块编译失败，提示用户
            if not success and module_config.get("essential", False):
                print(f"\n[WARN] 核心模块 {module_name} 编译失败，可能影响功能")

        return results

    def verify_compiled_modules(self) -> bool:
        """
        验证编译产物

        Returns:
            验证是否通过
        """
        print("\n" + "="*60)
        print("  验证编译产物")
        print("="*60)

        import glob
        all_passed = True

        for module_name in self.compiled_modules:
            # 查找.pyd文件（文件名包含Python版本）
            pyd_pattern = str(self.backend_dir / f"{module_name}.cp*.pyd")
            pyd_files = glob.glob(pyd_pattern)

            if pyd_files:
                pyd_file = Path(pyd_files[0])
                size_kb = pyd_file.stat().st_size / 1024
                print(f"[OK] {pyd_file.name} ({size_kb:.1f} KB)")
            else:
                print(f"[MISS] {module_name}.cp*.pyd 不存在")
                all_passed = False

        if all_passed:
            print("\n[SUCCESS] 所有编译产物验证通过")
        else:
            print("\n[WARN] 部分编译产物缺失")

        return all_passed

    def move_pyds_to_app(self) -> None:
        """
        将编译好的.pyd文件移动到对应的app目录
        这样Python可以正常导入
        """
        print("\n" + "="*60)
        print("  移动编译产物到目标目录")
        print("="*60)

        for module_name in self.compiled_modules:
            output_name = module_name.replace("/", "_")
            pyd_file = self.backend_dir / f"{output_name}.pyd"

            if pyd_file.exists():
                # 确定目标目录
                module_config = COMPILE_MODULES.get(module_name, {})
                target_dir = self.backend_dir / module_config.get("path", "")

                if target_dir.exists() and target_dir.is_dir():
                    # 重命名为__init__.pyd或保持原模块名
                    target_file = target_dir / f"{output_name}.pyd"

                    # 如果目标文件已存在，先删除
                    if target_file.exists():
                        target_file.unlink()

                    # 移动文件
                    shutil.move(str(pyd_file), str(target_file))
                    print(
                        f"[MOVE] {pyd_file.name} -> {target_file.relative_to(self.backend_dir)}")

    def generate_build_report(self) -> str:
        """生成构建报告"""
        report = []
        report.append("\n" + "="*60)
        report.append("  编译报告")
        report.append("="*60)
        report.append(f"编译成功的模块: {len(self.compiled_modules)}")

        for module_name in self.compiled_modules:
            output_name = module_name.replace("/", "_")
            pyd_file = self.backend_dir / f"{output_name}.pyd"
            if pyd_file.exists():
                size_kb = pyd_file.stat().st_size / 1024
                report.append(f"  - {module_name}: {size_kb:.1f} KB")

        return "\n".join(report)


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(description="Nuitka代码保护编译器")
    parser.add_argument(
        "action",
        choices=["build", "verify", "install"],
        help="执行的操作: build=编译, verify=验证, install=安装Nuitka"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="清理后重新编译"
    )
    parser.add_argument(
        "--module",
        type=str,
        help="只编译指定模块"
    )

    args = parser.parse_args()

    # 确定backend目录
    backend_dir = Path(__file__).parent.resolve()
    compiler = NuitkaCompiler(str(backend_dir))

    if args.action == "install":
        compiler.install_nuitka()

    elif args.action == "build":
        if args.module:
            # 编译指定模块
            if args.module in COMPILE_MODULES:
                compiler.compile_module(
                    args.module, COMPILE_MODULES[args.module], args.clean)
            else:
                print(f"[ERROR] 未知模块: {args.module}")
                print(f"可用模块: {list(COMPILE_MODULES.keys())}")
        else:
            # 编译所有模块
            results = compiler.build_all(clean=args.clean)
            compiler.generate_build_report()

    elif args.action == "verify":
        compiler.verify_compiled_modules()


if __name__ == "__main__":
    main()
