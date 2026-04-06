"""
GraphRAG 双轨知识库配置模块
定义通用知识库和垂直领域知识库的实体类型、关系类型和提示词工程

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Dict, List, Any

# ============================================================================
# 通用知识库配置（创意理论层）
# ============================================================================

GENERAL_KB_CONFIG = {
    "category": "general",
    "description": "通用创意理论知识库",
    "fixed_call": True,  # 每次创意生成固定调用
    "entity_types": {
        "创意理论": {
            "description": "经典创意方法论和思维工具",
            "theory_tags": ["创意方法", "思维工具", "创新理论"],
            "examples": ["头脑风暴法", "SCAMPER法", "六顶思考帽"]
        },
        "叙事结构": {
            "description": "故事构建框架和情节模式",
            "theory_tags": ["故事结构", "情节设计", "叙事模式"],
            "examples": ["三幕式结构", "英雄之旅", "起承转合"]
        },
        "情感要素": {
            "description": "情感触发点和心理机制",
            "theory_tags": ["情感设计", "心理触发", "共鸣机制"],
            "examples": ["共鸣点", "冲突点", "高潮点", "转折点"]
        },
        "受众画像": {
            "description": "目标人群特征和心理",
            "theory_tags": ["用户心理", "人群特征", "行为模式"],
            "examples": ["Z世代", "宝妈群体", "职场新人"]
        },
        "平台特性": {
            "description": "各平台内容特点和分发机制",
            "theory_tags": ["平台算法", "内容分发", "社区文化"],
            "examples": ["抖音算法", "小红书种草", "B站文化"]
        },
        "认知理论": {
            "description": "认知科学和心理学原理",
            "theory_tags": ["认知负荷", "注意力", "记忆机制"],
            "examples": ["峰终定律", "蔡格尼克效应", "格式塔原则"]
        }
    },
    "relation_types": {
        "衍生自": {"description": "理论的理论基础", "weight_range": (0.8, 1.0)},
        "互补于": {"description": "理论间的协同关系", "weight_range": (0.7, 0.9)},
        "应用于": {"description": "理论的适用领域", "weight_range": (0.75, 0.95)},
        "限制于": {"description": "理论的边界条件", "weight_range": (0.6, 0.8)}
    }
}

# ============================================================================
# 用户专属知识库配置（用户个性化知识层）
# ============================================================================

USER_SPECIFIC_KB_CONFIG = {
    "category": "user-specific",
    "description": "用户专属知识库 - 补充LLM知识盲区",
    "fixed_call": False,  # 用户选择启用后才调用
    "entity_types": {
        "小众人物": {
            "description": "LLM知识盲区的人物资料",
            "extraction_hints": [
                "网络红人、KOL、小众博主",
                "地方名人、行业专家",
                "虚构人物、原创角色",
                "历史小人物、冷门人物"
            ],
            "attributes": ["身份", "职业", "成就", "特点", "关联事件"]
        },
        "专属概念": {
            "description": "用户定义的专有概念",
            "extraction_hints": [
                "自定义术语、行话",
                "品牌特有名词",
                "项目代号、内部概念",
                "自创理论、方法论"
            ],
            "attributes": ["定义", "特征", "适用范围", "来源"]
        },
        "专业知识": {
            "description": "特定领域的深度知识",
            "extraction_hints": [
                "行业内部知识",
                "专业技能细节",
                "细分领域理论",
                "实践经验总结"
            ],
            "attributes": ["领域", "核心内容", "应用场景", "实践要点"]
        },
        "个人经验": {
            "description": "用户积累的经验知识",
            "extraction_hints": [
                "成功案例分析",
                "失败教训总结",
                "实践心得体会",
                "独特见解观点"
            ],
            "attributes": ["场景", "经验内容", "适用条件", "效果评估"]
        },
        "特定作品": {
            "description": "特定作品的详细资料",
            "extraction_hints": [
                "原创作品背景",
                "系列作品设定",
                "世界观细节",
                "角色详细信息"
            ],
            "attributes": ["作品名", "类型", "核心元素", "设定细节"]
        }
    },
    "relation_types": {
        "关联于": {"description": "实体间的关联关系", "weight_range": (0.6, 0.9)},
        "属于": {"description": "从属关系", "weight_range": (0.7, 0.95)},
        "应用于": {"description": "应用场景关系", "weight_range": (0.65, 0.85)},
        "补充说明": {"description": "知识补充关系", "weight_range": (0.5, 0.8)},
        "背景支撑": {"description": "背景知识支撑", "weight_range": (0.6, 0.85)}
    }
}

# ============================================================================
# 垂直领域知识库配置（应用案例层）
# ============================================================================

VERTICAL_KB_CONFIGS = {
    "short-video": {
        "category": "short-video",
        "description": "短视频脚本专业知识库",
        "entity_types": {
            "爆款脚本": {
                "description": "成功案例分析",
                "connection_focus": ["情感共鸣", "峰终定律", "注意力理论"]
            },
            "开场钩子": {
                "description": "前3秒抓人技巧",
                "connection_focus": ["悬念构建", "认知负荷", "注意力理论"]
            },
            "节奏控制": {
                "description": "视频节奏和信息密度",
                "connection_focus": ["认知负荷", "注意力理论", "情感曲线"]
            },
            "变现模式": {
                "description": "商业化路径",
                "connection_focus": ["社会认同", "行为经济学"]
            },
            "人设标签": {
                "description": "博主定位要素",
                "connection_focus": ["社会认同", "身份象征"]
            },
            "热点话题": {
                "description": "时效性内容",
                "connection_focus": ["社会认同", "从众心理"]
            }
        }
    },
    "script": {
        "category": "script",
        "description": "剧本大纲专业知识库",
        "entity_types": {
            "剧本结构": {
                "description": "剧本组织方式",
                "connection_focus": ["叙事结构", "英雄之旅", "三幕式"]
            },
            "人物原型": {
                "description": "经典角色类型",
                "connection_focus": ["英雄之旅", "心理原型", "人物弧光"]
            },
            "冲突类型": {
                "description": "戏剧冲突分类",
                "connection_focus": ["情感共鸣", "张力理论", "戏剧理论"]
            },
            "场景设计": {
                "description": "场景构建要素",
                "connection_focus": ["格式塔原则", "象征意义", "氛围理论"]
            },
            "对白技巧": {
                "description": "对话写作方法",
                "connection_focus": ["沟通理论", "潜台词", "心理距离"]
            },
            "类型惯例": {
                "description": "类型片特征",
                "connection_focus": ["叙事模式", "观众预期", "类型理论"]
            }
        }
    },
    # =========================================================================
    # 【重要说明】novel 配置项的语义错位问题
    # =========================================================================
    # 这里的 "novel" 实际上是【正文项目专属知识库】(ProjectKnowledgeBase) 的配置，
    # 用于存储具体项目的人物、情节、世界观等数据，而非"小说写作专业知识"。
    #
    # 该知识库：
    # - 不参与双轨检索（is_isolated: True）
    # - 跟随项目生命周期，项目间完全隔离
    # - 存储具体的人物设定、故事情节、世界观规则
    #
    # 如需添加"小说写作专业知识库"（参与双轨检索的垂直领域知识库），
    # 请使用下方的 "novel-writing" 配置项。
    # =========================================================================
    "novel": {
        "category": "novel",
        "description": "【项目专属】正文生成知识库 - 存储具体项目的人物/情节/世界观，不参与双轨检索",
        "is_isolated": True,  # 标记为独立知识库，不与公共知识库关联
        "_usage_note": "这是ProjectKnowledgeBase的配置，用于正文项目专属数据存储，非垂直领域专业知识库",
        "entity_types": {
            # ========== 宏观层（全集大纲）==========
            "主题": {
                "description": "小说的核心思想、主旨或探讨的议题",
                "level": "macro",
                "attributes": ["名称", "描述", "相关人物", "相关事件"],
                "examples": ["命运与选择", "成长与蜕变", "爱与牺牲"]
            },
            "世界观规则": {
                "description": "世界的基本设定，如魔法体系、科技水平、社会结构、物理规则等",
                "level": "macro",
                "attributes": ["名称", "描述", "适用范围", "影响对象"],
                "examples": ["魔法体系", "社会等级制度", "科技限制"]
            },
            "人物": {
                "description": "角色的基础设定（全集大纲中的人物谱系）",
                "level": "macro",
                "attributes": ["姓名", "别名", "年龄", "性别", "性格", "背景故事", "初始目标", "外貌描述"],
                "examples": ["主角", "反派", "配角"]
            },
            "故事结构": {
                "description": "故事的宏观框架，如三幕、起承转合、英雄之旅等",
                "level": "macro",
                "attributes": ["结构名称", "阶段描述", "包含的宏观事件"],
                "examples": ["三幕式", "英雄之旅", "起承转合"]
            },
            "章节概要": {
                "description": "各章节的宏观概述，含主要冲突、情节走向",
                "level": "macro",
                "attributes": ["章节号", "标题", "概要", "宏观冲突", "涉及的主要人物", "涉及地点"],
                "examples": ["第1章概要", "第2章概要"]
            },
            "地点": {
                "description": "故事发生的地点/场景设定",
                "level": "macro",
                "attributes": ["名称", "描述", "特点", "重要性"],
                "examples": ["主城", "秘密基地", "故乡"]
            },
            # ========== 微观层（章节详细大纲）==========
            "详细事件": {
                "description": "章节内的具体事件，可细分为多个场景",
                "level": "micro",
                "attributes": ["名称", "详细描述", "发生地点", "参与角色", "前因后果", "故事内时间", "重要性(1-5)"],
                "examples": ["主角收到信件", "关键战斗", "重要对话"]
            },
            "核心冲突": {
                "description": "推动情节的冲突，可以是人物之间、人物与环境、人物内心等",
                "level": "micro",
                "attributes": ["冲突描述", "冲突类型(外部/内部)", "冲突双方", "涉及事件", "强度(1-5)"],
                "examples": ["主角vs反派", "内心挣扎", "人与自然"]
            },
            "角色发展弧": {
                "description": "角色在特定章节中的变化或成长节点",
                "level": "micro",
                "attributes": ["所属角色", "发展阶段描述", "触发事件", "结果状态", "变化前状态", "变化后状态"],
                "examples": ["接受命运", "觉醒力量", "做出选择"]
            },
            "关键对话": {
                "description": "对情节或人物塑造有重要作用的对话",
                "level": "micro",
                "attributes": ["对话内容", "参与者", "对话目的", "所在事件"],
                "examples": ["关键告白", "真相揭露", "誓言承诺"]
            },
            "情节线": {
                "description": "贯穿多章的子情节，可宏观可微观",
                "level": "micro",
                "attributes": ["名称", "描述", "类型(主线/支线)", "包含事件"],
                "examples": ["主线", "感情线", "复仇线"]
            },
            "场景": {
                "description": "更细粒度的单元，场景描述",
                "level": "micro",
                "attributes": ["场景描述", "环境", "动作", "对话", "氛围"],
                "examples": ["开场场景", "高潮场景", "结尾场景"]
            }
        },
        "relation_types": {
            # ========== 宏观层内部关系 ==========
            "体现于": {"description": "主题体现于章节概要", "level": "macro_to_macro"},
            "属于": {"description": "人物属于世界观规则（如种族、阵营）", "level": "macro_to_macro"},
            "包含": {"description": "故事结构包含章节概要", "level": "macro_to_macro"},
            "影响": {"description": "世界观规则影响人物/地点", "level": "macro_to_macro"},
            # ========== 宏观与微观之间的桥梁关系 ==========
            "经历": {"description": "人物经历角色发展弧步骤", "level": "bridge"},
            "参与": {"description": "人物参与详细事件", "level": "bridge"},
            "展开为": {"description": "章节概要展开为详细事件", "level": "bridge"},
            "约束": {"description": "世界观规则约束详细事件", "level": "bridge"},
            "渗透于": {"description": "主题渗透于详细事件/核心冲突", "level": "bridge"},
            "定位": {"description": "故事结构定位详细事件", "level": "bridge"},
            "发生于": {"description": "事件发生于地点", "level": "bridge"},
            # ========== 微观层内部关系 ==========
            "前序": {"description": "详细事件的前序事件", "level": "micro_to_micro"},
            "导致": {"description": "详细事件导致另一个事件", "level": "micro_to_micro"},
            "包含冲突": {"description": "详细事件包含核心冲突", "level": "micro_to_micro"},
            "触发于": {"description": "角色发展弧步骤触发于详细事件", "level": "micro_to_micro"},
            "发生于事件": {"description": "关键对话发生于详细事件", "level": "micro_to_micro"},
            "包含事件": {"description": "情节线包含详细事件", "level": "micro_to_micro"},
            "关联": {"description": "核心冲突关联角色发展弧步骤", "level": "micro_to_micro"},
            "关联人物": {"description": "事件/场景关联的人物", "level": "micro_to_micro"}
        }
    },
    # =========================================================================
    # 【小说写作专业知识库】- 真正的垂直领域知识库
    # =========================================================================
    # 这是"小说类型"的垂直领域专业知识库，用于存储：
    # - 小说写作技巧、方法论、创作指南
    # - 经典小说案例分析、类型惯例总结
    # - 与通用创意理论的连接关系
    #
    # 该知识库参与双轨检索，为创意生成提供理论指导 + 案例参考
    # =========================================================================
    "novel-writing": {
        "category": "novel-writing",
        "description": "小说写作专业知识库 - 写作技巧、方法论、案例分析，参与双轨检索",
        "entity_types": {
            "开场技巧": {
                "description": "小说开篇设计方法，吸引读者的开篇策略",
                "connection_focus": ["悬念理论", "注意力理论", "认知负荷", "峰终定律"]
            },
            "人物塑造": {
                "description": "角色刻画技巧，包括性格、外貌、行为模式设计",
                "connection_focus": ["英雄之旅", "心理原型", "人物弧光", "认知心理学"]
            },
            "冲突设计": {
                "description": "戏剧冲突构建方法，推动情节发展的矛盾设计",
                "connection_focus": ["戏剧理论", "张力理论", "情感共鸣", "叙事结构"]
            },
            "叙事视角": {
                "description": "叙事视角选择技巧，第一人称/第三人称/多视角等",
                "connection_focus": ["视角理论", "沉浸感", "认知距离", "可靠性叙事"]
            },
            "节奏控制": {
                "description": "情节节奏把控技巧，信息密度与情绪曲线设计",
                "connection_focus": ["认知负荷", "注意力理论", "情感曲线", "峰终定律"]
            },
            "伏笔技巧": {
                "description": "伏笔埋设与回收方法，悬念的铺垫与揭示",
                "connection_focus": ["悬念理论", "记忆巩固", "预期管理", "蔡格尼克效应"]
            },
            "对话技巧": {
                "description": "对话写作方法，包括潜台词、对话节奏、角色声音",
                "connection_focus": ["潜台词理论", "情感共鸣", "角色一致性", "信息差理论"]
            },
            "场景描写": {
                "description": "场景构建技巧，环境渲染与氛围营造",
                "connection_focus": ["格式塔原则", "感官心理学", "沉浸理论", "象征意义"]
            },
            "世界观构建": {
                "description": "虚构世界设计方法，规则体系与设定一致性",
                "connection_focus": ["世界构建理论", "一致性原则", "认知模型", "想象力学"]
            },
            "类型惯例": {
                "description": "各类型小说的惯例特征与读者预期",
                "connection_focus": ["叙事模式", "类型理论", "读者预期", "社会认同"]
            },
            "经典案例": {
                "description": "知名小说创作技巧分析，成功作品的结构解析",
                "connection_focus": ["叙事结构", "风格理论", "文学技巧", "情感设计"]
            },
            "风格流派": {
                "description": "小说写作风格与流派特征",
                "connection_focus": ["风格理论", "文学传统", "审美心理学", "文化认同"]
            }
        },
        "relation_types": {
            "体现了": {"description": "案例体现了通用理论", "weight_range": (0.8, 1.0)},
            "应用了": {"description": "技巧应用了理论方法", "weight_range": (0.7, 0.95)},
            "符合": {"description": "案例符合理论模型", "weight_range": (0.75, 0.95)},
            "违背了": {"description": "创新突破打破常规", "weight_range": (0.6, 0.85)},
            "衍生自": {"description": "技巧衍生自基础理论", "weight_range": (0.75, 0.9)},
            "互补于": {"description": "技巧间的协同关系", "weight_range": (0.7, 0.85)},
            "应用于": {"description": "技巧适用于特定场景", "weight_range": (0.65, 0.9)}
        }
    },
    "print-ad": {
        "category": "print-ad",
        "description": "平面广告专业知识库",
        "entity_types": {
            "品牌调性": {
                "description": "品牌个性特征",
                "connection_focus": ["社会认同", "身份象征", "品牌人格"]
            },
            "视觉元素": {
                "description": "视觉构成要素",
                "connection_focus": ["格式塔原则", "色彩心理学", "构图理论"]
            },
            "文案策略": {
                "description": "文案写作方法",
                "connection_focus": ["损失厌恶", "框架效应", "说服理论"]
            },
            "传播渠道": {
                "description": "投放媒介特性",
                "connection_focus": ["媒介效应", "场景理论", "注意力理论"]
            },
            "受众触点": {
                "description": "用户接触点",
                "connection_focus": ["用户体验", "旅程地图", "触点理论"]
            },
            "竞品案例": {
                "description": "竞争对手分析",
                "connection_focus": ["差异化理论", "定位理论", "竞争策略"]
            }
        }
    },
    "tvc": {
        "category": "tvc",
        "description": "TVC广告专业知识库",
        "entity_types": {
            "创意概念": {
                "description": "核心创意点",
                "connection_focus": ["差异化理论", "定位理论", "Big Idea"]
            },
            "分镜设计": {
                "description": "镜头语言",
                "connection_focus": ["注意力理论", "认知负荷", "视觉语法"]
            },
            "声音设计": {
                "description": "音频元素",
                "connection_focus": ["情感共鸣", "联觉效应", "音频心理学"]
            },
            "演员表演": {
                "description": "表演风格",
                "connection_focus": ["可信度理论", "共情机制", "真实感"]
            },
            "制作规格": {
                "description": "技术要求",
                "connection_focus": ["技术标准", "质量感知", "专业度"]
            },
            "投放策略": {
                "description": "媒体规划",
                "connection_focus": ["重复曝光", "熟悉性效应", "频次理论"]
            }
        }
    }
}

# ============================================================================
# 垂直-通用连接关系类型
# ============================================================================

CONNECTION_RELATIONS = {
    "体现了": {
        "description": "垂直案例体现了通用理论",
        "weight_range": (0.8, 1.0),
        "direction": "vertical_to_general",
        "examples": [
            ("三秒反转", "悬念理论"),
            ("结尾高潮", "峰终定律"),
            ("人物弧光", "英雄之旅")
        ]
    },
    "应用了": {
        "description": "垂直案例应用了理论方法",
        "weight_range": (0.7, 0.95),
        "direction": "vertical_to_general",
        "examples": [
            ("极简构图", "格式塔原则"),
            ("快节奏剪辑", "注意力理论"),
            ("痛点文案", "损失厌恶")
        ]
    },
    "符合": {
        "description": "垂直案例符合理论模型",
        "weight_range": (0.75, 0.95),
        "direction": "vertical_to_general",
        "examples": [
            ("三幕式剧本", "英雄之旅"),
            ("品牌人格", "社会认同"),
            ("色彩对比", "色彩心理学")
        ]
    },
    "违背了": {
        "description": "垂直案例打破理论常规（创新突破）",
        "weight_range": (0.6, 0.85),
        "direction": "vertical_to_general",
        "examples": [
            ("反套路结局", "传统三幕式"),
            ("非线性叙事", "经典结构"),
            ("反广告风格", "商业惯例")
        ]
    }
}

# ============================================================================
# LLM 提示词工程
# ============================================================================

EXTRACTION_PROMPTS = {
    "general": """你是一位创意理论专家。请从通用创意理论资料中提取核心实体，并为每个理论赋予**明确的理论标签**。

