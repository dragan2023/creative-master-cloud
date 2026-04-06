"""
多Agent协作文学作品生成系统 - 写手Agent提示词

模块: agents.writing.prompts
文件: writer_prompts.py
功能: 定义写手Agent的系统提示词和任务提示词，支持小说和剧本分类处理

创建时间: 2026-03-27
最后修改: 2026-04-01
版本: 2.0.0

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""

from .character_state_prompts import (
    get_writer_system_prompt,
    get_writer_user_prompt,
    CHARACTER_STATE_PROMPTS,
    NOVEL_STATE_DIMENSIONS,
    SCRIPT_STATE_DIMENSIONS,
    STATE_CHANGE_TYPES,
    VISUAL_PRESENTATION_GUIDE
)

WRITER_PROMPTS = {
    "system": CHARACTER_STATE_PROMPTS["novel_writer_system"],

    "system_novel": CHARACTER_STATE_PROMPTS["novel_writer_system"],

    "system_script": CHARACTER_STATE_PROMPTS["script_writer_system"],

    "write_scene": """请根据以下场景规划创作正文内容。

## 创作要求

1. **场景目标**：清晰呈现场景规划中的核心事件
2. **角色表现**：通过对话和行动展现角色性格
3. **环境描写**：营造符合情绪基调的场景氛围
4. **情节推进**：推动故事向前发展
5. **结尾钩子**：在场景结尾设置适当的悬念或过渡

## 场景规划

**场景标题：** {scene_title}

**场景地点：** {location}

**出场角色：** {characters}

**核心事件：** {event}

**情绪基调：** {mood}

**字数目标：** {word_target}字

**结尾钩子要求：** {hook}

## 参考信息

**前文摘要：**
{previous_content}

**角色设定：**
{character_profiles}

**风格指南：**
{style_guide}

**全局背景：**
{global_context}

## 输出要求

请直接输出场景正文内容，不要包含JSON格式或其他元数据。内容应当：
- 符合字数目标（允许±10%的浮动）
- 语言流畅，描写生动
- 对话自然，符合角色身份
- 在结尾处体现钩子设计
- 保持与前文的连贯性""",

    "write_dialogue": """请为以下场景创作一段高质量的对话。

## 对话创作原则

1. **角色区分**：每个角色的语言风格要有明显区别
2. **潜台词**：对话要有言外之意，不要直白表达
3. **节奏变化**：长短句交替，避免单调
4. **动作穿插**：适当插入动作和表情描写
5. **推进情节**：对话要推动情节或揭示信息

## 场景信息

**对话场景：** {scene_context}

**参与角色：** {characters}

**对话目的：** {dialogue_purpose}

**情绪氛围：** {mood}

**需要揭示的信息：** {reveal_info}

## 角色语言特点

{character_voices}

## 输出要求

请创作一段自然流畅的对话，穿插适当的动作和神态描写。对话应当：
- 符合角色性格和身份
- 推动情节发展
- 展现角色关系
- 富有张力和层次感""",

    "write_description": """请为以下场景创作环境描写。

## 描写创作原则

1. **五感并用**：调动视觉、听觉、嗅觉、触觉、味觉
2. **动静结合**：静态景物与动态元素结合
3. **情感投射**：通过景物描写烘托情绪
4. **细节选择**：选择有代表性的细节，避免堆砌
5. **视角统一**：保持叙述视角的一致性

## 场景信息

**描写对象：** {subject}

**场景氛围：** {atmosphere}

**情绪基调：** {mood}

**时间段：** {time_of_day}

**天气/季节：** {weather_season}

**观察视角：** {perspective}

## 输出要求

请创作一段富有感染力的环境描写，应当：
- 营造清晰的画面感
- 烘托场景氛围
- 为后续情节做铺垫
- 字数控制在200-500字""",

    "write_action": """请为以下场景创作动作描写。

## 动作描写原则

1. **节奏感**：快节奏场景用短句，慢节奏场景可详细描写
2. **连贯性**：动作序列要逻辑连贯
3. **感官细节**：描写动作的视觉、听觉效果
4. **心理反应**：穿插角色的心理活动
5. **结果呈现**：清晰呈现动作的结果和影响

## 场景信息

**动作类型：** {action_type}

**参与角色：** {characters}

**动作起因：** {cause}

**预期结果：** {expected_result}

**紧张程度：** {tension_level}

**环境限制：** {environment_constraints}

## 输出要求

请创作一段紧张刺激的动作描写，应当：
- 动作序列清晰连贯
- 节奏张弛有度
- 富有画面感和冲击力
- 展现角色的能力和性格""",

    "continue_writing": """请根据前文继续创作以下内容。

## 续写要求

1. **保持连贯**：与前文在情节、风格、语气上保持一致
2. **自然过渡**：从断点处自然延续
3. **推进发展**：推动情节向前发展
4. **保持风格**：延续前文的叙事风格和语言特点

## 前文内容

{previous_content}

## 续写目标

**续写方向：** {continuation_goal}

**需要达到的效果：** {target_effect}

**字数要求：** {word_count}字

## 场景规划（如有）

{scene_plan}

## 输出要求

请直接输出续写内容，与前文自然衔接，不要重复前文内容。""",

    "revise_content": """请根据以下反馈修改内容。

## 修改要求

1. **针对性修改**：针对反馈中的每一点进行修改
2. **保持核心**：保持原文的核心情节和风格
3. **提升质量**：在修改的同时提升整体质量
4. **完整呈现**：输出修改后的完整内容

## 原文内容

{original_content}

## 修改反馈

{feedback}

## 修改重点

{revision_focus}

## 输出要求

请输出修改后的完整内容，应当：
- 解决反馈中的所有问题
- 保持文风统一
- 提升整体质量
- 完整呈现修改后的内容""",

    "write_scene_with_state": CHARACTER_STATE_PROMPTS["novel_writer_user"],

    "write_scene_novel": CHARACTER_STATE_PROMPTS["novel_writer_user"],

    "write_scene_script": CHARACTER_STATE_PROMPTS["script_writer_user"]
}


def get_writer_prompts(content_type: str = "novel") -> dict:
    """获取写手提示词

    Args:
        content_type: 内容类型，"novel" 或 "script"

    Returns:
        包含系统提示词和用户提示词的字典
    """
    return {
        "system": get_writer_system_prompt(content_type),
        "user": get_writer_user_prompt(content_type)
    }


def get_state_dimensions(content_type: str = "novel") -> list:
    """获取状态变化维度列表

    Args:
        content_type: 内容类型，"novel" 或 "script"/"series_script"/"movie_script"

    Returns:
        状态变化维度列表
    """
    # 判断是否为剧本类型（包括剧集和电影）
    if content_type in ("script", "series_script", "movie_script"):
        return SCRIPT_STATE_DIMENSIONS
    return NOVEL_STATE_DIMENSIONS
