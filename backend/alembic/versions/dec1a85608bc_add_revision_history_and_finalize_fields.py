"""add revision history and finalize fields

Revision ID: dec1a85608bc
Revises: 017_add_style_document_fields
Create Date: 2026-04-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dec1a85608bc'
down_revision: Union[str, None] = '017_add_style_document_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库架构"""
    # 创建generation_revision_history表
    op.create_table(
        'generation_revision_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('generation_id', sa.Integer(), sa.ForeignKey(
            'generations.id', ondelete='CASCADE'), nullable=False, index=True, comment='生成记录ID'),
        sa.Column('round_number', sa.Integer(),
                  nullable=False, comment='修订轮次(从1开始)'),
        sa.Column('user_feedback', sa.Text(),
                  nullable=False, comment='用户修改意见'),
        sa.Column('diff_instructions', sa.Text(),
                  nullable=True, comment='LLM输出的差异指令(JSON格式)'),
        sa.Column('content_before', sa.Text(),
                  nullable=True, comment='修订前完整内容'),
        sa.Column('content_after', sa.Text(),
                  nullable=True, comment='修订后完整内容'),
        sa.Column('token_usage', sa.Integer(), default=0, comment='该轮token消耗'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # 在generations表中添加新字段
    op.add_column('generations', sa.Column('is_finalized',
                  sa.Boolean(), default=False, comment='是否已最终确认'))
    op.add_column('generations', sa.Column('revision_count',
                  sa.Integer(), default=0, comment='修订轮次总数'))


def downgrade() -> None:
    """降级数据库架构"""
    # 删除generations表中的新字段
    op.drop_column('generations', 'revision_count')
    op.drop_column('generations', 'is_finalized')

    # 删除generation_revision_history表
    op.drop_table('generation_revision_history')
