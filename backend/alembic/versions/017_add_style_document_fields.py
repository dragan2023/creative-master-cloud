"""add style document fields

Revision ID: 017_add_style_document_fields
Revises: 016_add_unique_constraints
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '017_add_style_document_fields'
down_revision = '016_add_unique_constraints'
branch_labels = None
depends_on = None


def upgrade():
    """添加风格文档相关字段到 novel_projects 表"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # 获取 novel_projects 表的列信息
    columns = [col['name'] for col in inspector.get_columns('novel_projects')]
    
    # 添加缺失的字段
    if 'style_document_path' not in columns:
        op.add_column('novel_projects', 
            sa.Column('style_document_path', sa.String(255), nullable=True, comment='风格文档路径'))
    
    if 'style_document_name' not in columns:
        op.add_column('novel_projects', 
            sa.Column('style_document_name', sa.String(200), nullable=True, comment='风格文档名称'))
    
    if 'style_analysis_status' not in columns:
        op.add_column('novel_projects', 
            sa.Column('style_analysis_status', sa.String(20), nullable=True, server_default='pending', 
                      comment='风格分析状态(pending/analyzing/completed/failed)'))
    
    if 'style_analysis_error' not in columns:
        op.add_column('novel_projects', 
            sa.Column('style_analysis_error', sa.Text(), nullable=True, comment='风格分析错误信息'))
    
    if 'style_config' not in columns:
        op.add_column('novel_projects', 
            sa.Column('style_config', sa.JSON(), nullable=True, comment='风格配置(JSON)'))
    
    if 'ai_elimination_enabled' not in columns:
        op.add_column('novel_projects', 
            sa.Column('ai_elimination_enabled', sa.Boolean(), nullable=True, server_default='1', 
                      comment='是否启用AI文风消除'))
    
    if 'ai_elimination_threshold' not in columns:
        op.add_column('novel_projects', 
            sa.Column('ai_elimination_threshold', sa.Integer(), nullable=True, server_default='50', 
                      comment='AI文风消除阈值(0-100)'))


def downgrade():
    """回滚：移除风格文档相关字段"""
    op.drop_column('novel_projects', 'ai_elimination_threshold')
    op.drop_column('novel_projects', 'ai_elimination_enabled')
    op.drop_column('novel_projects', 'style_config')
    op.drop_column('novel_projects', 'style_analysis_error')
    op.drop_column('novel_projects', 'style_analysis_status')
    op.drop_column('novel_projects', 'style_document_name')
    op.drop_column('novel_projects', 'style_document_path')
