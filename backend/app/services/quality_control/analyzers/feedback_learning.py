"""
用户反馈学习模块 - 三维质控v2.0优化

功能：
1. 记录用户对检测结果的反馈(认可/忽略/误报)
2. 基于反馈自动调整检测规则和阈值
3. 学习用户偏好，提供个性化检测

@date: 2026-04-14
@version: v2.0.0
"""
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict

from app.core.logger import get_logger

logger = get_logger("quality_control.feedback_learning")


# ==================== 数据模型 ====================

@dataclass
class UserFeedback:
    """用户反馈记录"""
    feedback_id: str                     # 反馈ID
    user_id: int                         # 用户ID
    project_id: int                      # 项目ID
    issue_id: str                        # 问题ID (如 UL-1, UC-2)
    # 维度 (unit_structure/unit_character/unit_consistency)
    dimension: str
    category: str                        # 问题分类
    # 反馈类型 (accepted/ignored/false_positive)
    feedback_type: str
    feedback_time: str                   # 反馈时间
    comment: str = ""                    # 用户备注
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ThresholdConfig:
    """阈值配置"""
    dimension: str                       # 维度
    category: str                        # 分类
    base_threshold: float                # 基础阈值
    current_threshold: float             # 当前阈值
    adjustment_history: List[Dict] = field(default_factory=list)
    feedback_count: int = 0              # 反馈次数
    false_positive_rate: float = 0.0     # 误报率
    last_updated: str = ""

    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return asdict(self)


# ==================== 反馈学习管理器 ====================

