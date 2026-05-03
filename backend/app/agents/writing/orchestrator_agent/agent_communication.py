"""
多Agent协作文学作品生成系统 - Agent间消息传递模块

模块: agents.writing.orchestrator_agent
文件: agent_communication.py
功能: Agent实例管理、各专业Agent调用封装

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Any, Dict, List, Optional, Type

from sqlalchemy import select

from app.agents.writing.base_agent import AgentContext, AgentResult, AgentRole, BaseWritingAgent
from app.models.writing_unit import WritingUnit
from app.models.writing_scene import WritingScene


class AgentCommunicationMixin:
    """Agent间消息传递 Mixin
    
    提供：
    - Agent实例获取与缓存
    - 结构师Agent调用
    - 写手Agent调用（在content_pipeline中）
    - 逻辑编辑Agent调用
    - 风格润色Agent调用
    - 合规审查Agent调用
    - 合成Agent调用
    """
    
    # 这些属性由主类提供，类型提示
    db: Any  # AsyncSession
    _agent_instances: Dict[AgentRole, BaseWritingAgent]
    _stats_interceptor: Any  # StatsInterceptor
    _character_tracker: Any  # CharacterStateTracker
    logger: Any
    config: Any  # AgentConfig
    
    def _get_agent(
        self, 
        role: AgentRole, 
        agent_class: Type[BaseWritingAgent],
        **kwargs
    ) -> BaseWritingAgent:
        """获取或创建子Agent实例（惰性创建）

        Args:
            role: Agent角色
            agent_class: Agent类
            **kwargs: 传递给Agent构造函数的额外参数

        Returns:
            Agent实例
        """
        if role not in self._agent_instances:
            agent = agent_class(config=self.config, **kwargs)
            if self._stats_interceptor:
                agent.set_stats_interceptor(self._stats_interceptor)
            self._agent_instances[role] = agent
        return self._agent_instances[role]
    
    async def _call_structural_agent(self, context: AgentContext, unit: WritingUnit) -> AgentResult:
        """调用结构师Agent拆解场景

        增强版：传递人物状态信息，确保场景拆解考虑人物当前位置和状态。

        Args:
            context: Agent执行上下文
            unit: 写作单元

        Returns:
            AgentResult: 包含场景列表
        """
        from app.agents.writing.structural_agent import StructuralAgent

        structural_agent = self._get_agent(AgentRole.STRUCTURAL, StructuralAgent)

        words_per_unit = context.config.get("words_per_unit", 3000)
        words_per_scene = words_per_unit // 4

        character_state_snapshot = ""
        relationship_summary = ""
        character_states = {}
        character_location_map = {}
        character_identity_map = {}
        active_characters = []

        if self._character_tracker:
            character_state_snapshot = self._character_tracker.get_state_for_prompt(
                chapter_num=unit.unit_index
            )
            relationship_summary = self._character_tracker.get_relationship_summary()

            all_states = self._character_tracker.get_all_characters()
            character_states = {name: state.to_dict() for name, state in all_states.items()}
            character_location_map = {name: state.location for name, state in all_states.items() if state.location}
            character_identity_map = {name: state.identity for name, state in all_states.items() if state.identity}
            active_characters = [name for name, state in all_states.items() 
                               if state.status.value in ["active", "mentioned"]]

        structural_context = AgentContext(
            task_id=context.task_id,
            unit_index=unit.unit_index,
            project_id=context.project_id,
            user_id=context.user_id,
            outline=context.outline,
            global_context=context.global_context,
            character_profiles=context.character_profiles,
            world_settings=context.world_settings,
            style_guide=context.style_guide,
            character_state_snapshot=character_state_snapshot,
            relationship_summary=relationship_summary,
            character_states=character_states,
            character_location_map=character_location_map,
            character_identity_map=character_identity_map,
            active_characters=active_characters,
            extra={
                "unit_title": unit.unit_title,
                "unit_summary": unit.unit_summary,
                "previous_content": context.previous_content,
                "target_words": words_per_unit,
                "words_per_scene": words_per_scene
            }
        )

        return await structural_agent.execute(structural_context)
    
    async def _call_logic_editor(
        self, 
        context: AgentContext, 
        unit: WritingUnit, 
        scene_index: int,
        content: str
    ) -> AgentResult:
        """调用逻辑编辑Agent

        增强版：传递完整的人物状态信息，支持人物状态一致性检查和状态更新提取。

        Args:
            context: Agent执行上下文
            unit: 写作单元
            scene_index: 场景序号
            content: 场景内容

        Returns:
            AgentResult: 逻辑审阅结果，包含character_state_updates和new_characters
        """
        try:
            from app.agents.writing.logic_editor import LogicEditorAgent

            agent = self._get_agent(AgentRole.LOGIC_EDITOR, LogicEditorAgent)

            character_state_snapshot = ""
            relationship_summary = ""
            character_states = {}
            character_location_map = {}
            character_identity_map = {}
            character_state_evolution = {}
            previous_chapter_characters = []

            if self._character_tracker:
                character_state_snapshot = self._character_tracker.get_state_summary()
                relationship_summary = self._character_tracker.get_relationship_summary()

                all_states = self._character_tracker.get_all_characters()
                character_states = {name: state.to_dict() for name, state in all_states.items()}
                character_location_map = {name: state.location for name, state in all_states.items() if state.location}
                character_identity_map = {name: state.identity for name, state in all_states.items() if state.identity}

                for char_name in all_states:
                    evolution = self._character_tracker.get_state_evolution(char_name)
                    if evolution:
                        evolution_text = "\n".join([
                            f"第{e['chapter']}章({e['chapter_title']}): {e['state'].get('status_change', '无变化')}"
                            for e in evolution[-3:]
                        ])
                        character_state_evolution[char_name] = evolution_text

                prev_snapshot = self._character_tracker.get_chapter_snapshot(unit.unit_index - 1)
                if prev_snapshot:
                    previous_chapter_characters = list(prev_snapshot.characters.keys())

            editor_context = AgentContext(
                task_id=context.task_id,
                unit_index=unit.unit_index,
                scene_index=scene_index,
                project_id=context.project_id,
                user_id=context.user_id,
                global_context=context.global_context,
                character_profiles=context.character_profiles,
                character_state_snapshot=character_state_snapshot,
                relationship_summary=relationship_summary,
                character_states=character_states,
                character_location_map=character_location_map,
                character_identity_map=character_identity_map,
                character_state_evolution=character_state_evolution,
                previous_chapter_characters=previous_chapter_characters,
                extra={
                    "draft_content": content,
                    "unit_title": unit.unit_title
                }
            )

            return await agent.execute(editor_context)
        except ImportError:
            return AgentResult(
                success=True,
                agent_role=AgentRole.LOGIC_EDITOR,
                content=content,
                data={"issues": [], "character_state_updates": [], "new_characters": []}
            )

    async def _call_style_editor(
        self, 
        context: AgentContext, 
        unit: WritingUnit,
        scene_index: int,
        content: str
    ) -> AgentResult:
        """调用风格润色Agent
    
        Args:
            context: Agent执行上下文
            unit: 写作单元
            scene_index: 场景序号
            content: 场景内容
    
        Returns:
            AgentResult: 风格润色结果
        """
        try:
            from app.agents.writing.style_editor import StyleEditorAgent
    
            # 从上下文配置中获取AI文风消除设置
            ai_elimination_enabled = context.config.get("ai_elimination_enabled", True)
            ai_elimination_threshold = context.config.get("ai_elimination_threshold", 50)
            style_document_features = context.config.get("style_document_features", "")
    
            agent = self._get_agent(
                AgentRole.STYLE_EDITOR, 
                StyleEditorAgent,
                enable_ai_detection=ai_elimination_enabled,
                enable_humanization=ai_elimination_enabled,
                humanization_threshold=ai_elimination_threshold
            )
    
            editor_context = AgentContext(
                task_id=context.task_id,
                unit_index=unit.unit_index,
                scene_index=scene_index,
                project_id=context.project_id,
                user_id=context.user_id,
                style_guide=context.style_guide,
                extra={
                    "content": content,
                    "unit_title": unit.unit_title,
                    "style_document_features": style_document_features
                }
            )
    
            return await agent.execute(editor_context)
        except ImportError:
            return AgentResult(
                success=True,
                agent_role=AgentRole.STYLE_EDITOR,
                content=content,
                data={"suggestions": []}
            )

    async def _call_compliance_agent(
        self, 
        context: AgentContext, 
        unit: WritingUnit, 
        scene_index: int,
        content: str
    ) -> AgentResult:
        """调用合规审查Agent

        Args:
            context: Agent执行上下文
            unit: 写作单元
            scene_index: 场景序号
            content: 场景内容

        Returns:
            AgentResult: 合规审查结果
        """
        try:
            from app.agents.writing.compliance_agent import ComplianceAgent

            agent = self._get_agent(AgentRole.COMPLIANCE, ComplianceAgent)

            compliance_context = AgentContext(
                task_id=context.task_id,
                unit_index=unit.unit_index,
                scene_index=scene_index,
                project_id=context.project_id,
                user_id=context.user_id,
                extra={
                    "content": content,
                    "unit_title": unit.unit_title
                }
            )

            return await agent.execute(compliance_context)
        except ImportError:
            return AgentResult(
                success=True,
                agent_role=AgentRole.COMPLIANCE,
                content="",
                data={"violations": []}
            )

    async def _call_assembler_agent(self, context: AgentContext, unit: WritingUnit) -> str:
        """调用合成Agent合并场景

        Args:
            context: Agent执行上下文
            unit: 写作单元

        Returns:
            str: 合并后的完整章节内容
        """
        # 延迟导入避免循环依赖
        from app.agents.writing.assembler_agent import AssemblerAgent

        agent = self._get_agent(AgentRole.ASSEMBLER, AssemblerAgent)

        # 显式查询场景（避免lazy-load greenlet错误）
        scenes_query = await self.db.execute(
            select(WritingScene).where(WritingScene.unit_id == unit.id)
            .order_by(WritingScene.scene_index)
        )
        scenes = scenes_query.scalars().all()

        # 获取所有场景的最终内容
        scenes_content = []
        for scene in scenes:
            if scene.final_content:
                scenes_content.append({
                    "scene_index": scene.scene_index,
                    "scene_title": scene.scene_title or f"场景{scene.scene_index}",
                    "content": scene.final_content
                })

        # 按场景序号排序
        scenes_content.sort(key=lambda x: x["scene_index"])

        assembler_context = AgentContext(
            task_id=context.task_id,
            unit_index=unit.unit_index,
            project_id=context.project_id,
            user_id=context.user_id,
            extra={
                "scenes_content": scenes_content,
                "unit_title": unit.unit_title,
                "style_guide": context.style_guide
            }
        )

        result = await agent.execute(assembler_context)

        if result.success:
            return result.content
        else:
            # 合成失败，简单拼接
            return "\n\n".join([s["content"] for s in scenes_content])
