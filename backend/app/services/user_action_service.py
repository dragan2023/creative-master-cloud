"""
用户行为追踪服务模块

封装用户行为记录的操作。
支持 UI 动作（复制/下载等）和体验事件（阶段04新增）。

@date: 2026-04-02
@version: v4.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case

from app.models.user_action import UserAction, ActionType, EXPERIENCE_EVENTS
from app.core.logger import get_logger

logger = get_logger("user_action_service")


class UserActionService:
    """用户行为追踪服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def track_action(
        self,
        user_id: int,
        generation_id: int,
        module: str,
        action: str,
        content_snippet: Optional[str] = None,
    ):
        """记录用户行为（原有接口，向后兼容）"""
        try:
            action_enum = ActionType(action)
        except ValueError:
            logger.warning(f"无效的行为类型: {action}，使用默认值 COPY")
            action_enum = ActionType.COPY

        action_obj = UserAction(
            user_id=user_id,
            generation_id=generation_id,
            module=module,
            action=action_enum,
            content_snippet=content_snippet,
        )
        self.db.add(action_obj)
        await self.db.commit()
        await self.db.refresh(action_obj)
        logger.debug(f"记录用户行为: user={user_id}, action={action}, module={module}")
        return action_obj

    async def track_experience_event(
        self,
        user_id: int,
        module: str,
        event_type: str,
        *,
        generation_id: Optional[int] = None,
        phase: Optional[str] = None,
        duration_bucket: Optional[str] = None,
        error_category: Optional[str] = None,
        is_retry: bool = False,
        is_first_use: bool = False,
    ):
        """
        记录体验事件（阶段04新增）

        Args:
            user_id: 用户ID
            module: 模块名称
            event_type: 事件类型（creation_started / creation_completed 等）
            generation_id: 关联的生成记录ID
            phase: 创作阶段
            duration_bucket: 时长分桶
            error_category: 错误类别
            is_retry: 是否重试
            is_first_use: 是否首次使用
        """
        try:
            action_enum = ActionType(event_type)
        except ValueError:
            logger.warning(f"无效的体验事件类型: {event_type}，跳过记录")
            return None

        action_obj = UserAction(
            user_id=user_id,
            generation_id=generation_id,
            module=module,
            action=action_enum,
            phase=phase,
            duration_bucket=duration_bucket,
            error_category=error_category,
            is_retry=is_retry,
            is_first_use=is_first_use,
            content_snippet=None,  # 体验事件不采集内容片段
        )
        self.db.add(action_obj)
        await self.db.commit()
        await self.db.refresh(action_obj)
        logger.debug(
            f"记录体验事件: user={user_id}, event={event_type}, "
            f"module={module}, phase={phase}"
        )
        return action_obj

    # ==================== 体验指标聚合查询 ====================

    async def get_experience_metrics(
        self,
        tenant_id: Optional[int] = None,
        days: int = 14,
    ) -> dict:
        """
        按模块聚合体验指标：开始率、完成率、中断率、恢复成功率、平均修订轮次、错误类别分布。

        Args:
            tenant_id: 租户ID（None = 跨租户聚合，仅超级管理员）
            days: 统计最近 N 天
        """
        since = datetime.utcnow() - timedelta(days=days)

        # 基础查询：过滤时间范围和租户
        def _base_query():
            q = select(UserAction).where(UserAction.created_at >= since)
            # 仅统计体验事件
            q = q.where(UserAction.action.in_(EXPERIENCE_EVENTS))
            if tenant_id is not None:
                from app.models.user import User
                q = q.join(User, UserAction.user_id == User.id)
                q = q.where(User.tenant_id == tenant_id)
            return q

        # 按模块聚合各事件计数
        metrics_by_module = {}
        modules = await self._get_distinct_modules(since, tenant_id)

        for module_name in modules:
            base = _base_query().where(UserAction.module == module_name)

            count = lambda action_type: self._count(base, action_type)

            started = await count(ActionType.CREATION_STARTED)
            completed = await count(ActionType.CREATION_COMPLETED)
            cancelled = await count(ActionType.CREATION_CANCELLED)
            recovered = await count(ActionType.ERROR_RECOVERED)
            revision_count = await count(ActionType.REVISION_APPLIED)

            metrics_by_module[module_name] = {
                "creation_started": started,
                "creation_completed": completed,
                "creation_cancelled": cancelled,
                "error_recovered": recovered,
                "revision_applied": revision_count,
                "completion_rate": round(completed / started, 3) if started > 0 else 0,
                "cancellation_rate": round(cancelled / started, 3) if started > 0 else 0,
                "recovery_rate": round(recovered / (cancelled + recovered), 3) if (cancelled + recovered) > 0 else 0,
                "avg_revision_rounds": round(revision_count / completed, 1) if completed > 0 else 0,
            }

        # 错误类别分布（全局）
        error_dist = await self._get_error_distribution(since, tenant_id)

        # 样本量判断
        total_started = sum(m["creation_started"] for m in metrics_by_module.values())

        return {
            "by_module": metrics_by_module,
            "error_distribution": error_dist,
            "total_creation_started": total_started,
            "observation_days": days,
            "sample_sufficient": total_started >= 100,
            "sample_note": (
                "样本量充足（≥100），指标具有统计意义"
                if total_started >= 100
                else f"样本量不足（{total_started}次），指标仅供参考"
            ),
        }

    async def _get_distinct_modules(self, since: datetime, tenant_id: Optional[int]) -> List[str]:
        """获取统计周期内所有有事件的模块名"""
        q = select(UserAction.module).where(
            UserAction.created_at >= since,
            UserAction.action.in_(EXPERIENCE_EVENTS),
        )
        if tenant_id is not None:
            from app.models.user import User
            q = q.join(User, UserAction.user_id == User.id)
            q = q.where(User.tenant_id == tenant_id)
        q = q.distinct()
        result = await self.db.execute(q)
        return [row[0] for row in result.all() if row[0]]

    async def _count(self, base_query, action_type: ActionType) -> int:
        """执行计数查询"""
        q = base_query.where(UserAction.action == action_type)
        subq = select(func.count(UserAction.id)).select_from(q.subquery())
        result = await self.db.execute(subq)
        return result.scalar() or 0

    async def _get_error_distribution(self, since: datetime, tenant_id: Optional[int]) -> dict:
        """获取错误类别分布"""
        from app.models.user import User

        q = select(
            UserAction.error_category,
            func.count(UserAction.id)
        ).where(
            UserAction.created_at >= since,
            UserAction.action == ActionType.ERROR_RECOVERED,
            UserAction.error_category.isnot(None),
        )
        if tenant_id is not None:
            q = q.join(User, UserAction.user_id == User.id)
            q = q.where(User.tenant_id == tenant_id)
        q = q.group_by(UserAction.error_category)

        result = await self.db.execute(q)
        return {row[0]: row[1] for row in result.all()}
