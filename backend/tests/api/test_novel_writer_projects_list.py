"""
小说项目列表 API 搜索与排序集成测试

通过真实 FastAPI 路由 + 内存 SQLite 验证 /api/v1/novel-writer/projects：
- 标题命中、题材（简介）命中、空白搜索、中文搜索、大小写不敏感
- LIKE 通配符转义（%、_、\\ 不改变匹配语义）
- 非法 sort_by / sort_order 返回 422（白名单校验）
- 升降序、筛选与搜索组合、分页总数准确与稳定 ID 次级排序
- 用户数据隔离
"""
from datetime import datetime

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.v1.endpoints import novel_writer
from app.core.database import Base, get_db
from app.models import NovelProject, ProjectStatus, ProjectType, User

pytestmark = pytest.mark.asyncio

PROJECTS_URL = "/api/v1/novel-writer/projects"

TEST_USER_ID = 1
OTHER_USER_ID = 2

# 种子项目 ID（显式主键，便于断言排序与分页）
PROJECT_XIUZHEN_WORLD = 101      # title 含「修真」「世界」
PROJECT_CITY_ROMANCE = 102       # 都市言情
PROJECT_STAR_TREK = 103          # 剧集剧本
PROJECT_ALPHA_PLAN = 104         # genre 含「硬核修真」，title 含 Alpha
PROJECT_UNDERSCORE_NAME = 105    # title 含 A_B（转义测试目标）
PROJECT_WILDCARD_DECOY = 106     # title 含 AxB（若未转义 _ 会被误命中）
PROJECT_OTHER_USER = 201         # 属于其他用户，不可见


def _build_seed_project(
    project_id: int,
    user_id: int,
    title: str,
    genre: str,
    content_type: str,
    updated_at: datetime,
    created_at: datetime,
) -> NovelProject:
    """构造种子项目（显式时间戳，保证排序断言确定性）"""
    project_type = ProjectType.NOVEL if content_type == "novel" else ProjectType.SCRIPT
    return NovelProject(
        id=project_id,
        user_id=user_id,
        title=title,
        project_type=project_type,
        content_type=content_type,
        genre=genre,
        status=ProjectStatus.INIT,
        created_at=created_at,
        updated_at=updated_at,
    )


def _seed_projects() -> list:
    """当前用户 6 个项目 + 其他用户 1 个项目"""
    return [
        _build_seed_project(
            PROJECT_XIUZHEN_WORLD, TEST_USER_ID, "修真世界", "玄幻", "novel",
            updated_at=datetime(2026, 1, 3, 12, 0, 0),
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        ),
        _build_seed_project(
            PROJECT_CITY_ROMANCE, TEST_USER_ID, "都市爱情故事", "言情", "novel",
            updated_at=datetime(2026, 1, 2, 12, 0, 0),
            created_at=datetime(2026, 1, 2, 12, 0, 0),
        ),
        _build_seed_project(
            PROJECT_STAR_TREK, TEST_USER_ID, "星际迷航之旅", "科幻", "series_script",
            updated_at=datetime(2026, 1, 1, 12, 0, 0),
            created_at=datetime(2026, 1, 3, 12, 0, 0),
        ),
        _build_seed_project(
            PROJECT_ALPHA_PLAN, TEST_USER_ID, "Alpha计划", "硬核修真", "movie_script",
            updated_at=datetime(2026, 1, 4, 12, 0, 0),
            created_at=datetime(2026, 1, 4, 12, 0, 0),
        ),
        # 105/106 共享同一 updated_at：验证 ID 次级排序稳定性
        _build_seed_project(
            PROJECT_UNDERSCORE_NAME, TEST_USER_ID, "A_B测试项目", "实验", "novel",
            updated_at=datetime(2026, 1, 5, 12, 0, 0),
            created_at=datetime(2026, 1, 5, 12, 0, 0),
        ),
        _build_seed_project(
            PROJECT_WILDCARD_DECOY, TEST_USER_ID, "AxB对照组", "实验", "novel",
            updated_at=datetime(2026, 1, 5, 12, 0, 0),
            created_at=datetime(2026, 1, 5, 13, 0, 0),
        ),
        _build_seed_project(
            PROJECT_OTHER_USER, OTHER_USER_ID, "修真世界外传", "玄幻", "novel",
            updated_at=datetime(2026, 1, 6, 12, 0, 0),
            created_at=datetime(2026, 1, 6, 12, 0, 0),
        ),
    ]


