"""质量管控 v2.0 公共定义 - 请求模型、辅助函数、SSE订阅管理器"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

from pydantic import BaseModel

from ..utils import router, logger


# ==================== 辅助函数 ====================

async def _generate_fixes_for_issues(
    issues: list,
    chapters_data: list,
    project: Any,
    db: Any,
    user_id: int
) -> list:
    """
    为检测结果中的每个问题自动生成修正建议

    Args:
        issues: 问题列表
        chapters_data: 章节数据
        project: 项目对象
        db: 数据库会话
        user_id: 用户ID

    Returns:
        包含修正建议的问题列表
    """
    from app.services.quality_control.fix_generator import QualityFixGenerator

    fix_generator = QualityFixGenerator()
    issues_with_fixes = []

    for issue in issues:
        # 获取章节号
        chapter_number = issue.get('location', {}).get('chapter_number', 0)
        if not chapter_number:
            issues_with_fixes.append(issue)
            continue

        # 查找对应章节内容和单元概述
        chapter_content = ""
        chapter_summary = ""  # 新增：单元概述
        for ch in chapters_data:
            if ch.get('chapter_number') == chapter_number:
                chapter_content = ch.get('content', '')
                chapter_summary = ch.get('summary', '') or ch.get(
                    'unit_summary', '')  # 新增：获取单元概述
                break

        if not chapter_content:
            issues_with_fixes.append(issue)
            continue

        try:
            # 新增：查询知识图谱上下文
            from app.services.quality_control.kg_helper import get_kg_helper
            kg_helper = get_kg_helper()

            issue_category = issue.get('category', '')
            kg_data = kg_helper.query_relevant_entities(
                project_id=getattr(project, 'id', 0),
                unit_index=chapter_number,
                issue_category=issue_category,
                max_entities=15
            )
            knowledge_graph_context = kg_helper.format_kg_context(kg_data)

            logger.info(
                f"[修正建议] 知识图谱查询完成: issue={issue.get('id')}, "
                f"人物={len(kg_data.get('characters', []))}, "
                f"事件={len(kg_data.get('events', []))}"
            )

            # 调用LLM生成修正建议
            fix_result = await fix_generator.generate_fix(
                issue=issue,
                chapter_content=chapter_content,
                unit_summary=chapter_summary,
                knowledge_graph_context=knowledge_graph_context,
                character_profiles=getattr(
                    project, 'character_profiles', []) or [],
                worldview_settings=getattr(
                    project, 'worldview_settings', {}) or {},
                db=db,
                user_id=user_id
            )

            # 将修正建议添加到问题中
            issue['auto_fix'] = fix_result
            issues_with_fixes.append(issue)

            logger.debug(
                f"[修正建议] 为问题 {issue.get('id')} 生成修正建议成功, "
                f"confidence={fix_result.get('confidence', 0):.2f}"
            )
        except Exception as e:
            logger.warning(f"[修正建议] 为问题 {issue.get('id')} 生成修正建议失败: {e}")
            issues_with_fixes.append(issue)

    return issues_with_fixes


# ==================== 请求/响应模型 ====================

class ApplyFixRequest(BaseModel):
    """应用修正请求"""
    issue_id: str                    # 问题ID
    auto_fix: Optional[Dict[str, Any]] = None  # 自动修正方案(可选,如果不提供则调用LLM生成)
    chapter_number: int              # 单元号
    project_id: Optional[int] = None  # 项目ID(用于获取上下文)


class GenerateFixRequest(BaseModel):
    """生成修正方案请求"""
    issue_id: str                    # 问题ID
    chapter_number: int              # 单元号
    category: str                    # 问题分类
    description: str                 # 问题描述
    project_id: int = 0              # 项目ID(可选，默认为0表示大纲阶段)
    chapter_content: str = ""        # 单元内容(大纲阶段前端传递)
    global_outline: str = ""         # 全局大纲(大纲阶段前端传递)


class ReAnalyzeRequest(BaseModel):
    """重新分析请求"""
    project_id: int                  # 项目ID
    chapter_number: Optional[int] = None  # 单元号(可选,不指定则分析所有)
    dimensions: Optional[List[str]] = None  # 分析维度(可选)
    depth: str = "standard"          # 分析深度


class CancelQCRequest(BaseModel):
    """取消质控检测请求"""
    project_id: int                  # 项目ID


class FeedbackRequest(BaseModel):
    """用户反馈请求"""
    issue_id: str                    # 问题ID
    dimension: str                   # 维度
    category: str                    # 分类
    feedback_type: str               # 反馈类型 (accepted/ignored/false_positive)
    comment: str = ""                # 用户备注


class ImportedOutlineAutoReviseRequest(BaseModel):
    """导入大纲自动质控修正请求（v2.3新增）"""
    outline_content: str             # 导入的大纲内容
    dimensions: Optional[List[str]] = None  # 分析维度（可选，默认四维度）
    depth: str = "standard"          # 分析深度（默认standard以确保LLM深度分析）


class UnitQualityControlRequest(BaseModel):
    """单单元质控检测请求（v2.0新增 - 实时质控）"""
    project_id: int                  # 项目ID
    unit_index: int                  # 单元序号
    content: str                     # 单元内容
    dimensions: Optional[List[str]] = None  # 分析维度（可选）
    depth: str = "standard"          # 分析深度
    auto_fix: bool = True            # 是否自动修正
    auto_fix_threshold: float = 0.8  # 自动修正置信度阈值


class GlobalOutlineQCRequest(BaseModel):
    """全局大纲质量检测请求"""
    dimensions: Optional[List[str]] = None  # 分析维度(可选,默认全部四维度)
    depth: str = "standard"          # 分析深度(quick/standard/deep)
    existing_outline: Optional[str] = ""  # 全局大纲内容(两阶段模式由前端传递)


class GlobalOutlineReviseRequest(BaseModel):
    """全局大纲修正请求"""
    quality_report: Dict[str, Any]   # 质控报告
    issues_to_fix: List[str]         # 需要修正的问题ID列表


# ==================== SSE实时推送 (v1.1新增) ====================

class QCProgressSubscriber:
    """质控进度SSE订阅管理器

    v1.1新增: 资源清理机制
    - 订阅数上限: 每个任务最多5个订阅者
    - 任务超时: 1小时后自动清理
    """

    MAX_SUBSCRIBERS_PER_TASK = 5  # 每个任务最多5个订阅者
    TASK_TIMEOUT = 3600  # 1小时后自动清理

    def __init__(self):
        # task_id -> {"queues": list, "created_at": datetime}
        self._subscribers: Dict[str, dict] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """订阅任务进度

        Raises:
            ValueError: 订阅数已达上限
        """
        # 清理过期任务
        self._cleanup_expired_tasks()

        if task_id not in self._subscribers:
            self._subscribers[task_id] = {
                "queues": [],
                "created_at": datetime.now()
            }

        # 检查订阅数上限
        if len(self._subscribers[task_id]["queues"]) >= self.MAX_SUBSCRIBERS_PER_TASK:
            logger.warning(f"[SSE订阅] 任务 {task_id} 订阅数已达上限")
            raise ValueError(f"任务 {task_id} 订阅数已达上限")

        queue = asyncio.Queue()
        self._subscribers[task_id]["queues"].append(queue)
        logger.info(
            f"[SSE订阅] task_id={task_id}, 当前订阅数: {len(self._subscribers[task_id]['queues'])}")
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue):
        """取消订阅"""
        if task_id in self._subscribers:
            if queue in self._subscribers[task_id]["queues"]:
                self._subscribers[task_id]["queues"].remove(queue)
            if not self._subscribers[task_id]["queues"]:
                del self._subscribers[task_id]
                logger.info(f"[SSE取消订阅] 任务 {task_id} 已清理")
            else:
                logger.info(
                    f"[SSE取消订阅] task_id={task_id}, 剩余订阅数: {len(self._subscribers[task_id]['queues'])}")

    async def publish(self, task_id: str, event: Dict):
        """发布进度事件"""
        # 触发清理过期任务(防止内存泄漏)
        self._cleanup_expired_tasks()

        if task_id in self._subscribers:
            for queue in self._subscribers[task_id]["queues"]:
                try:
                    await queue.put(event)
                except Exception as e:
                    logger.warning(f"[SSE发布] 队列推送失败: {e}")

    def _cleanup_expired_tasks(self):
        """清理过期任务"""
        now = datetime.now()
        expired_tasks = []

        for task_id, data in list(self._subscribers.items()):
            created_at = data.get("created_at", now)
            if (now - created_at).total_seconds() > self.TASK_TIMEOUT:
                expired_tasks.append(task_id)

        for task_id in expired_tasks:
            del self._subscribers[task_id]
            logger.info(f"[SSE清理] 过期任务已清理: {task_id}")

    def get_task_count(self) -> int:
        """获取当前任务数"""
        return len(self._subscribers)

    def get_total_subscribers(self) -> int:
        """获取总订阅者数"""
        return sum(len(data["queues"]) for data in self._subscribers.values())


# 全局订阅实例
_qc_subscriber = QCProgressSubscriber()


def get_qc_subscriber() -> QCProgressSubscriber:
    """获取质控SSE订阅器单例"""
    return _qc_subscriber


async def publish_qc_progress(
    task_id: str,
    event_type: str,
    dimension: str = None,
    status: str = None,
    progress: float = None,
    message: str = None,
    data: Dict = None
):
    """
    发布质控进度事件(供业务逻辑调用)

    Args:
        task_id: 任务ID
        event_type: 事件类型(started/progress/completed/error)
        dimension: 维度名称
        status: 状态(running/success/failed)
        progress: 进度(0-100)
        message: 消息
        data: 附加数据
    """
    event = {
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id
    }

    if dimension:
        event["dimension"] = dimension
    if status:
        event["status"] = status
    if progress is not None:
        event["progress"] = progress
    if message:
        event["message"] = message
    if data:
        event["data"] = data

    await _qc_subscriber.publish(task_id, event)
    logger.debug(
        f"[SSE发布] task_id={task_id}, type={event_type}, "
        f"dimension={dimension}, progress={progress}"
    )
