"""
多Agent协作文学作品生成系统 - Agent抽象基类

模块: agents.writing
文件: base_agent.py
功能: 定义所有写作Agent的抽象基类，包括角色枚举、上下文数据结构、结果数据结构和核心方法

依赖关系:
    - 依赖: app.agents.llm_manager, app.core.logger, app.core.config
    - 被依赖: 所有具体的写作Agent实现

使用说明:
    class MyAgent(BaseWritingAgent):
        agent_name = "my_agent"
        agent_role = AgentRole.WRITER
        default_model = "deepseek-ai/DeepSeek-V3.2"
        default_temperature = 0.8
        
        async def execute(self, context: AgentContext) -> AgentResult:
            # 实现具体逻辑
            pass

创建时间: 2026-03-27
最后修改: 2026-03-27

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
import enum
import time

if TYPE_CHECKING:
    from app.agents.writing.agent_config import AgentConfig
    from app.agents.writing.stats_interceptor import StatsInterceptor

from app.agents.llm_manager import get_llm_manager, LLMManager
from app.agents.base_provider import BaseLLMProvider, LLMResponse
from app.core.logger import get_logger
from app.core.config import PRESET_MODELS, get_settings
from app.utils.llm_retry import (
    should_retry,
    is_rate_limit_error,
    is_network_error,
    calculate_retry_delay
)


class AgentRole(str, enum.Enum):
    """Agent角色枚举

    定义多Agent协作系统中的角色类型，每个角色有特定的职责。
    """
    ORCHESTRATOR = "orchestrator"      # 总线Agent - 负责任务分解和协调
    STRUCTURAL = "structural"          # 结构师Agent - 负责大纲和场景规划
    WRITER = "writer"                  # 写手Agent - 负责正文内容生成
    LOGIC_EDITOR = "logic_editor"      # 逻辑编辑Agent - 负责一致性检查
    STYLE_EDITOR = "style_editor"      # 风格润色Agent - 负责文风优化
    COMPLIANCE = "compliance"          # 合规审查Agent - 负责内容审核
    KNOWLEDGE = "knowledge"            # 知识顾问Agent - 负责知识检索
    ASSEMBLER = "assembler"            # 合成Agent - 负责最终内容整合


@dataclass
class AgentContext:
    """Agent执行上下文 - Agent间通信标准数据结构

    包含Agent执行所需的所有上下文信息，作为Agent间通信的标准载体。
    """
    # 任务标识
    task_id: str                              # 任务唯一标识
    unit_index: int                           # 当前单元索引（章节/场景）
    scene_index: Optional[int] = None         # 场景索引（如果适用）

    # 项目信息
    project_id: int = 0                       # 项目ID
    user_id: int = 0                          # 用户ID

    # 创作上下文
    outline: Dict[str, Any] = field(default_factory=dict)      # 大纲数据
    previous_content: str = ""                                    # 前文内容
    global_context: str = ""                                      # 全局背景信息

    # 角色和设定
    character_profiles: List[Dict[str, Any]] = field(
        default_factory=list)  # 人物档案
    world_settings: Dict[str, Any] = field(
        default_factory=dict)            # 世界观设定
    style_guide: Dict[str, Any] = field(
        default_factory=dict)               # 风格指南

    # 人物状态追踪（增强版）
    # 用于章节间传递人物状态信息，支持动态追踪和一致性维护
    # 当前章节人物状态快照文本（用于提示词）
    character_state_snapshot: str = ""
    character_state_evolution: Dict[str, str] = field(
        default_factory=dict)  # 人物状态演变 {角色名: 演变文本}
    relationship_summary: str = ""                                           # 人物关系摘要

    # 结构化人物状态数据（新增：用于程序化处理）
    # 当前所有人物状态 {角色名: CharacterState.to_dict()}
    character_states: Dict[str, Any] = field(default_factory=dict)
    previous_chapter_characters: List[str] = field(
        default_factory=list)    # 前一章出场人物列表
    character_location_map: Dict[str, str] = field(
        default_factory=dict)    # 人物当前位置映射 {角色名: 位置}
    character_identity_map: Dict[str, str] = field(
        default_factory=dict)    # 人物身份映射 {角色名: 身份/官职}
    active_characters: List[str] = field(
        default_factory=list)              # 当前活跃人物列表（用于场景生成）
    new_characters_detected: List[Dict[str, Any]] = field(
        default_factory=list)  # 新检测到的人物列表

    # 配置和扩展
    config: Dict[str, Any] = field(default_factory=dict)        # Agent配置
    extra: Dict[str, Any] = field(default_factory=dict)         # 扩展字段


@dataclass
class AgentResult:
    """Agent执行结果 - 标准返回结构

    所有Agent执行后返回的标准结果格式，包含生成内容、状态、统计等信息。
    """
    # 基本状态
    success: bool                             # 是否成功
    agent_role: AgentRole                     # Agent角色

    # 内容结果
    content: str = ""                         # 生成的内容
    data: Dict[str, Any] = field(default_factory=dict)  # 附加数据

    # 错误和警告
    errors: List[str] = field(default_factory=list)     # 错误列表
    warnings: List[str] = field(default_factory=list)   # 警告列表

    # Token统计
    token_usage: Dict[str, int] = field(default_factory=lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0
    })

    # 执行统计
    duration_ms: int = 0                      # 执行耗时（毫秒）
    model_id: str = ""                        # 使用的模型ID
    timestamp: datetime = field(default_factory=datetime.now)  # 时间戳


class BaseWritingAgent(ABC):
    """Agent抽象基类 - 所有写作Agent的父类

    定义了写作Agent的基本接口和行为，包括：
    - LLM调用封装
    - 日志记录
    - 统计拦截
    - 系统提示词构建
    - LLM调用权限控制

    子类需要实现：
    - agent_name: Agent名称
    - agent_role: Agent角色
    - default_model: 默认模型
    - default_temperature: 默认温度
    - execute(): 核心执行逻辑
    """

    # 子类必须定义的类属性
    agent_name: str = "base_agent"
    agent_role: AgentRole = AgentRole.WRITER
    default_model: str = ""
    default_temperature: float = 0.7

    # LLM调用权限控制
    # True: 该Agent需要调用LLM（默认）
    # False: 该Agent不需要LLM（如纯调度类Agent），禁用call_llm方法
    requires_llm: bool = True

    def __init__(self, config: Optional['AgentConfig'] = None):
        """初始化Agent

        Args:
            config: Agent配置对象，如果为None则使用默认配置
        """
        self.config = config
        self.logger = get_logger(f"agent.{self.agent_role.value}")
        self._stats_interceptor: Optional['StatsInterceptor'] = None
        self._llm_manager: Optional[LLMManager] = None
        self._provider: Optional[BaseLLMProvider] = None

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行Agent任务 - 子类必须实现

        Args:
            context: Agent执行上下文

        Returns:
            AgentResult: 执行结果
        """
        pass

    def set_stats_interceptor(self, interceptor: 'StatsInterceptor') -> None:
        """注入统计拦截器

        Args:
            interceptor: 统计拦截器实例
        """
        self._stats_interceptor = interceptor

    def _get_llm_manager(self) -> LLMManager:
        """获取LLM管理器实例（懒加载）"""
        if self._llm_manager is None:
            self._llm_manager = get_llm_manager()
        return self._llm_manager

    def _resolve_model_config(self, model: Optional[str], temperature: Optional[float]) -> tuple:
        """解析模型配置，返回 (provider_name, model_id, temperature, max_tokens, api_base, api_key)

        优先级：参数 > config
        支持完全自定义API配置：用户可传入任意provider、api_base、api_key

        Args:
            model: 指定的模型ID（可选）
            temperature: 指定的温度（可选）

        Returns:
            tuple: (provider_name, model_id, temperature, max_tokens, api_base, api_key)

        Raises:
            ValueError: 当Agent角色未配置模型时
        """
        # 从配置获取模型信息
        config_api_base = None
        config_api_key = None

        if self.config:
            model_config = self.config.get_config(self.agent_role)
            config_model = model_config.model_id if model_config else None
            config_provider = model_config.provider if model_config else None
            config_temperature = model_config.temperature if model_config else None
            config_max_tokens = model_config.max_tokens if model_config else 8192
            # 获取自定义API配置
            config_api_base = model_config.api_base if model_config else None
            config_api_key = model_config.api_key if model_config else None
        else:
            config_model = None
            config_provider = None
            config_temperature = None
            config_max_tokens = 8192

        # 确定最终值
        final_model = model or config_model
        final_temperature = temperature if temperature is not None else config_temperature
        final_max_tokens = config_max_tokens

        # 检查模型是否已配置
        if not final_model:
            raise ValueError(
                f"Agent '{self.agent_role.value}' 未配置模型，请在写作工作台中为该Agent配置模型")

        # 根据模型ID推断provider（如果未指定）
        provider_name = config_provider
        if not provider_name:
            provider_name = self._infer_provider_from_model(final_model)

        return provider_name, final_model, final_temperature, final_max_tokens, config_api_base, config_api_key

    def _infer_provider_from_model(self, model_id: str) -> str:
        """根据模型ID推断provider名称

        Args:
            model_id: 模型ID

        Returns:
            provider名称
        """
        model_id_lower = model_id.lower()

        # 遍历PRESET_MODELS查找匹配的provider
        for provider_name, provider_config in PRESET_MODELS.items():
            models = provider_config.get("models", [])
            for model_info in models:
                if model_info.get("id", "").lower() == model_id_lower:
                    return provider_name
                # 也检查模型名称中是否包含关键标识
                if model_id_lower in model_info.get("id", "").lower():
                    return provider_name

        # 根据模型名称前缀推断
        if "gpt" in model_id_lower or "claude" in model_id_lower or "glm" in model_id_lower:
            return "t8star"  # 默认使用t8star作为聚合平台
        elif "deepseek" in model_id_lower:
            return "siliconflow"
        elif "qwen" in model_id_lower:
            return "qianwen"
        elif "doubao" in model_id_lower:
            return "doubao"
        elif "gemini" in model_id_lower:
            return "openrouter"

        # 默认返回siliconflow
        return "siliconflow"

    async def _get_provider(
        self,
        provider_name: str,
        model_id: str,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> BaseLLMProvider:
        """获取LLM Provider实例

        支持完全自定义API配置：
        1. 如果传入了 api_key，直接使用（优先级最高）
        2. 如果传入了 api_base，使用传入值
        3. 如果都没传入，走原有逻辑（环境变量/DB获取）

        Args:
            provider_name: Provider名称
            model_id: 模型ID
            api_base: 自定义API端点（可选）
            api_key: API密钥（可选）

        Returns:
            LLM Provider实例
        """
        llm_manager = self._get_llm_manager()

        # 1. 如果提供了 api_key，直接使用自定义配置创建provider
        if api_key:
            final_api_base = api_base
            # 如果没有提供api_base，尝试从预设配置获取
            if not final_api_base:
                preset = PRESET_MODELS.get(provider_name, {})
                final_api_base = preset.get("api_base")

            self.logger.info(
                f"使用自定义API配置创建provider: provider={provider_name}, api_base={final_api_base}")
            return llm_manager.create_provider(
                provider_name=provider_name,
                api_key=api_key,
                model_name=model_id,
                api_base=final_api_base
            )

        # 2. 如果有 api_base 但没有 api_key，尝试从DB获取api_key
        if api_base:
            # 尝试从UserAPIKey获取
            db_api_key = await self._get_api_key_from_db(provider_name)
            if db_api_key:
                self.logger.info(
                    f"使用自定义api_base + DB中的api_key: provider={provider_name}, api_base={api_base}")
                return llm_manager.create_provider(
                    provider_name=provider_name,
                    api_key=db_api_key,
                    model_name=model_id,
                    api_base=api_base
                )
            # 如果DB中也没有，使用预设的api_base，但需要从环境变量获取api_key
            settings = get_settings()
            env_key_name = f"{provider_name.upper().replace('-', '_')}_API_KEY"
            env_api_key = getattr(settings, env_key_name, None)

            if env_api_key:
                self.logger.info(
                    f"使用自定义api_base + 环境变量api_key: provider={provider_name}, api_base={api_base}")
                return llm_manager.create_provider(
                    provider_name=provider_name,
                    api_key=env_api_key,
                    model_name=model_id,
                    api_base=api_base
                )

            raise ValueError(f"未配置 {provider_name} 的 API Key，请在环境变量中设置或通过配置传入")

        # 3. 走原有逻辑：尝试使用系统默认provider
        try:
            provider = llm_manager.get_default_provider(provider_name)
            # 更新模型名称
            provider.model_name = model_id
            return provider
        except ValueError:
            # 如果系统没有配置，尝试从PRESET_MODELS获取API Key
            settings = get_settings()
            preset = PRESET_MODELS.get(provider_name, {})

            # 获取API Key
            env_key_name = f"{provider_name.upper().replace('-', '_')}_API_KEY"
            api_key = getattr(settings, env_key_name, None)

            if not api_key:
                # 最后尝试从DB获取
                db_api_key = await self._get_api_key_from_db(provider_name)
                if db_api_key:
                    api_key = db_api_key
                else:
                    raise ValueError(
                        f"未配置 {provider_name} 的 API Key，请在环境变量中设置 {env_key_name} 或通过配置传入")

            # 创建provider
            return llm_manager.create_provider(
                provider_name=provider_name,
                api_key=api_key,
                model_name=model_id,
                api_base=preset.get("api_base")
            )

    async def _get_api_key_from_db(self, provider_name: str) -> Optional[str]:
        """从数据库获取API Key

        Args:
            provider_name: Provider名称

        Returns:
            API Key字符串，如果不存在返回None
        """
        try:
            from app.core.database import get_async_session
            from app.models.api_key import UserAPIKey
            from app.core.security import api_key_encryption
            from sqlalchemy import select

            async for session in get_async_session():
                stmt = select(UserAPIKey).where(
                    UserAPIKey.provider == provider_name,
                    UserAPIKey.is_valid == True
                ).order_by(UserAPIKey.created_at.desc()).limit(1)
                result = await session.execute(stmt)
                api_key_record = result.scalar_one_or_none()

                if api_key_record:
                    # 解密API Key
                    return api_key_encryption.decrypt(api_key_record.encrypted_key)
                break
        except Exception as e:
            self.logger.warning(
                f"从数据库获取API Key失败: provider={provider_name}, error={e}")

        return None

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,  # None表示使用模型配置的值，不做限制
        task_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        max_retries: int = 3,  # 最大重试次数
        retry_delay: float = 5.0  # 重试基础延迟（秒）
    ) -> Dict[str, Any]:
        """统一LLM调用接口（通过StatsInterceptor包装）

        封装LLM调用，支持统计记录、错误处理和自动重连机制。

        注意：如果Agent设置了 requires_llm=False，调用此方法将抛出异常。

        重连机制：
        - 遇到API限流（429错误、RateLimitError等）时自动重试
        - 遇到网络断联错误时自动重试
        - 使用指数退避策略，延迟时间递增
        - 达到最大重试次数后抛出异常

        Args:
            messages: 消息列表，格式为 [{"role": "system/user/assistant", "content": "..."}]
            model: 指定模型ID（可选，默认使用Agent配置）
            temperature: 温度参数（可选）
            max_tokens: 最大输出token数（None表示使用模型配置值，不主动限制）
            task_id: 任务ID（用于统计）
            scene_id: 场景ID（用于统计）
            max_retries: 最大重试次数（默认3次）
            retry_delay: 重试基础延迟时间（默认5秒）

        Returns:
            Dict包含:
            - content: str - 生成的内容
            - input_tokens: int - 输入token数
            - output_tokens: int - 输出token数
            - total_tokens: int - 总token数
            - model: str - 使用的模型ID
            - provider: str - 使用的provider
            - retries: int - 重试次数（用于调试）

        Raises:
            RuntimeError: 当Agent设置了requires_llm=False时
            Exception: 达到最大重试次数后抛出最后一次异常
        """
        # 检查LLM调用权限
        if not self.requires_llm:
            raise RuntimeError(
                f"Agent '{self.agent_name}' (role={self.agent_role.value}) 不需要LLM调用。"
                f"该Agent被设计为纯调度/整合类Agent，不应调用call_llm方法。"
                f"如果确实需要LLM功能，请将requires_llm设置为True。"
            )

        start_time = time.time()
        retry_count = 0  # 记录重试次数

        # 解析配置（返回值已包含 api_base 和 api_key）
        provider_name, model_id, resolved_temp, resolved_max_tokens, api_base, api_key = self._resolve_model_config(
            model, temperature)

        # 使用传入的max_tokens或配置的值
        final_max_tokens = max_tokens or resolved_max_tokens

        self.logger.info(
            f"LLM调用开始 - Agent: {self.agent_name}, Model: {model_id}, "
            f"Provider: {provider_name}, Temperature: {resolved_temp}, MaxTokens: {final_max_tokens}"
        )

        last_error = None
        for attempt in range(max_retries + 1):  # +1 因为第一次不算重试
            try:
                # 获取provider（支持自定义api_base和api_key）
                provider = await self._get_provider(provider_name, model_id, api_base, api_key)

                # 提取system_prompt和user_prompt
                system_prompt = None
                user_prompt = ""

                for msg in messages:
                    if msg.get("role") == "system":
                        system_prompt = msg.get("content", "")
                    elif msg.get("role") == "user":
                        user_prompt = msg.get("content", "")

                # 调用LLM
                response: LLMResponse = await provider.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=resolved_temp,
                    max_tokens=final_max_tokens
                )

                # 计算耗时
                duration_sec = time.time() - start_time
                duration_ms = int(duration_sec * 1000)

                # 提取token使用量
                usage = response.usage or {}
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get(
                    "total_tokens", input_tokens + output_tokens)

                # 记录统计
                if self._stats_interceptor and task_id:
                    await self._stats_interceptor.record(
                        agent_name=self.agent_name,
                        model_id=model_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        duration_sec=duration_sec,
                        scene_id=scene_id
                    )

                # 重连成功日志
                if retry_count > 0:
                    self.logger.info(
                        f"LLM调用成功（重连后） - Agent: {self.agent_name}, Tokens: {total_tokens}, "
                        f"重试次数: {retry_count}, 总耗时: {duration_ms}ms"
                    )
                else:
                    self.logger.info(
                        f"LLM调用成功 - Agent: {self.agent_name}, Tokens: {total_tokens} "
                        f"(in: {input_tokens}, out: {output_tokens}), Duration: {duration_ms}ms"
                    )

                return {
                    "content": response.content,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "model": response.model,
                    "provider": response.provider,
                    "duration_ms": duration_ms,
                    "retries": retry_count
                }

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                error_msg = str(e)[:200]

                # 判断是否应该重试（限流或网络错误）
                if should_retry(e) and attempt < max_retries:
                    # 计算延迟时间（指数退避）
                    delay = calculate_retry_delay(
                        attempt, retry_delay, max_delay=60.0, strategy="exponential")

                    # 确定错误类型描述
                    if is_rate_limit_error(e):
                        error_desc = "API限流(429)"
                    elif is_network_error(e):
                        error_desc = "网络断联"
                    else:
                        error_desc = "临时故障"

                    retry_count += 1
                    self.logger.warning(
                        f"LLM调用失败({error_desc})，{delay:.1f}秒后重试... "
                        f"(尝试 {attempt + 1}/{max_retries + 1}): {error_type}: {error_msg}"
                    )

                    # 等待后重试
                    import asyncio
                    await asyncio.sleep(delay)
                    continue
                else:
                    # 不应该重试或已达到最大重试次数
                    duration_ms = int((time.time() - start_time) * 1000)
                    self.logger.error(
                        f"LLM调用失败 - Agent: {self.agent_name}, Error: {error_type}: {error_msg}, "
                        f"Duration: {duration_ms}ms, 重试次数: {retry_count}"
                    )
                    raise

        # 不应该到达这里，但以防万一
        if last_error:
            raise last_error
        raise RuntimeError("LLM调用失败：未知错误")

    async def call_llm_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,  # None表示使用模型配置的值，不做限制
        task_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        max_retries: int = 3,  # 最大重试次数
        retry_delay: float = 5.0  # 重试基础延迟（秒）
    ):
        """统一LLM流式调用接口

        异步生成器，逐块返回生成的内容。
        支持断联重连机制。

        注意：如果Agent设置了 requires_llm=False，调用此方法将抛出异常。

        重连机制说明：
        - 重试发生在流开始之前（连接阶段）
        - 一旦流开始输出，重试将不会触发
        - 适用于连接超时、API限流等连接阶段错误

        Args:
            messages: 消息列表
            model: 指定模型ID（可选）
            temperature: 温度参数（可选）
            max_tokens: 最大输出token数（None表示使用模型配置值，不主动限制）
            task_id: 任务ID（用于统计）
            scene_id: 场景ID（用于统计）
            max_retries: 最大重试次数（默认3次）
            retry_delay: 重试基础延迟时间（默认5秒）

        Yields:
            str: 内容片段

        Raises:
            RuntimeError: 当Agent设置了requires_llm=False时
        """
        # 检查LLM调用权限
        if not self.requires_llm:
            raise RuntimeError(
                f"Agent '{self.agent_name}' (role={self.agent_role.value}) 不需要LLM调用。"
                f"该Agent被设计为纯调度/整合类Agent，不应调用call_llm_stream方法。"
            )

        import asyncio
        start_time = time.time()
        content_chunks = []
        retry_count = 0
        last_error = None

        # 解析配置（返回值已包含 api_base 和 api_key）
        provider_name, model_id, resolved_temp, resolved_max_tokens, api_base, api_key = self._resolve_model_config(
            model, temperature)
        final_max_tokens = max_tokens or resolved_max_tokens

        self.logger.info(
            f"LLM流式调用开始 - Agent: {self.agent_name}, Model: {model_id}, "
            f"Provider: {provider_name}"
        )

        for attempt in range(max_retries + 1):
            try:
                # 获取provider（支持自定义api_base和api_key）
                provider = await self._get_provider(provider_name, model_id, api_base, api_key)

                # 提取system_prompt和user_prompt
                system_prompt = None
                user_prompt = ""

                for msg in messages:
                    if msg.get("role") == "system":
                        system_prompt = msg.get("content", "")
                    elif msg.get("role") == "user":
                        user_prompt = msg.get("content", "")

                # 流式调用LLM
                async for chunk in provider.generate_stream(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=resolved_temp,
                    max_tokens=final_max_tokens
                ):
                    content_chunks.append(chunk)
                    yield chunk

                # 计算耗时
                duration_sec = time.time() - start_time

                # 估算token数（流式模式下只能估算）
                full_content = "".join(content_chunks)
                # 简单估算：中文字符约0.5 token，英文单词约1 token
                estimated_output_tokens = len(full_content) // 2

                # 记录统计
                if self._stats_interceptor and task_id:
                    await self._stats_interceptor.record(
                        agent_name=self.agent_name,
                        model_id=model_id,
                        input_tokens=0,  # 流式模式下无法获取精确值
                        output_tokens=estimated_output_tokens,
                        duration_sec=duration_sec,
                        scene_id=scene_id
                    )

                # 重连成功日志
                if retry_count > 0:
                    self.logger.info(
                        f"LLM流式调用成功（重连后） - Agent: {self.agent_name}, "
                        f"Est. Tokens: {estimated_output_tokens}, Duration: {int(duration_sec * 1000)}ms, "
                        f"重试次数: {retry_count}"
                    )
                else:
                    self.logger.info(
                        f"LLM流式调用完成 - Agent: {self.agent_name}, "
                        f"Est. Tokens: {estimated_output_tokens}, Duration: {int(duration_sec * 1000)}ms"
                    )

                # 流式调用成功完成，退出重试循环
                return

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                error_msg = str(e)[:200]

                # 判断是否应该重试（限流或网络错误）
                if should_retry(e) and attempt < max_retries:
                    # 计算延迟时间（指数退避）
                    delay = calculate_retry_delay(
                        attempt, retry_delay, max_delay=60.0, strategy="exponential")

                    # 确定错误类型描述
                    if is_rate_limit_error(e):
                        error_desc = "API限流(429)"
                    elif is_network_error(e):
                        error_desc = "网络断联"
                    else:
                        error_desc = "临时故障"

                    retry_count += 1
                    self.logger.warning(
                        f"LLM流式调用失败({error_desc})，{delay:.1f}秒后重试... "
                        f"(尝试 {attempt + 1}/{max_retries + 1}): {error_type}: {error_msg}"
                    )

                    # 等待后重试
                    await asyncio.sleep(delay)
                    continue
                else:
                    # 不应该重试或已达到最大重试次数
                    self.logger.error(
                        f"LLM流式调用失败 - Agent: {self.agent_name}, Error: {error_type}: {error_msg}, "
                        f"重试次数: {retry_count}"
                    )
                    raise

        # 不应该到达这里
        if last_error:
            raise last_error

    def _build_system_prompt(
        self,
        role_description: str,
        additional_instructions: str = ""
    ) -> str:
        """构建系统提示词

        Args:
            role_description: 角色描述
            additional_instructions: 附加指令

        Returns:
            完整的系统提示词
        """
        base_prompt = f"""# 角色定义

你是【{self.agent_name}】，一个专业的{role_description}。

## 核心职责

{role_description}

## 工作原则

1. 专业性：始终保持高质量、专业化的输出
2. 一致性：确保内容与上下文保持一致
3. 创意性：在保证质量的前提下，发挥创意
4. 准确性：确保所有信息的准确性和合理性

"""

        if additional_instructions:
            base_prompt += f"""## 特别指令

{additional_instructions}

"""

        return base_prompt

    def _build_error_result(self, error_message: str, **kwargs) -> AgentResult:
        """构建错误结果

        Args:
            error_message: 错误信息
            **kwargs: 其他附加数据

        Returns:
            AgentResult: 包含错误信息的结果
        """
        return AgentResult(
            success=False,
            agent_role=self.agent_role,
            content="",
            errors=[error_message],
            data=kwargs
        )

    def _build_success_result(
        self,
        content: str,
        token_usage: Dict[str, int] = None,
        duration_ms: int = 0,
        model_id: str = "",
        **kwargs
    ) -> AgentResult:
        """构建成功结果

        Args:
            content: 生成的内容
            token_usage: Token使用统计
            duration_ms: 执行耗时
            model_id: 使用的模型ID
            **kwargs: 其他附加数据

        Returns:
            AgentResult: 成功的结果
        """
        return AgentResult(
            success=True,
            agent_role=self.agent_role,
            content=content,
            token_usage=token_usage or {
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            duration_ms=duration_ms,
            model_id=model_id,
            data=kwargs
        )