class FeedbackLearningManager:
    """
    用户反馈学习管理器

    负责：
    - 记录和管理用户反馈
    - 基于反馈调整检测阈值
    - 提供个性化检测配置
    """

    def __init__(self, data_dir: str = None):
        # 使用基于backend目录的绝对路径
        if data_dir is None:
            # 获取backend目录的路径
            backend_dir = Path(__file__).parent.parent.parent.parent
            self.data_dir = backend_dir / "data" / "feedback_learning"
        else:
            self.data_dir = Path(data_dir)

        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 内存缓存
        self._feedback_cache: Dict[int, List[UserFeedback]] = defaultdict(list)
        self._threshold_cache: Dict[str, ThresholdConfig] = {}

        # 加载已有数据
        self._load_thresholds()

    def record_feedback(
        self,
        user_id: int,
        project_id: int,
        issue_id: str,
        dimension: str,
        category: str,
        feedback_type: str,
        comment: str = "",
        metadata: Dict = None
    ) -> UserFeedback:
        """
        记录用户反馈

        Args:
            user_id: 用户ID
            project_id: 项目ID
            issue_id: 问题ID
            dimension: 维度
            category: 问题分类
            feedback_type: 反馈类型 (accepted/ignored/false_positive)
            comment: 用户备注
            metadata: 额外元数据

        Returns:
            UserFeedback对象
        """
        feedback = UserFeedback(
            feedback_id=f"FB-{int(time.time()*1000)}",
            user_id=user_id,
            project_id=project_id,
            issue_id=issue_id,
            dimension=dimension,
            category=category,
            feedback_type=feedback_type,
            feedback_time=datetime.now().isoformat(),
            comment=comment,
            metadata=metadata or {}
        )

        # 保存到缓存
        self._feedback_cache[user_id].append(feedback)

        # 持久化到文件
        self._save_feedback(user_id, feedback)

        # 触发阈值调整
        self._adjust_thresholds(user_id, dimension, category, feedback_type)

        logger.info(
            f"记录用户反馈: user={user_id}, issue={issue_id}, "
            f"type={feedback_type}, dimension={dimension}"
        )

        return feedback

    def get_user_feedback(
        self,
        user_id: int,
        dimension: Optional[str] = None,
        feedback_type: Optional[str] = None,
        limit: int = 100
    ) -> List[UserFeedback]:
        """获取用户反馈记录"""
        feedbacks = self._feedback_cache.get(user_id, [])

        # 过滤
        if dimension:
            feedbacks = [f for f in feedbacks if f.dimension == dimension]
        if feedback_type:
            feedbacks = [
                f for f in feedbacks if f.feedback_type == feedback_type]

        # 按时间倒序
        feedbacks = sorted(
            feedbacks, key=lambda x: x.feedback_time, reverse=True)

        return feedbacks[:limit]

    def get_adjusted_threshold(
        self,
        dimension: str,
        category: str,
        base_threshold: float
    ) -> float:
        """
        获取调整后的阈值

        Args:
            dimension: 维度
            category: 分类
            base_threshold: 基础阈值

        Returns:
            调整后的阈值
        """
        key = f"{dimension}:{category}"

        if key in self._threshold_cache:
            return self._threshold_cache[key].current_threshold

        return base_threshold

    def get_false_positive_rate(
        self,
        user_id: int,
        dimension: str,
        category: str
    ) -> float:
        """
        计算特定维度和分类的误报率

        Args:
            user_id: 用户ID
            dimension: 维度
            category: 分类

        Returns:
            误报率 (0.0-1.0)
        """
        feedbacks = [
            f for f in self._feedback_cache.get(user_id, [])
            if f.dimension == dimension and f.category == category
        ]

        if not feedbacks:
            return 0.0

        false_positive_count = sum(
            1 for f in feedbacks if f.feedback_type == "false_positive"
        )

        return false_positive_count / len(feedbacks)

    def _adjust_thresholds(
        self,
        user_id: int,
        dimension: str,
        category: str,
        feedback_type: str
    ):
        """
        基于反馈调整阈值

        策略：
        - 如果用户标记为误报(false_positive)，提高阈值(减少检测)
        - 如果用户接受(accepted)，降低阈值(增强检测)
        - 如果用户忽略(ignored)，轻微提高阈值
        """
        key = f"{dimension}:{category}"

        # 获取或创建阈值配置
        if key not in self._threshold_cache:
            self._threshold_cache[key] = ThresholdConfig(
                dimension=dimension,
                category=category,
                base_threshold=0.3,  # 默认基础阈值
                current_threshold=0.3
            )

        config = self._threshold_cache[key]

        # 计算当前误报率
        false_positive_rate = self.get_false_positive_rate(
            user_id, dimension, category
        )

        # 调整策略
        adjustment = 0.0
        if feedback_type == "false_positive":
            # 误报：提高阈值，减少检测灵敏度
            adjustment = +0.05
        elif feedback_type == "accepted":
            # 接受：降低阈值，增强检测灵敏度
            adjustment = -0.02
        elif feedback_type == "ignored":
            # 忽略：轻微提高阈值
            adjustment = +0.01

        # 应用调整(限制范围)
        old_threshold = config.current_threshold
        config.current_threshold = max(
            0.1, min(0.9, config.current_threshold + adjustment)
        )
        config.feedback_count += 1
        config.false_positive_rate = false_positive_rate
        config.last_updated = datetime.now().isoformat()

        # 记录调整历史
        config.adjustment_history.append({
            "time": datetime.now().isoformat(),
            "feedback_type": feedback_type,
            "old_threshold": old_threshold,
            "new_threshold": config.current_threshold,
            "false_positive_rate": false_positive_rate
        })

        # 限制历史记录数量
        if len(config.adjustment_history) > 50:
            config.adjustment_history = config.adjustment_history[-50:]

        logger.info(
            f"调整阈值: {key}, old={old_threshold:.3f}, "
            f"new={config.current_threshold:.3f}, "
            f"fp_rate={false_positive_rate:.2%}"
        )

    def _save_feedback(self, user_id: int, feedback: UserFeedback):
        """保存反馈到文件"""
        try:
            feedback_file = self.data_dir / f"user_{user_id}_feedback.json"

            # 读取现有数据
            feedbacks = []
            if feedback_file.exists():
                with open(feedback_file, "r", encoding="utf-8") as f:
                    feedbacks = json.load(f)

            # 添加新反馈
            feedbacks.append(feedback.to_dict())

            # 限制文件大小(保留最近500条)
            if len(feedbacks) > 500:
                feedbacks = feedbacks[-500:]

            # 保存
            with open(feedback_file, "w", encoding="utf-8") as f:
                json.dump(feedbacks, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存反馈失败: {e}")

    def _load_thresholds(self):
        """加载阈值配置"""
        try:
            threshold_file = self.data_dir / "thresholds.json"

            if threshold_file.exists():
                with open(threshold_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for key, config_data in data.items():
                    self._threshold_cache[key] = ThresholdConfig(**config_data)

                logger.info(f"加载阈值配置: {len(self._threshold_cache)}条")

        except Exception as e:
            logger.warning(f"加载阈值配置失败: {e}")

    def save_thresholds(self):
        """保存阈值配置"""
        try:
            threshold_file = self.data_dir / "thresholds.json"

            data = {
                key: config.to_dict()
                for key, config in self._threshold_cache.items()
            }

            with open(threshold_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"保存阈值配置: {len(data)}条")

        except Exception as e:
            logger.error(f"保存阈值配置失败: {e}")

    def get_false_positive_rate(
        self,
        user_id: int,
        dimension: str,
        category: str
    ) -> float:
        """
        v1.1增强: 获取指定维度和分类的误报率

        优化点:
        - 考虑时间衰减(最近的反馈权重更高)
        - 考虑样本量(反馈数量少时返回保守值)
        - 支持全局大纲维度(global_*)
        """
        feedbacks = self._feedback_cache.get(user_id, [])

        if not feedbacks:
            return 0.0  # 无反馈时返回0

        # 筛选相关反馈
        relevant_feedbacks = [
            f for f in feedbacks
            if f.dimension == dimension and f.category == category
        ]

        if len(relevant_feedbacks) < 3:
            # 样本量不足,返回保守值
            return 0.2

        # 计算时间衰减权重(最近30天的反馈权重为1,之前递减)
        import time
        current_time = time.time()
        thirty_days_seconds = 30 * 24 * 3600

        weighted_total = 0
        weighted_fp = 0

        for feedback in relevant_feedbacks:
            # 解析反馈时间
            try:
                feedback_time = datetime.fromisoformat(feedback.feedback_time)
                age_seconds = current_time - feedback_time.timestamp()

                # 时间衰减: 指数衰减,30天半衰期
                weight = 2 ** (-age_seconds / thirty_days_seconds)
            except (ValueError, TypeError):
                weight = 0.5  # 解析失败时使用默认权重

            weighted_total += weight
            if feedback.feedback_type == "false_positive":
                weighted_fp += weight

        # 计算加权误报率
        if weighted_total > 0:
            return weighted_fp / weighted_total

        return 0.0

    def get_adaptive_severity(
        self,
        user_id: int,
        dimension: str,
        category: str,
        base_severity: str
    ) -> str:
        """
        v1.1新增: 基于反馈历史自适应调整严重程度

        Args:
            user_id: 用户ID
            dimension: 维度
            category: 分类
            base_severity: 基础严重程度(critical/warning/info)

        Returns:
            调整后的严重程度
        """
        fp_rate = self.get_false_positive_rate(user_id, dimension, category)

        # 根据误报率调整严重程度
        if fp_rate > 0.8:
            # 误报率极高,降级两级
            if base_severity == "critical":
                return "info"
            elif base_severity == "warning":
                return "info"
            else:
                return "info"
        elif fp_rate > 0.5:
            # 误报率较高,降级一级
            if base_severity == "critical":
                return "warning"
            elif base_severity == "warning":
                return "info"
            else:
                return "info"
        elif fp_rate < 0.1:
            # 误报率极低,可以保持或升级
            return base_severity
        else:
            # 正常范围,保持原样
            return base_severity

    def get_user_detection_preferences(self, user_id: int) -> Dict[str, Any]:
        """
        v1.1新增: 获取用户的检测偏好

        分析用户历史反馈,识别:
        - 哪些维度用户更关注(误报率低)
        - 哪些维度用户更宽容(误报率高)
        - 建议的检测深度

        Returns:
            用户偏好配置
        """
        stats = self.get_learning_statistics(user_id)

        if stats["total_feedbacks"] == 0:
            return {
                "preferred_dimensions": [],
                "tolerant_dimensions": [],
                "recommended_depth": "standard",
                "custom_thresholds": {}
            }

        preferred_dims = []
        tolerant_dims = []
        custom_thresholds = {}

        for dim, fp_rate in stats["false_positive_rates"].items():
            if fp_rate < 0.2:
                # 用户认可度高,优先检测
                preferred_dims.append(dim)
                custom_thresholds[dim] = {"strictness": 1.2}  # 更严格
            elif fp_rate > 0.6:
                # 用户认为误报多,降低检测强度
                tolerant_dims.append(dim)
                custom_thresholds[dim] = {"strictness": 0.7}  # 更宽松

        # 根据反馈数量推荐检测深度
        total_feedbacks = stats["total_feedbacks"]
        if total_feedbacks > 50:
            recommended_depth = "deep"  # 丰富反馈,可以深度检测
        elif total_feedbacks > 20:
            recommended_depth = "standard"
        else:
            recommended_depth = "quick"  # 反馈少,快速检测

        return {
            "preferred_dimensions": preferred_dims,
            "tolerant_dimensions": tolerant_dims,
            "recommended_depth": recommended_depth,
            "custom_thresholds": custom_thresholds,
            "confidence": min(total_feedbacks / 50.0, 1.0)  # 置信度
        }

    def generate_feedback_insights(self, user_id: int) -> Dict[str, Any]:
        """
        v1.1新增: 生成反馈洞察报告

        提供:
        - 检测质量趋势
        - 常见问题类型
        - 改进建议

        Returns:
            洞察报告
        """
        stats = self.get_learning_statistics(user_id)
        preferences = self.get_user_detection_preferences(user_id)

        # 分析趋势
        feedbacks = self._feedback_cache.get(user_id, [])
        recent_feedbacks = []

        import time
        current_time = time.time()
        seven_days_seconds = 7 * 24 * 3600

        for feedback in feedbacks:
            try:
                feedback_time = datetime.fromisoformat(feedback.feedback_time)
                age_seconds = current_time - feedback_time.timestamp()
                if age_seconds < seven_days_seconds:
                    recent_feedbacks.append(feedback)
            except (ValueError, TypeError) as parse_err:
                logger.debug(f"解析反馈时间失败: {parse_err}")

        # 生成洞察
        insights = {
            "summary": {
                "total_feedbacks": stats["total_feedbacks"],
                "recent_feedbacks_7d": len(recent_feedbacks),
                "overall_fp_rate": sum(stats["false_positive_rates"].values()) / max(len(stats["false_positive_rates"]), 1)
            },
            "trends": {
                "quality_improving": len(recent_feedbacks) > 0 and (
                    sum(1 for f in recent_feedbacks if f.feedback_type == "accepted") /
                    len(recent_feedbacks) > 0.7
                ),
                "most_problematic_dimension": max(
                    stats["false_positive_rates"].items(),
                    key=lambda x: x[1],
                    default=(None, 0)
                )[0],
                "best_performing_dimension": min(
                    stats["false_positive_rates"].items(),
                    key=lambda x: x[1],
                    default=(None, 1)
                )[0]
            },
            "recommendations": [],
            "user_preferences": preferences
        }

        # 生成建议
        if insights["trends"]["quality_improving"]:
            insights["recommendations"].append(
                "检测质量持续提升,建议使用'deep'深度检测获取更精准的结果"
            )

        if insights["trends"]["most_problematic_dimension"]:
            insights["recommendations"].append(
                f"维度'{insights['trends']['most_problematic_dimension']}'误报率较高,已自动调整检测阈值"
            )

        if len(recent_feedbacks) == 0 and stats["total_feedbacks"] > 0:
            insights["recommendations"].append(
                "最近7天无新反馈,建议对新生成内容进行检测并提供反馈"
            )

        return insights

    def get_learning_statistics(self, user_id: int) -> Dict:
        """
        获取学习统计信息

        Returns:
            统计信息字典
        """
        feedbacks = self._feedback_cache.get(user_id, [])

        if not feedbacks:
            return {
                "total_feedbacks": 0,
                "dimensions": {},
                "false_positive_rates": {}
            }

        # 按维度统计
        dimension_stats = defaultdict(lambda: {
            "total": 0,
            "accepted": 0,
            "ignored": 0,
            "false_positive": 0
        })

        for feedback in feedbacks:
            stats = dimension_stats[feedback.dimension]
            stats["total"] += 1
            stats[feedback.feedback_type] += 1

        # 计算误报率
        fp_rates = {}
        for dim, stats in dimension_stats.items():
            fp_rates[dim] = (
                stats["false_positive"] / stats["total"]
                if stats["total"] > 0 else 0.0
            )

        return {
            "total_feedbacks": len(feedbacks),
            "dimensions": dict(dimension_stats),
            "false_positive_rates": fp_rates,
            "last_feedback_time": feedbacks[-1].feedback_time if feedbacks else None
        }


# ==================== 全局实例 ====================

_feedback_manager = None


def get_feedback_manager() -> FeedbackLearningManager:
    """获取反馈学习管理器单例"""
    global _feedback_manager

    if _feedback_manager is None:
        _feedback_manager = FeedbackLearningManager()

    return _feedback_manager
