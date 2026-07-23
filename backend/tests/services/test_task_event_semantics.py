# -*- coding: utf-8 -*-
"""
统一任务事件与错误语义测试

覆盖：
    - TaskEvent 固定结构与默认值；
    - Provider 超时/限流/鉴权/内容解析分别映射为明确错误码与 retryable 值；
    - 已是领域异常时 classify_provider_error 原样透传；
    - WebSocket 事件序号 task_id + sequence 单调递增，且不同任务互相独立。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.exceptions import (
    ErrorCode,
    ProviderRateLimitException,
    classify_provider_error,
)
from app.schemas.task_event import TaskEvent, build_error_event
from app.services.writing_engine.websocket_manager import WebSocketManager


class TestTaskEventSchema:
    """TaskEvent 固定结构"""

    def test_fixed_structure_serialization(self):
        event = TaskEvent(
            task_id=42, sequence=17, type="task_progress",
            status="running", progress=0.45, message="正在生成第 3 章",
        )
        dumped = event.model_dump()
        for key in ("task_id", "sequence", "type", "status", "progress", "message", "retryable"):
            assert key in dumped
        assert dumped["retryable"] is False

    def test_retryable_defaults_false(self):
        event = TaskEvent(task_id=1, sequence=1, type="status_change")
        assert event.retryable is False


class TestProviderErrorMapping:
    """Provider 错误分类与 retryable 语义"""

    def test_timeout_is_retryable(self):
        event = build_error_event(1, 1, TimeoutError("read timed out"))
        assert event.error_code == ErrorCode.PROVIDER_TIMEOUT.value
        assert event.retryable is True

    def test_rate_limit_is_retryable(self):
        event = build_error_event(1, 2, Exception("HTTP 429 Too Many Requests"))
        assert event.error_code == ErrorCode.PROVIDER_RATE_LIMITED.value
        assert event.retryable is True

    def test_auth_is_not_retryable(self):
        event = build_error_event(1, 3, Exception("401 Unauthorized: invalid api key"))
        assert event.error_code == ErrorCode.PROVIDER_AUTH_FAILED.value
        assert event.retryable is False

    def test_content_parse_is_not_retryable(self):
        event = build_error_event(1, 4, ValueError("Expecting value: JSON decode error"))
        assert event.error_code == ErrorCode.CONTENT_PARSE_FAILED.value
        assert event.retryable is False

    def test_unknown_falls_back_to_llm_service_error(self):
        event = build_error_event(1, 5, Exception("something odd happened"))
        assert event.error_code == ErrorCode.LLM_SERVICE_ERROR.value
        assert event.retryable is False

    def test_existing_domain_exception_is_passed_through(self):
        original = ProviderRateLimitException()
        classified = classify_provider_error(original)
        assert classified is original


class TestSequenceMonotonic:
    """事件序号单调递增"""

    def test_next_sequence_monotonic_per_task(self):
        manager = WebSocketManager()
        assert manager._next_sequence(1) == 1
        assert manager._next_sequence(1) == 2
        assert manager._next_sequence(1) == 3

    def test_sequences_are_independent_across_tasks(self):
        manager = WebSocketManager()
        assert manager._next_sequence(1) == 1
        assert manager._next_sequence(2) == 1
        assert manager._next_sequence(1) == 2
        assert manager._next_sequence(2) == 2

    def test_broadcast_stamps_monotonic_sequence(self):
        async def scenario():
            manager = WebSocketManager()

            sent_messages = []

            class _FakeWebSocket:
                async def accept(self):
                    return None

                async def send_text(self, text):
                    import json
                    sent_messages.append(json.loads(text))

            ws = _FakeWebSocket()
            await manager.connect(7, ws)

            await manager.send_status_change(7, "pending", "running")
            await manager.send_status_change(7, "running", "completed")

            assert [m["sequence"] for m in sent_messages] == [1, 2]
            assert all(m["task_id"] == 7 for m in sent_messages)

        asyncio.run(scenario())

    def test_status_change_uses_the_task_event_contract(self):
        async def scenario():
            manager = WebSocketManager()
            sent_messages = []

            class _FakeWebSocket:
                async def accept(self):
                    return None

                async def send_text(self, text):
                    import json
                    sent_messages.append(json.loads(text))

            await manager.connect(9, _FakeWebSocket())
            await manager.send_status_change(9, "running", "completed")

            assert sent_messages == [{
                "task_id": 9,
                "sequence": 1,
                "type": "status_change",
                "status": "completed",
                "old_status": "running",
                "retryable": False,
            }]

        asyncio.run(scenario())


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-v"]))
