"""
提示词管理器
管理各模块的提示词模板，支持智能变量填充
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import re

from app.models import PromptTemplate
from app.core.config import get_settings
from app.core.logger import get_logger


# ==================== 模块变量配置 ====================
# 定义每个模块支持的变量、默认值和描述
MODULE_VARIABLES_CONFIG = {
    "short_video": {
        "variables": {
            "topic": {
                "default": "创意短视频",
                "description": "视频主题",
                "required": True,
                "front_field": "title"
            },
            "audience": {
                "default": "年轻用户",
                "description": "目标受众",
                "required": True,
                "front_field": "target_audience"
            },
            "description": {
                "default": "待补充详细描述",
                "description": "对视频内容的进一步说明",
                "required": True,
                "front_field": "description"
            },
            "platform": {
                "default": "抖音",
                "description": "发布平台",
                "required": False
            },
            "style": {
                "default": "轻松有趣",
                "description": "风格调性",
                "required": False,
                "front_field": "style_types_combined"
            },
            "duration": {
                "default": 60,
                "description": "视频时长(秒)",
                "required": False
            },
            "generate_ai_prompt": {
                "default": "否",
                "description": "是否生成AI视频提示",
                "required": False
            },
            "ai_platforms": {
                "default": "无",
                "description": "AI视频生成平台",
                "required": False
            },
            "reference_video": {
                "default": "无",
                "description": "参考视频URL（仅Gemini 1.5 Pro/Flash支持）",
                "required": False
            },
            # 运营相关自定义变量
            "account_tone": {
                "default": "未指定",
                "description": "账号调性（如：专业干货型、搞笑娱乐型、情感治愈型等）",
                "required": False
            },
            "target_fans": {
                "default": "未指定",
                "description": "目标粉丝群体（如：18-25岁女性、职场白领、宝妈群体等）",
                "required": False
            },
            "content_position": {
                "default": "未指定",
                "description": "内容定位（如：知识科普、生活记录、好物推荐等）",
                "required": False
            }
        }
    },

    "script": {
        "variables": {
            "series_type": {
                "default": "网剧",
                "description": "剧集类型",
                "required": True,
                "options": ["院线电影", "网络电影", "长剧", "短剧", "微电影", "纪录片", "动画电影", "网络剧", "竖屏剧"]
            },
            "theme": {
                "default": "都市",
                "description": "题材",
                "required": True,
                "front_field": "genre"
            },
            "audience": {
                "default": "年轻观众",
                "description": "目标受众",
                "required": True,
                "front_field": "target_audience"
            },
            "platform": {
                "default": "爱奇艺",
                "description": "投放平台",
                "required": True,
                "options": ["央视", "地方卫视", "爱奇艺", "腾讯视频", "优酷", "芒果TV", "B站", "抖音", "快手", "西瓜视频", "Netflix", "HBO", "Disney+", "院线发行", "电影节展映"]
            },
            "reference_works": {
                "default": "无",
                "description": "对标作品（可填写作品名称）",
                "required": False
            },
            "synopsis": {
                "default": "待补充故事梗概",
                "description": "故事梗概",
                "required": True,
                "front_field": "description"
            },
            "episode_count": {
                "default": "",
                "description": "集数",
                "required": False
            },
            "custom_outline": {
                "default": "",
                "description": "自写大纲（用户上传的文本文件内容）",
                "required": False
            }
        }
    },

    "novel": {
        "variables": {
            "length": {
                "default": "中篇",
                "description": "篇幅体量",
                "required": True,
                "options": ["长篇", "中篇", "短篇"]
            },
            "genre": {
                "default": "言情",
                "description": "类型标签",
                "required": True,
                "options": ["言情", "悬疑推理", "科幻", "奇幻玄幻", "历史", "现实题材", "轻小说"]
            },
            "target_platform": {
                "default": "起点",
                "description": "目标读者/平台",
                "required": True,
                "options": ["起点", "晋江", "番茄", "实体出版", "纯个人创作"]
            },
            "tone": {
                "default": "正剧",
                "description": "基调氛围",
                "required": True,
                "options": ["正剧", "喜剧", "虐恋催泪", "爽文", "治愈温暖"]
            },
            "theme": {
                "default": "",
                "description": "故事主题——想表达的核心思想",
                "required": False
            },
            "unique_selling_point": {
                "default": "",
                "description": "独特卖点——最吸引人的钩子",
                "required": False
            },
            "synopsis": {
                "default": "待补充故事梗概",
                "description": "故事梗概",
                "required": True,
                "front_field": "description"
            },
            "chapter_count": {
                "default": "",
                "description": "章节数",
                "required": False
            },
            "custom_outline": {
                "default": "",
                "description": "自写大纲（用户上传的文本文件内容）",
                "required": False
            }
        }
    },

    "print_ad": {
        "variables": {
            "brand_product": {
                "default": "",
                "description": "品牌/产品名称（具体品牌+产品，新品牌需说明调性）",
                "required": True,
                "front_field": "brand_product"
            },
            "ad_purpose": {
                "default": "",
                "description": "广告目的",
                "required": True,
                "front_field": "ad_purpose"
            },
            "core_message": {
                "default": "",
                "description": "核心信息（如果受众看完只记住一件事，你希望是什么？必须用一句话说清楚）",
                "required": True,
                "front_field": "core_message"
            },
            "audience_profile": {
                "default": "",
                "description": "受众特征（年龄+性别+学历+职业+收入+地域）",
                "required": True,
                "front_field": "audience_profile"
            },
            "contact_scene": {
                "default": "",
                "description": "接触场景（他们通常在哪里看到这则广告？）",
                "required": True,
                "front_field": "contact_scene"
            },
            "style_tone": {
                "default": "视觉冲击",
                "description": "风格调性",
                "required": True,
                "options": ["视觉冲击", "极简留白", "幽默搞怪", "温情走心", "功能直给", "复古怀旧", "科技感", "高级感", "国潮风", "赛博朋克", "手绘插画", "摄影写实"]
            },
            "copy_content": {
                "default": "",
                "description": "文案内容",
                "required": False,
                "front_field": "copy_content"
            },
            "size_spec": {
                "default": "",
                "description": "具体尺寸",
                "required": False,
                "front_field": "size_spec"
            },
            "publish_media": {
                "default": "",
                "description": "发布媒介",
                "required": False,
                "front_field": "publish_media"
            },
            "ai_platforms": {
                "default": "豆包",
                "description": "AI提示词目标平台",
                "required": False,
                "options": ["豆包", "即梦", "千问", "Gemini", "GPT", "Grok", "可灵", "Midjourney", "Stable Diffusion"]
            }
        }
    },

    "tvc": {
        "variables": {
            "brand_product": {
                "default": "",
                "description": "品牌/产品名称（具体品牌+产品线）",
                "required": True,
                "front_field": "brand_product"
            },
            "ad_purpose": {
                "default": "",
                "description": "广告目的（如：品牌认知、产品推广、节日营销、形象升级、促销活动）",
                "required": True,
                "front_field": "ad_purpose"
            },
            "core_message": {
                "default": "",
                "description": "核心信息（如果观众看完只记住一句话，你希望是什么？）",
                "required": True,
                "front_field": "core_message"
            },
            "audience_profile": {
                "default": "",
                "description": "受众特征（年龄+性别+学历+职业+收入+地域）",
                "required": True,
                "front_field": "audience_profile"
            },
            "broadcast_platform": {
                "default": "视频平台",
                "description": "投放平台",
                "required": True,
                "options": ["电视台-央视", "电视台-卫视", "电视台-地方台", "视频平台-爱奇艺", "视频平台-腾讯视频", "视频平台-优酷", "视频平台-芒果TV", "视频平台-B站", "网络贴片广告", "户外大屏-商圈", "户外大屏-机场", "户外大屏-高铁站", "电梯广告", "影院映前广告", "社交媒体-抖音", "社交媒体-快手", "社交媒体-视频号"]
            },
            "style_tone": {
                "default": "温情走心",
                "description": "风格调性",
                "required": True,
                "options": ["温情走心", "幽默搞怪", "视觉冲击", "极简留白", "功能直给", "史诗大气", "悬疑烧脑", "热血励志", "复古怀旧", "科技感", "高级感", "纪实风格"]
            },
            "duration": {
                "default": 30,
                "description": "时长(秒)",
                "required": True
            },
            "generate_ai_prompt": {
                "default": "否",
                "description": "是否生成AI视频生成提示",
                "required": False
            },
            "ai_platforms": {
                "default": "可灵",
                "description": "AI视频生成平台",
                "required": False,
                "options": ["可灵", "Seedance 2.0", "Sora 2", "Veo 3.1", "Runway", "Pika", "Wan 2.2"]
            },
            "reference_video": {
                "default": "",
                "description": "参考视频URL（仅Gemini 1.5 Pro/Flash支持）",
                "required": False
            }
        }
    }
}


# 默认提示词模板
DEFAULT_PROMPTS = {
    # 短视频脚本
    "short_video": {
        "name": "短视频脚本生成器",
        "description": "根据用户输入生成短视频脚本",
        "content": """# 短视频脚本生成指令

