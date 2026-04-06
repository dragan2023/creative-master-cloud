"""UserActionService 单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.user_action_service import UserActionService
from app.models.user_action import UserAction, ActionType


class TestUserActionService:
    """UserActionService 单元测试（使用Mock数据库）"""
    
    def setup_method(self):
        """每个测试前创建mock db session"""
        self.mock_db = AsyncMock()
        self.service = UserActionService(self.mock_db)
    
    @pytest.mark.asyncio
    async def test_track_action_copy(self):
        """测试记录用户行为（复制）"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.track_action(
            user_id=1,
            generation_id=100,
            module="novel",
            action="copy",
            content_snippet="测试内容片段"
        )
        
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
        
        assert result.user_id == 1
        assert result.generation_id == 100
        assert result.module == "novel"
        assert result.action == ActionType.COPY
    
    @pytest.mark.asyncio
    async def test_track_action_download(self):
        """测试记录用户行为（下载）"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.track_action(
            user_id=1,
            generation_id=100,
            module="short_video",
            action="download"
        )
        
        assert result.action == ActionType.DOWNLOAD
    
    @pytest.mark.asyncio
    async def test_track_action_regenerate(self):
        """测试记录用户行为（重新生成）"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.track_action(
            user_id=1,
            generation_id=100,
            module="script",
            action="regenerate"
        )
        
        assert result.action == ActionType.REGENERATE
    
    @pytest.mark.asyncio
    async def test_track_action_like(self):
        """测试记录用户行为（点赞/收藏）"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.track_action(
            user_id=1,
            generation_id=100,
            module="tvc",
            action="like"
        )
        
        assert result.action == ActionType.LIKE
    
    @pytest.mark.asyncio
    async def test_track_action_share(self):
        """测试记录用户行为（分享）"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.track_action(
            user_id=1,
            generation_id=100,
            module="print_ad",
            action="share"
        )
        
        assert result.action == ActionType.SHARE
    
    @pytest.mark.asyncio
    async def test_track_action_invalid_action_defaults_to_copy(self):
        """测试记录用户行为（无效行为类型默认为复制）"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.track_action(
            user_id=1,
            generation_id=100,
            module="novel",
            action="invalid_action"
        )
        
        # 无效行为应默认为 COPY
        assert result.action == ActionType.COPY
    
    @pytest.mark.asyncio
    async def test_track_action_with_content_snippet(self):
        """测试记录用户行为（带内容片段）"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        content_snippet = "这是内容的开头部分..."
        result = await self.service.track_action(
            user_id=1,
            generation_id=100,
            module="novel",
            action="copy",
            content_snippet=content_snippet
        )
        
        assert result.content_snippet == content_snippet
    
    @pytest.mark.asyncio
    async def test_track_action_without_content_snippet(self):
        """测试记录用户行为（无内容片段）"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.track_action(
            user_id=1,
            generation_id=100,
            module="novel",
            action="copy"
        )
        
        assert result.content_snippet is None
