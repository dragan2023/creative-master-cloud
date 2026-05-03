"""人物状态追踪常量定义

包含状态变化维度、类型映射、视觉呈现指南等常量
"""

NOVEL_STATE_DIMENSIONS = [
    "能力变化",
    "身份变化",
    "地点变化",
    "性格变化",
    "关系变化",
    "称呼变化",
    "台词风格",
    "情感变化",
    "其他变化"
]

SCRIPT_STATE_DIMENSIONS = [
    "能力变化",
    "身份变化",
    "地点变化",
    "性格变化",
    "关系变化",
    "称呼变化",
    "台词风格",
    "情感变化",
    "其他变化"
]

STATE_CHANGE_TYPES = {
    "location": "位置变化",
    "identity": "身份变化",
    "ability": "能力变化",
    "relationship": "关系变化",
    "personality": "性格变化",
    "title": "称呼变化",
    "dialogue_style": "台词风格",
    "emotion": "情感变化",
    "other": "其他变化"
}

VISUAL_PRESENTATION_GUIDE = {
    "location": {
        "novel": "通过环境描写、移动过程呈现",
        "script": "通过转场设计、场景切换呈现"
    },
    "identity": {
        "novel": "通过他人态度、正式场合描写呈现",
        "script": "通过服装变化、场景变化、他人态度呈现"
    },
    "ability": {
        "novel": "通过战斗/训练场景描写呈现",
        "script": "通过动作设计、特效呈现"
    },
    "relationship": {
        "novel": "通过对话、互动描写呈现",
        "script": "通过对手戏、站位、眼神交流呈现"
    },
    "personality": {
        "novel": "通过行为、心理描写呈现",
        "script": "通过表演层次、表情动作呈现"
    },
    "emotion": {
        "novel": "通过心理描写、行为反应呈现",
        "script": "通过表情、肢体语言、镜头语言呈现"
    }
}
