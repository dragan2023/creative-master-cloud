"""add quality control fields to writing_units table

添加实时质控机制所需的字段到writing_units表。

Revision ID: 021_add_quality_control_fields
Revises: 020_create_unit_outlines_table, 018_add_quality_reports
Create Date: 2026-04-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '021_add_quality_control_fields'
down_revision = '020_create_unit_outlines_table'
branch_labels = None
depends_on = None


def upgrade():
    """添加质控相关字段到writing_units表"""
    # 添加质控状态字段
    op.add_column('writing_units',
                  sa.Column('quality_control_status', sa.String(50), nullable=True,
                            server_default='pending',
                            comment="质控状态: pending/running/completed/failed"))

    # 添加质控报告字段
    op.add_column('writing_units',
                  sa.Column('quality_control_report', sa.JSON(), nullable=True,
                            server_default='{}',
                            comment="质控报告JSON"))

    # 添加修正列表字段
    op.add_column('writing_units',
                  sa.Column('quality_control_fixes', sa.JSON(), nullable=True,
                            server_default='[]',
                            comment="应用的修正列表JSON"))

    # 添加质控得分字段
    op.add_column('writing_units',
                  sa.Column('quality_control_score', sa.Float(), nullable=True,
                            server_default='0.0',
                            comment="质控得分(0-100)"))

    # 添加质控完成时间字段
    op.add_column('writing_units',
                  sa.Column('quality_control_completed_at', sa.DateTime(), nullable=True,
                            comment="质控完成时间"))

    # 添加修正前原始内容字段
    op.add_column('writing_units',
                  sa.Column('original_content_before_fix', sa.Text(), nullable=True,
                            comment="修正前的原始内容(用于撤销)"))


def downgrade():
    """移除质控相关字段"""
    op.drop_column('writing_units', 'original_content_before_fix')
    op.drop_column('writing_units', 'quality_control_completed_at')
    op.drop_column('writing_units', 'quality_control_score')
    op.drop_column('writing_units', 'quality_control_fixes')
    op.drop_column('writing_units', 'quality_control_report')
    op.drop_column('writing_units', 'quality_control_status')
