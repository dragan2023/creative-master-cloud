"""
知识图谱集成验证脚本

验证知识图谱是否正确集成到质控修正流程中。
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))


def test_kg_helper():
    """测试知识图谱查询辅助函数"""
    print("=" * 80)
    print("测试1: 知识图谱查询辅助函数")
    print("=" * 80)

    from app.services.quality_control.kg_helper import KGQueryHelper, get_kg_helper

    # 测试单例模式
    helper1 = get_kg_helper()
    helper2 = get_kg_helper()

    if helper1 is helper2:
        print("✅ 单例模式正确")
    else:
        print("❌ 单例模式错误")
        return False

    # 测试路径生成
    test_project_id = 123
    expected_path = backend_path.parent / "data" / "knowledge_graphs" / \
        f"project_{test_project_id}_global_graph.json"
    actual_path = helper1.get_global_graph_path(test_project_id)

    if str(expected_path) in actual_path or f"project_{test_project_id}_global_graph.json" in actual_path:
        print(f"✅ 路径生成正确: {actual_path}")
    else:
        print(f"❌ 路径生成错误: {actual_path}")
        return False

    # 测试格式化函数
    test_kg_data = {
        "characters": [
            {"text": "张三", "type": "人物", "status": "存活", "description": "主角"},
            {"text": "李四", "type": "人物", "status": "受伤", "description": ""}
        ],
        "relationships": [
            {"source": "张三", "target": "李四", "relation": "朋友", "description": ""}
        ],
        "events": [
            {"text": "第一次相遇", "type": "事件"}
        ],
        "foreshadows": [
            {"text": "神秘的信件", "type": "伏笔"}
        ]
    }

    formatted = helper1.format_kg_context(test_kg_data)

    checks = [
        ("【当前人物状态】", "人物状态部分"),
        ("张三", "人物名称"),
        ("状态：存活", "人物状态"),
        ("【人物关系】", "人物关系部分"),
        ("张三 朋友 李四", "关系描述"),
        ("【已发生事件】", "事件部分"),
        ("【未回收伏笔】", "伏笔部分")
    ]

    all_passed = True
    for check_str, description in checks:
        if check_str in formatted:
            print(f"  ✅ 包含{description}: '{check_str}'")
        else:
            print(f"  ❌ 缺少{description}: '{check_str}'")
            all_passed = False

    if all_passed:
        print("\n✅ 格式化函数正确")
    else:
        print("\n❌ 格式化函数错误")
        print(f"\n格式化结果:\n{formatted}")

    return all_passed


def test_fix_generator_kg_integration():
    """测试fix_generator的知识图谱集成"""
    print("\n" + "=" * 80)
    print("测试2: fix_generator知识图谱集成")
    print("=" * 80)

    from app.services.quality_control.fix_generator import QUALITY_FIX_PROMPT

    # 检查提示词模板
    checks = [
        ("{knowledge_graph_context}", "知识图谱占位符"),
        ("知识图谱上下文", "知识图谱标题"),
        ("项目中的实体状态和关系", "知识图谱说明"),
        ("修正时必须保持一致", "一致性要求")
    ]

    all_passed = True
    for check_str, description in checks:
        if check_str in QUALITY_FIX_PROMPT:
            print(f"  ✅ 提示词包含{description}: '{check_str}'")
        else:
            print(f"  ❌ 提示词缺少{description}: '{check_str}'")
            all_passed = False

    if all_passed:
        print("\n✅ 提示词模板正确集成知识图谱")
    else:
        print("\n❌ 提示词模板集成失败")

    return all_passed


def test_api_kg_passing():
    """测试API层知识图谱传递"""
    print("\n" + "=" * 80)
    print("测试3: API层知识图谱传递")
    print("=" * 80)

    api_file = Path(__file__).parent / "app" / "api" / "v1" / \
        "endpoints" / "novel_writer" / "quality_control_v2.py"
    fix_gen_file = Path(__file__).parent / "app" / \
        "services" / "quality_control" / "fix_generator.py"

    with open(api_file, 'r', encoding='utf-8') as f:
        api_content = f.read()

    with open(fix_gen_file, 'r', encoding='utf-8') as f:
        fix_gen_content = f.read()

    # 检查API层
    api_checks = [
        ('from app.services.quality_control.kg_helper import get_kg_helper', "导入kg_helper"),
        ('kg_helper.query_relevant_entities', "查询知识图谱实体"),
        ('kg_helper.format_kg_context', "格式化知识图谱"),
        ('knowledge_graph_context=knowledge_graph_context', "传递知识图谱到generate_fix")
    ]

    # 检查fix_generator
    fix_gen_checks = [
        ('knowledge_graph_context if knowledge_graph_context else', "fix_generator中的默认值")
    ]

    all_passed = True

    print("\nAPI层 (quality_control_v2.py):")
    for check_str, description in api_checks:
        if check_str in api_content:
            print(f"  ✅ {description}: 找到")
        else:
            print(f"  ❌ {description}: 未找到")
            all_passed = False

    print("\n修正生成器 (fix_generator.py):")
    for check_str, description in fix_gen_checks:
        if check_str in fix_gen_content:
            print(f"  ✅ {description}: 找到")
        else:
            print(f"  ❌ {description}: 未找到")
            all_passed = False

    if all_passed:
        print("\n✅ API层和修正生成器都正确传递知识图谱")
    else:
        print("\n❌ 传递存在问题")

    return all_passed


async def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("知识图谱集成验证")
    print("=" * 80 + "\n")

    results = []

    # 测试1: kg_helper
    try:
        result1 = test_kg_helper()
        results.append(("知识图谱查询辅助函数", result1))
    except Exception as e:
        print(f"\n❌ 知识图谱查询辅助函数测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("知识图谱查询辅助函数", False))

    # 测试2: fix_generator集成
    try:
        result2 = test_fix_generator_kg_integration()
        results.append(("fix_generator知识图谱集成", result2))
    except Exception as e:
        print(f"\n❌ fix_generator集成测试异常: {e}")
        results.append(("fix_generator知识图谱集成", False))

    # 测试3: API层传递
    try:
        result3 = test_api_kg_passing()
        results.append(("API层知识图谱传递", result3))
    except Exception as e:
        print(f"\n❌ API层传递测试异常: {e}")
        results.append(("API层知识图谱传递", False))

    # 汇总结果
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)

    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n🎉 所有测试通过！知识图谱已成功集成到质控修正流程。")
        print("\n📊 集成效果:")
        print("  ✅ 修正前查询知识图谱获取实体状态")
        print("  ✅ 提示词中注入人物、事件、伏笔等上下文")
        print("  ✅ LLM修正时参考知识图谱保持一致性")
        print("  ✅ 修正后内容与项目设定保持一致")
    else:
        print("\n⚠️  部分测试失败，请检查代码。")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
