"""
数据库迁移脚本 - 添加质控相关字段到writing_units表

执行方式:
python scripts/migrate_add_qc_fields.py
"""
import sqlite3
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_column_exists(cursor, table_name, column_name):
    """检查列是否存在"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def add_column_if_not_exists(cursor, table_name, column_name, column_definition):
    """如果列不存在则添加"""
    if not check_column_exists(cursor, table_name, column_name):
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        cursor.execute(sql)
        print(f"✓ 添加列: {column_name}")
    else:
        print(f"- 列已存在: {column_name}")


def main():
    """执行迁移"""
    # 尝试多个可能的数据库路径
    possible_paths = [
        os.path.join(os.path.dirname(__file__), '..',
                     'data', 'creative_master.db'),
        os.path.join(os.path.dirname(__file__), '..', 'data', 'dev.db'),
        os.path.join(os.path.dirname(__file__), '..',
                     'data', 'creative_master.sqlite'),
    ]

    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break

    if not db_path:
        print(f"错误: 数据库文件不存在")
        print(f"尝试的路径:")
        for path in possible_paths:
            print(f"  - {path}")
        sys.exit(1)

    print(f"数据库路径: {db_path}")
    print("=" * 60)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查writing_units表是否存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='writing_units'")
        if not cursor.fetchone():
            print("错误: writing_units表不存在")
            sys.exit(1)

        print("开始添加质控相关字段...")
        print()

        # 添加质控状态字段
        add_column_if_not_exists(
            cursor, 'writing_units',
            'quality_control_status',
            "VARCHAR(50) DEFAULT 'pending'"
        )

        # 添加质控报告字段
        add_column_if_not_exists(
            cursor, 'writing_units',
            'quality_control_report',
            "JSON DEFAULT '{}'"
        )

        # 添加修正列表字段
        add_column_if_not_exists(
            cursor, 'writing_units',
            'quality_control_fixes',
            "JSON DEFAULT '[]'"
        )

        # 添加质控得分字段
        add_column_if_not_exists(
            cursor, 'writing_units',
            'quality_control_score',
            "FLOAT DEFAULT 0.0"
        )

        # 添加质控完成时间字段
        add_column_if_not_exists(
            cursor, 'writing_units',
            'quality_control_completed_at',
            "DATETIME"
        )

        # 添加修正前原始内容字段
        add_column_if_not_exists(
            cursor, 'writing_units',
            'original_content_before_fix',
            "TEXT"
        )

        # 提交更改
        conn.commit()

        print()
        print("=" * 60)
        print("✓ 数据库迁移完成!")
        print()

        # 验证迁移结果
        cursor.execute("PRAGMA table_info(writing_units)")
        columns = cursor.fetchall()

        print("writing_units表当前字段:")
        for col in columns:
            col_name = col[1]
            if col_name.startswith('quality_control') or col_name == 'original_content_before_fix':
                print(f"  ✓ {col_name} ({col[2]})")

        conn.close()

    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
