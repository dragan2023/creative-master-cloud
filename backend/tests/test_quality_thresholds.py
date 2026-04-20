"""
单元概述质控阈值测试工具

用于测试和优化评分阈值，避免误报和漏报。

使用方法:
    cd backend
    python tests/test_quality_thresholds.py

@date: 2026-04-14
@author: AI助手
"""
from app.services.quality_control.analyzers.unit_quality_analyzer import (
    UnitStructureAnalyzer,
    UnitCharacterAnalyzer,
    UnitConsistencyAnalyzer
)
from typing import List, Dict
import json
import asyncio
import sys
import os
from pathlib import Path

# 添加backend目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


class QualityThresholdTester:
    """质控阈值测试器"""

    def __init__(self):
        self.structure_analyzer = UnitStructureAnalyzer()
        self.character_analyzer = UnitCharacterAnalyzer()
        self.consistency_analyzer = UnitConsistencyAnalyzer()

    def generate_test_data(self) -> Dict[str, List[Dict]]:
        """生成不同质量的测试数据"""

        # 测试集1: 高质量单元概述（应该得高分）
        high_quality = [
            {
                "chapter_number": i,
                "id": i,
                "content": f"第{i}章：主角遭遇重大危机，与反派展开激烈对决。在生死关头，主角突破自我，觉醒新能力，最终逆转局势。此战奠定了主角在势力中的地位，同时也引出了更大的阴谋。",
                "summary": f"主角遭遇重大危机，与反派展开激烈对决。在生死关头，主角突破自我，觉醒新能力，最终逆转局势。"
            }
            for i in range(1, 21)
        ]

        # 测试集2: 低质量单元概述（过短、平淡）
        low_quality = [
            {
                "chapter_number": i,
                "id": i,
                "content": f"主角在家里休息。" if i % 2 == 0 else f"主角出去买东西。",
                "summary": f"主角休息。" if i % 2 == 0 else f"主角买东西。"
            }
            for i in range(1, 21)
        ]

        # 测试集3: 混合质量（部分好部分差）
        mixed_quality = []
        for i in range(1, 31):
            if i <= 10:
                # 前10章高质量
                mixed_quality.append({
                    "chapter_number": i,
                    "id": i,
                    "content": f"第{i}章：主角发现重要线索，展开调查。遭遇敌人伏击，展开激烈战斗。最终击败敌人，获得关键信息。",
                    "summary": f"主角发现线索并遭遇战斗。"
                })
            elif i <= 20:
                # 中间10章低质量（连续平淡）
                mixed_quality.append({
                    "chapter_number": i,
                    "id": i,
                    "content": f"主角在家里休息。什么都没发生。",
                    "summary": f"主角休息。"
                })
            else:
                # 后10章高质量
                mixed_quality.append({
                    "chapter_number": i,
                    "id": i,
                    "content": f"第{i}章：主角根据线索找到宝藏，但遭遇强大守护兽。经过艰苦战斗，主角成功击败守护兽，获得宝藏。",
                    "summary": f"主角找到宝藏并战斗。"
                })

        # 测试集4: 矛盾状态（人物发展问题）
        contradictory = [
            {
                "chapter_number": 1,
                "id": 1,
                "content": "主角安全地回到家中，享受平静的生活。突然敌人来袭，主角在战斗中被杀。但主角又复活了，继续冒险。",
                "summary": "主角被杀但又复活。"
            },
            {
                "chapter_number": 2,
                "id": 2,
                "content": "主角失败后放弃了一切。但第二天又充满信心，决定重新开始。",
                "summary": "主角失败后重新开始。"
            }
        ]

        return {
            "high_quality": high_quality,
            "low_quality": low_quality,
            "mixed_quality": mixed_quality,
            "contradictory": contradictory
        }

    async def test_structure_analyzer(self, test_data: Dict[str, List[Dict]]):
        """测试单元结构分析器"""
        print("\n" + "="*80)
        print("测试: 单元结构分析器")
        print("="*80)

        for name, data in test_data.items():
            print(f"\n--- 测试集: {name} ({len(data)}个单元) ---")

            result = await self.structure_analyzer.analyze(
                chapters_data=data,
                project=None,
                depth="standard",
                db=None,
                user_id=0
            )

            print(f"得分: {result['score']}")
            print(f"问题数: {len(result['issues'])}")

            # 统计问题类型
            categories = {}
            severities = {"critical": 0, "warning": 0, "info": 0}
            for issue in result['issues']:
                cat = issue.get('category', 'unknown')
                categories[cat] = categories.get(cat, 0) + 1
                sev = issue.get('severity', 'info')
                severities[sev] += 1

            print(f"问题分类: {categories}")
            print(f"严重程度: {severities}")

            # 打印部分问题详情
            if result['issues']:
                print("\n问题示例:")
                for i, issue in enumerate(result['issues'][:3]):
                    print(
                        f"  {i+1}. [{issue.get('severity')}] {issue.get('description')}")

    async def test_character_analyzer(self, test_data: Dict[str, List[Dict]]):
        """测试人物发展分析器"""
        print("\n" + "="*80)
        print("测试: 人物发展分析器")
        print("="*80)

        for name, data in test_data.items():
            print(f"\n--- 测试集: {name} ({len(data)}个单元) ---")

            result = await self.character_analyzer.analyze(
                chapters_data=data,
                project=None,
                depth="standard",
                db=None,
                user_id=0
            )

            print(f"得分: {result['score']}")
            print(f"问题数: {len(result['issues'])}")

            if result['issues']:
                print("\n问题示例:")
                for i, issue in enumerate(result['issues'][:3]):
                    print(
                        f"  {i+1}. [{issue.get('severity')}] {issue.get('description')}")

    async def test_consistency_analyzer(self, test_data: Dict[str, List[Dict]]):
        """测试一致性分析器"""
        print("\n" + "="*80)
        print("测试: 一致性分析器")
        print("="*80)

        # 模拟全局大纲
        global_outline = """
        这是一部玄幻小说，讲述主角从凡人成长为强者的故事。
        主角将在第10章觉醒血脉之力，第20章突破到筑基期，第30章获得神器。
        主要反派是魔教教主，最终决战在第50章。
        世界观设定：修炼分为炼气、筑基、金丹、元婴四个境界。
        """

        for name, data in test_data.items():
            print(f"\n--- 测试集: {name} ({len(data)}个单元) ---")

            result = await self.consistency_analyzer.analyze(
                chapters_data=data,
                project=None,
                depth="standard",
                db=None,
                user_id=0,
                global_outline=global_outline
            )

            print(f"得分: {result['score']}")
            print(f"问题数: {len(result['issues'])}")

            if 'deviation_rate' in result.get('metadata', {}):
                print(f"偏离率: {result['metadata']['deviation_rate']}%")

            if result['issues']:
                print("\n问题示例:")
                for i, issue in enumerate(result['issues'][:3]):
                    print(
                        f"  {i+1}. [{issue.get('severity')}] {issue.get('description')}")

    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "#"*80)
        print("# 单元概述质控阈值测试工具")
        print("# 目标: 验证评分阈值的合理性，避免误报和漏报")
        print("#"*80)

        test_data = self.generate_test_data()

        # 测试三个分析器
        await self.test_structure_analyzer(test_data)
        await self.test_character_analyzer(test_data)
        await self.test_consistency_analyzer(test_data)

        # 总结建议
        print("\n" + "="*80)
        print("测试总结与建议")
        print("="*80)
        print("""
请根据测试结果评估：

1. 高质量测试集是否得到高分（>80）？
   - 如果否，说明阈值过于严格，需要放宽

2. 低质量测试集是否得到低分（<60）？
   - 如果否，说明阈值过于宽松，需要收紧

3. 混合质量测试集是否能准确识别问题区域？
   - 检查问题定位是否准确

4. 矛盾状态测试集是否能检测到问题？
   - 检查人物发展检测是否有效

5. 误报率是否可接受？
   - 高质量内容被误判为有问题的比例

6. 漏报率是否可接受？
   - 低质量内容未被检测出的比例

根据评估结果，调整以下阈值：
- _calculate_structure_score() 中的扣分规则
- _calculate_character_score() 中的扣分规则
- _calculate_consistency_score() 中的扣分规则
- _analyze_unit_length_distribution() 中的长度阈值
- _analyze_pacing_rules() 中的平淡判定条件
        """)


async def main():
    """主函数"""
    tester = QualityThresholdTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
