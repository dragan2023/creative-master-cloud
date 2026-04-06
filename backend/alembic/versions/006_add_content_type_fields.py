"""add content_type and type config fields

Revision ID: 003
Revises: 002_add_generation_title
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_content_type_fields'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # 检查列是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('novel_projects')]

    # 添加 content_type 字段
    if 'content_type' not in columns:
        op.add_column('novel_projects', sa.Column('content_type', sa.String(20), nullable=True, comment='内容类型(novel/series_script/movie_script)'))
    
    # 添加三种类型的专属配置字段
    if 'novel_config' not in columns:
        op.add_column('novel_projects', sa.Column('novel_config', sa.JSON, nullable=True, comment='小说专属配置'))
    if 'series_script_config' not in columns:
        op.add_column('novel_projects', sa.Column('series_script_config', sa.JSON, nullable=True, comment='剧集剧本专属配置'))
    if 'movie_script_config' not in columns:
        op.add_column('novel_projects', sa.Column('movie_script_config', sa.JSON, nullable=True, comment='电影剧本专属配置'))


def downgrade():
    # 删除新增字段
    op.drop_column('novel_projects', 'movie_script_config')
    op.drop_column('novel_projects', 'series_script_config')
    op.drop_column('novel_projects', 'novel_config')
    op.drop_column('novel_projects', 'content_type')
