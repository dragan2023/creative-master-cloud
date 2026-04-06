"""add episode_outlines field to novel_projects

Revision ID: 007_add_episode_outlines
Revises: 006_add_content_type_fields
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_add_episode_outlines'
down_revision = '006_add_content_type_fields'
branch_labels = None
depends_on = None


def upgrade():
    # 检查列是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('novel_projects')]

    # 添加 episode_outlines 字段到 novel_projects 表
    # 用于存储分集详细大纲
    if 'episode_outlines' not in columns:
        op.add_column('novel_projects', sa.Column(
            'episode_outlines', sa.JSON(), nullable=True, comment='分集详细大纲'))


def downgrade():
    op.drop_column('novel_projects', 'episode_outlines')
