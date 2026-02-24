"""add custom provider fields to user_api_keys

Revision ID: 001_custom_provider
Revises: 
Create Date: 2026-02-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_custom_provider'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 添加 is_custom 字段
    op.add_column('user_api_keys', sa.Column(
        'is_custom', sa.Boolean(), nullable=False, server_default='0'))

    # 添加 provider_config 字段
    op.add_column('user_api_keys', sa.Column(
        'provider_config', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('user_api_keys', 'provider_config')
    op.drop_column('user_api_keys', 'is_custom')
