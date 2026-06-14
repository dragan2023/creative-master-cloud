"""add ai_resource_content to writing_units

添加AI视觉资源生成内容字段到 writing_units 表：
- ai_resource_content: 独立于剧本正文存储的AI视觉资源生成内容
  包含人物参考图/场景参考图/物品参考图/Seedance 2.0视频生成提示词

Revision ID: 027_add_ai_resource_content
Revises: 026_add_self_revise_field
Create Date: 2026-06-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '027_add_ai_resource_content'
down_revision = '026_add_self_revise_field'
branch_labels = None
depends_on = None


def upgrade():
    """添加 ai_resource_content 列"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('writing_units')
    column_names = [col['name'] for col in columns]

    if 'ai_resource_content' not in column_names:
        op.add_column(
            'writing_units',
            sa.Column(
                'ai_resource_content',
                sa.Text(),
                nullable=True,
                comment="AI视觉资源生成内容(独立于剧本正文存储,包含人物/场景/物品参考图及视频生成提示词)"
            )
        )
        print("[Migration 027] 已添加字段: ai_resource_content (TEXT)")
    else:
        print("[Migration 027] 字段已存在，跳过: ai_resource_content")


def downgrade():
    """回滚：删除AI视觉资源字段"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('writing_units')
    column_names = [col['name'] for col in columns]

    if 'ai_resource_content' in column_names:
        op.drop_column('writing_units', 'ai_resource_content')
        print("[Migration 027] 已删除字段: ai_resource_content")
