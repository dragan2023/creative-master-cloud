"""
写作流水线

连接TaskManager和OrchestratorAgent，管理写作任务的执行生命周期

从原始 pipeline.py (1215行) 拆分为以下模块：
- _base.py: PipelineBase - 基类及生命周期管理
- _config.py: PipelineConfigMixin - 模型配置加载
- _context_builder.py: ContextBuilderMixin - 上下文构建
- _execute.py: PipelineExecuteMixin - 执行方法
- _control.py: PipelineControlMixin - 中断/续传/继续生成

@date: 2026-04-24
@version: v1.0.0
"""
from ._base import PipelineBase
from ._config import PipelineConfigMixin
from ._context_builder import ContextBuilderMixin
from ._execute import PipelineExecuteMixin
from ._control import PipelineControlMixin


class WritingPipeline(PipelineControlMixin):
    """写作流水线 - 管理单个写作任务的执行

    继承链: PipelineControlMixin -> PipelineExecuteMixin -> ContextBuilderMixin -> PipelineConfigMixin -> PipelineBase
    """
    pass


__all__ = ["WritingPipeline"]
