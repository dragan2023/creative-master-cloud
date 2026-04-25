import sqlite3
import json

conn = sqlite3.connect('data/creative_master.db')
cursor = conn.cursor()

# 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("数据库中的所有表:")
for table in tables:
    print(f"  - {table}")

# 查找可能包含生成记录的表
print("\n查找可能包含生成数据的表...")
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    if count > 0:
        print(f"\n{table}: {count}条记录")
        # 查看表结构
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [r[1] for r in cursor.fetchall()]
        print(f"  列: {columns}")

        # 如果包含content或result相关列,查看最近记录
        if any('content' in c or 'result' in c or 'outline' in c for c in columns):
            cursor.execute(
                f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                # 查找包含1.5的记录
                row_str = str(row)
                if '1.5' in row_str:
                    print(f"  ✓ 找到包含1.5的记录!")
                    for i, val in enumerate(row):
                        if val and '1.5' in str(val):
                            print(f"    {columns[i]}: {str(val)[:200]}...")

conn.close()
