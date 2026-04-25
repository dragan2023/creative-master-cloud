"""检查质控修正内容是否保存到数据库"""
import asyncio
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
        print("质控修正内容检查")
        print("=" * 80)

        for u in units:
            has_original = u.original_content_before_fix is not None and len(
                u.original_content_before_fix) > 0
            has_final = u.final_content is not None and len(
                u.final_content) > 0

            print(f"\n单元 {u.unit_index} ({u.unit_title or '无标题'}):")
            print(f"  - 质控状态: {u.quality_control_status}")
            print(f"  - 质控得分: {u.quality_control_score}")
            print(f"  - 修正数量: {len(u.quality_control_fixes or [])}")
            print(
                f"  - original_content_before_fix: {'✅ 有' if has_original else '❌ 无'} ({len(u.original_content_before_fix or '')} 字符)")
            print(
                f"  - final_content: {'✅ 有' if has_final else '❌ 无'} ({len(u.final_content or '')} 字符)")

            if has_original:
                preview = u.original_content_before_fix[:100].replace(
                    '\n', ' ')
                print(f"    预览: {preview}...")

            if has_final:
                preview = u.final_content[:100].replace('\n', ' ')
                print(f"    预览: {preview}...")


if __name__ == "__main__":
    asyncio.run(check())
