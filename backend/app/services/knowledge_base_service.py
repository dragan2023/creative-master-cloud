"""
知识库服务模块

封装知识库的CRUD操作和业务逻辑。

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from app.core.logger import get_logger
from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    AuthorizationException,
    KnowledgeBaseException,
)
from app.models import (
    User, 
    KnowledgeBase, 
    KnowledgeBaseType, 
    KnowledgeBaseStatus, 
    KnowledgeBaseCategory
)

logger = get_logger("knowledge_base_service")


class KnowledgeBaseService:
    """知识库服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_knowledge_base(
        self,
        user_id: int,
        name: str,
        description: Optional[str],
        category: KnowledgeBaseCategory,
        file_path: str,
        file_type: str,
        file_size: int,
        collection_name: str,
        kb_type: KnowledgeBaseType = KnowledgeBaseType.TEMP
    ) -> KnowledgeBase:
        """
        创建知识库记录
        
        Args:
            user_id: 用户ID
            name: 知识库名称
            description: 描述
            category: 业务板块分类
            file_path: 文件路径
            file_type: 文件类型
            file_size: 文件大小
            collection_name: 集合名称
            kb_type: 知识库类型，默认为 TEMP
            
        Returns:
            创建的知识库对象
        """
        kb = KnowledgeBase(
            user_id=user_id,
            name=name,
            description=description,
            type=kb_type,
            category=category,
            status=KnowledgeBaseStatus.PROCESSING,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            collection_name=collection_name,
            expires_at=None  # 用户知识库不设置过期时间
        )
        
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        
        logger.info(f"知识库创建成功: {name}, id={kb.id}")
        return kb
    
    async def get_knowledge_base_by_id(
        self, 
        kb_id: int, 
        user_id: Optional[int] = None
    ) -> Optional[KnowledgeBase]:
        """
        根据ID获取知识库
        
        Args:
            kb_id: 知识库ID
            user_id: 可选，如果提供则同时检查用户权限
            
        Returns:
            知识库对象或None
        """
        query = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        
        if user_id is not None:
            query = query.where(KnowledgeBase.user_id == user_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_knowledge_base_or_404(
        self, 
        kb_id: int, 
        user_id: Optional[int] = None
    ) -> KnowledgeBase:
        """
        根据ID获取知识库，不存在则抛出404异常
        
        Args:
            kb_id: 知识库ID
            user_id: 可选，如果提供则同时检查用户权限
            
        Returns:
            知识库对象
            
        Raises:
            ResourceNotFoundException: 知识库不存在
        """
        kb = await self.get_knowledge_base_by_id(kb_id, user_id)
        if not kb:
            raise ResourceNotFoundException("知识库不存在")
        return kb
    
    async def get_knowledge_base_with_permission_check(
        self,
        kb_id: int,
        current_user: User
    ) -> KnowledgeBase:
        """
        获取知识库并进行权限检查
        
        Args:
            kb_id: 知识库ID
            current_user: 当前用户
            
        Returns:
            知识库对象
            
        Raises:
            ResourceNotFoundException: 知识库不存在
            AuthorizationException: 无权访问此知识库
        """
        kb = await self.get_knowledge_base_by_id(kb_id)
        if not kb:
            raise ResourceNotFoundException("知识库不存在")
        
        # 检查权限：知识库所有者或管理员可以访问
        if kb.user_id and kb.user_id != current_user.id and not current_user.is_admin:
            raise AuthorizationException("无权访问此知识库")
        
        return kb
    
    async def list_knowledge_bases(
        self,
        user_id: int,
        category: Optional[str] = None
    ) -> List[KnowledgeBase]:
        """
        获取用户的知识库列表
        
        Args:
            user_id: 用户ID
            category: 可选的业务板块筛选
            
        Returns:
            知识库列表
        """
        query = select(KnowledgeBase).where(
            KnowledgeBase.user_id == user_id
        )
        
        # 按业务模块筛选
        if category and category != "all":
            try:
                cat_enum = KnowledgeBaseCategory(category)
            except ValueError:
                raise ValidationException(f"未知的知识库分类: {category}")
            query = query.where(KnowledgeBase.category == cat_enum)
        
        query = query.order_by(KnowledgeBase.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_all_general_knowledge_bases(
        self,
        only_ready: bool = True
    ) -> List[KnowledgeBase]:
        """
        获取所有通用类型的知识库
        
        Args:
            only_ready: 是否只返回就绪状态的知识库
            
        Returns:
            知识库列表
        """
        query = select(KnowledgeBase).where(
            KnowledgeBase.category == KnowledgeBaseCategory.GENERAL
        )
        
        if only_ready:
            query = query.where(KnowledgeBase.status == KnowledgeBaseStatus.READY)
        
        query = query.order_by(KnowledgeBase.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_manual_knowledge_bases(
        self,
        only_ready: bool = True
    ) -> List[KnowledgeBase]:
        """
        获取所有官方手册类型的知识库
        
        Args:
            only_ready: 是否只返回就绪状态的知识库
            
        Returns:
            知识库列表
        """
        query = select(KnowledgeBase).where(
            KnowledgeBase.category == KnowledgeBaseCategory.MANUAL
        )
        
        if only_ready:
            query = query.where(KnowledgeBase.status == KnowledgeBaseStatus.READY)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_knowledge_base(
        self,
        kb_id: int,
        user_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[KnowledgeBaseCategory] = None
    ) -> KnowledgeBase:
        """
        更新知识库信息
        
        Args:
            kb_id: 知识库ID
            user_id: 用户ID（用于权限检查）
            name: 新名称
            description: 新描述
            category: 新分类
            
        Returns:
            更新后的知识库对象
            
        Raises:
            ResourceNotFoundException: 知识库不存在
        """
        kb = await self.get_knowledge_base_or_404(kb_id, user_id)
        
        # 更新字段
        if name is not None:
            kb.name = name
        if description is not None:
            kb.description = description
        if category is not None:
            kb.category = category
        
        await self.db.commit()
        await self.db.refresh(kb)
        
        logger.info(f"知识库更新成功: {kb_id}")
        return kb
    
    async def update_knowledge_base_status(
        self,
        kb_id: int,
        status: KnowledgeBaseStatus
    ) -> KnowledgeBase:
        """
        更新知识库状态
        
        Args:
            kb_id: 知识库ID
            status: 新状态
            
        Returns:
            更新后的知识库对象
            
        Raises:
            ResourceNotFoundException: 知识库不存在
        """
        kb = await self.get_knowledge_base_or_404(kb_id)
        kb.status = status
        await self.db.commit()
        return kb
    
    async def update_document_count(
        self,
        kb_id: int,
        document_count: int
    ) -> KnowledgeBase:
        """
        更新知识库文档数量
        
        Args:
            kb_id: 知识库ID
            document_count: 文档数量
            
        Returns:
            更新后的知识库对象
        """
        kb = await self.get_knowledge_base_or_404(kb_id)
        kb.document_count = document_count
        await self.db.commit()
        return kb
    
    async def update_preprocessor_metadata(
        self,
        kb_id: int,
        metadata: Dict[str, Any]
    ) -> KnowledgeBase:
        """
        更新知识库预处理元数据
        
        Args:
            kb_id: 知识库ID
            metadata: 元数据字典
            
        Returns:
            更新后的知识库对象
        """
        kb = await self.get_knowledge_base_or_404(kb_id)
        kb.preprocessor_metadata = metadata
        await self.db.commit()
        return kb
    
    async def delete_knowledge_base(
        self,
        kb_id: int,
        user_id: int
    ) -> bool:
        """
        删除知识库
        
        Args:
            kb_id: 知识库ID
            user_id: 用户ID（用于权限检查）
            
        Returns:
            是否删除成功
            
        Raises:
            ResourceNotFoundException: 知识库不存在
        """
        kb = await self.get_knowledge_base_or_404(kb_id, user_id)
        
        await self.db.delete(kb)
        await self.db.commit()
        
        logger.info(f"知识库删除成功: {kb_id}")
        return True
    
    async def get_user_kb_ids(self, user_id: int) -> List[int]:
        """
        获取用户的所有知识库ID列表
        
        Args:
            user_id: 用户ID
            
        Returns:
            知识库ID列表
        """
        result = await self.db.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.user_id == user_id
            )
        )
        return [row[0] for row in result.all()]
    
    async def check_kb_ready(
        self,
        kb_id: int,
        user_id: Optional[int] = None
    ) -> KnowledgeBase:
        """
        检查知识库是否存在且处于就绪状态
        
        Args:
            kb_id: 知识库ID
            user_id: 可选的用户ID（用于权限检查）
            
        Returns:
            知识库对象
            
        Raises:
            ResourceNotFoundException: 知识库不存在
            ValidationException: 知识库未就绪
        """
        kb = await self.get_knowledge_base_or_404(kb_id, user_id)
        
        if kb.status != KnowledgeBaseStatus.READY:
            raise ValidationException("知识库未就绪")
        
        return kb
    
    async def check_kb_processing(
        self,
        kb_id: int
    ) -> KnowledgeBase:
        """
        检查知识库是否处于处理中状态
        
        Args:
            kb_id: 知识库ID
            
        Returns:
            知识库对象
            
        Raises:
            ResourceNotFoundException: 知识库不存在
            ValidationException: 知识库未在处理中
        """
        kb = await self.get_knowledge_base_or_404(kb_id)
        
        if kb.status != KnowledgeBaseStatus.PROCESSING:
            raise ValidationException("知识库未在处理中")
        
        return kb
    
    async def check_kb_ownership_or_admin(
        self,
        kb: KnowledgeBase,
        current_user: User
    ) -> None:
        """
        检查用户是否是知识库所有者或管理员
        
        Args:
            kb: 知识库对象
            current_user: 当前用户
            
        Raises:
            AuthorizationException: 无权操作此知识库
        """
        from app.models import UserRole
        
        if current_user.role != UserRole.SUPER_ADMIN and kb.user_id != current_user.id:
            raise AuthorizationException("无权操作此知识库")
