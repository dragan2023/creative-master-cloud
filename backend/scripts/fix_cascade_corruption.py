"""
[fix] Fix cascading corruption in project.unit_summaries.

Problem: parse_unit_summaries_from_content had a bug where the summary boundary
regex didn't match **第N集：标题** format. Each unit's summary contains all
subsequent units' content concatenated.

Fix: Reconstruct each unit's correct summary by truncating at the next
unit's title boundary within the concatenated content.

Usage:
    python scripts/fix_cascade_corruption.py --dry-run
    python scripts/fix_cascade_corruption.py --fix
"""
import asyncio, sys, re, argparse

sys.path.insert(0, '.')
from app.core.database import async_session_maker
from sqlalchemy import select
from app.models.novel_project import NovelProject


async def fix(project_id: int = 11, dry_run: bool = True):

    async with async_session_maker() as db:
        result = await db.execute(
            select(NovelProject).where(NovelProject.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            print(f"[ERROR] Project {project_id} not found")
            return

        data = project.unit_summaries
        if not isinstance(data, dict):
            print(f"[ERROR] unit_summaries is not dict: {type(data)}")
            return

        fixed = {}
        keys_sorted = sorted(data.keys(), key=int)
        total = len(keys_sorted)

        for i, k in enumerate(keys_sorted):
            v = data[k]
            if not isinstance(v, dict):
                print(f"[SKIP] Key {k}: not dict")
                fixed[k] = v
                continue

            summary = v.get('summary', '')

            # For the last unit, summary is already correct
            if i == total - 1:
                new_summary = summary
            else:
                # Truncate at the next unit's title boundary
                next_k = keys_sorted[i + 1]
                next_title = data[next_k].get('title', '')
                if not next_title:
                    # Can't determine boundary, keep as-is
                    print(f"[WARN] Key {k}: next unit {next_k} has no title, can't fix")
                    new_summary = summary
                else:
                    # Search for the next unit's title in the concatenated summary
                    # Patterns: **第N集：title** or 第N集：title
                    next_num = int(next_k)
                    patterns = [
                        rf'\n\*\*第{next_num}集[：:].*?\*\*\n',
                        rf'\n第{next_num}集[：:].*?\n',
                        rf'\*\*第{next_num}集[：:].*?\*\*',
                    ]
                    cutoff = None
                    for pat in patterns:
                        m = re.search(pat, summary)
                        if m:
                            cutoff = m.start()
                            break

                    if cutoff is not None and cutoff > 0:
                        new_summary = summary[:cutoff].strip()
                    else:
                        # Try to find just "第N集" as a boundary
                        m = re.search(rf'\n?\*\*?第{next_num}集', summary)
                        if m and m.start() > 0:
                            new_summary = summary[:m.start()].strip()
                        else:
                            print(f"[WARN] Key {k}: can't find boundary for unit {next_num}")
                            new_summary = summary

            old_len = len(summary)
            new_len = len(new_summary)
            diff = old_len - new_len

            fixed[k] = {
                **v,
                'summary': new_summary,
            }

            if diff > 0:
                print(f"[OK] Key {k}: {old_len} -> {new_len} (-{diff}) title: {v.get('title', '')[:40]}")
            else:
                print(f"[OK] Key {k}: {old_len} chars (no change)")

        if dry_run:
            print(f"\n[DRY-RUN] Would fix {total} unit summaries in project {project_id}")
            return

        # Apply fix
        project.unit_summaries = fixed
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(project, 'unit_summaries')
        await db.commit()
        print(f"\n[OK] Fixed {total} unit summaries in project {project_id}")


if __name__ == '__main__':
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    parser = argparse.ArgumentParser()
    parser.add_argument('--project-id', type=int, default=11)
    parser.add_argument('--fix', action='store_true', help='Apply fixes (default: dry-run)')
    args = parser.parse_args()

    print(f"Starting: project_id={args.project_id}, fix={args.fix}")
    dry_run = not args.fix
    asyncio.run(fix(project_id=args.project_id, dry_run=dry_run))
