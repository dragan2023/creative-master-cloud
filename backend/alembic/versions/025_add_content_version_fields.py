"""add content_after_generation and content_after_qc_fix to writing_units

添加双版本内容字段到 writing_units 表：
- content_after_generation: LLM生成的初稿内容(生成完成后存储，永不覆盖)
- content_after_qc_fix: 质控修正后的内容(质控完成后存储)

Revision ID: 025_add_content_version_fields
Revises: 024_merge_heads
Create Date: 2026-05-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '025_add_content_version_fields'
down_revision = '024_merge_heads'
branch_labels = None
depends_on = None


def upgrade():
    """添加 content_after_generation 和 content_after_qc_fix 列"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('writing_units')
    column_names = [col['name'] for col in columns]

    if 'content_after_generation' not in column_names:
        op.add_column(
            'writing_units',
            sa.Column(
                'content_after_generation',
                sa.Text(),
                nullable=True,
                comment="LLM生成的初稿内容(生成完成后存储，永不覆盖)"
            )
        )
        print("[Migration 025] 已添加字段: content_after_generation (TEXT)")
    else:
        print("[Migration 025] 字段已存在，跳过: content_after_generation")

    if 'content_after_qc_fix' not in column_names:
        op.add_column(
            'writing_units',
            sa.Column(
                'content_after_qc_fix',
                sa.Text(),
                nullable=True,
                comment="质控修正后的内容(质控完成后存储)"
            )
        )
        print("[Migration 025] 已添加字段: content_after_qc_fix (TEXT)")
    else:
        print("[Migration 025] 字段已存在，跳过: content_after_qc_fix")


def downgrade():
    """回滚：删除双版本内容字段"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('writing_units')
    column_names = [col['name'] for col in columns]

    if 'content_after_generation' in column_names:
        op.drop_column('writing_units', 'content_after_generation')
        print("[Migration 025] 已删除字段: content_after_generation")

    if 'content_after_qc_fix' in column_names:
        op.drop_column('writing_units', 'content_after_qc_fix')
        print("[Migration 025] 已删除字段: content_after_qc_fix")
