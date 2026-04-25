import sqlite3
import json

conn = sqlite3.connect('data/creative_master.db')
cursor = conn.cursor()

# 查询所有包含1.5的novel_projects
cursor.execute(
    "SELECT id, title, unit_summaries, unit_summaries_status, created_at FROM novel_projects")

rows = cursor.fetchall()
found = []

for row in rows:
    if row[2] and '1.5' in row[2]:
        found.append(row)
    elif row[1] and '1.5' in row[1]:
        found.append(row)

print(f"找到 {len(found)} 个包含1.5章的项目:\n")

for i, row in enumerate(found):
    print(f"=" * 80)
    print(f"项目 {i+1}:")
    print(f"ID: {row[0]}")
    print(f"标题: {row[1]}")
    print(f"创建时间: {row[4]}")
    print(f"单元概述状态: {row[3]}")

    if row[2]:
        try:
            unit_summaries = json.loads(row[2])
            print(f"单元概述章节数: {len(unit_summaries)}")

            # 查找所有单元编号
            unit_numbers = sorted(unit_summaries.keys(), key=lambda x: float(
                x) if '.' in str(x) else int(x))
            print(f"单元编号: {unit_numbers}")

            # 显示1.5章的详细信息
            if '1.5' in unit_summaries:
                print(f"\n✓ 第1.5章详情:")
                chapter_1_5 = unit_summaries['1.5']
                if isinstance(chapter_1_5, dict):
                    for key, value in chapter_1_5.items():
                        print(f"  {key}: {str(value)[:200]}")
        except Exception as e:
            print(f"解析失败: {e}")

    print()

conn.close()
