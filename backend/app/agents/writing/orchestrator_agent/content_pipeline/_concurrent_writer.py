"""
content_pipeline - 并发写作模块

包含 ContentPipelineMixin._concurrent_write_scenes() 方法，
以及内嵌的 write_single_scene() 闭包。

@date: 2026-04-24
@version: v3.0.0
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.writing.base_agent import AgentContext, AgentResult, AgentRole
from app.models.writing_scene import WritingScene, SceneStatus
from app.models.writing_unit import WritingUnit


class ConcurrentWriterMixin:
    """并发写作 Mixin

    提供 _concurrent_write_scenes() 方法 - 并发调用写手Agent生成场景内容。
    """

    # 由主类提供的属性
    db: Any
    _interrupt_event: Any
    _semaphore: Optional[Any]
    logger: Any
    _character_tracker: Any
    _project_knowledge_base: Any
    _current_task: Optional[Any]

    # 从其他 Mixin 继承的方法
    _check_interrupted: callable
    _send_ws_message: callable
    _get_agent: callable

    # 从本模块子模块继承的方法
    _get_or_create_scene_with_db: callable

    async def _concurrent_write_scenes(
        self,
        context: AgentContext,
        unit: WritingUnit,
        scenes_data: List[Dict]
    ) -> List[Dict[str, Any]]:
        """并发调用写手Agent生成场景内容

        使用asyncio.Semaphore控制并发数量

        Args:
            context: Agent执行上下文
            unit: 写作单元
            scenes_data: 场景数据列表

        Returns:
            List[Dict]: 场景结果列表
        """
        words_per_unit = context.config.get("words_per_unit", 3000)
        scene_count = len(scenes_data)
        words_per_scene = words_per_unit // scene_count if scene_count > 0 else words_per_unit

        async def write_single_scene(scene_data: Dict, scene_index: int) -> Dict[str, Any]:
            """单个场景的写入任务 - 每个任务使用独立的数据库会话"""
            async with self._semaphore:
                if self._check_interrupted():
                    return {
                        "scene_index": scene_index,
                        "success": False,
                        "error": "任务被中断"
                    }

                scene_title = scene_data.get("scene_title", f"场景{scene_index}")

                await self._send_ws_message("scene_progress", {
                    "unit_index": unit.unit_index,
                    "scene_index": scene_index,
                    "scene_title": scene_title,
                    "status": "writing"
                })

                from app.core.database import async_session_maker
                async with async_session_maker() as scene_db:
                    try:
                        from app.agents.writing.writer_agent import WriterAgent

                        writer_agent = self._get_agent(AgentRole.WRITER, WriterAgent)

                        scene = await self._get_or_create_scene_with_db(
                            scene_db, unit.id, scene_index, scene_data)
                        scene.status = SceneStatus.WRITING
                        await scene_db.commit()

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
                            character_states = {name: state.to_dict()
                                                for name, state in all_states.items()}
                            character_location_map = {
                                name: state.location for name, state in all_states.items() if state.location}
                            character_identity_map = {
                                name: state.identity for name, state in all_states.items() if state.identity}
                            active_characters = [name for name, state in all_states.items()
                                                 if state.status.value in ["active", "mentioned"]]

                        knowledge_graph_states = ""
                        if self._project_knowledge_base and context.project_id:
                            try:
                                knowledge_graph_states = self._project_knowledge_base.get_all_character_states_for_chapter(
                                    context.project_id, unit.unit_index
                                )
                            except Exception as kg_error:
                                self.logger.warning(f"获取知识图谱人物状态失败: {kg_error}")

                        writer_context = AgentContext(
                            task_id=context.task_id,
                            unit_index=unit.unit_index,
                            scene_index=scene_index,
                            project_id=context.project_id,
                            user_id=context.user_id,
                            outline=context.outline,
                            global_context=context.global_context,
                            character_profiles=context.character_profiles,
                            world_settings=context.world_settings,
                            style_guide=context.style_guide,
                            previous_content=context.previous_content,
                            character_state_snapshot=character_state_snapshot,
                            relationship_summary=relationship_summary,
                            character_states=character_states,
                            character_location_map=character_location_map,
                            character_identity_map=character_identity_map,
                            active_characters=active_characters,
                            extra={
                                "scene_outline": scene_data,
                                "unit_title": unit.unit_title,
                                "knowledge_graph_states": knowledge_graph_states
                            },
                            config={
                                "words_per_scene": words_per_scene,
                                **context.config
                            }
                        )

                        result = await writer_agent.execute(writer_context)

                        if result.success:
                            scene.writer_result = {
                                "content": result.content,
                                "token_usage": result.token_usage
                            }
                            scene.final_content = result.content
                            scene.word_count = len(result.content)
                            scene.status = SceneStatus.REVIEWING
                        else:
                            scene.status = SceneStatus.FAILED

                        await scene_db.commit()

                        scene_status = "completed" if result.success else "failed"
                        await self._send_ws_message("scene_progress", {
                            "unit_index": unit.unit_index,
                            "scene_index": scene_index,
                            "scene_title": scene_title,
                            "status": scene_status
                        })

                        return {
                            "scene_index": scene_index,
                            "scene_id": scene.id,
                            "success": result.success,
                            "content": result.content if result.success else "",
                            "error": result.errors[0] if result.errors else None
                        }

                    except Exception as e:
                        self.logger.exception(f"场景 {scene_index} 写入失败: {str(e)}")
                        await self._send_ws_message("scene_progress", {
                            "unit_index": unit.unit_index,
                            "scene_index": scene_index,
                            "scene_title": scene_title,
                            "status": "failed"
                        })
                        return {
                            "scene_index": scene_index,
                            "success": False,
                            "error": str(e)
                        }

        import asyncio
        tasks = [
            write_single_scene(scene_data, idx + 1)
            for idx, scene_data in enumerate(scenes_data)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        return processed_results
