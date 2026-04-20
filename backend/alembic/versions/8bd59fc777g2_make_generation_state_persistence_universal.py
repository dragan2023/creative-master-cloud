"""make generation state persistence universal

Revision ID: 8bd59fc777g2
Revises: 7ac48cb666f1
Create Date: 2026-04-11 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8bd59fc777g2'
down_revision: Union[str, None] = '7ac48cb666f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将大纲专用字段改为通用状态字段"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('generations')]

    # 添加通用字段
    if 'current_stage' not in columns:
        op.add_column('generations', sa.Column('current_stage', sa.String(
            50), nullable=True, comment='当前生成阶段标识(由各模块自定义)'))

    if 'stage_data' not in columns:
        op.add_column('generations', sa.Column(
            'stage_data', sa.JSON(), nullable=True, comment='各阶段的完整状态数据(JSON格式)'))

    if 'session_context' not in columns:
        op.add_column('generations', sa.Column('session_context',
                      sa.JSON(), nullable=True, comment='会话上下文(修订历史、对话记录等)'))

    # 迁移旧数据到新字段(如果存在旧字段)
    if 'outline_stage' in columns:
        # 将outline_stage数据迁移到current_stage
        op.execute("""
            UPDATE generations 
            SET current_stage = 'outline_stage_' || outline_stage 
            WHERE outline_stage IS NOT NULL AND current_stage IS NULL
        """)

    if 'global_outline_content' in columns or 'unit_summaries_content' in columns:
        # 将内容数据迁移到stage_data
        op.execute("""
            UPDATE generations 
            SET stage_data = json_object(
                'global_outline', COALESCE(global_outline_content, ''),
                'unit_summaries', COALESCE(unit_summaries_content, '')
            )
            WHERE (global_outline_content IS NOT NULL OR unit_summaries_content IS NOT NULL) 
            AND stage_data IS NULL
        """)

    if 'revision_messages' in columns:
        # 将修订消息迁移到session_context
        op.execute("""
            UPDATE generations 
            SET session_context = json_object(
                'revision_messages', revision_messages
            )
            WHERE revision_messages IS NOT NULL AND session_context IS NULL
        """)


def downgrade() -> None:
    """回滚到大纲专用字段"""
    op.drop_column('generations', 'session_context')
    op.drop_column('generations', 'stage_data')
    op.drop_column('generations', 'current_stage')
