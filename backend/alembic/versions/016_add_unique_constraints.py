"""add unique constraints to writing_units and writing_scenes

Revision ID: 016_add_unique_constraints
Revises: 015_add_multi_agent_writing_tables
Create Date: 2026-03-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '016_add_unique_constraints'
down_revision = '015_add_multi_agent_writing_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add unique constraints to prevent duplicate records"""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # 1. Clean up duplicate records in writing_units (keep the latest one)
    op.execute("""
        DELETE FROM writing_units 
        WHERE id NOT IN (
            SELECT MAX(id) FROM writing_units GROUP BY task_id, unit_index
        )
    """)
    
    # 2. Clean up duplicate records in writing_scenes (keep the latest one)
    op.execute("""
        DELETE FROM writing_scenes 
        WHERE id NOT IN (
            SELECT MAX(id) FROM writing_scenes GROUP BY unit_id, scene_index
        )
    """)
    
    # 3. Add unique constraints using batch mode for SQLite
    if is_sqlite:
        # SQLite requires batch mode for constraint operations
        with op.batch_alter_table('writing_units', schema=None) as batch_op:
            batch_op.create_unique_constraint(
                'uq_writing_units_task_unit', 
                ['task_id', 'unit_index']
            )
        
        with op.batch_alter_table('writing_scenes', schema=None) as batch_op:
            batch_op.create_unique_constraint(
                'uq_writing_scenes_unit_scene', 
                ['unit_id', 'scene_index']
            )
    else:
        # PostgreSQL and other databases
        try:
            op.create_unique_constraint(
                'uq_writing_units_task_unit', 
                'writing_units', 
                ['task_id', 'unit_index']
            )
        except Exception as e:
            print(f"Warning: Could not create unique constraint on writing_units: {e}")
        
        try:
            op.create_unique_constraint(
                'uq_writing_scenes_unit_scene', 
                'writing_scenes', 
                ['unit_id', 'scene_index']
            )
        except Exception as e:
            print(f"Warning: Could not create unique constraint on writing_scenes: {e}")


def downgrade():
    """Remove unique constraints"""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    if is_sqlite:
        with op.batch_alter_table('writing_units', schema=None) as batch_op:
            batch_op.drop_constraint('uq_writing_units_task_unit', type_='unique')
        
        with op.batch_alter_table('writing_scenes', schema=None) as batch_op:
            batch_op.drop_constraint('uq_writing_scenes_unit_scene', type_='unique')
    else:
        try:
            op.drop_constraint('uq_writing_units_task_unit', 'writing_units', type_='unique')
        except Exception:
            pass
        
        try:
            op.drop_constraint('uq_writing_scenes_unit_scene', 'writing_scenes', type_='unique')
        except Exception:
            pass