## 任务目标
构建创意理论的知识图谱，为后续与垂直领域案例建立连接做准备。

## 核心实体类型
{entity_types}

## 理论标签命名规范
使用简洁、标准化的标签，便于匹配：
- 悬念构建、情节设计、节奏控制
- 视觉设计、构图原理、色彩理论
- 用户体验、情感设计、认知负荷
- 人物塑造、叙事结构、冲突设计
- 受众心理、传播策略、社会认同

## 输出格式
{{
  "entities": [
    {{
      "text": "理论名称",
      "type": "实体类型",
      "theory_tags": ["标签1", "标签2"],
      "definition": "理论定义",
      "application_scope": ["适用场景1", "适用场景2"],
      "key_principles": ["核心原则1", "核心原则2"]
    }}
  ],
  "relations": [
    {{"source": "源实体", "target": "目标实体", "relation": "关系类型", "weight": 0.9}}
  ]
}}

待分析内容：
{content}
""",
    "vertical": """你是一位{domain}分析专家。请从{domain}资料中提取专业实体，并**主动建立与通用创意理论的连接**。

## 核心实体类型
{entity_types}

## 主动连接机制

对于每个提取的垂直实体，必须分析其与通用理论的关系：

**[体现了]** - 该实体体现了什么理论？
- 示例：三秒反转 → 体现了 → 悬念理论

