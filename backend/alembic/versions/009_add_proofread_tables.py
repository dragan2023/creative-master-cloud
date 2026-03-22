"""add proofread tables

Revision ID: 009_add_proofread_tables
Revises: 008_add_chapter_scene_outlines
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_add_proofread_tables'
down_revision = '009'  # 依赖于 009_add_generation_task_fields
branch_labels = None
depends_on = None


def upgrade():
    # 创建校对任务表
    op.create_table(
        'proofread_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('outline_file', sa.String(500), nullable=True),
        sa.Column('chapter_outline_file', sa.String(500), nullable=False),
        sa.Column('novel_file', sa.String(500), nullable=False),
        sa.Column('check_types', sa.JSON(), nullable=True),
        sa.Column('compliance_level', sa.String(20), nullable=True),
        sa.Column('llm_provider', sa.String(50), nullable=True),
        sa.Column('status', sa.Enum('pending', 'parsing', 'extracting', 'proofreading',
                  'completed', 'failed', name='proofreadstatus'), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('current_step', sa.String(200), nullable=True),
        sa.Column('total_chapters', sa.Integer(), nullable=True),
        sa.Column('chapters', sa.JSON(), nullable=True),
        sa.Column('chapter_outlines', sa.JSON(), nullable=True),
        sa.Column('knowledge_base', sa.JSON(), nullable=True),
        sa.Column('issues', sa.JSON(), nullable=True),
        sa.Column('statistics', sa.JSON(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('total_cost', sa.String(20), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_proofread_tasks_user_id',
                    'proofread_tasks', ['user_id'])

    # 创建校对问题记录表
    op.create_table(
        'proofread_issues',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=True),
        sa.Column('chapter_title', sa.String(200), nullable=True),
        sa.Column('issue_type', sa.Enum('plot_consistency', 'plot_coherence', 'world_consistency', 'character_consistency',
                  'sensitive_location', 'sensitive_person', 'sensitive_event', 'sensitive_word', 'error', name='issuetype'), nullable=False),
        sa.Column('severity', sa.Enum('high', 'medium', 'low',
                  name='issueseverity'), nullable=True),
        sa.Column('original_text', sa.Text(), nullable=True),
        sa.Column('position_start', sa.Integer(), nullable=True),
        sa.Column('position_end', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('suggestion', sa.Text(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('user_feedback', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['task_id'], ['proofread_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_proofread_issues_task_id',
                    'proofread_issues', ['task_id'])

    # 创建校对缓存表
    op.create_table(
        'proofread_cache',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cache_key', sa.String(64), nullable=False),
        sa.Column('cache_value', sa.Text(), nullable=False),
        sa.Column('cache_type', sa.String(50), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cache_key')
    )
    op.create_index('ix_proofread_cache_cache_key',
                    'proofread_cache', ['cache_key'])

    # 创建敏感实体库表
    op.create_table(
        'sensitive_entities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('aliases', sa.JSON(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('severity', sa.String(20), nullable=True),
        sa.Column('extra_info', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sensitive_entities_entity_type',
                    'sensitive_entities', ['entity_type'])
    op.create_index('ix_sensitive_entities_name',
                    'sensitive_entities', ['name'])


def downgrade():
    op.drop_table('sensitive_entities')
    op.drop_table('proofread_cache')
    op.drop_table('proofread_issues')
    op.drop_table('proofread_tasks')
