"""add cache expires_at index

Revision ID: 010_add_cache_expires_index
Revises: 009_add_proofread_tables
Create Date: 2026-03-10

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '010_add_cache_expires_index'
# 依赖 proofread_tables，因为需要 proofread_cache 表
down_revision = '009_add_proofread_tables'
branch_labels = None
depends_on = None


def upgrade():
    """添加缓存表过期时间索引，优化过期缓存清理查询"""
    # 检查索引是否已存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes('proofread_cache')]
    
    # 添加 expires_at 索引，用于快速清理过期缓存
    if 'ix_proofread_cache_expires_at' not in indexes:
        op.create_index(
            'ix_proofread_cache_expires_at',
            'proofread_cache',
            ['expires_at']
        )

    # 添加复合索引，优化缓存查询（虽然 cache_key 是 UNIQUE，但复合索引可以加速过期检查）
    if 'ix_proofread_cache_key_expires' not in indexes:
        op.create_index(
            'ix_proofread_cache_key_expires',
            'proofread_cache',
            ['cache_key', 'expires_at']
        )


def downgrade():
    """移除索引"""
    op.drop_index('ix_proofread_cache_key_expires',
                  table_name='proofread_cache')
    op.drop_index('ix_proofread_cache_expires_at',
                  table_name='proofread_cache')
