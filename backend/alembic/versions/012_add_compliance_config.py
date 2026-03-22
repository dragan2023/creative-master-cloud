"""add compliance_config field

Revision ID: 012
Revises: 011_add_project_knowledge_base_fields
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012_add_compliance_config'
down_revision = '011_add_outline_stages'
branch_labels = None
depends_on = None


def upgrade():
    """添加合规审核配置字段"""
    # 检查列是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('novel_projects')]

    if 'compliance_config' not in columns:
        op.add_column(
            'novel_projects',
            sa.Column('compliance_config', sa.JSON(),
                      nullable=True, comment='合规审核配置')
        )


def downgrade():
    """移除合规审核配置字段"""
    op.drop_column('novel_projects', 'compliance_config')
