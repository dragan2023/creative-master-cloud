# -*- coding: utf-8 -*-
"""
任务状态机单一迁移表测试

覆盖：正常完成、用户取消、服务重启中断、重复终态写入、非法 completed -> running。
"""
import os
import sys

import pytest

# 确保 backend 目录在 Python 路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.exceptions import InvalidTaskTransitionException
from app.models.writing_task import TaskStatus, WritingTask
from app.services.task_manager_constants import (
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_INTERRUPTED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    assert_task_transition_allowed,
    is_task_transition_allowed,
    is_terminal_task_status,
)


class TestAllowedTransitions:
    """迁移表基础规则"""

    def test_pending_to_running_is_allowed(self):
        assert is_task_transition_allowed(TASK_STATUS_PENDING, TASK_STATUS_RUNNING)

    def test_running_to_completed_is_allowed(self):
        assert is_task_transition_allowed(TASK_STATUS_RUNNING, TASK_STATUS_COMPLETED)

    def test_running_to_interrupted_is_allowed(self):
        assert is_task_transition_allowed(TASK_STATUS_RUNNING, TASK_STATUS_INTERRUPTED)

    def test_pending_to_cancelled_is_allowed(self):
        assert is_task_transition_allowed(TASK_STATUS_PENDING, TASK_STATUS_CANCELLED)

    def test_completed_to_running_is_illegal(self):
        assert not is_task_transition_allowed(TASK_STATUS_COMPLETED, TASK_STATUS_RUNNING)

    def test_interrupted_to_pending_is_allowed_for_resume(self):
        assert is_task_transition_allowed(TASK_STATUS_INTERRUPTED, TASK_STATUS_PENDING)

    def test_failed_to_pending_is_allowed_for_retry(self):
        assert is_task_transition_allowed(TASK_STATUS_FAILED, TASK_STATUS_PENDING)

    def test_completed_to_pending_is_allowed_for_continue(self):
        assert is_task_transition_allowed(TASK_STATUS_COMPLETED, TASK_STATUS_PENDING)

    def test_terminal_states_are_terminal(self):
        for status in (TASK_STATUS_COMPLETED, TASK_STATUS_FAILED,
                       TASK_STATUS_CANCELLED, TASK_STATUS_INTERRUPTED):
            assert is_terminal_task_status(status)


class TestAssertTransition:
    """assert_task_transition_allowed 行为"""

    def test_illegal_completed_to_running_raises(self):
        with pytest.raises(InvalidTaskTransitionException) as exc_info:
            assert_task_transition_allowed(TASK_STATUS_COMPLETED, TASK_STATUS_RUNNING)
        assert exc_info.value.from_status == TASK_STATUS_COMPLETED
        assert exc_info.value.to_status == TASK_STATUS_RUNNING

    def test_duplicate_terminal_write_is_rejected(self):
        # completed -> completed 属于同态写入，非合法迁移，应被拒绝
        with pytest.raises(InvalidTaskTransitionException):
            assert_task_transition_allowed(TASK_STATUS_COMPLETED, TASK_STATUS_COMPLETED)

    def test_reason_is_carried_into_details(self):
        with pytest.raises(InvalidTaskTransitionException) as exc_info:
            assert_task_transition_allowed(
                TASK_STATUS_FAILED, TASK_STATUS_RUNNING, reason="非法恢复"
            )
        assert exc_info.value.details.get("reason") == "非法恢复"

    def test_enum_input_is_normalized(self):
        result = assert_task_transition_allowed(TaskStatus.RUNNING, TaskStatus.COMPLETED)
        assert result == TASK_STATUS_COMPLETED


class TestModelTransitionTo:
    """WritingTask.transition_to 落地行为（无需数据库）"""

    def test_normal_completion(self):
        task = WritingTask(status=TaskStatus.RUNNING)
        task.transition_to(TaskStatus.COMPLETED)
        assert task.status == TaskStatus.COMPLETED
        assert task.end_time is not None

    def test_user_cancel(self):
        task = WritingTask(status=TaskStatus.RUNNING)
        task.transition_to(TaskStatus.CANCELLED, reason="用户取消")
        assert task.status == TaskStatus.CANCELLED
        assert task.end_time is not None

    def test_server_restart_interrupt_records_reason(self):
        task = WritingTask(status=TaskStatus.RUNNING)
        task.transition_to(TaskStatus.INTERRUPTED, reason="server_restarted")
        assert task.status == TaskStatus.INTERRUPTED
        assert task.error_message == "server_restarted"
        assert task.end_time is not None

    def test_resume_prepares_a_new_run(self):
        task = WritingTask(status=TaskStatus.INTERRUPTED)
        task.end_time = object()
        task.error_message = "server_restarted"

        task.transition_to(TaskStatus.PENDING)

        assert task.status == TaskStatus.PENDING
        assert task.end_time is None
        assert task.error_message is None

    def test_illegal_completed_to_running_keeps_state(self):
        task = WritingTask(status=TaskStatus.COMPLETED)
        with pytest.raises(InvalidTaskTransitionException):
            task.transition_to(TaskStatus.RUNNING)
        # 原状态保持不变
        assert task.status == TaskStatus.COMPLETED

    def test_duplicate_terminal_write_keeps_end_time(self):
        task = WritingTask(status=TaskStatus.RUNNING)
        task.transition_to(TaskStatus.COMPLETED)
        first_end_time = task.end_time
        with pytest.raises(InvalidTaskTransitionException):
            task.transition_to(TaskStatus.COMPLETED)
        assert task.end_time == first_end_time


class TestProductionTransitionHelper:
    def test_transition_helper_updates_model_and_emits_status_event(self):
        from app.services.writing_engine.task_lifecycle import transition_task

        class _WebSocketManager:
            def __init__(self):
                self.events = []

            async def send_status_change(self, task_id, old_status, new_status):
                self.events.append((task_id, old_status, new_status))

        async def scenario():
            task = WritingTask(id=18, status=TaskStatus.FAILED)
            manager = _WebSocketManager()

            await transition_task(task, TaskStatus.PENDING, manager)

            assert task.status == TaskStatus.PENDING
            assert manager.events == [(18, TaskStatus.FAILED, TaskStatus.PENDING)]

        import asyncio
        asyncio.run(scenario())