## 角色
你是一位资深的短视频脚本创作专家，深谙网络传播规律、受众心理、平台调性，擅长创作具有网感、高传播度的短视频脚本。

## 任务
根据以下用户提供的信息，创作一份高质量的短视频脚本。脚本需包含分镜、画面描述、台词/旁白、字幕、音效/背景音乐、特效建议等要素。同时，需考虑平台特性、目标受众心理、网感元素（如悬念、反转、热点、情绪共鸣等），并确保内容合规，避免违规内容。

## 用户输入
- **标题/主题**：{topic}
- **目标受众**：{audience}
- **详细描述**：{description}
- **视频时长**：{duration}
- **目标平台**：{platform}
- **风格类型**：{style}
- **是否生成AI视频提示**：{generate_ai_prompt}
- **AI视频生成平台**：{ai_platforms}
- **参考视频**：{reference_video}

## 脚本创作要求
1. **传播要素**：脚本需包含至少一个传播引爆点（如情感共鸣、意外反转、实用价值、热点关联等），开头前3秒需抓住观众注意力。
2. **受众心理**：根据目标受众特征，设计符合其兴趣、痛点、价值观的内容。
3. **平台适配**：考虑目标平台的算法推荐机制、用户习惯、内容偏好（如抖音侧重快节奏、B站欢迎深度内容、小红书强调实用美学等）。
4. **网感表达**：语言风格符合网络流行语习惯，可适当加入热梗（需确保不过时），节奏紧凑，信息密度高。
5. **合规审核**：生成脚本前，请自我检查合规要点，无违法违规内容。

## 输出格式
请以Markdown表格形式呈现脚本，包含分镜序号、画面描述、台词/旁白、字幕、音效/BGM、特效/转场、时长等要素。

如果"是否生成AI视频提示"为"是"，请在脚本之后，额外提供每个分镜的AI视频生成提示词，必须严格使用用户选择的AI视频生成平台名称："{ai_platforms}"，必须用中文输出提示词。

## 注意事项
- 总时长需与用户输入一致，每个分镜时长总和等于总时长。
- 台词需简洁有力，符合人物设定。
- 若用户提供参考视频URL，需在脚本中体现参考视频的风格或关键元素。

现在，请根据以上指令，为用户创作脚本。
""",
        "variables": ["topic", "audience", "description", "platform", "style", "duration", "generate_ai_prompt", "ai_platforms", "reference_video"]
    },

    # 剧本大纲
    "script": {
        "name": "剧本大纲生成器",
        "description": "根据用户输入生成剧本大纲",
        "content": """你是一位资深的编剧，擅长创作引人入胜的剧本大纲。

## 任务
根据用户提供的信息，创作一份完整的剧本大纲。

## 用户输入
- 剧集类型：{series_type}
- 题材：{theme}
- 目标受众：{audience}
- 投放平台：{platform}
- 对标作品：{reference_works}
- 故事梗概：{synopsis}
- 集数：{episode_count}
- 自写大纲：{custom_outline}

