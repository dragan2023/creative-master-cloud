"""GenerationService 单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.generation_service import GenerationService
from app.models.generation import Generation, GenerationModule, GenerationStatus


class TestGenerationService:
    """GenerationService 单元测试（使用Mock数据库）"""
    
    def setup_method(self):
        """每个测试前创建mock db session"""
        self.mock_db = AsyncMock()
        self.service = GenerationService(self.mock_db)
    
    @pytest.mark.asyncio
    async def test_save_generation(self):
        """测试保存生成记录"""
        # 配置 mock
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        # 调用方法
        result = await self.service.save_generation(
            user_id=1,
            module=GenerationModule.SHORT_VIDEO,
            input_params={"topic": "测试"},
            title="测试标题",
            output_content="测试内容",
        )
        
        # 验证调用
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
        
        # 验证返回的对象
        assert result.user_id == 1
        assert result.module == GenerationModule.SHORT_VIDEO
        assert result.title == "测试标题"
        assert result.output_content == "测试内容"
    
    @pytest.mark.asyncio
    async def test_save_generation_with_all_params(self):
        """测试保存生成记录（完整参数）"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.save_generation(
            user_id=1,
            module=GenerationModule.NOVEL,
            input_params={"theme": "科幻"},
            title="科幻小说",
            output_content="小说内容",
            provider="openai",
            model_name="gpt-4",
            token_count=500,
            duration_ms=3000,
            status=GenerationStatus.COMPLETED,
        )
        
        assert result.provider == "openai"
        assert result.model_name == "gpt-4"
        assert result.token_count == 500
        assert result.duration_ms == 3000
        assert result.status == GenerationStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_get_generation_by_id_found(self):
        """测试根据ID获取生成记录（存在）"""
        # 创建 mock 结果
        mock_generation = Generation()
        mock_generation.id = 1
        mock_generation.title = "测试记录"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_generation
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_generation_by_id(1)
        
        assert result is not None
        assert result.id == 1
        assert result.title == "测试记录"
    
    @pytest.mark.asyncio
    async def test_get_generation_by_id_not_found(self):
        """测试根据ID获取生成记录（不存在）"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_generation_by_id(999)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_generations(self):
        """测试获取用户生成历史"""
        # 创建 mock 数据
        mock_generations = [
            MagicMock(spec=Generation, id=1, title="记录1"),
            MagicMock(spec=Generation, id=2, title="记录2"),
        ]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_generations
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_user_generations(user_id=1)
        
        assert len(result) == 2
        assert result[0].id == 1
    
    @pytest.mark.asyncio
    async def test_get_user_generations_with_module_filter(self):
        """测试获取用户生成历史（带模块过滤）"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_user_generations(
            user_id=1, 
            module=GenerationModule.NOVEL
        )
        
        assert result == []
        # 验证 execute 被调用
        self.mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_generations_with_pagination(self):
        """测试获取用户生成历史（分页）"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_user_generations(
            user_id=1,
            skip=10,
            limit=20
        )
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_count_user_generations(self):
        """测试统计用户生成记录数"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        self.mock_db.execute.return_value = mock_result
        
        count = await self.service.count_user_generations(user_id=1)
        
        assert count == 42
    
    @pytest.mark.asyncio
    async def test_count_user_generations_zero(self):
        """测试统计用户生成记录数（零）"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        self.mock_db.execute.return_value = mock_result
        
        count = await self.service.count_user_generations(user_id=999)
        
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_count_user_generations_with_module_filter(self):
        """测试统计用户生成记录数（带模块过滤）"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        self.mock_db.execute.return_value = mock_result
        
        count = await self.service.count_user_generations(
            user_id=1, 
            module=GenerationModule.NOVEL
        )
        
        assert count == 10
    
    @pytest.mark.asyncio
    async def test_delete_generation_success(self):
        """测试删除生成记录（成功）"""
        # 创建可删除的 mock generation
        mock_generation = MagicMock(spec=Generation)
        mock_generation.id = 1
        mock_generation.status = GenerationStatus.COMPLETED
        mock_generation.can_delete.return_value = True
        
        # 配置 get_generation_by_id 返回
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_generation
        self.mock_db.execute.return_value = mock_result
        self.mock_db.delete = AsyncMock()
        self.mock_db.commit = AsyncMock()
        
        result = await self.service.delete_generation(1)
        
        assert result is True
        self.mock_db.delete.assert_called_once()
        self.mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_generation_not_found(self):
        """测试删除生成记录（不存在）"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.delete_generation(999)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_generation_cannot_delete(self):
        """测试删除生成记录（不可删除状态）"""
        # 创建不可删除的 mock generation
        mock_generation = MagicMock(spec=Generation)
        mock_generation.id = 1
        mock_generation.status = GenerationStatus.PROCESSING
        mock_generation.can_delete.return_value = False
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_generation
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.delete_generation(1)
        
        assert result is False
