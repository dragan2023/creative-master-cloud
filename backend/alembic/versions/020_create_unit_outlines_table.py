"""create unit_outlines table for independent outline storage

将大型JSON字段(unit_summaries/episode_outlines/scene_outlines/chapter_outlines)
中的数据迁移到独立表，支持增量查询/更新。

过渡期策略：双写（独立表+JSON字段），读取优先独立表。

Revision ID: 020_create_unit_outlines_table
Revises: 019_migrate_generation_task_to_writing_task
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '020_create_unit_outlines_table'
down_revision = '019_migrate_generation_task_to_writing_task'
branch_labels = None
depends_on = None


def upgrade():
    """创建unit_outlines表并迁移现有JSON数据"""
    # 1. 创建unit_outlines表
    op.create_table(
        'unit_outlines',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer, sa.ForeignKey(
            'novel_projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('unit_number', sa.Integer, nullable=False),
        sa.Column('content_type', sa.String(20), nullable=False),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('detailed_outline', sa.Text, nullable=True),
        sa.Column('key_events', sa.JSON, nullable=True),
        sa.Column('character_arcs', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # 2. 创建索引
    op.create_index(
        'ix_unit_outline_project_unit',
        'unit_outlines',
        ['project_id', 'unit_number'],
        unique=True
    )
    op.create_index(
        'ix_unit_outline_project_type',
        'unit_outlines',
        ['project_id', 'content_type'],
        unique=False
    )

    # 3. 迁移现有JSON数据到独立表
    bind = op.get_bind()

    # 检查novel_projects表是否存在
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    if 'novel_projects' not in existing_tables:
        print("[迁移] novel_projects表不存在，跳过数据迁移")
        return

    np_columns = [col['name']
                  for col in inspector.get_columns('novel_projects')]

    # 迁移unit_summaries
    if 'unit_summaries' in np_columns:
        _migrate_json_field(
            bind,
            json_field='unit_summaries',
            content_type='novel',
            extract_fn=lambda k, v: {
                'unit_number': int(k),
                'title': v.get('title', '') if isinstance(v, dict) else '',
                'summary': v.get('summary', '') if isinstance(v, dict) else str(v),
                'status': v.get('status', 'pending') if isinstance(v, dict) else 'pending',
            }
        )

    # 迁移chapter_outlines
    if 'chapter_outlines' in np_columns:
        _migrate_json_field(
            bind,
            json_field='chapter_outlines',
            content_type='novel',
            extract_fn=lambda k, v: {
                'unit_number': int(k),
                'title': v.get('chapter_title', '') if isinstance(v, dict) else '',
                'summary': v.get('chapter_summary', '') if isinstance(v, dict) else '',
                'detailed_outline': v.get('detailed_outline', '') if isinstance(v, dict) else '',
                'key_events': v.get('key_events', []) if isinstance(v, dict) else [],
                'character_arcs': v.get('character_arcs', '') if isinstance(v, dict) else '',
                'status': v.get('status', 'pending') if isinstance(v, dict) else 'pending',
            }
        )

    # 迁移episode_outlines
    if 'episode_outlines' in np_columns:
        _migrate_json_field(
            bind,
            json_field='episode_outlines',
            content_type='series_script',
            extract_fn=lambda k, v: {
                'unit_number': int(k),
                'title': v.get('episode_title', '') if isinstance(v, dict) else '',
                'summary': v.get('episode_summary', '') if isinstance(v, dict) else '',
                'detailed_outline': v.get('detailed_outline', '') if isinstance(v, dict) else '',
                'status': v.get('status', 'pending') if isinstance(v, dict) else 'pending',
            }
        )

    # 迁移scene_outlines
    if 'scene_outlines' in np_columns:
        _migrate_json_field(
            bind,
            json_field='scene_outlines',
            content_type='movie_script',
            extract_fn=lambda k, v: {
                'unit_number': int(k),
                'title': v.get('scene_title', '') if isinstance(v, dict) else '',
                'summary': v.get('scene_summary', '') if isinstance(v, dict) else '',
                'detailed_outline': v.get('detailed_outline', '') if isinstance(v, dict) else '',
                'status': v.get('status', 'pending') if isinstance(v, dict) else 'pending',
            }
        )

    print("[迁移] unit_outlines表创建和数据迁移完成")


def _migrate_json_field(bind, json_field, content_type, extract_fn):
    """从JSON字段迁移数据到unit_outlines表

    Args:
        bind: 数据库连接
        json_field: JSON字段名
        content_type: 内容类型
        extract_fn: 从JSON值提取字段的函数
    """
    import json

    novel_projects = sa.table(
        'novel_projects',
        sa.column('id', sa.Integer),
        sa.column(json_field, sa.JSON),
    )

    unit_outlines = sa.table(
        'unit_outlines',
        sa.column('project_id', sa.Integer),
        sa.column('unit_number', sa.Integer),
        sa.column('content_type', sa.String),
        sa.column('title', sa.String),
        sa.column('summary', sa.Text),
        sa.column('detailed_outline', sa.Text),
        sa.column('key_events', sa.JSON),
        sa.column('character_arcs', sa.Text),
        sa.column('status', sa.String),
    )

    # 查询所有有该JSON字段的项目
    results = bind.execute(
        sa.select([novel_projects.c.id, novel_projects.c[json_field]])
    ).fetchall()

    migrated = 0
    for project_id, json_data in results:
        if not json_data or not isinstance(json_data, dict):
            continue

        for key, value in json_data.items():
            try:
                extracted = extract_fn(key, value)
                bind.execute(
                    unit_outlines.insert().values(
                        project_id=project_id,
                        content_type=content_type,
                        **extracted,
                    )
                )
                migrated += 1
            except (ValueError, TypeError) as e:
                print(f"[迁移] 项目{project_id}字段{json_field}键{key}迁移失败: {e}")

    print(f"[迁移] {json_field}→unit_outlines: 迁移{migrated}条记录")


def downgrade():
    """回滚：删除unit_outlines表"""
    op.drop_index('ix_unit_outline_project_type', table_name='unit_outlines')
    op.drop_index('ix_unit_outline_project_unit', table_name='unit_outlines')
    op.drop_table('unit_outlines')
    print("[回滚] unit_outlines表已删除")
