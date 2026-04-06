"""
多Agent协作文学作品生成系统 - 结构师Agent（Structural Agent）

模块: agents.writing
文件: structural_agent.py
功能: 将写作单元（章/集）拆解为多个场景，规划场景结构和叙事节奏

依赖关系:
    - 依赖: base_agent.py, agent_config.py
    - 依赖模型: WritingUnit（间接）
    - 被依赖: OrchestratorAgent

使用说明:
    agent = StructuralAgent(config=agent_config)
    result = await agent.execute(context)
    # result.data["scenes"] 包含场景列表

创建时间: 2026-03-27
最后修改: 2026-03-27

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import json
import re
import time
from typing import Any, Dict, List, Optional

from app.agents.writing.base_agent import BaseWritingAgent, AgentContext, AgentResult, AgentRole
from app.agents.writing.agent_config import AgentConfig
from app.utils.json_parser import parse_json


class StructuralAgent(BaseWritingAgent):
    """结构师Agent - 负责将写作单元拆解为场景
    
    职责：
    1. 分析单元大纲和全局上下文
    2. 将单元内容拆分为3-6个场景
    3. 为每个场景规划：标题、地点、角色、事件、情绪、字数目标、钩子
    4. 确保场景间逻辑衔接和叙事节奏
    
    输出格式：
    {
        "scenes": [
            {
                "scene_index": 1,
                "scene_title": "场景标题",
                "location": "发生地点",
                "characters": ["角色1", "角色2"],
                "event": "核心事件描述",
                "mood": "情绪基调",
                "word_target": 800,
                "hook": "钩子/悬念"
            },
            ...
        ]
    }
    """
    
    agent_name = "结构师Agent"
    agent_role = AgentRole.STRUCTURAL
    default_model = ""
    default_temperature = 0.6
    
    # 系统提示词模板
    SYSTEM_PROMPT_TEMPLATE = """# 角色定义

你是【结构师Agent】，一位专业的叙事结构设计师。你的职责是将文学作品的一个单元（章节或剧集）拆解为多个连贯的场景。

## 核心职责

1. **场景拆解**：将一个单元的内容合理拆分为3-6个场景
2. **结构设计**：为每个场景设计清晰的叙事目标和功能定位
3. **节奏把控**：确保场景间的张弛有度，叙事节奏流畅
4. **逻辑衔接**：保证场景之间的因果逻辑和时空连贯性

## 场景设计原则

1. **单一性原则**：每个场景应聚焦于一个核心事件或冲突
2. **递进性原则**：场景之间要有明确的因果推进关系
3. **多样性原则**：场景类型应多样化（对话、动作、内心独白等）
4. **平衡性原则**：场景长度应相对均衡，避免过长或过短

## 输出格式要求

你必须输出严格的JSON格式，包含以下字段：

```json
{
    "scenes": [
        {
            "scene_index": 1,
            "scene_title": "场景标题（简洁有力）",
            "location": "具体地点描述",
            "characters": ["出场角色1", "出场角色2"],
            "event": "核心事件描述（50字以内）",
            "mood": "情绪基调（如：紧张、温馨、悬疑、悲伤等）",
            "word_target": 800,
            "hook": "场景结束时的钩子或悬念"
        }
    ]
}
```

## 场景类型参考

- **开篇场景**：建立情境，引入冲突
- **发展场景**：推进情节，展现人物关系
- **高潮场景**：冲突爆发，情绪顶点
- **转折场景**：意外发生，方向改变
- **收束场景**：问题解决，铺垫下文

## 注意事项

1. 场景数量建议在3-6个之间，根据单元内容复杂度调整
2. 每个场景的字数目标建议500-1500字，总字数符合单元要求
3. 场景标题要简洁有力，能概括场景核心
4. 钩子设计要自然，能有效引导读者继续阅读
5. 角色出场要合理，避免不必要的角色堆砌
"""
    
    # 用户提示词模板
    USER_PROMPT_TEMPLATE = """# 单元结构分析任务

## 单元信息

- **单元序号**：第{unit_index}章/集
- **单元标题**：{unit_title}
- **单元概述**：{unit_summary}

## 全局上下文

### 作品背景
{global_context}

### 人物档案
{character_profiles}

### 世界观设定
{world_settings}

### 前文内容摘要
{previous_content}

## 人物状态追踪（重要：场景设计时请参考）

### 人物状态快照
{character_state_snapshot}

### 人物关系链
{relationship_summary}

### 人物当前位置
{character_location_info}

### 人物身份/官职
{character_identity_info}

### 活跃人物列表
{active_characters_info}

## 任务要求

请将上述单元拆解为多个场景，要求：

