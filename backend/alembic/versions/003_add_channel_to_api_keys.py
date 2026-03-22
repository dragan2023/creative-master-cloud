"""add channel field to user_api_keys

Revision ID: 003_api_key_channel
Revises: 002_generation_title
Create Date: 2026-02-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_api_key_channel'
down_revision = '002_generation_title'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 channel 字段到 user_api_keys 表
    op.add_column('user_api_keys', sa.Column(
        'channel', sa.String(50), nullable=True,
        server_default='default', comment='渠道分组'))


def downgrade():
    op.drop_column('user_api_keys', 'channel')
