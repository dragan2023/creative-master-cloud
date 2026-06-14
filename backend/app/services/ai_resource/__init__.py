"""AI视觉资源生成服务

提供独立的AI视觉资源生成能力，与剧本正文生成流程完全解耦。
用户可基于任意版本剧本(初稿/修正稿/自主修订稿)触发AI资源生成。

@date: 2026-06-04
@version: v1.0.0
"""
from .generator import AIResourceGenerator

__all__ = ["AIResourceGenerator"]
