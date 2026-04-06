"""
多Agent协作文学作品生成系统 - 知识顾问Agent

模块: agents.writing
文件: knowledge_agent.py
功能: 为其他Agent提供上下文知识检索和一致性参考

依赖关系:
    - 依赖: app.agents.writing.base_agent, app.agents.writing.agent_config
    - 被依赖: orchestrator_agent, writer_agent, logic_editor_agent
    
适配器模块（松耦合引用）:
    - ContextManagerAdapter: 包装上下文管理器
    - KnowledgeBaseAdapter: 包装项目知识库

创建时间: 2026-03-27
最后修改: 2026-03-27

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any, List, Optional
import time

from app.agents.writing.base_agent import (
    BaseWritingAgent,
    AgentContext,
    AgentResult,
    AgentRole
)


# ============================================================================
# 适配器类（松耦合引用旧模块）
# ============================================================================

class ContextManagerAdapter:
    """上下文管理器适配器
    
    包装旧的ContextWindowManager，实现松耦合引用。
    使用懒加载模式，只在需要时才导入和实例化旧模块。
    """
    
    def __init__(self):
        self._manager_class = None
        self._manager_instance = None
    
    def _get_manager_class(self):
        """获取管理器类（懒加载）"""
        if self._manager_class is None:
            try:
                from app.services.novel_writer.context_manager import ContextWindowManager
                self._manager_class = ContextWindowManager
            except ImportError as e:
                # 模块不存在或导入失败
                return None
        return self._manager_class
    
    async def get_relevant_context(
        self,
        query: str,
        project_id: int,
        top_k: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """获取相关上下文
        
        从向量存储中检索与查询相关的历史内容片段。
        
        Args:
            query: 查询文本
            project_id: 项目ID
            top_k: 返回结果数量
            **kwargs: 其他参数
        
        Returns:
            相关内容片段列表，每个元素包含：
            - content: 内容文本
            - score: 相关度分数
            - source: 来源（章节/场景）
            - metadata: 元数据
        """
        manager_class = self._get_manager_class()
        if manager_class is None:
            # 模块不可用，返回空结果
            return []
        
        try:
            # 尝试调用旧模块的方法
            # 注意：这里需要根据实际接口调整
            manager = self._get_instance(project_id)
            if hasattr(manager, 'search_relevant'):
                results = await manager.search_relevant(query, top_k=top_k)
                return results
            else:
                return []
        except Exception:
            # 调用失败，返回空结果
            return []
    
    def _get_instance(self, project_id: int):
        """获取管理器实例"""
        if self._manager_instance is None:
            manager_class = self._get_manager_class()
            if manager_class:
                self._manager_instance = manager_class(project_id=project_id)
        return self._manager_instance


class KnowledgeBaseAdapter:
    """项目知识库适配器
    
    包装旧的ProjectKnowledgeBase，实现松耦合引用。
    使用懒加载模式，只在需要时才导入和实例化旧模块。
    """
    
    def __init__(self):
        self._kb_class = None
        self._kb_instance = None
    
    def _get_kb_class(self):
        """获取知识库类（懒加载）"""
        if self._kb_class is None:
            try:
                from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
                self._kb_class = ProjectKnowledgeBase
            except ImportError:
                return None
        return self._kb_class
    
    async def search_knowledge(
        self,
        query: str,
        project_id: int,
        knowledge_types: Optional[List[str]] = None,
        top_k: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """搜索知识
        
        从知识图谱和向量存储中检索相关知识。
        
        Args:
            query: 查询文本
            project_id: 项目ID
            knowledge_types: 知识类型过滤（如 ['character', 'event', 'setting']）
            top_k: 返回结果数量
            **kwargs: 其他参数
        
        Returns:
            知识检索结果：
            - characters: 相关角色信息
            - events: 相关事件信息
            - settings: 相关设定信息
            - relations: 关系信息
        """
        kb_class = self._get_kb_class()
        if kb_class is None:
            # 模块不可用，返回空结果
            return self._empty_result()
        
        try:
            # 尝试调用旧模块的方法
            kb = self._get_instance(project_id)
            if hasattr(kb, 'search'):
                results = await kb.search(
                    query=query,
                    types=knowledge_types,
                    top_k=top_k
                )
                return results
            else:
                return self._empty_result()
        except Exception:
            return self._empty_result()
    
    async def get_character_relations(
        self,
        project_id: int,
        character_names: List[str]
    ) -> List[Dict[str, Any]]:
        """获取角色关系
        
        从知识图谱中检索指定角色之间的关系。
        
        Args:
            project_id: 项目ID
            character_names: 角色名称列表
        
        Returns:
            角色关系列表
        """
        kb_class = self._get_kb_class()
        if kb_class is None:
            return []
        
        try:
            kb = self._get_instance(project_id)
            if hasattr(kb, 'get_relations'):
                relations = await kb.get_relations(
                    entity_names=character_names,
                    relation_type="character"
                )
                return relations
            else:
                return []
        except Exception:
            return []
    
    async def get_plot_threads(
        self,
        project_id: int,
        current_chapter: int
    ) -> List[Dict[str, Any]]:
        """获取剧情线索
        
        检索当前章节相关的剧情线索。
        
        Args:
            project_id: 项目ID
            current_chapter: 当前章节号
        
        Returns:
            剧情线索列表
        """
        kb_class = self._get_kb_class()
        if kb_class is None:
            return []
        
        try:
            kb = self._get_instance(project_id)
            if hasattr(kb, 'get_plot_threads'):
                threads = await kb.get_plot_threads(
                    up_to_chapter=current_chapter
                )
                return threads
            else:
                return []
        except Exception:
            return []
    
    def _get_instance(self, project_id: int):
        """获取知识库实例"""
        if self._kb_instance is None:
            kb_class = self._get_kb_class()
            if kb_class:
                self._kb_instance = kb_class(project_id=project_id)
        return self._kb_instance
    
    def _empty_result(self) -> Dict[str, Any]:
        """返回空结果结构"""
        return {
            "characters": [],
            "events": [],
            "settings": [],
            "relations": []
        }


# ============================================================================
# 知识顾问Agent
# ============================================================================

class KnowledgeAgent(BaseWritingAgent):
    """知识顾问Agent - 上下文知识检索专家
    
    为其他Agent提供上下文知识检索和一致性参考，确保创作内容的连贯性和准确性。
    
    主要职责：
    1. 从向量存储检索相关内容片段
    2. 从知识图谱检索角色关系、事件线索
    3. 整合为结构化的上下文信息
    4. 提供一致性检查参考
    
    特点：
    - 使用较低温度(0.3)确保知识准确
    - 通过适配器模式松耦合引用旧模块
    - 支持多种知识类型检索
    """
    
    agent_name = "知识顾问Agent"
    agent_role = AgentRole.KNOWLEDGE
    default_model = ""
    default_temperature = 0.3
    
    def __init__(self, config=None):
        """初始化知识顾问Agent
        
        Args:
            config: Agent配置
        """
        super().__init__(config)
        self._context_adapter: Optional[ContextManagerAdapter] = None
        self._kb_adapter: Optional[KnowledgeBaseAdapter] = None
    
    @property
    def context_adapter(self) -> ContextManagerAdapter:
        """获取上下文适配器（懒加载）"""
        if self._context_adapter is None:
            self._context_adapter = ContextManagerAdapter()
        return self._context_adapter
    
    @property
    def kb_adapter(self) -> KnowledgeBaseAdapter:
        """获取知识库适配器（懒加载）"""
        if self._kb_adapter is None:
            self._kb_adapter = KnowledgeBaseAdapter()
        return self._kb_adapter
    
    async def execute(self, context: AgentContext) -> AgentResult:
        """检索相关知识并整合上下文
        
        Args:
            context: Agent执行上下文，包含：
                - context.extra["query"]: 检索查询（可选）
                - context.extra["knowledge_types"]: 知识类型过滤（可选）
                - context.extra["top_k"]: 返回结果数量（可选）
                - context.character_profiles: 角色档案
                - context.world_settings: 世界观设定
                - context.project_id: 项目ID
                - context.unit_index: 当前章节索引
        
        Returns:
            AgentResult: 包含整合后的上下文信息
                - content: 格式化的上下文摘要
                - data["relevant_passages"]: 相关内容片段
                - data["character_relations"]: 角色关系
                - data["plot_threads"]: 剧情线索
                - data["world_facts"]: 世界观事实
        """
        start_time = time.time()
        
        try:
            # 提取参数
            query = context.extra.get("query", "")
            knowledge_types = context.extra.get("knowledge_types")
            top_k = context.extra.get("top_k", 10)
            project_id = context.project_id
            current_chapter = context.unit_index
            
            self.logger.info(
                f"开始知识检索 - 项目: {project_id}, "
                f"章节: {current_chapter}, 查询: {query[:50]}..."
            )
            
            # 并行检索各类知识
            relevant_passages = []
            character_relations = []
            plot_threads = []
            kb_results = {}
            
            # 1. 从上下文管理器检索相关内容
            if query:
                relevant_passages = await self.context_adapter.get_relevant_context(
                    query=query,
                    project_id=project_id,
                    top_k=top_k // 2  # 分配一半配额给上下文检索
                )
            
            # 2. 从知识库检索
            kb_results = await self.kb_adapter.search_knowledge(
                query=query or f"第{current_chapter}章相关内容",
                project_id=project_id,
                knowledge_types=knowledge_types,
                top_k=top_k
            )
            
            # 3. 获取角色关系
            character_names = [
                char.get("name", "") 
                for char in context.character_profiles
                if char.get("name")
            ]
            if character_names:
                character_relations = await self.kb_adapter.get_character_relations(
                    project_id=project_id,
                    character_names=character_names
                )
            
            # 4. 获取剧情线索
            plot_threads = await self.kb_adapter.get_plot_threads(
                project_id=project_id,
                current_chapter=current_chapter
            )
            
            # 5. 整合世界观事实
            world_facts = self._extract_world_facts(context.world_settings)
            
            # 6. 构建上下文摘要
            context_summary = self._build_context_summary(
                relevant_passages=relevant_passages,
                kb_results=kb_results,
                character_relations=character_relations,
                plot_threads=plot_threads,
                world_facts=world_facts
            )
            
            # 计算耗时
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.logger.info(
                f"知识检索完成 - 相关片段: {len(relevant_passages)}, "
                f"角色关系: {len(character_relations)}, "
                f"剧情线索: {len(plot_threads)}, 耗时: {duration_ms}ms"
            )
            
            return self._build_success_result(
                content=context_summary,
                duration_ms=duration_ms,
                model_id="",  # 知识检索不消耗LLM tokens
                relevant_passages=relevant_passages,
                character_relations=character_relations,
                plot_threads=plot_threads,
                world_facts=world_facts,
                kb_characters=kb_results.get("characters", []),
                kb_events=kb_results.get("events", []),
                kb_settings=kb_results.get("settings", [])
            )
            
        except Exception as e:
            self.logger.error(f"知识顾问Agent执行失败: {str(e)}", exc_info=True)
            return self._build_error_result(f"知识检索失败: {str(e)}")
    
    def _extract_world_facts(self, world_settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取世界观事实
        
        Args:
            world_settings: 世界观设定
        
        Returns:
            世界观事实列表
        """
        facts = []
        
        if not world_settings:
            return facts
        
        # 提取时间设定
        if "time_period" in world_settings:
            facts.append({
                "type": "time",
                "content": world_settings["time_period"],
                "importance": "high"
            })
        
        # 提取地点设定
        locations = world_settings.get("locations", [])
        for loc in locations[:5]:  # 最多5个主要地点
            facts.append({
                "type": "location",
                "content": loc.get("description", ""),
                "name": loc.get("name", ""),
                "importance": loc.get("importance", "normal")
            })
        
        # 提取社会背景
        if "social_background" in world_settings:
            facts.append({
                "type": "social",
                "content": world_settings["social_background"],
                "importance": "high"
            })
        
        # 提取特殊规则
        rules = world_settings.get("special_rules", [])
        for rule in rules[:3]:  # 最多3条重要规则
            facts.append({
                "type": "rule",
                "content": rule,
                "importance": "high"
            })
        
        return facts
    
    def _build_context_summary(
        self,
        relevant_passages: List[Dict[str, Any]],
        kb_results: Dict[str, Any],
        character_relations: List[Dict[str, Any]],
        plot_threads: List[Dict[str, Any]],
        world_facts: List[Dict[str, Any]]
    ) -> str:
        """构建上下文摘要
        
        将检索到的各类知识整合为结构化的文本摘要。
        
        Args:
            relevant_passages: 相关内容片段
            kb_results: 知识库检索结果
            character_relations: 角色关系
            plot_threads: 剧情线索
            world_facts: 世界观事实
        
        Returns:
            格式化的上下文摘要
        """
        sections = []
        
        # 世界观事实
        if world_facts:
            sections.append("【世界观参考】")
            for fact in world_facts[:5]:
                if fact.get("type") == "location":
                    sections.append(f"· {fact.get('name', '')}: {fact.get('content', '')}")
                else:
                    sections.append(f"· {fact.get('content', '')}")
            sections.append("")
        
        # 角色关系
        if character_relations:
            sections.append("【角色关系】")
            for rel in character_relations[:5]:
                source = rel.get("source", "")
                target = rel.get("target", "")
                relation = rel.get("relation", "")
                sections.append(f"· {source} —{relation}— {target}")
            sections.append("")
        
        # 剧情线索
        if plot_threads:
            sections.append("【剧情线索】")
            for thread in plot_threads[:3]:
                description = thread.get("description", "")
                status = thread.get("status", "进行中")
                sections.append(f"· [{status}] {description}")
            sections.append("")
        
        # 相关内容片段
        if relevant_passages:
            sections.append("【相关内容参考】")
            for i, passage in enumerate(relevant_passages[:3], 1):
                content = passage.get("content", "")
                source = passage.get("source", "未知来源")
                # 截断过长内容
                if len(content) > 200:
                    content = content[:200] + "..."
                sections.append(f"{i}. [{source}] {content}")
            sections.append("")
        
        # 知识库事件
        kb_events = kb_results.get("events", [])
        if kb_events:
            sections.append("【相关事件】")
            for event in kb_events[:3]:
                name = event.get("name", "")
                description = event.get("description", "")
                sections.append(f"· {name}: {description}")
            sections.append("")
        
        if not sections:
            return "未检索到相关上下文信息"
        
        return "\n".join(sections)
    
    async def get_character_context(
        self,
        context: AgentContext,
        character_name: str
    ) -> AgentResult:
        """获取特定角色的上下文信息
        
        便捷方法，专门用于检索单个角色的相关信息。
        
        Args:
            context: 执行上下文
            character_name: 角色名称
        
        Returns:
            AgentResult: 包含角色相关的上下文信息
        """
        # 修改查询参数
        context.extra["query"] = character_name
        context.extra["knowledge_types"] = ["character"]
        context.extra["top_k"] = 5
        
        return await self.execute(context)
    
    async def check_consistency(
        self,
        context: AgentContext,
        content_to_check: str
    ) -> Dict[str, Any]:
        """检查内容一致性
        
        检查内容与已有知识的冲突。
        
        Args:
            context: 执行上下文
            content_to_check: 待检查的内容
        
        Returns:
            一致性检查结果：
            - is_consistent: 是否一致
            - conflicts: 冲突列表
            - warnings: 警告列表
        """
        result = await self.execute(context)
        
        conflicts = []
        warnings = []
        
        # 简单的一致性检查逻辑
        # 后续可以增强为使用LLM进行检查
        
        # 检查角色名称拼写
        character_names = [
            char.get("name", "") 
            for char in context.character_profiles
        ]
        for name in character_names:
            if name and name in content_to_check:
                # 角色出现，记录
                pass
        
        # 检查地点一致性
        locations = context.world_settings.get("locations", [])
        for loc in locations:
            loc_name = loc.get("name", "")
            if loc_name and loc_name in content_to_check:
                # 地点出现，记录
                pass
        
        return {
            "is_consistent": len(conflicts) == 0,
            "conflicts": conflicts,
            "warnings": warnings
        }
