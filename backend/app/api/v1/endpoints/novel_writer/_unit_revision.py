"""小说/剧本正文生成 - 单元对话修正端点

提供用户通过对话形式对单元内容进行最终人工修正的流式API。
修正流程：初稿生成 -> 质控自动修正 -> 用户对话修正（最终修正）

LLM配置：使用写手agent所配置的API和模型参数。
思考模式：若用户在写手agent配置中启用了思考模式，此处同步启用。

@date: 2026-06-02
@version: v1.0.0
"""
import json
from typing import Optional, List, Dict, Any

from fastapi import Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, SystemConfig
from app.models.writing_unit import WritingUnit
from app.models.writing_task import WritingTask
from app.schemas.common import ResponseModel
from app.core.logger import get_logger

from .utils import router, logger as novel_writer_logger

logger = get_logger("unit_revision")


# ==================== 请求模型 ====================

class UnitRevisionRequest(BaseModel):
    """单元对话修正请求 — POST body 传输，避免 URL 超长触发 HTTP 431"""
    project_id: int
    user_feedback: str
    current_content: str
    revision_history: Optional[List[Dict[str, Any]]] = None


# ==================== 辅助函数 ====================

def _compress_revision_history(revision_history: List[Dict], max_rounds: int = 3) -> str:
    """压缩修订历史为摘要"""
    if not revision_history:
        return "无历史修订"

    recent = revision_history[-max_rounds:]
    summaries = []
    for rev in recent:
        feedback = rev.get('user_feedback', '')[:50]
        round_num = rev.get('round_number', '?')
        summary_text = f"第{round_num}轮: 用户要求'{feedback}...'"
        summaries.append(summary_text)

    return "\n".join(summaries) if summaries else "无历史修订"


def _build_unit_revision_prompt(
    unit_summary: str,
    current_content: str,
    user_feedback: str,
    history_summary: str
) -> str:
    """构建单元修订提示词

    v4.0优化: 增强单元概述上下文权重，空单元概述时添加推断提示
    """
    # v4.0: 当单元概述为空时，引导LLM根据内容和用户反馈自行推断修改意图
    unit_summary_section = unit_summary if unit_summary and unit_summary.strip() else (
        "（未提供单元概述，请根据当前内容和用户修改意见推断修改意图和范围）"
    )

    return f"""你是专业的文学创作修订助手。请仔细阅读以下信息，准确理解修改意图。

## 单元概述（核心参考）
{unit_summary_section}

## 当前完整内容
{current_content}

## 用户修改意见（本轮）
{user_feedback}

## 历史修订摘要（最近3轮）
{history_summary}

## 修订原则
1. **以单元概述为核心依据**：修改必须服务于单元概述的目标和情节方向
2. 保持内容整体结构和核心情节不变
3. 只修改用户明确提到的部分，不扩大修改范围
4. 确保修改后逻辑自洽、前后连贯
5. 保持原有的语言风格和叙述节奏
6. 如果内容包含拍摄脚本参考、AI视觉资源等附属章节，请原样保留
7. 如果内容涉及对话、场景描写或节奏控制，请参考单元概述的基调进行调整

请直接输出修订后的完整内容（不要输出JSON或diff格式）："""


