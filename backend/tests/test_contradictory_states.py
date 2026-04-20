"""
矛盾状态检测有效性测试工具

用于验证人物发展分析器能否正确检测真实的矛盾状态。

使用方法:
    cd backend
    python tests/test_contradictory_states.py

@date: 2026-04-14
@author: AI助手
"""
from app.services.quality_control.analyzers.unit_quality_analyzer import UnitCharacterAnalyzer
import asyncio
import sys
from pathlib import Path

# 添加backend目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


class ContradictoryStateTester:
    """矛盾状态检测测试器"""

    def __init__(self):
        self.analyzer = UnitCharacterAnalyzer()

    def get_test_cases(self):
        """获取测试用例"""
        return {
            "案例1_真实矛盾_无转折": {
                "description": "主角从生到死但没有复活描述（真实矛盾）",
                "data": [
                    {
                        "chapter_number": 1,
                        "id": 1,
                        "content": "主角还活着，与反派激战。最终不敌，被反派一剑击杀，倒在血泊中死去。主角的身体已经完全冰冷，确认死亡。",
                        "summary": "主角从活着到死亡。"
                    }
                ],
                "should_detect": True,  # 应该检测到矛盾
                "expected_category": "状态矛盾"
            },

            "案例2_成语误报_生死关头": {
                "description": "使用成语'生死关头'（不应误报）",
                "data": [
                    {
                        "chapter_number": 1,
                        "id": 1,
                        "content": "主角在生死关头突破自我，觉醒新能力，最终战胜敌人。",
                        "summary": "主角在生死关头突破。"
                    }
                ],
                "should_detect": False,  # 不应该误报
                "expected_category": None
            },

            "案例3_有转折词_复活": {
                "description": "有明确转折词'复活'（不应误报）",
                "data": [
                    {
                        "chapter_number": 1,
                        "id": 1,
                        "content": "主角在战斗中被杀，但通过神器复活，继续冒险。",
                        "summary": "主角被杀后复活。"
                    }
                ],
                "should_detect": False,  # 不应该误报（有复活）
                "expected_category": None
            },

            "案例4_胜利失败矛盾": {
                "description": "同时出现胜利和失败（真实矛盾）",
                "data": [
                    {
                        "chapter_number": 1,
                        "id": 1,
                        "content": "主角取得了胜利，击败了所有敌人。但随后又遭遇失败，被敌人俘虏。",
                        "summary": "主角胜利后又失败。"
                    }
                ],
                "should_detect": True,  # 应该检测到矛盾
                "expected_category": "状态矛盾"
            },

            "案例5_安全危险矛盾": {
                "description": "同时出现安全和危险（真实矛盾）",
                "data": [
                    {
                        "chapter_number": 1,
                        "id": 1,
                        "content": "主角安全地回到家中，享受平静生活。但家中早已埋伏着危险，主角陷入危机。",
                        "summary": "主角安全回家但遭遇危险。"
                    }
                ],
                "should_detect": True,  # 应该检测到矛盾
                "expected_category": "状态矛盾"
            },

            "案例6_重生类词汇": {
                "description": "使用'重生'词汇（不应误报）",
                "data": [
                    {
                        "chapter_number": 1,
                        "id": 1,
                        "content": "主角死亡后重生回到十年前，决定改变命运。",
                        "summary": "主角重生。"
                    }
                ],
                "should_detect": False,  # 不应该误报（有重生）
                "expected_category": None
            },

            "案例7_成功失败矛盾": {
                "description": "成功和失败矛盾",
                "data": [
                    {
                        "chapter_number": 1,
                        "id": 1,
                        "content": "主角成功破解了密码，打开了宝箱。但发现宝箱是空的，任务失败了。",
                        "summary": "主角成功但任务失败。"
                    }
                ],
                "should_detect": True,  # 应该检测到矛盾
                "expected_category": "状态矛盾"
            }
        }

    async def test_case(self, name, test_case):
        """测试单个案例"""
        print(f"\n{'='*80}")
        print(f"测试案例: {name}")
        print(f"描述: {test_case['description']}")
        print(f"期望检测: {'是' if test_case['should_detect'] else '否'}")
        print(f"{'='*80}")

        # 运行分析
        result = await self.analyzer.analyze(
            chapters_data=test_case['data'],
            project=None,
            depth="standard",
            db=None,
            user_id=0
        )

        # 提取结果
        detected_issues = [
            issue for issue in result['issues']
            if issue.get('category') == test_case.get('expected_category')
        ]

        is_detected = len(detected_issues) > 0
        is_correct = is_detected == test_case['should_detect']

        # 打印结果
        print(f"\n检测结果:")
        print(f"  得分: {result['score']}")
        print(f"  问题数: {len(result['issues'])}")
        print(f"  矛盾检测: {'[已检测]' if is_detected else '[未检测]'}")

        if detected_issues:
            print(f"\n  问题详情:")
            for issue in detected_issues:
                print(
                    f"    - [{issue.get('severity')}] {issue.get('description')}")

        # 判断是否通过
        if is_correct:
            print(f"\n[通过] 测试通过！")
        else:
            print(f"\n[失败] 测试失败！")
            if test_case['should_detect'] and not is_detected:
                print(f"   期望检测到矛盾，但实际未检测到")
            elif not test_case['should_detect'] and is_detected:
                print(f"   期望不检测，但实际误报了")

        return {
            "name": name,
            "passed": is_correct,
            "expected": test_case['should_detect'],
            "actual": is_detected,
            "score": result['score'],
            "issues_count": len(result['issues'])
        }

    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "#"*80)
        print("# 矛盾状态检测有效性测试")
        print("# 目标: 验证人物发展分析器能否正确检测真实矛盾，避免误报")
        print("#"*80)

        test_cases = self.get_test_cases()
        results = []

        for name, test_case in test_cases.items():
            result = await self.test_case(name, test_case)
            results.append(result)

        # 统计结果
        print("\n" + "#"*80)
        print("# 测试总结")
        print("#"*80)

        passed_count = sum(1 for r in results if r['passed'])
        total_count = len(results)
        pass_rate = (passed_count / total_count *
                     100) if total_count > 0 else 0

        print(f"\n总测试数: {total_count}")
        print(f"通过数: {passed_count}")
        print(f"失败数: {total_count - passed_count}")
        print(f"通过率: {pass_rate:.1f}%")

        if pass_rate == 100:
            print(f"\n[优秀] 所有测试通过！矛盾状态检测功能正常！")
        elif pass_rate >= 80:
            print(f"\n[良好] 大部分测试通过，但有少量需要优化")
        else:
            print(f"\n[需改进] 测试通过率较低，需要进一步优化")

        # 打印失败案例
        failed_results = [r for r in results if not r['passed']]
        if failed_results:
            print(f"\n失败案例详情:")
            for r in failed_results:
                print(
                    f"  - {r['name']}: 期望{'检测' if r['expected'] else '不检测'}，实际{'检测' if r['actual'] else '不检测'}")

        return results


async def main():
    """主函数"""
    tester = ContradictoryStateTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
