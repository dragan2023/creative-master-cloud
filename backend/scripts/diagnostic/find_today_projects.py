import sqlite3
import json

conn = sqlite3.connect('data/creative_master.db')
cursor = conn.cursor()

# 查询今天创建的novel_projects
cursor.execute("""
    SELECT id, title, unit_summaries, unit_summaries_status, global_outline_content, created_at
    FROM novel_projects 
    WHERE created_at >= '2026-04-21'
    ORDER BY created_at DESC
""")

rows = cursor.fetchall()
print(f"找到 {len(rows)} 个今天创建的项目:\n")

for i, row in enumerate(rows):
    print(f"=" * 80)
    print(f"项目 {i+1}:")
    print(f"ID: {row[0]}")
    print(f"标题: {row[1]}")
    print(f"创建时间: {row[5]}")
    print(f"单元概述状态: {row[3]}")

    # 检查unit_summaries中是否有1.5
    if row[2]:
        try:
            unit_summaries = json.loads(row[2])
            print(f"单元概述章节数: {len(unit_summaries)}")

            # 查找所有单元编号
            unit_numbers = sorted(unit_summaries.keys(), key=lambda x: float(
                x) if '.' in str(x) else int(x))
            print(f"单元编号: {unit_numbers}")

            # 检查是否有1.5
            if '1.5' in unit_summaries or '1.5' in str(unit_summaries):
                print(f"\n✓ 找到包含1.5章的项目!")
                print(f"\n单元概述内容:")
                for key in unit_numbers:
                    unit = unit_summaries[key]
                    title = unit.get('title', '') if isinstance(
                        unit, dict) else ''
                    content_preview = str(unit)[:100] if unit else ''
                    print(f"  第{key}章: {title}")
                    if '1.5' in str(key):
                        print(f"    内容预览: {content_preview}...")
        except Exception as e:
            print(f"解析unit_summaries失败: {e}")

    # 检查global_outline_content
    if row[4] and '1.5' in row[4]:
        print(f"\n全局大纲中也包含1.5章")

    print()

conn.close()
