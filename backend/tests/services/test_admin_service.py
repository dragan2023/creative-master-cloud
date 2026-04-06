"""AdminService 单元测试"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from app.services.admin_service import AdminService
from app.models import User, Tenant, OperationLog, NovelProject, Generation
from app.models.user import UserRole


class TestAdminService:
    """AdminService 单元测试（使用Mock数据库）"""
    
    def setup_method(self):
        """每个测试前创建mock db session"""
        self.mock_db = AsyncMock()
        self.service = AdminService(self.mock_db)
    
    def _create_mock_user(self, user_id=1, username="testuser", tenant_id=None, is_active=True, role=UserRole.USER):
        """创建 mock 用户对象"""
        user = MagicMock(spec=User)
        user.id = user_id
        user.username = username
        user.email = f"{username}@test.com"
        user.tenant_id = tenant_id
        user.is_active = is_active
        user.role = role
        user.nickname = username
        user.created_at = datetime.utcnow()
        user.last_login_at = datetime.utcnow()
        return user
    
    def _create_mock_tenant(self, tenant_id=1, name="测试租户"):
        """创建 mock 租户对象"""
        tenant = MagicMock(spec=Tenant)
        tenant.id = tenant_id
        tenant.name = name
        tenant.slug = name.lower().replace(" ", "-")
        tenant.status = "active"
        tenant.plan = "free"
        tenant.max_users = 10
        tenant.max_projects = 10
        tenant.max_storage_mb = 1024
        tenant.created_at = datetime.utcnow()
        return tenant
    
    # ==================== 用户管理测试 ====================
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self):
        """测试根据ID获取用户（存在）"""
        mock_user = self._create_mock_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_user_by_id(1)
        
        assert result is not None
        assert result.id == 1
        assert result.username == "testuser"
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self):
        """测试根据ID获取用户（不存在）"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_user_by_id(999)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_with_tenant_name(self):
        """测试获取用户及其租户名称"""
        mock_user = self._create_mock_user(tenant_id=1)
        
        # Mock get_user_by_id
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        # Mock get_tenant_name_by_id
        mock_tenant_result = MagicMock()
        mock_tenant_result.scalar.return_value = "测试租户"
        
        self.mock_db.execute.side_effect = [mock_user_result, mock_tenant_result]
        
        user, tenant_name = await self.service.get_user_with_tenant_name(1)
        
        assert user is not None
        assert tenant_name == "测试租户"
    
    @pytest.mark.asyncio
    async def test_get_user_with_tenant_name_no_tenant(self):
        """测试获取用户及其租户名称（无租户）"""
        mock_user = self._create_mock_user(tenant_id=None)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        self.mock_db.execute.return_value = mock_result
        
        user, tenant_name = await self.service.get_user_with_tenant_name(1)
        
        assert user is not None
        assert tenant_name is None
    
    @pytest.mark.asyncio
    async def test_get_user_with_tenant_name_not_found(self):
        """测试获取用户及其租户名称（用户不存在）"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_result
        
        user, tenant_name = await self.service.get_user_with_tenant_name(999)
        
        assert user is None
        assert tenant_name is None
    
    @pytest.mark.asyncio
    async def test_get_tenant_name_by_id(self):
        """测试根据ID获取租户名称"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = "测试租户"
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_tenant_name_by_id(1)
        
        assert result == "测试租户"
    
    @pytest.mark.asyncio
    async def test_list_users(self):
        """测试获取用户列表"""
        mock_users = [
            self._create_mock_user(user_id=1, username="user1"),
            self._create_mock_user(user_id=2, username="user2"),
        ]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_users
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_users()
        
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_list_users_with_search(self):
        """测试获取用户列表（带搜索）"""
        mock_users = [self._create_mock_user(username="testuser")]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_users
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_users(search="test")
        
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_list_users_with_tenant_filter(self):
        """测试获取用户列表（租户过滤）"""
        mock_users = [self._create_mock_user(tenant_id=1)]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_users
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_users(tenant_id=1)
        
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_list_users_with_active_filter(self):
        """测试获取用户列表（状态过滤）"""
        mock_users = [self._create_mock_user(is_active=True)]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_users
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_users(is_active=True)
        
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_list_users_tenant_admin(self):
        """测试租户管理员获取用户列表"""
        mock_users = [self._create_mock_user(tenant_id=1)]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_users
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_users(
            admin_tenant_id=1, 
            is_super_admin=False
        )
        
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_update_user(self):
        """测试更新用户"""
        mock_user = self._create_mock_user()
        self.mock_db.commit = AsyncMock()
        
        result = await self.service.update_user(
            user=mock_user,
            is_active=False,
            nickname="新昵称"
        )
        
        assert mock_user.is_active is False
        assert mock_user.nickname == "新昵称"
        self.mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_user_role(self):
        """测试更新用户角色"""
        mock_user = self._create_mock_user()
        self.mock_db.commit = AsyncMock()
        
        result = await self.service.update_user(
            user=mock_user,
            role=UserRole.SUPER_ADMIN
        )
        
        assert mock_user.role == UserRole.SUPER_ADMIN
    
    @pytest.mark.asyncio
    async def test_delete_user(self):
        """测试删除用户"""
        mock_user = self._create_mock_user()
        self.mock_db.delete = AsyncMock()
        self.mock_db.commit = AsyncMock()
        
        await self.service.delete_user(mock_user)
        
        self.mock_db.delete.assert_called_once_with(mock_user)
        self.mock_db.commit.assert_called_once()
    
    # ==================== 租户管理测试 ====================
    
    @pytest.mark.asyncio
    async def test_get_tenant_by_id_found(self):
        """测试根据ID获取租户（存在）"""
        mock_tenant = self._create_mock_tenant()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_tenant_by_id(1)
        
        assert result is not None
        assert result.id == 1
    
    @pytest.mark.asyncio
    async def test_get_tenant_by_id_not_found(self):
        """测试根据ID获取租户（不存在）"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.get_tenant_by_id(999)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_list_tenants(self):
        """测试获取租户列表"""
        mock_tenants = [
            self._create_mock_tenant(tenant_id=1, name="租户1"),
            self._create_mock_tenant(tenant_id=2, name="租户2"),
        ]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_tenants
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_tenants()
        
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_list_tenants_with_search(self):
        """测试获取租户列表（带搜索）"""
        mock_tenants = [self._create_mock_tenant(name="测试租户")]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_tenants
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_tenants(search="测试")
        
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_update_tenant(self):
        """测试更新租户"""
        mock_tenant = self._create_mock_tenant()
        self.mock_db.commit = AsyncMock()
        
        result = await self.service.update_tenant(
            tenant=mock_tenant,
            name="新租户名",
            max_users=100
        )
        
        assert mock_tenant.name == "新租户名"
        assert mock_tenant.max_users == 100
        self.mock_db.commit.assert_called_once()
    
    # ==================== 操作日志测试 ====================
    
    @pytest.mark.asyncio
    async def test_list_operation_logs(self):
        """测试获取操作日志列表"""
        mock_logs = [
            MagicMock(spec=OperationLog, id=1),
            MagicMock(spec=OperationLog, id=2),
        ]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_logs
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_operation_logs()
        
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_list_operation_logs_with_user_filter(self):
        """测试获取操作日志列表（用户过滤）"""
        mock_logs = [MagicMock(spec=OperationLog, user_id=1)]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_logs
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_operation_logs(user_id=1)
        
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_list_operation_logs_tenant_admin(self):
        """测试租户管理员获取操作日志"""
        mock_logs = [MagicMock(spec=OperationLog, tenant_id=1)]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_logs
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.list_operation_logs(
            admin_tenant_id=1,
            is_super_admin=False
        )
        
        assert len(result) == 1
    
    # ==================== 仪表盘统计测试 ====================
    
    @pytest.mark.asyncio
    async def test_get_dashboard_stats(self):
        """测试获取仪表盘统计数据"""
        # Mock scalar calls
        self.mock_db.scalar = AsyncMock(side_effect=[10, 3, 5, 20, 100, 2])
        
        result = await self.service.get_dashboard_stats()
        
        assert result["total_users"] == 10
        assert result["total_tenants"] == 3
        assert result["active_users_today"] == 5
        assert result["total_projects"] == 20
        assert result["total_generations"] == 100
        assert result["new_users_this_week"] == 2
    
    @pytest.mark.asyncio
    async def test_get_dashboard_stats_with_none_values(self):
        """测试获取仪表盘统计数据（None值处理）"""
        # Mock scalar calls returning None
        self.mock_db.scalar = AsyncMock(side_effect=[None, None, None, None, None, None])
        
        result = await self.service.get_dashboard_stats()
        
        assert result["total_users"] == 0
        assert result["total_tenants"] == 0
        assert result["active_users_today"] == 0
        assert result["total_projects"] == 0
        assert result["total_generations"] == 0
        assert result["new_users_this_week"] == 0
    
    # ==================== 系统健康检查测试 ====================
    
    @pytest.mark.asyncio
    async def test_check_database_health_healthy(self):
        """测试数据库健康检查（正常）"""
        mock_result = MagicMock()
        self.mock_db.execute.return_value = mock_result
        
        result = await self.service.check_database_health()
        
        assert result == "healthy"
    
    @pytest.mark.asyncio
    async def test_check_database_health_unhealthy(self):
        """测试数据库健康检查（异常）"""
        self.mock_db.execute.side_effect = Exception("连接失败")
        
        result = await self.service.check_database_health()
        
        assert result == "unhealthy"