**[应用了]** - 该实体应用了什么方法？
- 示例：极简构图 → 应用了 → 格式塔原则

**[符合]** - 该实体符合什么模型？
- 示例：人物弧光 → 符合 → 英雄之旅模型

**[违背了]** - 该实体是否打破常规？违背了哪个理论？
- 示例：反套路结局 → 违背了 → 传统三幕式

## 理论匹配参考
{theory_reference}

## 输出格式
{{
  "entities": [
    {{
      "text": "实体名称",
      "type": "实体类型",
      "description": "详细描述",
      "theory_connections": [
        {{
          "relation": "体现了/应用了/符合/违背了",
          "target_theory": "理论名称",
          "confidence": 0.92,
          "explanation": "匹配解释"
        }}
      ]
    }}
  ],
  "relations": [
    {{"source": "垂直实体", "target": "通用理论", "relation": "体现了", "weight": 0.92}}
  ]
}}

待分析内容：
{content}
"""
}

# 垂直领域特定的理论匹配参考
VERTICAL_THEORY_REFERENCES = {
    "short-video": """
| 垂直实体特征 | 可能匹配的理论标签 |
|-------------|------------------|
| 悬念、反转、好奇 | 悬念理论、蔡格尼克效应 |
| 结尾设计、高潮 | 峰终定律、情感曲线 |
| 视觉构图、色彩 | 格式塔原则、色彩心理学 |
| 人物成长、转变 | 英雄之旅、人物弧光 |
| 信息密度、节奏 | 认知负荷、注意力理论 |
| 互动、传播 | 社会认同、参与感理论 |
""",
    "script": """
