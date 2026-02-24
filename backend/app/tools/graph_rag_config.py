"""
GraphRAG 双轨知识库配置模块
定义通用知识库和垂直领域知识库的实体类型、关系类型和提示词工程
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
    "novel": {
        "category": "novel",
        "description": "小说大纲专业知识库",
        "entity_types": {
            "世界观": {
                "description": "故事背景设定",
                "connection_focus": ["系统论", "一致性理论", "建构主义"]
            },
            "人物关系": {
                "description": "角色关联网络",
                "connection_focus": ["社会网络", "依恋理论", "情感纽带"]
            },
            "情节主线": {
                "description": "核心故事线",
                "connection_focus": ["英雄之旅", "目标理论", "动机理论"]
            },
            "支线任务": {
                "description": "辅助情节",
                "connection_focus": ["蔡格尼克效应", "好奇心", "伏笔理论"]
            },
            "写作手法": {
                "description": "叙事技巧",
                "connection_focus": ["认知负荷", "沉浸理论", "视角理论"]
            },
            "风格标签": {
                "description": "作品风格",
                "connection_focus": ["情感基调", "审美理论", "类型特征"]
            }
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
| 垂直实体特征 | 可能匹配的理论标签 |
|-------------|------------------|
| 规则、逻辑 | 系统论、一致性理论 |
| 关系、情感 | 社会网络、依恋理论 |
| 动机、目标 | 马斯洛需求、自我决定 |
| 悬念、谜题 | 蔡格尼克效应、好奇心理论 |
| 道德、选择 | 伦理学、认知失调 |
| 视角、叙述 | 认知局限、视角理论 |
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
# 辅助函数
# ============================================================================


def get_kb_config(category: str) -> Dict[str, Any]:
    """获取知识库配置"""
    if category == "general":
        return GENERAL_KB_CONFIG
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
    else:
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