## 创作要求
1. **剧集类型适配**：根据"{series_type}"的类型特点进行创作
2. **投放平台适配**：根据"{platform}"的平台调性调整内容
3. **对标作品参考**：参考"{reference_works}"的成功元素，注重创新突破
4. **集数规划**：根据用户指定的集数"{episode_count}"进行合理的故事分配
5. **自写大纲参考**：如果用户提供了自写大纲"{custom_outline}"，请在此基础上进行优化和扩展

## 输出要求
请按以下格式输出剧本大纲：

### 1. 基础信息
- 剧名：
- 类型：
- 预计集数：
- 每集时长：
- 目标受众：

### 2. 故事概述
- 一句话梗概：
- 核心冲突：
- 主题立意：

### 3. 主要人物
[列出3-5个主要人物]

### 4. 故事大纲
**第一幕：开端**
**第二幕：发展**
**第三幕：高潮**
**第四幕：结局**

### 5. 分集大纲
[根据用户指定的集数提供每集的简要剧情]

### 6. 创作建议
- 视觉风格：
- 节奏把控：
- 情感曲线：
""",
        "variables": ["series_type", "theme", "audience", "platform", "reference_works", "synopsis", "episode_count", "custom_outline"]
    },

    # 小说大纲
    "novel": {
        "name": "小说大纲生成器",
        "description": "根据用户输入生成专业级小说大纲",
        "content": """你是一位顶级畅销书策划人+资深文学编辑+爆款网文导师的三位一体创作专家。你深谙市场规律，精通叙事艺术，擅长将创意转化为具有商业潜力的完整大纲。

## 核心任务
基于用户提供的创作要素，构建一份**可直接用于投稿或创作**的专业级小说大纲。这份大纲需要同时具备文学价值和市场竞争力。

---

## 用户创作要素

**基础定位**
- 篇幅体量：{length}
- 类型标签：{genre}
- 目标读者/平台：{target_platform}
- 基调氛围：{tone}

**核心创意**
- 故事梗概：{synopsis}

**深度要素**
- 故事主题：{theme}
- 独特卖点：{unique_selling_point}

**扩展信息**
- 章节数：{chapter_count}
- 自写大纲：{custom_outline}

---

## 输出格式

# 《书名》

## 一、项目定位
- 类型标签、篇幅体量（章节数：{chapter_count}）、目标平台、核心受众、一句话卖点

## 二、核心创意
- 概念金句、主题内核、独特卖点

## 三、世界观架构
- 基础设定、势力版图、核心设定详解

## 四、人物谱系
- 主角档案、反派/对手档案、重要配角群像

## 五、故事结构
- 三幕式框架、关键节拍点

## 六、分卷/分章规划
[根据章节数{chapter_count}进行规划]

## 七、创作执行指南
- 开篇策略、爽点/泪点设计、写作风格指引、避坑指南

---

## 特别要求

1. **所有内容必须基于用户输入**，不要脱离用户给定的核心创意
2. **如果用户提供了自写大纲"{custom_outline}"，请在此基础上优化扩展，保留核心创意**
3. **平台适配要具体**，给出可执行的策略
4. **人物要有血有肉**，避免脸谱化
5. **情节要有逻辑**，避免为爽而爽
6. **商业性要突出**，思考如何让作品在同类中脱颖而出

该方案已经过全能创意大师修正完善。
""",
        "variables": ["length", "genre", "target_platform", "tone", "synopsis", "theme", "unique_selling_point", "chapter_count", "custom_outline"]
    },

    # 平面广告
    "print_ad": {
        "name": "平面广告创意生成器",
        "description": "根据用户输入生成专业级平面广告创意方案",
        "content": """你是一位国际4A广告公司的创意总监+视觉艺术指导+AI提示词工程师的三位一体专家。你深谙消费者心理学，精通视觉传达设计，擅长将商业目标转化为具有传播力的平面广告创意。

## 核心任务
基于用户提供的广告要素，构建一份**可直接用于提案和执行**的专业级平面广告创意方案。这份方案需要同时具备商业转化力和艺术表现力。

---

## 用户输入要素

**品牌与策略**
- 品牌/产品名称：{brand_product}
- 广告目的：{ad_purpose}
- 核心信息：{core_message}

**受众与场景**
- 受众特征：{audience_profile}
- 接触场景：{contact_scene}

**执行要素**
- 风格调性：{style_tone}
- 文案内容：{copy_content}
- 具体尺寸：{size_spec}
- 发布媒介：{publish_media}
- AI提示词目标平台：{ai_platforms}

---

## 风格调性创作指南

### 视觉冲击
- 高对比度配色、大胆构图、强烈视觉张力
- 适合：新品发布、潮流品牌、年轻化产品
- 技巧：打破常规比例、夸张表现、动态冻结

### 极简留白
- 大量负空间、单一焦点、高级感传达
- 适合：奢侈品牌、科技产品、高端服务
- 技巧：少即是多、精准对齐、质感细节

### 幽默搞怪
- 反差萌、谐音梗、 unexpected 的趣味
- 适合：快消品、休闲食品、年轻品牌
- 技巧：情理之中意料之外、自嘲精神、社交货币

### 温情走心
- 情感共鸣、生活场景、细腻洞察
- 适合：母婴产品、金融服务、节日营销
- 技巧：真实感、细节打动、普世情感

### 功能直给
- 产品为核心、卖点可视化、利益点明确
- 适合：电商促销、功能型产品、效果导向
- 技巧：前后对比、数据可视化、使用场景

### 复古怀旧
- 年代感、经典元素、情怀杀
- 适合：老字号、经典产品、节日营销
- 技巧：做旧质感、经典字体、时代符号

### 科技感
- 未来感、数据流、光影效果
- 适合：科技产品、互联网服务、创新品牌
- 技巧：霓虹光效、几何线条、数字元素

### 高级感
- 精致细节、优雅配色、品质感
- 适合：奢侈品、高端服务、品质生活
- 技巧：金色/黑色运用、纹理质感、精致排版