| 垂直实体特征 | 可能匹配的理论标签 |
|-------------|------------------|
| 人物弧光、成长 | 英雄之旅、成长模型 |
| 反派、阴影面 | 荣格原型、心理阴影 |
| 关系、情感线 | 依恋理论、情感共鸣 |
| 三幕式、结构 | 经典叙事结构 |
| 非线性、多视角 | 认知负荷、记忆重构 |
| 悬念、反转 | 悬念理论、预期违背 |
""",
    "novel": """
| 【项目专属知识库 - 不参与双轨检索】 |
该配置对应 ProjectKnowledgeBase，用于存储具体小说项目的人物、情节、世界观数据。
此知识库完全独立，无需匹配通用理论标签。

如需添加小说写作专业知识（参与双轨检索），请使用 "novel-writing" 类别。
""",
    "novel-writing": """
| 垂直实体特征 | 可能匹配的理论标签 |
|-------------|------------------|
| 开场、钩子、悬念 | 悬念理论、注意力理论、蔡格尼克效应 |
| 人物、性格、成长 | 英雄之旅、心理原型、人物弧光 |
| 冲突、矛盾、张力 | 戏剧理论、张力理论、情感共鸣 |
| 视角、人称、叙事 | 视角理论、沉浸感、认知距离 |
| 节奏、密度、情绪 | 认知负荷、注意力理论、情感曲线 |
| 伏笔、铺垫、回收 | 悬念理论、记忆巩固、预期管理 |
| 对话、潜台词、声音 | 潜台词理论、情感共鸣、信息差理论 |
| 场景、环境、氛围 | 格式塔原则、感官心理学、沉浸理论 |
| 世界观、设定、规则 | 世界构建理论、一致性原则、认知模型 |
| 类型、惯例、预期 | 叙事模式、类型理论、读者预期 |
| 风格、流派、传统 | 风格理论、文学传统、审美心理学 |
""",
    "print-ad": """
