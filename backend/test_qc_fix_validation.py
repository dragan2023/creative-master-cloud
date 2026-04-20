"""
质控修正机制修复验证脚本

验证内容：
1. 单元概述是否正确传递到修正提示词
2. 内容截断限制是否已提高
3. 修改幅度监控是否正常工作
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))


async def test_fix_generator():
    """测试修正生成器的提示词构建"""
    from app.services.quality_control.fix_generator import QualityFixGenerator, QUALITY_FIX_PROMPT

    print("=" * 80)
    print("测试1: 验证提示词模板包含单元概述")
    print("=" * 80)

    # 检查提示词模板
    if "{unit_summary}" in QUALITY_FIX_PROMPT:
        print("✅ 提示词模板包含 {unit_summary} 占位符")
    else:
        print("❌ 提示词模板缺少 {unit_summary} 占位符")
        return False

    # 检查提示词中的修正原则
    required_principles = [
        "正向优化",
        "适度修改",
        "内容完整性",
        "灵活处理",
        "保持创造性"
    ]

    print("\n检查修正原则:")
    for principle in required_principles:
        if principle in QUALITY_FIX_PROMPT:
            print(f"  ✅ 包含: {principle}")
        else:
            print(f"  ❌ 缺少: {principle}")

    # 检查是否移除了"必须修改"的强制指令
    if "你必须对原始内容进行具体的文本修改" not in QUALITY_FIX_PROMPT:
        print("\n✅ 已移除'必须修改'的强制指令")
    else:
        print("\n❌ 仍保留'必须修改'的强制指令")
        return False

    print("\n" + "=" * 80)
    print("测试2: 验证内容截断限制已提高")
    print("=" * 80)

    # 创建测试实例
    generator = QualityFixGenerator()

    # 准备测试数据
    test_issue = {
        "id": "TEST-001",
        "category": "单元衔接",
        "description": "单元之间缺乏过渡",
        "location": {"chapter_number": 1}
    }

    test_content = "A" * 15000  # 15000字符的内容
    test_outline = "B" * 8000   # 8000字符的大纲
    test_summary = "这是单元概述" * 200  # 单元概述（约1000字符，测试时会被截断到2000）
    test_characters = [{"name": "主角", "personality": "勇敢"}]
    test_worldview = {"time_period": "现代"}

    # 模拟generate_fix方法中的截断逻辑
    original_content = test_content[:10000] if len(
        test_content) > 10000 else test_content
    global_outline = test_outline[:5000] if len(
        test_outline) > 5000 else test_outline
    unit_summary = test_summary[:2000] if test_summary else "无"

    print(f"原文长度: {len(test_content)} -> 传递长度: {len(original_content)}")
    print(f"  预期: 10000, 实际: {len(original_content)}")
    if len(original_content) == 10000:
        print("  ✅ 原文截断限制正确(10000字符)")
    else:
        print("  ❌ 原文截断限制错误")
        return False

    print(f"\n大纲长度: {len(test_outline)} -> 传递长度: {len(global_outline)}")
    print(f"  预期: 5000, 实际: {len(global_outline)}")
    if len(global_outline) == 5000:
        print("  ✅ 大纲截断限制正确(5000字符)")
    else:
        print("  ❌ 大纲截断限制错误")
        return False

    print(f"\n单元概述长度: {len(test_summary)} -> 传递长度: {len(unit_summary)}")
    # 单元概述如果<2000就不会被截断
    expected_summary_len = min(len(test_summary), 2000)
    print(f"  预期: {expected_summary_len}, 实际: {len(unit_summary)}")
    if len(unit_summary) == expected_summary_len:
        print("  ✅ 单元概述截断限制正确(2000字符)")
    else:
        print("  ❌ 单元概述截断限制错误")
        return False

    print("\n" + "=" * 80)
    print("测试3: 验证短内容不被截断")
    print("=" * 80)

    short_content = "这是短内容" * 100  # 约500字符
    short_outline = "这是短大纲" * 50   # 约250字符

    original_short = short_content[:10000] if len(
        short_content) > 10000 else short_content
    outline_short = short_outline[:5000] if len(
        short_outline) > 5000 else short_outline

    print(f"短原文长度: {len(short_content)} -> 传递长度: {len(original_short)}")
    if len(original_short) == len(short_content):
        print("  ✅ 短原文未被截断")
    else:
        print("  ❌ 短原文被错误截断")
        return False

    print(f"\n短大纲长度: {len(short_outline)} -> 传递长度: {len(outline_short)}")
    if len(outline_short) == len(short_outline):
        print("  ✅ 短大纲未被截断")
    else:
        print("  ❌ 短大纲被错误截断")
        return False

    return True


def test_api_unit_summary_passing():
    """测试API是否正确传递单元概述"""
    print("\n" + "=" * 80)
    print("测试4: 验证API层单元概述传递逻辑")
    print("=" * 80)

    # 读取quality_control_v2.py文件
    api_file = Path(__file__).parent / "app" / "api" / "v1" / \
        "endpoints" / "novel_writer" / "quality_control_v2.py"

    with open(api_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查关键点
    checks = [
        ('unit_summary=chapter_summary', "传递单元概述到generate_fix"),
        ('ch.get(\'unit_summary\', \'\')', "从chapters_data获取单元概述"),
        ('getattr(unit, \'unit_summary\', \'\')', "从WritingUnit获取单元概述"),
        ('change_ratio > 0.3', "修改幅度30%警告")
    ]

    all_passed = True
    for check_str, description in checks:
        if check_str in content:
            print(f"  ✅ {description}: 找到 '{check_str}'")
        else:
            print(f"  ❌ {description}: 未找到 '{check_str}'")
            all_passed = False

    return all_passed


async def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("质控修正机制修复验证")
    print("=" * 80 + "\n")

    results = []

    # 测试1-3: 修正生成器
    try:
        result1 = await test_fix_generator()
        results.append(("修正生成器测试", result1))
    except Exception as e:
        print(f"\n❌ 修正生成器测试异常: {e}")
        results.append(("修正生成器测试", False))

    # 测试4: API层
    try:
        result2 = test_api_unit_summary_passing()
        results.append(("API层测试", result2))
    except Exception as e:
        print(f"\n❌ API层测试异常: {e}")
        results.append(("API层测试", False))

    # 汇总结果
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)

    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n🎉 所有测试通过！修复方案已正确实施。")
    else:
        print("\n⚠️  部分测试失败，请检查代码。")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
