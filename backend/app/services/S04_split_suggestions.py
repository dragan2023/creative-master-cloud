# -*- coding: utf-8 -*-
"""
S-04 拆分建议：超大文件拆分方案

标记说明：
S-04 = 建议拆分（文件 > 500行），因复杂度高或需专项工作，先记录方案后实施。
"""

SPLIT_SUGGESTIONS = {
    "content_pipeline.py": {
        "path": "backend/app/agents/writing/orchestrator_agent/content_pipeline.py",
        "lines": 1333,
        "status": "建议拆分",
        "plan": "拆分为 content_pipeline/ 包结构:",
        "sub_modules": [
            "content_pipeline/_content_generation.py — 正文生成逻辑",
            "content_pipeline/_context_building.py — 上下文构建",
            "content_pipeline/_review.py — 内容审校",
            "content_pipeline/_scene_operations.py — 场景操作（会审Agent编排）",
            "content_pipeline/__init__.py — 重新导出 ContentPipelineMixin",
        ],
        "risk": "高 - 涉及多Agent交互，需完整回归测试",
    },
    "monitoring.py": {
        "path": "backend/app/agents/writing/orchestrator_agent/monitoring.py",
        "lines": "~1200（54.5KB）",
        "status": "建议拆分",
        "plan": "拆分为 monitoring/ 包结构:",
        "sub_modules": [
            "monitoring/_metrics.py — 指标收集与聚合",
            "monitoring/_report.py — 报告生成",
            "monitoring/_alert.py — 告警规则",
            "monitoring/__init__.py — 重新导出",
        ],
        "risk": "中 - 逻辑相对独立",
    },
    "_execute.py": {
        "path": "backend/app/services/writing_engine/pipeline/_execute.py",
        "lines": 569,
        "status": "建议拆分（低优先）",
        "plan": "将过长的方法提取到单独文件",
        "risk": "低 - Mixin模式天然适合拆分",
    },
    "task_manager.py": {
        "path": "backend/app/services/task_manager.py",
        "lines": 606,
        "status": "已部分优化（常量/取消令牌已提取），仍超500行",
        "plan": "未来可考虑将 SSE 管理、TaskManager 核心方法进一步拆分",
        "risk": "低",
    },
}