| 垂直实体特征 | 可能匹配的理论标签 |
|-------------|------------------|
| 极简、留白 | 格式塔原则、少即是多 |
| 色彩、对比 | 色彩心理学、对比理论 |
| 痛点、恐惧 | 损失厌恶、风险规避 |
| 利益、收益 | 前景理论、价值感知 |
| 社会证明 | 社会认同、从众心理 |
| 稀缺、限时 | 稀缺原理、FOMO |
""",
    "tvc": """
| 垂直实体特征 | 可能匹配的理论标签 |
|-------------|------------------|
| 快节奏、信息 | 注意力理论、认知负荷 |
| 音乐、情绪 | 情感共鸣、联觉效应 |
| 镜头、视角 | 视角理论、沉浸感 |
| 差异化、独特 | 差异化理论、定位理论 |
| 情感、故事 | 叙事传输、情感共鸣 |
| 重复、频次 | 熟悉性效应、记忆巩固 |
"""
}

# ============================================================================
# 用户专属知识库提取提示词
# ============================================================================

USER_SPECIFIC_EXTRACTION_PROMPT = """你是一位知识图谱专家，专注于提取用户个性化知识。请从用户上传的内容中提取实体，弥补LLM的知识盲区。

## 核心实体类型
{entity_types}

## 提取重点

