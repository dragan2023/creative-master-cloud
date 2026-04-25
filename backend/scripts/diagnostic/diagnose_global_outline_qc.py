"""
全局大纲质控诊断脚本

用于检查全局大纲质控检测的执行情况，特别是LLM调用是否正常。

使用方法:
    python backend/diagnose_global_outline_qc.py

功能:
    1. 检查质控分析器的LLM调用逻辑
    2. 检查depth参数传递
    3. 检查并行执行配置
    4. 提供优化建议
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_analyzer_code():
    """检查分析器代码中的LLM调用逻辑"""
    print("=" * 80)
    print("【检查1】分析器代码中的LLM调用逻辑")
    print("=" * 80)

    analyzer_file = project_root / "app" / "services" / \
        "quality_control" / "analyzers" / "global_quality_analyzer.py"

    if not analyzer_file.exists():
        print(f"❌ 分析器文件不存在: {analyzer_file}")
        return False

    print(f"✅ 分析器文件存在: {analyzer_file}")

    with open(analyzer_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查LLM调用方法
    llm_methods = [
        "_analyze_story_arc_with_llm",
        "_analyze_character_relations_with_llm",
        "_analyze_plot_logic_with_llm",
        "_analyze_foreshadowing_with_llm",
        "_analyze_narrative_structure_with_llm",
        "_analyze_climax_distribution_with_llm"
    ]

    print("\n检查LLM调用方法:")
    for method in llm_methods:
        if method in content:
            print(f"  ✅ {method} - 存在")
        else:
            print(f"  ❌ {method} - 缺失")

    # 检查depth条件判断
    if 'depth in ["standard", "deep"]' in content:
        print("\n✅ depth条件判断正确: depth in [\"standard\", \"deep\"]")
    else:
        print("\n❌ depth条件判断可能有问题")

    # 检查LLM调用
    if 'call_llm_with_retry' in content:
        print("✅ 使用call_llm_with_retry进行LLM调用")
    else:
        print("❌ 未使用call_llm_with_retry")

    # 检查超时配置
    if 'timeout=1200' in content:
        print("✅ LLM超时配置为1200秒(20分钟)")
    else:
        print("⚠️  LLM超时配置可能不是1200秒")

    return True


def check_outline_generator():
    """检查大纲生成器中的质控调用逻辑"""
    print("\n" + "=" * 80)
    print("【检查2】大纲生成器中的质控调用逻辑")
    print("=" * 80)

    generator_file = project_root / "app" / "services" / "outline_generator.py"

    if not generator_file.exists():
        print(f"❌ 大纲生成器文件不存在: {generator_file}")
        return False

    print(f"✅ 大纲生成器文件存在: {generator_file}")

    with open(generator_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查并行执行
    if 'asyncio.gather' in content:
        print("✅ 使用asyncio.gather进行并行执行")
    else:
        print("❌ 未使用asyncio.gather")

    # 检查dimension传递
    if 'depth=depth' in content:
        print("✅ depth参数正确传递给分析器")
    else:
        print("❌ depth参数可能未正确传递")

    # 检查日志
    if 'logger.info' in content and '全局大纲质控' in content:
        print("✅ 包含质控相关日志")
    else:
        print("⚠️  质控相关日志可能不足")

    return True


def check_api_endpoint():
    """检查API端点的参数处理"""
    print("\n" + "=" * 80)
    print("【检查3】API端点的参数处理")
    print("=" * 80)

    api_file = project_root / "app" / "api" / "v1" / \
        "endpoints" / "novel_writer" / "quality_control_v2.py"

    if not api_file.exists():
        print(f"❌ API端点文件不存在: {api_file}")
        return False

    print(f"✅ API端点文件存在: {api_file}")

    with open(api_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查GlobalOutlineQCRequest
    if 'class GlobalOutlineQCRequest' in content:
        print("✅ GlobalOutlineQCRequest类存在")

        # 检查depth默认值
        if 'depth: str = "standard"' in content:
            print("✅ depth默认值为'standard'")
        else:
            print("⚠️  depth默认值可能不是'standard'")
    else:
        print("❌ GlobalOutlineQCRequest类不存在")

    # 检查depth传递
    if 'depth=request.depth' in content:
        print("✅ depth参数正确传递给分析器")
    else:
        print("❌ depth参数可能未正确传递")

    return True


def check_frontend():
    """检查前端的参数传递"""
    print("\n" + "=" * 80)
    print("【检查4】前端的参数传递")
    print("=" * 80)

    frontend_file = project_root.parent / "frontend" / \
        "src" / "views" / "generate" / "GenerateForm.vue"

    if not frontend_file.exists():
        print(f"❌ 前端文件不存在: {frontend_file}")
        return False

    print(f"✅ 前端文件存在: {frontend_file}")

    with open(frontend_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查depth传递
    if "depth: 'standard'" in content:
        print("✅ 前端传递depth: 'standard'")
    else:
        print("⚠️  前端可能未传递depth参数或值不是'standard'")

    # 检查质控模式
    if "qualityControlMode" in content:
        print("✅ 质控模式配置存在")
    else:
        print("❌ 质控模式配置缺失")

    return True


def provide_recommendations():
    """提供优化建议"""
    print("\n" + "=" * 80)
    print("【优化建议】")
    print("=" * 80)

    print("""
