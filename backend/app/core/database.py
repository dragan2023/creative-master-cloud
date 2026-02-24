"""
数据库连接配置
使用 SQLAlchemy 异步引擎连接 PostgreSQL
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData
from typing import AsyncGenerator

from app.core.config import get_settings

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
    初始化数据库（创建所有表）
    """
    # 导入所有模型以确保它们被注册到 Base.metadata
    from app.models import (
        User, UserAPIKey, Generation, KnowledgeBase,
        PromptTemplate, SystemLog, SystemVersion, UserAction, SystemConfig
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 运行数据库迁移（添加缺失的列）
    await run_migrations()


async def run_migrations() -> None:
    """
    数据库迁移：添加缺失的列
    """
    from sqlalchemy import text

    async with engine.begin() as conn:
        if is_sqlite:
            # SQLite 迁移
            try:
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

                print(
                    f"Migration completed: system_versions columns={columns}, knowledge_bases columns={kb_columns}")
            except Exception as e:
                print(f"Migration error: {e}")
        else:
            # PostgreSQL 迁移
            try:
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

                # knowledge_bases 表迁移
                result = await conn.execute(text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'knowledge_bases'
                """))
                kb_columns = [row[0] for row in result.fetchall()]

                if 'category' not in kb_columns:
                    await conn.execute(text("ALTER TABLE knowledge_bases ADD COLUMN category VARCHAR(50) DEFAULT 'general'"))
                if 'api_config' not in kb_columns:
                    await conn.execute(text("ALTER TABLE knowledge_bases ADD COLUMN api_config TEXT"))

            except Exception as e:
                print(f"Migration error: {e}")


async def close_db() -> None:
    """
    关闭数据库连接
    """
    await engine.dispose()
