"""add content_after_self_revise to writing_units

添加用户自主修订稿字段到 writing_units 表：
- content_after_self_revise: 用户通过UnitRevisionDialog确认保存的修订内容

Revision ID: 026_add_self_revise_field
Revises: 025_add_content_version_fields
Create Date: 2026-06-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '026_add_self_revise_field'
down_revision = '025_add_content_version_fields'
branch_labels = None
depends_on = None


def upgrade():
    """添加 content_after_self_revise 列"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('writing_units')
    column_names = [col['name'] for col in columns]

    if 'content_after_self_revise' not in column_names:
        op.add_column(
            'writing_units',
            sa.Column(
                'content_after_self_revise',
                sa.Text(),
                nullable=True,
                comment="用户自主修订后的内容(通过UnitRevisionDialog确认保存)"
            )
        )
        print("[Migration 026] 已添加字段: content_after_self_revise (TEXT)")
    else:
        print("[Migration 026] 字段已存在，跳过: content_after_self_revise")


def downgrade():
    """回滚：删除自主修订稿字段"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('writing_units')
    column_names = [col['name'] for col in columns]

    if 'content_after_self_revise' in column_names:
        op.drop_column('writing_units', 'content_after_self_revise')
        print("[Migration 026] 已删除字段: content_after_self_revise")
