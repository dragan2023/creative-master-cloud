"""KnowledgeBaseService 单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.knowledge_base_service import KnowledgeBaseService
from app.models import KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory, User, UserRole
from app.core.exceptions import ResourceNotFoundException, ValidationException, AuthorizationException


class TestKnowledgeBaseService:
    """KnowledgeBaseService 单元测试（使用Mock数据库）"""
    
    def setup_method(self):
        """每个测试前创建mock db session"""
        self.mock_db = AsyncMock()
        self.service = KnowledgeBaseService(self.mock_db)
    
    def _create_mock_kb(self, kb_id=1, user_id=1, status=KnowledgeBaseStatus.READY):
        """创建 mock 知识库对象"""
        kb = MagicMock(spec=KnowledgeBase)
        kb.id = kb_id
        kb.user_id = user_id
        kb.name = "测试知识库"
        kb.status = status
        kb.category = KnowledgeBaseCategory.GENERAL
        kb.document_count = 10
        return kb
    
    def _create_mock_user(self, user_id=1, is_admin=False, role=UserRole.USER):
        """创建 mock 用户对象"""
        user = MagicMock(spec=User)
        user.id = user_id
        user.is_admin = is_admin
        user.role = role
        return user
    
    @pytest.mark.asyncio
    async def test_create_knowledge_base(self):
        """测试创建知识库"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.create_knowledge_base(
            user_id=1,
            name="测试知识库",
            description="测试描述",
            category=KnowledgeBaseCategory.GENERAL,
            file_path="/data/test.pdf",
            file_type="pdf",
            file_size=1024,
            collection_name="test_collection",
        )
        
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
        
        assert result.user_id == 1
        assert result.name == "测试知识库"
        assert result.status == KnowledgeBaseStatus.PROCESSING
    
    @pytest.mark.asyncio
    async def test_create_knowledge_base_with_type(self):
        """测试创建知识库（指定类型）"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.create_knowledge_base(
            user_id=1,
            name="永久知识库",
            description="永久存储",
            category=KnowledgeBaseCategory.MANUAL,
            file_path="/data/manual.pdf",
            file_type="pdf",
            file_size=2048,
            collection_name="manual_collection",
            kb_type=KnowledgeBaseType.STATIC,
        )
        
        assert result.type == KnowledgeBaseType.STATIC
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base_by_id_found(self):
        """测试根据ID获取知识库（存在）"""
        mock_kb = self._create_mock_kb()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_knowledge_base_by_id(1)
        
        assert result is not None
        assert result.id == 1
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base_by_id_not_found(self):
        """测试根据ID获取知识库（不存在）"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_knowledge_base_by_id(999)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base_by_id_with_user_id(self):
        """测试根据ID获取知识库（带用户ID过滤）"""
        mock_kb = self._create_mock_kb(user_id=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_knowledge_base_by_id(1, user_id=1)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base_or_404_found(self):
        """测试获取知识库或404（存在）"""
        mock_kb = self._create_mock_kb()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_knowledge_base_or_404(1)
        
        assert result.id == 1
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base_or_404_not_found(self):
        """测试获取知识库或404（不存在）"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_result
        
        with pytest.raises(ResourceNotFoundException):
            await self.service.get_knowledge_base_or_404(999)
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base_with_permission_check_owner(self):
        """测试获取知识库并检查权限（所有者）"""
        mock_kb = self._create_mock_kb(user_id=1)
        mock_user = self._create_mock_user(user_id=1, is_admin=False)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_knowledge_base_with_permission_check(1, mock_user)
        
        assert result.id == 1
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base_with_permission_check_admin(self):
        """测试获取知识库并检查权限（管理员）"""
        mock_kb = self._create_mock_kb(user_id=2)  # 其他用户的知识库
        mock_user = self._create_mock_user(user_id=1, is_admin=True, role=UserRole.SUPER_ADMIN)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_knowledge_base_with_permission_check(1, mock_user)
        
        assert result.id == 1
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base_with_permission_check_forbidden(self):
        """测试获取知识库并检查权限（无权限）"""
        mock_kb = self._create_mock_kb(user_id=2)  # 其他用户的知识库
        mock_user = self._create_mock_user(user_id=1, is_admin=False)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        
        with pytest.raises(AuthorizationException):
            await self.service.get_knowledge_base_with_permission_check(1, mock_user)
    
    @pytest.mark.asyncio
    async def test_get_knowledge_base_with_permission_check_not_found(self):
        """测试获取知识库并检查权限（不存在）"""
        mock_user = self._create_mock_user()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_result
        
        with pytest.raises(ResourceNotFoundException):
            await self.service.get_knowledge_base_with_permission_check(999, mock_user)
    
    @pytest.mark.asyncio
    async def test_list_knowledge_bases(self):
        """测试获取知识库列表"""
        mock_kbs = [
            self._create_mock_kb(kb_id=1),
            self._create_mock_kb(kb_id=2),
        ]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_kbs
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_knowledge_bases(user_id=1)
        
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_list_knowledge_bases_with_category(self):
        """测试获取知识库列表（带分类过滤）"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_knowledge_bases(
            user_id=1, 
            category=KnowledgeBaseCategory.GENERAL.value
        )
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_list_knowledge_bases_rejects_unknown_category(self):
        """Unknown category must not silently return all knowledge bases."""
        with pytest.raises(ValidationException):
            await self.service.list_knowledge_bases(
                user_id=1,
                category="movie-outline"
            )
    
    @pytest.mark.asyncio
    async def test_update_knowledge_base(self):
        """测试更新知识库"""
        mock_kb = self._create_mock_kb()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        
        result = await self.service.update_knowledge_base(
            kb_id=1,
            user_id=1,
            name="新名称",
            description="新描述"
        )
        
        assert result.name == "新名称"
        assert result.description == "新描述"
    
    @pytest.mark.asyncio
    async def test_update_knowledge_base_status(self):
        """测试更新知识库状态"""
        mock_kb = self._create_mock_kb(status=KnowledgeBaseStatus.PROCESSING)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        self.mock_db.commit = AsyncMock()
        
        result = await self.service.update_knowledge_base_status(
            kb_id=1,
            status=KnowledgeBaseStatus.READY
        )
        
        assert result.status == KnowledgeBaseStatus.READY
    
    @pytest.mark.asyncio
    async def test_update_document_count(self):
        """测试更新文档数量"""
        mock_kb = self._create_mock_kb()
        mock_kb.document_count = 5
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        self.mock_db.commit = AsyncMock()
        
        result = await self.service.update_document_count(1, 20)
        
        assert result.document_count == 20
    
    @pytest.mark.asyncio
    async def test_delete_knowledge_base(self):
        """测试删除知识库"""
        mock_kb = self._create_mock_kb()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        self.mock_db.delete = AsyncMock()
        self.mock_db.commit = AsyncMock()
        
        result = await self.service.delete_knowledge_base(1, user_id=1)
        
        assert result is True
        self.mock_db.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_knowledge_base_not_found(self):
        """测试删除知识库（不存在）"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_result
        
        with pytest.raises(ResourceNotFoundException):
            await self.service.delete_knowledge_base(999, user_id=1)
    
    @pytest.mark.asyncio
    async def test_check_kb_ready_success(self):
        """测试检查知识库就绪状态（成功）"""
        mock_kb = self._create_mock_kb(status=KnowledgeBaseStatus.READY)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.check_kb_ready(1)
        
        assert result.status == KnowledgeBaseStatus.READY
    
    @pytest.mark.asyncio
    async def test_check_kb_ready_not_ready(self):
        """测试检查知识库就绪状态（未就绪）"""
        mock_kb = self._create_mock_kb(status=KnowledgeBaseStatus.PROCESSING)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        
        with pytest.raises(ValidationException):
            await self.service.check_kb_ready(1)
    
    @pytest.mark.asyncio
    async def test_check_kb_processing_success(self):
        """测试检查知识库处理中状态（成功）"""
        mock_kb = self._create_mock_kb(status=KnowledgeBaseStatus.PROCESSING)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.check_kb_processing(1)
        
        assert result.status == KnowledgeBaseStatus.PROCESSING
    
    @pytest.mark.asyncio
    async def test_check_kb_processing_not_processing(self):
        """测试检查知识库处理中状态（非处理中）"""
        mock_kb = self._create_mock_kb(status=KnowledgeBaseStatus.READY)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        self.mock_db.execute.return_value = mock_result
        
        with pytest.raises(ValidationException):
            await self.service.check_kb_processing(1)
    
    @pytest.mark.asyncio
    async def test_check_kb_ownership_or_admin_owner(self):
        """测试检查知识库所有权（所有者）"""
        mock_kb = self._create_mock_kb(user_id=1)
        mock_user = self._create_mock_user(user_id=1)
        
        # 不应抛出异常
        await self.service.check_kb_ownership_or_admin(mock_kb, mock_user)
    
    @pytest.mark.asyncio
    async def test_check_kb_ownership_or_admin_admin(self):
        """测试检查知识库所有权（管理员）"""
        mock_kb = self._create_mock_kb(user_id=2)
        mock_user = self._create_mock_user(user_id=1, role=UserRole.SUPER_ADMIN)
        
        # 不应抛出异常
        await self.service.check_kb_ownership_or_admin(mock_kb, mock_user)
    
    @pytest.mark.asyncio
    async def test_check_kb_ownership_or_admin_forbidden(self):
        """测试检查知识库所有权（无权限）"""
        mock_kb = self._create_mock_kb(user_id=2)
        mock_user = self._create_mock_user(user_id=1, role=UserRole.USER)
        
        with pytest.raises(AuthorizationException):
            await self.service.check_kb_ownership_or_admin(mock_kb, mock_user)
    
    @pytest.mark.asyncio
    async def test_get_user_kb_ids(self):
        """测试获取用户知识库ID列表"""
        mock_result = MagicMock()
        mock_result.all.return_value = [(1,), (2,), (3,)]
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_user_kb_ids(user_id=1)
        
        assert result == [1, 2, 3]
    
    @pytest.mark.asyncio
    async def test_get_all_general_knowledge_bases(self):
        """测试获取所有通用知识库"""
        mock_kbs = [self._create_mock_kb(kb_id=i) for i in range(3)]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_kbs
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_all_general_knowledge_bases()
        
        assert len(result) == 3
    
    @pytest.mark.asyncio
    async def test_get_manual_knowledge_bases(self):
        """测试获取官方手册知识库"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_manual_knowledge_bases()
        
        assert result == []
