"""QA测试路由的双重环境门禁。"""

from fastapi import FastAPI


def mount_qa_test_hooks(
    application: FastAPI,
    *,
    qa_flag: str | None,
    runtime_env: str,
) -> bool:
    """仅显式QA开关且运行环境严格为test时挂载测试路由。"""
    if qa_flag != "1" or runtime_env != "test":
        return False

    from app.api.v1.endpoints import qa_test_hooks

    application.include_router(qa_test_hooks.router, prefix="/api/v1")
    return True
