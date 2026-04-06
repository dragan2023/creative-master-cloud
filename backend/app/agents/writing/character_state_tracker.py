"""
多Agent协作文学作品生成系统 - 人物状态追踪器

模块: agents.writing
文件: character_state_tracker.py
功能: 动态追踪人物状态变化，支持章节间状态传递和新人物自动记录

依赖关系:
    - 依赖: app.core.logger
    - 被依赖: OrchestratorAgent, LogicEditorAgent, AgentContext

使用说明:
    tracker = CharacterStateTracker(project_id=1)
    
    # 初始化人物状态
    await tracker.initialize(character_profiles)
    
    # 记录章节状态快照
    snapshot = await tracker.record_chapter_snapshot(
        chapter_num=1,
        chapter_title="初遇",
        content=chapter_content,
        characters_present=["沈无衣", "苏映雪"]
    )
    
    # 获取人物当前状态
    state = tracker.get_character_state("沈无衣")
    
    # 检测新人物
    new_chars = tracker.detect_new_characters(content)
    
    # 更新人物状态
    tracker.update_character_state("沈无衣", {
        "location": "京城",
        "status_change": "晋升为监察御史"
    })

创建时间: 2026-03-29
最后修改: 2026-03-29

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum


class CharacterStatus(Enum):
    """人物状态枚举"""
    ACTIVE = "active"           # 活跃中（当前章节出场）
    MENTIONED = "mentioned"      # 被提及（未出场但被提到）
    ABSENT = "absent"           # 缺席（未出场也未提及）
    DEPARTED = "departed"       # 离场（永久或长期离开）
    DECEASED = "deceased"       # 已故


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


class CharacterStateTracker:
    """人物状态追踪器

    核心功能：
    1. 维护人物状态总表（跨章节的状态演变）
    2. 记录每章的人物状态快照
    3. 追踪人物关系变化
    4. 自动检测新人物
    5. 提供状态一致性检查支持
    """

    def __init__(
        self,
        project_id: int,
        persist_dir: Optional[str] = None
    ):
        """初始化追踪器

        Args:
            project_id: 项目ID
            persist_dir: 持久化目录（可选，默认使用项目数据目录）
        """
        self.project_id = project_id
        self.persist_dir = persist_dir

        # 内存中的状态存储
        self._character_states: Dict[str, CharacterState] = {}  # 人物名 -> 最新状态
        self._chapter_snapshots: Dict[int, ChapterSnapshot] = {}  # 章节号 -> 快照
        self._relationship_history: List[RelationshipChange] = []  # 关系变化历史
        self._character_names: Set[str] = set()  # 已知人物名称集合

        # 已知地点集合（用于位置一致性检查）
        self._known_locations: Set[str] = set()

        # 追踪器状态
        self._initialized = False
        self._current_chapter = 0

        # 延迟导入logger
        from app.core.logger import get_logger
        self.logger = get_logger("character_state_tracker")

    async def initialize(
        self,
        character_profiles: List[Dict[str, Any]],
        world_settings: Optional[Dict[str, Any]] = None
    ) -> None:
        """初始化人物状态追踪器

        从初始人物设定加载人物状态，构建追踪基线。

        Args:
            character_profiles: 初始人物设定列表
            world_settings: 世界观设定（包含地点等）
        """
        self.logger.info(f"初始化人物状态追踪器，项目ID: {self.project_id}")

        # 加载初始人物设定
        for profile in character_profiles:
            name = profile.get("name", "")
            if not name:
                continue

            state = CharacterState(
                name=name,
                identity=profile.get("identity", profile.get("position", "")),
                location=profile.get(
                    "location", profile.get("initial_location", "")),
                status=CharacterStatus.ACTIVE,
                relationships=profile.get("relationships", {}),
                attributes={
                    "personality": profile.get("personality", ""),
                    "background": profile.get("background", ""),
                    "traits": profile.get("traits", []),
                    "age": profile.get("age", ""),
                    "gender": profile.get("gender", "")
                },
                first_appearance=0,  # 初始设定，视为第0章
                last_appearance=0
            )

            self._character_states[name] = state
            self._character_names.add(name)

            # 记录初始位置
            if state.location:
                self._known_locations.add(state.location)

        # 加载世界观中的地点
        if world_settings:
            locations = world_settings.get("locations", [])
            for loc in locations:
                loc_name = loc.get("name", "")
                if loc_name:
                    self._known_locations.add(loc_name)

        self._initialized = True
        self.logger.info(
            f"人物状态追踪器初始化完成，已加载 {len(self._character_states)} 个人物，"
            f"{len(self._known_locations)} 个地点"
        )

    def get_character_state(self, name: str) -> Optional[CharacterState]:
        """获取人物当前状态

        Args:
            name: 人物名称

        Returns:
            人物状态对象，如果不存在返回None
        """
        return self._character_states.get(name)

    def get_all_characters(self) -> Dict[str, CharacterState]:
        """获取所有人物状态"""
        return self._character_states.copy()

    def get_chapter_snapshot(self, chapter_num: int) -> Optional[ChapterSnapshot]:
        """获取指定章节的状态快照

        Args:
            chapter_num: 章节号

        Returns:
            章节快照，如果不存在返回None
        """
        return self._chapter_snapshots.get(chapter_num)

    def get_state_evolution(self, character_name: str) -> List[Dict[str, Any]]:
        """获取指定人物的状态演变历史

        Args:
            character_name: 人物名称

        Returns:
            状态演变列表，每项包含章节号和该章节的状态
        """
        evolution = []

        for chapter_num in sorted(self._chapter_snapshots.keys()):
            snapshot = self._chapter_snapshots[chapter_num]
            if character_name in snapshot.characters:
                state = snapshot.characters[character_name]
                evolution.append({
                    "chapter": chapter_num,
                    "chapter_title": snapshot.chapter_title,
                    "state": state.to_dict()
                })

        return evolution

    def detect_new_characters(self, content: str) -> List[str]:
        """从内容中检测新人物

        使用多种启发式规则检测可能的新人物：
        1. 引号中的对话归属人名（精确化）
        2. 特定格式的角色介绍（带身份描述）
        3. 人物动作描述模式（上下文验证）
        4. 姓名称谓结构
        5. 新增：人物介绍句型（增强版）
        6. 新增：首次提及标记

        Args:
            content: 章节内容

        Returns:
            检测到的新人物名称列表
        """
        new_characters = []

        # 模式1：对话归属 - "xxx"某人说道（更精确的模式）
        # 要求：引号内容后紧跟人物名，然后是对话动词
        dialogue_pattern = r'"[^"]*"[，。]?\s*([一-龥]{2,4})(说道|问道|答道|笑道|怒道|叹道|喊道|叫道|低声道|高声道|沉声道)'
        matches = re.findall(dialogue_pattern, content)
        for match in matches:
            name = match[0] if isinstance(match, tuple) else match
            if name not in self._character_names and self._is_likely_character_name(name):
                new_characters.append(name)

        # 模式2：人物出场描述 - 姓名（身份/介绍）
        # 例如："李明（京城市令）"、"张三，一位老者"
        intro_pattern = r'([一-龥]{2,4})[（\(]([^）\)]{2,20})[）\)]'
        matches = re.findall(intro_pattern, content)
        for match in matches:
            name = match[0] if isinstance(match, tuple) else match
            # 检查括号内容是否像身份描述
            description = match[1] if isinstance(match, tuple) else ""
            if self._is_identity_description(description):
                if name not in self._character_names and self._is_likely_character_name(name):
                    new_characters.append(name)

        # 模式3：人物动作描述 - 姓名后跟特定动作动词
        # 更严格的上下文要求：前面需要有句号或开头
        action_pattern = r'(?:^|。！？)\s*([一-龥]{2,4})(走上前|转过身|抬起头|低下头|开口道|笑着说道|皱眉道|点点头|摇摇头|站起身|坐下来)'
        matches = re.findall(action_pattern, content)
        for match in matches:
            name = match[0] if isinstance(match, tuple) else match
            if name not in self._character_names and self._is_likely_character_name(name):
                new_characters.append(name)

        # 模式4：姓名+称谓结构 - 例如"范大人"、"李公子"、"张将军"
        title_pattern = r'([一-龥]{2,3})(大人|公子|小姐|夫人|将军|王爷|丞相|大夫|掌柜|掌门|前辈|少侠)'
        matches = re.findall(title_pattern, content)
        for match in matches:
            name = match[0] if isinstance(match, tuple) else match
            if name not in self._character_names and self._is_likely_character_name(name):
                new_characters.append(name)

        # 模式5（新增）：人物介绍句型 - "名叫XXX"、"名为XXX"、"叫做XXX"
        intro_sentence_patterns = [
            r'名叫([一-龥]{2,4})',
            r'名为([一-龥]{2,4})',
            r'叫做([一-龥]{2,4})',
            r'名字叫([一-龥]{2,4})',
            r'名字是([一-龥]{2,4})',
            r'(一位|一名)([一-龥]{2,8})?名叫([一-龥]{2,4})',
            r'(有一|来了一)(位|名)([一-龥]{2,8})?，?名叫([一-龥]{2,4})'
        ]
        for pattern in intro_sentence_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # 根据捕获组数量确定名字位置
                if isinstance(match, tuple):
                    # 取最后一个元素（通常是名字）
                    name = match[-1]
                else:
                    name = match
                if name not in self._character_names and self._is_likely_character_name(name):
                    new_characters.append(name)

        # 模式6（新增）：“首次出现”、“第一次见到”等标记
        first_appearance_patterns = [
            r'([一-龥]{2,4})首次(出现|登场|露面)',
            r'([一-龥]{2,4})第一次(出现|登场)',
            r'新(来|出现)(的)?([一-龥]{2,4})',
            r'来了一位名叫([一-龥]{2,4})',
            r'走进(一位|一名)([一-龥]{2,8})?的?([一-龥]{2,4})'
        ]
        for pattern in first_appearance_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    # 取最后一个非空元素
                    name = [m for m in match if m][-1]
                else:
                    name = match
                if name not in self._character_names and self._is_likely_character_name(name):
                    new_characters.append(name)

        # 模式7（新增）：“是XXX”、“为XXX”人物判断句型
        judgement_patterns = [
            r'这位([一-龥]{2,4})(是|便是|正是)',
            r'来者正是([一-龥]{2,4})',
            r'来人是([一-龥]{2,4})',
            r'原来(他|她)是([一-龥]{2,4})'
        ]
        for pattern in judgement_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    # 取最后一个元素
                    name = match[-1] if match[-1] else match[0]
                else:
                    name = match
                if name not in self._character_names and self._is_likely_character_name(name):
                    new_characters.append(name)

        # 去重
        new_characters = list(set(new_characters))

        if new_characters:
            self.logger.info(f"检测到可能的新人物: {new_characters}")
        else:
            self.logger.debug("未检测到新人物")

        return new_characters

    def _is_identity_description(self, text: str) -> bool:
        """判断文本是否像身份描述

        Args:
            text: 括号内的文本

        Returns:
            是否为身份描述
        """
        # 身份描述通常包含以下特征
        identity_keywords = [
            "官", "职", "位", "人", "者", "员", "主", "长", "师",
            "大夫", "先生", "公子", "小姐", "夫人", "将军", "统领",
            "掌柜", "老板", "店小二", "侍女", "丫鬟", "管家"
        ]

        # 排除纯数字和纯时间描述
        if text.isdigit() or re.match(r'^第.+章$', text):
            return False

        # 检查是否包含身份关键词
        return any(kw in text for kw in identity_keywords)

    def _is_likely_character_name(self, name: str) -> bool:
        """判断是否可能是人物名称

        使用多级启发式规则过滤误检：
        - 长度通常在2-4个字符
        - 不是常见的非人物词汇
        - 不是代词、动词、形容词等
        - 不含非人名特征词缀
        """
        # 长度检查
        if len(name) < 2 or len(name) > 4:
            return False

        # 排除常见非人物词汇（大幅扩展）
        non_character_words = {
            # 时间词
            "此时", "这时", "那日", "今日", "当时", "那时", "此刻", "刚才",
            "之后", "之前", "后来", "原来", "开始", "结束", "终于", "正在",
            # 地点/方位词
            "这里", "那里", "哪里", "前面", "后面", "里面", "外面", "旁边",
            "京城", "城里", "宫中", "府中", "房中", "屋内", "门外",
            # 疑问/代词
            "什么", "怎么", "为何", "如何", "哪里", "谁人", "哪个", "多少",
            "某个", "某个", "一些", "这些", "那些", "其他", "别的",
            # 副词/连词
            "忽然", "突然", "只见", "只见得", "正是", "原来是", "也就是",
            "但是", "不过", "虽然", "如果", "因为", "所以", "而且",
            # 动词
            "想到", "看到", "听到", "感觉", "觉得", "知道", "明白", "发现",
            "转身", "抬头", "低头", "开口", "闭口", "出手", "动手",
            # 常见误检词汇
            "退烧药", "抗生素", "阿司匹林", "止痛药", "感冒药",  # 药物
            "高热", "发烧", "咳嗽", "头痛", "腹痛", "受伤", "生病",  # 症状
            "铁炮", "火炮", "长剑", "短刀", "弓箭", "盾牌",  # 武器
            "战马", "马车", "轿子", "船只", "汽车", "火车",  # 交通工具
            "终于", "重重", "轻轻", "慢慢", "渐渐", "微微", "暗暗",  # 副词
            "一路", "一起", "一块", "一边", "一面", "一声",  # 数量/状态
            "老者", "少妇", "青年", "少年", "少女", "孩童", "婴儿",  # 泛指人群（无具体名字）
            "大夫", "医生", "将军", "王爷", "丞相", "大人", "公子",  # 职业称呼（无具体名字）
        }
        if name in non_character_words:
            return False

        # 排除纯代词
        pronouns = {"他", "她", "它", "我", "你", "谁", "某人", "自己", "咱们", "大家"}
        if name in pronouns:
            return False

        # 排除以动词后缀结尾的词
        verb_suffixes = ["得", "了", "着", "过", "起", "开", "出", "入", "来", "去"]
        if any(name.endswith(suffix) for suffix in verb_suffixes):
            return False

        # 排除以形容词后缀结尾的词
        adj_suffixes = ["然", "然地", "得很"]
        if any(name.endswith(suffix) for suffix in adj_suffixes):
            return False

        # 排除数字开头的词
        if name[0].isdigit():
            return False

        # 检查是否全部是汉字（排除混合字符）
        if not all('\u4e00' <= char <= '\u9fff' for char in name):
            return False

        return True

    def detect_new_entities(
        self,
        content: str,
        known_entities: Dict[str, Set[str]] = None
    ) -> Dict[str, List[str]]:
        """
        从内容中检测各类新实体（通用方法）

        这是一个扩展方法，不仅检测新人物，还检测：n        - 新地点
        - 新组织/群体
        - 新物品/道具
        - 新概念/术语

        Args:
            content: 章节内容
            known_entities: 已知实体字典 {"characters": set(), "locations": set(), ...}

        Returns:
            检测到的新实体字典
        """
        if known_entities is None:
            known_entities = {
                "characters": self._character_names,
                "locations": self._known_locations,
                "organizations": set(),
                "items": set(),
                "concepts": set()
            }

        new_entities = {
            "characters": [],
            "locations": [],
            "organizations": [],
            "items": [],
            "concepts": []
        }

        try:
            # 1. 检测新人物（使用现有方法）
            new_characters = self.detect_new_characters(content)
            new_entities["characters"] = [
                c for c in new_characters
                if c not in known_entities.get("characters", set())
            ]

            # 2. 检测新地点
            new_entities["locations"] = self._detect_new_locations(
                content, known_entities.get("locations", set()))

            # 3. 检测新组织
            new_entities["organizations"] = self._detect_new_organizations(
                content, known_entities.get("organizations", set()))

            # 4. 检测新物品
            new_entities["items"] = self._detect_new_items(
                content, known_entities.get("items", set()))

            # 汇总日志
            total_new = sum(len(v) for v in new_entities.values())
            if total_new > 0:
                self.logger.info(
                    f"检测到新实体: 人物={len(new_entities['characters'])}, "
                    f"地点={len(new_entities['locations'])}, "
                    f"组织={len(new_entities['organizations'])}, "
                    f"物品={len(new_entities['items'])}")

        except Exception as e:
            self.logger.error(f"检测新实体失败: {e}")

        return new_entities

    def _detect_new_locations(
        self,
        content: str,
        known_locations: Set[str]
    ) -> List[str]:
        """检测新地点"""
        new_locations = []

        # 地点模式
        location_patterns = [
            r'([一-龥]{2,6})(府|宫|殿|阁|楼|院|堂|斋|轩|亭|园)',  # 建筑名
            r'([一-龥]{2,6})(城|镇|村|山|谷|岭|峰|洞|海|江|河|湖)',  # 地名
            r'来到([一-龥]{2,6})(府|宫|城|镇|村|山)',  # 来到某地
            r'位于([一-龥]{2,6})(之|的)(东|西|南|北)',  # 位于某方位
            r'在([一-龥]{2,6})(之中|之内|之外)',  # 在某范围内
        ]

        for pattern in location_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    location = match[0]
                else:
                    location = match

                if location not in known_locations and len(location) >= 2:
                    new_locations.append(location)

        return list(set(new_locations))

    def _detect_new_organizations(
        self,
        content: str,
        known_orgs: Set[str]
    ) -> List[str]:
        """检测新组织/群体"""
        new_orgs = []

        # 组织模式
        org_patterns = [
            r'([一-龥]{2,6})(门|派|帮|会|盟|教|宗|族|家|院)',  # 门派帮会
            r'([一-龥]{2,6})军',  # 军队
            r'([一-龥]{2,6})卫',  # 卫所
            r'([一-龥]{2,6})营',  # 营地
            r'([一-龥]{2,6})(阁|楼|坊)',  # 组织名
        ]

        for pattern in org_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    org = match[0] + match[1] if len(match) > 1 else match[0]
                else:
                    org = match

                if org not in known_orgs and len(org) >= 2:
                    new_orgs.append(org)

        return list(set(new_orgs))

    def _detect_new_items(
        self,
        content: str,
        known_items: Set[str]
    ) -> List[str]:
        """检测新物品/道具"""
        new_items = []

        # 物品模式
        item_patterns = [
            r'([一-龥]{2,6})(剑|刀|枪|棍|鞭|盾|甲|盔)',  # 武器
            r'([一-龥]{2,6})(丹|药|丸|散)',  # 药物
            r'([一-龥]{2,6})(玉|佩|符|印|令)',  # 信物
            r'([一-龥]{2,6})经',  # 经书
            r'([一-龥]{2,6})谱',  # 谱籍
        ]

        for pattern in item_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    item = match[0] + match[1] if len(match) > 1 else match[0]
                else:
                    item = match

                if item not in known_items and len(item) >= 2:
                    new_items.append(item)

        return list(set(new_items))

    def merge_new_entities_to_global(
        self,
        global_graph,
        new_entities: Dict[str, List[str]],
        chapter_num: int
    ) -> Dict[str, int]:
        """
        将检测到的新实体合并到全局知识图谱

        Args:
            global_graph: 全局知识图谱实例
            new_entities: 新实体字典
            chapter_num: 章节号

        Returns:
            合并结果统计
        """
        result = {
            "characters_added": 0,
            "locations_added": 0,
            "organizations_added": 0,
            "items_added": 0,
            "total_added": 0
        }

        try:
            # 添加新人物
            for char_name in new_entities.get("characters", []):
                entity_data = {
                    "text": char_name,
                    "type": "人物",
                    "level": "micro",
                    "description": f"第{chapter_num}章首次出现",
                    "first_appearance_chapter": chapter_num
                }
                global_graph.add_entity(
                    entity_data, doc_id=f"chapter_{chapter_num}")
                result["characters_added"] += 1

            # 添加新地点
            for loc_name in new_entities.get("locations", []):
                entity_data = {
                    "text": loc_name,
                    "type": "地点",
                    "level": "macro",
                    "description": f"第{chapter_num}章首次提及",
                    "first_appearance_chapter": chapter_num
                }
                global_graph.add_entity(
                    entity_data, doc_id=f"chapter_{chapter_num}")
                result["locations_added"] += 1

            # 添加新组织
            for org_name in new_entities.get("organizations", []):
                entity_data = {
                    "text": org_name,
                    "type": "群体组织",
                    "level": "macro",
                    "description": f"第{chapter_num}章首次提及",
                    "first_appearance_chapter": chapter_num
                }
                global_graph.add_entity(
                    entity_data, doc_id=f"chapter_{chapter_num}")
                result["organizations_added"] += 1

            # 添加新物品
            for item_name in new_entities.get("items", []):
                entity_data = {
                    "text": item_name,
                    "type": "道具物品",
                    "level": "micro",
                    "description": f"第{chapter_num}章首次出现",
                    "first_appearance_chapter": chapter_num
                }
                global_graph.add_entity(
                    entity_data, doc_id=f"chapter_{chapter_num}")
                result["items_added"] += 1

            result["total_added"] = sum([
                result["characters_added"],
                result["locations_added"],
                result["organizations_added"],
                result["items_added"]
            ])

            if result["total_added"] > 0:
                global_graph.save()
                self.logger.info(
                    f"新实体已合并到全局图谱: 章节{chapter_num}, "
                    f"人物={result['characters_added']}, 地点={result['locations_added']}, "
                    f"组织={result['organizations_added']}, 物品={result['items_added']}")

        except Exception as e:
            self.logger.error(f"合并新实体到全局图谱失败: {e}")

        return result

    def update_character_state(
        self,
        name: str,
        updates: Dict[str, Any],
        chapter_num: Optional[int] = None
    ) -> bool:
        """更新人物状态

        Args:
            name: 人物名称
            updates: 更新内容，可包含identity, location, status_change, relationships等
            chapter_num: 当前章节号

        Returns:
            是否更新成功
        """
        if name not in self._character_states:
            # 创建新人物状态
            self._character_states[name] = CharacterState(
                name=name,
                first_appearance=chapter_num,
                last_appearance=chapter_num
            )
            self._character_names.add(name)
            self.logger.info(f"创建新人物状态记录: {name}")

        state = self._character_states[name]

        # 更新各字段
        if "identity" in updates:
            state.identity = updates["identity"]
        if "location" in updates:
            old_location = state.location
            state.location = updates["location"]
            # 记录新地点
            if updates["location"]:
                self._known_locations.add(updates["location"])
        if "status_change" in updates:
            state.status_change = updates["status_change"]
        if "status" in updates:
            if isinstance(updates["status"], str):
                state.status = CharacterStatus(updates["status"])
            else:
                state.status = updates["status"]
        if "relationships" in updates:
            state.relationships.update(updates["relationships"])
        if "attributes" in updates:
            state.attributes.update(updates["attributes"])

        # 更新出场章节
        if chapter_num is not None:
            if state.first_appearance is None:
                state.first_appearance = chapter_num
            state.last_appearance = chapter_num

        self.logger.debug(f"更新人物状态: {name} -> {updates}")
        return True

    def record_chapter_snapshot(
        self,
        chapter_num: int,
        chapter_title: str,
        content: str,
        characters_present: Optional[List[str]] = None,
        character_updates: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> ChapterSnapshot:
        """记录章节人物状态快照

        这是追踪器的核心方法，在每章完成后调用：
        1. 更新出场人物的状态
        2. 检测并记录新人物
        3. 生成状态快照
        4. 更新关系变化

        Args:
            chapter_num: 章节号
            chapter_title: 章节标题
            content: 章节内容
            characters_present: 出场人物列表（可选，不提供则自动检测）
            character_updates: 人物状态更新（可选，由LLM提取）

        Returns:
            生成的章节快照
        """
        self.logger.info(f"记录第{chapter_num}章人物状态快照")

        # 自动检测出场人物（如果未提供）
        if characters_present is None:
            characters_present = self._detect_present_characters(content)

        # 检测新人物
        new_characters = self.detect_new_characters(content)

        # 构建快照
        snapshot_characters: Dict[str, CharacterState] = {}
        new_char_names = []

        for name in characters_present:
            # 获取或创建状态
            if name in self._character_states:
                state = self._character_states[name]
            else:
                # 新人物
                state = CharacterState(
                    name=name,
                    first_appearance=chapter_num,
                    last_appearance=chapter_num
                )
                self._character_states[name] = state
                self._character_names.add(name)
                new_char_names.append(name)

            # 应用外部提供的更新
            if character_updates and name in character_updates:
                updates = character_updates[name]
                if "identity" in updates:
                    state.identity = updates["identity"]
                if "location" in updates:
                    state.location = updates["location"]
                    if updates["location"]:
                        self._known_locations.add(updates["location"])
                if "status_change" in updates:
                    state.status_change = updates["status_change"]
                if "relationships" in updates:
                    state.relationships.update(updates["relationships"])

            state.last_appearance = chapter_num
            state.status = CharacterStatus.ACTIVE

            # 添加到快照
            snapshot_characters[name] = CharacterState(
                name=state.name,
                identity=state.identity,
                location=state.location,
                status=CharacterStatus.ACTIVE,
                status_change=state.status_change,
                relationships=state.relationships.copy(),
                attributes=state.attributes.copy(),
                first_appearance=state.first_appearance,
                last_appearance=state.last_appearance
            )

        # 标记未出场人物状态
        for name, state in self._character_states.items():
            if name not in characters_present:
                # 检查是否被提及
                if name in content:
                    state.status = CharacterStatus.MENTIONED
                else:
                    state.status = CharacterStatus.ABSENT

        # 创建快照
        snapshot = ChapterSnapshot(
            chapter_num=chapter_num,
            chapter_title=chapter_title,
            timestamp=datetime.now().isoformat(),
            characters=snapshot_characters,
            new_characters=new_char_names,
            relationship_changes=[]  # 关系变化由外部检测后添加
        )

        self._chapter_snapshots[chapter_num] = snapshot
        self._current_chapter = chapter_num

        self.logger.info(
            f"第{chapter_num}章快照记录完成: {len(snapshot_characters)}个出场人物，"
            f"{len(new_char_names)}个新人物"
        )

        return snapshot

    def _detect_present_characters(self, content: str) -> List[str]:
        """从内容中检测实际出场人物

        区分“被提及”和“实际出场”：
        - 实际出场：有对话、动作、心理描写等
        - 被提及：仅被他人提到名字

        Args:
            content: 章节内容

        Returns:
            实际出场人物名称列表
        """
        present = []
        mentioned_only = []  # 仅被提及的人物

        for name in self._character_names:
            # 统计名称出现次数
            count = content.count(name)

            if count == 0:
                continue

            # 检查是否有实际出场迹象（对话、动作、心理描写）
            has_dialogue = self._check_character_dialogue(name, content)
            has_action = self._check_character_action(name, content)
            has_mental = self._check_character_mental(name, content)

            if has_dialogue or has_action or has_mental:
                # 有对话/动作/心理描写，认为实际出场
                present.append(name)
            elif count >= 2:
                # 仅被提及，出现2次以上才记录
                mentioned_only.append(name)

        # 记录日志区分出场和提及
        if mentioned_only:
            self.logger.debug(
                f"仅被提及的人物: {mentioned_only}")

        return present

    def _check_character_dialogue(self, name: str, content: str) -> bool:
        """检查人物是否有对话

        Args:
            name: 人物名称
            content: 章节内容

        Returns:
            是否有对话
        """
        # 模式：引号后跟人物名+对话动词
        patterns = [
            rf'"[^"]*"[，。]?\s*{re.escape(name)}(说道|问道|答道|笑道|怒道|叹道|喊道|叫道|低声道|高声道|沉声道)',
            rf'{re.escape(name)}(说道|问道|答道|笑道|怒道|叹道|喊道|叫道)[：:"“]',
            rf'{re.escape(name)}[，。]\s*"',  # 人物名后跟引号
        ]

        for pattern in patterns:
            if re.search(pattern, content):
                return True
        return False

    def _check_character_action(self, name: str, content: str) -> bool:
        """检查人物是否有动作描写

        Args:
            name: 人物名称
            content: 章节内容

        Returns:
            是否有动作描写
        """
        # 模式：句首或句号后跟人物名+动作动词
        action_verbs = [
            '走上前', '转过身', '抬起头', '低下头', '站起身', '坐下来',
            '迈步', '走进', '离开', '来到', '看向', '望向', '伸手', '握住',
            '拱手', '作揖', '行礼', '点头', '摇头', '皱眉', '微笑', '叹气'
        ]

        for verb in action_verbs:
            # 检查是否是主语位置（句首或句号后）
            pattern = rf'(?:^|[。！？\n])\s*{re.escape(name)}{verb}'
            if re.search(pattern, content):
                return True

        return False

    def _check_character_mental(self, name: str, content: str) -> bool:
        """检查人物是否有心理描写

        Args:
            name: 人物名称
            content: 章节内容

        Returns:
            是否有心理描写
        """
        # 模式：人物名+心理动词/形容词
        mental_patterns = [
            rf'{re.escape(name)}(心中|心里|暗自|不禁|不由得)',
            rf'{re.escape(name)}(感到|觉得|想到|想起|意识到)',
            rf'{re.escape(name)}(心中[一二三四五六七八九十]+惊|喜|忧|怒)',
        ]

        for pattern in mental_patterns:
            if re.search(pattern, content):
                return True
        return False

    def add_relationship_change(
        self,
        chapter_num: int,
        char1: str,
        char2: str,
        relationship_type: str,
        previous_state: str,
        new_state: str,
        description: str = ""
    ) -> None:
        """记录人物关系变化

        Args:
            chapter_num: 发生章节
            char1: 人物1
            char2: 人物2
            relationship_type: 关系类型
            previous_state: 之前的关系状态
            new_state: 新的关系状态
            description: 变化描述
        """
        change = RelationshipChange(
            chapter_num=chapter_num,
            character1=char1,
            character2=char2,
            relationship_type=relationship_type,
            previous_state=previous_state,
            new_state=new_state,
            description=description
        )

        self._relationship_history.append(change)

        # 更新到章节快照
        if chapter_num in self._chapter_snapshots:
            snapshot = self._chapter_snapshots[chapter_num]
            snapshot.relationship_changes.append({
                "characters": [char1, char2],
                "type": relationship_type,
                "previous": previous_state,
                "new": new_state,
                "description": description
            })

        self.logger.info(
            f"记录关系变化: {char1} ↔ {char2} ({relationship_type}): "
            f"{previous_state} -> {new_state}"
        )

    def get_relationship_summary(self) -> str:
        """获取人物关系摘要（用于提示词）

        Returns:
            格式化的关系摘要文本
        """
        if not self._relationship_history:
            return "暂无人物关系变化记录"

        lines = ["# 人物关系链追踪表", ""]
        lines.append("| 关系类型 | 涉及人物 | 初始关系 | 最新状态 | 变化章节 |")
        lines.append(
            "|----------|----------|----------|----------|----------|")

        # 按人物对分组
        seen_pairs = set()
        for change in reversed(self._relationship_history):
            pair = tuple(sorted([change.character1, change.character2]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            lines.append(
                f"| {change.relationship_type} | "
                f"{change.character1}↔{change.character2} | "
                f"{change.previous_state or '无'} | "
                f"{change.new_state} | "
                f"第{change.chapter_num}章 |"
            )

        return "\n".join(lines)

    def get_state_summary(self, chapter_num: Optional[int] = None) -> str:
        """获取人物状态摘要（用于提示词）

        Args:
            chapter_num: 章节号（可选，默认使用最新章节）

        Returns:
            格式化的状态摘要文本
        """
        if chapter_num is None:
            chapter_num = self._current_chapter

        if chapter_num and chapter_num in self._chapter_snapshots:
            snapshot = self._chapter_snapshots[chapter_num]
            return snapshot.format_as_table()

        # 返回当前状态总表
        lines = ["# 人物状态总表", ""]

        for name, state in self._character_states.items():
            lines.append(f"## {name}")
            lines.append(f"- 身份/官职: {state.identity or '未设定'}")
            lines.append(f"- 所在位置: {state.location or '未知'}")
            lines.append(f"- 当前状态: {state.status.value}")
            if state.status_change:
                lines.append(f"- 最近变化: {state.status_change}")
            lines.append("")

        return "\n".join(lines)

    def get_evolution_table(self, character_name: str) -> str:
        """获取单个人物的状态演变表（用于提示词）

        Args:
            character_name: 人物名称

        Returns:
            格式化的状态演变表格
        """
        evolution = self.get_state_evolution(character_name)

        if not evolution:
            return f"人物 '{character_name}' 暂无状态演变记录"

        lines = [
            f"# {character_name} 状态演变",
            "",
            "| 章节 | 身份/官职 | 所在位置 | 状态变化 |",
            "|------|-----------|----------|----------|"
        ]

        for entry in evolution:
            state = entry["state"]
            lines.append(
                f"| 第{entry['chapter']}章 | "
                f"{state.get('identity', '-') or '-'} | "
                f"{state.get('location', '-') or '-'} | "
                f"{state.get('status_change', '-') or '-'} |"
            )

        return "\n".join(lines)

    def check_consistency(
        self,
        chapter_num: int,
        content: str
    ) -> Dict[str, Any]:
        """检查人物状态一致性

        检查以下方面：
        1. 人物位置是否合理（是否在合理时间内到达）
        2. 人物身份是否与设定一致
        3. 人物行为是否符合当前状态
        4. 新人物是否有冲突

        Args:
            chapter_num: 章节号
            content: 章节内容

        Returns:
            检查结果，包含issues和warnings
        """
        result = {
            "issues": [],
            "warnings": [],
            "passed": True
        }

        # 获取前一章状态作为参考
        prev_snapshot = self._chapter_snapshots.get(chapter_num - 1)
        if not prev_snapshot:
            return result

        # 检查每个出场人物
        for name, prev_state in prev_snapshot.characters.items():
            if name in content:
                current_state = self._character_states.get(name)
                if not current_state:
                    continue

                # 检查位置合理性
                if prev_state.location and current_state.location:
                    if prev_state.location != current_state.location:
                        # 位置变化，检查是否有过渡
                        if prev_state.location not in content and current_state.location not in content:
                            result["warnings"].append({
                                "type": "location_transition_missing",
                                "character": name,
                                "message": f"人物'{name}'从'{prev_state.location}'到'{current_state.location}'的位置变化缺少过渡描述"
                            })

        if result["issues"]:
            result["passed"] = False

        return result

    def export_to_dict(self) -> Dict[str, Any]:
        """导出追踪器状态为字典（用于持久化）

        Returns:
            包含完整追踪器状态的字典
        """
        return {
            "project_id": self.project_id,
            "initialized": self._initialized,
            "current_chapter": self._current_chapter,
            "character_states": {
                name: state.to_dict()
                for name, state in self._character_states.items()
            },
            "chapter_snapshots": {
                str(num): snapshot.to_dict()
                for num, snapshot in self._chapter_snapshots.items()
            },
            "relationship_history": [
                {
                    "chapter_num": r.chapter_num,
                    "character1": r.character1,
                    "character2": r.character2,
                    "relationship_type": r.relationship_type,
                    "previous_state": r.previous_state,
                    "new_state": r.new_state,
                    "description": r.description
                }
                for r in self._relationship_history
            ],
            "known_locations": list(self._known_locations)
        }

    def import_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典导入追踪器状态

        Args:
            data: 包含追踪器状态的字典
        """
        # 导入人物状态
        self._character_states = {
            name: CharacterState.from_dict(state_data)
            for name, state_data in data.get("character_states", {}).items()
        }

        # 导入章节快照
        self._chapter_snapshots = {}
        for num_str, snapshot_data in data.get("chapter_snapshots", {}).items():
            num = int(num_str)
            characters = {
                name: CharacterState.from_dict(state_data)
                for name, state_data in snapshot_data.get("characters", {}).items()
            }
            self._chapter_snapshots[num] = ChapterSnapshot(
                chapter_num=snapshot_data.get("chapter_num", num),
                chapter_title=snapshot_data.get("chapter_title", ""),
                timestamp=snapshot_data.get("timestamp", ""),
                characters=characters,
                new_characters=snapshot_data.get("new_characters", []),
                relationship_changes=snapshot_data.get(
                    "relationship_changes", [])
            )

        # 导入关系历史
        self._relationship_history = []
        for r_data in data.get("relationship_history", []):
            self._relationship_history.append(RelationshipChange(
                chapter_num=r_data.get("chapter_num", 0),
                character1=r_data.get("character1", ""),
                character2=r_data.get("character2", ""),
                relationship_type=r_data.get("relationship_type", ""),
                previous_state=r_data.get("previous_state", ""),
                new_state=r_data.get("new_state", ""),
                description=r_data.get("description", "")
            ))

        # 导入已知地点
        self._known_locations = set(data.get("known_locations", []))

        # 重建人物名称集合
        self._character_names = set(self._character_states.keys())

        # 更新状态
        self._initialized = data.get("initialized", False)
        self._current_chapter = data.get("current_chapter", 0)

        self.logger.info(
            f"导入追踪器状态完成: {len(self._character_states)}个人物，"
            f"{len(self._chapter_snapshots)}个章节快照"
        )

    async def save(self, file_path: Optional[str] = None) -> bool:
        """保存追踪器状态到文件

        Args:
            file_path: 保存路径（可选，默认使用persist_dir）

        Returns:
            是否保存成功
        """
        if file_path is None:
            if self.persist_dir is None:
                self.logger.warning("未指定保存路径，无法保存追踪器状态")
                return False
            file_path = os.path.join(
                self.persist_dir,
                f"character_state_tracker_{self.project_id}.json"
            )

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            data = self.export_to_dict()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"追踪器状态已保存: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"保存追踪器状态失败: {e}")
            return False

    async def load(self, file_path: Optional[str] = None) -> bool:
        """从文件加载追踪器状态

        Args:
            file_path: 加载路径（可选，默认使用persist_dir）

        Returns:
            是否加载成功
        """
        if file_path is None:
            if self.persist_dir is None:
                self.logger.warning("未指定加载路径，无法加载追踪器状态")
                return False
            file_path = os.path.join(
                self.persist_dir,
                f"character_state_tracker_{self.project_id}.json"
            )

        if not os.path.exists(file_path):
            self.logger.info(f"追踪器状态文件不存在: {file_path}")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.import_from_dict(data)
            self.logger.info(f"追踪器状态已加载: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"加载追踪器状态失败: {e}")
            return False

    def sync_from_knowledge_graph(self, knowledge_graph) -> None:
        """从知识图谱同步人物状态

        将知识图谱中的人物状态追踪实体同步到追踪器中。
        这个方法用于在追踪器初始化后，从已有的知识图谱中恢复人物状态。

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
        """
        try:
            # 获取所有人物的状态实体
            for char_name in self._character_names:
                state_entities = knowledge_graph.get_character_state_entities(
                    character_name=char_name
                )

                # 处理身份变化
                for entity in state_entities.get("identity_changes", []):
                    self.update_character_state(
                        char_name,
                        {
                            "identity": entity.get("text", ""),
                            "status_change": entity.get("description", "")
                        },
                        chapter_num=entity.get("chapter")
                    )

                # 处理位置变化
                location_entities = state_entities.get("location_changes", [])
                if location_entities:
                    # 取最新的位置
                    latest_location = location_entities[-1]
                    self.update_character_state(
                        char_name,
                        {"location": latest_location.get("text", "")},
                        chapter_num=latest_location.get("chapter")
                    )

                # 处理关系变化
                for entity in state_entities.get("relationship_changes", []):
                    desc = entity.get("description", "")
                    text = entity.get("text", "")
                    # 尝试解析关系变化描述
                    self._parse_relationship_change(char_name, text, desc)

            self.logger.info(
                f"从知识图谱同步人物状态完成: {len(self._character_states)}个人物")

        except Exception as e:
            self.logger.error(f"从知识图谱同步人物状态失败: {e}")

    def _parse_relationship_change(self, char_name: str, text: str, description: str) -> None:
        """解析关系变化描述并更新人物关系"""
        # 简单的关系解析逻辑
        # 格式通常是 "与XXX的关系变为YYY" 或 "XXX成为XXX"
        import re

        # 尝试提取目标人物
        patterns = [
            r"与([\\u4e00-\\u9fa5]{2,4})的?关系",
            r"([\\u4e00-\\u9fa5]{2,4})成为",
            r"([\\u4e00-\\u9fa5]{2,4})与([\\u4e00-\\u9fa5]{2,4})"
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                target_char = match.group(1)
                if target_char in self._character_names:
                    # 更新关系
                    if char_name in self._character_states:
                        state = self._character_states[char_name]
                        state.relationships[target_char] = description or text
                break

    def export_to_knowledge_graph(self, knowledge_graph, chapter_num: int = None, only_appeared: bool = True) -> None:
        """导出人物状态到知识图谱

        将追踪器中的人物状态变化导出到知识图谱中作为实体存储。
        通常在章节生成完成后调用。

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            chapter_num: 章节号
            only_appeared: 是否只导出本章节登场的人物（默认True）
                - True: 只导出 last_appearance == chapter_num 的人物（用于单元图谱）
                - False: 导出所有人物（用于全局图谱）
        """
        try:
            entity_count = 0
            relation_count = 0
            appeared_count = 0  # 统计实际登场人物数

            for char_name, state in self._character_states.items():
                # 【关键修复】单元图谱只导出本章节实际登场的人物
                # 判断标准：last_appearance == chapter_num 表示本章节登场
                if only_appeared and chapter_num is not None:
                    if state.last_appearance != chapter_num:
                        # 该人物本章节未登场，跳过
                        self.logger.debug(
                            f"跳过未登场人物: {char_name}, last_appearance={state.last_appearance}, current_chapter={chapter_num}")
                        continue
                    appeared_count += 1

                # 导出人物实体（始终导出，确保图谱有基础节点）
                knowledge_graph.add_entity({
                    "text": char_name,
                    "type": "人物",
                    "level": "macro",
                    "description": f"身份: {state.identity or '未知'}，位置: {state.location or '未知'}"
                }, doc_id=f"chapter_{chapter_num}")
                entity_count += 1

                # 导出身份变化（有变化时才记录）
                if state.status_change and state.identity:
                    knowledge_graph.add_entity({
                        "text": state.identity,
                        "type": "身份变化",
                        "level": "micro",
                        "character": char_name,
                        "chapter": chapter_num or state.last_appearance,
                        "description": state.status_change
                    }, doc_id=f"chapter_{chapter_num}")
                    entity_count += 1

                    # 添加身份变化关系
                    knowledge_graph.add_relation({
                        "source": char_name,
                        "target": state.identity,
                        "relation": "身份转变为",
                        "context": state.status_change
                    }, doc_id=f"chapter_{chapter_num}")
                    relation_count += 1

                # 导出位置变化
                if state.location:
                    knowledge_graph.add_entity({
                        "text": state.location,
                        "type": "位置变化",
                        "level": "micro",
                        "character": char_name,
                        "chapter": chapter_num or state.last_appearance,
                        "description": f"当前位置: {state.location}"
                    }, doc_id=f"chapter_{chapter_num}")
                    entity_count += 1

                    # 添加位置关系
                    knowledge_graph.add_relation({
                        "source": char_name,
                        "target": state.location,
                        "relation": "位于",
                        "context": f"第{chapter_num or state.last_appearance}章位置"
                    }, doc_id=f"chapter_{chapter_num}")
                    relation_count += 1

                # 导出关系变化
                for related_char, relation in state.relationships.items():
                    knowledge_graph.add_entity({
                        "text": f"{char_name}与{related_char}",
                        "type": "关系变化",
                        "level": "micro",
                        "character": char_name,
                        "chapter": chapter_num or state.last_appearance,
                        "description": relation
                    }, doc_id=f"chapter_{chapter_num}")
                    entity_count += 1

                    # 添加关系边
                    knowledge_graph.add_relation({
                        "source": char_name,
                        "target": related_char,
                        "relation": "关联人物",
                        "context": relation
                    }, doc_id=f"chapter_{chapter_num}")
                    relation_count += 1

                # 导出性格发展、能力成长、心理状态、行为模式（存储在attributes中）
                attr_type_mapping = {
                    "性格发展": "性格发展",
                    "心理状态": "心理状态",
                    "能力成长": "能力成长",
                    "行为模式": "行为模式"
                }
                for attr_key, entity_type in attr_type_mapping.items():
                    attr_value = state.attributes.get(
                        attr_key, "") or state.attributes.get(attr_key.lower(), "")
                    if attr_value:
                        knowledge_graph.add_entity({
                            "text": attr_value if len(attr_value) <= 20 else attr_value[:20],
                            "type": entity_type,
                            "level": "micro",
                            "character": char_name,
                            "chapter": chapter_num or state.last_appearance,
                            "description": attr_value
                        }, doc_id=f"chapter_{chapter_num}")
                        entity_count += 1

            # 构建日志信息
            if only_appeared and chapter_num is not None:
                self.logger.info(
                    f"导出人物状态到单元图谱完成: 章节{chapter_num}, "
                    f"本章节登场人物={appeared_count}个, "
                    f"总实体={entity_count}个, 关系={relation_count}条 "
                    f"(已过滤{len(self._character_states) - appeared_count}个未登场人物)")
            else:
                self.logger.info(
                    f"导出人物状态到知识图谱完成: 章节{chapter_num}, "
                    f"{len(self._character_states)}个人物, "
                    f"{entity_count}个实体, {relation_count}个关系")

        except Exception as e:
            self.logger.error(f"导出人物状态到知识图谱失败: {e}")

    def export_character_profiles_to_knowledge_graph(
        self,
        knowledge_graph,
        character_profiles: List[Dict[str, Any]] = None
    ) -> None:
        """导出人物设定到全局知识图谱

        将人物的基础设定（性格、背景、关系等）作为持久化实体存入全局知识图谱。
        这些设定不会随章节变化，是人物的常态属性。

        Args:
            knowledge_graph: NovelKnowledgeGraph实例（全局图谱）
            character_profiles: 人物设定列表（可选，默认使用追踪器中的状态）
        """
        try:
            entity_count = 0

            # 使用传入的设定或追踪器中的状态
            profiles_to_export = character_profiles or []

            # 如果没有传入设定，从追踪器状态构建
            if not profiles_to_export:
                for char_name, state in self._character_states.items():
                    profile = {
                        "name": char_name,
                        "identity": state.identity,
                        "location": state.location,
                        **state.attributes
                    }
                    profiles_to_export.append(profile)

            for profile in profiles_to_export:
                char_name = profile.get("name", "")
                if not char_name:
                    continue

                # 创建人物设定实体
                profile_entity = {
                    "text": char_name,
                    "type": "人物设定",
                    "level": "macro",
                    "description": self._build_profile_description(profile)
                }

                # 添加详细属性
                attributes = {}
                if profile.get("identity"):
                    attributes["身份"] = profile.get("identity")
                if profile.get("role"):
                    attributes["角色定位"] = profile.get("role")
                if profile.get("personality"):
                    attributes["性格特点"] = profile.get("personality")
                if profile.get("background"):
                    attributes["背景故事"] = profile.get("background")
                if profile.get("age"):
                    attributes["年龄"] = profile.get("age")
                if profile.get("gender"):
                    attributes["性别"] = profile.get("gender")
                if profile.get("location") or profile.get("initial_location"):
                    attributes["初始位置"] = profile.get(
                        "location") or profile.get("initial_location")
                if profile.get("goals"):
                    attributes["目标动机"] = profile.get("goals")

                if attributes:
                    profile_entity["attributes"] = attributes

                knowledge_graph.add_entity(
                    profile_entity, doc_id="character_profiles")
                entity_count += 1

                # 导出人物关系作为图谱边
                relationships = profile.get("relationships", {})
                for related_char, relation_desc in relationships.items():
                    knowledge_graph.add_relation({
                        "source": char_name,
                        "target": related_char,
                        "relation": "人物关系",
                        "context": relation_desc
                    }, doc_id="character_profiles")

            # 保存图谱
            knowledge_graph.save()

            self.logger.info(
                f"导出人物设定到全局图谱完成: {entity_count}个人物设定")

        except Exception as e:
            self.logger.error(f"导出人物设定到全局图谱失败: {e}")

    # ==================== 全局知识图谱动态更新方法 ====================

    def sync_unit_to_global_graph(
        self,
        global_graph,
        unit_graph,
        chapter_num: int,
        sync_extended_entities: bool = True
    ) -> Dict[str, Any]:
        """将单元图谱的实体同步到全局知识图谱

        将章节级别的人物状态变化合并到全局图谱，确保全局图谱反映最新故事状态。
        实现正文优先原则：以正文内容为准更新知识图谱。

        增强功能：
        1. 支持扩展实体同步（设施、事件、群体、道具、伏笔等）
        2. 新实体自动检测与合并
        3. 实体信息增量更新
        4. 关系网络同步

        Args:
            global_graph: 全局知识图谱实例
            unit_graph: 单元知识图谱实例
            chapter_num: 章节号
            sync_extended_entities: 是否同步扩展实体（默认True）

        Returns:
            同步结果摘要，包含更新数量和冲突信息
        """
        result = {
            "chapter": chapter_num,
            "entities_synced": 0,
            "relations_synced": 0,
            "profiles_updated": 0,
            "new_entities": [],
            "extended_entities_synced": {
                "facilities": 0,
                "events": 0,
                "groups": 0,
                "items": 0,
                "foreshadows": 0,
                "world_rules": 0,
                "time_nodes": 0
            },
            "conflicts": []
        }

        try:
            # 1. 获取单元图谱中的所有实体
            unit_entities = self._get_all_entities_from_graph(unit_graph)
            unit_relations = self._get_all_relations_from_graph(unit_graph)

            # 2. 将实体同步到全局图谱
            for entity in unit_entities:
                entity_type = entity.get("type", "")
                entity_text = entity.get("text", "")

                # 检查是否为新实体（全局图谱中不存在）
                is_new_entity = not self._entity_exists_in_graph(
                    global_graph, entity_text)

                # 跳过人物设定实体（这些会被动态更新）
                if entity_type == "人物设定":
                    continue

                # 同步实体
                global_graph.add_entity(
                    entity, doc_id=f"chapter_{chapter_num}")
                result["entities_synced"] += 1

                # 记录新实体
                if is_new_entity:
                    result["new_entities"].append({
                        "text": entity_text,
                        "type": entity_type,
                        "chapter": chapter_num
                    })

                # 统计扩展实体
                if sync_extended_entities:
                    self._count_extended_entity(result, entity_type)

            # 3. 将关系同步到全局图谱
            for relation in unit_relations:
                global_graph.add_relation(
                    relation, doc_id=f"chapter_{chapter_num}")
                result["relations_synced"] += 1

            # 4. 检测冲突并更新人物设定
            conflicts = self._detect_and_resolve_conflicts(
                global_graph, unit_entities, chapter_num)
            result["conflicts"] = conflicts
            result["profiles_updated"] = len(
                [c for c in conflicts if c.get("resolved")])

            # 5. 同步扩展实体的关系网络
            if sync_extended_entities:
                self._sync_extended_relations(
                    global_graph, unit_graph, chapter_num, result)

            # 6. 保存全局图谱
            global_graph.save()

            # 7. 记录同步日志
            new_entity_count = len(result["new_entities"])
            self.logger.info(
                f"单元图谱同步到全局图谱完成: 章节{chapter_num}, "
                f"实体={result['entities_synced']}, 关系={result['relations_synced']}, "
                f"新实体={new_entity_count}, 设定更新={result['profiles_updated']}, 冲突={len(result['conflicts'])}")

            # 如果有新实体，记录详细信息
            if result["new_entities"]:
                self.logger.info(
                    f"检测到新实体: {[e['text'] for e in result['new_entities'][:10]]}")

        except Exception as e:
            self.logger.error(f"同步单元图谱到全局图谱失败: {e}")

        return result

    def _get_all_entities_from_graph(self, knowledge_graph) -> List[Dict[str, Any]]:
        """从知识图谱中获取所有实体

        Args:
            knowledge_graph: NovelKnowledgeGraph实例

        Returns:
            实体列表
        """
        entities = []
        try:
            # 遍历图谱中的所有节点
            import networkx as nx
            graph = knowledge_graph.graph

            for node_id, node_data in graph.nodes(data=True):
                if node_data.get("type") in ["人物", "身份变化", "位置变化", "关系变化",
                                             "性格发展", "能力成长", "心理状态", "行为模式",
                                             "设施", "事件", "群体组织", "道具物品",
                                             "伏笔", "世界规则", "时间节点"]:
                    entity = {
                        "text": node_data.get("text", node_id),
                        "type": node_data.get("type", ""),
                        "level": node_data.get("level", "micro"),
                        "chapter": node_data.get("chapter"),
                        "description": node_data.get("description", ""),
                        "attributes": node_data.get("attributes", {})
                    }
                    if node_data.get("character"):
                        entity["character"] = node_data.get("character")
                    entities.append(entity)

        except Exception as e:
            self.logger.error(f"获取图谱实体失败: {e}")

        return entities

    def _get_all_relations_from_graph(self, knowledge_graph) -> List[Dict[str, Any]]:
        """从知识图谱中获取所有关系

        Args:
            knowledge_graph: NovelKnowledgeGraph实例

        Returns:
            关系列表
        """
        relations = []
        try:
            graph = knowledge_graph.graph

            for source, target, edge_data in graph.edges(data=True):
                relation = {
                    "source": source,
                    "target": target,
                    "relation": edge_data.get("relation", "关联"),
                    "context": edge_data.get("context", ""),
                    "chapter": edge_data.get("chapter")
                }
                relations.append(relation)

        except Exception as e:
            self.logger.error(f"获取图谱关系失败: {e}")

        return relations

    def _entity_exists_in_graph(self, knowledge_graph, entity_text: str) -> bool:
        """检查实体是否存在于知识图谱中

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            entity_text: 实体文本

        Returns:
            是否存在
        """
        try:
            # 使用实体索引快速查找
            if hasattr(knowledge_graph, 'entity_index'):
                return entity_text in knowledge_graph.entity_index

            # 回退到遍历查找
            graph = knowledge_graph.graph
            for node_id, node_data in graph.nodes(data=True):
                if node_data.get("text") == entity_text:
                    return True
            return False

        except Exception as e:
            self.logger.error(f"检查实体存在失败: {entity_text}, {e}")
            return False

    def _count_extended_entity(self, result: Dict[str, Any], entity_type: str) -> None:
        """统计扩展实体类型

        Args:
            result: 结果字典
            entity_type: 实体类型
        """
        extended_counts = result["extended_entities_synced"]

        # 设施相关
        if entity_type in ["设施", "设施状态变化", "设施归属变更", "设施物理状态"]:
            extended_counts["facilities"] += 1
        # 事件相关
        elif entity_type in ["事件", "事件状态变化", "事件影响", "事件因果链", "详细事件"]:
            extended_counts["events"] += 1
        # 群体相关
        elif entity_type in ["群体组织", "群体状态变化", "群体成员变动", "群体关系变化"]:
            extended_counts["groups"] += 1
        # 道具相关
        elif entity_type in ["道具物品", "道具状态变化", "道具归属变更", "道具功能使用"]:
            extended_counts["items"] += 1
        # 伏笔相关
        elif entity_type in ["伏笔", "伏笔回收"]:
            extended_counts["foreshadows"] += 1
        # 世界规则相关
        elif entity_type in ["世界规则", "规则引用", "规则例外", "世界观规则"]:
            extended_counts["world_rules"] += 1
        # 时间节点相关
        elif entity_type in ["时间节点", "时间流逝"]:
            extended_counts["time_nodes"] += 1

    def _sync_extended_relations(
        self,
        global_graph,
        unit_graph,
        chapter_num: int,
        result: Dict[str, Any]
    ) -> None:
        """同步扩展实体的关系网络

        确保扩展实体之间的关系也被同步到全局图谱。
        包括：
        - 人物与设施的归属关系
        - 事件与人物的参与关系
        - 群体与人物的关系
        - 道具与人物的持有关系
        - 伏笔与事件的关联关系

        Args:
            global_graph: 全局知识图谱
            unit_graph: 单元知识图谱
            chapter_num: 章节号
            result: 结果字典
        """
        try:
            # 定义需要特别处理的关系类型
            extended_relation_types = {
                "属于", "拥有", "持有", "使用", "参与", "引发",
                "导致", "关联", "关联人物", "发生于", "触发于"
            }

            graph = unit_graph.graph
            synced_count = 0

            for source, target, edge_data in graph.edges(data=True):
                relation_type = edge_data.get("relation", "")

                # 只处理扩展关系类型
                if relation_type not in extended_relation_types:
                    continue

                # 检查源节点和目标节点类型
                source_data = graph.nodes.get(source, {})
                target_data = graph.nodes.get(target, {})

                source_type = source_data.get("type", "")
                target_type = target_data.get("type", "")

                # 扩展实体相关的关系
                extended_types = {
                    "设施", "事件", "群体组织", "道具物品", "伏笔",
                    "世界规则", "时间节点", "详细事件"
                }

                if source_type in extended_types or target_type in extended_types:
                    # 构建关系数据
                    relation_data = {
                        "source": source_data.get("text", source),
                        "target": target_data.get("text", target),
                        "relation": relation_type,
                        "context": edge_data.get("context", ""),
                        "chapter": chapter_num
                    }

                    # 同步到全局图谱
                    global_graph.add_relation(
                        relation_data, doc_id=f"chapter_{chapter_num}")
                    synced_count += 1

            if synced_count > 0:
                self.logger.info(f"同步扩展关系: {synced_count}条")

        except Exception as e:
            self.logger.error(f"同步扩展关系失败: {e}")

    def _detect_and_resolve_conflicts(
        self,
        global_graph,
        unit_entities: List[Dict[str, Any]],
        chapter_num: int
    ) -> List[Dict[str, Any]]:
        """检测并解决正文内容与初始设定的冲突

        实现正文优先原则：
        1. 检测正文中的状态变化与初始设定是否冲突
        2. 以正文为准更新全局图谱中的人物设定
        3. 记录冲突信息用于报告

        Args:
            global_graph: 全局知识图谱
            unit_entities: 单元图谱中的实体列表
            chapter_num: 章节号

        Returns:
            检测到的冲突列表
        """
        conflicts = []

        try:
            # 按人物分组实体
            character_entities = {}
            for entity in unit_entities:
                char_name = entity.get("character", "")
                if char_name:
                    if char_name not in character_entities:
                        character_entities[char_name] = []
                    character_entities[char_name].append(entity)

            # 检测每个有变化的人物的冲突
            for char_name, entities in character_entities.items():
                # 获取初始设定
                initial_profile = self._get_character_profile_from_graph(
                    global_graph, char_name)

                if not initial_profile:
                    continue

                # 检测各类冲突
                for entity in entities:
                    entity_type = entity.get("type", "")
                    entity_text = entity.get("text", "")

                    conflict = None

                    # 身份变化冲突检测
                    if entity_type == "身份变化":
                        initial_identity = initial_profile.get(
                            "attributes", {}).get("身份", "")
                        if initial_identity and initial_identity != entity_text:
                            conflict = {
                                "character": char_name,
                                "type": "身份变化",
                                "initial_value": initial_identity,
                                "new_value": entity_text,
                                "chapter": chapter_num,
                                "description": f"{char_name}的身份从'{initial_identity}'变为'{entity_text}'",
                                "resolved": True
                            }
                            # 更新人物设定
                            self._update_character_profile_in_graph(
                                global_graph, char_name,
                                {"身份": entity_text}, chapter_num)

                    # 位置变化冲突检测
                    elif entity_type == "位置变化":
                        initial_location = initial_profile.get(
                            "attributes", {}).get("初始位置", "")
                        if initial_location and initial_location != entity_text:
                            conflict = {
                                "character": char_name,
                                "type": "位置变化",
                                "initial_value": initial_location,
                                "new_value": entity_text,
                                "chapter": chapter_num,
                                "description": f"{char_name}的位置从'{initial_location}'变为'{entity_text}'",
                                "resolved": True
                            }
                            # 更新人物设定
                            self._update_character_profile_in_graph(
                                global_graph, char_name,
                                {"当前位置": entity_text}, chapter_num)

                    # 性格发展冲突检测
                    elif entity_type == "性格发展":
                        initial_personality = initial_profile.get(
                            "attributes", {}).get("性格特点", "")
                        if initial_personality:
                            conflict = {
                                "character": char_name,
                                "type": "性格发展",
                                "initial_value": initial_personality,
                                "new_value": entity.get("description", entity_text),
                                "chapter": chapter_num,
                                "description": f"{char_name}的性格有所发展",
                                "resolved": True
                            }
                            # 追加性格发展记录
                            self._append_character_attribute_in_graph(
                                global_graph, char_name, "性格发展记录",
                                f"第{chapter_num}章: {entity.get('description', entity_text)}")

                    if conflict:
                        conflicts.append(conflict)

            if conflicts:
                self.logger.info(
                    f"检测到 {len(conflicts)} 个设定冲突，已按正文内容更新全局图谱")

        except Exception as e:
            self.logger.error(f"检测冲突失败: {e}")

        return conflicts

    def _get_character_profile_from_graph(
        self,
        knowledge_graph,
        char_name: str
    ) -> Optional[Dict[str, Any]]:
        """从知识图谱中获取人物设定

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            char_name: 人物名称

        Returns:
            人物设定字典，如果不存在返回None
        """
        try:
            graph = knowledge_graph.graph

            for node_id, node_data in graph.nodes(data=True):
                if node_data.get("type") == "人物设定" and node_data.get("text") == char_name:
                    return {
                        "text": node_id,
                        "type": node_data.get("type"),
                        "description": node_data.get("description", ""),
                        "attributes": node_data.get("attributes", {})
                    }
        except Exception as e:
            self.logger.error(f"获取人物设定失败: {char_name}, {e}")

        return None

    def _update_character_profile_in_graph(
        self,
        knowledge_graph,
        char_name: str,
        updates: Dict[str, Any],
        chapter_num: int
    ) -> bool:
        """更新全局知识图谱中的人物设定

        以正文内容为准，动态更新人物设定属性。

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            char_name: 人物名称
            updates: 要更新的属性字典
            chapter_num: 章节号

        Returns:
            是否更新成功
        """
        try:
            graph = knowledge_graph.graph

            # 查找人物设定节点
            for node_id, node_data in graph.nodes(data=True):
                if node_data.get("type") == "人物设定" and node_data.get("text") == char_name:
                    # 更新属性
                    attributes = node_data.get("attributes", {})
                    for key, value in updates.items():
                        old_value = attributes.get(key, "")
                        attributes[key] = value

                        # 记录变更历史
                        history_key = f"{key}_变更历史"
                        history = attributes.get(history_key, [])
                        if not isinstance(history, list):
                            history = []
                        history.append({
                            "chapter": chapter_num,
                            "old_value": old_value,
                            "new_value": value
                        })
                        attributes[history_key] = history

                    node_data["attributes"] = attributes

                    # 更新描述
                    node_data["description"] = self._build_profile_description_from_attrs(
                        attributes)
                    node_data["last_updated_chapter"] = chapter_num

                    self.logger.info(
                        f"更新人物设定: {char_name}, 属性={list(updates.keys())}, 章节={chapter_num}")
                    return True

            # 如果没找到现有节点，创建新的
            self._create_character_profile_in_graph(
                knowledge_graph, char_name, updates, chapter_num)
            return True

        except Exception as e:
            self.logger.error(f"更新人物设定失败: {char_name}, {e}")
            return False

    def _create_character_profile_in_graph(
        self,
        knowledge_graph,
        char_name: str,
        attributes: Dict[str, Any],
        chapter_num: int
    ) -> None:
        """在全局图谱中创建新的人物设定节点

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            char_name: 人物名称
            attributes: 属性字典
            chapter_num: 章节号
        """
        try:
            profile_entity = {
                "text": char_name,
                "type": "人物设定",
                "level": "macro",
                "description": self._build_profile_description_from_attrs(attributes),
                "attributes": attributes,
                "first_appearance_chapter": chapter_num,
                "last_updated_chapter": chapter_num
            }

            knowledge_graph.add_entity(
                profile_entity, doc_id="character_profiles")

            self.logger.info(
                f"创建人物设定节点: {char_name}, 章节={chapter_num}")

        except Exception as e:
            self.logger.error(f"创建人物设定节点失败: {char_name}, {e}")

    def _append_character_attribute_in_graph(
        self,
        knowledge_graph,
        char_name: str,
        attr_name: str,
        value: str
    ) -> None:
        """追加人物属性记录（用于性格发展等累积性属性）

        Args:
            knowledge_graph: NovelKnowledgeGraph实例
            char_name: 人物名称
            attr_name: 属性名称
            value: 要追加的值
        """
        try:
            graph = knowledge_graph.graph

            for node_id, node_data in graph.nodes(data=True):
                if node_data.get("type") == "人物设定" and node_data.get("text") == char_name:
                    attributes = node_data.get("attributes", {})

                    # 获取或创建列表
                    existing = attributes.get(attr_name, [])
                    if not isinstance(existing, list):
                        existing = [existing] if existing else []

                    existing.append(value)
                    attributes[attr_name] = existing
                    node_data["attributes"] = attributes

                    self.logger.debug(
                        f"追加人物属性: {char_name}.{attr_name} += {value}")
                    return

        except Exception as e:
            self.logger.error(f"追加人物属性失败: {char_name}, {e}")

    def _build_profile_description_from_attrs(self, attributes: Dict[str, Any]) -> str:
        """从属性字典构建人物设定描述

        Args:
            attributes: 属性字典

        Returns:
            格式化的描述文本
        """
        parts = []

        # 主要属性
        main_attrs = [
            ("角色定位", "角色"),
            ("身份", "身份"),
            ("性格特点", "性格"),
            ("年龄", "年龄"),
            ("性别", "性别"),
            ("当前位置", "位置")
        ]

        for attr_key, display_name in main_attrs:
            if attributes.get(attr_key):
                parts.append(f"{display_name}: {attributes[attr_key]}")

        # 背景故事（截取前50字）
        if attributes.get("背景故事"):
            bg = attributes["背景故事"]
            if len(bg) > 50:
                bg = bg[:50] + "..."
            parts.append(f"背景: {bg}")

        return " | ".join(parts) if parts else "人物设定"

    def _build_profile_description(self, profile: Dict[str, Any]) -> str:
        """构建人物设定描述文本

        Args:
            profile: 人物设定字典

        Returns:
            格式化的描述文本
        """
        parts = []

        if profile.get("role"):
            parts.append(f"角色: {profile['role']}")
        if profile.get("identity"):
            parts.append(f"身份: {profile['identity']}")
        if profile.get("personality"):
            parts.append(f"性格: {profile['personality']}")
        if profile.get("background"):
            # 背景可能较长，截取前100字
            bg = profile['background']
            if len(bg) > 100:
                bg = bg[:100] + "..."
            parts.append(f"背景: {bg}")
        if profile.get("age"):
            parts.append(f"年龄: {profile['age']}")
        if profile.get("gender"):
            parts.append(f"性别: {profile['gender']}")

        return " | ".join(parts) if parts else "人物设定"

    def get_state_for_prompt(self, chapter_num: int = None) -> str:
        """获取人物状态摘要用于写作提示词

        返回格式化的人物状态信息，供写作Agent在生成下一章时使用。

        Args:
            chapter_num: 章节号（可选，只显示到该章节为止的状态）

        Returns:
            格式化的人物状态文本
        """
        lines = ["# 人物状态追踪摘要", ""]
        lines.append("以下是各主要人物到当前为止的状态，请在写作时保持一致性：")
        lines.append("")

        for char_name, state in self._character_states.items():
            # 只显示活跃或最近出场的人物
            if state.status == CharacterStatus.ABSENT and state.last_appearance:
                if chapter_num and (chapter_num - state.last_appearance) > 3:
                    continue  # 超过3章未出场，跳过

            lines.append(f"## {char_name}")

            if state.identity:
                lines.append(f"- 身份/官职: {state.identity}")
            if state.location:
                lines.append(f"- 所在位置: {state.location}")
            if state.status_change:
                lines.append(f"- 最近变化: {state.status_change}")
            if state.relationships:
                lines.append("- 人物关系:")
                for related, relation in state.relationships.items():
                    lines.append(f"  - 与{related}: {relation}")

            attrs = state.attributes
            if attrs:
                personality = attrs.get("personality", attrs.get("性格", ""))
                if personality:
                    lines.append(f"- 性格特点: {personality}")

            lines.append("")

        # 添加关系变化历史
        if self._relationship_history:
            lines.append("## 人物关系变化历史")
            lines.append(self.get_relationship_summary())
            lines.append("")

        return "\n".join(lines)

    async def extract_knowledge_graph_from_content(
        self,
        content: str,
        chapter_num: int,
        llm_provider=None
    ) -> Dict[str, Any]:
        """从前文内容中提取知识图谱信息（架构优化新增）

        使用NovelKnowledgeGraph工具从前文正文中提取实体和关系信息，
        包括人物、地点、事件、人物状态变化等。

        Args:
            content: 前文正文内容
            chapter_num: 章节号
            llm_provider: LLM提供者（用于提取）

        Returns:
            提取的知识图谱信息字典
        """
        try:
            from app.tools.novel_graph_rag import NovelKnowledgeGraph

            # 创建临时知识图谱用于提取
            temp_graph_path = None  # 不持久化
            knowledge_graph = NovelKnowledgeGraph(persist_path=temp_graph_path)

            # 使用LLM提取实体和关系
            if llm_provider:
                extraction_result = await knowledge_graph.extract_from_content(
                    content=content,
                    chapter_num=chapter_num,
                    llm_provider=llm_provider
                )

                # 将提取结果同步到追踪器
                if extraction_result:
                    self._sync_extraction_to_tracker(
                        extraction_result, chapter_num)

                return extraction_result
            else:
                # 无LLM提供者，使用简单的规则提取
                return self._simple_extraction(content, chapter_num)

        except Exception as e:
            self.logger.error(f"从前文内容提取知识图谱失败: {e}")
            return {}

    def _sync_extraction_to_tracker(
        self,
        extraction_result: Dict[str, Any],
        chapter_num: int
    ) -> None:
        """将知识图谱提取结果同步到追踪器"""
        try:
            entities = extraction_result.get("entities", [])

            for entity in entities:
                entity_type = entity.get("type", "")
                character = entity.get("character", "")
                text = entity.get("text", "")
                description = entity.get("description", "")

                # 只处理人物状态相关实体
                if entity_type == "身份变化" and character:
                    self.update_character_state(
                        character,
                        {"identity": text, "status_change": description},
                        chapter_num=chapter_num
                    )
                elif entity_type == "位置变化" and character:
                    self.update_character_state(
                        character,
                        {"location": text},
                        chapter_num=chapter_num
                    )
                elif entity_type == "关系变化" and character:
                    self._parse_relationship_change(
                        character, text, description)

        except Exception as e:
            self.logger.error(f"同步知识图谱提取结果失败: {e}")

    def _simple_extraction(self, content: str, chapter_num: int) -> Dict[str, Any]:
        """简单的规则提取（无LLM时的备选方案）"""
        result = {
            "entities": [],
            "relations": []
        }

        # 使用已有的人物检测方法
        new_chars = self.detect_new_characters(content)

        for char_name in new_chars:
            result["entities"].append({
                "text": char_name,
                "type": "人物",
                "level": "macro",
                "chapter": chapter_num,
                "description": f"第{chapter_num}章新登场人物"
            })

        return result

    def get_knowledge_graph_context_for_writing(
        self,
        chapter_num: int = None,
        max_entities: int = 30
    ) -> str:
        """获取前文知识图谱参考信息用于写作（架构优化新增）

        将追踪器中积累的人物状态、关系变化、位置变化等信息
        格式化为知识图谱参考文本，供写作Agent参考。

        Args:
            chapter_num: 当前章节号
            max_entities: 最大实体数量

        Returns:
            格式化的知识图谱参考文本
        """
        lines = ["# 前文知识图谱参考（架构优化版）", ""]
        lines.append("以下是从前文中提取的核心信息，请在创作时保持一致性：")
        lines.append("")

        # 1. 人物状态汇总
        lines.append("## 人物状态汇总")
        lines.append("")

        entity_count = 0
        for char_name, state in self._character_states.items():
            if entity_count >= max_entities:
                break

            # 只显示最近5章内出场的人物
            if state.last_appearance:
                if chapter_num and (chapter_num - state.last_appearance) > 5:
                    continue

            lines.append(f"### {char_name}")

            if state.identity:
                lines.append(f"- 当前身份: {state.identity}")
                entity_count += 1
            if state.location:
                lines.append(f"- 当前位置: {state.location}")
                entity_count += 1
            if state.status_change:
                lines.append(f"- 最近变化: {state.status_change}")
                entity_count += 1

            lines.append("")

        # 2. 人物关系网络
        if self._relationship_history:
            lines.append("## 人物关系网络")
            lines.append("")

            for rel_change in self._relationship_history[-10:]:  # 最近10条关系变化
                lines.append(
                    f"- {rel_change.character1} ↔ {rel_change.character2}: "
                    f"{rel_change.new_state or rel_change.relationship_type}"
                )
                entity_count += 1
                if entity_count >= max_entities:
                    break
            lines.append("")

        # 3. 已知地点
        if self._known_locations:
            lines.append("## 已知地点")
            lines.append(", ".join(list(self._known_locations)[:20]))
            lines.append("")

        # 4. 章节快照历史
        if self._chapter_snapshots:
            recent_snapshots = sorted(
                self._chapter_snapshots.items(),
                key=lambda x: x[0],
                reverse=True
            )[:3]  # 最近3章

            if recent_snapshots:
                lines.append("## 近期章节人物状态")
                lines.append("")

                for snap_chapter, snapshot in recent_snapshots:
                    if chapter_num and snap_chapter >= chapter_num:
                        continue
                    chars = list(snapshot.characters.keys())[:5]  # 最多显示5个人物
                    if chars:
                        lines.append(
                            f"- 第{snap_chapter}章出场: {', '.join(chars)}")

        return "\n".join(lines)

    # ==================== 人物设定自动生成方法 ====================

    async def generate_character_profiles_from_outline(
        self,
        outline: Dict[str, Any],
        llm_provider=None
    ) -> List[Dict[str, Any]]:
        """从全局大纲中提取并生成人物设定

        根据全局大纲中的人物简述，自动生成完整的人物设定。
        适用于初始化时的人物设定补充。

        Args:
            outline: 全局大纲字典
            llm_provider: LLM提供者（用于生成人物设定）

        Returns:
            生成的人物设定列表
        """
        generated_profiles = []

        try:
            # 1. 从大纲中提取人物简述
            character_mentions = self._extract_character_mentions_from_outline(
                outline)

            for char_name, char_info in character_mentions.items():
                # 检查是否已有完整设定
                if char_name in self._character_states:
                    existing = self._character_states[char_name]
                    # 如果已有较完整的设定，跳过
                    if existing.attributes.get("personality") and existing.attributes.get("background"):
                        continue

                # 2. 使用LLM生成完整设定
                if llm_provider:
                    profile = await self._generate_profile_with_llm(
                        char_name=char_name,
                        char_info=char_info,
                        llm_provider=llm_provider,
                        outline_context=outline
                    )
                else:
                    # 无LLM时使用简单模板
                    profile = self._generate_simple_profile(
                        char_name, char_info)

                if profile:
                    generated_profiles.append(profile)

                    # 同步到追踪器
                    self.update_character_state(
                        char_name,
                        {
                            "identity": profile.get("role", ""),
                            "location": profile.get("initial_location", ""),
                            "attributes": {
                                "personality": profile.get("personality", ""),
                                "background": profile.get("background", ""),
                                "age": profile.get("age", ""),
                                "gender": profile.get("gender", "")
                            }
                        }
                    )

            self.logger.info(f"从大纲生成人物设定完成: {len(generated_profiles)}个人物")

        except Exception as e:
            self.logger.error(f"从大纲生成人物设定失败: {e}")

        return generated_profiles

    def _extract_character_mentions_from_outline(self, outline: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """从大纲中提取人物提及信息

        Args:
            outline: 全局大纲字典

        Returns:
            人物名称 -> 人物信息的映射
        """
        character_mentions = {}

        # 检查多种可能的大纲结构
        # 结构1: outline.characters
        if outline.get("characters"):
            for char in outline.get("characters", []):
                if isinstance(char, dict):
                    name = char.get("name", "")
                    if name:
                        character_mentions[name] = char
                elif isinstance(char, str):
                    character_mentions[char] = {"name": char}

        # 结构2: outline.人物设定
        if outline.get("人物设定"):
            for char in outline.get("人物设定", []):
                if isinstance(char, dict):
                    name = char.get("name", char.get("姓名", ""))
                    if name:
                        character_mentions[name] = char

        # 结构3: outline.main_characters
        if outline.get("main_characters"):
            for char in outline.get("main_characters", []):
                if isinstance(char, dict):
                    name = char.get("name", "")
                    if name:
                        character_mentions[name] = char

        # 结构4: 从章节大纲中提取
        chapters = outline.get("chapters", outline.get("章节大纲", []))
        if isinstance(chapters, list):
            for chapter in chapters:
                if isinstance(chapter, dict):
                    # 检查章节中的人物字段
                    chars = chapter.get("characters", chapter.get("出场人物", []))
                    if isinstance(chars, list):
                        for char in chars:
                            if isinstance(char, str) and char not in character_mentions:
                                character_mentions[char] = {
                                    "name": char, "source": "章节提及"}
                            elif isinstance(char, dict):
                                name = char.get("name", "")
                                if name and name not in character_mentions:
                                    character_mentions[name] = char

        return character_mentions

    async def _generate_profile_with_llm(
        self,
        char_name: str,
        char_info: Dict[str, Any],
        llm_provider,
        outline_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """使用LLM生成人物设定

        Args:
            char_name: 人物名称
            char_info: 已有的人物信息
            llm_provider: LLM提供者
            outline_context: 全局大纲上下文

        Returns:
            生成的人物设定字典
        """
        try:
            # 构建提示词
            prompt = f"""请根据以下信息生成一个完整的人物设定。

人物名称：{char_name}
已有信息：{json.dumps(char_info, ensure_ascii=False, indent=2)}

全局大纲背景：
{json.dumps(outline_context.get("synopsis", outline_context.get("简介", "未知")), ensure_ascii=False)}

请生成以下人物设定信息（JSON格式）：
{{
  "name": "人物名称",
  "role": "角色定位（主角/重要配角/次要配角）",
  "identity": "身份/职业",
  "personality": "性格特点（3-5个关键词）",
  "background": "背景故事（50-100字）",
  "age": "年龄范围",
  "gender": "性别",
  "initial_location": "初始位置",
  "goals": "目标/动机",
  "relationships": {{"其他人物": "关系描述"}}
}}

只输出JSON，不要其他说明文字。"""

            # 调用LLM
            if hasattr(llm_provider, 'generate'):
                response = await llm_provider.generate(prompt)
            elif hasattr(llm_provider, 'call'):
                response = await llm_provider.call(prompt)
            else:
                # 尝试作为可调用对象
                response = await llm_provider(prompt)

            # 解析响应
            if isinstance(response, dict):
                content = response.get("content", response.get("text", ""))
            else:
                content = str(response)

            # 提取JSON
            profile = self._parse_json_from_response(content)

            if profile:
                profile["name"] = char_name  # 确保名称正确
                return profile

        except Exception as e:
            self.logger.error(f"LLM生成人物设定失败: {char_name}, 错误: {e}")

        return None

    def _generate_simple_profile(self, char_name: str, char_info: Dict[str, Any]) -> Dict[str, Any]:
        """生成简单的人物设定（无LLM时的备选方案）

        Args:
            char_name: 人物名称
            char_info: 已有的人物信息

        Returns:
            简单的人物设定字典
        """
        return {
            "name": char_name,
            "role": char_info.get("role", char_info.get("身份", "角色")),
            "identity": char_info.get("identity", char_info.get("身份", "")),
            "personality": char_info.get("personality", char_info.get("性格", "待补充")),
            "background": char_info.get("background", char_info.get("背景", "待补充")),
            "age": char_info.get("age", char_info.get("年龄", "未知")),
            "gender": char_info.get("gender", char_info.get("性别", "未知")),
            "initial_location": char_info.get("location", char_info.get("初始位置", "")),
            "relationships": char_info.get("relationships", {})
        }

    async def generate_profile_for_new_character(
        self,
        char_name: str,
        content: str,
        chapter_num: int,
        llm_provider=None
    ) -> Optional[Dict[str, Any]]:
        """为新发现的人物生成设定

        当检测到新人物时，根据上下文自动生成人物设定。

        Args:
            char_name: 人物名称
            content: 章节内容（用于提取上下文）
            chapter_num: 章节号
            llm_provider: LLM提供者

        Returns:
            生成的人物设定
        """
        try:
            # 提取人物在内容中的上下文
            char_context = self._extract_character_context(char_name, content)

            if llm_provider:
                # 使用LLM生成设定
                profile = await self._generate_new_character_profile_with_llm(
                    char_name=char_name,
                    char_context=char_context,
                    chapter_num=chapter_num,
                    llm_provider=llm_provider
                )
            else:
                # 使用简单模板
                profile = {
                    "name": char_name,
                    "role": "配角",
                    "first_appearance": chapter_num,
                    "source": "自动检测"
                }

            if profile:
                # 添加到追踪器
                self.update_character_state(
                    char_name,
                    {
                        "identity": profile.get("identity", ""),
                        "location": profile.get("location", profile.get("initial_location", "")),
                        "attributes": {
                            "personality": profile.get("personality", ""),
                            "background": profile.get("background", ""),
                            "role": profile.get("role", "配角")
                        }
                    },
                    chapter_num=chapter_num
                )

                self.logger.info(f"为新人物生成设定: {char_name}")

            return profile

        except Exception as e:
            self.logger.error(f"生成新人物设定失败: {char_name}, 错误: {e}")
            return None

    def _extract_character_context(self, char_name: str, content: str) -> str:
        """提取人物在内容中的上下文

        Args:
            char_name: 人物名称
            content: 完整内容

        Returns:
            包含该人物的上下文片段
        """
        # 查找人物名称出现的位置
        contexts = []

        # 使用正则查找人物名称及其周围的上下文
        pattern = rf'.{{0,100}}{re.escape(char_name)}.{{0,100}}'
        matches = re.findall(pattern, content)

        # 最多取前3个匹配
        for match in matches[:3]:
            contexts.append(match)

        return "...".join(contexts)

    async def _generate_new_character_profile_with_llm(
        self,
        char_name: str,
        char_context: str,
        chapter_num: int,
        llm_provider
    ) -> Optional[Dict[str, Any]]:
        """使用LLM为新人物生成设定"""
        try:
            prompt = f"""请根据以下文本片段中的人物上下文，生成一个简要的人物设定。

人物名称：{char_name}
首次出场章节：第{chapter_num}章
人物上下文：
{char_context}

请生成以下人物设定信息（JSON格式）：
{{
  "name": "人物名称",
  "role": "角色定位（主角/重要配角/次要配角/路人）",
  "identity": "身份/职业（根据上下文推断）",
  "personality": "性格特点（根据上下文推断）",
  "background": "可能的背景（根据上下文推断，如不确定可填'待补充'）",
  "location": "当前位置（根据上下文推断）"
}}

只输出JSON，不要其他说明文字。"""

            # 调用LLM
            if hasattr(llm_provider, 'generate'):
                response = await llm_provider.generate(prompt)
            elif hasattr(llm_provider, 'call'):
                response = await llm_provider.call(prompt)
            else:
                response = await llm_provider(prompt)

            # 解析响应
            if isinstance(response, dict):
                content = response.get("content", response.get("text", ""))
            else:
                content = str(response)

            return self._parse_json_from_response(content)

        except Exception as e:
            self.logger.error(f"LLM生成新人物设定失败: {e}")
            return None

    def _parse_json_from_response(self, content: str) -> Optional[Dict[str, Any]]:
        """从LLM响应中解析JSON

        Args:
            content: LLM响应内容

        Returns:
            解析出的JSON字典
        """
        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON代码块
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取花括号内容
        brace_pattern = r'\{[\s\S]*\}'
        match = re.search(brace_pattern, content)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    async def verify_new_characters_with_llm(
        self,
        character_names: List[str],
        content: str,
        llm_provider
    ) -> List[str]:
        """使用LLM验证检测到的新人物

        对规则检测到的新人物进行语义验证，排除误检。

        Args:
            character_names: 检测到的人物名称列表
            content: 章节内容
            llm_provider: LLM提供者

        Returns:
            验证后确认的人物名称列表
        """
        if not character_names:
            return []

        try:
            # 提取每个人物的上下文
            char_contexts = []
            for name in character_names:
                context = self._extract_character_context(name, content)
                char_contexts.append(f"{name}: {context[:200]}...")

            prompt = f"""请判断以下名称是否是真实的人物角色名称。

名称列表及其上下文：
{chr(10).join(char_contexts)}

请返回一个JSON数组，包含所有确实是人物角色的名称。
例如：["张三", "李四"]

只输出JSON数组，不要其他说明文字。"""

            # 调用LLM
            if hasattr(llm_provider, 'generate'):
                response = await llm_provider.generate(prompt)
            elif hasattr(llm_provider, 'call'):
                response = await llm_provider.call(prompt)
            else:
                response = await llm_provider(prompt)

            # 解析响应
            if isinstance(response, dict):
                content = response.get("content", response.get("text", ""))
            else:
                content = str(response)

            # 解析JSON数组
            result = self._parse_json_from_response(
                f"{{\"result\": {content}}}")
            if result and isinstance(result.get("result"), list):
                return result["result"]

            # 尝试直接解析为数组
            try:
                verified = json.loads(content)
                if isinstance(verified, list):
                    return verified
            except:
                pass

        except Exception as e:
            self.logger.error(f"LLM验证新人物失败: {e}")

        # 验证失败时，返回原始列表
        return character_names