1. **场景数量**：3-6个场景，根据内容复杂度决定
2. **场景设计**：每个场景包含标题、地点、角色、事件、情绪、字数目标、钩子
3. **逻辑连贯**：场景之间要有清晰的因果推进关系
4. **节奏把控**：合理安排紧张场景和舒缓场景的顺序
5. **角色调度**：合理分配角色出场，避免场景过于拥挤或空旷
6. **字数分配**：总字数目标约 {total_word_target} 字，合理分配到各场景
7. **人物状态一致性**：场景中人物的出场位置、身份必须与上述状态追踪信息一致

## 输出要求

请直接输出JSON格式的场景列表，不要包含任何其他说明文字。
"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """初始化结构师Agent
        
        Args:
            config: Agent配置对象
        """
        super().__init__(config)
    
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行单元结构拆解
        
        将单元大纲拆解为结构化的场景列表。
        
        Args:
            context: Agent执行上下文，包含：
                - unit_index: 单元序号
                - extra["unit_title"]: 单元标题
                - extra["unit_summary"]: 单元概述
                - global_context: 全局背景
                - character_profiles: 角色档案
                - world_settings: 世界观设定
                - previous_content: 前文内容
                
        Returns:
            AgentResult: 包含场景列表的数据
                - success: 是否成功
                - data["scenes"]: 场景列表
                - errors: 错误信息（如有）
        """
        start_time = time.time()
        self.logger.info(f"开始拆解单元 {context.unit_index} 的结构")
        
        try:
            # 1. 构建提示词
            messages = self._build_prompt(context)
            
            # 2. 调用LLM（不传递max_tokens，让LLM自主控制）
            llm_result = await self.call_llm(
                messages=messages,
                model=self.default_model,
                temperature=self.default_temperature,
                task_id=context.task_id,
                scene_id=f"{context.unit_index}_structural"
            )
            
            # 3. 记录LLM原始返回内容
            response = llm_result.get("content", "")
            self.logger.info(f"LLM原始返回内容(前500字符): {response[:500]}")
            
            # 4. 解析LLM输出
            scenes_data = self._parse_scenes(response)
            
            # 5. 如果解析失败，尝试重试一次
            if not scenes_data:
                self.logger.warning("第一次解析失败，尝试重试并强调JSON格式要求")
                scenes_data = await self._retry_parse_with_strict_prompt(context, messages)
            
            if not scenes_data:
                return self._build_error_result(
                    "无法从LLM输出中解析场景结构",
                    raw_content=response[:500]
                )
            
            # 4. 验证场景数据
            validated_scenes = self._validate_scenes(scenes_data)
            
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.info(f"单元 {context.unit_index} 结构拆解完成，生成 {len(validated_scenes)} 个场景，耗时 {duration_ms}ms")
            
            return self._build_success_result(
                content=json.dumps({"scenes": validated_scenes}, ensure_ascii=False, indent=2),
                token_usage={
                    "input_tokens": llm_result.get("input_tokens", 0),
                    "output_tokens": llm_result.get("output_tokens", 0),
                    "total_tokens": llm_result.get("total_tokens", 0)
                },
                duration_ms=duration_ms,
                model_id=llm_result.get("model", self.default_model),
                scenes=validated_scenes,
                scene_count=len(validated_scenes)
            )
            
        except Exception as e:
            self.logger.exception(f"拆解单元结构时发生异常: {str(e)}")
            return self._build_error_result(f"结构拆解失败: {str(e)}")
    
    def _build_prompt(self, context: AgentContext) -> List[Dict[str, str]]:
        """构建提示词
        
        Args:
            context: Agent执行上下文
            
        Returns:
            List[Dict]: 消息列表
        """
        # 提取单元信息 - 从多个来源获取
        unit_title = context.extra.get("unit_title", f"第{context.unit_index}章")
        unit_summary = context.extra.get("unit_summary", "")
        
        self.logger.info(f"[StructuralAgent] 单元 {context.unit_index} 初始数据: extra.unit_title={unit_title}, extra.unit_summary_len={len(unit_summary)}")
        
        # 如果 unit_summary 为空，尝试从其他来源获取
        if not unit_summary:
            # 尝试从 context.config.unit_summaries 获取
            unit_summaries = context.config.get("unit_summaries", {})
            self.logger.info(f"[StructuralAgent] 单元 {context.unit_index}: 尝试从 config.unit_summaries 获取，可用单元数: {len(unit_summaries)}")
            if unit_summaries and isinstance(unit_summaries, dict):
                unit_data = unit_summaries.get(str(context.unit_index)) or unit_summaries.get(context.unit_index)
                if unit_data:
                    if not unit_title or unit_title == f"第{context.unit_index}章":
                        unit_title = unit_data.get("title", unit_title)
                    unit_summary = unit_data.get("summary", "")
                    self.logger.info(f"[StructuralAgent] 从 unit_summaries 获取单元 {context.unit_index}: title={unit_title}, summary_len={len(unit_summary)}")
                else:
                    self.logger.warning(f"[StructuralAgent] 单元 {context.unit_index} 在 unit_summaries 中未找到")

            # 如果仍然为空，尝试从 context.outline.chapters 获取
            if not unit_summary and context.outline:
                chapters = context.outline.get("chapters", [])
                self.logger.info(f"[StructuralAgent] 尝试从 outline.chapters 获取，章节数: {len(chapters)}")
                if 0 <= context.unit_index - 1 < len(chapters):
                    chapter = chapters[context.unit_index - 1]
                    if not unit_title or unit_title == f"第{context.unit_index}章":
                        unit_title = chapter.get("title", unit_title)
                    unit_summary = chapter.get("summary", "")
                    self.logger.info(f"[StructuralAgent] 从 outline.chapters 获取单元 {context.unit_index}: title={unit_title}")
        
        # 最终记录获取结果
        self.logger.info(f"[StructuralAgent] 单元 {context.unit_index} 最终数据: title={unit_title}, summary_len={len(unit_summary)}")

        # 格式化角色档案
        character_profiles_str = self._format_character_profiles(context.character_profiles)

        # 格式化世界观设定
        world_settings_str = self._format_world_settings(context.world_settings)

        # 格式化前文内容（限制长度）
        previous_content = context.previous_content
        if len(previous_content) > 3000:
            previous_content = previous_content[-3000:] + "\n...[前文省略]"

        # 计算字数目标（优先从 extra 获取，然后从 config 获取）
        total_word_target = context.extra.get("target_words") or context.config.get("words_per_unit") or context.config.get("word_target_per_unit", 3000)

        character_state_snapshot = context.character_state_snapshot or "（暂无人物状态快照）"
        relationship_summary = context.relationship_summary or "（暂无人物关系记录）"
        
        character_location_info = "（暂无位置信息）"
        if context.character_location_map:
            location_lines = [f"- {name}: {loc}" for name, loc in context.character_location_map.items() if loc]
            if location_lines:
                character_location_info = "\n".join(location_lines)
        
        character_identity_info = "（暂无身份信息）"
        if context.character_identity_map:
            identity_lines = [f"- {name}: {identity}" for name, identity in context.character_identity_map.items() if identity]
            if identity_lines:
                character_identity_info = "\n".join(identity_lines)
        
        active_characters_info = "（暂无活跃人物）"
        if context.active_characters:
            active_characters_info = "、".join(context.active_characters)

        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            unit_index=context.unit_index,
            unit_title=unit_title,
            unit_summary=unit_summary or "（无详细概述）",
            global_context=context.global_context or "（无特殊背景设定）",
            character_profiles=character_profiles_str,
            world_settings=world_settings_str or "（无特殊世界观设定）",
            previous_content=previous_content or "（无前文）",
            total_word_target=total_word_target,
            character_state_snapshot=character_state_snapshot,
            relationship_summary=relationship_summary,
            character_location_info=character_location_info,
            character_identity_info=character_identity_info,
            active_characters_info=active_characters_info
        )

        return [
            {"role": "system", "content": self.SYSTEM_PROMPT_TEMPLATE},
            {"role": "user", "content": user_prompt}
        ]
    
    def _format_character_profiles(self, profiles: List[Dict[str, Any]]) -> str:
        """格式化角色档案
        
        Args:
            profiles: 角色档案列表
            
        Returns:
            str: 格式化后的字符串
        """
        if not profiles:
            return "（无详细角色设定）"
        
        lines = []
        for i, profile in enumerate(profiles, 1):
            name = profile.get("name", f"角色{i}")
            role = profile.get("role", "")
            personality = profile.get("personality", "")
            background = profile.get("background", "")
            
            lines.append(f"### {name}")
            if role:
                lines.append(f"- **身份**：{role}")
            if personality:
                lines.append(f"- **性格**：{personality}")
            if background:
                lines.append(f"- **背景**：{background}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_world_settings(self, settings: Dict[str, Any]) -> str:
        """格式化世界观设定
        
        Args:
            settings: 世界观设定字典
            
        Returns:
            str: 格式化后的字符串
        """
        if not settings:
            return ""
        
        lines = []
        
        # 时代背景
        if "era" in settings:
            lines.append(f"- **时代背景**：{settings['era']}")
        
        # 地理环境
        if "geography" in settings:
            lines.append(f"- **地理环境**：{settings['geography']}")
        
        # 社会结构
        if "society" in settings:
            lines.append(f"- **社会结构**：{settings['society']}")
        
        # 特殊规则
        if "rules" in settings:
            lines.append(f"- **特殊规则**：{settings['rules']}")
        
        # 其他设定
        for key, value in settings.items():
            if key not in ["era", "geography", "society", "rules"]:
                lines.append(f"- **{key}**：{value}")
        
        return "\n".join(lines) if lines else ""
    
    def _extract_json(self, text: str) -> Optional[dict]:
        """从LLM输出中提取JSON，使用健壮的JSON解析器
        
        Args:
            text: LLM输出文本
            
        Returns:
            Optional[dict]: 解析后的JSON数据，失败返回None
        """
        if not text or not text.strip():
            return None
        
        # 使用健壮的JSON解析器
        result = parse_json(text, default=None)
        
        if result is not None:
            self.logger.debug("JSON解析成功")
            return result
        
        return None
    
    async def _retry_parse_with_strict_prompt(self, context: AgentContext, original_messages: List[Dict[str, str]]) -> Optional[List[Dict[str, Any]]]:
        """使用更严格的prompt重试解析
        
        Args:
            context: Agent执行上下文
            original_messages: 原始提示词消息
            
        Returns:
            Optional[List[Dict]]: 场景列表，解析失败返回None
        """
        try:
            # 构建强调JSON格式的提示词
            strict_messages = original_messages.copy()
            strict_system_prompt = self.SYSTEM_PROMPT_TEMPLATE + """

## 重要提醒

你必须严格以JSON格式返回，不要包含任何额外文字、说明或markdown标记。
只输出纯JSON数据，格式如下：
{"scenes": [{...}, {...}]}
"""
            strict_messages[0] = {"role": "system", "content": strict_system_prompt}
            
            self.logger.info("使用严格JSON格式要求重新调用LLM")
            
            # 重新调用LLM（不传递max_tokens，让LLM自主控制）
            llm_result = await self.call_llm(
                messages=strict_messages,
                model=self.default_model,
                temperature=0.3,  # 降低温度以获得更确定性的输出
                task_id=context.task_id,
                scene_id=f"{context.unit_index}_structural_retry"
            )
            
            response = llm_result.get("content", "")
            self.logger.info(f"重试LLM返回内容(前500字符): {response[:500]}")
            
            # 再次尝试解析
            return self._parse_scenes(response)
            
        except Exception as e:
            self.logger.error(f"重试解析时发生异常: {str(e)}")
            return None
    
    def _parse_scenes(self, content: str) -> Optional[List[Dict[str, Any]]]:
        """解析LLM输出的场景数据
        
        Args:
            content: LLM输出内容
            
        Returns:
            Optional[List[Dict]]: 场景列表，解析失败返回None
        """
        self.logger.info(f"开始解析场景数据，内容长度: {len(content)}")
        
        # 使用健壮的JSON提取方法
        data = self._extract_json(content)
        
        if data is None:
            self.logger.warning(f"无法提取JSON，原始内容前200字符: {content[:200]}...")
            return None
        
        self.logger.info(f"成功提取JSON数据，类型: {type(data)}")
        
        # 处理不同的返回格式
        if isinstance(data, dict):
            if "scenes" in data:
                scenes = data["scenes"]
                self.logger.info(f"从字典中提取scenes字段，场景数量: {len(scenes)}")
                return scenes
            else:
                # 可能是直接返回的场景对象，包装成列表
                self.logger.info("字典中没有scenes字段，尝试将整个字典作为单个场景")
                return [data]
        elif isinstance(data, list):
            self.logger.info(f"直接返回列表格式，场景数量: {len(data)}")
            return data
        
        self.logger.warning(f"无法识别的数据格式: {type(data)}")
        return None
    
    def _validate_scenes(self, scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """验证和规范化场景数据
        
        Args:
            scenes: 场景数据列表
            
        Returns:
            List[Dict]: 验证后的场景列表
        """
        validated = []
        
        for i, scene in enumerate(scenes, 1):
            validated_scene = {
                "scene_index": scene.get("scene_index", i),
                "scene_title": scene.get("scene_title", f"场景{i}"),
                "location": scene.get("location", "未指定"),
                "characters": scene.get("characters", []),
                "event": scene.get("event", ""),
                "mood": scene.get("mood", "中性"),
                "word_target": scene.get("word_target", 800),
                "hook": scene.get("hook", "")
            }
            
            # 确保characters是列表
            if not isinstance(validated_scene["characters"], list):
                validated_scene["characters"] = [str(validated_scene["characters"])]
            
            # 确保word_target是整数且在合理范围
            word_target = validated_scene["word_target"]
            if not isinstance(word_target, int):
                try:
                    word_target = int(word_target)
                except (ValueError, TypeError):
                    word_target = 800
            word_target = max(300, min(2000, word_target))  # 限制在300-2000之间
            validated_scene["word_target"] = word_target
            
            validated.append(validated_scene)
        
        return validated
