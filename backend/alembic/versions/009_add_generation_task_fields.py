"""添加生成任务状态字段

Revision ID: 009
Revises: 008
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008_add_chapter_scene_outlines'
branch_labels = None
depends_on = None


def upgrade():
    # 检查列是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('novel_projects')]

    # 添加生成任务相关字段到 novel_projects 表
    if 'generation_task_type' not in columns:
        op.add_column('novel_projects', sa.Column(
            'generation_task_type', sa.String(50), nullable=True, comment='当前生成任务类型'))
    if 'generation_task_status' not in columns:
        op.add_column('novel_projects', sa.Column('generation_task_status', sa.String(
            20), nullable=True, comment='生成任务状态(running/completed/cancelled/failed)'))
    if 'generation_task_total' not in columns:
        op.add_column('novel_projects', sa.Column(
            'generation_task_total', sa.Integer, default=0, comment='任务总数量'))
    if 'generation_task_completed' not in columns:
        op.add_column('novel_projects', sa.Column(
            'generation_task_completed', sa.Integer, default=0, comment='已完成数量'))
    if 'generation_task_failed' not in columns:
        op.add_column('novel_projects', sa.Column(
            'generation_task_failed', sa.Integer, default=0, comment='失败数量'))
    if 'generation_task_skipped' not in columns:
        op.add_column('novel_projects', sa.Column(
            'generation_task_skipped', sa.Integer, default=0, comment='跳过数量'))
    if 'generation_task_current' not in columns:
        op.add_column('novel_projects', sa.Column(
            'generation_task_current', sa.Integer, nullable=True, comment='当前处理项'))
    if 'generation_task_started_at' not in columns:
        op.add_column('novel_projects', sa.Column(
            'generation_task_started_at', sa.DateTime, nullable=True, comment='任务开始时间'))
    if 'generation_task_updated_at' not in columns:
        op.add_column('novel_projects', sa.Column(
            'generation_task_updated_at', sa.DateTime, nullable=True, comment='任务更新时间'))


def downgrade():
    # 删除字段
    op.drop_column('novel_projects', 'generation_task_type')
    op.drop_column('novel_projects', 'generation_task_status')
    op.drop_column('novel_projects', 'generation_task_total')
    op.drop_column('novel_projects', 'generation_task_completed')
    op.drop_column('novel_projects', 'generation_task_failed')
    op.drop_column('novel_projects', 'generation_task_skipped')
    op.drop_column('novel_projects', 'generation_task_current')
    op.drop_column('novel_projects', 'generation_task_started_at')
    op.drop_column('novel_projects', 'generation_task_updated_at')
