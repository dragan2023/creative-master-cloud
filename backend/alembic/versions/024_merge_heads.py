"""merge heads 018_add_quality_reports and 023_add_character_profiles

Revision ID: 024_merge_heads
Revises: 018_add_quality_reports, 023_add_character_profiles
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa


revision = '024_merge_heads'
down_revision = ('018_add_quality_reports', '023_add_character_profiles')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
