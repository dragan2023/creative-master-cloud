"""检查修正前后的内容差异"""
import asyncio
from sqlalchemy import select
from app.core.database import async_session_maker
from app.models.writing_unit import WritingUnit


async def check():
    async with async_session_maker() as db:
        result = await db.execute(
            select(WritingUnit)
            .where(WritingUnit.task_id == 4, WritingUnit.unit_index == 1)
        )
        unit = result.scalar_one()

        print("=" * 80)
        print("单元 1 修正前后内容对比")
        print("=" * 80)

        original = unit.original_content_before_fix or ""
        final = unit.final_content or ""

        print(f"\n原始内容长度: {len(original)}")
        print(f"最终内容长度: {len(final)}")
        print(f"内容是否相同: {original == final}")

        if original != final:
            # 找不同
            for i in range(min(len(original), len(final))):
                if original[i] != final[i]:
                    print(f"\n第一个差异位置: {i}")
                    print(f"原始: ...{original[max(0, i-50):i+50]}...")
                    print(f"最终: ...{final[max(0, i-50):i+50]}...")
                    break
        else:
            print("\n⚠️ 修正前后内容完全相同！")
            print("\n检查修正列表：")
            for fix in (unit.quality_control_fixes or []):
                print(
                    f"  - {fix.get('category')}: {fix.get('description') or fix.get('title') or fix.get('fix') or '无描述'}")

        # 显示前200个字符对比
        print("\n\n原始内容前200字符:")
        print(original[:200])
        print("\n最终内容前200字符:")
        print(final[:200])


if __name__ == "__main__":
    asyncio.run(check())
