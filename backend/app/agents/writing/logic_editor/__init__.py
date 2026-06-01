"""
逻辑编辑Agent 包入口

将原 logic_editor_agent.py 拆分为多个功能模块，通过 Mixin 多重继承组合。

包结构:
    __init__.py: 统一导出 LogicEditorAgent（从子 Mixin 组合）
    _consistency_adapter.py: ConsistencyAdapter 类
    _detection.py: 逻辑检测 Mixin
    _correction.py: 逻辑修正 Mixin
    _prompts.py: 提示词格式化 Mixin

@date: 2026-04-24
@version: v2.0.0
"""
import json
import time
from typing import Any, Dict, List, Optional

from app.agents.writing.base_agent import BaseWritingAgent, AgentRole, AgentContext, AgentResult
from app.agents.writing.logic_editor._consistency_adapter import ConsistencyAdapter
from app.agents.writing.logic_editor._detection import LogicDetectionMixin
from app.agents.writing.logic_editor._correction import LogicCorrectionMixin
from app.agents.writing.logic_editor._prompts import LogicPromptsMixin


class LogicEditorAgent(
    LogicDetectionMixin,
    LogicCorrectionMixin,
    LogicPromptsMixin,
):
    """逻辑编辑Agent

    负责审查写手输出内容的逻辑一致性，并在检测到问题时进行修正，包括：
    - 情节逻辑连贯性
    - 角色行为与人设一致性
    - 时间线一致性
    - 场景描述矛盾
    - 对话与角色身份匹配
    - 人物状态一致性
    """

    agent_name = "逻辑编辑Agent"
    agent_role = AgentRole.LOGIC_EDITOR
    default_model = ""
    default_temperature = 0.2

    AUTO_CORRECT_DEFAULT = True
    MIN_SEVERITY_FOR_CORRECTION = "medium"

    def __init__(self, config=None, auto_correct: bool = None, min_severity: str = None):
        super().__init__(config)
        self._consistency_adapter = None
        self._knowledge_graph = None
        self.auto_correct = auto_correct if auto_correct is not None else self.AUTO_CORRECT_DEFAULT
        self.min_severity_for_correction = min_severity or self.MIN_SEVERITY_FOR_CORRECTION

    def _get_consistency_adapter(self) -> ConsistencyAdapter:
        """获取一致性适配器（懒加载）"""
        if self._consistency_adapter is None:
            self._consistency_adapter = ConsistencyAdapter()
        return self._consistency_adapter

    def _get_knowledge_graph(self, project_id: int, chapter_num: int = None):
        """获取知识图谱实例（懒加载）"""
        if self._knowledge_graph is None and project_id:
            try:
                from app.tools.novel_graph_rag import NovelKnowledgeGraph
                from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
                import os
                pkb = ProjectKnowledgeBase()
                graph_path = pkb.get_graph_path(project_id, chapter_num or 1)
                if graph_path and os.path.exists(graph_path):
                    self._knowledge_graph = NovelKnowledgeGraph(persist_path=graph_path)
                    self._knowledge_graph.load()
                    self.logger.debug(f"知识图谱加载成功: {graph_path}")
            except Exception as e:
                self.logger.warning(f"加载知识图谱失败: {e}")
        return self._knowledge_graph

    def _get_extended_consistency_context(self, context: AgentContext) -> Dict[str, Any]:
        """获取扩展实体一致性上下文"""
        extended_context = {
            "facilities_context": "", "events_context": "",
            "groups_context": "", "items_context": "",
            "rules_context": "", "timeline_context": "",
            "foreshadows_context": ""
        }
        try:
            project_id = context.project_id
            chapter_num = context.unit_index
            knowledge_graph = self._get_knowledge_graph(project_id, chapter_num)
            if knowledge_graph is None:
                return extended_context
            consistency_report = knowledge_graph.get_consistency_report(chapter_num)

            if consistency_report.get("facility_states"):
                facilities_lines = ["## 设施状态参考"]
                for name, state in consistency_report["facility_states"].items():
                    facilities_lines.append(
                        f"- {name}: 状态={state.get('status', '未知')}, "
                        f"负责人={state.get('manager', '未知')}")
                extended_context["facilities_context"] = "\n".join(facilities_lines)

            if consistency_report.get("unfinished_events"):
                events_lines = ["## 未完成事件"]
                for event in consistency_report["unfinished_events"]:
                    events_lines.append(
                        f"- {event.get('name', '未知')}: 状态={event.get('status', '进行中')}")
                extended_context["events_context"] = "\n".join(events_lines)

            if consistency_report.get("group_states"):
                groups_lines = ["## 群体组织状态"]
                for name, state in consistency_report["group_states"].items():
                    groups_lines.append(
                        f"- {name}: 状态={state.get('status', '活跃')}, "
                        f"规模={state.get('scale', '未知')}")
                extended_context["groups_context"] = "\n".join(groups_lines)

            if consistency_report.get("item_ownership"):
                items_lines = ["## 道具归属情况"]
                for name, state in consistency_report["item_ownership"].items():
                    items_lines.append(
                        f"- {name}: 持有者={state.get('owner', '未知')}, "
                        f"状态={state.get('status', '完好')}")
                extended_context["items_context"] = "\n".join(items_lines)

            if consistency_report.get("active_rules"):
                rules_lines = ["## 世界规则约束"]
                for rule in consistency_report["active_rules"]:
                    rules_lines.append(
                        f"- {rule.get('name', '未知')}: {rule.get('description', '')}")
                extended_context["rules_context"] = "\n".join(rules_lines)

            if consistency_report.get("time_context"):
                time_ctx = consistency_report["time_context"]
                time_lines = ["## 时间线上下文"]
                if time_ctx.get("time_nodes"):
                    time_lines.append("已建立的时间节点:")
                    for node in time_ctx["time_nodes"]:
                        time_lines.append(f"  - {node.get('name', '')}")
                extended_context["timeline_context"] = "\n".join(time_lines)

            if consistency_report.get("pending_foreshadows"):
                foreshadows_lines = ["## 待回收伏笔"]
                for foreshadow in consistency_report["pending_foreshadows"]:
                    foreshadows_lines.append(
                        f"- [{foreshadow.get('importance', '普通')}] {foreshadow.get('name', '')} "
                        f"(第{foreshadow.get('planted_chapter', '?')}章)")
                extended_context["foreshadows_context"] = "\n".join(foreshadows_lines)
        except Exception as e:
            self.logger.warning(f"获取扩展实体上下文失败: {e}")
        return extended_context

    async def execute(self, context: AgentContext) -> AgentResult:
        """审查内容的逻辑一致性，并在检测到问题时进行修正"""
        start_time = self._get_timestamp()
        try:
            # 🔴 防御：安全提取 extra（defense-in-depth，__post_init__ 已标准化但保留二次守卫）
            _ext = context.extra if isinstance(context.extra, dict) else {}

            draft_content = _ext.get("draft_content", "")
            if not draft_content:
                return self._build_error_result("缺少待审查内容", error_type="missing_content")

            content_type = _ext.get("content_type", "novel")
            character_profiles = context.character_profiles or []
            previous_scenes = _ext.get("previous_scenes", [])
            outline = context.outline or {}
            global_context = context.global_context or ""
            global_outline = _ext.get("global_outline", {})
            previous_summary = _ext.get("previous_summary", "")
            character_state_snapshot = context.character_state_snapshot or "暂无人物状态快照"
            relationship_summary = context.relationship_summary or "暂无人物关系摘要"

            extended_context = self._get_extended_consistency_context(context)

            detection_result = await self._detect_logic_issues(
                content=draft_content, content_type=content_type,
                character_profiles=character_profiles, global_outline=global_outline,
                previous_summary=previous_summary,
                character_state_snapshot=character_state_snapshot,
                context=context, extended_context=extended_context
            )

            if detection_result is None:
                return self._build_error_result("逻辑检测失败", error_type="detection_failed")

            issues = detection_result.get("issues", [])
            has_issues = detection_result.get("has_issues", False)
            overall_score = detection_result.get("overall_score", 0)
            high_severity_issues = [i for i in issues if i.get("severity") == "high"]
            approved = overall_score >= 70 and len(high_severity_issues) == 0

            corrected_content = None
            corrections = []

            if self.auto_correct and has_issues and self._should_correct(issues):
                self.logger.info(
                    f"检测到逻辑问题，开始修正 - Task: {context.task_id}, "
                    f"Issues: {len(issues)}")
                correction_result = await self._correct_logic_issues(
                    original_content=draft_content, content_type=content_type,
                    detected_issues=issues, character_profiles=character_profiles,
                    global_outline=global_outline, previous_summary=previous_summary,
                    character_state_snapshot=character_state_snapshot, context=context)
                if correction_result:
                    corrected_content = correction_result.get("corrected_content")
                    corrections = correction_result.get("corrections", [])

            duration_ms = self._get_timestamp() - start_time
            character_state_updates = detection_result.get("character_state_updates", [])
            new_characters = detection_result.get("new_characters", [])

            self.logger.info(
                f"逻辑审查完成 - Task: {context.task_id}, "
                f"Score: {overall_score}, Issues: {len(issues)}, Approved: {approved}")

            result_data = {
                "issues": issues, "score": overall_score, "approved": approved,
                "character_state_updates": character_state_updates,
                "new_characters": new_characters,
                "consistency_warnings": extended_context
            }
            if corrected_content:
                result_data["corrected_content"] = corrected_content
                result_data["corrections"] = corrections

            return self._build_success_result(
                content=corrected_content or "",
                token_usage=detection_result.get("token_usage", {}),
                duration_ms=duration_ms,
                model_id=detection_result.get("model_id", ""),
                **result_data)

        except Exception as e:
            import traceback
            self.logger.error(f"逻辑审查执行失败: {type(e).__name__}: {str(e)}")
            self.logger.debug(f"异常堆栈: {traceback.format_exc()}")
            return self._build_error_result(f"{type(e).__name__}: {str(e)}")

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """解析LLM返回的JSON响应"""
        if content is None:
            self.logger.warning("LLM返回内容为None，使用默认结构")
            return self._default_result()
        if not isinstance(content, str):
            self.logger.warning(f"LLM返回内容类型异常: {type(content)}，尝试转换")
            try:
                content = str(content)
            except Exception as e:
                self.logger.warning(f"LLM返回内容转换失败: {e!r}")
                return self._default_result()
        content = content.strip()
        if not content:
            self.logger.warning("LLM返回内容为空，使用默认结构")
            return self._default_result()

        try:
            result = json.loads(content)
            if isinstance(result, dict) and "issues" in result:
                return result
        except json.JSONDecodeError:
            pass

        import re
        json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(json_pattern, content, re.DOTALL)
        for match in matches:
            try:
                result = json.loads(match.strip())
                if isinstance(result, dict) and "issues" in result:
                    return result
            except json.JSONDecodeError:
                continue

        json_pattern2 = r'\{[^{}]*"issues"[^{}]*\}'
        matches2 = re.findall(json_pattern2, content)
        for match in matches2:
            try:
                result = json.loads(match)
                if isinstance(result, dict) and "issues" in result:
                    return result
            except json.JSONDecodeError:
                continue

        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = content[start_idx:end_idx + 1]
            try:
                result = json.loads(json_str)
                if isinstance(result, dict) and "issues" in result:
                    return result
            except json.JSONDecodeError:
                pass

        self.logger.warning("无法解析LLM返回的JSON，使用默认结构")
        return self._default_result()

    def _default_result(self) -> Dict[str, Any]:
        """返回默认的解析结果结构"""
        return {"issues": [], "score": 50, "note": "解析失败，返回默认值"}

    def _get_timestamp(self) -> int:
        """获取当前时间戳（毫秒）"""
        return int(time.time() * 1000)


__all__ = ["LogicEditorAgent"]
