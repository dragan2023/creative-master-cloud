"""
数据库迁移脚本：添加 preprocessor_metadata 字段到 knowledge_bases 表
运行方式：python -m scripts.migrate_add_preprocessor_metadata
"""
from app.core.config import get_settings
import sqlite3
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def migrate():
    settings = get_settings()
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")

    print(f"数据库路径: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查列是否已存在
    cursor.execute("PRAGMA table_info(knowledge_bases)")
    columns = [col[1] for col in cursor.fetchall()]

    if "preprocessor_metadata" not in columns:
        print("添加 preprocessor_metadata 列...")
        cursor.execute("""
            ALTER TABLE knowledge_bases 
            ADD COLUMN preprocessor_metadata JSON
        """)
        conn.commit()
        print("迁移成功！")
    else:
        print("列 preprocessor_metadata 已存在，跳过迁移")

    conn.close()


if __name__ == "__main__":
    migrate()
