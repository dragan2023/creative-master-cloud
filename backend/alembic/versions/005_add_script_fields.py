"""添加剧本专用字段

Revision ID: 005
Revises: 004_add_novel_writer_tables
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 novel_projects 表的剧本专用配置字段
    op.add_column('novel_projects', sa.Column('script_config',
                  sa.JSON(), nullable=True, comment='剧本专用配置'))

    # 添加 novel_chapters 表的场景编号字段
    op.add_column('novel_chapters', sa.Column('episode_number',
                  sa.Integer(), nullable=True, comment='集数（剧本专用）'))
    op.add_column('novel_chapters', sa.Column('scene_number',
                  sa.Integer(), nullable=True, comment='场景编号（剧本专用）'))

    # 创建索引
    op.create_index('ix_novel_chapters_episode_number',
                    'novel_chapters', ['episode_number'])
    op.create_index('ix_novel_chapters_episode_scene', 'novel_chapters', [
                    'project_id', 'episode_number', 'scene_number'])


def downgrade() -> None:
    # 删除索引
    op.drop_index('ix_novel_chapters_episode_scene', 'novel_chapters')
    op.drop_index('ix_novel_chapters_episode_number', 'novel_chapters')

    # 删除字段
    op.drop_column('novel_chapters', 'scene_number')
    op.drop_column('novel_chapters', 'episode_number')
    op.drop_column('novel_projects', 'script_config')
