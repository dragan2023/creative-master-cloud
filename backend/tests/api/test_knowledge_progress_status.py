"""Knowledge upload progress has durable, explicit terminal states."""

from app.api.v1.endpoints.knowledge import _state


def test_progress_records_processing_completed_and_failed_states(monkeypatch):
    monkeypatch.setattr(_state, "kb_processing_progress", {})
    monkeypatch.setattr(_state, "_sync_update_kb_progress", lambda *_args: None)

    _state.update_kb_progress(1, "extracting", 30, 2)
    _state.update_kb_progress(2, "done", 100, 6)
    _state.update_kb_progress(3, "failed", 0, 3, error="KB-PARSE-001: invalid")

    assert _state.get_kb_progress(1)["status"] == "processing"
    assert _state.get_kb_progress(2)["status"] == "completed"
    assert _state.get_kb_progress(2)["is_processing"] is False
    assert _state.get_kb_progress(3)["status"] == "failed"
