"""add outline persistence fields

Revision ID: 7ac48cb666f1
Revises: dec1a85608bc
Create Date: 2026-04-11 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ac48cb666f1'
down_revision: Union[str, None] = 'dec1a85608bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加大纲持久化字段"""
    # 检查列是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('generations')]

    if 'outline_stage' not in columns:
        op.add_column('generations', sa.Column('outline_stage', sa.Integer(
        ), nullable=True, comment='两阶段大纲当前阶段: 0-未开始, 1-全局大纲生成中, 2-全局大纲完成, 3-单元概述生成中, 4-完成'))

    if 'global_outline_content' not in columns:
        op.add_column('generations', sa.Column(
            'global_outline_content', sa.Text(), nullable=True, comment='全局大纲内容'))

    if 'unit_summaries_content' not in columns:
        op.add_column('generations', sa.Column(
            'unit_summaries_content', sa.Text(), nullable=True, comment='单元概述内容'))

    if 'revision_messages' not in columns:
        op.add_column('generations', sa.Column('revision_messages',
                      sa.JSON(), nullable=True, comment='修订对话历史'))


def downgrade() -> None:
    """回滚大纲持久化字段"""
    op.drop_column('generations', 'revision_messages')
    op.drop_column('generations', 'unit_summaries_content')
    op.drop_column('generations', 'global_outline_content')
    op.drop_column('generations', 'outline_stage')
