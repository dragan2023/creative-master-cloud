# -*- coding: utf-8 -*-
"""
Repository 统一导出
"""
from app.repositories.novel_project import NovelProjectRepository
from app.repositories.user import UserRepository
from app.repositories.writing_task import WritingTaskRepository

__all__ = [
    "NovelProjectRepository",
    "UserRepository",
    "WritingTaskRepository",
]
