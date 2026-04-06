"""add title field to generations

Revision ID: 002_generation_title
Revises: 001_custom_provider
Create Date: 2026-02-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_generation_title'
down_revision = '001_custom_provider'
branch_labels = None
depends_on = None


def upgrade():
    # 检查列是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('generations')]

    # 添加 title 字段到 generations 表
    if 'title' not in columns:
        op.add_column('generations', sa.Column(
            'title', sa.String(200), nullable=True, comment='生成标题'))


def downgrade():
    op.drop_column('generations', 'title')
