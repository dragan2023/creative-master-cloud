"""
数据库连接配置
使用 SQLAlchemy 异步引擎连接 PostgreSQL

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData
from typing import AsyncGenerator

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

settings = get_settings()

# 判断是否使用SQLite
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# 同步数据库URL（用于后台任务）
if is_sqlite:
    SYNC_DATABASE_URL = settings.DATABASE_URL.replace(
        "sqlite+aiosqlite://", "sqlite://")
else:
    SYNC_DATABASE_URL = settings.DATABASE_URL.replace(
        "+aiosqlite", "").replace("+asyncpg", "")

# 创建异步引擎
if is_sqlite:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # 禁用SQL日志输出
        connect_args={"check_same_thread": False}  # SQLite需要
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # 禁用SQL日志输出
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 声明基类
Base = declarative_base()

# 命名约定（用于约束命名）
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖项

    Yields:
        AsyncSession: 数据库会话实例
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    初始化数据库

    策略：只创建基础表结构，依赖 run_migrations() 完成列扩展
    这样避免与 Alembic 迁移冲突
    """
    # 导入所有模型以确保它们被注册到 Base.metadata
    from app.models import (
        User, UserAPIKey, Generation, KnowledgeBase,
        PromptTemplate, SystemLog, SystemVersion, UserAction, SystemConfig,
        WritingModelConfig
    )

    # 数据库连接重试机制（生产环境必需）
    import asyncio
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    max_retries = 30
    retry_delay = 2
    last_error = None

    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                if is_sqlite:
                    result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
                else:
                    result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name = 'users'"))

                if result.fetchone() is None:
                    # 数据库未初始化，创建基础表
                    await conn.run_sync(Base.metadata.create_all)
                    logger.info("[DB] 数据库表首次创建完成")
                else:
                    logger.info("[DB] 数据库表已存在，跳过 create_all")

            # 连接成功，跳出重试循环
            break

        except (OperationalError, ConnectionRefusedError, OSError) as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"[DB] 数据库连接失败 (尝试 {attempt + 1}/{max_retries})，{retry_delay}秒后重试: {e}")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"[DB] 数据库连接失败，已达到最大重试次数: {e}")
                raise

    # 运行数据库迁移（添加缺失的列）
    await run_migrations()