def _revision_rule_check(
    original_content: str,
    revised_content: str,
    user_feedback: str,
    unit_index: int
) -> list:
    """修订后轻量级规则检测

    v4.0优化: 替代传统自动质控，提供非阻塞的写作提示。
    检测项：字数变化率告警、关键词匹配异常。

    Returns:
        list: 提示消息列表，每个元素为 {"type": "warning"|"info", "message": str}
    """
    hints = []

    # 1. 字数变化率检测
    original_len = len(original_content) if original_content else 0
    revised_len = len(revised_content) if revised_content else 0

    if original_len > 0:
        change_rate = (revised_len - original_len) / original_len

        if change_rate > 0.5:
            hints.append({
                "type": "warning",
                "message": (
                    f"字数大幅增加（{original_len}→{revised_len}字，增长{change_rate:.0%}），"
                    f"请确认修订后内容是否符合预期"
                )
            })
        elif change_rate < -0.3:
            hints.append({
                "type": "warning",
                "message": (
                    f"字数大幅减少（{original_len}→{revised_len}字，减少{abs(change_rate):.0%}），"
                    f"请确认是否意外删除了重要内容"
                )
            })
        elif abs(change_rate) > 0.2:
            hints.append({
                "type": "info",
                "message": (
                    f"字数变化较大（{original_len}→{revised_len}字，变化{abs(change_rate):.0%}），"
                    f"可检查内容是否合理"
                )
            })

    # 2. 关键词匹配检测（用户反馈中提到的内容在新版本中是否存在）
    import re
    # 提取用户反馈中可能的关键操作词
    action_keywords = ["删除", "添加", "修改", "调整", "增加", "减少", "缩短", "扩展",
                      "替换", "重写", "改写", "补充", "移除", "插入", "强化", "弱化"]
    mentioned_actions = []
    for kw in action_keywords:
        if kw in user_feedback:
            mentioned_actions.append(kw)

    if mentioned_actions:
        hints.append({
            "type": "info",
            "message": f"已根据用户要求执行：{'、'.join(mentioned_actions)}"
        })

    # 3. 字数极端值检测（< 100 字或 > 50000 字）
    if revised_len < 100:
        hints.append({
            "type": "warning",
            "message": f"修订后内容仅{revised_len}字，过短的内容可能不完整"
        })
    elif revised_len > 50000:
        hints.append({
            "type": "info",
            "message": f"修订后内容{revised_len}字，篇幅较长，请注意查看"
        })

    return hints


async def _get_writer_agent_config(task: WritingTask, db: AsyncSession) -> Dict[str, Any]:
    """从WritingTask的config中获取写手agent配置"""
    task_config = task.config or {}

    # 优先从 agent_configs 获取（pipeline启动后写入的解析后配置）
    agent_configs = task_config.get("agent_configs", {})
    writer_config = agent_configs.get("writer", {})

    if writer_config:
        logger.info(f"[单元对话修正] 从agent_configs获取写手配置: provider={writer_config.get('provider')}, model={writer_config.get('model_id')}")
        return writer_config

    # 兜底：从 agents 获取（前端提交的原始配置）
    agents_config = task_config.get("agents", {})
    writer_config = agents_config.get("writer", {})

    if writer_config:
        logger.info(f"[单元对话修正] 从agents获取写手配置: provider={writer_config.get('provider')}, model={writer_config.get('model')}")
        # 统一字段名
        if writer_config.get("model") and not writer_config.get("model_id"):
            writer_config["model_id"] = writer_config["model"]
        return writer_config

    logger.warning(f"[单元对话修正] 未找到写手agent配置，将使用系统默认provider")
    return {}


async def _get_thinking_mode_config(user_id: int, db: AsyncSession) -> Dict[str, Any]:
    """查询用户思考模式配置"""
    config_key = f"user_thinking_mode_config_{user_id}"
    try:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.id == config_key)
        )
        config = result.scalar_one_or_none()
        if config and config.config_value:
            thinking_config = json.loads(config.config_value)
            logger.info(f"[单元对话修正] 用户思考模式: enable_thinking={thinking_config.get('enable_thinking', False)}")
            return thinking_config
    except Exception as e:
        logger.warning(f"[单元对话修正] 查询思考模式配置失败: {e}")

    return {"enable_thinking": False, "reasoning_effort": "high", "thinking_save_dir": "./data/thinking_logs"}


# ==================== 端点 ====================