### 国潮风
- 传统元素现代演绎、文化自信、年轻表达
- 适合：国货品牌、文化产品、节日营销
- 技巧：传统纹样、书法字体、中国色

### 赛博朋克
- 霓虹灯、高科技低生活、未来都市
- 适合：游戏、电子产品、年轻潮牌
- 技巧：蓝紫色调、故障艺术、未来城市

### 手绘插画
- 温暖手绘、个性化、艺术感
- 适合：文创产品、儿童产品、生活方式
- 技巧：笔触质感、温暖配色、故事性

### 摄影写实
- 真实质感、生活化、代入感强
- 适合：食品、美妆、生活方式
- 技巧：自然光、真实场景、细节丰富

---

## AI提示词工程规范（针对{ai_platforms}平台）

### 平台特性适配

**豆包/即梦/可灵（国内AI绘图）**
- 使用中文描述，强调中国审美
- 适合：国潮风、写实风格、人物肖像
- 提示词结构：主体+风格+细节+质量词

**Midjourney**
- 使用英文提示词，强调艺术风格
- 适合：概念艺术、插画风格、创意视觉
- 提示词结构：主体描述::风格参考::参数设置

**Stable Diffusion**
- 详细参数控制，强调技术精度
- 适合：精细调整、特定风格、商业出图
- 提示词结构：正向提示词+反向提示词+参数

**DALL-E/GPT**
- 自然语言描述，强调创意概念
- 适合：概念验证、创意发散、快速原型

### 提示词撰写原则
1. **主体明确**：清晰描述画面主体是什么
2. **风格具体**：指定艺术家风格或视觉风格
3. **细节丰富**：光线、色彩、构图、质感
4. **质量限定**：分辨率、渲染质量、专业参数
5. **中文输出**：所有提示词必须用中文撰写

---

## 输出格式（严格按照以下结构）

# 《广告主题》（提炼核心信息的创意表达）

## 一、策略定位

| 维度 | 内容 |
|------|------|
| 品牌/产品 | {brand_product} |
| 广告目的 | {ad_purpose} |
| 核心信息 | {core_message} |
| 目标受众 | {audience_profile} |
| 接触场景 | {contact_scene} |
| 风格调性 | {style_tone} |
| 发布媒介 | {publish_media} |
| 尺寸规格 | {size_spec} |

### 1.1 创意概念
**一句话概念**：用一句话概括这个广告的创意核心

**概念阐释**：
- 洞察来源：（这个创意的洞察来自哪里）
- 创意策略：（如何传达核心信息）
- 情感连接：（与受众建立什么情感联系）

### 1.2 传播目标
- 认知目标：（让受众知道什么）
- 情感目标：（让受众感受什么）
- 行为目标：（让受众做什么）

---

## 二、视觉创意方案

### 2.1 主视觉描述

**画面构图**
```
[用文字详细描述画面布局，如：]
画面采用三分法构图，主体位于右侧黄金分割点...
前景为...，中景为...，背景为...
```

**视觉元素**
- 主体元素：（画面核心是什么）
- 辅助元素：（配合主体的元素）
- 背景处理：（背景如何设计）
- 留白运用：（负空间如何处理）

**色彩方案**
- 主色调：（品牌色或情感色）
- 辅助色：（搭配色，提供具体色号如#FF5733）
- 点缀色：（强调色）
- 色彩心理学：（为什么用这个配色）

**光影氛围**
- 光源方向：（自然光/人造光，方向）
- 光影效果：（柔和/强烈/戏剧化）
- 氛围营造：（光线如何服务情绪）

### 2.2 字体与排版

**字体选择**
- 主标题字体：（字体名称+风格说明）
- 正文字体：（字体名称+风格说明）
- 字体搭配逻辑：（为什么这样搭配）

**排版布局**
```
[描述文字在画面中的位置关系，如：]
主标题位于画面上方1/3处，居中对齐...
正文位于左下角，左对齐...
品牌logo位于右下角...
```

**层级关系**
- 第一视觉层级：（最吸引眼球的元素）
- 第二视觉层级：（次要信息）
- 第三视觉层级：（补充信息）

---

## 三、文案创意

### 3.1 主标题（Slogan）
**方案A**：
**方案B**：
**方案C**：

*选择建议*：（根据广告目的推荐最佳方案）

### 3.2 副标题
[补充主标题，提供更多上下文]

### 3.3 正文文案
[如有需要，提供详细文案]

### 3.4 行动号召（CTA）
[引导用户下一步行动的话术]

### 3.5 品牌标语
[品牌口号或标签line]

---

## 四、AI生成提示词

### 4.1 主视觉提示词（针对{ai_platforms}）

**中文提示词**：
```
[撰写详细的中文AI绘图提示词，包含：]
- 画面主体详细描述
- 风格调性关键词
- 构图与视角
- 光线与色彩
- 质感与细节
- 质量参数
```

**参考示例**：
- 如果{ai_platforms}是Midjourney，提供英文版本
- 如果{ai_platforms}是豆包/即梦，强调中文审美关键词

### 4.2 备选方案提示词
**方案B提示词**：（同一概念的不同视觉表现）
**方案C提示词**：（不同角度的创意尝试）

### 4.3 局部优化提示词
**主体优化**：（如果主体不够突出）
**背景优化**：（如果背景需要调整）
**色彩优化**：（如果色调需要微调）

---

## 五、执行规范

### 5.1 设计规范
- 安全区域：（重要元素避开边缘距离）
- 最小字号：（保证可读性的最小尺寸）
- 品牌元素：（logo使用规范、品牌色值）
- 文件格式：（输出格式建议）

### 5.2 媒介适配
**主视觉延展**：
- 横版适配：（16:9或更宽比例的调整）
- 竖版适配：（9:16或更窄比例的调整）
- 方形适配：（1:1社交媒体版本）

**动态化建议**：（如果需要制作动态版本）
- 动效思路：
- 关键帧描述：

### 5.3 印刷/投放注意事项
- 色彩模式：（RGB for数字，CMYK for印刷）
- 分辨率要求：（根据媒介指定DPI）
- 文件格式：（PNG/JPG/PDF等）
- 出血设置：（印刷出血尺寸）

---

## 六、效果预估与优化

### 6.1 预期效果
- 视觉冲击力：（如何抓住注意力）
- 信息传达率：（核心信息是否清晰）
- 情感共鸣度：（能否打动目标受众）
- 记忆度：（是否容易被记住）

### 6.2 A/B测试建议
**测试变量A**：（如：不同主视觉风格）
**测试变量B**：（如：不同标题文案）
**测试变量C**：（如：不同配色方案）

### 6.3 优化方向
- 如果点击率不理想：（可能的改进点）
- 如果转化率不理想：（可能的改进点）
- 如果品牌认知度不够：（可能的改进点）

---

## 特别要求

1. **所有内容必须基于用户输入**，不要脱离给定的品牌调性和广告目的
2. **风格必须统一**，从视觉到文案到提示词都要符合{style_tone}的定位
3. **AI提示词必须针对{ai_platforms}平台特性优化**，确保生成效果
4. **商业性要突出**，每个创意点都要能解释如何服务商业目标
5. **可执行性要强**，提供的设计规范要具体可操作

该方案已经过全能创意大师修正完善。
""",
        "variables": ["brand_product", "ad_purpose", "core_message", "audience_profile", "contact_scene", "style_tone", "copy_content", "size_spec", "publish_media", "ai_platforms"]
    },

    # TVC广告脚本
    "tvc": {
        "name": "TVC广告脚本生成器",
        "description": "根据用户输入生成专业级TVC电视广告脚本",
        "content": """你是一位国际4A广告公司的创意总监+资深导演+AI视频提示词工程师的三位一体专家。你深谙消费者心理学，精通视听语言，擅长将商业目标转化为具有传播力的TVC广告脚本。

## 核心任务
基于用户提供的广告要素，构建一份**可直接用于提案和拍摄执行**的专业级TVC广告脚本。这份脚本需要同时具备商业转化力和艺术表现力。

---

## 用户输入要素

**品牌与策略**
- 品牌/产品名称：{brand_product}
- 广告目的：{ad_purpose}
- 核心信息：{core_message}

**受众与平台**
- 受众特征：{audience_profile}
- 投放平台：{broadcast_platform}

**执行要素**
- 风格调性：{style_tone}
- 时长：{duration}秒
- 是否生成AI视频提示：{generate_ai_prompt}
- AI视频生成平台：{ai_platforms}
- 参考视频：{reference_video}

---

## 投放平台特性指南

### 电视台-央视
- 调性：大气、正能量、家国情怀
- 受众：全年龄段，偏中老年
- 要求：内容健康向上，避免敏感话题
- 时长：15秒、30秒、60秒标准规格

### 电视台-卫视
- 调性：时尚、年轻化、娱乐性强
- 受众：18-45岁，女性偏多
- 要求：符合频道定位（如湖南卫视偏娱乐，浙江卫视偏综艺）
- 特点：可尝试更具创意的表现形式

### 视频平台（爱奇艺/腾讯/优酷/芒果/B站）
- 调性：根据平台用户画像调整
- B站：二次元、年轻化、弹幕文化
- 芒果TV：女性向、综艺感强
- 特点：可跳过，前3秒必须抓人

### 网络贴片广告
- 调性：快节奏、强冲击、信息密度高
- 特点：用户可跳过，5秒后才有效果
- 要求：前5秒必须有钩子，品牌尽早露出

### 户外大屏（商圈/机场/高铁站）
- 调性：视觉冲击、大场面、少文字
- 特点：无声播放，依赖画面和字幕
- 要求：画面要震撼，信息要简洁

### 电梯广告
- 调性：高频重复、简单直接、洗脑式
- 特点：强制观看但时间短
- 要求：15秒内，重复品牌名，简单卖点

### 影院映前广告
- 调性：高品质、沉浸感、大银幕思维
- 特点：观众无法跳过，注意力集中
- 要求：视听品质要高，可利用环绕声

### 社交媒体（抖音/快手/视频号）
- 调性：原生感、互动性、话题性
- 特点：竖屏优先，节奏快，可互动
- 要求：前3秒必须抓人，适配竖屏

---

## 风格调性创作指南

### 温情走心
- 情感共鸣、生活场景、细腻洞察
- 适合：母婴、金融、保险、节日营销
- 技巧：真实感、细节打动、普世情感
- 音乐：钢琴、弦乐、温暖人声

### 幽默搞怪
- 反差萌、 unexpected 的趣味、社交货币
- 适合：快消品、休闲食品、年轻品牌
- 技巧：情理之中意料之外、自嘲精神
- 节奏：快节奏、反转、意外结局

### 视觉冲击
- 大场面、高对比度、强烈视觉张力
- 适合：汽车、运动品牌、科技产品
- 技巧：航拍、慢动作、特效、宏大场景
- 调色：高饱和度、电影感

### 极简留白
- 大量负空间、单一焦点、高级感
- 适合：奢侈品牌、科技产品、高端服务
- 技巧：少即是多、精准对齐、质感细节
- 节奏：慢节奏、呼吸感

### 功能直给
- 产品为核心、卖点可视化、利益点明确
- 适合：电商、功能型产品、效果导向
- 技巧：前后对比、数据可视化、使用场景
- 信息：清晰、直接、可量化

### 史诗大气
- 宏大叙事、历史感、品牌格局
- 适合：大品牌形象片、周年纪念、企业宣传
- 技巧：大场面、群像、时间跨度、交响乐
- 气质：厚重、深远、格局

### 悬疑烧脑
- 谜题、反转、智商在线
- 适合：游戏、悬疑电影宣传、智力产品
- 技巧：线索埋设、意外真相、开放式结局
- 节奏：层层递进、最后揭晓

### 热血励志
- 拼搏精神、逆袭、梦想
- 适合：运动品牌、教育、招聘、年轻品牌
- 技巧： montage、金句、音乐高潮
- 情绪：燃、感动、共鸣

### 复古怀旧
- 年代感、经典元素、情怀杀
- 适合：老字号、经典产品、节日营销
- 技巧：做旧质感、经典音乐、时代符号
- 色调：暖黄、胶片感

### 科技感
- 未来感、数据流、光影效果
- 适合：科技产品、互联网服务、创新品牌
- 技巧：霓虹光效、几何线条、数字元素
- 音乐：电子、合成器

### 高级感
- 精致细节、优雅、品质感
- 适合：奢侈品、高端服务、品质生活
- 技巧：金色/黑色运用、纹理质感、精致排版
- 气质：克制、优雅、品质

### 纪实风格
- 真实、 raw 、纪录片质感
- 适合：公益、品牌故事、真实案例
- 技巧：手持摄影、自然光、真实采访
- 气质：真实、 raw 、可信

---

## AI视频提示词工程规范（针对{ai_platforms}平台）

### 平台特性适配

**可灵/豆包（国内AI视频）**
- 使用中文描述，强调中国审美和人物表演
- 适合：国风、写实、人物表情动作、日常生活场景
- 提示词结构：主体+动作+场景+风格+质量词
- 注意：人物表情和动作要详细描述，强调自然流畅

**Seedance 2.0（即梦视频生成模型）**
- 使用中文描述，字节跳动出品，质量优秀
- 适合：短视频风格、快节奏剪辑感、年轻人审美
- 提示词结构：场景描述+镜头运动+情绪氛围+风格关键词
- 注意：强调动态感和节奏感，适合社交媒体风格

**Sora 2（OpenAI视频生成）**
- 使用英文提示词效果最佳，物理规律理解强
- 适合：复杂场景、多主体互动、电影级画面
- 提示词结构：主体描述::动作::场景::光影::镜头::质量
- 注意：对物理规律、光影效果理解深刻，可描述复杂运动

**Veo 3.1（Google视频生成）**
- 使用英文提示词，细节丰富，时长较长
- 适合：细腻画面、丰富细节、长镜头
- 提示词结构：详细场景+主体动作+环境描述+氛围+技术参数
- 注意：擅长生成细腻、丰富的视觉细节

**Runway（创意AI视频）**
- 使用英文提示词，艺术性强，创意工具丰富
- 适合：实验性视频、艺术表达、风格化视觉
- 提示词结构：风格参考+主体+运动描述+艺术风格
- 注意：抽象概念的可视化，支持多种创意控制

**Pika（快速AI视频生成）**
- 使用英文提示词，生成速度快，适合快速原型
- 适合：概念验证、快速迭代、社交媒体内容
- 提示词结构：简洁描述+风格+动作
- 注意：快速生成，适合探索性创作

**Wan 2.2（阿里视频生成模型）**
- 使用中文描述，阿里出品，中文理解优秀
- 适合：中文场景、国风元素、电商视频
- 提示词结构：中文场景描述+主体动作+商业氛围+质量词
- 注意：对中文语境理解好，适合商业视频生成

### 提示词撰写原则
1. **镜头语言**：明确镜头类型（特写/中景/全景）、运镜方式（推/拉/摇/移）
2. **光影氛围**：光源方向、光线质感、时间氛围
3. **动作描述**：主体动作要具体、连贯、有节奏
4. **场景细节**：环境元素、道具、背景
5. **质量限定**：分辨率、帧率、渲染质量
6. **中文输出**：所有提示词必须用中文撰写

---

## 输出格式（严格按照以下结构）

# 《TVC广告主题》（提炼核心信息的创意表达）

## 一、项目定位

| 维度 | 内容 |
|------|------|
| 品牌/产品 | {brand_product} |
| 广告目的 | {ad_purpose} |
| 核心信息 | {core_message} |
| 目标受众 | {audience_profile} |
| 投放平台 | {broadcast_platform} |
| 时长 | {duration}秒 |
| 风格调性 | {style_tone} |

### 1.1 创意概念
**一句话概念**：用一句话概括这个广告的创意核心

**概念阐释**：
- 洞察来源：（这个创意的洞察来自哪里）
- 创意策略：（如何传达核心信息）
- 情感连接：（与受众建立什么情感联系）
- 平台适配：（如何适配{broadcast_platform}的特性）

### 1.2 传播目标
- 认知目标：（让受众知道什么）
- 情感目标：（让受众感受什么）
- 行为目标：（让受众做什么）

---

## 二、创意方案

### 2.1 故事梗概（100字内）
[概括整个广告的故事，突出冲突和转折]

### 2.2 叙事结构
**起**（0-{duration//4}s）：
- 钩子：（如何抓住注意力）
- 设定：（建立场景和人物）

**承**（{duration//4}s-{duration//2}s）：
- 发展：（情节推进）
- 冲突：（核心矛盾展现）

**转**（{duration//2}s-{duration*3//4}s）：
- 高潮：（情感或情节顶点）
- 转折：（关键转折时刻）

**合**（{duration*3//4}s-{duration}s）：
- 结局：（问题解决或情感升华）
- 品牌露出：（自然融入品牌信息）

---

## 三、详细脚本

### 3.1 分镜脚本

| 镜号 | 时间 | 景别 | 画面描述 | 镜头运动 | 声音/对白 | 字幕/花字 | 备注 |
|------|------|------|----------|----------|-----------|-----------|------|
| 1 | 0-3s | 全景 | ... | 固定 | ... | ... | ... |
| 2 | 3-6s | 中景 | ... | 推镜 | ... | ... | ... |
| ... | ... | ... | ... | ... | ... | ... | ... |

### 3.2 关键帧描述
**关键帧1**（时间点）：
- 画面：（详细视觉描述）
- 情绪：（此时应有的情感氛围）
- 信息：（此时传达的信息）

**关键帧2**（时间点）：
...

---

## 四、制作执行方案

### 4.1 场景清单

**场景一**：[场景名称]
- 地点：
- 时间：（日/夜/黄昏等）
- 氛围：（光影、色调、情绪）
- 人物：
- 关键道具：
- 拍摄难度：（高/中/低）

**场景二**：
...

### 4.2 演员需求
**主要演员**
- 角色：（年龄、性别、气质要求）
- 表演要求：（情绪层次、动作要求）
- 参考形象：（可对标的具体演员或形象）

**群演/特约**
...

### 4.3 拍摄技术要求
**摄影**
- 设备规格：（如：ARRI Alexa Mini LF）
- 镜头组：（如：Master Prime定焦组）
- 特殊设备：（如：摇臂、轨道、无人机）
- 拍摄手法：（如：手持、斯坦尼康、固定）

**灯光**
- 光效设计：（如：自然光效、戏剧光效）
- 特殊光效：（如：霓虹、投影、剪影）

**美术**
- 场景设计：
- 道具清单：
- 服装造型：
- 化妆要求：

### 4.4 后期制作要求
**剪辑**
- 剪辑风格：（如：快节奏、叙事性、诗意）
- 转场方式：（如：硬切、叠化、匹配剪辑）
- 节奏控制：（如：前快后慢、层层递进）

**调色**
- 整体色调：（如：暖黄、冷蓝、高对比）
- 特殊处理：（如：胶片模拟、复古质感）

**声音设计**
- 配音风格：（如：温暖女声、磁性男声）
- BGM：（风格描述+参考音乐）
- 音效：（关键音效设计）
- 混音要求：（如：人声突出、氛围沉浸）

**特效**
- CG需求：（如：场景延伸、产品CG）
- 合成需求：（如：绿幕合成、画面修复）
- 字幕包装：（如：动态字幕、品牌logo动画）

---

## 五、AI视频生成提示词（如{generate_ai_prompt}为"是"）

### 5.1 整体风格提示词
```
[针对{ai_platforms}平台的整体风格描述，包括：]
- 视觉风格关键词
- 光影氛围
- 色彩调性
- 镜头语言
- 质量参数
```

### 5.2 分镜提示词
**镜号1**（时间：0-3s）：
- 中文提示词：
- 英文提示词（如适用）：
- 负向提示词（如适用）：

**镜号2**（时间：3-6s）：
...

### 5.3 关键帧提示词
**关键帧1**：
- 提示词：
- 参考参数：

---

## 六、品牌整合方案

### 6.1 品牌露出策略
**露出时机**：
- 首次露出：（时间点，方式）
- 二次露出：（时间点，方式）
- 最终露出：（时间点，方式）

**露出方式**：
- 产品展示：（如何自然展示产品）
- Logo呈现：（Logo出现的方式）
- 品牌色运用：（如何在画面中融入品牌色）

### 6.2 Slogan与文案
**主Slogan**：（15字以内）
**副文案**：（补充说明）
**行动号召**：（引导行动的话术）

### 6.3 品牌调性契合
- 如何体现品牌核心价值：
- 如何强化品牌记忆点：
- 如何与品牌历史/其他广告形成呼应：

---

## 七、效果预估与优化

### 7.1 预期效果
- 记忆度：（预计受众能记住什么）
- 好感度：（预计受众情感反应）
- 传播力：（是否具备社交传播潜力）
- 转化率：（对行为的预期影响）

### 7.2 测试建议
**A/B测试方案**
- 变量A：（如：不同结尾）
- 变量B：（如：不同音乐）
- 测试指标：（如：完播率、点击率）

### 7.3 优化方向
- 如果完播率不理想：（可能的改进点）
- 如果品牌记忆度不够：（可能的改进点）
- 如果情感共鸣不足：（可能的改进点）

---

## 特别要求

1. **所有内容必须基于用户输入**，不要脱离给定的品牌调性和广告目的
2. **时长必须严格控制在{duration}秒内**，每镜时间要精确计算
3. **平台适配要具体**，针对{broadcast_platform}给出可执行的策略
4. **AI提示词必须针对{ai_platforms}平台特性优化**，确保生成效果
5. **商业性要突出**，每个创意点都要能解释如何服务商业目标
6. **可执行性要强**，提供的制作规范要具体可操作

该方案已经过全能创意大师修正完善。
""",
        "variables": ["brand_product", "ad_purpose", "core_message", "audience_profile", "broadcast_platform", "style_tone", "duration", "generate_ai_prompt", "ai_platforms", "reference_video"]
    }
}


class PromptManager:
    """提示词管理器"""

    def __init__(self):
        self.settings = get_settings()

    async def get_prompt(
        self,
        db: AsyncSession,
        module: str
    ) -> PromptTemplate:
        """
        获取模块的激活提示词模板

        Args:
            db: 数据库会话
            module: 模块名称

        Returns:
            提示词模板
        """
        # 尝试从数据库获取激活的模板
        result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.module == module)
            .where(PromptTemplate.is_active == True)
            .order_by(PromptTemplate.updated_at.desc())
            .limit(1)
        )
        template = result.scalar_one_or_none()

        if template:
            return template

        # 如果数据库中没有，返回默认模板
        return self.get_default_prompt(module)

    def get_default_prompt(self, module: str) -> PromptTemplate:
        """
        获取默认提示词模板

        Args:
            module: 模块名称

        Returns:
            提示词模板
        """
        default = DEFAULT_PROMPTS.get(module, {})

        return PromptTemplate(
            module=module,
            name=default.get("name", f"{module} 生成器"),
            description=default.get("description", ""),
            content=default.get("content", ""),
            variables=str(default.get("variables", []))
        )

    def render_prompt(
        self,
        template: PromptTemplate,
        variables: Dict[str, Any],
        module: str = None
    ) -> str:
        """
        渲染提示词模板（智能变量填充）

        未提供的变量将自动使用默认值

        Args:
            template: 提示词模板
            variables: 变量字典（用户输入）
            module: 模块名称（用于获取变量配置）

        Returns:
            渲染后的提示词
        """
        logger = get_logger("prompt_manager")
        content = template.content

        # 获取模块变量配置
        module_config = MODULE_VARIABLES_CONFIG.get(module, {})
        var_configs = module_config.get("variables", {})

        # 从模板中提取所有变量
        template_vars = self._extract_variables(content)

        # 构建完整的变量字典（用户值 + 默认值）
        filled_vars = {}
        for var_name in template_vars:
            # 1. 优先使用用户提供的值
            if var_name in variables and variables[var_name] is not None and variables[var_name] != "":
                filled_vars[var_name] = variables[var_name]
            # 2. 尝试从前端字段映射
            elif var_name in var_configs:
                front_field = var_configs[var_name].get("front_field")
                if front_field and front_field in variables and variables[front_field]:
                    filled_vars[var_name] = variables[front_field]
                else:
                    # 3. 使用默认值
                    filled_vars[var_name] = var_configs[var_name].get(
                        "default", "未指定")
            # 4. 使用通用默认值
            else:
                filled_vars[var_name] = "未指定"

        # 特殊处理：custom_outline 变量
        # 如果内容已包含"用户上传的大纲文件内容"标记，说明已正确解析
        # 如果为空或只是URL，则显示"未提供"
        if "custom_outline" in filled_vars:
            outline_value = filled_vars["custom_outline"]
            if not outline_value or outline_value.strip() == "":
                filled_vars["custom_outline"] = "（未提供自写大纲）"
            elif outline_value.startswith("http") or outline_value.startswith("/api"):
                # 如果还是URL格式，说明解析失败
                filled_vars["custom_outline"] = f"（文件解析失败，原URL: {outline_value[:50]}...）"
                logger.warning(
                    f"custom_outline 文件解析可能失败，值仍为URL: {outline_value[:100]}")

        # 替换变量
        for key, value in filled_vars.items():
            placeholder = f"{{{key}}}"
            # 处理不同类型的值
            if value is None:
                display_value = "未指定"
            elif isinstance(value, (list, dict)):
                display_value = json.dumps(value, ensure_ascii=False)
            else:
                display_value = str(value)
            content = content.replace(placeholder, display_value)

            # 调试日志：记录 ai_platforms 的值
            if key == "ai_platforms":
                logger.info(
                    f"AI平台变量填充 - 原始值: {value!r}, 显示值: {display_value!r}")

        logger.info(f"提示词变量填充完成 - 模块: {module}, 变量数: {len(filled_vars)}")
        return content

    def _extract_variables(self, content: str) -> List[str]:
        """
        从模板内容中提取变量名

        Args:
            content: 模板内容

        Returns:
            变量名列表
        """
        # 匹配 {variable_name} 格式的变量
        pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
        variables = list(set(re.findall(pattern, content)))
        return variables

    def get_module_variables(self, module: str) -> Dict[str, Any]:
        """
        获取模块的变量配置

        Args:
            module: 模块名称

        Returns:
            变量配置字典
        """
        return MODULE_VARIABLES_CONFIG.get(module, {})

    def validate_variables(
        self,
        module: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证变量是否满足模块要求

        Args:
            module: 模块名称
            variables: 变量字典

        Returns:
            验证结果 {"valid": bool, "missing": list, "errors": list}
        """
        module_config = MODULE_VARIABLES_CONFIG.get(module, {})
        var_configs = module_config.get("variables", {})

        missing = []
        errors = []

        for var_name, var_config in var_configs.items():
            if var_config.get("required", False):
                # 检查必需变量
                front_field = var_config.get("front_field", var_name)
                if var_name not in variables and front_field not in variables:
                    missing.append(var_name)
                elif not variables.get(var_name) and not variables.get(front_field):
                    missing.append(var_name)

        return {
            "valid": len(missing) == 0,
            "missing": missing,
            "errors": errors
        }

    def build_prompt_context(
        self,
        module: str,
        user_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建提示词上下文（用于调试和预览）

        显示每个变量的实际值和来源

        Args:
            module: 模块名称
            user_input: 用户输入

        Returns:
            上下文字典
        """
        module_config = MODULE_VARIABLES_CONFIG.get(module, {})
        var_configs = module_config.get("variables", {})

        context = {
            "module": module,
            "variables": {}
        }

        for var_name, var_config in var_configs.items():
            var_info = {
                "description": var_config.get("description", ""),
                "required": var_config.get("required", False),
                "default": var_config.get("default"),
                "actual_value": None,
                "source": "default"
            }

            # 确定实际值和来源
            if var_name in user_input and user_input[var_name]:
                var_info["actual_value"] = user_input[var_name]
                var_info["source"] = "user_input"
            elif "front_field" in var_config:
                front_field = var_config["front_field"]
                if front_field in user_input and user_input[front_field]:
                    var_info["actual_value"] = user_input[front_field]
                    var_info["source"] = "mapped"

            if var_info["actual_value"] is None:
                var_info["actual_value"] = var_config.get("default")

            context["variables"][var_name] = var_info

        return context

    async def create_or_update_prompt(
        self,
        db: AsyncSession,
        module: str,
        name: str,
        content: str,
        description: Optional[str] = None,
        variables: Optional[List[str]] = None,
        is_active: bool = True
    ) -> PromptTemplate:
        """
        创建或更新提示词模板

        Args:
            db: 数据库会话
            module: 模块名称
            name: 模板名称
            content: 提示词内容
            description: 描述
            variables: 变量列表
            is_active: 是否启用

        Returns:
            提示词模板
        """
        # 将之前的激活模板设为非激活
        result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.module == module)
            .where(PromptTemplate.is_active == True)
        )
        old_templates = result.scalars().all()

        for old_template in old_templates:
            old_template.is_active = False

        # 创建新模板
        new_template = PromptTemplate(
            module=module,
            name=name,
            content=content,
            description=description,
            variables=json.dumps(
                variables, ensure_ascii=False) if variables else None,
            is_active=is_active
        )

        db.add(new_template)
        await db.commit()
        await db.refresh(new_template)

        return new_template

    def get_all_modules(self) -> List[str]:
        """获取所有支持的模块"""
        return list(DEFAULT_PROMPTS.keys())


# 全局提示词管理器实例
prompt_manager = PromptManager()


def get_prompt_manager() -> PromptManager:
    """获取提示词管理器实例"""
    return prompt_manager
