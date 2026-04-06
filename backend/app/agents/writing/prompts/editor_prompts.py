"""
多Agent协作文学作品生成系统 - 逻辑编辑Agent提示词

模块: agents.writing.prompts
文件: editor_prompts.py
功能: 定义逻辑编辑Agent的系统提示词和任务提示词，支持小说和剧本分类处理

创建时间: 2026-03-27
最后修改: 2026-04-01
版本: 2.0.0

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""

from .character_state_prompts import (
    get_editor_system_prompt,
    get_editor_user_prompt,
    CHARACTER_STATE_PROMPTS,
    NOVEL_STATE_DIMENSIONS,
    SCRIPT_STATE_DIMENSIONS,
    STATE_CHANGE_TYPES,
    VISUAL_PRESENTATION_GUIDE
)

EDITOR_PROMPTS = {
    "system": CHARACTER_STATE_PROMPTS["novel_editor_system"],

    "system_novel": CHARACTER_STATE_PROMPTS["novel_editor_system"],

    "system_script": CHARACTER_STATE_PROMPTS["script_editor_system"],

    "check_logic": """请对以下内容进行全面的逻辑一致性审查。

## 审查维度

1. **情节逻辑**
   - 事件因果关系是否合理
   - 情节转折是否有铺垫
   - 关键决策是否符合情境
   - 是否存在逻辑漏洞或跳跃

2. **角色一致性**
   - 角色行为是否符合其性格设定
   - 角色决策是否与其背景一致
   - 角色能力是否前后一致
   - 角色关系发展是否合理

3. **时间线一致性**
   - 时间顺序是否正确
   - 时间跨度是否合理
   - 是否存在时间矛盾
   - 季节、时辰等细节是否一致

4. **场景一致性**
   - 场景描述是否前后矛盾
   - 空间布局是否合理
   - 物品出现/消失是否有交代
   - 环境变化是否有依据

5. **对话合理性**
   - 对话是否符合角色身份
   - 对话是否符合情境氛围
   - 对话是否推动情节
   - 对话风格是否统一

6. **人物状态一致性**（重点）
   - 人物当前位置是否与前文状态一致
   - 人物身份/官职变化是否有合理过渡
   - 人物关系的演变是否符合轨迹
   - 新增人物设定是否与已有设定冲突
   - 人物行为是否符合其当前状态和历史轨迹

## 待审查内容

{draft_content}

## 角色设定

{character_profiles}

## 前文场景

{previous_scenes}

## 当前大纲

{outline}

## 全局背景

{global_context}

## 人物状态快照（重要：用于状态一致性检查）

{character_state_snapshot}

## 人物关系摘要

{relationship_summary}

## 人物状态提取指南（重要）

请仔细阅读内容，提取以下人物状态变化信息：

### 位置变化检测
- 人物是否移动到新地点？
- 移动是否有合理过渡描述？
- 是否有瞬移等不合理现象？

### 身份/官职变化检测
- 人物身份是否有变化？
- 变化是否有剧情支撑？
- 是否有正式的晋升/贬谪过程？

### 关系变化检测
- 人物间关系是否有新发展？
- 关系变化是否有情感铺垫？
- 是否有新的敌对/联盟关系建立？

### 新人物检测
- 是否有新人物登场？
- 新人物是否有基本设定（身份、背景）？
- 新人物是否与已有设定冲突？

## 输出格式

```json
{{
    "issues": [
        {{
            "type": "情节逻辑/角色一致性/时间线/场景一致性/对话合理性/人物状态一致性",
            "severity": "high/medium/low",
            "location": "问题所在位置（如：第3段）",
            "description": "具体问题描述",
            "suggestion": "修改建议"
        }}
    ],
    "character_state_updates": [
        {{
            "character": "人物名称",
            "updates": {{
                "location": "新位置（如有变化）",
                "identity": "新身份（如有变化）",
                "status_change": "状态变化描述（如：受伤、晋升、情绪变化等）",
                "relationships": {{"其他人物": "关系变化描述"}}
            }},
            "evidence": "内容中支持此变化的原文引用"
        }}
    ],
    "new_characters": [
        {{
            "name": "新人物名称",
            "identity": "身份",
            "location": "首次出现位置",
            "attributes": {{
                "personality": "性格特点",
                "background": "背景信息"
            }},
            "first_appearance_context": "首次出现的上下文"
        }}
    ],
    "score": 85,
    "approved": true,
    "summary": "总体评价"
}}
```

请直接输出JSON格式的审查结果。""",

    "check_character_consistency": """请重点检查以下内容的角色一致性。

## 检查重点

1. **性格一致性**
   - 角色的言行是否与其性格设定一致
   - 面对相似情境时反应是否一致
   - 性格发展是否有合理过渡

2. **能力一致性**
   - 角色的能力水平是否前后一致
   - 新能力的出现是否有铺垫
   - 能力使用是否符合设定

3. **关系一致性**
   - 角色间关系发展是否合理
   - 情感变化是否有依据
   - 互动模式是否符合关系定位

