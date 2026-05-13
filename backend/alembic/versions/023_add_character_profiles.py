"""add character_profiles column to novel_projects

添加 character_profiles JSON 列到 novel_projects 表，
用于存储从 Markdown/JSON 大纲中解析的结构化人物设定信息，
使写作提示词构建和质控模块都能访问完整的人物小传数据。

Revision ID: 023_add_character_profiles
Revises: 022_drop_generation_task_fields
Create Date: 2026-05-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '023_add_character_profiles'
down_revision = '022_drop_generation_task_fields'
branch_labels = None
depends_on = None


def upgrade():
    """添加 character_profiles JSON 列"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('novel_projects')
    column_names = [col['name'] for col in columns]

    if 'character_profiles' not in column_names:
        op.add_column(
            'novel_projects',
            sa.Column(
                'character_profiles',
                sa.JSON(),
                nullable=True,
                comment="人物设定列表(从大纲提取的结构化角色信息)"
            )
        )
        print("[Migration 023] 已添加字段: character_profiles (JSON)")
    else:
        print("[Migration 023] 字段已存在，跳过: character_profiles")


def downgrade():
    """回滚：删除 character_profiles 列"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('novel_projects')
    column_names = [col['name'] for col in columns]

    if 'character_profiles' in column_names:
        op.drop_column('novel_projects', 'character_profiles')
        print("[Migration 023] 已删除字段: character_profiles")
