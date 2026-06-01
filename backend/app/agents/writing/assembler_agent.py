"""
多Agent协作文学作品生成系统 - 合成Agent（Assembler Agent）

模块: agents.writing
文件: assembler_agent.py
功能: 将一个Unit下所有Scene的最终内容合并为完整章节，处理场景间衔接

依赖关系:
    - 依赖: base_agent.py, agent_config.py
    - 依赖模型: WritingUnit, WritingScene（间接）
    - 被依赖: OrchestratorAgent
    - 可选依赖: NovelExporter（通过适配器封装）

使用说明:
    agent = AssemblerAgent(config=agent_config)
    result = await agent.execute(context)
    # result.content 包含合并后的完整章节内容

创建时间: 2026-03-27
最后修改: 2026-03-27

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import time
import re
from typing import Any, Dict, List, Optional

from app.agents.writing.base_agent import BaseWritingAgent, AgentContext, AgentResult, AgentRole
from app.agents.writing.agent_config import AgentConfig


class ExporterAdapter:
    """导出器适配器 - 封装对旧模块的引用
    
    使用适配器模式封装对 NovelExporter 的引用，避免直接依赖，
    同时提供统一的导出接口。
    
    使用示例:
        adapter = ExporterAdapter()
        content = adapter.merge_scenes(scenes_content, style_config)
    """
    
    def __init__(self):
        self._exporter = None
        self._exporter_class = None
    
    def _get_exporter_class(self):
        """懒加载获取导出器类"""
        if self._exporter_class is None:
            try:
                from app.services.novel_writer.exporter import NovelExporter
                self._exporter_class = NovelExporter
            except ImportError:
                self._exporter_class = None
        return self._exporter_class
    
    def merge_scenes(
        self, 
        scenes_content: List[Dict[str, Any]], 
        style_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """合并场景内容为完整章节
        
        Args:
            scenes_content: 场景内容列表，每项包含 scene_index, scene_title, content
            style_config: 风格配置（可选）
            
        Returns:
            str: 合并后的完整内容
        """
        exporter_class = self._get_exporter_class()
        
        if exporter_class and hasattr(exporter_class, 'merge_scenes'):
            try:
                return exporter_class.merge_scenes(scenes_content, style_config)
            except Exception as e:
                self.logger.debug(f"使用导出器合并场景失败: {e}")
                pass
        
        # 默认合并逻辑：简单拼接并添加场景分隔
        return self._default_merge(scenes_content, style_config)
    
    def _default_merge(
        self, 
        scenes_content: List[Dict[str, Any]],
        style_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """默认的场景合并逻辑
        
        Args:
            scenes_content: 场景内容列表
            style_config: 风格配置
            
        Returns:
            str: 合并后的内容
        """
        if not scenes_content:
            return ""
        
        parts = []
        separator = style_config.get("scene_separator", "\n\n") if style_config else "\n\n"
        
        for scene in scenes_content:
            content = scene.get("content", "").strip()
            if content:
                # 可选：添加场景标题
                scene_title = scene.get("scene_title", "")
                if scene_title and style_config and style_config.get("include_scene_titles", False):
                    parts.append(f"## {scene_title}\n\n{content}")
                else:
                    parts.append(content)
        
        return separator.join(parts)


class AssemblerAgent(BaseWritingAgent):
    """合成Agent - 负责将多个场景合并为完整章节
    
    职责：
    1. 收集一个Unit下所有Scene的最终内容
    2. 按scene_index排序
    3. 处理场景间的衔接和过渡（可选：调用LLM进行微调）
    4. 添加章节标题和格式
    5. 统计总字数
    
    特点：
    - 默认不需要LLM，主要进行文本拼接和格式化
    - 支持通过配置启用LLM进行智能衔接优化（设置enable_llm_optimization=True）
    - 提供字数统计和格式检查
    
    注意：本Agent默认禁用LLM调用，仅在进行智能衔接优化时临时启用。
    """
    
    agent_name = "合成Agent"
    agent_role = AgentRole.ASSEMBLER
    default_model = ""  # 合成Agent通常不需要LLM
    default_temperature = 0.0
    requires_llm = False  # 默认禁用LLM，仅在进行智能优化时临时启用
    
    # 系统提示词模板（仅在启用LLM优化时使用）
    SYSTEM_PROMPT_TEMPLATE = """# 角色定义

你是【合成Agent】，一位专业的文本整合编辑。你的职责是将多个场景内容合并为流畅完整的章节。

## 核心职责

1. **场景衔接**：处理场景之间的过渡，确保叙事流畅
2. **格式统一**：统一段落格式、对话格式、标点使用
3. **冗余消除**：删除场景间的重复内容或冗余描述
4. **节奏调整**：优化章节整体节奏，确保阅读体验

## 处理原则

