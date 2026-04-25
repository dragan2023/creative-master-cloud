"""
多Agent协作文学作品生成系统 - 逻辑编辑Agent

模块: agents.writing
文件: logic_editor_agent.py
功能: 检查写手输出中的逻辑错误和一致性问题，并支持自动修正

依赖关系:
    - 依赖: app.agents.writing.base_agent, app.agents.writing.agent_config
    - 依赖: app.agents.writing.prompts.character_state_prompts (逻辑修正提示词)
    - 被依赖: 总线Agent、风格润色Agent

创建时间: 2026-03-27
最后修改: 2026-04-02
版本: 3.0.0

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）

更新日志:
    - v3.0.0 (2026-04-02): 集成知识图谱深度一致性检查
      - 新增扩展实体一致性检查：设施、事件、群体、道具、世界规则、时间线、伏笔
      - 支持知识图谱查询和参考功能
      - 增强检测提示词，包含完整的一致性信息
    - v2.0.0 (2026-04-01): 集成逻辑修正功能，支持五类逻辑问题的检测与修正
      - 设定冲突（世界观设定、规则体系、能力设定等方面的前后矛盾）
      - 剧情衔接跳脱（场景转换突兀、事件发展缺乏合理过渡）
      - 人物成长过快（角色能力、认知或情感变化缺乏足够铺垫与合理性）
      - 时间线矛盾（事件发生顺序混乱、时间跨度不合理）
      - 核心线索断裂（关键情节线索中断或未得到合理延续）
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from app.agents.writing.base_agent import BaseWritingAgent, AgentRole, AgentContext, AgentResult
from app.agents.writing.prompts.editor_prompts import EDITOR_PROMPTS
from app.agents.writing.prompts.character_state_prompts import (
    LOGIC_CORRECTION_PROMPTS,
    get_logic_detection_prompt,
    get_logic_correction_prompt
)
from app.utils.json_parser import parse_json


class ConsistencyAdapter:
    """一致性管理器适配器
    
    用于适配一致性管理器，提供统一的检查接口。
    暂时返回空结果，后续对接实际的ConsistencyManager。
    """
    
    def __init__(self):
        self._manager = None
    
    def _get_manager(self):
        """获取一致性管理器实例（懒加载）"""
        if self._manager is None:
            try:
                from app.services.novel_writer.consistency import ConsistencyManager
                self._manager = ConsistencyManager
            except ImportError:
                self._manager = None
        return self._manager
    
    async def check_consistency(self, content: str, context: dict, **kwargs) -> Dict[str, Any]:
        """检查一致性（适配器方法）
        
        Args:
            content: 待检查内容
            context: 上下文信息
            **kwargs: 额外参数
            
        Returns:
            检查结果字典
        """
        manager = self._get_manager()
        if manager is None:
            # 暂时返回空结果，表示没有发现问题
            return {"issues": [], "score": 100}
        
        try:
            # 后续实现实际的调用逻辑
            # return await manager.check(content, context)
            return {"issues": [], "score": 100}
        except Exception as e:
            return {"issues": [], "score": 100, "error": str(e)}


class LogicEditorAgent(BaseWritingAgent):
    """逻辑编辑Agent
    
    负责审查写手输出内容的逻辑一致性，并在检测到问题时进行修正，包括：
    - 情节逻辑连贯性
    - 角色行为与人设一致性
    - 时间线一致性
    - 场景描述矛盾
    - 对话与角色身份匹配
    - 人物状态一致性
    
    支持的五类逻辑问题检测与修正：
    1. 设定冲突：世界观设定、规则体系、能力设定等方面的前后矛盾
    2. 剧情衔接跳脱：场景转换突兀、事件发展缺乏合理过渡
    3. 人物成长过快：角色能力、认知或情感变化缺乏足够铺垫与合理性
    4. 时间线矛盾：事件发生顺序混乱、时间跨度不合理
    5. 核心线索断裂：关键情节线索中断或未得到合理延续
    
    v3.0.0 新增：
    - 扩展实体一致性检查：设施、事件、群体、道具、世界规则、时间线、伏笔
    - 知识图谱查询功能：主动获取已有实体状态进行对比
    
    Attributes:
        agent_name: Agent名称
        agent_role: Agent角色类型
        default_model: 默认使用模型
        default_temperature: 默认温度参数
        auto_correct: 是否自动修正检测到的逻辑问题
        min_severity_for_correction: 触发修正的最低严重程度
    """
    
    agent_name = "逻辑编辑Agent"
    agent_role = AgentRole.LOGIC_EDITOR
    default_model = ""
    default_temperature = 0.2

    AUTO_CORRECT_DEFAULT = True
    MIN_SEVERITY_FOR_CORRECTION = "medium"

    def __init__(self, config=None, auto_correct: bool = None, min_severity: str = None):
        """初始化逻辑编辑Agent
        
        Args:
            config: Agent配置对象
            auto_correct: 是否自动修正检测到的逻辑问题，默认True
            min_severity: 触发修正的最低严重程度，默认"medium"
        """
        super().__init__(config)
        self._consistency_adapter = None
        self._knowledge_graph = None  # 知识图谱实例
        self.auto_correct = auto_correct if auto_correct is not None else self.AUTO_CORRECT_DEFAULT
        self.min_severity_for_correction = min_severity or self.MIN_SEVERITY_FOR_CORRECTION
    
    def _get_consistency_adapter(self) -> ConsistencyAdapter:
        """获取一致性适配器（懒加载）"""
        if self._consistency_adapter is None:
            self._consistency_adapter = ConsistencyAdapter()
        return self._consistency_adapter
        
    def _get_knowledge_graph(self, project_id: int, chapter_num: int = None):
        """获取知识图谱实例（懒加载）
            
        Args:
            project_id: 项目ID
            chapter_num: 章节号（可选）
                
        Returns:
            NovelKnowledgeGraph实例或None
        """
        if self._knowledge_graph is None and project_id:
            try:
                from app.tools.novel_graph_rag import NovelKnowledgeGraph
                from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase
                import os
                    
                # 获取知识图谱路径
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
        """获取扩展实体一致性上下文
            
        从知识图谱中提取扩展实体的状态信息，用于一致性检查。
            
        Args:
            context: Agent上下文
                
        Returns:
            扩展实体上下文字典，包含设施、事件、群体、道具等信息
        """
        extended_context = {
            "facilities_context": "",
            "events_context": "",
            "groups_context": "",
            "items_context": "",
            "rules_context": "",
            "timeline_context": "",
            "foreshadows_context": ""
        }
            
        try:
            project_id = context.project_id
            chapter_num = context.unit_index
                
            knowledge_graph = self._get_knowledge_graph(project_id, chapter_num)
                
            if knowledge_graph is None:
                return extended_context
                
            # 获取一致性报告
            consistency_report = knowledge_graph.get_consistency_report(chapter_num)
                
            # 1. 设施状态
            if consistency_report.get("facility_states"):
                facilities_lines = ["## 设施状态参考"]
                for name, state in consistency_report["facility_states"].items():
                    facilities_lines.append(
                        f"- {name}: 状态={state.get('status', '未知')}, "
                        f"负责人={state.get('manager', '未知')}"
                    )
                extended_context["facilities_context"] = "\n".join(facilities_lines)
                
            # 2. 未完成事件
            if consistency_report.get("unfinished_events"):
                events_lines = ["## 未完成事件"]
                for event in consistency_report["unfinished_events"]:
                    events_lines.append(
                        f"- {event.get('name', '未知')}: 状态={event.get('status', '进行中')}"
                    )
                extended_context["events_context"] = "\n".join(events_lines)
                
            # 3. 群体动态
            if consistency_report.get("group_states"):
                groups_lines = ["## 群体组织状态"]
                for name, state in consistency_report["group_states"].items():
                    groups_lines.append(
                        f"- {name}: 状态={state.get('status', '活跃')}, "
                        f"规模={state.get('scale', '未知')}"
                    )
                extended_context["groups_context"] = "\n".join(groups_lines)
                
            # 4. 道具归属
            if consistency_report.get("item_ownership"):
                items_lines = ["## 道具归属情况"]
                for name, state in consistency_report["item_ownership"].items():
                    items_lines.append(
                        f"- {name}: 持有者={state.get('owner', '未知')}, "
                        f"状态={state.get('status', '完好')}"
                    )
                extended_context["items_context"] = "\n".join(items_lines)
                
            # 5. 世界规则
            if consistency_report.get("active_rules"):
                rules_lines = ["## 世界规则约束"]
                for rule in consistency_report["active_rules"]:
                    rules_lines.append(
                        f"- {rule.get('name', '未知')}: {rule.get('description', '')}"
                    )
                extended_context["rules_context"] = "\n".join(rules_lines)
                
            # 6. 时间上下文
            if consistency_report.get("time_context"):
                time_ctx = consistency_report["time_context"]
                time_lines = ["## 时间线上下文"]
                if time_ctx.get("time_nodes"):
                    time_lines.append("已建立的时间节点:")
                    for node in time_ctx["time_nodes"]:
                        time_lines.append(f"  - {node.get('name', '')}")
                extended_context["timeline_context"] = "\n".join(time_lines)
                
            # 7. 待回收伏笔
            if consistency_report.get("pending_foreshadows"):
                foreshadows_lines = ["## 待回收伏笔"]
                for foreshadow in consistency_report["pending_foreshadows"]:
                    foreshadows_lines.append(
                        f"- [{foreshadow.get('importance', '普通')}] {foreshadow.get('name', '')} "
                        f"(第{foreshadow.get('planted_chapter', '?')}章)"
                    )
                extended_context["foreshadows_context"] = "\n".join(foreshadows_lines)
                
        except Exception as e:
            self.logger.warning(f"获取扩展实体上下文失败: {e}")
            
        return extended_context
    
    async def execute(self, context: AgentContext) -> AgentResult:
        """审查内容的逻辑一致性，并在检测到问题时进行修正
        
        从上下文中获取写手输出、角色设定和前文场景，
        使用LLM检查逻辑问题，如检测到问题且配置允许则进行修正。
        
        Args:
            context: Agent执行上下文
            
        Returns:
            AgentResult: 包含以下data字段:
                - issues: 问题列表，每项包含type、severity、description、suggestion
                - score: 逻辑一致性评分0-100
                - approved: 是否通过审查
                - corrected_content: 修正后的内容（如有修正）
                - corrections: 修正记录列表（如有修正）
                - character_state_updates: 人物状态更新列表
                - new_characters: 新检测的人物列表
        """
        start_time = self._get_timestamp()
        
        try:
            draft_content = context.extra.get("draft_content", "")
            if not draft_content:
                return self._build_error_result(
                    "缺少待审查内容",
                    error_type="missing_content"
                )
            
            content_type = context.extra.get("content_type", "novel")
            character_profiles = context.character_profiles or []
            previous_scenes = context.extra.get("previous_scenes", [])
            outline = context.outline or {}
            global_context = context.global_context or ""
            global_outline = context.extra.get("global_outline", {})
            previous_summary = context.extra.get("previous_summary", "")
            
            character_state_snapshot = context.character_state_snapshot or "暂无人物状态快照"
            relationship_summary = context.relationship_summary or "暂无人物关系摘要"
                        
            # v3.0.0: 获取扩展实体一致性上下文
            extended_context = self._get_extended_consistency_context(context)
                        
            detection_result = await self._detect_logic_issues(
                content=draft_content,
                content_type=content_type,
                character_profiles=character_profiles,
                global_outline=global_outline,
                previous_summary=previous_summary,
                character_state_snapshot=character_state_snapshot,
                context=context,
                extended_context=extended_context
            )
            
            if detection_result is None:
                return self._build_error_result(
                    "逻辑检测失败",
                    error_type="detection_failed"
                )
            
            issues = detection_result.get("issues", [])
            has_issues = detection_result.get("has_issues", False)
            overall_score = detection_result.get("overall_score", 0)
            
            high_severity_issues = [i for i in issues if i.get("severity") == "high"]
            medium_severity_issues = [i for i in issues if i.get("severity") == "medium"]
            
            approved = overall_score >= 70 and len(high_severity_issues) == 0
            
            corrected_content = None
            corrections = []
            
            if self.auto_correct and has_issues and self._should_correct(issues):
                self.logger.info(
                    f"检测到逻辑问题，开始修正 - Task: {context.task_id}, "
                    f"Issues: {len(issues)}, High: {len(high_severity_issues)}, Medium: {len(medium_severity_issues)}"
                )
                
                correction_result = await self._correct_logic_issues(
                    original_content=draft_content,
                    content_type=content_type,
                    detected_issues=issues,
                    character_profiles=character_profiles,
                    global_outline=global_outline,
                    previous_summary=previous_summary,
                    character_state_snapshot=character_state_snapshot,
                    context=context
                )
                
                if correction_result:
                    corrected_content = correction_result.get("corrected_content")
                    corrections = correction_result.get("corrections", [])
                    self.logger.info(
                        f"逻辑修正完成 - Task: {context.task_id}, "
                        f"Corrections: {len(corrections)}"
                    )
            
            duration_ms = self._get_timestamp() - start_time
            
            character_state_updates = detection_result.get("character_state_updates", [])
            new_characters = detection_result.get("new_characters", [])
            
            self.logger.info(
                f"逻辑审查完成 - Task: {context.task_id}, "
                f"Score: {overall_score}, Issues: {len(issues)}, Approved: {approved}, "
                f"Corrected: {corrected_content is not None}, "
                f"StateUpdates: {len(character_state_updates)}, NewChars: {len(new_characters)}"
            )
            
            result_data = {
                "issues": issues,
                "score": overall_score,
                "approved": approved,
                "character_state_updates": character_state_updates,
                "new_characters": new_characters,
                "consistency_warnings": extended_context  # 返回一致性警告信息
            }
            
            if corrected_content:
                result_data["corrected_content"] = corrected_content
                result_data["corrections"] = corrections
            
            return self._build_success_result(
                content=corrected_content or "",
                token_usage=detection_result.get("token_usage", {}),
                duration_ms=duration_ms,
                model_id=detection_result.get("model_id", ""),
                **result_data
            )
            
        except Exception as e:
            import traceback
            self.logger.error(f"逻辑审查执行失败: {type(e).__name__}: {str(e)}")
            self.logger.debug(f"异常堆栈: {traceback.format_exc()}")
            return self._build_error_result(f"{type(e).__name__}: {str(e)}")
    
    def _should_correct(self, issues: List[Dict]) -> bool:
        """判断是否需要进行修正
        
        Args:
            issues: 检测到的问题列表
            
        Returns:
            是否需要修正
        """
        severity_order = {"high": 3, "medium": 2, "low": 1}
        min_level = severity_order.get(self.min_severity_for_correction, 2)
        
        for issue in issues:
            issue_severity = issue.get("severity", "low")
            issue_level = severity_order.get(issue_severity, 1)
            if issue_level >= min_level:
                return True
        
        return False
    
    async def _detect_logic_issues(
        self,
        content: str,
        content_type: str,
        character_profiles: List[Dict],
        global_outline: Dict,
        previous_summary: str,
        character_state_snapshot: str,
        context: AgentContext,
        extended_context: Dict[str, str] = None
    ) -> Optional[Dict[str, Any]]:
        """检测逻辑问题
            
        使用逻辑检测提示词对内容进行全面检测。
        v3.0.0: 增加扩展实体一致性检查
    
        Args:
            content: 待检测内容
            content_type: 内容类型（novel/script）
            character_profiles: 人物设定
            global_outline: 全局大纲
            previous_summary: 前文摘要
            character_state_snapshot: 人物状态快照
            context: Agent上下文
            extended_context: 扩展实体上下文（v3.0.0新增）
                
        Returns:
            检测结果字典，包含issues、has_issues、overall_score等
        """
        try:
            detection_prompt = get_logic_detection_prompt(content_type)
                
            # 构建扩展实体上下文提示词
            extended_context_prompt = ""
            if extended_context:
                extended_parts = []
                for key, value in extended_context.items():
                    if value and isinstance(value, str) and value.strip():
                        extended_parts.append(value)
                    
                if extended_parts:
                    extended_context_prompt = "\n\n# 扩展实体一致性参考（重要）\n\n" + "\n\n".join(extended_parts)
                    extended_context_prompt += "\n\n**请确保内容与上述扩展实体状态保持一致。如有冲突，请在issues中指出。**"
                
            formatted_prompt = detection_prompt.format(
                content=content,
                global_outline=self._format_global_outline(global_outline),
                character_profiles=self._format_character_profiles(character_profiles),
                previous_summary=previous_summary or "暂无前文摘要",
                character_state_snapshot=character_state_snapshot,
                series_type=context.extra.get("series_type", "电视剧"),
                script_mode=context.extra.get("script_mode", "real"),
                extended_context=extended_context_prompt
            )
                
            messages = [
                {"role": "user", "content": formatted_prompt}
            ]
                
            self.logger.info(f"逻辑检测LLM调用开始 - Task: {context.task_id}")
                
            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(context.scene_index) if context.scene_index else None
            )
                
            if not llm_result:
                self.logger.error(f"逻辑检测LLM返回结果为空 - Task: {context.task_id}")
                return None
                
            llm_content = llm_result.get("content")
            if llm_content is None:
                self.logger.error(f"逻辑检测LLM返回内容为None - Task: {context.task_id}")
                return None
                
            result = self._parse_detection_response(llm_content)
                
            if result:
                result["token_usage"] = {
                    "input_tokens": llm_result.get("input_tokens", 0),
                    "output_tokens": llm_result.get("output_tokens", 0),
                    "total_tokens": llm_result.get("total_tokens", 0)
                }
                result["model_id"] = llm_result.get("model", "")
                
            return result
                
        except Exception as e:
            self.logger.error(f"逻辑检测执行失败: {type(e).__name__}: {str(e)}")
            return None
    
    async def _correct_logic_issues(
        self,
        original_content: str,
        content_type: str,
        detected_issues: List[Dict],
        character_profiles: List[Dict],
        global_outline: Dict,
        previous_summary: str,
        character_state_snapshot: str,
        context: AgentContext
    ) -> Optional[Dict[str, Any]]:
        """修正逻辑问题
        
        使用逻辑修正提示词对检测到的问题进行修正。
        
        Args:
            original_content: 原始内容
            content_type: 内容类型（novel/script）
            detected_issues: 检测到的问题列表
            character_profiles: 人物设定
            global_outline: 全局大纲
            previous_summary: 前文摘要
            character_state_snapshot: 人物状态快照
            context: Agent上下文
            
        Returns:
            修正结果字典，包含corrected_content、corrections等
        """
        try:
            correction_prompt = get_logic_correction_prompt(content_type)
            
            issues_text = self._format_detected_issues(detected_issues)
            
            formatted_prompt = correction_prompt.format(
                detected_issues=issues_text,
                original_content=original_content,
                global_outline=self._format_global_outline(global_outline),
                character_profiles=self._format_character_profiles(character_profiles),
                previous_summary=previous_summary or "暂无前文摘要",
                character_state_snapshot=character_state_snapshot,
                series_type=context.extra.get("series_type", "电视剧"),
                script_mode=context.extra.get("script_mode", "real")
            )
            
            messages = [
                {"role": "user", "content": formatted_prompt}
            ]
            
            self.logger.info(f"逻辑修正LLM调用开始 - Task: {context.task_id}")
            
            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id,
                scene_id=str(context.scene_index) if context.scene_index else None
            )
            
            if not llm_result:
                self.logger.error(f"逻辑修正LLM返回结果为空 - Task: {context.task_id}")
                return None
            
            llm_content = llm_result.get("content")
            if llm_content is None:
                self.logger.error(f"逻辑修正LLM返回内容为None - Task: {context.task_id}")
                return None
            
            result = self._parse_correction_response(llm_content)
            
            return result
            
        except Exception as e:
            self.logger.error(f"逻辑修正执行失败: {type(e).__name__}: {str(e)}")
            return None
    
    def _format_detected_issues(self, issues: List[Dict]) -> str:
        """格式化检测到的问题列表
        
        Args:
            issues: 问题列表
            
        Returns:
            格式化后的字符串
        """
        if not issues:
            return "未检测到逻辑问题"
        
        formatted = []
        for i, issue in enumerate(issues, 1):
            issue_type = issue.get("type", "未知类型")
            severity = issue.get("severity", "未知")
            location = issue.get("location", "未知位置")
            description = issue.get("description", "无描述")
            conflict_with = issue.get("conflict_with", "无")
            impact = issue.get("impact", "无")
            
            formatted.append(
                f"【问题{i}】\n"
                f"类型: {issue_type}\n"
                f"严重程度: {severity}\n"
                f"位置: {location}\n"
                f"描述: {description}\n"
                f"冲突对象: {conflict_with}\n"
                f"影响: {impact}"
            )
        
        return "\n\n".join(formatted)
    
    def _format_global_outline(self, outline: Dict) -> str:
        """格式化全局大纲
        
        Args:
            outline: 全局大纲数据
            
        Returns:
            格式化后的字符串
        """
        if not outline:
            return "无全局大纲"
        
        title = outline.get("title", "")
        summary = outline.get("summary", "")
        world_setting = outline.get("world_setting", "")
        
        lines = []
        if title:
            lines.append(f"标题: {title}")
        if summary:
            lines.append(f"概要: {summary}")
        if world_setting:
            lines.append(f"世界观: {world_setting}")
        
        return "\n".join(lines) if lines else "无全局大纲"
    
    def _parse_detection_response(self, content: str) -> Optional[Dict[str, Any]]:
        """解析逻辑检测响应
        
        Args:
            content: LLM返回的原始内容
            
        Returns:
            解析后的字典
        """
        if content is None:
            return None
        
        if not isinstance(content, str):
            try:
                content = str(content)
            except Exception as e:
                self.logger.debug(f"内容转换字符串失败: {e!r}")
                return None
        
        content = content.strip()
        if not content:
            return None
        
        # 使用健壮的JSON解析器
        result = parse_json(content, default=None)
        
        if result is not None and isinstance(result, dict):
            self.logger.debug("逻辑检测JSON解析成功")
            return result
        
        self.logger.warning("无法解析逻辑检测响应")
        return {
            "has_issues": False,
            "issues": [],
            "overall_score": 50,
            "summary": "响应解析失败"
        }
    
    def _parse_correction_response(self, content: str) -> Optional[Dict[str, Any]]:
        """解析逻辑修正响应
        
        Args:
            content: LLM返回的原始内容
            
        Returns:
            解析后的字典
        """
        if content is None:
            return None
        
        if not isinstance(content, str):
            try:
                content = str(content)
            except Exception as e:
                self.logger.debug(f"内容转换字符串失败: {e!r}")
                return None
        
        content = content.strip()
        if not content:
            return None
        
        # 使用健壮的JSON解析器
        result = parse_json(content, default=None)
        
        if result is not None and isinstance(result, dict):
            self.logger.debug("逻辑修正JSON解析成功")
            # 如果有corrected_content字段则返回，否则返回整个结果
            return result
        
        self.logger.warning("无法解析逻辑修正响应，返回原始内容")
        return {
            "corrected_content": content,
            "corrections": [],
            "preservation_notes": "响应解析失败，返回原始内容"
        }
    
    def _format_character_profiles(self, profiles: List[Dict]) -> str:
        """格式化角色档案
        
        Args:
            profiles: 角色档案列表
            
        Returns:
            格式化后的字符串
        """
        if not profiles:
            return "无角色设定"
        
        formatted = []
        for profile in profiles:
            name = profile.get("name", "未知")
            personality = profile.get("personality", "")
            background = profile.get("background", "")
            traits = profile.get("traits", [])
            
            lines = [f"【{name}】"]
            if personality:
                lines.append(f"  性格: {personality}")
            if background:
                lines.append(f"  背景: {background}")
            if traits:
                lines.append(f"  特征: {', '.join(traits)}")
            
            formatted.append("\n".join(lines))
        
        return "\n\n".join(formatted)
    
    def _format_previous_scenes(self, scenes: List[Dict]) -> str:
        """格式化前文场景
        
        Args:
            scenes: 前文场景列表
            
        Returns:
            格式化后的字符串
        """
        if not scenes:
            return "无前文场景"
        
        formatted = []
        for i, scene in enumerate(scenes, 1):
            title = scene.get("title", f"场景{i}")
            summary = scene.get("summary", "")
            key_events = scene.get("key_events", [])
            
            lines = [f"{i}. {title}"]
            if summary:
                lines.append(f"   摘要: {summary}")
            if key_events:
                lines.append(f"   关键事件: {', '.join(key_events)}")
            
            formatted.append("\n".join(lines))
        
        return "\n\n".join(formatted)
    
    def _format_outline(self, outline: Dict) -> str:
        """格式化大纲
        
        Args:
            outline: 大纲数据
            
        Returns:
            格式化后的字符串
        """
        if not outline:
            return "无大纲信息"
        
        title = outline.get("title", "")
        summary = outline.get("summary", "")
        
        lines = []
        if title:
            lines.append(f"标题: {title}")
        if summary:
            lines.append(f"概要: {summary}")
        
        return "\n".join(lines) if lines else "无大纲信息"
    
    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """解析LLM返回的JSON响应
        
        Args:
            content: LLM返回的原始内容
            
        Returns:
            解析后的字典
        """
        # 确保 content 是字符串类型
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
        
        
        # 清理内容（移除可能的前后空白）
        content = content.strip()
        
        if not content:
            self.logger.warning("LLM返回内容为空，使用默认结构")
            return self._default_result()
        
        
        # 尝试直接解析
        try:
            result = json.loads(content)
            if isinstance(result, dict) and "issues" in result:
                return result
        except json.JSONDecodeError:
            logger.debug("直接JSON解析失败，尝试从Markdown代码块提取")
        
        # 尝试从Markdown代码块中提取
        import re
        json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(json_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                result = json.loads(match.strip())
                if isinstance(result, dict) and "issues" in result:
                    return result
            except json.JSONDecodeError:
                logger.debug(f"Markdown代码块JSON解析失败，跳过: {match.strip()[:100]}")
                continue

        # 尝试查找完整的JSON对象（使用更精确的正则表达式）
        # 匹配从 { 开始到 } 结束的完整 JSON 对象
        json_pattern2 = r'\{[^{}]*"issues"[^{}]*\}'
        matches2 = re.findall(json_pattern2, content)
        
        for match in matches2:
            try:
                result = json.loads(match)
                if isinstance(result, dict) and "issues" in result:
                    return result
            except json.JSONDecodeError:
                logger.debug(f"精确正则JSON解析失败，跳过: {match[:100]}")
                continue

        # 尝试使用更宽松的方法：找到第一个 { 和最后一个 }
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = content[start_idx:end_idx + 1]
            try:
                result = json.loads(json_str)
                if isinstance(result, dict) and "issues" in result:
                    return result
            except json.JSONDecodeError as e:
                self.logger.debug(f"JSON解析失败: {e}")

        # 如果都失败了，返回默认结构
        self.logger.warning("无法解析LLM返回的JSON，使用默认结构")
        return self._default_result()
    
    def _default_result(self) -> Dict[str, Any]:
        """返回默认的解析结果结构"""
        return {
            "issues": [],
            "score": 50,
            "note": "解析失败，返回默认值"
        }
    
    def _get_timestamp(self) -> int:
        """获取当前时间戳（毫秒）"""
        import time
        return int(time.time() * 1000)
