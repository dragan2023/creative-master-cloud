"""
三维质控v2.0功能测试脚本

测试三大核心功能:
1. 用户反馈学习
2. 多维度交叉验证
3. 智能修正建议

@date: 2026-04-14
@version: v2.0.0
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_feedback_learning():
    """测试用户反馈学习模块"""
    print("\n" + "="*60)
    print("测试1: 用户反馈学习模块")
    print("="*60)

    from app.services.quality_control.analyzers.feedback_learning import get_feedback_manager

    feedback_manager = get_feedback_manager()

    # 测试1: 记录反馈
    print("\n1.1 记录用户反馈...")
    feedback = feedback_manager.record_feedback(
        user_id=999,  # 测试用户ID
        project_id=1,
        issue_id="UL-1",
        dimension="unit_structure",
        category="单元过短",
        feedback_type="false_positive",
        comment="测试反馈"
    )
    print(f"✅ 反馈记录成功: {feedback.feedback_id}")

    # 测试2: 获取误报率
    print("\n1.2 计算误报率...")
    fp_rate = feedback_manager.get_false_positive_rate(
        user_id=999,
        dimension="unit_structure",
        category="单元过短"
    )
    print(f"✅ 误报率: {fp_rate:.2%}")

    # 测试3: 获取调整后阈值
    print("\n1.3 获取调整后阈值...")
    threshold = feedback_manager.get_adjusted_threshold(
        dimension="unit_structure",
        category="单元过短",
        base_threshold=0.3
    )
    print(f"✅ 调整后阈值: {threshold:.3f}")

    # 测试4: 获取学习统计
    print("\n1.4 获取学习统计...")
    stats = feedback_manager.get_learning_statistics(user_id=999)
    print(f"✅ 总反馈数: {stats['total_feedbacks']}")

    print("\n✅ 用户反馈学习模块测试通过")


async def test_cross_validation():
    """测试多维度交叉验证引擎"""
    print("\n" + "="*60)
    print("测试2: 多维度交叉验证引擎")
    print("="*60)

    from app.services.quality_control.analyzers.cross_validation import get_cross_validation_engine

    cross_engine = get_cross_validation_engine()

    # 准备测试数据
    chapters_data = [
        {
            "chapter_number": i,
            "content": f"第{i}单元内容，包含一些情节描述"
        }
        for i in range(1, 11)
    ]

    global_outline = "这是一个关于主角成长的故事，包含决战、转折和觉醒"

    character_profiles = [
        {
            "name": "主角",
            "abilities": ["火球术", "瞬移"],
            "personality": ["勇敢", "聪明"]
        }
    ]

    worldview_settings = {
        "rules": ["魔法需要吟唱", "瞬移有冷却时间"],
        "magic_system": {"type": "元素魔法"}
    }

    # 测试交叉验证
    print("\n2.1 执行交叉验证...")
    result = await cross_engine.validate_all(
        chapters_data=chapters_data,
        global_outline=global_outline,
        character_profiles=character_profiles,
        worldview_settings=worldview_settings,
        depth="standard",
        db=None,
        user_id=999
    )

    print(f"✅ 交叉验证完成")
    print(f"   - 发现问题数: {len(result['issues'])}")
    print(f"   - 综合得分: {result['overall_score']:.1f}")
    print(f"   - 验证维度数: {result['total_validations']}")

    # 显示各维度得分
    print("\n2.2 各维度得分:")
    for dim, score in result['validation_scores'].items():
        print(f"   - {dim}: {score:.1f}")

    print("\n✅ 多维度交叉验证引擎测试通过")


async def test_smart_suggestions():
    """测试智能修正建议引擎"""
    print("\n" + "="*60)
    print("测试3: 智能修正建议引擎")
    print("="*60)

    from app.services.quality_control.analyzers.smart_suggestions import get_smart_suggestion_engine

    suggestion_engine = get_smart_suggestion_engine()

    # 准备测试问题
    test_issues = [
        {
            "id": "UL-1",
            "dimension": "unit_structure",
            "category": "单元过短",
            "severity": "warning",
            "location": {"chapter_number": 1},
            "description": "第1单元概述仅30字，内容过于简略",
            "evidence": "这是很短的内容",
            "suggestion": "建议补充关键情节要素",
            "metadata": {"length": 30}
        },
        {
            "id": "UT-1",
            "dimension": "unit_structure",
            "category": "单元衔接",
            "severity": "info",
            "location": {"chapter_number": 2},
            "description": "第2单元与第3单元之间的衔接可能不够流畅",
            "evidence": "两个单元都较短",
            "suggestion": "建议增加逻辑关联词",
            "metadata": {}
        }
    ]

    chapters_data = [
        {
            "chapter_number": i,
            "content": f"第{i}单元的内容描述"
        }
        for i in range(1, 6)
    ]

    # 测试建议生成
    print("\n3.1 生成智能修正建议...")
    enhanced_issues = suggestion_engine.generate_suggestions(
        issues=test_issues,
        chapters_data=chapters_data
    )

    print(f"✅ 建议生成完成: {len(enhanced_issues)}个问题")

    # 显示建议详情
    print("\n3.2 建议详情:")
    for issue in enhanced_issues:
        print(f"\n   问题: {issue['id']} - {issue['category']}")
        print(f"   优先级: {issue.get('priority', 'N/A')}")
        print(f"   修正难度: {issue.get('fix_difficulty', 'N/A')}")
        print(f"   自动修正: {'✅' if issue.get('auto_fix') else '❌'}")
        if issue.get('auto_fix'):
            print(f"   置信度: {issue['auto_fix'].get('confidence', 0):.0%}")

    print("\n✅ 智能修正建议引擎测试通过")


async def test_integration():
    """测试集成效果"""
    print("\n" + "="*60)
    print("测试4: 集成效果测试")
    print("="*60)

    from app.services.quality_control.analyzers.unit_quality_analyzer import (
        UnitStructureAnalyzer,
        UnitCharacterAnalyzer,
        UnitConsistencyAnalyzer
    )

    # 准备测试数据
    chapters_data = [
        {
            "id": i,
            "chapter_number": i,
            "content": f"第{i}单元的详细内容包括冲突和转折"
        }
        for i in range(1, 21)
    ]

    class MockProject:
        def __init__(self):
            self.id = 1
            self.title = "测试项目"

    # 测试结构分析器
    print("\n4.1 测试单元结构分析器(v2.0)...")
    structure_analyzer = UnitStructureAnalyzer()
    structure_result = await structure_analyzer.analyze(
        chapters_data=chapters_data,
        project=MockProject(),
        depth="standard",
        db=None,
        user_id=999
    )
    print(f"✅ 结构分析完成")
    print(f"   - 得分: {structure_result['score']:.1f}")
    print(f"   - 问题数: {len(structure_result['issues'])}")

    # 测试人物分析器
    print("\n4.2 测试人物发展分析器(v2.0)...")
    character_analyzer = UnitCharacterAnalyzer()
    character_result = await character_analyzer.analyze(
        chapters_data=chapters_data,
        project=MockProject(),
        depth="standard",
        db=None,
        user_id=999
    )
    print(f"✅ 人物分析完成")
    print(f"   - 得分: {character_result['score']:.1f}")
    print(f"   - 问题数: {len(character_result['issues'])}")

    # 测试一致性分析器
    print("\n4.3 测试一致性分析器(v2.0)...")
    consistency_analyzer = UnitConsistencyAnalyzer()
    consistency_result = await consistency_analyzer.analyze(
        chapters_data=chapters_data,
        project=MockProject(),
        global_outline="这是一个包含主角成长和决战的故事",
        character_profiles=[{"name": "主角", "abilities": []}],
        worldview_settings={"rules": []},
        depth="standard",
        db=None,
        user_id=999
    )
    print(f"✅ 一致性分析完成")
    print(f"   - 得分: {consistency_result['score']:.1f}")
    print(f"   - 问题数: {len(consistency_result['issues'])}")

    print("\n✅ 集成效果测试通过")


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("三维质控v2.0功能测试")
    print("="*60)

    try:
        # 测试1: 用户反馈学习
        await test_feedback_learning()

        # 测试2: 交叉验证
        await test_cross_validation()

        # 测试3: 智能建议
        await test_smart_suggestions()

        # 测试4: 集成效果
        await test_integration()

        print("\n" + "="*60)
        print("✅ 所有测试通过!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
