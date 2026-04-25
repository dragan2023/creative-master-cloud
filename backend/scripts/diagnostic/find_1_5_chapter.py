import sqlite3
import json

conn = sqlite3.connect('data/creative_master.db')
cursor = conn.cursor()

# 查询今天创建的包含单元概述的记录
cursor.execute("""
    SELECT id, content_type, status, created_at, parameters, result_data 
    FROM generation_records 
    WHERE created_at >= '2026-04-21' 
    AND (result_data LIKE '%1.5%' OR parameters LIKE '%1.5%')
    ORDER BY created_at DESC 
    LIMIT 5
""")

rows = cursor.fetchall()
print(f"找到 {len(rows)} 条包含1.5章的记录:\n")

for row in rows:
    print(f"=" * 80)
    print(f"ID: {row[0]}")
    print(f"类型: {row[1]}")
    print(f"状态: {row[2]}")
    print(f"创建时间: {row[3]}")

    # 解析parameters
    if row[4]:
        try:
            params = json.loads(row[4])
            print(f"\n参数:")
            if 'unit_count' in params:
                print(f"  单元数量: {params['unit_count']}")
            if 'qc_mode' in params:
                print(f"  质控模式: {params['qc_mode']}")
            if 'enable_auto_revise' in params:
                print(f"  自动修正: {params['enable_auto_revise']}")
        except:
            pass

    # 解析result_data,查找1.5章相关内容
    if row[5]:
        try:
            result = json.loads(row[5])
            result_str = json.dumps(result, ensure_ascii=False)
            if '1.5' in result_str:
                print(f"\n结果中包含1.5章内容")
                # 查找qc_report或quality_report
                if 'qc_report' in result:
                    print(f"  包含质控报告")
                if 'quality_report' in result:
                    print(f"  包含质量报告")
                if 'revised_content' in result:
                    print(f"  包含修正后内容")
                    # 检查修正内容中是否有1.5章
                    if '1.5' in result.get('revised_content', ''):
                        print(f"  修正内容中包含1.5章")
        except:
            pass

    print()

conn.close()
