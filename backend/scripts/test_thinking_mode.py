"""
DeepSeek 思考模式测试脚本

用于验证思考模式功能是否正常工作

使用方法（必须使用项目虚拟环境）:
    方式1 - 在 backend 目录下运行:
        cd backend
        venv\\Scripts\\python.exe scripts\\test_thinking_mode.py
    
    方式2 - 激活虚拟环境后运行:
        cd backend
        venv\\Scripts\\activate
        python scripts\\test_thinking_mode.py
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径（ scripts 的父目录）
backend_dir = Path(__file__).parent.parent  # scripts的父目录就是backend
backend_dir_str = str(backend_dir)
if backend_dir_str not in sys.path:
    sys.path.insert(0, backend_dir_str)
    print(f"✅ 已添加路径: {backend_dir_str}")

# 检查是否在虚拟环境中
if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    print("✅ 检测到虚拟环境")
else:
    print("⚠️  警告: 未使用虚拟环境，可能会缺少依赖")
    print("   请使用: backend\\venv\\Scripts\\python.exe scripts\\test_thinking_mode.py")
    print()

# 现在可以正确导入 app 模块
try:
    from app.agents.deepseek_provider import DeepSeekProvider
    from app.core.config import get_settings
    print("✅ 模块导入成功")
except ModuleNotFoundError as e:
    print(f"❌ 导入模块失败: {e}")
    print("\n请确保:")
    print("1. 在 backend 目录下运行")
    print("2. 使用虚拟环境: backend\\venv\\Scripts\\python.exe")
    print("3. 已安装所有依赖: pip install -r requirements.txt")
    print(f"\n当前 sys.path:")
    for p in sys.path[:5]:
        print(f"   - {p}")
    sys.exit(1)


async def test_thinking_mode():
    """测试思考模式功能"""
    print("=" * 60)
    print("DeepSeek 思考模式测试")
    print("=" * 60)
    
    # 获取设置
    settings = get_settings()
    api_key = settings.DEEPSEEK_API_KEY
    
    if not api_key:
        print("❌ 错误: 未配置 DEEPSEEK_API_KEY")
        print("请在 .env 文件中设置 DeepSeek API Key")
        return
    
    # 测试目录
    thinking_save_dir = "./data/thinking_logs_test"
    
    # 创建提供者（启用思考模式）
    provider = DeepSeekProvider(
        api_key=api_key,
        model_name="deepseek-v4-pro",
        reasoning_effort="high",
        enable_thinking=True,
        thinking_save_dir=thinking_save_dir
    )
    
    print(f"\n✅ 已创建 DeepSeekProvider")
    print(f"   模型: deepseek-v4-pro")
    print(f"   思考强度: high")
    print(f"   思考模式: 启用")
    print(f"   保存目录: {thinking_save_dir}")
    
    # 测试问题
    test_prompt = """
请分析以下数学问题的解题思路：

问题：如果一个正方形的边长增加20%，那么它的面积增加百分之多少？

请详细说明你的推理过程。
"""
    
    print(f"\n📝 测试问题: {test_prompt.strip()[:50]}...")
    print("\n⏳ 正在调用 DeepSeek API（思考模式）...")
    
    try:
        # 调用API
        response = await provider.generate(
            prompt=test_prompt,
            module_name="test_math_reasoning"
        )
        
        print("\n" + "=" * 60)
        print("✅ API 调用成功！")
        print("=" * 60)
        
        # 显示响应信息
        print(f"\n📊 Token 使用:")
        if response.usage:
            print(f"   输入: {response.usage.get('prompt_tokens', 0)} tokens")
            print(f"   输出: {response.usage.get('completion_tokens', 0)} tokens")
            print(f"   总计: {response.usage.get('total_tokens', 0)} tokens")
        
        # 检查思考过程
        if response.reasoning_content:
            print(f"\n💭 思考过程:")
            print(f"   长度: {len(response.reasoning_content)} 字符")
            print(f"   已保存到文件")
            
            # 显示思考过程的前200个字符
            print(f"\n   预览: {response.reasoning_content[:200]}...")
        else:
            print(f"\n⚠️  未收到思考过程内容")
        
        # 显示最终答案
        print(f"\n📝 最终答案:")
        print(f"   {response.content[:300]}...")
        
        # 检查保存的文件
        print(f"\n📁 检查保存的思考过程文件:")
        save_dir = Path(thinking_save_dir)
        if save_dir.exists():
            files = list(save_dir.glob("test_math_reasoning_*.txt"))
            if files:
                latest_file = max(files, key=lambda f: f.stat().st_mtime)
                print(f"   ✅ 找到文件: {latest_file.name}")
                print(f"   大小: {latest_file.stat().st_size} 字节")
                
                # 显示文件内容的前10行
                with open(latest_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[:10]
                    print(f"\n   文件预览:")
                    for line in lines:
                        print(f"   {line.rstrip()}")
            else:
                print(f"   ❌ 未找到测试文件")
        else:
            print(f"   ❌ 保存目录不存在")
        
        print("\n" + "=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {type(e).__name__}")
        print(f"   错误信息: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_without_thinking():
    """测试非思考模式（对比）"""
    print("\n" + "=" * 60)
    print("对比测试: 非思考模式")
    print("=" * 60)
    
    settings = get_settings()
    api_key = settings.DEEPSEEK_API_KEY
    
    if not api_key:
        print("❌ 跳过: 未配置 DEEPSEEK_API_KEY")
        return
    
    # 创建提供者（不启用思考模式）
    provider = DeepSeekProvider(
        api_key=api_key,
        model_name="deepseek-v4-pro",
        enable_thinking=False  # 关闭思考模式
    )
    
    print(f"\n✅ 已创建 DeepSeekProvider（非思考模式）")
    
    test_prompt = "请简要解释什么是勾股定理。"
    
    print(f"\n📝 测试问题: {test_prompt}")
    print("\n⏳ 正在调用 DeepSeek API...")
    
    try:
        response = await provider.generate(
            prompt=test_prompt,
            module_name="test_no_thinking"
        )
        
        print("\n✅ API 调用成功！")
        print(f"\n📊 Token 使用:")
        if response.usage:
            print(f"   总计: {response.usage.get('total_tokens', 0)} tokens")
        
        if response.reasoning_content:
            print(f"\n💭 思考过程: 有（{len(response.reasoning_content)} 字符）")
        else:
            print(f"\n💭 思考过程: 无（符合预期）")
        
        print(f"\n📝 答案: {response.content[:200]}...")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")


async def main():
    """主函数"""
    print("\n")
    await test_thinking_mode()
    
    # 询问是否进行对比测试
    print("\n")
    choice = input("是否进行非思考模式对比测试？(y/n): ").strip().lower()
    if choice == 'y':
        await test_without_thinking()
    
    print("\n所有测试完成！\n")


if __name__ == "__main__":
    asyncio.run(main())
