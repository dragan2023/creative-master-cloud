"""质量管控 v2.0 公共定义 - 请求模型、辅助函数、SSE订阅管理器"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

from pydantic import BaseModel

from ..utils import router, logger


# ==================== 辅助函数 ====================

def _normalize_chapter_number(raw_value: Any) -> int:
    """
    归一化章节号为 int 类型
    
    LLM 可能返回多种格式的 chapter_number：
    - int: 1 → 1
    - str: "1" → 1
    - str: "第1单元" → 1
    - str: "1-1" → 1（取第一个数字）
    - None/0 → 0
    
    Args:
        raw_value: 原始值
        
    Returns:
        int 类型的章节号，无法解析时返回 0
    """
    if raw_value is None:
        return 0
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, float):
        return int(raw_value)
    
    # 字符串类型：尝试提取第一个数字
    import re
    match = re.search(r'(\d+)', str(raw_value))
    if match:
        return int(match.group(1))
    return 0


async def _generate_fixes_for_issues(
    issues: list,
    chapters_data: list,
    project: Any,
    db: Any,
    user_id: int,
    content_type: str = "novel"
) -> list:
    """
    为检测结果中的每个问题自动生成修正建议
    
    v2.2优化：按章节分组，批量调用LLM修正，显著提升效率
    v2.6: 新增 content_type 参数，用于按内容类型选择对应的修正提示词
    v2.7: 修复——对series_script/movie_script使用批量修正（合并同一章节所有问题一次性修正），
          与novel类型的批量修正流程保持一致，避免逐个问题分别调用LLM

    Args:
        issues: 问题列表
        chapters_data: 章节数据
        project: 项目对象
        db: 数据库会话
        user_id: 用户ID
        content_type: 内容类型 (novel/series_script/movie_script)，用于选择提示词

    Returns:
        包含修正建议的问题列表
    """
    from app.services.quality_control.fix_generator import QualityFixGenerator

    # v2.7: 确保 content_type 不为 None（旧项目可能 content_type 为 NULL）
    content_type = content_type or "novel"

    # v3.2: 过滤掉合规提醒类问题（敏感实体检测），仅提醒不自动修正
    compliance_issues = [i for i in issues if i.get('is_compliance')]
    fixable_issues = [i for i in issues if not i.get('is_compliance')]
    
    if compliance_issues:
        logger.info(
            f"[批量修正] 跳过 {len(compliance_issues)} 个合规提醒问题（仅提醒不自动修正）: "
            f"IDs={[i.get('id') for i in compliance_issues]}"
        )
        # 合规类问题不生成 auto_fix
        for issue in compliance_issues:
            issue['auto_fix'] = None
    
    # 如果没有可修正的问题，直接返回（合规类已标记 auto_fix=None）
    if not fixable_issues:
        logger.info("[批量修正] 所有问题均为合规提醒，无需生成修正方案")
        return issues

    fix_generator = QualityFixGenerator()
    
    # 按章节号分组问题（仅处理非合规问题）
    # [v2.7修复] 单单元场景（chapters_data仅1条）：强制所有issue合为一组，
    # 避免因LLM返回不一致的chapter_number导致issue被分到不同组，
    # 不同组各自调用generate_batch_fix产生不同的fixed_content，
    # 在应用阶段造成内容互相覆盖的"乒乓效应"。
    is_single_unit = len(chapters_data) == 1
    if is_single_unit:
        # 单单元场景：使用chapters_data[0]的chapter_number作为统一分组键
        unified_chapter = chapters_data[0].get('chapter_number', 1)
        if not unified_chapter:
            unified_chapter = 1
        issues_by_chapter = {unified_chapter: list(fixable_issues)}
        logger.info(
            f"[批量修正] 单单元场景，{len(fixable_issues)}个issue强制合组: "
            f"chapter={unified_chapter}"
        )
    else:
        issues_by_chapter = {}
        for issue in fixable_issues:
            chapter_number = (
                issue.get('location', {}).get('chapter_number') or
                issue.get('location', {}).get('chapter') or
                issue.get('location', {}).get('start_chapter') or
                0
            )
            
            # 归一化 chapter_number 为 int（LLM 可能返回字符串 "1"、"第1单元" 等格式）
            chapter_number = _normalize_chapter_number(chapter_number)
            
            # 如果 chapter_number 为 0，尝试从 chapters_data 推断 fallback
            if not chapter_number and chapters_data:
                fallback = chapters_data[0].get('chapter_number')
                if fallback:
                    logger.warning(
                        f"[批量修正] issue {issue.get('id', '?')} 缺少chapter_number，"
                        f"使用fallback chapter={fallback}"
                    )
                    chapter_number = int(fallback) if not isinstance(fallback, int) else fallback
            
            if chapter_number:
                if chapter_number not in issues_by_chapter:
                    issues_by_chapter[chapter_number] = []
                issues_by_chapter[chapter_number].append(issue)
            else:
                # 没有章节号且无 fallback 的问题单独处理
                if 0 not in issues_by_chapter:
                    issues_by_chapter[0] = []
                issues_by_chapter[0].append(issue)
    
    # 对每个章节批量修正
    for chapter_number, chapter_issues in issues_by_chapter.items():
        if chapter_number == 0:
            # 没有章节号且无 fallback 的问题，跳过并记录日志
            logger.warning(
                f"[批量修正] {len(chapter_issues)}个问题缺少chapter_number且"
                f"无chapters_data fallback可用，跳过修正生成"
            )
            for issue in chapter_issues:
                issue['auto_fix'] = None
            continue
        
        # 查找章节内容和单元概述
        chapter_content = ""
        chapter_summary = ""
        matched_chapter = None
        for ch in chapters_data:
            # 归一化比较：兼容 LLM 返回字符串 "1" 与 DB 中的整数 1
            if str(ch.get('chapter_number')) == str(chapter_number):
                chapter_content = ch.get('content', '')
                chapter_summary = ch.get('summary', '') or ch.get('unit_summary', '')
                matched_chapter = ch
                break
        
        # 单单元质控兜底：chapters_data 只有 1 条记录时，直接使用它
        if not chapter_content and len(chapters_data) == 1:
            first_ch = chapters_data[0]
            logger.info(
                f"[批量修正] 章节{chapter_number}在chapters_data中未精确匹配"
                f"(issues中的chapter_number={chapter_number}, "
                f"chapters_data中chapter_number={first_ch.get('chapter_number')})，"
                f"单单元模式兜底使用该章节内容"
            )
            chapter_content = first_ch.get('content', '')
            chapter_summary = first_ch.get('summary', '') or first_ch.get('unit_summary', '')
            matched_chapter = first_ch
        
        # 多单元兜底：尝试从相邻章节获取内容
        if not chapter_content and len(chapters_data) > 1:
            for ch in chapters_data:
                content = ch.get('content', '')
                if content:
                    logger.warning(
                        f"[批量修正] 章节{chapter_number}精确匹配失败且目标章节内容为空，"
                        f"降级使用章节{ch.get('chapter_number')}的内容"
                    )
                    chapter_content = content
                    chapter_summary = ch.get('summary', '') or ch.get('unit_summary', '')
                    matched_chapter = ch
                    break
        
        if not chapter_content:
            logger.warning(
                f"[批量修正] 章节{chapter_number}内容为空，跳过 "
                f"(chapters_data共{len(chapters_data)}条，"
                f"章节号列表={[c.get('chapter_number') for c in chapters_data]})"
            )
            for issue in chapter_issues:
                issue['auto_fix'] = None
            continue
        
        try:
            # 查询知识图谱上下文
            from app.services.quality_control.kg_helper import get_kg_helper
            kg_helper = get_kg_helper()
            
            # 使用第一个问题的类别查询
            issue_category = chapter_issues[0].get('category', '')
            kg_data = kg_helper.query_relevant_entities(
                project_id=getattr(project, 'id', 0),
                unit_index=chapter_number,
                issue_category=issue_category,
                max_entities=15
            )
            knowledge_graph_context = kg_helper.format_kg_context(kg_data)
            
            logger.info(
                f"[批量修正] 知识图谱查询完成: chapter={chapter_number}, "
                f"问题数={len(chapter_issues)}, "
                f"人物={len(kg_data.get('characters', []))}, "
                f"事件={len(kg_data.get('events', []))}"
            )
            
            # 批量调用LLM修正
            batch_fix_result = await fix_generator.generate_batch_fix(
                issues=chapter_issues,
                chapter_content=chapter_content,
                unit_summary=chapter_summary,
                knowledge_graph_context=knowledge_graph_context,
                character_profiles=getattr(project, 'character_profiles', []) or [],
                worldview_settings=getattr(project, 'worldview_settings', {}) or {},
                content_type=content_type,
                db=db,
                user_id=user_id
            )
            
            # 将批量修正结果分配给每个问题
            for issue in chapter_issues:
                issue['auto_fix'] = batch_fix_result
            
            logger.info(
                f"[批量修正] 章节{chapter_number}批量修正完成: "
                f"问题数={len(chapter_issues)}, "
                f"confidence={batch_fix_result.get('confidence', 0):.2f}, "
                f"type={batch_fix_result.get('type', 'unknown')}"
            )
            
        except Exception as e:
            logger.error(f"[批量修正] 章节{chapter_number}批量修正失败: {e}", exc_info=True)
            # 降级处理：为每个问题设置None
            for issue in chapter_issues:
                issue['auto_fix'] = None

    return issues


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
    project_id: Optional[int] = None # 项目ID（路径中已含，请求体可选）
    unit_index: Optional[int] = None  # 单元序号（路径中已含，请求体可选）
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
    logger.info(
        f"[SSE发布] task_id={task_id}, type={event_type}, "
        f"dimension={dimension}, progress={progress}"
    )


# ==================== WritingUnit → NovelChapter 数据同步 ====================

# 从共享服务模块导入统一同步函数，确保所有路径使用同一实现
from app.services.novel_writer.chapter_sync import sync_writing_unit_to_novel_chapter as _sync_writing_unit_to_novel_chapter
