"""drop deprecated generation_task fields from NovelProject

P0改造任务：删除NovelProject中已迁移到WritingTask的9个DEPRECATED字段
这些字段已通过迁移019迁移到WritingTask模型，现在可以安全删除

Revision ID: 022_drop_generation_task_fields
Revises: 021_add_quality_control_fields
Create Date: 2026-04-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '022_drop_generation_task_fields'
down_revision = '021_add_quality_control_fields'
branch_labels = None
depends_on = None


def upgrade():
    """删除NovelProject中9个DEPRECATED字段"""
    # 检查字段是否存在，避免重复删除报错
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('novel_projects')
    column_names = [col['name'] for col in columns]
    
    # 要删除的字段列表
    fields_to_drop = [
        'generation_task_type',
        'generation_task_status',
        'generation_task_total',
        'generation_task_completed',
        'generation_task_failed',
        'generation_task_skipped',
        'generation_task_current',
        'generation_task_started_at',
        'generation_task_updated_at'
    ]
    
    for field in fields_to_drop:
        if field in column_names:
            op.drop_column('novel_projects', field)
            print(f"[Migration] 已删除字段: {field}")
        else:
            print(f"[Migration] 字段已不存在，跳过: {field}")


def downgrade():
    """恢复删除的字段（用于回退）"""
    # 添加回删除的字段
    op.add_column('novel_projects', sa.Column(
        'generation_task_type', sa.String(50), nullable=True,
        comment="[DEPRECATED] 当前生成任务类型"))
    op.add_column('novel_projects', sa.Column(
        'generation_task_status', sa.String(20), nullable=True,
        comment="[DEPRECATED] 生成任务状态"))
    op.add_column('novel_projects', sa.Column(
        'generation_task_total', sa.Integer, default=0,
        comment="[DEPRECATED] 任务总数量"))
    op.add_column('novel_projects', sa.Column(
        'generation_task_completed', sa.Integer, default=0,
        comment="[DEPRECATED] 已完成数量"))
    op.add_column('novel_projects', sa.Column(
        'generation_task_failed', sa.Integer, default=0,
        comment="[DEPRECATED] 失败数量"))
    op.add_column('novel_projects', sa.Column(
        'generation_task_skipped', sa.Integer, default=0,
        comment="[DEPRECATED] 跳过数量"))
    op.add_column('novel_projects', sa.Column(
        'generation_task_current', sa.Integer, nullable=True,
        comment="[DEPRECATED] 当前处理项"))
    op.add_column('novel_projects', sa.Column(
        'generation_task_started_at', sa.String(50), nullable=True,
        comment="[DEPRECATED] 任务开始时间"))
    op.add_column('novel_projects', sa.Column(
        'generation_task_updated_at', sa.String(50), nullable=True,
        comment="[DEPRECATED] 任务更新时间"))