CURRENT_USER_PROJECT_IDS = {
    PROJECT_XIUZHEN_WORLD, PROJECT_CITY_ROMANCE, PROJECT_STAR_TREK,
    PROJECT_ALPHA_PLAN, PROJECT_UNDERSCORE_NAME, PROJECT_WILDCARD_DECOY,
}


@pytest_asyncio.fixture
async def api_client():
    """内存 SQLite + 真实 novel_writer 路由 + 依赖覆盖的 HTTP 客户端"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add(User(
            id=TEST_USER_ID, username="tester",
            email="tester@example.com", hashed_password="hashed",
        ))
        session.add(User(
            id=OTHER_USER_ID, username="other",
            email="other@example.com", hashed_password="hashed",
        ))
        for project in _seed_projects():
            session.add(project)
        await session.commit()

    test_app = FastAPI()
    test_app.include_router(novel_writer.router, prefix="/api/v1")

    async def override_get_db():
        async with session_factory() as session:
            yield session

    def override_get_current_user():
        return User(
            id=TEST_USER_ID, username="tester",
            email="tester@example.com", hashed_password="hashed",
        )

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = override_get_current_user

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await engine.dispose()


def _item_ids(payload: dict) -> list:
    """从响应载荷中提取项目 ID 列表（保持顺序）"""
    return [item["id"] for item in payload["data"]["items"]]


class TestProjectListSearch:
    """搜索行为：命中范围、空白处理、转义与大小写"""

    async def test_search_hits_project_title_only(self, api_client):
        response = await api_client.get(PROJECTS_URL, params={"search": "世界"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["data"]["total"] == 1
        assert _item_ids(payload) == [PROJECT_XIUZHEN_WORLD]

    async def test_search_hits_genre_field(self, api_client):
        response = await api_client.get(PROJECTS_URL, params={"search": "硬核"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["data"]["total"] == 1
        assert _item_ids(payload) == [PROJECT_ALPHA_PLAN]

    async def test_chinese_search_matches_title_and_genre_together(self, api_client):
        response = await api_client.get(PROJECTS_URL, params={"search": "修真"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["data"]["total"] == 2
        assert set(_item_ids(payload)) == {PROJECT_XIUZHEN_WORLD, PROJECT_ALPHA_PLAN}

    async def test_blank_search_returns_all_projects(self, api_client):
        response = await api_client.get(PROJECTS_URL, params={"search": "   "})
        assert response.status_code == 200
        payload = response.json()
        assert payload["data"]["total"] == len(CURRENT_USER_PROJECT_IDS)
        assert set(_item_ids(payload)) == CURRENT_USER_PROJECT_IDS

    async def test_search_is_case_insensitive(self, api_client):
        response = await api_client.get(PROJECTS_URL, params={"search": "alpha"})
        assert response.status_code == 200
        payload = response.json()
        assert _item_ids(payload) == [PROJECT_ALPHA_PLAN]

    async def test_search_escapes_like_underscore_wildcard(self, api_client):
        # A_B 中的下划线若未转义，将同时误命中「AxB对照组」
        response = await api_client.get(PROJECTS_URL, params={"search": "A_B"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["data"]["total"] == 1
        assert _item_ids(payload) == [PROJECT_UNDERSCORE_NAME]

    async def test_search_escapes_percent_wildcard(self, api_client):
        # 「%」若未转义等于匹配所有记录
        response = await api_client.get(PROJECTS_URL, params={"search": "%"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["data"]["total"] == 0

    async def test_search_longer_than_limit_returns_422(self, api_client):
        response = await api_client.get(
            PROJECTS_URL, params={"search": "长" * 101}
        )
        assert response.status_code == 422

    async def test_other_user_projects_are_isolated(self, api_client):
        response = await api_client.get(PROJECTS_URL, params={"search": "外传"})
        assert response.status_code == 200
        assert response.json()["data"]["total"] == 0


class TestProjectListSorting:
    """排序行为：白名单校验、升降序、稳定次级排序"""

    async def test_invalid_sort_by_returns_422(self, api_client):
        response = await api_client.get(
            PROJECTS_URL, params={"sort_by": "id; DROP TABLE novel_projects"}
        )
        assert response.status_code == 422

    async def test_invalid_sort_order_returns_422(self, api_client):
        response = await api_client.get(
            PROJECTS_URL, params={"sort_order": "random"}
        )
        assert response.status_code == 422

    async def test_sort_by_title_ascending_and_descending_are_reversed(self, api_client):
        asc_response = await api_client.get(
            PROJECTS_URL, params={"sort_by": "title", "sort_order": "asc"}
        )
        desc_response = await api_client.get(
            PROJECTS_URL, params={"sort_by": "title", "sort_order": "desc"}
        )
        assert asc_response.status_code == 200
        assert desc_response.status_code == 200
        asc_ids = _item_ids(asc_response.json())
        desc_ids = _item_ids(desc_response.json())
        assert len(asc_ids) == len(CURRENT_USER_PROJECT_IDS)
        assert asc_ids == list(reversed(desc_ids))

    async def test_sort_by_created_at_ascending(self, api_client):
        response = await api_client.get(
            PROJECTS_URL, params={"sort_by": "created_at", "sort_order": "asc"}
        )
        assert response.status_code == 200
        assert _item_ids(response.json()) == [
            PROJECT_XIUZHEN_WORLD, PROJECT_CITY_ROMANCE, PROJECT_STAR_TREK,
            PROJECT_ALPHA_PLAN, PROJECT_UNDERSCORE_NAME, PROJECT_WILDCARD_DECOY,
        ]

    async def test_same_updated_at_uses_stable_id_secondary_sort(self, api_client):
        # 105/106 updated_at 相同：desc 时 id 大者(106)在前，整体顺序完全确定
        response = await api_client.get(
            PROJECTS_URL, params={"sort_by": "updated_at", "sort_order": "desc"}
        )
        assert response.status_code == 200
        assert _item_ids(response.json()) == [
            PROJECT_WILDCARD_DECOY, PROJECT_UNDERSCORE_NAME, PROJECT_ALPHA_PLAN,
            PROJECT_XIUZHEN_WORLD, PROJECT_CITY_ROMANCE, PROJECT_STAR_TREK,
        ]


class TestProjectListFilterAndPagination:
    """筛选组合与分页总数一致性"""

    async def test_content_type_filter_combined_with_search(self, api_client):
        response = await api_client.get(
            PROJECTS_URL, params={"content_type": "novel", "search": "修真"}
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["data"]["total"] == 1
        assert _item_ids(payload) == [PROJECT_XIUZHEN_WORLD]

    async def test_pagination_total_matches_and_pages_do_not_overlap(self, api_client):
        page_size = 2
        collected_ids = []
        total_values = set()
        for page in (1, 2, 3):
            response = await api_client.get(
                PROJECTS_URL,
                params={
                    "page": page, "page_size": page_size,
                    "sort_by": "updated_at", "sort_order": "desc",
                },
            )
            assert response.status_code == 200
            payload = response.json()
            total_values.add(payload["data"]["total"])
            page_ids = _item_ids(payload)
            assert len(page_ids) == page_size
            collected_ids.extend(page_ids)

        # 各页总数一致、无重复、并集恰为全部项目
        assert total_values == {len(CURRENT_USER_PROJECT_IDS)}
        assert len(collected_ids) == len(set(collected_ids))
        assert set(collected_ids) == CURRENT_USER_PROJECT_IDS

    async def test_search_pagination_total_is_filtered_count(self, api_client):
        response = await api_client.get(
            PROJECTS_URL,
            params={"search": "修真", "page": 1, "page_size": 1},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["data"]["total"] == 2
        assert len(payload["data"]["items"]) == 1