### 1. 人物类实体
提取LLM可能不知道的人物信息：
- 网络红人、KOL、小众博主
- 地方名人、行业专家
- 虚构人物、原创角色
- 历史小人物、冷门人物

**必须提取的属性**：
- 身份/职业
- 主要成就/特点
- 关联事件/作品
- 独特之处（为什么LLM可能不知道）

### 2. 概念类实体
提取专有名词和概念：
- 自定义术语、行话、黑话
- 品牌特有名词
- 项目代号、内部概念
- 自创理论、方法论

**必须提取的属性**：
- 明确定义
- 使用场景
- 来源/创造者
- 与通用概念的区别

### 3. 知识类实体
提取领域专业知识：
- 行业内部知识
- 专业技能细节
- 细分领域理论
- 实践经验总结

**必须提取的属性**：
- 所属领域
- 核心内容要点
- 实际应用场景
- 与通用知识的差异

## 知识盲区标注
对于每个实体，请标注：
- `blind_spot_type`: LLM的知识盲区类型
  - "too_new": 太新，LLM训练数据中不存在
  - "too_niche": 太小众，LLM训练数据覆盖不足
  - "too_specific": 太具体，LLM无法精确记忆
  - "user_created": 用户原创内容

## 输出格式
{{
  "entities": [
    {{
      "text": "实体名称",
      "type": "实体类型",
      "blind_spot_type": "知识盲区类型",
      "description": "详细描述",
      "key_attributes": {{
        "身份": "...",
        "成就": "...",
        "特点": "..."
      }},
      "llm_knowledge_gap": "LLM可能不知道的关键信息"
    }}
  ],
  "relations": [
    {{"source": "实体A", "target": "实体B", "relation": "关系类型", "weight": 0.85}}
  ]
}}

