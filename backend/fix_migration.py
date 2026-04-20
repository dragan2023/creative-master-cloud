"""
手动修复数据库迁移 - 添加修订相关字段
"""
import sqlite3
import sys
from pathlib import Path

# 添加backend目录到路径
backend_dir = Path(__file__).parent
db_path = backend_dir / "data" / "creative_master.db"


def fix_database():
    """修复数据库,添加缺失的列和表"""
    if not db_path.exists():
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)

    print(f"连接到数据库: {db_path}")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # 检查generations表的列
        cursor.execute("PRAGMA table_info(generations)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"\n当前generations表的列: {columns}")

        # 添加is_finalized列
        if 'is_finalized' not in columns:
            print("\n添加 is_finalized 列...")
            cursor.execute(
                "ALTER TABLE generations ADD COLUMN is_finalized BOOLEAN DEFAULT 0")
            print("✓ is_finalized 列添加成功")
        else:
            print("\n✓ is_finalized 列已存在")

        # 添加revision_count列
        if 'revision_count' not in columns:
            print("\n添加 revision_count 列...")
            cursor.execute(
                "ALTER TABLE generations ADD COLUMN revision_count INTEGER DEFAULT 0")
            print("✓ revision_count 列添加成功")
        else:
            print("\n✓ revision_count 列已存在")

        # 检查generation_revision_history表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='generation_revision_history'
        """)
        table_exists = cursor.fetchone()

        if not table_exists:
            print("\n创建 generation_revision_history 表...")
            cursor.execute("""
                CREATE TABLE generation_revision_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation_id INTEGER NOT NULL,
                    round_number INTEGER NOT NULL,
                    user_feedback TEXT NOT NULL,
                    diff_instructions TEXT,
                    content_before TEXT,
                    content_after TEXT,
                    token_usage INTEGER DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY(generation_id) REFERENCES generations(id) ON DELETE CASCADE
                )
            """)
            print("✓ generation_revision_history 表创建成功")

            # 创建索引
            cursor.execute("""
                CREATE INDEX ix_generation_revision_history_generation_id 
                ON generation_revision_history(generation_id)
            """)
            cursor.execute("""
                CREATE INDEX ix_generation_revision_history_id 
                ON generation_revision_history(id)
            """)
            print("✓ 索引创建成功")
        else:
            print("\n✓ generation_revision_history 表已存在")

        # 提交更改
        conn.commit()
        print("\n✅ 数据库修复完成!")

        # 验证
        cursor.execute("PRAGMA table_info(generations)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"\n修复后generations表的列: {columns}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    fix_database()
