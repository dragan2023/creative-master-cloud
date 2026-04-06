"""
多Agent协作文学作品生成系统 - 统计拦截器

模块: agents.writing
文件: stats_interceptor.py
功能: Agent级别的LLM调用统计拦截器，记录每次调用的token数、耗时、费用

依赖关系:
    - 依赖: app.core.config, app.core.logger
    - 被依赖: BaseWritingAgent, AgentOrchestrator

使用说明:
    # 创建拦截器
    interceptor = StatsInterceptor(task_id="task-123", db_session=db)
    
    # 注入到Agent
    agent.set_stats_interceptor(interceptor)
    
    # Agent执行过程中自动记录统计
    result = await agent.execute(context)
    
    # 获取汇总
    summary = interceptor.get_summary()
    
    # 写入数据库
    await interceptor.flush()

创建时间: 2026-03-27
最后修改: 2026-03-27

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import time

from app.core.config import PRESET_MODELS, get_settings
from app.core.logger import get_logger


# 模型定价表（美元/千token）- 2026年参考价格
# 格式: {provider: {model_id: {"input": price, "output": price}}}
MODEL_PRICING = {
    "t8star": {
        # 贞贞AI工坊 - 平价API，价格较低
        "gpt-5.2-pro": {"input": 0.002, "output": 0.006},
        "gpt-5.2-thinking": {"input": 0.003, "output": 0.009},
        "claude-opus-4-5-20251101": {"input": 0.003, "output": 0.015},
        "glm-5": {"input": 0.0005, "output": 0.001},
    },
    "siliconflow": {
        # 硅基流动
        "deepseek-ai/DeepSeek-V3.2": {"input": 0.0005, "output": 0.001},
    },
    "qianwen": {
        # 通义千问
        "qwen3.5-plus": {"input": 0.0008, "output": 0.002},
    },
    "doubao": {
        # 豆包
        "doubao-seed-2-0-pro-260215": {"input": 0.0005, "output": 0.001},
    },
    "openrouter": {
        # OpenRouter
        "google/gemini-3.1-pro-preview": {"input": 0.001, "output": 0.003},
        "openai/gpt-5.2-pro": {"input": 0.002, "output": 0.006},
    },
}


@dataclass
class StatsRecord:
    """单次LLM调用统计记录"""
    agent_name: str
    model_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_sec: float
    estimated_cost: float
    scene_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class StatsInterceptor:
    """Agent级别的LLM调用统计拦截器
    
    记录每次LLM调用的token数、耗时、费用，
    按Agent维度聚合，支持持久化到writing_stats表。
    
    主要功能：
    1. 记录每次LLM调用的统计数据
    2. 按Agent聚合统计
    3. 计算预估费用
    4. 支持异步写入数据库
    """
    
    def __init__(
        self,
        task_id: str,
        db_session=None,
        auto_flush: bool = False,
        flush_threshold: int = 10
    ):
        """初始化统计拦截器
        
        Args:
            task_id: 任务ID
            db_session: 数据库会话（可选，用于持久化）
            auto_flush: 是否自动刷新到数据库
            flush_threshold: 自动刷新的记录数阈值
        """
        self.task_id = task_id
        self.db = db_session
        self.auto_flush = auto_flush
        self.flush_threshold = flush_threshold
        
        self.logger = get_logger(f"stats.{task_id[:8]}")
        self._records: List[StatsRecord] = []
        self._start_time = time.time()
    
    async def record(
        self,
        agent_name: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        duration_sec: float,
        scene_id: Optional[str] = None
    ) -> None:
        """记录一次LLM调用统计
        
        Args:
            agent_name: Agent名称
            model_id: 模型ID
            input_tokens: 输入token数
            output_tokens: 输出token数
            duration_sec: 调用耗时（秒）
            scene_id: 场景ID（可选）
        """
        total_tokens = input_tokens + output_tokens
        estimated_cost = self._calculate_cost(model_id, input_tokens, output_tokens)
        
        record = StatsRecord(
            agent_name=agent_name,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_sec=duration_sec,
            estimated_cost=estimated_cost,
            scene_id=scene_id
        )
        
        self._records.append(record)
        
        self.logger.debug(
            f"统计记录 - Agent: {agent_name}, Model: {model_id}, "
            f"Tokens: {total_tokens} (in: {input_tokens}, out: {output_tokens}), "
            f"Cost: ${estimated_cost:.6f}, Duration: {duration_sec:.2f}s"
        )
        
        # 检查是否需要自动刷新
        if self.auto_flush and self.db and len(self._records) >= self.flush_threshold:
            await self.flush()
    
    def _calculate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """计算预估费用
        
        Args:
            model_id: 模型ID
            input_tokens: 输入token数
            output_tokens: 输出token数
            
        Returns:
            预估费用（美元）
        """
        # 查找模型定价
        pricing = None
        for provider, models in MODEL_PRICING.items():
            if model_id in models:
                pricing = models[model_id]
                break
        
        if not pricing:
            # 默认定价（使用一个中等价格）
            pricing = {"input": 0.001, "output": 0.002}
        
        # 计算费用（美元）
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    async def flush(self) -> None:
        """将缓冲中的统计数据写入数据库
        
        如果没有数据库会话，此方法不做任何操作。
        """
        if not self.db or not self._records:
            return
        
        try:
            # 动态导入避免循环依赖
            from app.models.writing_stats import WritingStats
            from sqlalchemy import insert
            
            # 批量插入
            for record in self._records:
                stat = WritingStats(
                    task_id=self.task_id,
                    agent_name=record.agent_name,
                    model_id=record.model_id,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    total_tokens=record.total_tokens,
                    duration_ms=int(record.duration_sec * 1000),
                    estimated_cost=record.estimated_cost,
                    scene_id=record.scene_id,
                    created_at=record.timestamp
                )
                self.db.add(stat)
            
            await self.db.commit()
            
            self.logger.info(f"统计数据已写入数据库 - 记录数: {len(self._records)}")
            
            # 清空缓冲
            self._records.clear()
            
        except Exception as e:
            self.logger.error(f"写入统计数据失败: {str(e)}")
            await self.db.rollback()
            raise
    
    def get_summary(self) -> Dict[str, Any]:
        """获取汇总统计
        
        Returns:
            包含以下字段的字典:
            - total_tokens: 总token数
            - total_input_tokens: 总输入token数
            - total_output_tokens: 总输出token数
            - total_cost: 总费用（美元）
            - total_duration_sec: 总耗时（秒）
            - call_count: 调用次数
            - by_agent: 按Agent分组的统计
            - by_model: 按模型分组的统计
        """
        if not self._records:
            return {
                "task_id": self.task_id,
                "total_tokens": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "total_duration_sec": 0.0,
                "call_count": 0,
                "by_agent": {},
                "by_model": {}
            }
        
        # 总体统计
        total_tokens = sum(r.total_tokens for r in self._records)
        total_input = sum(r.input_tokens for r in self._records)
        total_output = sum(r.output_tokens for r in self._records)
        total_cost = sum(r.estimated_cost for r in self._records)
        total_duration = sum(r.duration_sec for r in self._records)
        
        # 按Agent聚合
        by_agent: Dict[str, Dict[str, Any]] = {}
        for record in self._records:
            if record.agent_name not in by_agent:
                by_agent[record.agent_name] = {
                    "call_count": 0,
                    "total_tokens": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0,
                    "duration_sec": 0.0,
                    "models_used": set()
                }
            
            agent_stats = by_agent[record.agent_name]
            agent_stats["call_count"] += 1
            agent_stats["total_tokens"] += record.total_tokens
            agent_stats["input_tokens"] += record.input_tokens
            agent_stats["output_tokens"] += record.output_tokens
            agent_stats["cost"] += record.estimated_cost
            agent_stats["duration_sec"] += record.duration_sec
            agent_stats["models_used"].add(record.model_id)
        
        # 转换set为list以便序列化
        for agent_stats in by_agent.values():
            agent_stats["models_used"] = list(agent_stats["models_used"])
        
        # 按模型聚合
        by_model: Dict[str, Dict[str, Any]] = {}
        for record in self._records:
            if record.model_id not in by_model:
                by_model[record.model_id] = {
                    "call_count": 0,
                    "total_tokens": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0
                }
            
            model_stats = by_model[record.model_id]
            model_stats["call_count"] += 1
            model_stats["total_tokens"] += record.total_tokens
            model_stats["input_tokens"] += record.input_tokens
            model_stats["output_tokens"] += record.output_tokens
            model_stats["cost"] += record.estimated_cost
        
        return {
            "task_id": self.task_id,
            "total_tokens": total_tokens,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost": total_cost,
            "total_duration_sec": total_duration,
            "call_count": len(self._records),
            "by_agent": by_agent,
            "by_model": by_model
        }
    
    def get_records(self) -> List[StatsRecord]:
        """获取所有原始记录
        
        Returns:
            统计记录列表
        """
        return self._records.copy()
    
    def clear(self) -> None:
        """清空缓冲区"""
        self._records.clear()
    
    @property
    def record_count(self) -> int:
        """当前缓冲的记录数"""
        return len(self._records)
    
    @property
    def elapsed_time(self) -> float:
        """从创建拦截器到现在经过的时间（秒）"""
        return time.time() - self._start_time
    
    def get_formatted_summary(self) -> str:
        """获取格式化的汇总报告
        
        Returns:
            格式化的文本报告
        """
        summary = self.get_summary()
        
        lines = [
            f"=== LLM调用统计报告 ===",
            f"任务ID: {self.task_id}",
            f"总调用次数: {summary['call_count']}",
            f"总Token数: {summary['total_tokens']:,} (输入: {summary['total_input_tokens']:,}, 输出: {summary['total_output_tokens']:,})",
            f"预估费用: ${summary['total_cost']:.4f}",
            f"总耗时: {summary['total_duration_sec']:.2f}s",
            "",
            "--- 按Agent统计 ---"
        ]
        
        for agent_name, stats in summary["by_agent"].items():
            lines.append(
                f"  {agent_name}: "
                f"{stats['call_count']}次调用, "
                f"{stats['total_tokens']:,} tokens, "
                f"${stats['cost']:.4f}, "
                f"{stats['duration_sec']:.2f}s"
            )
        
        lines.append("")
        lines.append("--- 按模型统计 ---")
        
        for model_id, stats in summary["by_model"].items():
            lines.append(
                f"  {model_id}: "
                f"{stats['call_count']}次调用, "
                f"{stats['total_tokens']:,} tokens, "
                f"${stats['cost']:.4f}"
            )
        
        lines.append("=" * 40)
        
        return "\n".join(lines)


async def create_stats_interceptor(
    task_id: str,
    db_session=None,
    **kwargs
) -> StatsInterceptor:
    """创建统计拦截器的工厂函数
    
    Args:
        task_id: 任务ID
        db_session: 数据库会话
        **kwargs: 其他参数
        
    Returns:
        StatsInterceptor实例
    """
    return StatsInterceptor(
        task_id=task_id,
        db_session=db_session,
        **kwargs
    )
