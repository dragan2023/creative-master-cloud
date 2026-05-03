"""
DeepSeek 思考模式 - 快速使用示例

展示如何在不同场景下使用思考模式
"""
import asyncio
from app.agents.llm_manager import get_llm_manager


async def example_1_basic_usage():
    """示例1: 基本使用 - 通过 LLM Manager"""
    print("=" * 60)
    print("示例1: 基本使用（通过 LLM Manager）")
    print("=" * 60)
    
    llm_manager = get_llm_manager()
    
    # 创建启用思考模式的提供者
    provider = llm_manager.create_provider(
        provider_name="deepseek",
        api_key="your-api-key",  # 替换为你的 API Key
        model_name="deepseek-v4-pro",
        reasoning_effort="high",      # 思考强度：high 或 max
        enable_thinking=True,         # 启用思考模式
        thinking_save_dir="./data/thinking_logs"
    )
    
    # 调用
    response = await provider.generate(
        prompt="请分析这个故事的主题和象征意义",
        module_name="theme_analysis"
    )
    
    print(f"内容: {response.content[:100]}...")
    print(f"思考过程: {'有' if response.reasoning_content else '无'}")


async def example_2_quality_control():
    """示例2: 在质控分析中使用思考模式"""
    print("\n" + "=" * 60)
    print("示例2: 质控分析中使用思考模式")
    print("=" * 60)
    
    llm_manager = get_llm_manager()
    
    # 质控场景推荐使用高思考强度
    provider = llm_manager.create_provider(
        provider_name="deepseek",
        api_key="your-api-key",
        model_name="deepseek-v4-pro",
        reasoning_effort="max",       # 最高思考强度
        enable_thinking=True,
        thinking_save_dir="./data/thinking_logs/qc"
    )
    
    # 逻辑一致性检查
    response = await provider.generate(
        prompt="""
请检查以下两段内容是否存在逻辑矛盾：

【第一段】
张三在2020年大学毕业，之后在北京工作了3年。

【第二段】
张三2019年就已经在上海的公司担任经理职务。
        """,
        module_name="logic_consistency_check"
    )
    
    print(f"检查结果: {response.content[:200]}...")
    if response.reasoning_content:
        print("💡 思考过程已保存到: ./data/thinking_logs/qc/")


async def example_3_stream_generation():
    """示例3: 流式生成中的思考模式"""
    print("\n" + "=" * 60)
    print("示例3: 流式生成（思考过程自动保存，不输出到前端）")
    print("=" * 60)
    
    from app.agents.deepseek_provider import DeepSeekProvider
    
    provider = DeepSeekProvider(
        api_key="your-api-key",
        model_name="deepseek-v4-flash",
        reasoning_effort="high",
        enable_thinking=True,
        thinking_save_dir="./data/thinking_logs/stream"
    )
    
    print("⏳ 开始流式生成（思考过程不会显示在这里）...\n")
    
    # 流式调用
    full_content = []
    async for chunk in provider.generate_stream(
        prompt="请写一段关于春天的诗歌",
        module_name="spring_poem"
    ):
        full_content.append(chunk)
        print(chunk, end="", flush=True)
    
    print("\n\n✅ 生成完成")
    print("💡 思考过程已保存到: ./data/thinking_logs/stream/spring_poem_*.txt")


async def example_4_compare_models():
    """示例4: 对比不同模型的思考能力"""
    print("\n" + "=" * 60)
    print("示例4: 对比 V4 Pro 和 V4 Flash 的思考模式")
    print("=" * 60)
    
    from app.agents.deepseek_provider import DeepSeekProvider
    
    # V4 Pro
    pro_provider = DeepSeekProvider(
        api_key="your-api-key",
        model_name="deepseek-v4-pro",
        reasoning_effort="high",
        enable_thinking=True,
        thinking_save_dir="./data/thinking_logs/compare"
    )
    
    # V4 Flash
    flash_provider = DeepSeekProvider(
        api_key="your-api-key",
        model_name="deepseek-v4-flash",
        reasoning_effort="high",
        enable_thinking=True,
        thinking_save_dir="./data/thinking_logs/compare"
    )
    
    test_question = "解释为什么天空是蓝色的"
    
    print(f"问题: {test_question}\n")
    
    # 测试 Pro
    print("🔵 使用 V4 Pro:")
    pro_response = await pro_provider.generate(
        prompt=test_question,
        module_name="compare_pro"
    )
    print(f"   回答: {pro_response.content[:100]}...")
    print(f"   思考: {'有' if pro_response.reasoning_content else '无'}")
    
    # 测试 Flash
    print("\n⚡ 使用 V4 Flash:")
    flash_response = await flash_provider.generate(
        prompt=test_question,
        module_name="compare_flash"
    )
    print(f"   回答: {flash_response.content[:100]}...")
    print(f"   思考: {'有' if flash_response.reasoning_content else '无'}")


async def example_5_disable_thinking():
    """示例5: 关闭思考模式（用于简单任务）"""
    print("\n" + "=" * 60)
    print("示例5: 关闭思考模式（提高响应速度）")
    print("=" * 60)
    
    from app.agents.deepseek_provider import DeepSeekProvider
    
    # 不启用思考模式
    provider = DeepSeekProvider(
        api_key="your-api-key",
        model_name="deepseek-v4-flash",
        enable_thinking=False  # 关闭思考模式
    )
    
    # 简单问答不需要思考模式
    response = await provider.generate(
        prompt="北京的首都是哪里？",
        module_name="simple_qa"
    )
    
    print(f"问题: 北京的首都是哪里？")
    print(f"回答: {response.content}")
    print(f"思考过程: {'有' if response.reasoning_content else '无（符合预期）'}")


async def main():
    """运行所有示例"""
    print("\n🚀 DeepSeek 思考模式使用示例\n")
    
    # 注意: 这些示例需要真实的 API Key 才能运行
    # 请将 'your-api-key' 替换为你的实际 API Key
    
    print("⚠️  注意: 以下示例需要配置真实的 DeepSeek API Key")
    print("    请在代码中将 'your-api-key' 替换为你的实际 API Key\n")
    
    # 取消注释以运行示例
    # await example_1_basic_usage()
    # await example_2_quality_control()
    # await example_3_stream_generation()
    # await example_4_compare_models()
    # await example_5_disable_thinking()
    
    print("💡 提示: 取消注释相应的示例函数来运行测试")
    print("📖 详细说明请查看: THINKING_MODE_EXAMPLE.md\n")


if __name__ == "__main__":
    asyncio.run(main())
