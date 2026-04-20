"""
质量分析提示词库

精心设计的提示词模板,用于LLM深度分析
优化策略:
- 精准输入: 仅传入必要信息
- 结构化输出: JSON格式
- 明确任务: 单一职责

@date: 2026-04-12
@version: v3.1.0
@author: 周金磊
"""

QUALITY_PROMPTS = {
    # ==================== 宏观结构层 ====================

    "pacing_analysis": """分析以下章节的情节节奏和冲突强度。

章节数据:
{chapters}

评估要求:
1. 为每章打分(1-10分),基于:
   - 事件转折次数
   - 冲突强度变化
   - 剧情推进速度

2. 识别低冲突区间(连续3章以上<5分)

输出格式(JSON):
{{
  "chapter_scores": {{
    "1": {{"score": 7, "reason": "有打斗和反转"}},
    "2": {{"score": 4, "reason": "纯对话过渡"}}
  }},
  "low_conflict_ranges": [
    {{"start_chapter": 5, "end_chapter": 8, "avg_score": 3.5}}
  ]
}}""",

    "foreshadowing_tracking": """分析以下伏笔的回收情况。

全文摘要(前3000字):
{summary}

已识别伏笔:
{foreshadows}

评估要求:
1. 追踪每个伏笔是否在后续被提及或回收
2. 计算伏笔-揭晓时间差(章节数)
3. 标记超过50章未回收的高风险伏笔

输出格式(JSON):
{{
  "foreshadows": [
    {{
      "id": "V001",
      "chapter_buried": 3,
      "description": "阁楼上的旧木匣",
      "last_mentioned_chapter": 15,
      "status": "unresolved",
      "risk_level": "high",
      "suggestion": "已过40章未提及,建议安排打开或丢失"
    }}
  ]
}}""",

    "volume_ending_analysis": """分析卷末章节的情绪张力和钩子强度。

卷末三章内容摘要:
{volume_endings}

评估要求:
1. 分析情绪词云(绝望/希望/愤怒/温馨/平淡占比)
2. 评估戏剧张力(是否有足够钩子让读者继续阅读)
3. 识别平淡结尾风险

输出格式(JSON):
{{
  "emotion_distribution": {{
    "tension": 0.15,
    "hope": 0.25,
    "despair": 0.10,
    "calm": 0.50
  }},
  "hook_strength": "weak",
  "score": 45,
  "suggestion": "作为分卷点缺乏钩子,建议在最后一段增加悬念"
}}""",

    # ==================== 人物塑造层 ====================

    "character_consistency": """分析角色行为是否与设定一致。

角色设定:
{profile}

角色行为记录(最近20次出场):
{actions}

评估要求:
1. 对比行为与核心欲望/性格设定
2. 识别偏离行为(允许成长,但需有触发事件)
3. 检查前文是否有转变的激励事件

输出格式(JSON):
{{
  "consistency_score": 85,
  "deviations": [
    {{
      "chapter": 42,
      "behavior": "主动深入虎穴",
      "conflict_with": "惜命、利己的初始设定",
      "has_motivation_event": false,
      "severity": "warning",
      "suggestion": "补充内心戏或修改为被迫无奈"
    }}
  ]
}}""",

    "dialogue_fingerprint": """分析角色台词指纹,识别OOC风险。

角色对话样本:
{dialogues}

评估要求:
1. 统计平均句长、高频词、语气词
2. 与角色人设对比(高冷/话痨/文雅等)
3. 识别突兀的台词风格变化

输出格式(JSON):
{{
  "dialogue_profile": {{
    "avg_sentence_length": 5.2,
    "top_words": ["嗯", "走", "好"],
    "tone_particles": ["嗯", "呵"],
    "formality_level": "high"
  }},
  "out_of_character_moments": [
    {{
      "chapter": 88,
      "dialogue": "哎哟喂,这可咋办啊",
      "reason": "使用了话痨角色的口头禅",
      "severity": "warning"
    }}
  ]
}}""",

    # ==================== 场景与感官层 ====================

    "sensory_balance_enhancement": """分析场景描写的感官平衡。

章节内容(节选):
{text_excerpt}

已知感官统计:
{sensory_stats}

评估要求:
1. 基于已有统计,分析缺失的感官维度
2. 结合场景类型(森林/城市/室内)给出具体建议
3. 提供2-3个可插入的感官描写示例

输出格式(JSON):
{{
  "missing_senses": ["嗅觉", "触觉"],
  "suggestions": [
    {{
      "sense": "嗅觉",
      "location": "第2段森林描写后",
      "example": "空气中弥漫着草木腐烂的潮湿气味"
    }}
  ]
}}""",

    "action_logic_check": """分析动作场面的力学逻辑。

动作场景:
{scenes}

评估要求:
1. 检查动作词共现是否存在逻辑矛盾
2. 识别人体力学不合理之处
3. 提供修正建议

输出格式(JSON):
{{
  "logic_issues": [
    {{
      "segment": "他站在原地,猛地翻身跃起",
      "contradiction": "站与翻身跃起存在动作衔接漏洞",
      "suggestion": "改为'他沉膝拧腰,猛地翻身跃起'",
      "severity": "warning"
    }}
  ]
}}""",

    # ==================== 文笔与修辞层 ====================

    "cliche_detection": """检测陈词滥调和抽象描写。

描写段落:
{descriptive_passages}

评估要求:
1. 识别抽象形容词(倾国倾城、英俊潇洒等)
2. 匹配网文俗套词库
3. 提供具体化改写示例

输出格式(JSON):
{{
  "cliches": [
    {{
      "original": "她长着倾国倾城的脸蛋",
      "issue": "抽象形容词,无画面感",
      "suggestion": "她的五官组合出一种危险的锋利感,让人想起话本里那些祸国的妖妃",
      "severity": "warning"
    }}
  ]
}}""",

    # ==================== 阅读体验层 ====================

    "chapter_hooks": """分析章末悬念强度。

章末段落(每章最后200字):
{endings}

评估要求:
1. 为每章结尾评分(A-F级)
   - A: 强烈悬念/危机揭示
   - B: 中等悬念/情感高潮
   - C: 平稳过渡
   - D: 平淡收尾
   - F: 完全无钩子

2. 提供优化方案

输出格式(JSON):
{{
  "hook_ratings": {{
    "33": {{
      "grade": "D",
      "ending_text": "他们走进了房间。",
      "score": 30,
      "suggestion": "他们走进了房间,却不知道桌上那封信的封蜡,刚刚被人动过。"
    }}
  }}
}}""",

    "highlight_extraction": """提取金句和爽点。

章节内容:
{chapter_content}

评估要求:
1. 识别高情绪值语句(燃点/泪点/哲理/深情)
2. 预测读者可能划线的段落
3. 评估爽点密度(每章建议2-3个)

输出格式(JSON):
{{
  "highlights": [
    {{
      "text": "跪下的是我的膝盖,碎的是你的道心。",
      "type": "燃点",
      "emotion_intensity": 9,
      "paragraph_number": 45
    }}
  ],
  "highlight_density": 2,
  "suggestion": "第89段可增加主角内心独白强化爽感"
}}""",

    # ==================== 技术性排雷层 ====================

    "anachronism_check": """检测时代/道具穿帮。

文本内容:
{text}

时代背景:
{era_setting}

违和词库:
{anachronism_keywords}

评估要求:
1. 匹配违和词
2. 识别超前道具/用语
3. 提供时代化替换建议

输出格式(JSON):
{{
  "anachronisms": [
    {{
      "text": "她给他发了个微信",
      "era": "1998年",
      "issue": "道具超前",
      "suggestion": "改为'她用传呼机给他留了条言'",
      "severity": "critical"
    }}
  ]
}}""",

    "pov_violation_deep": """深度检测视角越界。

叙事人称: {narrative_perspective}

文本内容:
{text}

评估要求:
1. 第一人称中检测第三人称心理描写
2. 第三人称有限视角中检测全知视角泄漏
3. 提供修正方案

输出格式(JSON):
{{
  "violations": [
    {{
      "text": "我蹲在墙角,完全不知道他在想什么。他心想:这傻子肯定中计了。",
      "violation_type": "first_person_mind_reading",
      "suggestion": "删除'他心想'后的内心独白,改为通过动作暗示",
      "severity": "critical"
    }}
  ]
}}""",

    # ==================== 新增：人物状态变化检测 ====================

    "character_state_changes": """检测人物状态的各个维度变化,包括地点、身份、情感、成长轨迹等。

【当前单元内容】
{chapter_content}

【人物设定】
{character_profiles}

【前文状态记录】(最近5次出场)
{previous_states}

评估要求:
1. **地点变化**: 人物位置转换是否合理?是否有移动说明?
2. **身份变化**: 职位、地位、角色身份的转变是否有铺垫?
3. **情感状态**: 情绪转换是否自然?是否有触发事件?
4. **成长轨迹**: 能力、认知、性格的成长是否符合逻辑?
5. **健康状况**: 受伤、康复、疲劳等状态是否连续?
6. **关系状态**: 与其他人物关系的转变是否合理?

输出格式(JSON):
{{
  "state_changes": [
    {{
      "character_name": "人物名",
      "state_dimension": "地点|身份|情感|成长|健康|关系",
      "previous_state": "之前状态",
      "current_state": "当前状态",
      "has_transition": true/false,
      "transition_natural": true/false,
      "severity": "critical|warning|info",
      "description": "详细描述状态变化及问题",
      "suggestion": "修正建议"
    }}
  ]
}}""",

    # ==================== 新增：世界观一致性检测 ====================

    "worldview_consistency": """检测正文内容与设定的世界观、规则、背景等是否保持一致。

【当前单元内容】
{chapter_content}

【世界观设定】
{worldview_settings}

【已建立的世界观规则】
{established_rules}

评估要求:
1. **物理法则**: 是否符合世界观中的物理规则?(如魔法系统、科技水平)
2. **社会制度**: 是否符合设定的社会结构、阶级、法律?
3. **文化习俗**: 是否符合设定的文化传统、礼仪、禁忌?
4. **经济体系**: 货币、交易、资源分配是否合理?
5. **力量体系**: 修炼等级、能力限制、代价是否一致?
6. **历史背景**: 是否与既定的历史事件、时间线冲突?
7. **地理环境**: 地形、气候、距离是否合理?
8. **生物设定**: 种族特性、寿命、能力是否符合设定?

输出格式(JSON):
{{
  "consistency_issues": [
    {{
      "rule_category": "物理法则|社会制度|文化习俗|经济体系|力量体系|历史背景|地理环境|生物设定",
      "rule_description": "违反的规则描述",
      "text_evidence": "原文引用",
      "conflict_description": "冲突说明",
      "severity": "critical|warning|info",
      "suggestion": "修正建议"
    }}
  ]
}}""",

    # ==================== 新增：时间线一致性检测 ====================

    "timeline_consistency": """检测故事情节的时间线是否连贯,事件发生的先后顺序是否合理。

【当前单元内容】
{chapter_content}

【完整时间线记录】
{timeline_records}

【全局大纲时间线】
{outline_timeline}

评估要求:
1. **时间顺序**: 事件发生的先后顺序是否合理?是否有时间倒流?
2. **时间跨度**: 两个事件之间的时间间隔是否合理?
3. **季节/天气**: 季节变化、天气描述是否连贯?
4. **年龄/成长**: 人物年龄增长、技能提升的时间是否合理?
5. **事件持续时间**: 长期事件(战争、旅行、修炼)的时间跨度是否一致?
6. **时间标记**: 明确的时间标记(如"三天后"、"次年春天")是否前后矛盾?
7. **并行事件**: 同时发生的不同事件线是否有时间冲突?
8. **历史事件**: 回忆、 flashback中的时间线是否与主线一致?

输出格式(JSON):
{{
  "timeline_issues": [
    {{
      "issue_type": "时间顺序|时间跨度|季节天气|年龄成长|事件持续|时间标记|并行事件|历史事件",
      "chapter_number": 单元号,
      "time_reference": "时间引用",
      "conflict_description": "冲突描述",
      "previous_timeline": "之前的时间线",
      "current_timeline": "当前的时间线",
      "severity": "critical|warning|info",
      "suggestion": "修正建议"
    }}
  ]
}}"""
}


def get_prompt(prompt_name: str, **kwargs) -> str:
    """
    获取提示词并填充变量

    Args:
        prompt_name: 提示词名称
        **kwargs: 变量键值对

    Returns:
        填充后的提示词
    """
    if prompt_name not in QUALITY_PROMPTS:
        raise ValueError(f"提示词不存在: {prompt_name}")

    template = QUALITY_PROMPTS[prompt_name]
    return template.format(**kwargs)
