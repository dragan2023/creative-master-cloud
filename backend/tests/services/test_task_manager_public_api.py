"""Public import contract for the split task-manager database helpers."""

from app.services import task_manager as task_manager_module
from app.services import task_manager_db


def test_task_manager_exports_session_factory_from_db_module():
    assert task_manager_module.set_session_factory is task_manager_db.set_session_factory
    assert not hasattr(task_manager_module, "set_novel_project_repo")
