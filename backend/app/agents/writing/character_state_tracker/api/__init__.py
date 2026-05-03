"""CharacterStateTracker - API层"""
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List


class CharacterStatus(Enum):
    """人物状态枚举"""
    ACTIVE = "active"          # 活跃
    INACTIVE = "inactive"      # 非活跃
    ABSENT = "absent"          # 缺席（未出场且未被提及）
    DEPARTED = "departed"      # 已退场
    DECEASED = "deceased"      # 已死亡
    MENTIONED = "mentioned"    # 被提及


@dataclass
class CharacterState:
    """单个人物的状态数据

    记录人物在特定时间点的完整状态信息。
    """
    name: str                                    # 人物名称
    identity: str = ""                          # 身份/官职
    location: str = ""                          # 所在位置
    status: CharacterStatus = CharacterStatus.ACTIVE  # 当前状态
    status_change: str = ""                     # 本章状态变化描述
    relationships: Dict[str, str] = field(default_factory=dict)  # 与其他人物的关系
    attributes: Dict[str, Any] = field(default_factory=dict)      # 其他属性
    first_appearance: Optional[int] = None      # 首次出场章节
    last_appearance: Optional[int] = None       # 最近出场章节

    # 台词风格特征（新增：用于维护人物语言一致性）
    speech_style: Dict[str, Any] = field(default_factory=dict)
    # speech_style结构:
    # {
    #     "vocabulary_level": "文雅/通俗/专业/市井",  # 词汇层次
    #     "sentence_pattern": "短句/长句/混合/断句",  # 句式偏好
    #     "tone": "严肃/幽默/讽刺/温婉/冷峻",  # 语气基调
    #     "catchphrase": ["口头禅1", "口头禅2"],  # 口头禅/习惯用语
    #     "style_influences": ["古龙式冷艳", "老舍式京味"],  # 受哪些文风影响
    #     "special_habits": ["思考时摸下巴", "紧张时结巴"]  # 特殊语言习惯
    # }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = asdict(self)
        result["status"] = self.status.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterState":
        """从字典创建实例"""
        if "status" in data and isinstance(data["status"], str):
            data["status"] = CharacterStatus(data["status"])
        return cls(**data)

@dataclass
class ChapterSnapshot:
    """章节人物状态快照

    记录单个章节中所有出场人物的状态。
    """
    chapter_num: int                             # 章节号
    chapter_title: str                          # 章节标题
    timestamp: str                              # 记录时间
    characters: Dict[str, CharacterState] = field(
        default_factory=dict)  # 人物状态映射
    new_characters: List[str] = field(default_factory=list)  # 新登场人物
    relationship_changes: List[Dict[str, Any]] = field(
        default_factory=list)  # 关系变化记录

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "chapter_num": self.chapter_num,
            "chapter_title": self.chapter_title,
            "timestamp": self.timestamp,
            "characters": {name: state.to_dict() for name, state in self.characters.items()},
            "new_characters": self.new_characters,
            "relationship_changes": self.relationship_changes
        }

    def format_as_table(self) -> str:
        """格式化为表格形式（用于提示词）"""
        lines = [
            f"### 第{self.chapter_num}章：{self.chapter_title} - 人物状态快照",
            "",
            "| 人物 | 身份/官职 | 所在位置 | 本章状态变化 |",
            "|------|-----------|----------|--------------|"
        ]

        for name, state in self.characters.items():
            lines.append(
                f"| {name} | {state.identity or '-'} | {state.location or '-'} | "
                f"{state.status_change or '无变化'} |"
            )

        return "\n".join(lines)

@dataclass
class RelationshipChange:
    """人物关系变化记录"""
    chapter_num: int                             # 发生章节
    character1: str                             # 人物1
    character2: str                             # 人物2
    relationship_type: str                      # 关系类型（师生/知己/敌对/盟友等）
    previous_state: str = ""                    # 之前的关系状态
    new_state: str = ""                         # 新的关系状态
    description: str = ""                       # 变化描述

