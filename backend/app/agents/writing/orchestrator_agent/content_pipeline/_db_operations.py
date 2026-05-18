"""
content_pipeline - 数据库操作模块

包含 ContentPipelineMixin 的所有单元/场景数据库操作方法。

@date: 2026-04-24
@version: v3.0.0
"""
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.writing.base_agent import AgentContext
from app.models.writing_scene import WritingScene, SceneStatus
from app.models.writing_unit import WritingUnit, UnitStatus


class DBOperationsMixin:
    """数据库操作 Mixin

    提供单元/场景的 CRUD 操作方法，包括：
    - _get_or_create_unit
    - _get_or_create_scene
    - _get_or_create_scene_with_db
    - _get_scene_by_id
    - _get_scene_by_id_with_db
    """

    # 由主类提供的属性
    db: Any
    logger: Any
    _current_task: Optional[Any]

    async def _get_or_create_unit(self, context: AgentContext, unit_index: int) -> WritingUnit:
        """获取或创建单元记录"""
        if not self._current_task:
            raise ValueError("当前任务未设置")

        result = await self.db.execute(
            select(WritingUnit).where(
                WritingUnit.task_id == self._current_task.id,
                WritingUnit.unit_index == unit_index
            ).limit(1)
        )
        unit = result.scalar_one_or_none()

        if unit:
            return unit

        unit_title = ""
        unit_summary = ""

        # 优先级1：从 context.config.unit_summaries 获取
        unit_summaries = context.config.get("unit_summaries", {})
        self.logger.info(
            f"[_get_or_create_unit] 单元 {unit_index}: 尝试从 unit_summaries 获取，可用单元数: {len(unit_summaries)}")
        if unit_summaries and isinstance(unit_summaries, dict):
            unit_data = (unit_summaries.get(str(unit_index))
                         or unit_summaries.get(unit_index)
                         or unit_summaries.get(f"{unit_index:04d}"))
            if unit_data:
                unit_title = unit_data.get("title", "")
                unit_summary = unit_data.get("summary", "")
                self.logger.info(
                    f"[_get_or_create_unit] 从 unit_summaries 获取单元 {unit_index} 成功: title={unit_title}, summary_len={len(unit_summary)}")
            else:
                self.logger.warning(
                    f"[_get_or_create_unit] 单元 {unit_index} 在 unit_summaries 中未找到，可用keys: {list(unit_summaries.keys())[:5]}...")

        # 优先级2：从 context.outline.chapters 获取
        if (not unit_title or not unit_summary) and context.outline:
            chapters = context.outline.get("chapters", [])
            if 0 <= unit_index - 1 < len(chapters):
                chapter = chapters[unit_index - 1]
                if not unit_title:
                    unit_title = chapter.get("title", "")
                if not unit_summary:
                    unit_summary = chapter.get("summary", "")
                self.logger.info(
                    f"[_get_or_create_unit] 从 outline.chapters 获取单元 {unit_index}: title={unit_title}")

        # 根据 content_type 确定默认单元标题
        content_type = context.config.get("content_type", "novel")
        if content_type == "series_script":
            default_title = f"第{unit_index}集"
        elif content_type == "movie_script":
            default_title = f"第{unit_index}场"
        else:
            default_title = f"第{unit_index}章"

        unit = WritingUnit(
            task_id=self._current_task.id,
            unit_index=unit_index,
            unit_title=unit_title or default_title,
            unit_summary=unit_summary,
            status=UnitStatus.PENDING
        )
        self.db.add(unit)
        await self.db.commit()
        await self.db.refresh(unit)

        self.logger.info(
            f"[_get_or_create_unit] 创建单元 {unit_index}: title={unit_title}, summary_len={len(unit_summary)}")

        return unit

    async def _get_or_create_scene(
        self,
        unit_id: int,
        scene_index: int,
        scene_data: Dict
    ) -> WritingScene:
        """获取或创建场景记录"""
        result = await self.db.execute(
            select(WritingScene).where(
                WritingScene.unit_id == unit_id,
                WritingScene.scene_index == scene_index
            ).limit(1)
        )
        scene = result.scalar_one_or_none()

        if scene:
            return scene

        scene = WritingScene(
            unit_id=unit_id,
            scene_index=scene_index,
            scene_title=scene_data.get("scene_title", f"场景{scene_index}"),
            scene_outline=scene_data,
            status=SceneStatus.PENDING
        )
        self.db.add(scene)
        await self.db.commit()
        await self.db.refresh(scene)

        return scene

    async def _get_or_create_scene_with_db(
        self,
        db: AsyncSession,
        unit_id: int,
        scene_index: int,
        scene_data: Dict
    ) -> WritingScene:
        """获取或创建场景记录（使用指定数据库会话）"""
        result = await db.execute(
            select(WritingScene).where(
                WritingScene.unit_id == unit_id,
                WritingScene.scene_index == scene_index
            ).limit(1)
        )
        scene = result.scalar_one_or_none()

        if scene:
            return scene

        scene = WritingScene(
            unit_id=unit_id,
            scene_index=scene_index,
            scene_title=scene_data.get("scene_title", f"场景{scene_index}"),
            scene_outline=scene_data,
            status=SceneStatus.PENDING
        )
        db.add(scene)
        await db.commit()
        await db.refresh(scene)

        return scene

    async def _get_scene_by_id(self, scene_id: int) -> Optional[WritingScene]:
        """通过ID获取场景"""
        result = await self.db.execute(
            select(WritingScene).where(WritingScene.id == scene_id).limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_scene_by_id_with_db(self, db: AsyncSession, scene_id: int) -> Optional[WritingScene]:
        """通过ID获取场景（使用指定数据库会话）"""
        result = await db.execute(
            select(WritingScene).where(WritingScene.id == scene_id).limit(1)
        )
        return result.scalar_one_or_none()