4. **背景一致性**
   - 角色的知识/经历是否与其背景一致
   - 角色的价值观是否与其成长环境一致
   - 角色的语言习惯是否与其身份一致

## 待审查内容

{draft_content}

## 角色详细设定

{character_profiles}

## 前文角色表现

{previous_character_actions}

## 输出格式

```json
{{
    "character_issues": [
        {{
            "character": "角色名",
            "issue_type": "性格/能力/关系/背景",
            "severity": "high/medium/low",
            "description": "具体问题",
            "evidence": "文本证据",
            "suggestion": "修改建议"
        }}
    ],
    "consistency_score": 90
}}
```

请直接输出JSON格式的检查结果。""",

    "check_timeline": """请检查以下内容的时间线一致性。

## 检查重点

1. **时间顺序**
   - 事件发生的先后顺序是否正确
   - 倒叙、插叙的时间定位是否清晰
   - 时间标记（如"三天后"）是否准确

2. **时间跨度**
   - 事件持续时间是否合理
   - 不同场景间的时间间隔是否一致
   - 季节、节日等时间参照是否正确

3. **时间矛盾**
   - 是否存在时间上的逻辑矛盾
   - 角色的行程时间是否合理
   - 事件发展所需时间是否充足

4. **细节一致性**
   - 时辰（早晨/中午/夜晚）是否一致
   - 天气状况是否连贯
   - 时间相关物品（如钟表）是否一致

## 待审查内容

{draft_content}

## 前文时间线

{previous_timeline}

## 已确定的时间节点

{established_timepoints}

## 输出格式

```json
{{
    "timeline_issues": [
        {{
            "type": "顺序/跨度/矛盾/细节",
            "severity": "high/medium/low",
            "description": "问题描述",
            "location": "位置",
            "suggestion": "修改建议"
        }}
    ],
    "timeline_score": 95
}}
```

请直接输出JSON格式的检查结果。""",

    "check_character_state": """请重点检查以下内容的人物状态一致性。

## 检查重点

1. **位置一致性**
   - 人物当前位置是否与前文记录一致
   - 如果位置变化，是否有过渡描述
   - 人物移动是否在合理时间内完成

2. **身份/官职一致性**
   - 人物身份是否与前文设定一致
   - 身份变化是否有合理的剧情支持
   - 职位升降是否有正式过程

3. **关系一致性**
   - 人物间关系是否与前文记录一致
   - 关系变化是否有情感铺垫
   - 新关系建立是否符合人物性格

4. **状态演变合理性**
   - 人物行为是否符合其当前状态
   - 心理变化是否有逻辑依据
   - 技能/能力变化是否有解释

5. **新人物检查**
   - 新人物是否与已有设定冲突
   - 新人物特征是否自洽
   - 新人物与现有人物关系是否合理

## 待审查内容

{draft_content}

## 当前章节

第{chapter_num}章：{chapter_title}

## 人物状态快照

{character_state_snapshot}

## 人物状态演变历史

{character_state_evolution}

## 人物关系摘要

{relationship_summary}

## 输出格式

```json
{{
    "state_issues": [
        {{
            "character": "人物名",
            "issue_type": "位置/身份/关系/状态/新人物",
            "severity": "high/medium/low",
            "description": "具体问题描述",
            "evidence": "文本证据",
            "suggestion": "修改建议"
        }}
    ],
    "state_updates": [
        {{
            "character": "人物名",
            "updates": {{
                "location": "新位置",
                "identity": "新身份",
                "status_change": "本章状态变化",
                "new_relationships": {{"其他人物": "关系"}}
            }}
        }}
    ],
    "new_characters_detected": [
        {{
            "name": "新人物名",
            "identity": "身份",
            "initial_location": "位置",
            "attributes": {{"性格": "...", "背景": "..."}}
        }}
    ],
    "consistency_score": 90
}}
```

请直接输出JSON格式的检查结果。""",

    "check_logic_with_state": CHARACTER_STATE_PROMPTS["novel_editor_user"],

    "check_logic_novel": CHARACTER_STATE_PROMPTS["novel_editor_user"],

    "check_logic_script": CHARACTER_STATE_PROMPTS["script_editor_user"]
}


def get_editor_prompts(content_type: str = "novel") -> dict:
    """获取编辑提示词

    Args:
        content_type: 内容类型，"novel" 或 "script"

    Returns:
        包含系统提示词和用户提示词的字典
    """
    return {
        "system": get_editor_system_prompt(content_type),
        "user": get_editor_user_prompt(content_type)
    }


def get_state_check_dimensions(content_type: str = "novel") -> list:
    """获取状态检查维度列表

    Args:
        content_type: 内容类型，"novel" 或 "script"/"series_script"/"movie_script"

    Returns:
        状态检查维度列表
    """
    # 判断是否为剧本类型（包括剧集和电影）
    if content_type in ("script", "series_script", "movie_script"):
        return SCRIPT_STATE_DIMENSIONS
    return NOVEL_STATE_DIMENSIONS
