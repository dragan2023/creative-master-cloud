"""添加质量管控模块表

Revision ID: 018_add_quality_reports
Revises: 8bd59fc777g2
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '018_add_quality_reports'
down_revision = '8bd59fc777g2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建质量分析报告表
    op.create_table(
        'quality_reports',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('analysis_scope', sa.String(20), nullable=False),
        sa.Column('chapters_analyzed', sa.JSON(), nullable=True),
        sa.Column('dimensions', sa.JSON(), nullable=False),
        sa.Column('analysis_depth', sa.String(20),
                  nullable=True, server_default='standard'),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('dimension_scores', sa.JSON(), nullable=True),
        sa.Column('report_data', sa.JSON(), nullable=True),
        sa.Column('total_issues', sa.Integer(),
                  nullable=True, server_default='0'),
        sa.Column('critical_issues', sa.Integer(),
                  nullable=True, server_default='0'),
        sa.Column('warning_issues', sa.Integer(),
                  nullable=True, server_default='0'),
        sa.Column('info_issues', sa.Integer(),
                  nullable=True, server_default='0'),
        sa.Column('total_tokens', sa.Integer(),
                  nullable=True, server_default='0'),
        sa.Column('rule_engine_tokens', sa.Integer(),
                  nullable=True, server_default='0'),
        sa.Column('llm_tokens', sa.Integer(),
                  nullable=True, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False,
                  server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.String(50), nullable=True),
        sa.Column('completed_at', sa.String(50), nullable=True),
        sa.Column('duration_ms', sa.Integer(),
                  nullable=True, server_default='0'),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('cache_key', sa.String(200), nullable=True),
        sa.Column('is_cached', sa.Boolean(),
                  nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(),
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['project_id'], ['novel_projects.id'], ondelete='CASCADE')
    )

    # 创建索引
    op.create_index('ix_quality_reports_id', 'quality_reports', ['id'])
    op.create_index('ix_quality_reports_user_id',
                    'quality_reports', ['user_id'])
    op.create_index('ix_quality_reports_project_id',
                    'quality_reports', ['project_id'])
    op.create_index('ix_quality_reports_status', 'quality_reports', ['status'])
    op.create_index('ix_quality_reports_content_hash',
                    'quality_reports', ['content_hash'])
    op.create_index('ix_quality_reports_created_at',
                    'quality_reports', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_quality_reports_created_at',
                  table_name='quality_reports')
    op.drop_index('ix_quality_reports_content_hash',
                  table_name='quality_reports')
    op.drop_index('ix_quality_reports_status', table_name='quality_reports')
    op.drop_index('ix_quality_reports_project_id',
                  table_name='quality_reports')
    op.drop_index('ix_quality_reports_user_id', table_name='quality_reports')
    op.drop_index('ix_quality_reports_id', table_name='quality_reports')
    op.drop_table('quality_reports')
