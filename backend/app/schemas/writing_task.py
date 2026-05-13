"""
多Agent协作文学作品生成系统 - 写作任务Schema

模块: schemas
文件: writing_task.py
功能: 定义写作任务的Pydantic Schema，用于数据验证和序列化

依赖关系:
    - 依赖: pydantic, typing, datetime
    - 被依赖: app.api.v1.writing (API路由)

使用说明:
    本模块定义了多Agent写作系统的所有请求和响应Schema，
    包括任务创建、更新、详情查询等场景的数据结构

创建时间: 2026-03-27
最后修改: 2026-03-27
版本: 1.0.0
作者: AI Assistant

[2026-03-28] 多Agent重构: 完善WSProgressMessage type字段注释，列出所有合法值
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ==================== 请求Schema ====================

class WritingTaskCreate(BaseModel):
    """创建写作任务请求"""
    project_id: int = Field(..., description="关联项目ID")
    config: Dict[str, Any] = Field(
        default_factory=dict, description="任务配置JSON")
    start_from: int = Field(default=1, ge=1, description="起始单元序号")
    unit_count: Optional[int] = Field(
        default=None, ge=1, description="生成单元数(None=全部)")


class WritingTaskUpdate(BaseModel):
    """更新写作任务请求"""
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="任务配置JSON")


class WritingTaskControl(BaseModel):
    """控制写作任务请求（暂停/继续/停止）"""
    action: str = Field(..., description="操作类型: pause/resume/stop")


class WritingTaskContinue(BaseModel):
    """继续生成写作任务请求"""
    unit_count: int = Field(..., ge=1, description="要继续生成的单元数量")


# ==================== 响应Schema ====================

class WritingTaskResponse(BaseModel):
    """写作任务基础响应"""
    id: int = Field(..., description="任务ID")
    uuid: str = Field(..., description="外部引用UUID")
    project_id: int = Field(..., description="关联项目ID")
    user_id: int = Field(..., description="用户ID")
    status: str = Field(..., description="任务状态")
    total_units: int = Field(default=0, description="总单元数")
    completed_units: int = Field(default=0, description="已完成单元数")
    config: Dict[str, Any] = Field(default_factory=dict, description="任务配置")
    total_tokens: int = Field(default=0, description="总token消耗")
    total_cost: float = Field(default=0.0, description="总费用估算")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class WritingUnitResponse(BaseModel):
    """写作单元响应"""
    id: int = Field(..., description="单元ID")
    task_id: int = Field(..., description="关联任务ID")
    unit_index: int = Field(..., description="单元序号")
    unit_title: Optional[str] = Field(default=None, description="单元标题")
    unit_summary: Optional[str] = Field(default=None, description="单元概述")
    status: str = Field(..., description="单元状态")
    word_count: int = Field(default=0, description="字数统计")
    token_count: int = Field(default=0, description="Token消耗")
    duration_ms: int = Field(default=0, description="生成耗时(毫秒)")
    # 质控相关字段 (v2.0新增)
    quality_control_status: Optional[str] = Field(
        default=None, description="质控状态")
    quality_control_score: Optional[float] = Field(
        default=None, description="质控得分")
    quality_control_report: Optional[Dict[str, Any]] = Field(
        default=None, description="质控报告")
    quality_control_fixes: Optional[list] = Field(
        default=None, description="应用的修正列表")
    original_content_before_fix: Optional[str] = Field(
        default=None, description="[DEPRECATED] 修正前的原始内容")
    final_content: Optional[str] = Field(
        default=None, description="最终内容(修正后)")
    # 双版本内容字段 (v3.0新增)
    content_after_generation: Optional[str] = Field(
        default=None, description="LLM初稿(生成完成后存储，永不覆盖)")
    content_after_qc_fix: Optional[str] = Field(
        default=None, description="质控修正稿(质控完成后存储)")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class WritingSceneResponse(BaseModel):
    """写作场景响应"""
    id: int = Field(..., description="场景ID")
    unit_id: int = Field(..., description="关联单元ID")
    scene_index: int = Field(..., description="场景序号")
    scene_title: Optional[str] = Field(default=None, description="场景标题")
    scene_outline: Dict[str, Any] = Field(
        default_factory=dict, description="场景大纲")
    status: str = Field(..., description="场景状态")
    final_content: Optional[str] = Field(default=None, description="最终内容")
    word_count: int = Field(default=0, description="字数统计")
    token_count: int = Field(default=0, description="Token消耗")
    duration_ms: int = Field(default=0, description="生成耗时(毫秒)")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class WritingSceneDetailResponse(WritingSceneResponse):
    """写作场景详细响应（包含Agent结果）"""
    writer_result: Optional[Dict[str, Any]] = Field(
        default=None, description="写手Agent输出")
    editor_result: Optional[Dict[str, Any]] = Field(
        default=None, description="逻辑编辑Agent输出")
    stylist_result: Optional[Dict[str, Any]] = Field(
        default=None, description="风格润色Agent输出")
    compliance_result: Optional[Dict[str, Any]] = Field(
        default=None, description="合规审查Agent输出")


class WritingUnitDetailResponse(WritingUnitResponse):
    """写作单元详细响应（包含场景列表）"""
    scenes_data: List[Dict[str, Any]] = Field(
        default_factory=list, description="场景数据列表")
    scenes: List[WritingSceneResponse] = Field(
        default_factory=list, description="场景列表")
    final_content: Optional[str] = Field(default=None, description="最终合成内容")


class WritingStatsResponse(BaseModel):
    """写作统计响应"""
    total_tokens: int = Field(default=0, description="总token数")
    total_cost: float = Field(default=0.0, description="总费用")
    by_agent: Dict[str, Any] = Field(
        default_factory=dict, description="按Agent统计")

    model_config = {"from_attributes": True}


class WritingTaskDetailResponse(WritingTaskResponse):
    """写作任务详细响应（包含单元列表和统计）"""
    units: List[WritingUnitResponse] = Field(
        default_factory=list, description="单元列表")
    stats_summary: Optional[WritingStatsResponse] = Field(
        default=None, description="统计摘要")


class WritingTaskListResponse(BaseModel):
    """写作任务列表响应"""
    items: List[WritingTaskResponse] = Field(
        default_factory=list, description="任务列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")

    model_config = {"from_attributes": True}


# ==================== WebSocket消息Schema ====================

class WSProgressData(BaseModel):
    """WebSocket进度数据"""
    current_unit: int = Field(default=0, description="当前单元序号")
    total_units: int = Field(default=0, description="总单元数")
    current_scene: int = Field(default=0, description="当前场景序号")
    total_scenes: int = Field(default=0, description="当前单元总场景数")
    status: str = Field(..., description="当前状态")
    progress_percentage: float = Field(default=0.0, description="进度百分比")
    message: str = Field(default="", description="进度消息")


class WSStatusChangeData(BaseModel):
    """WebSocket状态变更数据"""
    old_status: str = Field(..., description="旧状态")
    new_status: str = Field(..., description="新状态")
    message: str = Field(default="", description="状态变更消息")


class WSErrorData(BaseModel):
    """WebSocket错误数据"""
    error_code: str = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误消息")
    recoverable: bool = Field(default=False, description="是否可恢复")


class WSCompleteData(BaseModel):
    """WebSocket完成数据"""
    total_units: int = Field(..., description="完成单元数")
    total_word_count: int = Field(..., description="总字数")
    total_tokens: int = Field(..., description="总Token消耗")
    total_cost: float = Field(..., description="总费用")
    duration_sec: float = Field(..., description="总耗时(秒)")


class WSProgressMessage(BaseModel):
    """WebSocket进度消息

    消息类型(type)合法值:
    - status_change: 任务状态变更
    - task_progress: 整体任务进度
    - unit_progress: 单元进度
    - scene_progress: 场景进度
    - task_complete: 任务完成
    - task_failed: 任务失败
    - error: 错误消息
    - statistics: 统计数据更新
    """
    type: str = Field(..., description="消息类型")
    task_id: str = Field(..., description="任务UUID")
    data: Dict[str, Any] = Field(default_factory=dict, description="消息数据")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="时间戳")

    model_config = {"from_attributes": True}


# ==================== 其他Schema ====================

class WritingCheckpointResponse(BaseModel):
    """检查点响应"""
    id: int = Field(..., description="检查点ID")
    task_id: int = Field(..., description="关联任务ID")
    last_completed_unit: int = Field(default=0, description="最后完成的单元序号")
    last_completed_scene_id: Optional[int] = Field(
        default=None, description="最后完成的场景ID")
    last_operation: Optional[str] = Field(default=None, description="最后执行的操作")
    agent_states: Dict[str, Any] = Field(
        default_factory=dict, description="Agent状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class AgentStatItem(BaseModel):
    """Agent统计项"""
    agent_name: str = Field(..., description="Agent名称")
    model_id: str = Field(..., description="模型ID")
    call_count: int = Field(default=0, description="调用次数")
    total_input_tokens: int = Field(default=0, description="总输入token")
    total_output_tokens: int = Field(default=0, description="总输出token")
    total_tokens: int = Field(default=0, description="总token")
    total_duration_sec: float = Field(default=0.0, description="总耗时")
    total_cost: float = Field(default=0.0, description="总费用")


class WritingTaskStatsDetailResponse(BaseModel):
    """写作任务统计详情响应"""
    task_id: int = Field(..., description="任务ID")
    total_tokens: int = Field(default=0, description="总token数")
    total_cost: float = Field(default=0.0, description="总费用")
    by_agent: List[AgentStatItem] = Field(
        default_factory=list, description="按Agent统计")
    by_scene: Dict[str, Any] = Field(default_factory=dict, description="按场景统计")

    model_config = {"from_attributes": True}
