"""
功能开关配置验证脚本

验证 ENABLE_QUALITY_CONTROL 环境变量是否正确工作。
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))


def test_env_variable():
    """测试环境变量控制"""
    print("=" * 80)
    print("测试: 功能开关配置化")
    print("=" * 80)

    # 测试1: 默认值（应该为True）
    print("\n测试1: 默认值（未设置环境变量）")
    if "ENABLE_QUALITY_CONTROL" in os.environ:
        del os.environ["ENABLE_QUALITY_CONTROL"]

    # 重新导入以获取新值
    import importlib
    from app.services import outline_generator
    importlib.reload(outline_generator)

    if outline_generator.ENABLE_QUALITY_CONTROL:
        print("  ✅ 默认启用质控功能 (ENABLE_QUALITY_CONTROL=True)")
    else:
        print("  ❌ 默认禁用质控功能")
        return False

    # 测试2: 设置为false
    print("\n测试2: 设置为 false")
    os.environ["ENABLE_QUALITY_CONTROL"] = "false"
    importlib.reload(outline_generator)

    if not outline_generator.ENABLE_QUALITY_CONTROL:
        print("  ✅ 成功禁用质控功能 (ENABLE_QUALITY_CONTROL=False)")
    else:
        print("  ❌ 未能禁用质控功能")
        return False

    # 测试3: 设置为true
    print("\n测试3: 设置为 true")
    os.environ["ENABLE_QUALITY_CONTROL"] = "true"
    importlib.reload(outline_generator)

    if outline_generator.ENABLE_QUALITY_CONTROL:
        print("  ✅ 成功启用质控功能 (ENABLE_QUALITY_CONTROL=True)")
    else:
        print("  ❌ 未能启用质控功能")
        return False

    # 测试4: 检查代码中是否还有硬编码 if False
    print("\n测试4: 检查硬编码 if False")
    outline_file = Path(__file__).parent / "app" / \
        "services" / "outline_generator.py"

    with open(outline_file, 'r', encoding='utf-8') as f:
        content = f.read()

    if "if False and" in content:
        print("  ❌ 仍存在硬编码 if False")
        return False
    else:
        print("  ✅ 无硬编码 if False")

    # 测试5: 检查是否使用环境变量
    if 'os.getenv("ENABLE_QUALITY_CONTROL"' in content:
        print("  ✅ 使用环境变量控制")
    else:
        print("  ❌ 未使用环境变量控制")
        return False

    return True


def show_usage():
    """显示使用说明"""
    print("\n" + "=" * 80)
    print("使用说明")
    print("=" * 80)

    print("""
## 环境变量控制质控功能

### 默认行为
- 未设置环境变量时，质控功能**默认启用** (ENABLE_QUALITY_CONTROL=true)

### 禁用质控功能

#### 方法1: 命令行设置
```bash
# Linux/Mac
export ENABLE_QUALITY_CONTROL=false
python -m uvicorn app.main:app --reload

# Windows (CMD)
set ENABLE_QUALITY_CONTROL=false
python -m uvicorn app.main:app --reload

# Windows (PowerShell)
$env:ENABLE_QUALITY_CONTROL="false"
python -m uvicorn app.main:app --reload
```

#### 方法2: .env 文件
在 `backend/.env` 文件中添加：
```env
# 禁用质控功能
ENABLE_QUALITY_CONTROL=false
```

#### 方法3: Docker 环境变量
```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - ENABLE_QUALITY_CONTROL=false
```

### 启用质控功能
```bash
# 显式启用（默认就是启用）
export ENABLE_QUALITY_CONTROL=true
```

### 验证配置
运行验证脚本：
```bash
cd backend
python test_config_validation.py
```

### 优势
✅ 无需修改代码即可切换功能状态
✅ 支持不同环境使用不同配置（开发/测试/生产）
✅ 符合12-Factor App配置最佳实践
✅ 避免硬编码 if False 的不良实践
""")


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("功能开关配置验证")
    print("=" * 80 + "\n")

    # 保存原始环境变量
    original_value = os.environ.get("ENABLE_QUALITY_CONTROL")

    try:
        result = test_env_variable()

        if result:
            print("\n" + "=" * 80)
            print("✅ 所有测试通过！功能开关已正确配置化")
            print("=" * 80)

            # 显示使用说明
            show_usage()
        else:
            print("\n" + "=" * 80)
            print("❌ 部分测试失败，请检查代码")
            print("=" * 80)

        return result
    finally:
        # 恢复原始环境变量
        if original_value is not None:
            os.environ["ENABLE_QUALITY_CONTROL"] = original_value
        elif "ENABLE_QUALITY_CONTROL" in os.environ:
            del os.environ["ENABLE_QUALITY_CONTROL"]


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
