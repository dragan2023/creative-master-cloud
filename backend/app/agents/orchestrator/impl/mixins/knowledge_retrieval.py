"""Agent编排器 - 知识库检索与分类Mixin"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict
from typing import List
from typing import Optional
import re
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseType, KnowledgeBaseStatus, KnowledgeBaseCategory


class KnowledgeRetrievalMixin:
    """知识库检索与分类"""

    # 模块名 → 知识库业务分类 映射表
    MODULE_CATEGORY_MAP = {
        "short_video": KnowledgeBaseCategory.SHORT_VIDEO,
        "novel": KnowledgeBaseCategory.NOVEL,
        "novel_global_outline": KnowledgeBaseCategory.NOVEL_WRITING,
        "novel_unit_summaries": KnowledgeBaseCategory.NOVEL_WRITING,
        "print_ad": KnowledgeBaseCategory.PRINT_AD,
        "tvc": KnowledgeBaseCategory.TVC,
        "original_ip": KnowledgeBaseCategory.GENERAL,
        "practical_writing": KnowledgeBaseCategory.PRACTICAL_WRITING,
    }

    def _sort_knowledge_bases_by_priority(
        self,
        kb_list: List[KnowledgeBase],
        module: str
    ) -> List[KnowledgeBase]:
        """
        按优先级排序知识库：通用 → 当前模块业务 → 其他业务 → 官方手册

        Args:
            kb_list: 知识库列表
            module: 当前模块名称

        Returns:
            排序后的知识库列表
        """
        # 获取当前模块对应的业务分类
        target_category = self.MODULE_CATEGORY_MAP.get(module)

        # 分离通用、业务和官方手册知识库
        general_kbs = []
        business_kbs = []
        manual_kbs = []
        other_kbs = []

        for kb in kb_list:
            if kb.category == KnowledgeBaseCategory.GENERAL:
                general_kbs.append(kb)
            elif kb.category == KnowledgeBaseCategory.MANUAL:
                manual_kbs.append(kb)
            elif target_category and kb.category == target_category:
                business_kbs.append(kb)
            else:
                other_kbs.append(kb)

        # 返回排序结果：通用 → 匹配的业务 → 其他业务 → 官方手册
        return general_kbs + business_kbs + other_kbs + manual_kbs


    async def _get_static_knowledge_bases(
        self,
        db: AsyncSession,
        module: str = None
    ) -> List[KnowledgeBase]:
        """
        获取所有静态知识库（预置知识库），按优先级排序

        调用顺序：后台通用 → 后台业务（匹配当前模块）

        Args:
            db: 数据库会话
            module: 当前模块名称（用于匹配业务知识库）

        Returns:
            排序后的静态知识库列表
        """
        try:
            query = select(KnowledgeBase).where(
                KnowledgeBase.type == KnowledgeBaseType.STATIC,
                KnowledgeBase.status == KnowledgeBaseStatus.READY,
                # 排除 novel 类别：正文板块使用独立的项目专属知识库系统
                KnowledgeBase.category != KnowledgeBaseCategory.NOVEL
            )
            result = await db.execute(query)
            kb_list = list(result.scalars().all())

            # 按优先级排序
            if module:
                return self._sort_knowledge_bases_by_priority(kb_list, module)
            return kb_list
        except Exception as e:
            self.logger.exception("获取静态知识库失败")
            return []


    async def _get_user_knowledge_bases(
        self,
        db: AsyncSession,
        user_id: int,
        module: str = None
    ) -> List[KnowledgeBase]:
        """
        获取用户知识库，按优先级排序

        调用顺序：用户端通用 → 用户端业务（匹配当前模块） → 其他业务 → 官方手册

        Args:
            db: 数据库会话
            user_id: 用户ID
            module: 当前模块名称（用于匹配业务知识库）

        Returns:
            排序后的用户知识库列表
        """
        try:
            query = select(KnowledgeBase).where(
                KnowledgeBase.type == KnowledgeBaseType.TEMP,
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.status == KnowledgeBaseStatus.READY,
                # 排除 novel 类别：正文板块使用独立的项目专属知识库系统
                KnowledgeBase.category != KnowledgeBaseCategory.NOVEL
            )
            result = await db.execute(query)
            kb_list = list(result.scalars().all())

            # 按优先级排序
            if module:
                return self._sort_knowledge_bases_by_priority(kb_list, module)
            return kb_list
        except Exception as e:
            self.logger.exception("获取用户知识库失败")
            return []


    async def _retrieve_classified_knowledge(
        self,
        db: AsyncSession,
        user_id: int,
        module: str,
        query_text: str,
        # 知识库类别选择参数
        kb_vertical: bool = False,
        kb_user_specific: bool = False,
        kb_manual: bool = False,
        kb_vertical_ids: Optional[List[int]] = None,
        kb_user_specific_ids: Optional[List[int]] = None,
        kb_manual_ids: Optional[List[int]] = None
    ) -> Dict[str, str]:
        """
        按类别检索知识库

        检索顺序：
        1. 理论知识库（通用知识库）- 固定调用
        2. 垂直领域知识库 - 用户选择启用后调用
        3. 用户专属知识库 - 用户选择启用后调用
        4. 官方手册知识库 - 用户选择启用后调用

        Args:
            db: 数据库会话
            user_id: 用户ID
            module: 当前模块名称
            query_text: 检索查询文本
            kb_vertical: 是否启用垂直领域知识库
            kb_user_specific: 是否启用用户专属知识库
            kb_manual: 是否启用官方手册知识库
            kb_vertical_ids: 指定的垂直领域知识库ID列表
            kb_user_specific_ids: 指定的用户专属知识库ID列表
            kb_manual_ids: 指定的官方手册知识库ID列表

        Returns:
            {
                "theory": "通用理论知识库内容...",
                "case": "垂直领域知识库内容...",
                "user_specific": "用户专属知识库内容...",
                "manual": "官方手册内容..."
            }
        """
        kb_contexts = {
            "theory": "",
            "case": "",
            "user_specific": "",
            "manual": ""
        }

        try:
            # 获取用户的 GraphRAG 配置
            graphrag_enabled = await self._get_user_graphrag_config(db, user_id)

            # 获取用户知识库
            user_kb_list = await self._get_user_knowledge_bases(db, user_id, module)

            if not user_kb_list:
                return kb_contexts

            # 定义垂直领域类别
            # 注意：
            # - NOVEL 类别不在此列表中，因为它是项目专属知识库（ProjectKnowledgeBase），
            #   用于存储具体项目的人物/情节/世界观，完全独立
            # - NOVEL_WRITING 是小说写作专业知识库，参与双轨检索
            vertical_categories = [
                KnowledgeBaseCategory.SHORT_VIDEO,
                KnowledgeBaseCategory.SCRIPT,
                # KnowledgeBaseCategory.NOVEL,  # 已移除：项目专属知识库，不参与双轨检索
                KnowledgeBaseCategory.NOVEL_WRITING,  # 新增：小说写作专业知识库，参与双轨检索
                KnowledgeBaseCategory.PRINT_AD,
                KnowledgeBaseCategory.TVC,
                KnowledgeBaseCategory.PRACTICAL_WRITING
            ]

            # 逐个检索并按类别分类
            for kb in user_kb_list:
                try:
                    # 1. 通用知识库 - 固定调用
                    if kb.category == KnowledgeBaseCategory.GENERAL:
                        kb_result = await self._retrieve_single_kb(
                            kb, query_text, graphrag_enabled
                        )
                        if kb_result:
                            kb_contexts["theory"] += f"\n### {kb.name}\n{kb_result}\n"
                        continue

                    # 2. 垂直领域知识库 - 用户选择启用后调用
                    if kb.category in vertical_categories:
                        if not kb_vertical:
                            continue
                        # 如果指定了具体ID，检查是否在列表中
                        if kb_vertical_ids and kb.id not in kb_vertical_ids:
                            continue
                        kb_result = await self._retrieve_single_kb(
                            kb, query_text, graphrag_enabled
                        )
                        if kb_result:
                            kb_contexts["case"] += f"\n### {kb.name}\n{kb_result}\n"
                        continue

                    # 3. 用户专属知识库 - 用户选择启用后调用
                    if kb.category == KnowledgeBaseCategory.USER_SPECIFIC:
                        if not kb_user_specific:
                            continue
                        if kb_user_specific_ids and kb.id not in kb_user_specific_ids:
                            continue
                        # 用户专属知识库始终使用GraphRAG
                        kb_result = await self._retrieve_single_kb(
                            kb, query_text, True
                        )
                        if kb_result:
                            kb_contexts["user_specific"] += f"\n### {kb.name}\n{kb_result}\n"
                        continue

                    # 4. 官方手册 - 用户选择启用后调用（不使用GraphRAG）
                    if kb.category == KnowledgeBaseCategory.MANUAL:
                        if not kb_manual:
                            continue
                        if kb_manual_ids and kb.id not in kb_manual_ids:
                            continue
                        kb_result = await self._retrieve_single_kb(
                            kb, query_text, False
                        )
                        if kb_result:
                            kb_contexts["manual"] += f"\n### {kb.name}\n{kb_result}\n"
                        continue

                except Exception as e:
                    self.logger.warning(
                        f"知识库 '{kb.name}' (ID:{kb.id}) 检索失败，已跳过: {e}")
                    continue  # 确保继续处理下一个KB

            return kb_contexts

        except Exception as e:
            self.logger.exception("分类检索知识库失败")
            return kb_contexts


    async def _retrieve_single_kb(
        self,
        kb: KnowledgeBase,
        query_text: str,
        use_graphrag: bool
    ) -> Optional[str]:
        """
        检索单个知识库

        Args:
            kb: 知识库对象
            query_text: 检索查询文本
            use_graphrag: 是否使用GraphRAG

        Returns:
            检索结果字符串或None
        """
        try:
            if use_graphrag:
                # GraphRAG 检索（知识图谱增强）
                kb_result = await self.knowledge_retrieval.retrieve_with_graph_context(
                    collection_name=kb.collection_name,
                    query=query_text,
                    n_results=2
                )
            else:
                # 传统向量检索
                kb_result = await self.knowledge_retrieval.retrieve_with_context(
                    collection_name=kb.collection_name,
                    query=query_text,
                    n_results=2
                )

            if kb_result and "未找到" not in kb_result:
                return kb_result
            return None
        except Exception as e:
            self.logger.exception(f"检索知识库 {kb.name} 异常")
            return None


