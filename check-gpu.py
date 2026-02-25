"""
GPU 环境诊断脚本
用于检查 PyTorch CUDA 环境是否正确配置
"""
import os
import sys
import subprocess


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_status(name, status, detail=""):
    """打印状态"""
    icon = "✓" if status else "✗"
    print(f"  [{icon}] {name}", end="")
    if detail:
        print(f": {detail}")
    else:
        print()


def check_python_environment():
    """检查当前 Python 环境"""
    print_header("0. Python 环境检查")

    # 当前 Python 路径
    current_python = sys.executable
    print_status("当前 Python", True, current_python)

    # 检查是否在虚拟环境中
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )

    if in_venv:
        print_status("虚拟环境", True, "已激活")
        print(f"      虚拟环境路径: {sys.prefix}")
    else:
        print_status("虚拟环境", False, "未激活（使用系统 Python）")

        # 检查项目虚拟环境是否存在
        script_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.join(script_dir, "backend")
        venv_python = os.path.join(
            backend_dir, "venv", "Scripts", "python.exe")

        if os.path.exists(venv_python):
            print("\n  >>> 检测到项目虚拟环境存在，建议使用虚拟环境运行诊断:")
            print(f"      {venv_python} check-gpu.py")
            print("\n  >>> 或先激活虚拟环境后再运行:")
            print(
                f"      cd backend && venv\\Scripts\\activate && python ..\\check-gpu.py")
        else:
            print("\n  >>> 项目虚拟环境尚未创建，请先运行 start.bat 创建并安装依赖")

    print()
    return in_venv


