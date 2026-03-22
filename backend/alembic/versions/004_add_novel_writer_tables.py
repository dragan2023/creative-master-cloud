"""添加小说/剧本生成模块表

Revision ID: 004
Revises: 003_add_channel_to_api_keys
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003_api_key_channel'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建小说/剧本项目表
    op.create_table(
        'novel_projects',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('project_type', sa.String(20),
                  nullable=False, server_default='novel'),
        sa.Column('status', sa.String(20),
                  nullable=False, server_default='draft'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('outline_content', sa.Text(), nullable=True),
        sa.Column('outline_file_path', sa.String(255), nullable=True),
        sa.Column('outline_file_name', sa.String(100), nullable=True),
        sa.Column('toc_content', sa.Text(), nullable=True),
        sa.Column('total_chapters', sa.Integer(), server_default='0'),
        sa.Column('target_words_per_chapter',
                  sa.Integer(), server_default='3000'),
        sa.Column('style_guide', sa.String(500), nullable=True),
        sa.Column('genre', sa.String(50), nullable=True),
        sa.Column('language', sa.String(20), server_default='zh-CN'),
        sa.Column('knowledge_base_config', sa.Text(), nullable=True),
        sa.Column('generation_config', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(),
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )

    # 创建索引
    op.create_index('ix_novel_projects_user_id', 'novel_projects', ['user_id'])
    op.create_index('ix_novel_projects_status', 'novel_projects', ['status'])
    op.create_index('ix_novel_projects_project_type',
                    'novel_projects', ['project_type'])

    # 创建章节表
    op.create_table(
        'novel_chapters',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('status', sa.String(20), nullable=False,
                  server_default='pending'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('word_count', sa.Integer(), server_default='0'),
        sa.Column('character_count', sa.Integer(), server_default='0'),
        sa.Column('scene_metadata', sa.Text(), nullable=True),
        sa.Column('generation_model', sa.String(50), nullable=True),
        sa.Column('generation_time', sa.DateTime(), nullable=True),
        sa.Column('generation_duration', sa.Float(), nullable=True),
        sa.Column('file_path', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(),
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['project_id'], ['novel_projects.id'], ondelete='CASCADE')
    )

    # 创建索引
    op.create_index('ix_novel_chapters_project_id',
                    'novel_chapters', ['project_id'])
    op.create_index('ix_novel_chapters_chapter_number',
                    'novel_chapters', ['chapter_number'])
    op.create_index('ix_novel_chapters_status', 'novel_chapters', ['status'])
    op.create_index('ix_novel_chapters_project_chapter', 'novel_chapters', [
                    'project_id', 'chapter_number'], unique=True)


def downgrade() -> None:
    # 删除章节表
    op.drop_index('ix_novel_chapters_project_chapter', 'novel_chapters')
    op.drop_index('ix_novel_chapters_status', 'novel_chapters')
    op.drop_index('ix_novel_chapters_chapter_number', 'novel_chapters')
    op.drop_index('ix_novel_chapters_project_id', 'novel_chapters')
    op.drop_table('novel_chapters')

    # 删除项目表
    op.drop_index('ix_novel_projects_project_type', 'novel_projects')
    op.drop_index('ix_novel_projects_status', 'novel_projects')
    op.drop_index('ix_novel_projects_user_id', 'novel_projects')
    op.drop_table('novel_projects')
