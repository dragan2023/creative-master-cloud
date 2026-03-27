"""fix knowledge_bases expires_at field type from String to DateTime

Revision ID: 014_fix_kb_expires_at_type
Revises: 013_add_tenant_support
Create Date: 2026-03-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '014_fix_kb_expires_at_type'
down_revision = '013_add_tenant_support'
branch_labels = None
depends_on = None


def upgrade():
    """修复 knowledge_bases 表 expires_at 字段类型从 String(30) 改为 DateTime
    
    SQLite 使用 batch_alter_table，PostgreSQL 需要显式 USING 子句
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    if is_sqlite:
        # SQLite 使用 batch_alter_table
        with op.batch_alter_table('knowledge_bases') as batch_op:
            batch_op.alter_column(
                'expires_at',
                existing_type=sa.String(30),
                type_=sa.DateTime(),
                existing_nullable=True
            )
    else:
        # PostgreSQL 需要 USING 子句进行类型转换
        op.execute(
            "ALTER TABLE knowledge_bases "
            "ALTER COLUMN expires_at TYPE TIMESTAMP WITHOUT TIME ZONE "
            "USING expires_at::timestamp without time zone"
        )


def downgrade():
    """回滚：DateTime 改回 String(30)"""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    if is_sqlite:
        # SQLite 使用 batch_alter_table
        with op.batch_alter_table('knowledge_bases') as batch_op:
            batch_op.alter_column(
                'expires_at',
                existing_type=sa.DateTime(),
                type_=sa.String(30),
                existing_nullable=True
            )
    else:
        # PostgreSQL 需要 USING 子句进行类型转换
        op.execute(
            "ALTER TABLE knowledge_bases "
            "ALTER COLUMN expires_at TYPE VARCHAR(30) "
            "USING expires_at::varchar"
        )