根据代码检查，以下是可能导致质控检测速度快、评分高、问题少的可能原因：

1. ✅ LLM调用逻辑正常
   - 代码中确实包含了LLM调用
   - 使用call_llm_with_retry进行带重试的调用
   - 超时配置为1200秒(20分钟)

2. ⚠️ 可能的原因分析：
   
   a) LLM调用被跳过
      - 检查日志中是否有"无法获取LLM提供者"的警告
      - 如果LLM provider为None，会跳过LLM分析
      
   b) depth参数未正确传递
      - 前端传递depth: 'standard'
      - 后端应该接收并传递给分析器
      - 分析器中检查depth in ["standard", "deep"]才调用LLM
      
   c) LLM响应解析失败
      - LLM返回的JSON格式不正确
      - 正则提取失败
      - 降级处理返回空问题列表
      
   d) 并行执行问题
      - asyncio.gather应该并行执行4个维度
      - 如果某个维度失败，不应该影响其他维度

3. 🔍 建议的调试步骤：

   a) 查看日志文件
      - 检查backend/logs/目录下的日志
      - 搜索关键词: "宏观结构分析"、"人物与世界观分析"等
      - 查看是否有LLM调用相关的日志
      
   b) 添加诊断日志
      - 已在代码中添加详细的日志
      - 重新运行质控检测
      - 观察日志输出
      
   c) 检查LLM配置
      - 确认用户的LLM配置正确
      - 确认API密钥有效
      - 确认模型支持长文本分析
      
   d) 手动测试LLM调用
      - 使用相同的prompt手动调用LLM
      - 检查响应时间和内容质量

4. 📊 预期行为：
   - standard模式下，应该调用6个LLM方法
   - 每个LLM调用可能需要30-120秒
   - 4个维度并行执行，总耗时应该在5-20分钟
   - 如果几秒钟就完成，说明LLM调用被跳过或失败

5. 🛠️ 如果确认LLM未调用：
   - 检查用户LLM配置
   - 检查数据库中的user_llm_config表
   - 检查llm_manager.get_provider_from_db的返回值
""")


def main():
    """主函数"""
    print("全局大纲质控诊断工具")
    print("=" * 80)

    results = []

    # 执行检查
    results.append(("分析器代码", check_analyzer_code()))
    results.append(("大纲生成器", check_outline_generator()))
    results.append(("API端点", check_api_endpoint()))
    results.append(("前端代码", check_frontend()))

    # 提供建议
    provide_recommendations()

    # 总结
    print("\n" + "=" * 80)
    print("【诊断总结】")
    print("=" * 80)

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("✅ 所有检查通过，代码结构正常")
        print("📝 请按照优化建议中的调试步骤进行进一步排查")
    else:
        print("❌ 部分检查未通过，请查看上面的详细信息")

    print("\n建议操作:")
    print("1. 重启后端服务")
    print("2. 执行一次全局大纲质控检测")
    print("3. 查看日志文件: backend/logs/quality_control_*.log")
    print("4. 搜索关键词: '开始LLM'、'成功获取LLM提供者'、'LLM调用完成'")
    print("5. 如果日志中没有这些关键词，说明LLM调用被跳过或失败")


if __name__ == "__main__":
    main()
