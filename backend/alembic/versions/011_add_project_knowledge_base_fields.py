"""add project knowledge base fields

Revision ID: 011_add_project_knowledge_base_fields
Revises: 010_add_cache_expires_index
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_add_project_knowledge_base_fields'
down_revision = '010_add_cache_expires_index'
branch_labels = None
depends_on = None


def upgrade():
    """添加项目专属知识库相关字段"""
    # 添加项目专属知识库字段
    op.add_column(
        'novel_projects',
        sa.Column('project_kb_id', sa.Integer(),
                  nullable=True, comment='项目专属知识库ID')
    )

    op.add_column(
        'novel_projects',
        sa.Column('project_kb_collection', sa.String(
            100), nullable=True, comment='知识库集合名称')
    )

    op.add_column(
        'novel_projects',
        sa.Column('global_outline_graph_path', sa.String(
            255), nullable=True, comment='全局大纲图谱文件路径')
    )

    op.add_column(
        'novel_projects',
        sa.Column('kb_status', sa.String(20), nullable=True,
                  default='pending', comment='知识库状态(pending/building/ready/failed)')
    )

    op.add_column(
        'novel_projects',
        sa.Column('kb_graphrag_enabled', sa.Boolean(), nullable=True,
                  default=True, comment='是否启用GraphRAG')
    )

    op.add_column(
        'novel_projects',
        sa.Column('kb_build_progress', sa.JSON(),
                  nullable=True, comment='知识库构建进度')
    )

    # 添加索引以加速知识库状态查询
    op.create_index(
        'ix_novel_projects_kb_status',
        'novel_projects',
        ['kb_status']
    )


def downgrade():
    """移除项目专属知识库字段"""
    op.drop_index('ix_novel_projects_kb_status', table_name='novel_projects')

    op.drop_column('novel_projects', 'kb_build_progress')
    op.drop_column('novel_projects', 'kb_graphrag_enabled')
    op.drop_column('novel_projects', 'kb_status')
    op.drop_column('novel_projects', 'global_outline_graph_path')
    op.drop_column('novel_projects', 'project_kb_collection')
    op.drop_column('novel_projects', 'project_kb_id')
