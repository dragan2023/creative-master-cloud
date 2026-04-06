"""add outline stages fields

Revision ID: 011_add_outline_stages
Revises: 010_add_cache_expires_index
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_add_outline_stages'
down_revision = '011_add_project_knowledge_base_fields'
branch_labels = None
depends_on = None


def upgrade():
    """添加两阶段大纲生成所需的新字段"""
    # 检查列是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('novel_projects')]

    # 全局大纲字段（第一阶段）
    if 'global_outline_content' not in columns:
        op.add_column(
            'novel_projects',
            sa.Column('global_outline_content', sa.Text(),
                      nullable=True, comment='全局大纲内容（详细版）')
        )
    if 'global_outline_status' not in columns:
        op.add_column(
            'novel_projects',
            sa.Column('global_outline_status', sa.String(20), nullable=True,
                      default='pending', comment='全局大纲状态(pending/generating/completed)')
        )
    if 'global_outline_created_at' not in columns:
        op.add_column(
            'novel_projects',
            sa.Column('global_outline_created_at', sa.String(
                50), nullable=True, comment='全局大纲生成时间')
        )
    if 'global_outline_file_path' not in columns:
        op.add_column(
            'novel_projects',
            sa.Column('global_outline_file_path', sa.String(
                255), nullable=True, comment='全局大纲文件路径')
        )

    # 单元简要概述字段（第二阶段）
    if 'unit_summaries' not in columns:
        op.add_column(
            'novel_projects',
            sa.Column('unit_summaries', sa.JSON(), nullable=True, comment='单元简要概述')
        )
    if 'unit_summaries_status' not in columns:
        op.add_column(
            'novel_projects',
            sa.Column('unit_summaries_status', sa.String(20), nullable=True,
                      default='pending', comment='单元概述状态(pending/generating/completed)')
        )
    if 'unit_summaries_created_at' not in columns:
        op.add_column(
            'novel_projects',
            sa.Column('unit_summaries_created_at', sa.String(
                50), nullable=True, comment='单元概述生成时间')
        )
    if 'unit_summaries_file_path' not in columns:
        op.add_column(
            'novel_projects',
            sa.Column('unit_summaries_file_path', sa.String(
                255), nullable=True, comment='单元概述文件路径')
        )


def downgrade():
    """移除两阶段大纲生成字段"""
    # 移除单元简要概述字段
    op.drop_column('novel_projects', 'unit_summaries_file_path')
    op.drop_column('novel_projects', 'unit_summaries_created_at')
    op.drop_column('novel_projects', 'unit_summaries_status')
    op.drop_column('novel_projects', 'unit_summaries')

    # 移除全局大纲字段
    op.drop_column('novel_projects', 'global_outline_file_path')
    op.drop_column('novel_projects', 'global_outline_created_at')
    op.drop_column('novel_projects', 'global_outline_status')
    op.drop_column('novel_projects', 'global_outline_content')
