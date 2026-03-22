"""add chapter_outlines and scene_outlines fields to novel_projects

Revision ID: 008_add_chapter_scene_outlines
Revises: 007_add_episode_outlines
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_add_chapter_scene_outlines'
down_revision = '007_add_episode_outlines'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 chapter_outlines 字段到 novel_projects 表
    # 用于存储小说章节详细大纲
    op.add_column('novel_projects', sa.Column(
        'chapter_outlines', sa.JSON(), nullable=True, comment='章节详细大纲'))

    # 添加 scene_outlines 字段到 novel_projects 表
    # 用于存储电影剧本场景详细大纲
    op.add_column('novel_projects', sa.Column(
        'scene_outlines', sa.JSON(), nullable=True, comment='场景详细大纲'))


def downgrade():
    op.drop_column('novel_projects', 'scene_outlines')
    op.drop_column('novel_projects', 'chapter_outlines')
