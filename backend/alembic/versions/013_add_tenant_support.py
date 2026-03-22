"""add tenant and multi tenant support

Revision ID: 013_add_tenant_support
Revises: 012_add_compliance_config
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '013_add_tenant_support'
down_revision = '012_add_compliance_config'
branch_labels = None
depends_on = None


def upgrade():
    # 1. 创建租户表
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False, comment='租户名称'),
        sa.Column('slug', sa.String(50), nullable=False, comment='租户标识'),
        sa.Column('logo', sa.String(255), nullable=True, comment='租户Logo URL'),
        sa.Column('contact_name', sa.String(50), nullable=True, comment='联系人姓名'),
        sa.Column('contact_email', sa.String(100), nullable=False, comment='联系邮箱'),
        sa.Column('contact_phone', sa.String(20), nullable=True, comment='联系电话'),
        sa.Column('plan', sa.Enum('free', 'basic', 'pro', 'enterprise', name='tenantplan'), 
                  nullable=False, server_default='free', comment='套餐类型'),
        sa.Column('status', sa.Enum('trial', 'active', 'suspended', 'expired', name='tenantstatus'), 
                  nullable=False, server_default='trial', comment='租户状态'),
        sa.Column('max_users', sa.Integer(), nullable=True, server_default='5', comment='最大用户数'),
        sa.Column('max_projects', sa.Integer(), nullable=True, server_default='10', comment='最大项目数'),
        sa.Column('max_storage_mb', sa.Integer(), nullable=True, server_default='1024', comment='最大存储空间'),
        sa.Column('max_api_calls_per_day', sa.Integer(), nullable=True, server_default='1000', comment='每日API调用上限'),
        sa.Column('current_users', sa.Integer(), nullable=True, server_default='0', comment='当前用户数'),
        sa.Column('current_projects', sa.Integer(), nullable=True, server_default='0', comment='当前项目数'),
        sa.Column('current_storage_mb', sa.Integer(), nullable=True, server_default='0', comment='当前存储使用'),
        sa.Column('api_calls_today', sa.Integer(), nullable=True, server_default='0', comment='今日API调用数'),
        sa.Column('api_calls_total', sa.Integer(), nullable=True, server_default='0', comment='总API调用数'),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True, comment='试用结束时间'),
        sa.Column('subscription_ends_at', sa.DateTime(), nullable=True, comment='订阅结束时间'),
        sa.Column('last_active_at', sa.DateTime(), nullable=True, comment='最后活跃时间'),
        sa.Column('settings', sa.Text(), nullable=True, comment='租户自定义配置'),
        sa.Column('custom_domain', sa.String(100), nullable=True, comment='自定义域名'),
        sa.Column('features_enabled', sa.Text(), nullable=True, comment='启用的功能列表'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenants_name'), 'tenants', ['name'], unique=True)
    op.create_index(op.f('ix_tenants_slug'), 'tenants', ['slug'], unique=True)

    # 2. 创建操作日志表
    op.create_table(
        'operation_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True, comment='操作用户ID'),
        sa.Column('username', sa.String(50), nullable=True, comment='操作用户名'),
        sa.Column('tenant_id', sa.Integer(), nullable=True, comment='租户ID'),
        sa.Column('action', sa.String(50), nullable=False, comment='操作类型'),
        sa.Column('module', sa.String(50), nullable=True, comment='操作模块'),
        sa.Column('description', sa.Text(), nullable=True, comment='操作描述'),
        sa.Column('request_method', sa.String(10), nullable=True, comment='请求方法'),
        sa.Column('request_path', sa.String(255), nullable=True, comment='请求路径'),
        sa.Column('request_params', sa.Text(), nullable=True, comment='请求参数'),
        sa.Column('request_body', sa.Text(), nullable=True, comment='请求体'),
        sa.Column('response_status', sa.Integer(), nullable=True, comment='响应状态码'),
        sa.Column('response_time_ms', sa.Integer(), nullable=True, comment='响应时间'),
        sa.Column('ip_address', sa.String(50), nullable=True, comment='IP地址'),
        sa.Column('user_agent', sa.String(255), nullable=True, comment='用户代理'),
        sa.Column('resource_type', sa.String(50), nullable=True, comment='资源类型'),
        sa.Column('resource_id', sa.Integer(), nullable=True, comment='资源ID'),
        sa.Column('extra_data', sa.JSON(), nullable=True, comment='额外数据'),
        sa.Column('status', sa.String(20), nullable=True, server_default='success', comment='操作状态'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_operation_logs_user_id'), 'operation_logs', ['user_id'])
    op.create_index(op.f('ix_operation_logs_tenant_id'), 'operation_logs', ['tenant_id'])
    op.create_index(op.f('ix_operation_logs_action'), 'operation_logs', ['action'])
    op.create_index(op.f('ix_operation_logs_created_at'), 'operation_logs', ['created_at'])
    op.create_index('ix_operation_logs_tenant_created', 'operation_logs', ['tenant_id', 'created_at'])
    op.create_index('ix_operation_logs_user_created', 'operation_logs', ['user_id', 'created_at'])

    # 3. 为用户表添加租户字段
    op.add_column('users', sa.Column('tenant_id', sa.Integer(), nullable=True, comment='租户ID'))
    op.create_foreign_key('fk_users_tenant', 'users', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'])
    
    # 添加新用户字段
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=True, server_default='0', comment='邮箱是否已验证'))
    op.add_column('users', sa.Column('phone', sa.String(20), nullable=True, comment='手机号'))
    op.add_column('users', sa.Column('last_login_at', sa.String(30), nullable=True, comment='最后登录时间'))
    op.add_column('users', sa.Column('last_login_ip', sa.String(50), nullable=True, comment='最后登录IP'))
    op.add_column('users', sa.Column('login_count', sa.Integer(), nullable=True, server_default='0', comment='登录次数'))

    # 4. 为其他业务表添加租户字段
    # 小说项目表
    op.add_column('novel_projects', sa.Column('tenant_id', sa.Integer(), nullable=True, comment='租户ID'))
    op.create_index(op.f('ix_novel_projects_tenant_id'), 'novel_projects', ['tenant_id'])
    
    # 知识库表
    op.add_column('knowledge_bases', sa.Column('tenant_id', sa.Integer(), nullable=True, comment='租户ID'))
    op.create_index(op.f('ix_knowledge_bases_tenant_id'), 'knowledge_bases', ['tenant_id'])
    
    # 生成记录表
    op.add_column('generations', sa.Column('tenant_id', sa.Integer(), nullable=True, comment='租户ID'))
    op.create_index(op.f('ix_generations_tenant_id'), 'generations', ['tenant_id'])
    
    # API Key表
    op.add_column('user_api_keys', sa.Column('tenant_id', sa.Integer(), nullable=True, comment='租户ID'))
    op.create_index(op.f('ix_user_api_keys_tenant_id'), 'user_api_keys', ['tenant_id'])

    # 5. 创建默认租户（用于迁移现有数据）
    op.execute("""
        INSERT INTO tenants (name, slug, contact_email, plan, status, max_users, max_projects, max_storage_mb, max_api_calls_per_day)
        VALUES ('默认租户', 'default', 'admin@localhost', 'enterprise', 'active', -1, -1, -1, -1)
    """)
    
    # 6. 将现有用户关联到默认租户
    op.execute("""
        UPDATE users SET tenant_id = 1 WHERE tenant_id IS NULL
    """)
    
    # 7. 更新其他业务表的租户ID
    op.execute("""
        UPDATE novel_projects SET tenant_id = 1 WHERE tenant_id IS NULL
    """)
    op.execute("""
        UPDATE knowledge_bases SET tenant_id = 1 WHERE tenant_id IS NULL
    """)
    op.execute("""
        UPDATE generations SET tenant_id = 1 WHERE tenant_id IS NULL
    """)
    op.execute("""
        UPDATE user_api_keys SET tenant_id = 1 WHERE tenant_id IS NULL
    """)


def downgrade():
    # 移除租户字段
    op.drop_index(op.f('ix_user_api_keys_tenant_id'), 'user_api_keys')
    op.drop_column('user_api_keys', 'tenant_id')
    
    op.drop_index(op.f('ix_generations_tenant_id'), 'generations')
    op.drop_column('generations', 'tenant_id')
    
    op.drop_index(op.f('ix_knowledge_bases_tenant_id'), 'knowledge_bases')
    op.drop_column('knowledge_bases', 'tenant_id')
    
    op.drop_index(op.f('ix_novel_projects_tenant_id'), 'novel_projects')
    op.drop_column('novel_projects', 'tenant_id')
    
    # 移除用户表新字段
    op.drop_index(op.f('ix_users_tenant_id'), 'users')
    op.drop_constraint('fk_users_tenant', 'users', type_='foreignkey')
    op.drop_column('users', 'tenant_id')
    op.drop_column('users', 'is_verified')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'last_login_ip')
    op.drop_column('users', 'login_count')
    
    # 删除操作日志表
    op.drop_index('ix_operation_logs_user_created', 'operation_logs')
    op.drop_index('ix_operation_logs_tenant_created', 'operation_logs')
    op.drop_index(op.f('ix_operation_logs_created_at'), 'operation_logs')
    op.drop_index(op.f('ix_operation_logs_action'), 'operation_logs')
    op.drop_index(op.f('ix_operation_logs_tenant_id'), 'operation_logs')
    op.drop_index(op.f('ix_operation_logs_user_id'), 'operation_logs')
    op.drop_table('operation_logs')
    
    # 删除租户表
    op.drop_index(op.f('ix_tenants_slug'), 'tenants')
    op.drop_index(op.f('ix_tenants_name'), 'tenants')
    op.drop_table('tenants')
