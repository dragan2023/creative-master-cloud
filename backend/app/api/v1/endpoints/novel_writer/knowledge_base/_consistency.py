"""知识库管理 - 一致性检查端点

从 knowledge_base.py 拆分，包含：
- get_consistency_report: 获取一致性检查报告
- get_character_states: 获取人物状态详情
- get_extended_entities: 获取扩展实体状态
- check_content_consistency: 检查内容一致性
- get_character_profile_history: 获取人物设定变更历史

共享 novel_writer/utils.py 的 router
"""
import os
from typing import Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import (
    ResourceNotFoundException, AppException, ErrorCode
)
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, NovelProject
from app.schemas.common import ResponseModel

from ..utils import router, settings, logger


@router.get("/projects/{project_id}/consistency-report")
async def get_consistency_report(
    project_id: int,
    unit_number: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取项目一致性检查报告

    返回当前项目的知识图谱一致性状态，包括：
    - 人物状态摘要（身份、位置、关系、能力、心理状态等）
    - 设施状态摘要（运营状态、归属、物理状态等）
    - 未完成事件跟踪
    - 群体组织动态
    - 道具归属情况
    - 待回收伏笔提醒
    - 世界规则约束
    - 一致性警告和潜在冲突点

    参数：
    - unit_number: 单元号（章节号/集数/场景号），不传则返回全局一致性状态

    返回：
    - chapter: 当前章节号
    - character_states: 人物状态摘要
    - facility_states: 设施状态摘要
    - unfinished_events: 未完成事件列表
    - group_states: 群体动态
    - item_ownership: 道具归属情况
    - pending_foreshadows: 待回收伏笔
    - active_rules: 世界规则约束
    - time_context: 时间上下文
    - consistency_warnings: 一致性警告
    """
    try:
        # 查询项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 检查知识库状态
        if project.kb_status != "ready":
            return ResponseModel(
                success=True,
                data={
                    "status": "not_ready",
                    "kb_status": project.kb_status,
                    "message": "知识库尚未构建完成，请先构建知识库",
                    "chapter": unit_number,
                    "character_states": {},
                    "facility_states": {},
                    "unfinished_events": [],
                    "group_states": {},
                    "item_ownership": {},
                    "pending_foreshadows": [],
                    "active_rules": [],
                    "time_context": {},
                    "consistency_warnings": []
                }
            )

        # 加载知识图谱
        from app.tools.novel_graph_rag import NovelKnowledgeGraph
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_path = kb_manager.get_graph_path(project_id, unit_number or 1)

        if not graph_path or not os.path.exists(graph_path):
            # 尝试获取全局图谱
            graph_path = project.global_outline_graph_path
            if not graph_path or not os.path.exists(graph_path):
                return ResponseModel(
                    success=True,
                    data={
                        "status": "no_graph",
                        "message": "知识图谱文件不存在",
                        "chapter": unit_number,
                        "character_states": {},
                        "facility_states": {},
                        "unfinished_events": [],
                        "group_states": {},
                        "item_ownership": {},
                        "pending_foreshadows": [],
                        "active_rules": [],
                        "time_context": {},
                        "consistency_warnings": []
                    }
                )

        # 加载知识图谱并获取一致性报告
        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
        knowledge_graph.load()

        consistency_report = knowledge_graph.get_consistency_report(
            unit_number)

        # 添加项目基础信息
        consistency_report["project_id"] = project_id
        consistency_report["project_title"] = project.title
        consistency_report["status"] = "ready"

        return ResponseModel(
            success=True,
            data=consistency_report
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取一致性报告失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/character-states")
async def get_character_states(
    project_id: int,
    unit_number: Optional[int] = None,
    character_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取人物状态详情

    返回指定人物或所有人物的状态信息，包括：
    - 身份变化
    - 位置变化
    - 关系变化
    - 能力成长
    - 心理状态

    参数：
    - unit_number: 单元号，不传则返回全部
    - character_name: 角色名称，不传则返回所有角色
    """
    try:
        # 查询项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 检查知识库状态
        if project.kb_status != "ready":
            return ResponseModel(
                success=True,
                data={
                    "status": "not_ready",
                    "message": "知识库尚未构建完成",
                    "character_states": {}
                }
            )

        # 加载知识图谱
        from app.tools.novel_graph_rag import NovelKnowledgeGraph
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_path = kb_manager.get_graph_path(project_id, unit_number or 1)

        if not graph_path or not os.path.exists(graph_path):
            graph_path = project.global_outline_graph_path

        if not graph_path or not os.path.exists(graph_path):
            return ResponseModel(
                success=True,
                data={
                    "status": "no_graph",
                    "message": "知识图谱文件不存在",
                    "character_states": {}
                }
            )

        # 加载知识图谱
        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
        knowledge_graph.load()

        # 获取人物状态实体
        state_entities = knowledge_graph.get_character_state_entities(
            chapter_num=unit_number)

        # 如果指定了角色名称，过滤结果
        if character_name:
            filtered_entities = {
                "identity_changes": [],
                "location_changes": [],
                "relationship_changes": [],
                "ability_growth": [],
                "mental_states": []
            }
            for category in filtered_entities:
                for entity in state_entities.get(category, []):
                    if entity.get("character") == character_name:
                        filtered_entities[category].append(entity)
            state_entities = filtered_entities

        return ResponseModel(
            success=True,
            data={
                "status": "ready",
                "unit_number": unit_number,
                "character_name": character_name,
                "character_states": state_entities
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取人物状态失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/extended-entities")
async def get_extended_entities(
    project_id: int,
    unit_number: Optional[int] = None,
    entity_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取扩展实体状态

    返回扩展实体的状态信息，包括：
    - 设施状态
    - 事件进展
    - 群体动态
    - 道具归属
    - 世界规则
    - 时间线
    - 伏笔线索

    参数：
    - unit_number: 单元号，不传则返回全部
    - entity_type: 实体类型，可选值：facility/event/group/item/rule/timeline/foreshadow
    """
    try:
        # 查询项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 检查知识库状态
        if project.kb_status != "ready":
            return ResponseModel(
                success=True,
                data={
                    "status": "not_ready",
                    "message": "知识库尚未构建完成",
                    "entities": {}
                }
            )

        # 加载知识图谱
        from app.tools.novel_graph_rag import NovelKnowledgeGraph
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_path = kb_manager.get_graph_path(project_id, unit_number or 1)

        if not graph_path or not os.path.exists(graph_path):
            graph_path = project.global_outline_graph_path

        if not graph_path or not os.path.exists(graph_path):
            return ResponseModel(
                success=True,
                data={
                    "status": "no_graph",
                    "message": "知识图谱文件不存在",
                    "entities": {}
                }
            )

        # 加载知识图谱
        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
        knowledge_graph.load()

        # 获取扩展实体
        extended_entities = knowledge_graph.get_extended_state_entities(
            chapter_num=unit_number)

        # 根据entity_type过滤
        if entity_type:
            type_mapping = {
                "facility": ["facilities", "facility_states"],
                "event": ["events", "event_states"],
                "group": ["groups", "group_members"],
                "item": ["items", "item_ownerships", "item_states"],
                "rule": ["world_rules"],
                "timeline": ["time_nodes", "time_flows"],
                "foreshadow": ["foreshadows", "foreshadow_resolutions"]
            }
            keys = type_mapping.get(entity_type, [])
            filtered_entities = {k: v for k,
                                 v in extended_entities.items() if k in keys}
            extended_entities = filtered_entities

        return ResponseModel(
            success=True,
            data={
                "status": "ready",
                "unit_number": unit_number,
                "entity_type": entity_type,
                "entities": extended_entities
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取扩展实体失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/projects/{project_id}/check-content-consistency")
async def check_content_consistency(
    project_id: int,
    content: str,
    unit_number: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    检查内容一致性

    对指定内容进行一致性检查，返回与知识图谱中已有信息的冲突点。

    参数：
    - content: 待检查的内容
    - unit_number: 当前单元号

    返回：
    - is_consistent: 是否一致
    - conflicts: 冲突点列表
    - suggestions: 修正建议
    """
    try:
        # 查询项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 检查知识库状态
        if project.kb_status != "ready":
            return ResponseModel(
                success=True,
                data={
                    "status": "not_ready",
                    "is_consistent": True,
                    "conflicts": [],
                    "suggestions": [],
                    "message": "知识库尚未构建，跳过一致性检查"
                }
            )

        # 加载知识图谱
        from app.tools.novel_graph_rag import NovelKnowledgeGraph
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_path = kb_manager.get_graph_path(project_id, unit_number or 1)

        if not graph_path or not os.path.exists(graph_path):
            graph_path = project.global_outline_graph_path

        if not graph_path or not os.path.exists(graph_path):
            return ResponseModel(
                success=True,
                data={
                    "status": "no_graph",
                    "is_consistent": True,
                    "conflicts": [],
                    "suggestions": [],
                    "message": "知识图谱不存在，跳过一致性检查"
                }
            )

        # 加载知识图谱
        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
        knowledge_graph.load()

        # 获取一致性报告作为参考
        consistency_report = knowledge_graph.get_consistency_report(
            unit_number)

        # 简单的一致性检查逻辑（可扩展为LLM辅助检查）
        conflicts = []
        suggestions = []

        # 检查人物状态冲突
        for char_name, state in consistency_report.get("character_states", {}).items():
            if char_name in content:
                # 检查位置冲突
                latest_location = state.get("latest_location")
                if latest_location and latest_location not in content:
                    conflicts.append({
                        "type": "character_location",
                        "character": char_name,
                        "expected": latest_location,
                        "description": f"角色'{char_name}'当前位置应为'{latest_location}'，但内容中未体现"
                    })
                    suggestions.append(f"建议确认角色'{char_name}'的位置是否正确")

        # 检查设施状态冲突
        for facility_name, state in consistency_report.get("facility_states", {}).items():
            if facility_name in content:
                facility_status = state.get("status")
                if facility_status in ["关闭", "暂停营业", "损坏"]:
                    conflicts.append({
                        "type": "facility_status",
                        "facility": facility_name,
                        "status": facility_status,
                        "description": f"设施'{facility_name}'当前状态为'{facility_status}'，请注意一致性"
                    })

        # 检查道具归属冲突
        for item_name, state in consistency_report.get("item_ownership", {}).items():
            if item_name in content:
                owner = state.get("owner")
                status = state.get("status")
                if status in ["丢失", "损坏", "销毁"]:
                    conflicts.append({
                        "type": "item_status",
                        "item": item_name,
                        "status": status,
                        "description": f"道具'{item_name}'当前状态为'{status}'，请注意一致性"
                    })

        # 添加待回收伏笔提醒
        for foreshadow in consistency_report.get("pending_foreshadows", []):
            suggestions.append({
                "type": "foreshadow_reminder",
                "name": foreshadow.get("name"),
                "importance": foreshadow.get("importance"),
                "planted_chapter": foreshadow.get("planted_chapter"),
                "description": f"待回收伏笔: {foreshadow.get('name')} (第{foreshadow.get('planted_chapter', '?')}章)"
            })

        # 🆕 检查事件状态冲突
        for event in consistency_report.get("unfinished_events", []):
            event_name = event.get("name", "")
            event_status = event.get("status", "")
            if event_name and event_name in content:
                # 已结束事件不应重新活跃出现
                if event_status in ["已完成", "已结束", "已取消"]:
                    conflicts.append({
                        "type": "event_status",
                        "event": event_name,
                        "status": event_status,
                        "description": f"事件'{event_name}'已标记为'{event_status}'，但内容中再次出现，请注意事件生命周期一致性"
                    })
                # 可能已完结的事件需要提醒
                if event_status == "可能已完结":
                    suggestions.append({
                        "type": "event_stale",
                        "name": event_name,
                        "description": f"事件'{event_name}'长期未更新（始于第{event.get('first_chapter', '?')}章），可能已完结，请确认"
                    })

        # 🆕 检查群体状态冲突
        for group_name, state in consistency_report.get("group_states", {}).items():
            if group_name in content:
                group_status = state.get("status", "")
                if group_status in ["解散", "合并", "消亡"]:
                    conflicts.append({
                        "type": "group_status",
                        "group": group_name,
                        "status": group_status,
                        "description": f"群体'{group_name}'已{group_status}，内容中再次出现请注意一致性"
                    })

        # 🆕 检查世界规则冲突
        for rule in consistency_report.get("active_rules", []):
            rule_name = rule.get("name", "")
            rule_desc = rule.get("description", "")
            if rule_name and rule_name in content:
                suggestions.append({
                    "type": "rule_reminder",
                    "name": rule_name,
                    "description": f"世界规则'{rule_name}'被引用，请确保内容不违反该规则"
                })
            if rule_desc and rule_desc in content:
                suggestions.append({
                    "type": "rule_reference",
                    "name": rule_name,
                    "description": f"检测到对世界规则'{rule_name}'的描述引用，请确认一致性"
                })

        # 🆕 检查时间线一致性
        time_ctx = consistency_report.get("time_context", {})
        time_nodes = time_ctx.get("time_nodes", [])
        if time_nodes and len(time_nodes) >= 2:
            # 检查时间节点是否在内容中有序出现
            content_time_refs = []
            for node in time_nodes:
                node_name = node.get("name", "")
                if node_name and node_name in content:
                    content_time_refs.append(node_name)
            if len(content_time_refs) >= 2:
                # 简单检查：时间节点在内容中出现的顺序是否与记录一致
                for i, ref in enumerate(content_time_refs):
                    found_idx = content.find(ref)
                    for later_ref in content_time_refs[i + 1:]:
                        later_idx = content.find(later_ref)
                        if later_idx < found_idx:
                            suggestions.append({
                                "type": "timeline_order",
                                "description": f"时间节点'{later_ref}'出现在'{ref}'之前，请确认时间线顺序是否正确"
                            })

        is_consistent = len(conflicts) == 0

        return ResponseModel(
            success=True,
            data={
                "status": "ready",
                "is_consistent": is_consistent,
                "conflicts": conflicts,
                "suggestions": suggestions,
                "warnings": consistency_report.get("consistency_warnings", []),
                "unit_number": unit_number
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"检查内容一致性失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/character-profile-history")
async def get_character_profile_history(
    project_id: int,
    character_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取人物设定变更历史

    返回人物设定在写作过程中的变更历史，包括：
    - 身份变化历史
    - 位置变化历史
    - 性格发展记录
    - 与初始设定的偏差

    参数：
    - character_name: 人物名称，不传则返回所有人物
    """
    try:
        # 查询项目
        result = await db.execute(
            select(NovelProject).where(NovelProject.id == project_id)
        )
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 加载全局知识图谱
        from app.tools.novel_graph_rag import NovelKnowledgeGraph
        from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

        kb_manager = ProjectKnowledgeBase(db=db)
        graph_path = kb_manager.get_graph_path(project_id, unit_number=None)

        if not graph_path or not os.path.exists(graph_path):
            graph_path = project.global_outline_graph_path

        if not graph_path or not os.path.exists(graph_path):
            return ResponseModel(
                success=True,
                data={
                    "status": "no_graph",
                    "message": "全局知识图谱不存在",
                    "profiles": []
                }
            )

        knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
        knowledge_graph.load()

        # 从图谱中提取人物设定及其变更历史
        profiles = []
        graph = knowledge_graph.graph

        for node_id, node_data in graph.nodes(data=True):
            if node_data.get("type") == "人物设定":
                char_name = node_data.get("text", "")

                # 如果指定了人物名称，过滤
                if character_name and char_name != character_name:
                    continue

                attributes = node_data.get("attributes", {})

                # 构建变更历史
                change_history = []
                for key in ["身份", "位置", "性格特点"]:
                    history_key = f"{key}_变更历史"
                    if history_key in attributes:
                        for change in attributes[history_key]:
                            change_history.append({
                                "attribute": key,
                                "chapter": change.get("chapter"),
                                "old_value": change.get("old_value"),
                                "new_value": change.get("new_value")
                            })

                # 按章节排序
                change_history.sort(key=lambda x: x.get("chapter", 0))

                profile_info = {
                    "name": char_name,
                    "description": node_data.get("description", ""),
                    "current_identity": attributes.get("身份", ""),
                    "current_location": attributes.get("当前位置", attributes.get("初始位置", "")),
                    "personality": attributes.get("性格特点", ""),
                    "background": attributes.get("背景故事", ""),
                    "first_appearance": node_data.get("first_appearance_chapter"),
                    "last_updated": node_data.get("last_updated_chapter"),
                    "change_history": change_history,
                    "性格发展记录": attributes.get("性格发展记录", [])
                }

                profiles.append(profile_info)

        return ResponseModel(
            success=True,
            data={
                "status": "ready",
                "character_name": character_name,
                "profiles": profiles,
                "total_count": len(profiles)
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取人物设定变更历史失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))
