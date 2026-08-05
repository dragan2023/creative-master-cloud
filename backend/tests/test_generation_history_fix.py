"""
历史记录修复测试

覆盖:
1. 流式生成完成后，应更新预先创建的生成记录，而不是新建第二条记录；
2. 模块类型应显式落库（tvc 不再被误存为 short_video）；
3. 历史列表查询应过滤掉"已完成但无正文"的旧版状态记录。
"""
import asyncio
import time

import pytest
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.agents.orchestrator.impl.mixins.generation_core import GenerationCoreMixin
from app.agents.orchestrator.impl.mixins.session import SessionMixin
from app.core.database import Base
from app.models.generation import Generation, GenerationModule, GenerationStatus


class _FakeLLMProvider:
    model_name = "test-model"

    def get_model_info(self):
        return {"provider": "test-provider"}


class _FakeCtx:
    def __init__(self):
        self.input_params = {"title": "测试TVC", "brand_product": "楚尧面霜"}
        self.final_content = "测试正文内容"
        self.start_time = time.time()
        self.llm_provider = _FakeLLMProvider()
        self.model_display_name = "测试模型"


class _FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


class _MiniOrchestrator(GenerationCoreMixin, SessionMixin):
    """仅包含测试所需 mixin 的迷你编排器"""
    logger = None


@pytest.mark.asyncio
async def test_save_and_complete_updates_existing_record():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        # 模拟流式端点预先创建的"状态记录"（模块正确、无正文）
        state = Generation(
            user_id=1,
            module=GenerationModule.TVC,
            status=GenerationStatus.PROCESSING,
            input_params={"title": "测试TVC"},
            title="测试TVC",
            current_stage="generating",
        )
        db.add(state)
        await db.commit()
        await db.refresh(state)
        state_id = state.id

        orchestrator = _MiniOrchestrator()
        ctx = _FakeCtx()
        fake_logger = _FakeLogger()

        events = []
        async for chunk in orchestrator._save_and_complete(
            ctx=ctx,
            db=db,
            user_id=1,
            logger=fake_logger,
            module="tvc",
            generation_id=state_id,
        ):
            events.append(chunk)

        # 不应新增记录：仍只有一条
        count = (await db.execute(select(func.count(Generation.id)))).scalar()
        assert count == 1

        # 该记录应被更新为完成状态、正确模块、正文
        gen = (await db.execute(select(Generation).where(Generation.id == state_id))).scalar_one()
        assert gen.module == GenerationModule.TVC
        assert gen.status == GenerationStatus.COMPLETED
        assert gen.output_content.startswith("测试正文内容")
        assert gen.provider == "test-provider"
        assert gen.model_name == "test-model"

        # done 事件应携带正确的 generation_id
        done_event = next((e for e in events if "done" in e), None)
        assert done_event is not None
        assert f'"generation_id": {state_id}' in done_event

    await engine.dispose()


@pytest.mark.asyncio
async def test_save_and_complete_new_record_uses_explicit_module():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        orchestrator = _MiniOrchestrator()
        ctx = _FakeCtx()
        fake_logger = _FakeLogger()

        async for _ in orchestrator._save_and_complete(
            ctx=ctx,
            db=db,
            user_id=1,
            logger=fake_logger,
            module="tvc",
            generation_id=None,
        ):
            pass

        gen = (await db.execute(select(Generation))).scalar_one()
        assert gen.module == GenerationModule.TVC
        assert gen.output_content.startswith("测试正文内容")

    await engine.dispose()


@pytest.mark.asyncio
async def test_history_filter_excludes_empty_completed_records():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        db.add_all([
            Generation(user_id=1, module=GenerationModule.TVC,
                       status=GenerationStatus.COMPLETED, title="空状态记录",
                       output_content=None),
            Generation(user_id=1, module=GenerationModule.TVC,
                       status=GenerationStatus.COMPLETED, title="正常记录",
                       output_content="有正文"),
            Generation(user_id=1, module=GenerationModule.PRINT_AD,
                       status=GenerationStatus.PROCESSING, title="进行中记录",
                       output_content=None),
        ])
        await db.commit()

        # 复刻历史列表端点的过滤条件
        stmt = select(Generation).where(
            Generation.user_id == 1,
            or_(
                and_(
                    Generation.output_content.isnot(None),
                    Generation.output_content != "",
                ),
                Generation.status != GenerationStatus.COMPLETED,
            ),
        )
        rows = (await db.execute(stmt)).scalars().all()
        titles = {g.title for g in rows}
        assert titles == {"正常记录", "进行中记录"}

    await engine.dispose()


@pytest.mark.asyncio
async def test_history_additional_filters():
    """状态、关键词、日期范围筛选（复刻历史接口的查询条件）"""
    from datetime import datetime, timedelta

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now()

    async with async_session() as db:
        db.add_all([
            Generation(user_id=1, module=GenerationModule.TVC,
                       status=GenerationStatus.COMPLETED, title="化妆品广告",
                       output_content="有正文", created_at=now),
            Generation(user_id=1, module=GenerationModule.PRINT_AD,
                       status=GenerationStatus.FAILED, title="重阳节海报",
                       output_content="部分内容", created_at=now - timedelta(days=2)),
            Generation(user_id=1, module=GenerationModule.NOVEL,
                       status=GenerationStatus.COMPLETED, title="小说大纲A",
                       output_content="正文", created_at=now - timedelta(days=10)),
        ])
        await db.commit()

        # 状态筛选
        stmt = select(Generation).where(
            Generation.user_id == 1,
            Generation.status == GenerationStatus.FAILED,
        )
        titles = {g.title for g in (await db.execute(stmt)).scalars().all()}
        assert titles == {"重阳节海报"}

        # 关键词筛选（标题 LIKE）
        stmt = select(Generation).where(
            Generation.user_id == 1,
            Generation.title.ilike("%广告%"),
        )
        titles = {g.title for g in (await db.execute(stmt)).scalars().all()}
        assert titles == {"化妆品广告"}

        # 日期范围筛选（最近 3 天）
        stmt = select(Generation).where(
            Generation.user_id == 1,
            Generation.created_at >= now - timedelta(days=3),
        )
        titles = {g.title for g in (await db.execute(stmt)).scalars().all()}
        assert titles == {"化妆品广告", "重阳节海报"}

    await engine.dispose()