def check_gpu():
    """检查 GPU 环境"""
    # 先检查 Python 环境
    in_venv = check_python_environment()

    print_header("GPU 环境诊断工具")
    print()

    # ========== 1. 检查 PyTorch ==========
    print_header("1. PyTorch 检查")
    torch_import_error = None
    try:
        import torch
        print_status("PyTorch 已安装", True, f"版本 {torch.__version__}")

        # 检查 CUDA 编译版本
        torch_cuda_version = getattr(torch.version, 'cuda', None)
        if torch_cuda_version:
            print_status("PyTorch CUDA 支持", True, f"CUDA {torch_cuda_version}")
        else:
            print_status("PyTorch CUDA 支持", False, "未编译 CUDA（可能是 CPU 版本）")
            print("\n  >>> 解决方案：重新安装 GPU 版本 PyTorch:")
            print("      pip uninstall torch")
            print(
                "      pip install torch --index-url https://download.pytorch.org/whl/cu126")
            print()

        # 检查 CUDA 是否可用
        cuda_available = torch.cuda.is_available()
        print_status("torch.cuda.is_available()", cuda_available)

        if cuda_available:
            # GPU 详细信息
            gpu_count = torch.cuda.device_count()
            print_status("GPU 设备数量", True, f"{gpu_count} 个")

            for i in range(gpu_count):
                gpu_name = torch.cuda.get_device_name(i)
                gpu_memory = torch.cuda.get_device_properties(
                    i).total_memory / (1024**3)
                print(f"      GPU {i}: {gpu_name} ({gpu_memory:.1f} GB)")

            # 当前设备
            current_device = torch.cuda.current_device()
            print_status("当前 CUDA 设备", True, f"cuda:{current_device}")

            # 测试 GPU 计算
            try:
                test_tensor = torch.randn(1000, 1000, device='cuda')
                result = torch.matmul(test_tensor, test_tensor)
                print_status("GPU 计算测试", True, "矩阵乘法成功")
            except Exception as e:
                print_status("GPU 计算测试", False, str(e)[:50])
        else:
            print("\n  >>> CUDA 不可用，可能原因：")
            print("      1. 安装了 CPU 版本的 PyTorch")
            print("      2. NVIDIA 驱动版本过旧")
            print("      3. CUDA 版本不匹配")

    except ImportError as e:
        torch_import_error = str(e)
        print_status("PyTorch 已安装", False, "未找到 torch 模块")
        print(f"\n  错误详情: {e}")
        print("\n  >>> 解决方案：安装 PyTorch:")
        print("      pip install torch --index-url https://download.pytorch.org/whl/cu126")
    except OSError as e:
        torch_import_error = str(e)
        print_status("PyTorch 导入", False, "DLL 加载失败")
        print(f"\n  错误详情: {e}")

        # 分析 DLL 加载失败原因
        error_str = str(e).lower()
        if "caffe2_nvrtc.dll" in error_str or "nvrtc" in error_str:
            print("\n  >>> 诊断：CUDA 运行时库加载失败")
            print("  这通常是因为：")
            print("      1. PyTorch CUDA 版本与系统 CUDA 不匹配")
            print("      2. 缺少 CUDA 运行时 DLL 文件")
            print("      3. 缺少 Visual C++ Redistributable")
            print("\n  >>> 解决方案：")
            print("      方案1: 重新安装匹配的 PyTorch 版本")
            print("             pip uninstall torch torchvision torchaudio")
            print(
                "             pip install torch --index-url https://download.pytorch.org/whl/cu126")
            print("\n      方案2: 安装 Visual C++ Redistributable")
            print("             下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe")
            print("\n      方案3: 如果不需要 GPU 加速，安装 CPU 版本")
            print("             pip install torch")
        else:
            print("\n  >>> 解决方案：重新安装 PyTorch:")
            print("      pip uninstall torch torchvision torchaudio")
            print(
                "      pip install torch --index-url https://download.pytorch.org/whl/cu126")

    # ========== 2. 检查 NVIDIA 驱动 ==========
    print_header("2. NVIDIA 驱动检查")
    try:
        result = subprocess.run(
            ['nvidia-smi'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print_status("nvidia-smi", True, "NVIDIA 驱动已安装")
            # 解析驱动版本
            for line in result.stdout.split('\n')[:8]:
                if 'Driver Version' in line:
                    print(f"      {line.strip()}")
                    break
            print("\n  GPU 信息:")
            for line in result.stdout.split('\n'):
                if 'RTX' in line or 'GTX' in line or 'Tesla' in line or 'Quadro' in line or '|' in line:
                    if '--' not in line:
                        print(f"    {line}")
        else:
            print_status("nvidia-smi", False, "返回错误")
    except FileNotFoundError:
        print_status("nvidia-smi", False, "未找到（NVIDIA 驱动可能未安装）")
        print("\n  >>> 解决方案：从 NVIDIA 官网下载并安装驱动:")
        print("      https://www.nvidia.com/Download/index.aspx")
    except Exception as e:
        print_status("nvidia-smi", False, str(e))

    # ========== 3. 检查 CUDA Toolkit ==========
    print_header("3. CUDA Toolkit 检查")

    # CUDA_HOME
    cuda_home = os.environ.get('CUDA_HOME') or os.environ.get('CUDA_PATH')
    if cuda_home:
        print_status("CUDA_HOME", True, cuda_home)
    else:
        print_status("CUDA_HOME", False, "未设置（可选，不影响 PyTorch GPU 加速）")

    # nvcc
    try:
        result = subprocess.run(['nvcc', '--version'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print_status("nvcc", True)
            for line in result.stdout.strip().split('\n'):
                print(f"      {line}")
        else:
            print_status("nvcc", False)
    except FileNotFoundError:
        print_status("nvcc", False, "未找到（CUDA Toolkit 可能未安装）")
        print("\n  >>> 注意：CUDA Toolkit 不影响 PyTorch GPU 加速")
        print("      PyTorch 自带 CUDA 运行时，无需单独安装 CUDA Toolkit")
    except Exception as e:
        print_status("nvcc", False, str(e))

    # ========== 4. 环境变量 ==========
    print_header("4. 环境变量检查")

    env_vars = [
        ('CUDA_VISIBLE_DEVICES', 'GPU 设备可见性'),
        ('TORCH_DEVICE', 'PyTorch 设备设置'),
        ('PYTORCH_CUDA_ALLOC_CONF', 'CUDA 内存配置'),
    ]

    for var, desc in env_vars:
        value = os.environ.get(var)
        if value:
            print_status(desc, True, f"{var}={value}")
        else:
            print_status(desc, True, f"{var} 未设置（使用默认值）")

    # ========== 5. 总结 ==========
    print_header("诊断总结")

    if torch_import_error:
        print("\n  ✗ PyTorch 导入失败，无法使用 GPU 加速。")
        print("  请查看上方详细错误信息和解决方案。")
    else:
        try:
            import torch
            if torch.cuda.is_available():
                print("\n  ✓ GPU 加速可用！系统已正确配置 CUDA 环境。")
                print(f"  当前设备: {torch.cuda.get_device_name(0)}")
            else:
                torch_cuda = getattr(torch.version, 'cuda', None)
                if torch_cuda:
                    print("\n  ✗ GPU 加速不可用。")
                    print("  可能原因：NVIDIA 驱动版本与 PyTorch CUDA 版本不匹配")
                    print(f"  当前 PyTorch CUDA 版本: {torch_cuda}")
                    print("\n  >>> 解决方案：")
                    print("      1. 更新 NVIDIA 驱动到最新版本")
                    print("      2. 或安装匹配的 PyTorch 版本:")
                    print(
                        "         pip install torch --index-url https://download.pytorch.org/whl/cu121")
                else:
                    print("\n  ✗ GPU 加速不可用。")
                    print("  原因：安装的是 CPU 版本的 PyTorch")
                    print("\n  >>> 解决方案：重新安装 GPU 版本:")
                    print("      pip uninstall torch")
                    print(
                        "      pip install torch --index-url https://download.pytorch.org/whl/cu126")
        except Exception as e:
            print(f"\n  ✗ 检查过程中发生错误: {e}")

    print("\n" + "=" * 60)
    print(" 诊断完成")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    check_gpu()
    input("\n按回车键退出...")
