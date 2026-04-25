"""
content_pipeline - 审阅流水线模块

包含 ContentPipelineMixin._run_review_pipeline_for_unit() 方法，
以及内嵌的 review_single_scene() 闭包。

@date: 2026-04-24
@version: v3.0.0
"""
from typing import Any, Dict, List

from app.agents.writing.base_agent import AgentResult
from app.models.writing_scene import SceneStatus


class ReviewPipelineMixin:
    """审阅流水线 Mixin

    提供 _run_review_pipeline_for_unit() 方法 - 为单元的所有场景运行并行审阅。
    """

    # 由主类提供的属性
    db: Any
    logger: Any

    # 从其他 Mixin 继承的方法
    _call_logic_editor: callable
    _call_style_editor: callable
    _call_compliance_agent: callable
    _get_scene_by_id_with_db: callable

    async def _run_review_pipeline_for_unit(
        self,
        context: Any,
        unit: Any,
        scene_results: List[Dict[str, Any]]
    ) -> None:
        """为单元的所有场景运行并行审阅流水线

        并行执行：逻辑编辑 + 风格润色 + 合规审查

        Args:
            context: Agent执行上下文
            unit: 写作单元
            scene_results: 场景结果列表
        """
        successful_scenes = [r for r in scene_results if r.get("success")]

        async def review_single_scene(scene_result: Dict) -> None:
            """单个场景的审阅任务 - 每个任务使用独立的数据库会话"""
            scene_index = scene_result["scene_index"]
            scene_id = scene_result.get("scene_id")
            content = scene_result.get("content", "")

            if not scene_id:
                return

            from app.core.database import async_session_maker
            async with async_session_maker() as review_db:
                try:
                    import asyncio
                    logic_result, style_result, compliance_result = await asyncio.gather(
                        self._call_logic_editor(
                            context, unit, scene_index, content),
                        self._call_style_editor(
                            context, unit, scene_index, content),
                        self._call_compliance_agent(
                            context, unit, scene_index, content),
                        return_exceptions=True
                    )

                    scene = await self._get_scene_by_id_with_db(review_db, scene_id)
                    if scene:
                        if isinstance(logic_result, AgentResult):
                            scene.editor_result = {
                                "content": logic_result.content,
                                "issues": logic_result.data.get("issues", [])
                            }

                        if isinstance(style_result, AgentResult):
                            scene.stylist_result = {
                                "content": style_result.content,
                                "suggestions": style_result.data.get("suggestions", [])
                            }

                        if isinstance(compliance_result, AgentResult):
                            scene.compliance_result = {
                                "passed": compliance_result.success,
                                "violations": compliance_result.data.get("violations", [])
                            }

                        if isinstance(style_result, AgentResult) and style_result.success:
                            scene.final_content = style_result.content

                        scene.status = SceneStatus.COMPLETED
                        await review_db.commit()

                except Exception as e:
                    self.logger.exception(f"场景 {scene_index} 审阅失败: {str(e)}")

        import asyncio
        review_tasks = [review_single_scene(sr) for sr in successful_scenes]
        await asyncio.gather(*review_tasks, return_exceptions=True)
