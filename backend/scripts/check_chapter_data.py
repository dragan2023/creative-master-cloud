"""诊断脚本：验证 NovelChapter 和 WritingUnit 的数据一致性"""
import asyncio, sys
sys.path.insert(0, '.')
from app.core.database import async_session_maker
from sqlalchemy import select
from app.models.novel_chapter import NovelChapter
from app.models.writing_unit import WritingUnit
from app.models.writing_task import WritingTask
from app.models.novel_project import NovelProject

async def check():
    async with async_session_maker() as db:
        # 0. 检查 Project.unit_summaries 的原始结构
        print('=== Project.unit_summaries 原始类型检查 ===')
        pr = await db.execute(select(NovelProject).where(NovelProject.id == 11))
        p = pr.scalar_one()
        us = p.unit_summaries
        t = type(us).__name__
        print(f'  type={t}')
        if isinstance(us, dict):
            print(f'  is_dict, keys_count={len(us)}')
            keys_sample = sorted(us.keys())[:5]
            print(f'  first 5 keys: {keys_sample}')
            k1 = list(us.keys())[0] if us else None
            v1 = us.get(k1) if k1 else None
            print(f'  key="{k1}", value_type={type(v1).__name__}')
            if isinstance(v1, dict):
                print(f'  value_keys={list(v1.keys())[:5]}')
                print(f'  title={v1.get("title")}')
                print(f'  summary_len={len(v1.get("summary", ""))}')
            elif isinstance(v1, str):
                print(f'  value_len={len(v1)}, preview={v1[:200]}')
        elif isinstance(us, list):
            print(f'  is_list, len={len(us)}')
            if us:
                v0 = us[0]
                print(f'  element[0] type={type(v0).__name__}')
        elif isinstance(us, str):
            print(f'  is_string, len={len(us)}')
        else:
            print(f'  unknown, value={str(us)[:300]}')
        
        # 1. 检查所有 WritingTask
        tasks = await db.execute(
            select(WritingTask).where(WritingTask.project_id == 11)
            .order_by(WritingTask.id.desc()).limit(5)
        )
        tasks = tasks.scalars().all()
        print('=== All WritingTasks for project_id=11 ===')
        for t in tasks:
            print(f'  id={t.id}, status={t.status}, total_units={t.total_units}, '
                  f'completed={t.completed_units}, start_from={t.start_from}')

        # 2. 对每个 task，检查 WritingUnit unit_index=1 和 30
        for t in tasks:
            units = await db.execute(
                select(WritingUnit).where(
                    WritingUnit.task_id == t.id,
                    WritingUnit.unit_index.in_([1, 30])
                ).order_by(WritingUnit.unit_index)
            )
            units = units.scalars().all()
            print(f'\n=== WritingUnits for task_id={t.id} (unit 1 & 30) ===')
            for u in units:
                content = u.final_content or ''
                preview = content[:120].replace('\n', '\\n')
                us = u.unit_summary or ''
                us_preview = us[:150].replace('\n', '\\n')
                print(f'  unit_index={u.unit_index}, title="{u.unit_title}", '
                      f'status={u.status}, content_len={len(content)}')
                print(f'    unit_summary_len={len(us)}')
                if us_preview:
                    print(f'    unit_summary: {us_preview}...')
                # 如果超过500字符，打印中间和末尾部分
                if len(us) > 500:
                    mid_start = len(us) // 2
                    mid = us[mid_start:mid_start+150].replace('\n', '\\n')
                    tail = us[-200:].replace('\n', '\\n')
                    print(f'    unit_summary_mid: ...{mid}...')
                    print(f'    unit_summary_tail: ...{tail}')
                if preview:
                    print(f'    content: {preview}...')

        # 3. 检查 NovelChapter: chapter_number=1 和 30
        chapters = await db.execute(
            select(NovelChapter).where(
                NovelChapter.project_id == 11,
                NovelChapter.chapter_number.in_([1, 30])
            ).order_by(NovelChapter.chapter_number)
        )
        chapters = chapters.scalars().all()
        print('\n=== NovelChapters for project_id=11 (chapter 1 & 30) ===')
        for c in chapters:
            content = c.final_content or ''
            preview = content[:80].replace('\n', '\\n')
            print(f'  chapter_number={c.chapter_number}, '
                  f'episode_number={c.episode_number}, '
                  f'title="{c.chapter_title}", '
                  f'status={c.status}, content_len={len(content)}')
            if preview:
                print(f'    preview: {preview}...')

        # 4. 检查是否有 chapter_number=0 的记录
        zero_chapters = await db.execute(
            select(NovelChapter).where(NovelChapter.project_id == 11, NovelChapter.chapter_number == 0)
        )
        zero_chapters = zero_chapters.scalars().all()
        if zero_chapters:
            print(f'\n=== WARNING: Found {len(zero_chapters)} NovelChapters with chapter_number=0 ===')
            for c in zero_chapters:
                print(f'  id={c.id}, title="{c.chapter_title}", status={c.status}')

        # 5. 统计所有 NovelChapter 数量
        count_result = await db.execute(
            select(NovelChapter).where(NovelChapter.project_id == 11)
        )
        all_chapters = count_result.scalars().all()
        print(f'\n=== Total NovelChapters for project_id=11: {len(all_chapters)} ===')
        for c in all_chapters[:5]:
            print(f'  chapter_number={c.chapter_number}, title="{c.chapter_title}"')
        if len(all_chapters) > 5:
            print(f'  ... and {len(all_chapters) - 5} more')

asyncio.run(check())
