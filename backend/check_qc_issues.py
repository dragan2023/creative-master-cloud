"""检查质控问题的实际数据"""
import asyncio
import json
from sqlalchemy import select
from app.core.database import async_session_maker
from app.models.writing_unit import WritingUnit


async def check():
    async with async_session_maker() as db:
        result = await db.execute(
            select(WritingUnit)
            .where(WritingUnit.task_id == 4)
            .order_by(WritingUnit.unit_index)
        )
        units = result.scalars().all()

        print("=" * 80)
        print("质控问题详细检查")
        print("=" * 80)

        total_issues = 0
        total_fixed = 0

        for u in units:
            report = u.quality_control_report or {}
            issues = report.get('issues', [])
            fixes = u.quality_control_fixes or []

            print(f"\n单元 {u.unit_index}:")
            print(f"  - quality_control_status: {u.quality_control_status}")
            print(f"  - quality_control_score: {u.quality_control_score}")
            print(f"  - report.issues数量: {len(issues)}")
            print(f"  - quality_control_fixes数量: {len(fixes)}")
            print(
                f"  - original_content_before_fix: {'有' if u.original_content_before_fix else '无'} ({len(u.original_content_before_fix or '')} 字符)")
            print(
                f"  - final_content: {'有' if u.final_content else '无'} ({len(u.final_content or '')} 字符)")

            total_issues += len(issues)
            total_fixed += len(fixes)

            if issues:
                print(f"  问题列表（前3个）:")
                for issue in issues[:3]:
                    print(
                        f"    - {issue.get('category')}: {issue.get('description', '')[:50]}...")

            # 检查修正内容是否相同
            if u.original_content_before_fix and u.final_content:
                is_same = u.original_content_before_fix == u.final_content
                print(f"  - 修正前后内容是否相同: {is_same}")

        print("\n" + "=" * 80)
        print(f"总计: {total_issues} 个问题, {total_fixed} 个修正")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(check())