async def run_migrations() -> None:
    """
    数据库迁移：添加缺失的列和表

    所有迁移都检查列/表是否存在，确保幂等性
    """
    from sqlalchemy import text
    from app.models.writing_model_config import WritingModelConfig

    async with engine.begin() as conn:
        if is_sqlite:
            # SQLite 迁移
            try:
                # === writing_model_configs 表迁移 ===
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='writing_model_configs'"))
                if result.fetchone() is None:
                    await conn.run_sync(Base.metadata.create_all, tables=[WritingModelConfig.__table__])
                    logger.info("Migration: 创建 writing_model_configs 表")

                # === system_versions 表迁移 ===
                result = await conn.execute(text("PRAGMA table_info(system_versions)"))
                columns = [row[1] for row in result.fetchall()]

                if 'backup_path' not in columns:
                    await conn.execute(text("ALTER TABLE system_versions ADD COLUMN backup_path VARCHAR(500)"))
                if 'backup_size' not in columns:
                    await conn.execute(text("ALTER TABLE system_versions ADD COLUMN backup_size INTEGER DEFAULT 0"))
                if 'backup_created_at' not in columns:
                    await conn.execute(text("ALTER TABLE system_versions ADD COLUMN backup_created_at VARCHAR(30)"))

                # === knowledge_bases 表迁移 ===
                result = await conn.execute(text("PRAGMA table_info(knowledge_bases)"))
                kb_columns = [row[1] for row in result.fetchall()]

                if 'category' not in kb_columns:
                    await conn.execute(text("ALTER TABLE knowledge_bases ADD COLUMN category VARCHAR(50) DEFAULT 'general'"))
                if 'api_config' not in kb_columns:
                    await conn.execute(text("ALTER TABLE knowledge_bases ADD COLUMN api_config TEXT"))

                # === user_api_keys 表迁移 ===
                result = await conn.execute(text("PRAGMA table_info(user_api_keys)"))
                uak_columns = [row[1] for row in result.fetchall()]

                if 'channel' not in uak_columns:
                    await conn.execute(text("ALTER TABLE user_api_keys ADD COLUMN channel VARCHAR(50) DEFAULT 'default'"))

                # === novel_projects 表迁移（生成任务状态字段）===
                result = await conn.execute(text("PRAGMA table_info(novel_projects)"))
                np_columns = [row[1] for row in result.fetchall()]

                if 'generation_task_type' not in np_columns:
                    await conn.execute(text("ALTER TABLE novel_projects ADD COLUMN generation_task_type VARCHAR(50)"))
                if 'generation_task_status' not in np_columns:
                    await conn.execute(text("ALTER TABLE novel_projects ADD COLUMN generation_task_status VARCHAR(20)"))
                if 'generation_task_total' not in np_columns:
                    await conn.execute(text("ALTER TABLE novel_projects ADD COLUMN generation_task_total INTEGER DEFAULT 0"))
                if 'generation_task_completed' not in np_columns:
                    await conn.execute(text("ALTER TABLE novel_projects ADD COLUMN generation_task_completed INTEGER DEFAULT 0"))
                if 'generation_task_failed' not in np_columns:
                    await conn.execute(text("ALTER TABLE novel_projects ADD COLUMN generation_task_failed INTEGER DEFAULT 0"))
                if 'generation_task_skipped' not in np_columns:
                    await conn.execute(text("ALTER TABLE novel_projects ADD COLUMN generation_task_skipped INTEGER DEFAULT 0"))
                if 'generation_task_current' not in np_columns:
                    await conn.execute(text("ALTER TABLE novel_projects ADD COLUMN generation_task_current INTEGER"))
                if 'generation_task_started_at' not in np_columns:
                    await conn.execute(text("ALTER TABLE novel_projects ADD COLUMN generation_task_started_at VARCHAR(50)"))
                if 'generation_task_updated_at' not in np_columns:
                    await conn.execute(text("ALTER TABLE novel_projects ADD COLUMN generation_task_updated_at VARCHAR(50)"))

                logger.info("[Migration] SQLite 迁移检查完成")
            except Exception as e:
                logger.warning(f"[Migration] SQLite 迁移警告: {e}")
        else:
            # PostgreSQL 迁移
            try:
                # === writing_model_configs 表迁移 ===
                result = await conn.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name = 'writing_model_configs'
                """))
                if result.fetchone() is None:
                    await conn.run_sync(Base.metadata.create_all, tables=[WritingModelConfig.__table__])
                    logger.info("Migration: 创建 writing_model_configs 表")

                # === system_versions 表迁移 ===
                result = await conn.execute(text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'system_versions'
                """))
                columns = [row[0] for row in result.fetchall()]

                if 'backup_path' not in columns:
                    await conn.execute(text("ALTER TABLE system_versions ADD COLUMN backup_path VARCHAR(500)"))
                if 'backup_size' not in columns:
                    await conn.execute(text("ALTER TABLE system_versions ADD COLUMN backup_size INTEGER DEFAULT 0"))
                if 'backup_created_at' not in columns:
                    await conn.execute(text("ALTER TABLE system_versions ADD COLUMN backup_created_at VARCHAR(30)"))

                # === knowledge_bases 表迁移 ===
                result = await conn.execute(text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'knowledge_bases'
                """))
                kb_columns = [row[0] for row in result.fetchall()]

                if 'category' not in kb_columns:
                    await conn.execute(text("ALTER TABLE knowledge_bases ADD COLUMN category VARCHAR(50) DEFAULT 'general'"))
                if 'api_config' not in kb_columns:
                    await conn.execute(text("ALTER TABLE knowledge_bases ADD COLUMN api_config TEXT"))

                # === user_api_keys 表迁移 ===
                result = await conn.execute(text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'user_api_keys'
                """))
                uak_columns = [row[0] for row in result.fetchall()]

                if 'channel' not in uak_columns:
                    await conn.execute(text("ALTER TABLE user_api_keys ADD COLUMN channel VARCHAR(50) DEFAULT 'default'"))

                logger.info("[Migration] PostgreSQL 迁移检查完成")
            except Exception as e:
                logger.warning(f"[Migration] PostgreSQL 迁移警告: {e}")


async def close_db() -> None:
    """
    关闭数据库连接
    """
    await engine.dispose()


async def close_db() -> None:
    """
    关闭数据库连接
    """
    await engine.dispose()