1. **保持原意**：不改变原文的核心内容和表达意图
2. **最小干预**：只在必要时进行调整，尊重原作者的创作
3. **流畅优先**：确保章节整体的阅读流畅性
4. **一致性**：保持人称、时态、风格的一致性

## 输出要求

1. 直接输出合并后的完整章节内容
2. 不需要包含场景分隔标记
3. 保持自然的段落结构
4. 确保开头和结尾流畅
"""
    
    # 用户提示词模板（仅在启用LLM优化时使用）
    USER_PROMPT_TEMPLATE = """# 场景合并任务

## 单元信息

- **单元标题**：{unit_title}

## 场景内容列表

{scenes_content}

## 风格指南

{style_guide}

## 任务要求

请将上述场景内容合并为一个完整流畅的章节，要求：

1. **自然过渡**：确保场景之间的衔接自然流畅
2. **消除冗余**：删除重复的描述或信息
3. **统一格式**：统一对话格式、段落结构
4. **保持风格**：遵循提供的风格指南

请直接输出合并后的完整章节内容。
"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """初始化合成Agent
        
        Args:
            config: Agent配置对象
        """
        super().__init__(config)
        self._exporter_adapter = ExporterAdapter()
        self._enable_llm_optimization = False  # 默认不启用LLM优化
    
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行场景合并
        
        将一个Unit下所有Scene的最终内容合并为完整章节。
        
        Args:
            context: Agent执行上下文，需要包含：
                - extra["scenes_content"]: 场景内容列表
                - extra["unit_title"]: 单元标题（可选）
                - style_guide: 风格指南（可选）
                
        Returns:
            AgentResult: 包含合并后的完整章节内容
                - success: 是否成功
                - content: 完整章节内容
                - data["word_count"]: 字数统计
                - data["scene_count"]: 场景数量
        """
        start_time = time.time()
        self.logger.info(f"开始合并单元 {context.unit_index} 的场景内容")
        
        try:
            # 🔴 防御：安全提取 extra（defense-in-depth，__post_init__ 已标准化但保留二次守卫）
            _ext = context.extra if isinstance(context.extra, dict) else {}

            # 1. 获取场景内容
            scenes_content = _ext.get("scenes_content", [])
            
            if not scenes_content:
                self.logger.warning(f"单元 {context.unit_index} 没有场景内容")
                return self._build_success_result(
                    content="",
                    duration_ms=0,
                    word_count=0,
                    scene_count=0
                )
            
            # 2. 按scene_index排序
            sorted_scenes = sorted(scenes_content, key=lambda x: x.get("scene_index", 0))
            
            # 3. 合并场景内容
            if self._enable_llm_optimization and self.default_model:
                # 使用LLM进行智能合并
                final_content = await self._merge_with_llm(context, sorted_scenes)
            else:
                # 使用默认合并逻辑
                final_content = self._merge_scenes_default(context, sorted_scenes)
            
            # 4. 统计字数
            word_count = self._count_words(final_content)
            
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.info(
                f"单元 {context.unit_index} 场景合并完成，"
                f"共 {len(sorted_scenes)} 个场景，"
                f"总字数 {word_count}，"
                f"耗时 {duration_ms}ms"
            )
            
            return self._build_success_result(
                content=final_content,
                duration_ms=duration_ms,
                word_count=word_count,
                scene_count=len(sorted_scenes),
                unit_title=_ext.get("unit_title", "")
            )
            
        except Exception as e:
            self.logger.exception(f"合并场景内容时发生异常: {str(e)}")
            return self._build_error_result(f"场景合并失败: {str(e)}")
    
    def _merge_scenes_default(
        self, 
        context: AgentContext, 
        scenes_content: List[Dict[str, Any]]
    ) -> str:
        """默认的场景合并逻辑
        
        使用适配器或直接拼接方式合并场景。
        
        Args:
            context: Agent执行上下文
            scenes_content: 排序后的场景内容列表
            
        Returns:
            str: 合并后的完整内容
        """
        unit_title = (context.extra if isinstance(context.extra, dict) else {}).get("unit_title", "")
        style_guide = context.style_guide or {}
        
        # 构建风格配置
        style_config = {
            "scene_separator": style_guide.get("scene_separator", "\n\n"),
            "include_scene_titles": style_guide.get("include_scene_titles", False),
            "paragraph_spacing": style_guide.get("paragraph_spacing", "double")
        }
        
        # 使用适配器合并
        content = self._exporter_adapter.merge_scenes(scenes_content, style_config)
        
        # 添加章节标题（如果配置要求）
        if unit_title and style_guide.get("include_chapter_title", True):
            # 检查内容是否已经包含标题
            if not content.strip().startswith(unit_title):
                content = f"{unit_title}\n\n{content}"
        
        return content
    
    async def _merge_with_llm(
        self, 
        context: AgentContext, 
        scenes_content: List[Dict[str, Any]]
    ) -> str:
        """使用LLM进行智能场景合并
        
        当启用LLM优化时，调用LLM处理场景衔接。
        注意：此方法会临时启用LLM调用权限。
        
        Args:
            context: Agent执行上下文
            scenes_content: 排序后的场景内容列表
            
        Returns:
            str: 合并后的完整内容
        """
        # 临时启用LLM调用权限（用于智能衔接优化）
        original_requires_llm = self.requires_llm
        self.requires_llm = True
        
        try:
            # 构建场景内容文本
            scenes_text = self._format_scenes_for_llm(scenes_content)
            
            # 构建风格指南文本
            style_guide_text = self._format_style_guide(context.style_guide)
            
            # 构建提示词
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT_TEMPLATE},
                {"role": "user", "content": self.USER_PROMPT_TEMPLATE.format(
                    unit_title=(context.extra if isinstance(context.extra, dict) else {}).get("unit_title", ""),
                    scenes_content=scenes_text,
                    style_guide=style_guide_text
                )}
            ]
            
            # 调用LLM（不传递max_tokens，让LLM自主控制）
            llm_result = await self.call_llm(
                messages=messages,
                model=self.default_model,
                temperature=0.3,  # 低温度，保持内容稳定
                task_id=context.task_id,
                scene_id=f"{context.unit_index}_assembler"
            )
            
            return llm_result["content"]
        finally:
            # 恢复原始LLM调用权限设置
            self.requires_llm = original_requires_llm
    
    def _format_scenes_for_llm(self, scenes_content: List[Dict[str, Any]]) -> str:
        """格式化场景内容供LLM处理
        
        Args:
            scenes_content: 场景内容列表
            
        Returns:
            str: 格式化后的文本
        """
        parts = []
        
        for scene in scenes_content:
            scene_index = scene.get("scene_index", 0)
            scene_title = scene.get("scene_title", f"场景{scene_index}")
            content = scene.get("content", "")
            
            parts.append(f"### 场景 {scene_index}: {scene_title}\n\n{content}\n")
        
        return "\n---\n\n".join(parts)
    
    def _format_style_guide(self, style_guide: Optional[Dict[str, Any]]) -> str:
        """格式化风格指南
        
        Args:
            style_guide: 风格指南字典
            
        Returns:
            str: 格式化后的文本
        """
        if not style_guide:
            return "（无特殊风格要求）"
        
        lines = []
        
        # 叙事视角
        if "perspective" in style_guide:
            lines.append(f"- **叙事视角**：{style_guide['perspective']}")
        
        # 时态
        if "tense" in style_guide:
            lines.append(f"- **时态**：{style_guide['tense']}")
        
        # 语言风格
        if "language_style" in style_guide:
            lines.append(f"- **语言风格**：{style_guide['language_style']}")
        
        # 对话格式
        if "dialogue_format" in style_guide:
            lines.append(f"- **对话格式**：{style_guide['dialogue_format']}")
        
        # 段落长度
        if "paragraph_length" in style_guide:
            lines.append(f"- **段落长度**：{style_guide['paragraph_length']}")
        
        # 其他风格要求
        for key, value in style_guide.items():
            if key not in ["perspective", "tense", "language_style", "dialogue_format", "paragraph_length"]:
                lines.append(f"- **{key}**：{value}")
        
        return "\n".join(lines) if lines else "（无特殊风格要求）"
    
    def _count_words(self, content: str) -> int:
        """统计字数
        
        支持中英文混合文本的字数统计。
        
        Args:
            content: 文本内容
            
        Returns:
            int: 字数
        """
        if not content:
            return 0
        
        import re
        
        # 移除多余空白
        content = re.sub(r'\s+', ' ', content).strip()
        
        # 中文字符计数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
        
        # 英文单词计数
        english_words = len(re.findall(r'[a-zA-Z]+', content))
        
        # 数字计数
        numbers = len(re.findall(r'\d+', content))
        
        return chinese_chars + english_words + numbers
    
    def set_llm_optimization(self, enabled: bool, model: Optional[str] = None) -> None:
        """设置是否启用LLM优化
        
        Args:
            enabled: 是否启用
            model: 指定模型（可选）
        """
        self._enable_llm_optimization = enabled
        if model:
            self.default_model = model
        self.logger.info(f"LLM优化已{'启用' if enabled else '禁用'}" + (f"，模型: {model}" if model else ""))
    
    def enable_llm_optimization(self, model: Optional[str] = None) -> None:
        """启用LLM优化（便捷方法）
    
        Args:
            model: 使用的模型
        """
        self.set_llm_optimization(True, model)
    
    def disable_llm_optimization(self) -> None:
        """禁用LLM优化（便捷方法）"""
        self.set_llm_optimization(False)
    def disable_llm_optimization(self) -> None:
        """禁用LLM优化（便捷方法）"""
        self.set_llm_optimization(False)
    def disable_llm_optimization(self) -> None:
        """禁用LLM优化（便捷方法）"""
        self.set_llm_optimization(False)
