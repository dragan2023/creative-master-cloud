"""add multi agent writing tables

Revision ID: 015_add_multi_agent_writing_tables
Revises: 014_fix_kb_expires_at_type
Create Date: 2026-03-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '015_add_multi_agent_writing_tables'
down_revision = '014_fix_kb_expires_at_type'
branch_labels = None
depends_on = None


def upgrade():
    """创建多Agent写作系统相关表
    
    包含5个新表：
    - writing_tasks: 写作任务表
    - writing_units: 写作单元表
    - writing_scenes: 写作场景表
    - writing_checkpoints: 检查点表
    - writing_stats: 统计表
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    
    # 检查表是否已存在
    existing_tables = inspector.get_table_names()
    
    # 创建 writing_tasks 表
    if 'writing_tasks' not in existing_tables:
        op.create_table(
            'writing_tasks',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('uuid', sa.String(36), nullable=False),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('novel_projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(20) if is_sqlite else sa.Enum('pending', 'running', 'interrupted', 'completed', 'failed', name='taskstatus'), nullable=False, server_default='pending'),
            sa.Column('total_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('completed_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('start_from', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('unit_count', sa.Integer(), nullable=True),
            sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_cost', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('start_time', sa.DateTime(), nullable=True),
            sa.Column('end_time', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_writing_tasks_uuid', 'writing_tasks', ['uuid'], unique=True)
    
    # 创建 writing_units 表
    if 'writing_units' not in existing_tables:
        op.create_table(
            'writing_units',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('task_id', sa.Integer(), sa.ForeignKey('writing_tasks.id', ondelete='CASCADE'), nullable=False),
            sa.Column('unit_index', sa.Integer(), nullable=False),
            sa.Column('unit_title', sa.String(200), nullable=True),
            sa.Column('unit_summary', sa.Text(), nullable=True),
            sa.Column('status', sa.String(20) if is_sqlite else sa.Enum('pending', 'structuring', 'processing', 'completed', 'interrupted', name='unitstatus'), nullable=False, server_default='pending'),
            sa.Column('scenes_data', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('final_content', sa.Text(), nullable=True),
            sa.Column('word_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
            sa.PrimaryKeyConstraint('id')
        )
    
    # 创建 writing_scenes 表
    if 'writing_scenes' not in existing_tables:
        op.create_table(
            'writing_scenes',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('unit_id', sa.Integer(), sa.ForeignKey('writing_units.id', ondelete='CASCADE'), nullable=False),
            sa.Column('scene_index', sa.Integer(), nullable=False),
            sa.Column('scene_title', sa.String(200), nullable=True),
            sa.Column('scene_outline', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('status', sa.String(20) if is_sqlite else sa.Enum('pending', 'writing', 'reviewing', 'completed', 'failed', name='scenestatus'), nullable=False, server_default='pending'),
            sa.Column('writer_result', sa.JSON(), nullable=True),
            sa.Column('editor_result', sa.JSON(), nullable=True),
            sa.Column('stylist_result', sa.JSON(), nullable=True),
            sa.Column('compliance_result', sa.JSON(), nullable=True),
            sa.Column('final_content', sa.Text(), nullable=True),
            sa.Column('word_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
            sa.PrimaryKeyConstraint('id')
        )
    
    # 创建 writing_checkpoints 表
    if 'writing_checkpoints' not in existing_tables:
        op.create_table(
            'writing_checkpoints',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('task_id', sa.Integer(), sa.ForeignKey('writing_tasks.id', ondelete='CASCADE'), nullable=False),
            sa.Column('last_completed_unit', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_completed_scene_id', sa.Integer(), nullable=True),
            sa.Column('last_operation', sa.String(50), nullable=True),
            sa.Column('agent_states', sa.JSON(), nullable=False, server_default='{}'),
            sa.PrimaryKeyConstraint('id')
        )
    
    # 创建 writing_stats 表
    if 'writing_stats' not in existing_tables:
        op.create_table(
            'writing_stats',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('task_id', sa.Integer(), sa.ForeignKey('writing_tasks.id', ondelete='CASCADE'), nullable=False),
            sa.Column('agent_name', sa.String(50), nullable=False),
            sa.Column('model_id', sa.String(100), nullable=False),
            sa.Column('scene_id', sa.Integer(), nullable=True),
            sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('duration_sec', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('estimated_cost', sa.Float(), nullable=False, server_default='0.0'),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade():
    """回滚：删除多Agent写作系统相关表"""
    op.drop_table('writing_stats')
    op.drop_table('writing_checkpoints')
    op.drop_table('writing_scenes')
    op.drop_table('writing_units')
    op.drop_table('writing_tasks')
