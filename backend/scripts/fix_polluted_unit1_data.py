"""修复被污染的第1集数据

问题: unit_index=1 / chapter_number=1 的 final_content 被错误填充了第30集的内容
原因: WriterAgent prompt 未明确告知当前集数，LLM 在66K字的超长 unit_summary 中迷失

修复内容:
1. 清空 WritingUnit(unit_index=1) 的 final_content（保持其他字段不变）
2. 清空 WritingScene(unit_id=对应unit1) 的 final_content
3. 清空 NovelChapter(chapter_number=1) 的 final_content

这样可以重新生成第1集内容，而无需删除记录。
"""

import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import select, and_
from app.core.database import async_session_maker
from app.models.writing_unit import WritingUnit, UnitStatus
from app.models.writing_scene import WritingScene, SceneStatus
from app.models.writing_task import WritingTask
from app.models.novel_chapter import NovelChapter


async def fix_polluted_data(
    project_id: int = 11,
    unit_index: int = 1,
    dry_run: bool = True
):
    """清理被污染的数据

    Args:
        project_id: 项目ID
        unit_index: 被污染的单元索引
        dry_run: True=仅预览，False=执行修复
    """
    async with async_session_maker() as db:
        # 1. 找到最新的 WritingTask
        task_result = await db.execute(
            select(WritingTask).where(WritingTask.project_id == project_id)
            .order_by(WritingTask.id.desc()).limit(1)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            print(f"未找到 project_id={project_id} 的 WritingTask")
            return
        print(f"目标 WritingTask: id={task.id}, total_units={task.total_units}")

        # 2. 检查 WritingUnit
        unit_result = await db.execute(
            select(WritingUnit).where(
                WritingUnit.task_id == task.id,
                WritingUnit.unit_index == unit_index
            )
        )
        unit = unit_result.scalar_one_or_none()
        if not unit:
            print(f"未找到 unit_index={unit_index} 的 WritingUnit")
            return
        print(f"\n=== WritingUnit ===")
        print(f"  unit_id={unit.id}, title={unit.unit_title}")
        print(f"  status={unit.status}")
        print(f"  final_content length={len(unit.final_content or '')}")
        if unit.final_content:
            print(f"  content preview: {(unit.final_content or '')[:100]}...")

        # 3. 检查 WritingScene
        scene_result = await db.execute(
            select(WritingScene).where(
                WritingScene.unit_id == unit.id,
                WritingScene.scene_index == 1
            )
        )
        scene = scene_result.scalar_one_or_none()
        print(f"\n=== WritingScene ===")
        if scene:
            print(f"  scene_id={scene.id}, title={scene.scene_title}")
            print(f"  status={scene.status}")
            print(f"  final_content length={len(scene.final_content or '')}")
        else:
            print(f"  (不存在)")

        # 4. 检查 NovelChapter
        chapter_result = await db.execute(
            select(NovelChapter).where(
                NovelChapter.project_id == project_id,
                NovelChapter.chapter_number == unit_index
            )
        )
        chapter = chapter_result.scalar_one_or_none()
        print(f"\n=== NovelChapter ===")
        if chapter:
            print(f"  chapter_id={chapter.id}, title={chapter.chapter_title}")
            print(f"  chapter_number={chapter.chapter_number}")
            print(f"  status={chapter.status}")
            print(f"  final_content length={len(chapter.final_content or '')}")
        else:
            print(f"  (不存在)")

        if dry_run:
            print("\n[DRY RUN] - 未执行实际修改。使用 --fix 参数执行修复。")
            return

        # 执行修复
        print("\n[开始修复]...")
        changes = 0

        if unit and unit.final_content:
            old_len = len(unit.final_content)
            unit.final_content = None
            unit.status = UnitStatus.PENDING
            changes += 1
            print(f"  [OK] WritingUnit unit_index={unit_index}: 已清空 final_content ({old_len} 字符)")

        if scene and scene.final_content:
            old_len = len(scene.final_content)
            scene.final_content = None
            scene.status = SceneStatus.PENDING
            changes += 1
            print(f"  [OK] WritingScene: 已清空 final_content ({old_len} 字符)")

        if chapter and chapter.final_content:
            old_len = len(chapter.final_content)
            chapter.final_content = None
            changes += 1
            print(f"  [OK] NovelChapter chapter_number={unit_index}: 已清空 final_content ({old_len} 字符)")

        if changes > 0:
            await db.commit()
            print(f"\n[修复完成] 共清理 {changes} 条记录。请重新生成第{unit_index}集内容。")
        else:
            print(f"\n[提示] 没有发现需要清理的数据。")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="修复被污染的第1集数据")
    parser.add_argument("--project-id", type=int, default=11, help="项目ID (默认: 11)")
    parser.add_argument("--unit-index", type=int, default=1, help="单元索引 (默认: 1)")
    parser.add_argument("--fix", action="store_true", help="执行实际修复（否则仅预览）")
    args = parser.parse_args()

    asyncio.run(fix_polluted_data(
        project_id=args.project_id,
        unit_index=args.unit_index,
        dry_run=not args.fix
    ))