@router.post("/units/{unit_index}/revision/stream")
async def revise_unit_content_stream(
    unit_index: int,
    body: UnitRevisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    单元对话修正 - 流式生成修订内容

    工作流程:
    1. 查找WritingTask，获取写手agent的LLM配置
    2. 查询用户思考模式配置
    3. 创建LLM provider实例（使用写手agent的API配置）
    4. 构建修订提示词并流式输出修订内容
    5. 修订历史保存到WritingUnit记录

    SSE事件格式:
    - event: content / data: {"text": "..."}  (流式内容)
    - event: done / data: {"content": "..."}  (完成)
    - event: error / data: {"message": "..."} (错误)
    """
    async def event_generator():
        llm_provider = None
        try:
            logger.info(
                f"[单元对话修正] 开始: unit_index={unit_index}, project_id={body.project_id}, "
                f"user={current_user.id}, feedback_len={len(body.user_feedback)}"
            )

            # 1. 查找关联的 WritingTask
            task_result = await db.execute(
                select(WritingTask).where(
                    and_(
                        WritingTask.project_id == body.project_id,
                        WritingTask.user_id == current_user.id
                    )
                ).order_by(WritingTask.id.desc())
            )
            task = task_result.scalars().first()

            if not task:
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': f'未找到项目 {body.project_id} 的写作任务'}}, ensure_ascii=False)}\n\n"
                return

            # 2. 查找对应的 WritingUnit（加行级锁防并发覆盖）
            unit_result = await db.execute(
                select(WritingUnit).where(
                    and_(
                        WritingUnit.task_id == task.id,
                        WritingUnit.unit_index == unit_index
                    )
                ).with_for_update()
            )
            unit = unit_result.scalar_one_or_none()

            if not unit:
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': f'未找到单元 {unit_index}'}}, ensure_ascii=False)}\n\n"
                return

            unit_summary = unit.unit_summary or ""

            # 3. 获取写手agent配置
            writer_config = await _get_writer_agent_config(task, db)

            provider_name = writer_config.get("provider", "")
            model_id = writer_config.get("model_id") or writer_config.get("model", "")
            temperature = writer_config.get("temperature", 0.7)
            max_tokens = writer_config.get("max_tokens", 32000)
            api_base = writer_config.get("api_base")
            api_key = writer_config.get("api_key")
            config_id = writer_config.get("config_id")

            # 如果通过 config_id 引用预配置模型，先从数据库加载完整配置
            # （必须在 provider_name/model_id 空值检查之前执行）
            if config_id and (not provider_name or not model_id):
                try:
                    from app.models.writing_model_config import WritingModelConfig as WMC
                    from app.core.security import api_key_encryption

                    config_result = await db.execute(
                        select(WMC).where(WMC.id == config_id)
                    )
                    saved_config = config_result.scalar_one_or_none()
                    if saved_config:
                        api_key = api_key_encryption.decrypt(saved_config.encrypted_key)
                        api_base = saved_config.api_base
                        provider_name = saved_config.provider
                        model_id = saved_config.model_id
                        logger.info(f"[单元对话修正] 从config_id={config_id}加载: provider={provider_name}, model={model_id}")
                    else:
                        logger.warning(f"[单元对话修正] config_id={config_id} 对应的 WritingModelConfig 不存在")
                except Exception as e:
                    logger.warning(f"[单元对话修正] 从config_id加载失败: {e}")

            if not provider_name or not model_id:
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': '写手Agent未配置模型，请在写作工作台中为写手Agent配置模型'}}, ensure_ascii=False)}\n\n"
                return

            logger.info(
                f"[单元对话修正] 写手配置: provider={provider_name}, model={model_id}, "
                f"temperature={temperature}, has_api_key={bool(api_key)}, has_api_base={bool(api_base)}"
            )

            # 4. 查询思考模式配置
            thinking_config = await _get_thinking_mode_config(current_user.id, db)
            enable_thinking = thinking_config.get("enable_thinking", False)
            reasoning_effort = thinking_config.get("reasoning_effort", "high")
            thinking_save_dir = thinking_config.get("thinking_save_dir", "./data/thinking_logs")

            # 5. 创建LLM provider
            from app.agents.llm_manager import get_llm_manager
            from app.core.config import PRESET_MODELS

            llm_manager = get_llm_manager()

            try:
                if api_key:
                    # 使用自定义API配置
                    if not api_base:
                        preset = PRESET_MODELS.get(provider_name, {})
                        api_base = preset.get("api_base")

                    llm_provider = llm_manager.create_provider(
                        provider_name=provider_name,
                        api_key=api_key,
                        model_name=model_id,
                        api_base=api_base,
                        enable_thinking=enable_thinking,
                        reasoning_effort=reasoning_effort,
                        thinking_save_dir=thinking_save_dir
                    )
                else:
                    # 使用系统默认provider
                    llm_provider = await llm_manager.get_provider_from_db(
                        db, current_user.id, provider_name
                    )
                    if llm_provider:
                        llm_provider.model_name = model_id
                    else:
                        # 回退：使用系统provider
                        llm_provider = await llm_manager.get_system_provider(provider_name)
                        llm_provider.model_name = model_id
            except Exception as e:
                logger.error(f"[单元对话修正] 创建provider失败: {e}")
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': f'创建LLM provider失败: {str(e)}'}}, ensure_ascii=False)}\n\n"
                return

            if not llm_provider:
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': '无法获取LLM provider'}}, ensure_ascii=False)}\n\n"
                return

            # 6. 修订历史（由 Pydantic 自动反序列化为 list）
            revision_history_list = body.revision_history or []

            history_summary = _compress_revision_history(revision_history_list)

            # 7. 构建修订提示词
            revision_prompt = _build_unit_revision_prompt(
                unit_summary=unit_summary,
                current_content=body.current_content,
                user_feedback=body.user_feedback,
                history_summary=history_summary
            )

            logger.info(
                f"[单元对话修正] 提示词构建完成: prompt_len={len(revision_prompt)}, "
                f"enable_thinking={enable_thinking}"
            )

            # 8. 流式生成修订内容
            full_content = []
            try:
                async for chunk in llm_provider.generate_stream(
                    prompt=revision_prompt,
                    temperature=temperature if not enable_thinking else 0.7,
                    max_tokens=max_tokens,
                    module_name=f"unit_revision_{unit_index}"
                ):
                    if hasattr(chunk, 'content'):
                        text = chunk.content
                    else:
                        text = str(chunk)

                    full_content.append(text)
                    yield f"event: content\ndata: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"

            except Exception as gen_error:
                logger.error(f"[单元对话修正] 流式生成失败: {gen_error}")
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': f'生成失败: {str(gen_error)}'}}, ensure_ascii=False)}\n\n"
                return

            # 9. 流式生成完成
            revised_content = "".join(full_content)
            logger.info(
                f"[单元对话修正] 流式生成完成: len={len(revised_content)}, "
                f"unit_index={unit_index}"
            )

            # 9. 先保存修订历史（done 事件在 commit 成功后发送，保证数据一致性）
            # 10. 保存修订历史到 WritingUnit（追加到 existing revision_history）
            try:
                from datetime import datetime
                round_number = len(revision_history_list) + 1

                # 获取或初始化 unit 的修订历史
                existing_qc = unit.quality_control_report or {}
                if not isinstance(existing_qc, dict):
                    existing_qc = {}

                unit_revisions = existing_qc.get("revision_history", [])
                if not isinstance(unit_revisions, list):
                    unit_revisions = []

                unit_revisions.append({
                    "round_number": round_number,
                    "user_feedback": body.user_feedback,
                    "content_before": body.current_content[:500],  # 只保存前500字快照
                    "content_after": revised_content[:500],  # 只保存前500字快照
                    "timestamp": datetime.now().isoformat(),
                    "word_count_before": len(body.current_content),
                    "word_count_after": len(revised_content),
                })

                existing_qc["revision_history"] = unit_revisions
                unit.quality_control_report = existing_qc

                await db.commit()
                logger.info(f"[单元对话修正] 修订历史已保存: round={round_number}, unit_index={unit_index}")

                # v4.0优化: 轻量级规则检测提示（替代传统自动质控修正）
                try:
                    rule_hints = _revision_rule_check(
                        original_content=body.current_content,
                        revised_content=revised_content,
                        user_feedback=body.user_feedback,
                        unit_index=unit_index
                    )
                    if rule_hints:
                        logger.info(
                            f"[单元对话修正] 规则检测完成: unit={unit_index}, "
                            f"hints={len(rule_hints)}"
                        )
                        yield f"event: revision_hints\ndata: {json.dumps({'hints': rule_hints}, ensure_ascii=False)}\n\n"
                except Exception as hint_error:
                    logger.warning(f"[单元对话修正] 规则检测失败（不影响主流程）: {hint_error}")

                # 11. commit 成功后才发送 done 事件，确保客户端不会在数据未持久化时误判成功
                yield f"event: done\ndata: {json.dumps({'content': revised_content}, ensure_ascii=False)}\n\n"
            except Exception as save_error:
                logger.warning(f"[单元对话修正] 保存修订历史失败: {save_error}")
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': f'保存修订历史失败: {str(save_error)}'}}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"[单元对话修正] 端点异常: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': f'服务器错误: {str(e)}'}}, ensure_ascii=False)}\n\n"
        finally:
            if llm_provider:
                try:
                    await llm_provider.close()
                except Exception as close_err:
                    logger.warning(f"[单元对话修正] 关闭provider失败: {close_err}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )
