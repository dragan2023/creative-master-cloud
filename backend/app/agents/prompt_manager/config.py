"""
提示词管理器配置模块
定义各模块支持的变量、默认值和描述

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""

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
            "aspect_ratio": {
                "default": "9:16",
                "description": "画幅比例（如：9:16竖屏、16:9横屏、1:1方形、21:9超宽屏）",
                "required": False,
                "options": ["9:16", "16:9", "1:1", "3:4", "4:3", "21:9"]
            },
            "mode": {
                "default": "virtual",
                "description": "生成模式（real=现实模式用于真人拍摄，virtual=虚拟模式用于AI生成）",
                "required": False,
                "options": ["real", "virtual"]
            },
            "generate_ai_prompt": {
                "default": "否",
                "description": "是否生成AI视频提示",
                "required": False
            },
            "ai_platforms": {
                "default": "Seedance 2.0",
                "description": "AI视频生成平台",
                "required": False,
                "options": ["Seedance 2.0", "MiniMax H3"]
            },
            "generate_storyboard_images": {
                "default": "否",
                "description": "是否生成分镜图提示词（用于AI绘图生成参考图）",
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
            },
            # 参考资料上传
            "reference_materials": {
                "default": "",
                "description": "参考资料（用户上传的文本文件，包含创作参考素材）",
                "required": False,
                "front_field": "reference_materials"
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

    # ==================== 两阶段大纲生成模块变量配置 ====================

    "novel_global_outline": {
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
            "synopsis": {
                "default": "待补充故事梗概",
                "description": "故事梗概",
                "required": True,
                "front_field": "description"
            },
            "theme": {
                "default": "",
                "description": "故事主题",
                "required": False
            },
            "unique_selling_point": {
                "default": "",
                "description": "独特卖点",
                "required": False
            },
            "chapter_count": {
                "default": "",
                "description": "预计章节数",
                "required": False
            },
            "custom_outline": {
                "default": "",
                "description": "自写大纲",
                "required": False
            }
        }
    },

    "novel_unit_summaries": {
        "variables": {
            "global_outline": {
                "default": "",
                "description": "全局大纲内容",
                "required": True
            },
            "chapter_count": {
                "default": "",
                "description": "章节数",
                "required": True
            },
            "title_style_guidance": {
                "default": "",
                "description": "标题风格指导文本",
                "required": False
            }
        }
    },

    "print_ad": {
        "variables": {
            "design_category": {
                "default": "商业广告",
                "description": "设计类别（logo设计/商业广告/宣传单页/公益广告/政府宣传/海报设计/展架设计/包装设计/其他设计）",
                "required": True,
                "front_field": "design_category",
                "options": ["logo设计", "商业广告", "宣传单页", "公益广告", "政府宣传", "海报设计", "展架设计", "包装设计", "其他设计"]
            },
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
            },
            "description": {
                "default": "",
                "description": "详细描述（用户对广告创意的详细要求说明）",
                "required": False,
                "front_field": "description"
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
            "aspect_ratio": {
                "default": "16:9",
                "description": "画幅比例（如：16:9横屏、9:16竖屏、1:1方形、21:9影院宽屏）",
                "required": False,
                "options": ["16:9", "9:16", "1:1", "21:9", "3:4", "4:3"]
            },
            "generate_ai_prompt": {
                "default": "否",
                "description": "是否生成AI视频生成提示",
                "required": False
            },
            "ai_platforms": {
                "default": "Seedance 2.0",
                "description": "AI视频生成平台",
                "required": False,
                "options": ["Seedance 2.0", "MiniMax H3"]
            },
            "reference_video": {
                "default": "",
                "description": "参考视频URL（仅Gemini 1.5 Pro/Flash支持）",
                "required": False
            },
            "description": {
                "default": "",
                "description": "详细描述（用户对广告创意的详细要求说明）",
                "required": False,
                "front_field": "description"
            },
            "mode": {
                "default": "real",
                "description": "生成模式(real=现实模式用于真人拍摄，virtual=虚拟模式用于AI生成)",
                "required": False,
                "options": ["real", "virtual"]
            }
        }
    },

    # ==================== 原创IP计划模块变量配置 ====================
    "original_ip": {
        "variables": {
            "ip_description": {
                "default": "",
                "description": "IP角色概括性描述（自由文本，AI将自动解析并补足各维度信息）",
                "required": True,
                "front_field": "ip_description"
            },
            "target_platform": {
                "default": "综合",
                "description": "目标平台（漫画/动画/游戏/周边/短视频/综合）",
                "required": False,
                "front_field": "target_platform"
            },
            "reference_ip": {
                "default": "无",
                "description": "参考的知名IP（可选，用于风格借鉴）",
                "required": False,
                "front_field": "reference_ip"
            },
            "commercial_goal": {
                "default": "打造具有商业价值的原创IP角色",
                "description": "商业目标（可选，如：品牌代言、周边开发、内容IP化等）",
                "required": False,
                "front_field": "commercial_goal"
            },
            "custom_requirements": {
                "default": "无特殊要求",
                "description": "其他特殊要求（可选）",
                "required": False,
                "front_field": "custom_requirements"
            }
        }
    },
    "practical_writing": {
        "variables": {
            "title": {
                "default": "",
                "description": "文档标题/主题（必填）",
                "required": True,
                "front_field": "title"
            },
            "doc_type": {
                "default": "演讲稿",
                "description": "文案类型：演讲稿/新闻稿/会议纪要/商业计划书/财务报表/标书/求职信简历/工作总结/述职报告/市场调研报告/可行性分析报告/合同协议/通知公告/邀请函/感谢信道歉信/产品说明书/培训方案/活动策划方案/规章制度/社交媒体文案/学术白皮书",
                "required": True,
                "front_field": "doc_type"
            },
            "industry": {
                "default": "信息技术/互联网",
                "description": "所属行业：金融保险证券/信息技术互联网/教育培训/医疗健康制药/制造业工业/零售电商/房地产建筑/法律咨询/餐饮酒店/交通物流/能源环保/农业食品/文化传媒广告/政府公共事业/汽车出行/游戏娱乐",
                "required": True,
                "front_field": "industry"
            },
            "description": {
                "default": "",
                "description": "详细描述，说明具体需求、背景、关键要素等",
                "required": True,
                "front_field": "description"
            },
            "doc_length": {
                "default": "中篇（1000-3000字）",
                "description": "文档长度：短篇（500-1000字）/中篇（1000-3000字）/长篇（3000-8000字）",
                "required": False,
                "front_field": "doc_length"
            },
            "formality": {
                "default": "半正式",
                "description": "正式程度：正式/半正式/非正式",
                "required": False,
                "front_field": "formality"
            },
            "target_audience": {
                "default": "上级领导/管理层",
                "description": "目标受众：上级领导管理层/客户合作伙伴/下属团队成员/社会公众/特定群体",
                "required": False,
                "front_field": "target_audience"
            },
            "language_style": {
                "default": "专业严谨",
                "description": "语言风格：专业严谨/简洁明了/生动活泼/说服力强/情感共鸣/数据驱动",
                "required": False,
                "front_field": "language_style"
            },
            "additional_requirements": {
                "default": "",
                "description": "附加要求，补充其他特殊需求",
                "required": False,
                "front_field": "additional_requirements"
            }
        }
    }
}
