"""migrate generation_task fields to writing_tasks and deprecate

将NovelProject中generation_task_*字段数据迁移到WritingTask表，
并在NovelProject模型中标记这些字段为deprecated。

Revision ID: 019_migrate_generation_task_to_writing_task
Revises: dec1a85608bc
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '019_migrate_generation_task_to_writing_task'
down_revision = 'dec1a85608bc'
branch_labels = None
depends_on = None


def upgrade():
    """迁移generation_task_*数据到WritingTask表

    步骤：
    1. 查询所有generation_task_status不为NULL的NovelProject
    2. 为每个项目创建对应的WritingTask记录
    3. 迁移进度信息
    4. 不删除原字段（向后兼容）
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # 检查writing_tasks表是否存在
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'writing_tasks' not in existing_tables:
        # writing_tasks表不存在，跳过迁移
        print("[迁移] writing_tasks表不存在，跳过generation_task迁移")
        return

    # 检查novel_projects表是否有generation_task_status列
    np_columns = [col['name']
                  for col in inspector.get_columns('novel_projects')]
    if 'generation_task_status' not in np_columns:
        print("[迁移] novel_projects表无generation_task_status列，跳过迁移")
        return

    # 查询需要迁移的项目
    novel_projects = sa.table(
        'novel_projects',
        sa.column('id', sa.Integer),
        sa.column('user_id', sa.Integer),
        sa.column('generation_task_type', sa.String),
        sa.column('generation_task_status', sa.String),
        sa.column('generation_task_total', sa.Integer),
        sa.column('generation_task_completed', sa.Integer),
        sa.column('generation_task_failed', sa.Integer),
        sa.column('generation_task_current', sa.Integer),
        sa.column('generation_task_started_at', sa.String),
    )

    writing_tasks = sa.table(
        'writing_tasks',
        sa.column('id', sa.Integer),
        sa.column('project_id', sa.Integer),
        sa.column('user_id', sa.Integer),
        sa.column('status', sa.String),
        sa.column('total_units', sa.Integer),
        sa.column('completed_units', sa.Integer),
        sa.column('start_from', sa.Integer),
        sa.column('config', sa.JSON),
    )

    # 状态映射：旧版 → WritingTask TaskStatus
    status_map = {
        'running': 'running',
        'completed': 'completed',
        'failed': 'failed',
        'cancelled': 'interrupted',
        'pending': 'pending',
    }

    # 查询所有有活跃generation_task的项目
    select_query = sa.select([
        novel_projects.c.id,
        novel_projects.c.user_id,
        novel_projects.c.generation_task_type,
        novel_projects.c.generation_task_status,
        novel_projects.c.generation_task_total,
        novel_projects.c.generation_task_completed,
        novel_projects.c.generation_task_failed,
        novel_projects.c.generation_task_current,
    ]).where(novel_projects.c.generation_task_status != None)

    results = bind.execute(select_query).fetchall()

    migrated_count = 0
    skipped_count = 0

    for row in results:
        project_id, user_id, task_type, task_status, total, completed, failed, current = row

        if not task_status:
            continue

        # 检查该项目是否已有对应的WritingTask
        existing = bind.execute(
            sa.select([sa.func.count()]).select_from(writing_tasks).where(
                writing_tasks.c.project_id == project_id
            )
        ).scalar()

        if existing and existing > 0:
            skipped_count += 1
            continue

        # 映射状态
        mapped_status = status_map.get(task_status, 'pending')

        # 创建WritingTask记录
        config_data = {
            "task_type": task_type,
            "migrated_from": "generation_task_fields",
            "generation_task_failed": failed or 0,
        }

        try:
            bind.execute(
                writing_tasks.insert().values(
                    project_id=project_id,
                    user_id=user_id,
                    status=mapped_status,
                    total_units=total or 0,
                    completed_units=completed or 0,
                    start_from=current or 1,
                    config=config_data,
                )
            )
            migrated_count += 1
        except Exception as e:
            print(f"[迁移] 项目{project_id}迁移失败: {e}")
            skipped_count += 1

    print(f"[迁移] 完成: 迁移{migrated_count}个项目，跳过{skipped_count}个项目")

    # 注意：不删除generation_task_*字段，保持向后兼容
    # 这些字段在模型层标记为deprecated


def downgrade():
    """回滚迁移（仅删除迁移创建的WritingTask记录）"""
    bind = op.get_bind()

    # 删除由迁移创建的WritingTask记录（config中有migrated_from标记）
    writing_tasks = sa.table(
        'writing_tasks',
        sa.column('id', sa.Integer),
        sa.column('config', sa.JSON),
    )

    if bind.dialect.name == 'sqlite':
        # SQLite不支持JSON查询，逐条检查
        results = bind.execute(
            sa.select([writing_tasks.c.id, writing_tasks.c.config])).fetchall()
        ids_to_delete = []
        for row in results:
            task_id, config = row
            if config and isinstance(config, dict) and config.get('migrated_from') == 'generation_task_fields':
                ids_to_delete.append(task_id)

        if ids_to_delete:
            bind.execute(
                writing_tasks.delete().where(writing_tasks.c.id.in_(ids_to_delete))
            )
    else:
        # PostgreSQL等支持JSON查询
        bind.execute(
            writing_tasks.delete().where(
                writing_tasks.c.config['migrated_from'].as_string(
                ) == 'generation_task_fields'
            )
        )

    print("[回滚] 已删除迁移创建的WritingTask记录")