待分析内容：
{content}
"""

# ============================================================================
# 正文板块专用提取提示词（完全独立，不与公共知识库关联）
# ============================================================================

NOVEL_KB_EXTRACTION_PROMPT = """你是小说知识图谱专家。从大纲中提取实体和关系。

**重要：该知识库完全独立，禁止使用以下关系类型：**
体现了、应用了、符合、违背了、衍生自、互补于、应用于、限制于

## 实体类型

**宏观层(macro)：** 主题、世界观规则、人物、故事结构、章节概要、地点
**微观层(micro)：** 详细事件、核心冲突、角色发展弧、关键对话、情节线、场景

## 关系类型

**宏观层：** 体现于、属于、包含、影响
**桥梁：** 经历、参与、展开为、约束、渗透于、定位、发生于
**微观层：** 前序、导致、包含冲突、触发于、发生于事件、包含事件、关联、关联人物

## 输出格式

```json
{{
  "entities": [
    {{"text": "名称", "type": "类型", "level": "macro或micro", "description": "描述"}}
  ],
  "relations": [
    {{"source": "实体A", "target": "实体B", "relation": "关系类型"}}
  ]
}}
```

待分析内容：
{content}
"""

# ============================================================================
# 辅助函数
# ============================================================================


def get_kb_config(category: str) -> Dict[str, Any]:
    """获取知识库配置"""
    if category == "general":
        return GENERAL_KB_CONFIG
    elif category == "user-specific":
        return USER_SPECIFIC_KB_CONFIG
    return VERTICAL_KB_CONFIGS.get(category, {})


def get_entity_types(category: str) -> Dict[str, Any]:
    """获取指定知识库的实体类型"""
    config = get_kb_config(category)
    return config.get("entity_types", {})


def get_connection_relations() -> Dict[str, Any]:
    """获取连接关系类型"""
    return CONNECTION_RELATIONS


def get_extraction_prompt(category: str, content: str) -> str:
    """获取提取提示词"""
    if category == "general":
        entity_types = "\n".join([
            f"- **{k}**: {v['description']}"
            for k, v in GENERAL_KB_CONFIG["entity_types"].items()
        ])
        return EXTRACTION_PROMPTS["general"].format(
            entity_types=entity_types,
            content=content
        )
    elif category == "user-specific":
        # 用户专属知识库提取提示词
        entity_types = "\n".join([
            f"- **{k}**: {v['description']}"
            for k, v in USER_SPECIFIC_KB_CONFIG["entity_types"].items()
        ])
        return USER_SPECIFIC_EXTRACTION_PROMPT.format(
            entity_types=entity_types,
            content=content
        )
    elif category == "novel":
        # 正文板块专用提取提示词 - 完全独立，不与公共知识库关联
        return NOVEL_KB_EXTRACTION_PROMPT.format(content=content)
    else:
        # 其他垂直领域知识库提取提示词
        config = VERTICAL_KB_CONFIGS.get(category, {})
        entity_types = "\n".join([
            f"- **{k}**: {v['description']}"
            for k, v in config.get("entity_types", {}).items()
        ])
        theory_ref = VERTICAL_THEORY_REFERENCES.get(category, "")
        return EXTRACTION_PROMPTS["vertical"].format(
            domain=config.get("description", "垂直领域"),
            entity_types=entity_types,
            theory_reference=theory_ref,
            content=content
        )


def get_theory_tags() -> List[str]:
    """获取所有理论标签（用于匹配）"""
    tags = set()
    # 从通用知识库收集
    for entity_type in GENERAL_KB_CONFIG["entity_types"].values():
        tags.update(entity_type.get("theory_tags", []))
    return sorted(list(tags))


def is_isolated_kb(category: str) -> bool:
    """
    检查知识库是否为独立知识库（不与公共知识库关联）

    Args:
        category: 知识库类别

    Returns:
        True 表示独立知识库，False 表示公共知识库（参与双轨检索）

    注意：
        - "novel" 是项目专属知识库（ProjectKnowledgeBase），完全独立
        - "novel-writing" 是小说写作专业知识库，参与双轨检索
    """
    # 正文板块(novel)是完全独立的知识库 - 项目专属数据存储
    if category == "novel":
        return True

    # 检查配置中的 is_isolated 标记
    config = get_kb_config(category)
    return config.get("is_isolated", False)


def get_novel_entity_types() -> Dict[str, Any]:
    """
    获取正文板块的实体类型配置

    Returns:
        正文板块实体类型配置，分为宏观层和微观层
    """
    novel_config = VERTICAL_KB_CONFIGS.get("novel", {})
    entity_types = novel_config.get("entity_types", {})

    # 分离宏观层和微观层实体类型
    macro_types = {k: v for k, v in entity_types.items()
                   if v.get("level") == "macro"}
    micro_types = {k: v for k, v in entity_types.items()
                   if v.get("level") == "micro"}

    return {
        "macro": macro_types,
        "micro": micro_types,
        "all": entity_types
    }


def get_novel_relation_types() -> Dict[str, Any]:
    """
    获取正文板块的关系类型配置

    Returns:
        正文板块关系类型配置，分为宏观层、桥梁和微观层
    """
    novel_config = VERTICAL_KB_CONFIGS.get("novel", {})
    relation_types = novel_config.get("relation_types", {})

    # 分离不同层级的关系类型
    macro_relations = {k: v for k, v in relation_types.items() if v.get(
        "level") == "macro_to_macro"}
    bridge_relations = {
        k: v for k, v in relation_types.items() if v.get("level") == "bridge"}
    micro_relations = {k: v for k, v in relation_types.items() if v.get(
        "level") == "micro_to_micro"}

    return {
        "macro_to_macro": macro_relations,
        "bridge": bridge_relations,
        "micro_to_micro": micro_relations,
        "all": relation_types
    }
