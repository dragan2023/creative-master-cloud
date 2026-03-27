"""
提示词模板定义
包含小说和剧本生成的各类提示词
"""
import json
from typing import Dict, Any, Optional


# ==================== 小说章节生成提示词 ====================

NOVEL_CHAPTER_PROMPT = """【创作身份】
你是一位专业小说作家，专注于正文创作。你的核心任务是依据大纲摘要和前文，生成高质量的章节正文。

【项目大纲信息】
{outline_metadata}

【当前章节详细大纲】（必须严格遵循的剧情要点）
{chapter_detailed_outline}

【当前章节概要】（来自基础大纲的章节概述，如有）
{current_unit_outline}

【前序内容摘要】（用于保持剧情连贯性）
{previous_content_summaries}

【前序章节大纲摘要】
{previous_outline_summaries}

【前文参考】
前文摘要: {global_summary}
角色状态: {character_state}
当前章节摘要: {short_summary}

【知识库参考】
{knowledge_context}

【历史章节检索】
{vector_context}

【当前章节元数据】
第{chapter_number}章《{chapter_title}》：
├── 章节定位：{chapter_role}
├── 核心作用：{chapter_purpose}
├── 悬念密度：{suspense_level}
├── 伏笔设计：{foreshadowing}
├── 转折程度：{plot_twist_level}
├── 章节简述：{chapter_summary}

【投放平台】{target_platform}

🎯 创作核心原则：
1. **剧情连贯性**：参考【前序内容摘要】和【前序章节大纲摘要】，确保与前文剧情连贯
2. **设定一致性**：人物性格、世界观设定必须与已生成内容保持一致
3. **大纲遵循**：严格遵循【当前章节详细大纲】中的剧情要点和关键事件

🎯 正文创作规则：
1. 内容分级应用：
   - 写作技法类（优先）：场景构建模板/对话技巧
   - 设定资料类（选择性）：世界观元素/技术细节
   - 禁忌项类（必须规避）：已出现的情节/重复的关系发展

2. 原创性保障：
   ● 禁止直接复制已有章节的情节模式
   ● 历史章节内容仅允许：
     → 参照叙事节奏（不超过20%相似度）
     → 延续人物反应模式（需改编30%以上）

3. 冲突检测：
   ⚠️ 相似度>40%：必须重构叙事角度
      相似度20-40%：替换至少3个关键要素
      相似度<20%：允许保留概念但改变表现形式

【生成要求】
══════════════════════════════════════════════════════════════
🚨 【字数硬性约束】目标：{words_per_chapter}字，允许范围：{words_per_chapter}字的90%-110%
⚠️ 你必须精确控制输出字数！字数过多或过少都会影响作品质量！
⚠️ 不要在文章中出现字数统计，只输出正文内容。
══════════════════════════════════════════════════════════════
【字数分配建议】
- 开篇引入（约15%）：快速切入场景，建立氛围
- 核心发展（约40%）：详细展开剧情，人物互动  
- 高潮部分（约30%）：冲突爆发，情感递进
- 收尾铺垫（约15%）：悬念设置，过渡衔接
- 风格基调：{tone}
- 叙事视角：{narrative_perspective}
- 投放平台：{target_platform}

请直接开始创作第{chapter_number}章正文内容，不要输出任何前言或解释。
内容生成严格遵循：
- 当前章节详细大纲中的核心情节和关键事件
- 章节元数据中的定位和作用
- 与前文摘要、前章结尾段衔接流畅
- 避免逻辑漏洞，保持叙事连贯
"""


# ==================== 剧集剧本场景生成提示词 ====================

SERIES_SCRIPT_SCENE_PROMPT = """【创作身份】
你是一位专业编剧，专注于剧本正文创作。你的核心任务是依据大纲摘要和分集信息，生成高质量的剧本正文。

【项目大纲信息】
{outline_metadata}

【当前分集大纲】
{episode_outline}

【前序集数大纲摘要】
{previous_episodes_summary}

【前序正文摘要】（用于保持剧情连贯性）
{previous_content_summaries}

【当前场景大纲】
{current_unit_outline}

【剧集信息】
剧集类型：{series_type}
剧本格式：{format_standard}
对白比例：{dialogue_narration_ratio}
投放平台：{target_broadcast}

【场景信息】
场景编号：第{episode_number}集 第{scene_number}场
地点：{location}（{interior_exterior}景）
时间：{time_of_day}
在场角色：{characters_present}

【本场任务】
{scene_purpose}

🎯 分集连续性规则：
1. 必须严格遵循【当前分集大纲】中的本集剧情走向
2. 当前场景必须落实【当前场景大纲】中的情节要点
3. **关键：参考【前序正文摘要】和【前序集数大纲摘要】，确保与前面集数的剧情连贯、人物状态一致、伏笔呼应**
4. 注意与本集前场戏的逻辑衔接和情绪延续
5. 为后续场景埋设必要的伏笔

【格式要求】
剧本格式标准：{format_standard}
1. 场景头格式：
   第{scene_number}场 {location}·{time_of_day}·{interior_exterior}
   
2. 角色对话格式：
   角色名
   （动作/情绪提示）
   台词内容
   
3. 动作描述用"△"符号开头

【对白与叙述比例】
当前设置：{dialogue_narration_ratio}
- 如为"对话为主"：侧重角色对话，动作描述简洁
- 如为"均衡"：对白与动作描述各占约50%
- 如为"叙述为主"：侧重场景描述和氛围营造
- 如为"动作导向"：以动作描述为主，对白精简

【前场衔接】
{previous_scene_ending}

【角色状态】
{character_states}

【知识库参考】
{knowledge_context}

【生成要求】
- 预计时长：约{duration_minutes}分钟
- 对话风格：{dialogue_style}
- 叙事节奏：{narrative_rhythm}

请直接开始创作本场剧本内容，不要输出任何前言或解释。
"""


# ==================== 剧集单集正文生成提示词（新版：一集完整正文） ====================

SERIES_SCRIPT_EPISODE_PROMPT = """【创作身份】
你是一位专业编剧，专注于剧本正文创作。你的核心任务是依据分集详细大纲，生成完整的单集剧本正文。

【项目大纲信息】
{outline_metadata}

【当前分集详细大纲】
{episode_outline}

【前序集数大纲摘要】
{previous_episodes_summary}

【前序正文摘要】（用于保持剧情连贯性）
{previous_content_summaries}

【全局故事摘要】
{global_summary}

【前集结尾衔接】
{previous_scene_ending}

【剧集信息】
剧集类型：{series_type}
剧本格式：{format_standard}
对白比例：{dialogue_narration_ratio}
投放平台：{target_broadcast}

【本集信息】
第{episode_number}集《{episode_title}》
核心冲突：{core_conflict}
情感曲线：{emotional_curve}
预计时长：{estimated_duration}分钟

【场景规划】
{scenes_info}

🎯 创作规则：
1. 必须严格遵循【当前分集详细大纲】中的剧情走向
2. 按照【场景规划】中的场号顺序逐场创作
3. **关键：参考【前序正文摘要】和【前序集数大纲摘要】，确保与前面集数的剧情连贯、人物状态一致、伏笔呼应**
4. 参考【全局故事摘要】和【前集结尾衔接】，保持故事整体连贯性
5. 每场戏之间要有明确的场景转换标记

【剧本格式要求】
剧本格式标准：{format_standard}

**每场戏的标准格式：**
```
第X场 内/外景 地点 时间

△ 动作描述...

角色名
（动作/情绪提示）
台词内容

角色名B
（动作）
台词内容

△ 转场提示（如需要）
```

**格式要点：**
1. 场景头格式："第X场 内/外景 地点 时间"
2. 内景用"内景"，外景用"外景"
3. 时间用"日""夜""晨""昏"等
4. 角色对话格式：角色名单独一行，台词内容另起行
5. 动作描述用"△"符号开头
6. 场景之间用空行分隔

【对白与叙述比例】
当前设置：{dialogue_narration_ratio}
- 如为"对话为主"：侧重角色对话，动作描述简洁
- 如为"均衡"：对白与动作描述各占约50%
- 如为"叙述为主"：侧重场景描述和氛围营造
- 如为"动作导向"：以动作描述为主，对白精简

【关键对话参考】
{key_dialogues}

【角色状态】
{character_states}

【知识库参考】
{knowledge_context}

【相关内容参考】
{vector_context}

【生成要求】
- 预计时长：约{estimated_duration}分钟
- 对话风格：{dialogue_style}
- 叙事节奏：{narrative_rhythm}
══════════════════════════════════════════════════════════════
🚨 【字数硬性约束】目标：{words_per_episode}字，允许范围：{words_per_episode}字的90%-110%
⚠️ 你必须精确控制输出字数！字数过多或过少都会影响作品质量！
⚠️ 不要在文章中出现字数统计，只输出正文内容。
══════════════════════════════════════════════════════════════
【字数分配建议】
- 按场景规划合理分配篇幅
- 每场戏的篇幅应与预计时长成正比
- 重要场景（高潮、转折）可适当增加篇幅
- 过渡场景保持简洁，避免冗余

请直接开始创作第{episode_number}集的完整剧本正文，按照场景顺序逐场输出，不要输出任何前言或解释。
"""


# ==================== 电影剧本场景生成提示词 ====================

MOVIE_SCRIPT_SCENE_PROMPT = """【创作身份】
你是一位专业电影编剧，专注于电影剧本正文创作。你的核心任务是依据大纲和分场信息，生成高质量的电影剧本正文。

【故事大纲】
{outline_content}

【当前场景大纲】
{current_unit_outline}

【全局故事摘要】
{global_summary}

【前场结尾衔接】
{previous_scene_ending}

【前序场景大纲摘要】
{previous_scenes_summary}

【电影信息】
电影类型：{movie_type}
电影总时长：{total_duration}分钟
剧本格式：{format_standard}
对白比例：{dialogue_narration_ratio}
投放平台：{target_platform}

【场景信息】
场景编号：第{scene_number}场
地点：{location}（{interior_exterior}景）
时间：{time_of_day}
在场角色：{characters_present}

【本场任务】
{scene_purpose}

🎯 大纲遵循规则：
1. 必须严格遵循【故事大纲】中的核心情节和人物设定
2. 当前场景必须落实【当前场景大纲】中的剧情要点
3. 参考【全局故事摘要】和【前场结尾衔接】，保持故事整体连贯性
4. 保持电影叙事的紧凑性和视觉冲击力
5. 注意场景之间的逻辑衔接和节奏控制

【电影剧本格式要求】
剧本格式标准：{format_standard}
1. 场景头格式：
   第{scene_number}场 {location}·{time_of_day}·{interior_exterior}
   
2. 角色对话格式：
   角色名
   （动作/情绪提示）
   台词内容
   
3. 动作描述用"△"符号开头

【电影叙事特点】
- 电影剧本注重视觉叙事，多用动作和画面表达
- 每场戏要有明确的视觉目的和情绪传递
- 对白精炼有力，避免冗长
- 注意场景转换的流畅性

【对白与叙述比例】
当前设置：{dialogue_narration_ratio}
- 如为"对话为主"：侧重角色对话，动作描述简洁
- 如为"均衡"：对白与动作描述各占约50%
- 如为"叙述为主"：侧重场景描述和氛围营造
- 如为"动作导向"：以动作描述为主，对白精简

【角色状态】
{character_states}

【知识库参考】
{knowledge_context}

【相关内容参考】
{vector_context}

【生成要求】
- 预计时长：约{duration_minutes}分钟
- 对话风格：{dialogue_style}
- 叙事节奏：{narrative_rhythm}
══════════════════════════════════════════════════════════════
🚨 【字数硬性约束】目标：{estimated_words}字（按每分钟约250字计算），允许范围：90%-110%
⚠️ 你必须精确控制输出字数！字数过多或过少都会影响作品质量！
⚠️ 不要在文章中出现字数统计，只输出正文内容。
══════════════════════════════════════════════════════════════
【篇幅控制建议】
- 按预计时长合理分配内容
- 动作描述简洁有力，注重视觉表达
- 对白精炼，避免冗长对话
- 确保本场戏内容完整，有明确的开始和结束

请直接开始创作本场电影剧本内容，不要输出任何前言或解释。
"""


# ==================== 剧集剧本虚拟模式提示词（AI视频生成优化） ====================

SERIES_SCRIPT_VIRTUAL_PROMPT = """【创作身份】
你是一位专业编剧，专注于为AI视频生成平台创作剧本。你的核心任务是依据大纲和分集信息，生成适合AI视频生成的简洁剧本正文。

🔴 【核心定位】虚拟模式 - 专为AI视频生成优化
→ 适用场景：全AI生成流程（Seedance/Sora/Veo等平台）
→ 输出格式：简洁分镜剧情描述
→ 核心原则：视觉可生成性优先，减少复杂拍摄技法

【故事大纲】
{outline_content}

【当前分集大纲】
{episode_outline}

【前序集数大纲摘要】
{previous_episodes_summary}

【全局故事摘要】
{global_summary}

【前集结尾衔接】
{previous_scene_ending}

【当前场景大纲】
{current_unit_outline}

【剧集信息】
剧集类型：{series_type}
剧本格式：{format_standard}
对白比例：{dialogue_narration_ratio}
投放平台：{target_broadcast}

【场景信息】
场景编号：第{episode_number}集 第{scene_number}场
地点：{location}（{interior_exterior}景）
时间：{time_of_day}
在场角色：{characters_present}

【本场任务】
{scene_purpose}

🎯 虚拟模式核心规则：
1. **简化分镜结构**：每场戏用简洁的"一句话剧情+景别+效果"格式
2. **视觉描述优先**：描述画面内容，而非拍摄技法（不用"推拉摇移"等术语）
3. **AI可生成性**：场景描述要具体、可视觉化，便于AI理解生成
4. **减少运镜描述**：省略复杂的运镜、转场指令，让AI自动处理
5. **对白精简**：对话简洁有力，避免过长独白
6. 参考【全局故事摘要】和【前集结尾衔接】，保持故事整体连贯性

【虚拟模式格式要求】
每场戏的标准格式：

```
【第X场】地点·时间·内/外景

画面：一句话描述场景画面（AI生成依据）
角色：在场角色列表
剧情：本场核心剧情（2-3句话）

角色A
台词内容

角色B
台词内容

效果：本场视觉/情绪效果
```

【对白与叙述比例】
当前设置：{dialogue_narration_ratio}
- 如为"对话为主"：侧重角色对话，画面描述简洁
- 如为"均衡"：对白与画面描述各占约50%
- 如为"叙述为主"：侧重场景描述和氛围营造

【关键对话参考】
{key_dialogues}

【角色状态】
{character_states}

【知识库参考】
{knowledge_context}

【相关内容参考】
{vector_context}

【生成要求】
- 预计时长：约{estimated_duration}分钟
- 对话风格：{dialogue_style}
- 叙事节奏：{narrative_rhythm}
══════════════════════════════════════════════════════════════
🚨 【字数硬性约束】目标：{words_per_episode}字，允许范围：{words_per_episode}字的90%-110%
⚠️ 你必须精确控制输出字数！字数过多或过少都会影响作品质量！
⚠️ 不要在文章中出现字数统计，只输出正文内容。
══════════════════════════════════════════════════════════════

请直接开始创作第{episode_number}集的完整剧本正文（虚拟模式），按照场景顺序逐场输出，不要输出任何前言或解释。
"""


# ==================== 电影剧本虚拟模式提示词（AI视频生成优化） ====================

MOVIE_SCRIPT_VIRTUAL_PROMPT = """【创作身份】
你是一位专业电影编剧，专注于为AI视频生成平台创作剧本。你的核心任务是依据大纲和分场信息，生成适合AI视频生成的简洁电影剧本正文。

🔴 【核心定位】虚拟模式 - 专为AI视频生成优化
→ 适用场景：全AI生成流程（Seedance/Sora/Veo等平台）
→ 输出格式：简洁分镜剧情描述
→ 核心原则：视觉可生成性优先，减少复杂拍摄技法

【故事大纲】
{outline_content}

【当前场景大纲】
{current_unit_outline}

【全局故事摘要】
{global_summary}

【前场结尾衔接】
{previous_scene_ending}

【前序场景大纲摘要】
{previous_scenes_summary}

【电影信息】
电影类型：{movie_type}
电影总时长：{total_duration}分钟
剧本格式：{format_standard}
对白比例：{dialogue_narration_ratio}
投放平台：{target_platform}

【场景信息】
场景编号：第{scene_number}场
地点：{location}（{interior_exterior}景）
时间：{time_of_day}
在场角色：{characters_present}

【本场任务】
{scene_purpose}

🎯 虚拟模式核心规则：
1. **简化分镜结构**：每场戏用简洁的"一句话剧情+景别+效果"格式
2. **视觉描述优先**：描述画面内容，而非拍摄技法（不用"推拉摇移"等术语）
3. **AI可生成性**：场景描述要具体、可视觉化，便于AI理解生成
4. **减少运镜描述**：省略复杂的运镜、转场指令，让AI自动处理
5. **电影感保留**：虽然简化技法，但保持电影叙事的紧凑性和视觉冲击力
6. 参考【全局故事摘要】和【前场结尾衔接】，保持故事整体连贯性

【虚拟模式格式要求】
每场戏的标准格式：

```
【第X场】地点·时间·内/外景

画面：一句话描述场景画面（AI生成依据）
角色：在场角色列表
剧情：本场核心剧情（2-3句话）

角色A
台词内容

角色B
台词内容

效果：本场视觉/情绪效果
```

【电影叙事特点（虚拟模式）】
- 注重视觉叙事，用画面和动作表达
- 每场戏要有明确的视觉目的和情绪传递
- 对白精炼有力，避免冗长
- 场景描述具体可视觉化

【对白与叙述比例】
当前设置：{dialogue_narration_ratio}
- 如为"对话为主"：侧重角色对话，画面描述简洁
- 如为"均衡"：对白与画面描述各占约50%
- 如为"叙述为主"：侧重场景描述和氛围营造

【角色状态】
{character_states}

【知识库参考】
{knowledge_context}

【相关内容参考】
{vector_context}

【生成要求】
- 预计时长：约{duration_minutes}分钟
- 对话风格：{dialogue_style}
- 叙事节奏：{narrative_rhythm}
══════════════════════════════════════════════════════════════
🚨 【字数硬性约束】目标：{estimated_words}字（按每分钟约250字计算），允许范围：90%-110%
⚠️ 你必须精确控制输出字数！字数过多或过少都会影响作品质量！
⚠️ 不要在文章中出现字数统计，只输出正文内容。
══════════════════════════════════════════════════════════════

请直接开始创作本场电影剧本内容（虚拟模式），不要输出任何前言或解释。
"""


# ==================== 兼容旧版剧本场景生成提示词 ====================

SCRIPT_SCENE_PROMPT = SERIES_SCRIPT_SCENE_PROMPT


# ==================== 章节目录生成提示词 ====================

DIRECTORY_GENERATE_PROMPT = """你是一位专业{project_type}作家，请根据以下大纲生成分章目录。

【项目信息】
类型：{project_type}
总章节数：{total_chapters}
题材：{genre}
目标平台：{target_platform}

【故事大纲】
{outline_content}

【输出格式】
每章包含以下信息，用JSON数组格式输出：

```json
[
  {{
    "chapter_number": 1,
    "chapter_title": "章节标题",
    "chapter_role": "本章定位（角色/事件/主题）",
    "chapter_purpose": "核心作用（推进/转折/揭示）",
    "suspense_level": "悬念密度（紧凑/渐进/爆发）",
    "foreshadowing": "伏笔操作（埋设A线索→强化B矛盾）",
    "plot_twist_level": "认知颠覆强度（★☆☆☆☆ 到 ★★★★★）",
    "chapter_summary": "本章简述（一句话概括）"
  }}
]
```

【生成要求】
1. 章节划分要合理，每章应有明确的叙事目标
2. 悬念和转折要分布均匀，避免节奏单一
3. 伏笔设计要前后呼应，形成闭环
4. 章节标题要吸引人，体现章节核心

请生成{total_chapters}章的目录：
"""


# ==================== 章节名称预生成提示词 ====================

CHAPTER_NAMES_GENERATE_PROMPT = """你是一位专业{project_type}作家，请根据以下大纲为所有{unit_label}生成标题。

【项目信息】
类型：{project_type}
总{unit_label}数：{total_units}
题材：{genre}
目标平台：{target_platform}

【故事大纲】
{outline_content}

【输出格式】
请为每个{unit_label}生成一个吸引人的标题，用JSON数组格式输出：

```json
[
  {{"number": 1, "title": "第一章标题"}},
  {{"number": 2, "title": "第二章标题"}},
  ...
]
```

【标题命名要求】
1. 标题要能体现该{unit_label}的核心情节或主题
2. 标题要有吸引力，能引起读者兴趣
3. 标题风格要与题材和目标平台匹配
4. 标题长度控制在2-10个字
5. 避免"无题"、"未命名"等占位词

请生成{total_units}个{unit_label}的标题：
"""


# ==================== 剧集分集标题生成提示词 ====================

EPISODE_NAMES_GENERATE_PROMPT = """【重要提醒】这是剧集剧本，不是电影！输出格式必须使用"第X集"而非"第X场"！

你是一位专业编剧，请根据以下大纲为所有分集生成标题。

【项目信息】
剧集类型：{series_type}
总集数：{total_episodes}
题材：{genre}

【故事大纲】
{outline_content}

【输出格式】
请为每一集生成一个标题，用JSON数组格式输出：

```json
[
  {{"episode": 1, "title": "第一集标题", "summary": "本集梗概（50字内）"}},
  {{"episode": 2, "title": "第二集标题", "summary": "本集梗概（50字内）"}},
  ...
]
```

【分集标题要求】
1. 标题要能体现本集的核心冲突或情节
2. 标题要有戏剧张力，能引发观众期待
3. 每集梗概要简洁概括本集主要内容
4. 注意分集之间的连贯性和递进关系
5. ⚠️ 使用"第X集"格式，绝不能使用"第X场"

请生成{total_episodes}集的标题：
"""


# ==================== 剧集分集分场目录生成提示词 ====================

SCRIPT_DIRECTORY_PROMPT = """【重要提醒】这是剧集剧本，不是电影！输出格式必须使用"集"而非仅用"场"！

你是一位专业编剧，请根据以下大纲生成剧集的分集分场目录。

【剧集信息】
类型：{series_type}
总集数：{total_episodes}

【时长与场景控制】
- 每集时长：{episode_duration_range} 分钟
- 场景数设置：{scenes_per_episode_info}
- 剧本格式标准：{format_standard}
- 对白与叙述比例：{dialogue_narration_ratio}

【场景数估算参考】
如果场景数为"AI自动设计"，请根据以下规则估算：
- 电视剧（45-50分钟）：约15-25场/集
- 网络剧（30-45分钟）：约12-20场/集
- 短剧（5-15分钟）：约5-12场/集

【故事大纲】
{outline_content}

【格式标准说明】
- 标准格式：包含场景头、角色名、动作描述、对白、过渡等完整元素
- 简格式：精简场景描述，突出对白核心
- 网络平台格式：适配流媒体平台，注意节奏快、信息密度高
- 短剧格式：单场戏结构清晰，冲突集中，适合竖屏观看

【输出格式】⚠️ 注意：这是剧集，必须按"第X集"格式输出！
每集包含：
```json
{{
  "episode_number": 1,
  "episode_title": "第1集标题",
  "episode_summary": "本集梗概（200字内）",
  "estimated_duration": "预计时长（分钟）",
  "scenes": [
    {{
      "scene_number": 1,
      "location": "地点名称",
      "interior_exterior": "内/外",
      "time_of_day": "日/夜/晨/昏",
      "characters_present": ["角色1", "角色2"],
      "scene_purpose": "本场任务",
      "duration_minutes": 3
    }}
  ]
}}
```

【生成要求】
1. 根据设定的时长区间合理分配每场戏的时长
2. 场景数量要符合设定的时长比例
3. 每场戏要有明确的叙事目标
4. 注意场景之间的逻辑衔接
5. 对白密度要符合设定的"对白与叙述比例"

请生成分集分场目录（注意：使用"第X集"格式）：
"""


# ==================== 电影剧本场景目录生成提示词 ====================

MOVIE_DIRECTORY_PROMPT = """【重要提醒】这是电影剧本，不是剧集！输出格式必须使用"场"而非"集"！

你是一位专业电影编剧，请根据以下大纲生成电影场景目录。

【电影信息】
电影类型：{movie_type}
总时长：{total_duration}分钟
剧本格式：{format_standard}
对白与叙述比例：{dialogue_narration_ratio}

【时长与场景控制】
- 电影总场景数：约{total_scenes}场
- 场景数估算参考：
  - 院线电影（90-120分钟）：约80-150场
  - 微电影（30-45分钟）：约20-40场
  - 短片（10-20分钟）：约10-20场

【故事大纲】
{outline_content}

【格式标准说明】
- 标准格式：包含场景头、角色名、动作描述、对白、过渡等完整元素
- 简格式：精简场景描述，突出对白核心
- 艺术电影格式：注重视觉叙事和氛围营造

【输出格式】⚠️ 注意：这是电影，输出格式为"第X场"，绝不能出现"第X集"！
请按以下JSON格式输出场景目录：

```json
[
  {{
    "scene_number": 1,
    "scene_title": "场景标题",
    "location": "地点名称",
    "interior_exterior": "内景/外景",
    "time_of_day": "日/夜/晨/昏",
    "characters_present": ["角色1", "角色2"],
    "scene_purpose": "本场核心任务",
    "duration_minutes": 2,
    "scene_summary": "本场简要描述（50字内）"
  }},
  {{
    "scene_number": 2,
    "scene_title": "场景标题",
    "location": "地点名称",
    ...
  }}
]
```

【电影场景划分原则】
1. 每场戏要有明确的视觉目的和叙事功能
2. 场景时长要合理分配，注意整体节奏
3. 重要转折和高潮场景可以适当延长
4. 注意场景之间的逻辑衔接和情绪递进
5. 内景与外景要合理搭配
6. 时间线要清晰连贯

【电影叙事结构参考】
- 三幕式结构：
  - 第一幕（约25%）：建立世界观、人物关系、初始冲突
  - 第二幕（约50%）：冲突升级、人物发展、情节推进
  - 第三幕（约25%）：高潮、转折、结局
- 每幕内部的场景要有明确的情绪曲线

请生成电影场景目录（注意：使用"第X场"格式）：
"""


# ==================== 电影场景名称生成提示词 ====================

MOVIE_SCENE_NAMES_PROMPT = """【重要提醒】这是电影剧本，不是剧集！输出格式必须使用"场"而非"集"！

你是一位专业电影编剧，请根据以下大纲为所有场景生成标题。

【电影信息】
电影类型：{movie_type}
总场景数：{total_scenes}
总时长：{total_duration}分钟
题材：{genre}

【故事大纲】
{outline_content}

【输出格式】
请为每个场景生成一个标题，用JSON数组格式输出：

```json
[
  {{"scene_number": 1, "title": "第一场标题", "summary": "本场简要描述（30字内）"}},
  {{"scene_number": 2, "title": "第二场标题", "summary": "本场简要描述（30字内）"}},
  ...
]
```

【场景标题要求】
1. 标题要能体现本场戏的核心情节或视觉焦点
2. 标题要有画面感，适合电影叙事
3. 可以包含地点信息或关键动作
4. 标题长度控制在2-10个字
5. 避免"无题"、"未命名"等占位词
6. ⚠️ 使用"第X场"格式，绝不能使用"第X集"

请生成{total_scenes}个场景的标题：
"""


# ==================== 摘要更新提示词 ====================

SUMMARY_UPDATE_PROMPT = """根据新完成的章节，更新前文摘要。

【当前前文摘要】
{current_summary}

【新完成章节】
第{chapter_number}章《{chapter_title}》
{chapter_content}

【更新要求】
1. 保留既有重要信息，融入新剧情要点
2. 总字数控制在2000字以内
3. 突出关键事件、角色发展、伏笔线索
4. 按时间线组织，保持逻辑清晰
5. 删除已被解决的次要线索

请输出更新后的前文摘要：
"""


# ==================== 角色状态更新提示词 ====================

CHARACTER_UPDATE_PROMPT = """依据新完成的章节内容，更新角色状态表。

【当前角色状态】
{current_state}

【新完成章节】
第{chapter_number}章《{chapter_title}》
{chapter_content}

【角色状态格式】
```json
{{
  "角色名": {{
    "物品": {{
      "道具1": "描述",
      "武器": "描述"
    }},
    "能力": {{
      "技能1": "描述"
    }},
    "状态": {{
      "身体状态": "描述",
      "心理状态": "描述"
    }},
    "关系网": {{
      "角色A": "关系描述",
      "角色B": "关系描述"
    }},
    "触发事件": ["事件1", "事件2"]
  }}
}}
```

【更新要求】
1. 只更新有变化的部分，未提及的角色保持原状态
2. 新出现的角色需要添加
3. 物品/能力的变化要记录
4. 关系变化要详细说明
5. 保持JSON格式输出

请输出更新后的角色状态表（JSON格式）：
"""


# ==================== 一致性检查提示词 ====================

CONSISTENCY_CHECK_PROMPT = """请检查下面的小说设定与最新章节是否存在明显冲突。

【小说设定】
{novel_setting}

【角色状态】
{character_state}

【前文摘要】
{global_summary}

【已记录的未解决冲突】
{plot_arcs}

【最新章节内容】
第{chapter_number}章《{chapter_title}》
{chapter_content}

【检查维度】
1. 世界观设定冲突
2. 角色状态矛盾（如角色物品丢失后又出现）
3. 剧情逻辑漏洞
4. 伏笔遗漏（未解决的冲突被忽略）
5. 时间线混乱

【输出格式】
如果没有明显冲突，返回"无明显冲突"。
如果存在冲突，请按以下格式列出：

```
冲突类型: [世界观/角色/剧情/伏笔/时间线]
冲突描述: [具体说明]
涉及内容: [相关原文]
建议修改: [修改建议]
```
"""


# ==================== 知识库过滤提示词 ====================

KNOWLEDGE_FILTER_PROMPT = """对知识库内容进行三级过滤，用于章节生成。

【章节信息】
{chapter_info}

【检索到的知识库内容】
{retrieved_contexts}

【过滤任务】

1. 冲突检测：
   - 删除与已生成内容重复度＞40%的内容
   - 标记存在世界观矛盾的内容（▲前缀）

2. 价值评估：
   - 关键价值点（❗）: 新角色关系/隐喻素材/情节转折技巧
   - 次级价值点（·）: 环境细节/对话技巧

3. 结构重组：
   - 按"情节燃料/人物维度/世界碎片/叙事技法"分类
   - 添加适用场景提示

【输出要求】
输出过滤后的知识库内容，格式如下：

【情节燃料】
...

【人物维度】
...

【世界碎片】
...

【叙事技法】
...

请执行过滤：
"""


# ==================== 检索关键词生成提示词 ====================

SEARCH_KEYWORD_PROMPT = """根据章节信息生成知识库检索关键词。

【章节信息】
章节编号：第{chapter_number}章
章节标题：{chapter_title}
章节定位：{chapter_role}
核心作用：{chapter_purpose}
章节简述：{chapter_summary}

【伏笔信息】
{foreshadowing}

【输出要求】
请生成3-5个检索关键词，用于从知识库中检索相关内容。
关键词应该涵盖：
1. 场景/地点相关
2. 角色/关系相关
3. 情节/事件相关
4. 技法/风格相关

请直接输出关键词，用逗号分隔：
"""


def get_chapter_prompt(
    content_type: str,
    chapter_number: int,
    chapter_title: str,
    chapter_metadata: Dict[str, Any],
    context: Dict[str, Any],
    generation_config: Dict[str, Any],
    type_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    获取章节生成提示词

    Args:
        content_type: 内容类型 (novel/series_script/movie_script)
        chapter_number: 章节序号
        chapter_title: 章节标题
        chapter_metadata: 章节元数据
        context: 上下文信息
        generation_config: 生成配置
        type_config: 类型专用配置（可选）

    Returns:
        格式化后的提示词
    """
    if content_type == "novel":
        # 小说配置
        target_platform = ""
        words_per_chapter = 3000
        tone = "正剧"
        narrative_perspective = "第三人称"

        if type_config:
            target_platform = type_config.get("target_platform", "")
            words_per_chapter = type_config.get("words_per_chapter", 3000)
            tone = type_config.get("tone", "正剧")
            narrative_perspective = type_config.get(
                "narrative_perspective", "第三人称")

        return NOVEL_CHAPTER_PROMPT.format(
            # 大纲元信息（替代完整大纲嵌入）
            outline_metadata=context.get("outline_metadata", ""),
            # 单章详细大纲（优先使用，来自chapter_outlines数据库字段）
            chapter_detailed_outline=context.get(
                "chapter_detailed_outline", ""),
            # 基础大纲中的章节概要（向后兼容）
            current_unit_outline=context.get("current_unit_outline", ""),
            # 前序单元摘要（新增：用于保持剧情连贯性）
            previous_content_summaries=context.get(
                "previous_content_summaries", ""),
            previous_outline_summaries=context.get(
                "previous_outline_summaries", ""),
            # 上下文信息
            global_summary=context.get("global_summary", ""),
            character_state=context.get("character_state", ""),
            short_summary=context.get("short_summary", ""),
            knowledge_context=context.get("knowledge_context", ""),
            vector_context=context.get("vector_context", ""),
            # 章节信息
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_role=chapter_metadata.get("chapter_role", ""),
            chapter_purpose=chapter_metadata.get("chapter_purpose", ""),
            suspense_level=chapter_metadata.get("suspense_level", ""),
            foreshadowing=chapter_metadata.get("foreshadowing", ""),
            plot_twist_level=chapter_metadata.get("plot_twist_level", ""),
            chapter_summary=chapter_metadata.get("chapter_summary", ""),
            # 生成配置
            words_per_chapter=words_per_chapter,
            tone=tone,
            narrative_perspective=narrative_perspective,
            target_platform=target_platform
        )

    elif content_type == "series_script":
        # 剧集剧本配置
        series_type = "电视剧"
        format_standard = "标准格式"
        dialogue_narration_ratio = "均衡"
        target_broadcast = ""

        if type_config:
            series_type = type_config.get("series_type", "电视剧")
            format_standard = type_config.get("format_standard", "标准格式")
            dialogue_narration_ratio = type_config.get(
                "dialogue_narration_ratio", "均衡")
            target_broadcast = type_config.get("target_broadcast", "")

        scene_metadata = chapter_metadata.get("scene_metadata", {})

        return SERIES_SCRIPT_SCENE_PROMPT.format(
            # 大纲元信息（替代完整大纲嵌入）
            outline_metadata=context.get("outline_metadata", ""),
            episode_outline=context.get("episode_outline", ""),
            previous_episodes_summary=context.get(
                "previous_episodes_summary", ""),
            # 前序正文摘要（新增：用于保持剧情连贯性）
            previous_content_summaries=context.get(
                "previous_content_summaries", ""),
            current_unit_outline=context.get("current_unit_outline", ""),
            # 剧集信息
            series_type=series_type,
            format_standard=format_standard,
            dialogue_narration_ratio=dialogue_narration_ratio,
            target_broadcast=target_broadcast,
            # 场景信息
            episode_number=chapter_metadata.get("episode_number", 1),
            scene_number=scene_metadata.get("scene_number", chapter_number),
            location=scene_metadata.get("location", "未指定"),
            interior_exterior=scene_metadata.get("interior_exterior", "内"),
            time_of_day=scene_metadata.get("time_of_day", "日"),
            characters_present=", ".join(
                scene_metadata.get("characters_present", [])),
            scene_purpose=chapter_metadata.get("chapter_summary", ""),
            # 上下文
            previous_scene_ending=context.get("previous_scene_ending", ""),
            character_states=context.get("character_states", ""),
            knowledge_context=context.get("knowledge_context", ""),
            # 生成配置
            duration_minutes=scene_metadata.get("duration_minutes") or 3,
            dialogue_style=generation_config.get("dialogue_style", "自然对话"),
            narrative_rhythm=generation_config.get("narrative_rhythm", "紧凑")
        )

    elif content_type == "movie_script":
        # 电影剧本配置
        movie_type = "院线电影"
        total_duration = 90
        format_standard = "标准格式"
        dialogue_narration_ratio = "均衡"
        target_platform = ""

        if type_config:
            movie_type = type_config.get("movie_type", "院线电影")
            total_duration = type_config.get("total_duration", 90)
            format_standard = type_config.get("format_standard", "标准格式")
            dialogue_narration_ratio = type_config.get(
                "dialogue_narration_ratio", "均衡")
            target_platform = type_config.get("target_platform", "")

        scene_metadata = chapter_metadata.get("scene_metadata", {})

        return MOVIE_SCRIPT_SCENE_PROMPT.format(
            # 大纲内容（关键修复：确保大纲传递给LLM）
            outline_content=context.get("outline_content", ""),
            current_unit_outline=context.get("current_unit_outline", ""),
            # 电影信息
            movie_type=movie_type,
            total_duration=total_duration,
            format_standard=format_standard,
            dialogue_narration_ratio=dialogue_narration_ratio,
            target_platform=target_platform,
            # 场景信息
            scene_number=scene_metadata.get("scene_number", chapter_number),
            location=scene_metadata.get("location", "未指定"),
            interior_exterior=scene_metadata.get("interior_exterior", "内"),
            time_of_day=scene_metadata.get("time_of_day", "日"),
            characters_present=", ".join(
                scene_metadata.get("characters_present", [])),
            scene_purpose=chapter_metadata.get("chapter_summary", ""),
            # 上下文
            previous_scene_ending=context.get("previous_scene_ending", ""),
            character_states=context.get("character_states", ""),
            knowledge_context=context.get("knowledge_context", ""),
            # 生成配置
            duration_minutes=scene_metadata.get("duration_minutes") or 3,
            dialogue_style=generation_config.get("dialogue_style", "自然对话"),
            narrative_rhythm=generation_config.get("narrative_rhythm", "紧凑")
        )

    else:
        # 兼容旧版 project_type
        if content_type == "script":
            format_standard = "标准格式"
            dialogue_narration_ratio = "均衡"

            if type_config:
                format_standard = type_config.get("format_standard", "标准格式")
                dialogue_narration_ratio = type_config.get(
                    "dialogue_narration_ratio", "均衡")

            return SCRIPT_SCENE_PROMPT.format(
                # 大纲内容
                outline_content=context.get("outline_content", ""),
                episode_outline=context.get("episode_outline", ""),
                previous_episodes_summary=context.get(
                    "previous_episodes_summary", ""),
                current_unit_outline=context.get("current_unit_outline", ""),
                # 剧集信息
                series_type="电视剧",
                format_standard=format_standard,
                dialogue_narration_ratio=dialogue_narration_ratio,
                target_broadcast="",
                # 场景信息
                episode_number=1,
                scene_number=chapter_number,
                location=chapter_metadata.get(
                    "scene_metadata", {}).get("location", "未指定"),
                interior_exterior=chapter_metadata.get(
                    "scene_metadata", {}).get("interior_exterior", "内"),
                time_of_day=chapter_metadata.get(
                    "scene_metadata", {}).get("time_of_day", "日"),
                characters_present=", ".join(chapter_metadata.get(
                    "scene_metadata", {}).get("characters_present", [])),
                scene_purpose=chapter_metadata.get("chapter_summary", ""),
                # 上下文
                previous_scene_ending=context.get("previous_scene_ending", ""),
                character_states=context.get("character_states", ""),
                knowledge_context=context.get("knowledge_context", ""),
                # 生成配置
                duration_minutes=chapter_metadata.get(
                    "scene_metadata", {}).get("duration_minutes", 3),
                dialogue_style=generation_config.get("dialogue_style", "自然对话"),
                narrative_rhythm=generation_config.get(
                    "narrative_rhythm", "紧凑")
            )
        else:
            # 默认使用小说模板
            return NOVEL_CHAPTER_PROMPT.format(
                # 大纲内容
                outline_content=context.get("outline_content", ""),
                current_unit_outline=context.get("current_unit_outline", ""),
                # 上下文信息
                global_summary=context.get("global_summary", ""),
                character_state=context.get("character_state", ""),
                short_summary=context.get("short_summary", ""),
                knowledge_context=context.get("knowledge_context", ""),
                vector_context=context.get("vector_context", ""),
                # 章节信息
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_role=chapter_metadata.get("chapter_role", ""),
                chapter_purpose=chapter_metadata.get("chapter_purpose", ""),
                suspense_level=chapter_metadata.get("suspense_level", ""),
                foreshadowing=chapter_metadata.get("foreshadowing", ""),
                plot_twist_level=chapter_metadata.get("plot_twist_level", ""),
                chapter_summary=chapter_metadata.get("chapter_summary", ""),
                # 生成配置
                words_per_chapter=generation_config.get(
                    "words_per_chapter", 3000),
                tone=generation_config.get("tone", "正剧"),
                narrative_perspective=generation_config.get(
                    "narrative_perspective", "第三人称"),
                target_platform=""
            )


# ==================== 分集详细大纲生成提示词（剧集专用） ====================

EPISODE_DETAILED_OUTLINE_PROMPT = """【重要提醒】这是剧集剧本，不是电影！输出格式必须使用"集"而非仅用"场"！

【创作身份】
你是一位专业编剧，专注于分集大纲细化工作。你的核心任务是将基础大纲中的分集概要扩展为详细的分集大纲。

【基础大纲】
{outline_content}

【当前分集概要】
第{episode_number}集：{episode_title}
{episode_summary}

【剧集信息】
剧集类型：{series_type}
每集时长：{episode_duration_range} 分钟
剧本格式：{format_standard}
对白比例：{dialogue_narration_ratio}
投放平台：{target_broadcast}

【前序集数大纲摘要】
{previous_episodes_summary}

【输出要求】
请为第{episode_number}集生成详细的分集大纲，包含以下部分：

### 一、本集核心信息
- **集标题**：[保留或优化原标题]
- **核心冲突**：[本集的主要矛盾]
- **情感曲线**：[观众应该经历的情感变化]
- **预计时长**：[X]分钟（必须在{episode_duration_range}范围内）

### 二、详细剧情大纲（800-1200字）
按照以下结构详细展开本集剧情：

1. **开场（约10%）**：
   - 场景设定
   - 人物出场状态
   - 引入的问题/冲突

2. **发展（约40%）**：
   - 主要情节推进
   - 人物互动
   - 矛盾升级

3. **高潮（约30%）**：
   - 核心冲突爆发
   - 关键转折
   - 情感顶点

4. **收尾（约20%）**：
   - 问题阶段性解决或深化
   - 悬念埋设
   - 下集预告感

### 三、场景规划表
| 场号 | 地点 | 内/外 | 时间 | 核心内容 | 主要人物 | 预计时长 |
|------|------|-------|------|----------|----------|----------|
| {episode_number}-1 | [地点] | 内/外 | 日/夜 | [本场核心内容] | [人物] | [X]分钟 |
| {episode_number}-2 | [地点] | 内/外 | 日/夜 | [本场核心内容] | [人物] | [X]分钟 |
| ... | ... | ... | ... | ... | ... | ... |

**场景数估算参考**：
- 短剧（5-15分钟）：5-12场
- 网络剧（30-45分钟）：12-20场
- 长剧（45-50分钟）：15-25场

### 四、关键对话设计（3-5句核心台词）
列出本集最关键的几句台词，用于塑造人物和推动剧情。

### 五、视觉亮点
- **关键场景设计**：[需要特别设计的视觉场景]
- **转场建议**：[场景之间的衔接方式]

【创作原则】
1. 严格遵循基础大纲的人物设定和世界观
2. 与前序集数保持连贯性
3. 注意与前序集数的剧情衔接
4. 场景规划要符合时长约束
5. 确保每场戏都有明确的叙事目的
6. ⚠️ 这是剧集，使用"第X集"格式，不是电影

请直接输出详细分集大纲，不要添加额外的前言或解释。
"""


def get_episode_prompt(
    episode_number: int,
    episode_title: str,
    episode_outline: Dict[str, Any],
    context: Dict[str, Any],
    type_config: Optional[Dict[str, Any]] = None,
    generation_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    获取连续剧单集正文生成提示词（新版：一集完整正文）

    Args:
        episode_number: 集数
        episode_title: 集标题
        episode_outline: 单集详细大纲（从 episode_outlines 获取）
        context: 上下文信息
        type_config: 类型专用配置
        generation_config: 生成配置

    Returns:
        格式化后的提示词
    """
    generation_config = generation_config or {}

    # 剧集配置
    series_type = "电视剧"
    format_standard = "标准格式"
    dialogue_narration_ratio = "均衡"
    target_broadcast = ""
    words_per_episode = 5000  # 单集字数默认5000
    script_mode = "real"  # 默认现实模式

    if type_config:
        series_type = type_config.get("series_type", "电视剧")
        format_standard = type_config.get("format_standard", "标准格式")
        dialogue_narration_ratio = type_config.get(
            "dialogue_narration_ratio", "均衡")
        target_broadcast = type_config.get("target_broadcast", "")
        words_per_episode = type_config.get("words_per_episode", 5000)
        script_mode = type_config.get("script_mode", "real")

    # 从大纲中提取场景信息
    scenes = episode_outline.get("scenes", [])
    scenes_info = ""
    if scenes:
        scenes_lines = []
        for scene in scenes:
            scene_num = scene.get("scene_number", "")
            location = scene.get("location", "未指定")
            int_ext = scene.get("interior_exterior", "内")
            time_of_day = scene.get("time_of_day", "日")
            core_content = scene.get(
                "core_content", scene.get("scene_purpose", ""))
            main_chars = scene.get(
                "main_characters", scene.get("characters_present", ""))
            duration = scene.get("estimated_duration") or scene.get(
                "duration_minutes") or 3
            scenes_lines.append(
                f"第{scene_num}场 {int_ext}景 {location} {time_of_day} | {core_content} | {main_chars} | {duration}分钟"
            )
        scenes_info = "\n".join(scenes_lines)
    else:
        scenes_info = "（未提供场景规划，请根据剧情大纲自行设计场景）"

    # 根据 script_mode 选择提示词模板
    if script_mode == "virtual":
        prompt_template = SERIES_SCRIPT_VIRTUAL_PROMPT
    else:
        prompt_template = SERIES_SCRIPT_EPISODE_PROMPT

    return prompt_template.format(
        # 大纲内容
        outline_metadata=context.get("outline_metadata", ""),
        outline_content=context.get("outline_content", ""),
        episode_outline=context.get(
            "episode_outline", ""),  # 使用context中格式化后的完整大纲
        previous_episodes_summary=context.get("previous_episodes_summary", ""),
        previous_content_summaries=context.get("previous_content_summaries", ""),
        # 全局上下文（新增）
        global_summary=context.get("global_summary", ""),
        previous_scene_ending=context.get("previous_scene_ending", ""),
        vector_context=context.get("vector_context", ""),
        current_unit_outline=context.get("current_unit_outline", ""),
        # 本集信息
        episode_number=episode_number,
        episode_title=episode_title,
        core_conflict=episode_outline.get("core_conflict", "未指定"),
        emotional_curve=episode_outline.get("emotional_curve", "未指定"),
        estimated_duration=episode_outline.get("estimated_duration") or 40,
        scenes_info=scenes_info,
        # 场景信息（虚拟模式需要）
        scene_number=1,
        location=episode_outline.get("location", "未指定"),
        interior_exterior=episode_outline.get("interior_exterior", "内"),
        time_of_day=episode_outline.get("time_of_day", "日"),
        characters_present=episode_outline.get("main_characters", "未指定"),
        scene_purpose=episode_outline.get("core_content", ""),
        # 剧集信息
        series_type=series_type,
        format_standard=format_standard,
        dialogue_narration_ratio=dialogue_narration_ratio,
        target_broadcast=target_broadcast,
        # 关键对话
        key_dialogues=episode_outline.get("key_dialogues", "未提供"),
        # 上下文
        character_states=context.get("character_states", ""),
        knowledge_context=context.get("knowledge_context", ""),
        # 生成配置
        dialogue_style=generation_config.get("dialogue_style", "自然对话"),
        narrative_rhythm=generation_config.get("narrative_rhythm", "紧凑"),
        words_per_episode=words_per_episode
    )


def get_scene_script_prompt(
    scene_number: int,
    scene_title: str,
    scene_outline: Dict[str, Any],
    context: Dict[str, Any],
    type_config: Optional[Dict[str, Any]] = None,
    generation_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    获取电影单场景正文生成提示词

    Args:
        scene_number: 场景号
        scene_title: 场景标题
        scene_outline: 场景详细大纲（从 scene_outlines 获取）
        context: 上下文信息
        type_config: 类型专用配置
        generation_config: 生成配置

    Returns:
        格式化后的提示词
    """
    generation_config = generation_config or {}

    # 电影配置
    movie_type = "院线电影"
    format_standard = "标准格式"
    dialogue_narration_ratio = "均衡"
    target_platform = "院线"
    total_duration = 120  # 电影总时长默认120分钟
    script_mode = "real"  # 默认现实模式

    if type_config:
        movie_type = type_config.get("movie_type", "院线电影")
        format_standard = type_config.get("format_standard", "标准格式")
        dialogue_narration_ratio = type_config.get(
            "dialogue_narration_ratio", "均衡")
        target_platform = type_config.get("target_platform", "院线")
        total_duration = type_config.get("total_duration", 120)
        script_mode = type_config.get("script_mode", "real")

    # 从场景大纲中提取信息
    location = scene_outline.get("location", "未指定")
    interior_exterior = scene_outline.get(
        "interior_exterior", scene_outline.get("int_ext", "内"))
    time_of_day = scene_outline.get(
        "time_of_day", scene_outline.get("time", "日"))
    characters_present = scene_outline.get(
        "characters_present", scene_outline.get("main_characters", "未指定"))
    scene_purpose = scene_outline.get(
        "scene_purpose", scene_outline.get("core_content", "未指定"))
    # 获取时长，确保不为 None（防止 None * int 报错）
    duration_minutes = scene_outline.get(
        "estimated_duration") or scene_outline.get("duration_minutes") or 3
    # 根据时长估算字数（每分钟约250字）
    estimated_words = int(duration_minutes * 250)

    # 根据 script_mode 选择提示词模板
    if script_mode == "virtual":
        prompt_template = MOVIE_SCRIPT_VIRTUAL_PROMPT
    else:
        prompt_template = MOVIE_SCRIPT_SCENE_PROMPT

    return prompt_template.format(
        # 大纲内容
        outline_content=context.get("outline_content", ""),
        current_unit_outline=context.get("scene_outline", ""),
        previous_scene_ending=context.get("previous_scene_ending", ""),
        previous_scenes_summary=context.get("previous_scenes_summary", ""),
        # 全局上下文（新增）
        global_summary=context.get("global_summary", ""),
        vector_context=context.get("vector_context", ""),
        # 场景信息
        scene_number=scene_number,
        scene_title=scene_title,
        location=location,
        interior_exterior=interior_exterior,
        time_of_day=time_of_day,
        characters_present=characters_present,
        scene_purpose=scene_purpose,
        duration_minutes=duration_minutes,
        estimated_words=estimated_words,
        # 电影信息
        movie_type=movie_type,
        total_duration=total_duration,
        format_standard=format_standard,
        dialogue_narration_ratio=dialogue_narration_ratio,
        target_platform=target_platform,
        # 上下文
        character_states=context.get("character_states", ""),
        knowledge_context=context.get("knowledge_context", ""),
        # 生成配置
        dialogue_style=generation_config.get("dialogue_style", "自然对话"),
        narrative_rhythm=generation_config.get("narrative_rhythm", "紧凑")
    )


# ==================== 小说章节详细大纲生成提示词 ====================

CHAPTER_DETAILED_OUTLINE_PROMPT = """【创作身份】
你是一位专业小说家，专注于章节大纲细化工作。你的核心任务是将基础大纲中的章节概要扩展为详细的章节大纲。

【基础大纲】
{outline_content}

【当前章节概要】
第{chapter_number}章：{chapter_title}
{chapter_summary}

【小说配置】
每章字数：约{words_per_chapter}字
叙事视角：{narrative_perspective}
基调氛围：{tone}
投放平台：{target_platform}

【前序章节大纲摘要】
{previous_chapters_summary}

【输出要求】
请为第{chapter_number}章生成详细的章节大纲，包含以下部分：

### 一、章节核心信息
- **章节标题**：[保留或优化原标题]
- **核心冲突**：[本章的主要矛盾]
- **情感曲线**：[读者应该经历的情感变化]
- **字数分配**：约{words_per_chapter}字

### 二、详细剧情大纲（600-1000字）
按照以下结构详细展开本章剧情：

1. **开篇（约15%）**：
   - 场景设定
   - 人物出场状态
   - 引入的问题/冲突

2. **发展（约40%）**：
   - 主要情节推进
   - 人物互动
   - 矛盾升级

3. **高潮（约30%）**：
   - 核心冲突爆发
   - 关键转折
   - 情感顶点

4. **收尾（约15%）**：
   - 问题阶段性解决或深化
   - 悬念埋设
   - 下一章预告感

### 三、关键事件清单
列出本章需要完成的关键事件（3-5个）：
1. [事件1]
2. [事件2]
3. [事件3]

### 四、角色发展弧
描述本章中主要角色的发展变化：
- **主角**：[心理/状态/关系的变化]
- **配角**：[关键配角的互动和发展]

### 五、悬念与伏笔设置
- **本章悬念**：[吸引读者继续阅读的钩子]
- **伏笔埋设**：[为后续章节铺垫的内容]
- **伏笔回收**：[回应之前章节的伏笔]

### 六、情感基调说明
- **整体氛围**：[温馨/紧张/悲伤/欢乐等]
- **情绪高点**：[本章情绪最强烈的时刻]
- **情绪转折**：[情绪变化的关键节点]

【创作原则】
1. 严格遵循基础大纲的人物设定和世界观
2. 与前序章节保持连贯性
3. 注意与前序章节的剧情衔接
4. 保持叙事节奏的流畅性
5. 确保每个情节都有明确的叙事目的

请直接输出详细章节大纲，不要添加额外的前言或解释。
"""


# ==================== 电影场景详细大纲生成提示词 ====================

SCENE_DETAILED_OUTLINE_PROMPT = """【重要提醒】这是电影剧本，不是剧集！输出格式必须使用"场"而非"集"！

【创作身份】
你是一位专业电影编剧，专注于场景大纲细化工作。你的核心任务是将基础大纲中的场景概要扩展为详细的场景大纲。

【基础大纲】
{outline_content}

【当前场景概要】
第{scene_number}场：{scene_title}
地点：{location}
{scene_summary}

【电影配置】
电影类型：{movie_type}
总时长：{total_duration}分钟
剧本格式：{format_standard}
对白比例：{dialogue_narration_ratio}

【前序场景大纲摘要】
{previous_scenes_summary}

【输出要求】
请为第{scene_number}场生成详细的场景大纲，包含以下部分：

### 一、场景核心信息
- **场景标题**：[保留或优化原标题]
- **地点**：{location}
- **时间**：[日/夜/晨/昏]
- **内/外景**：[内景/外景]
- **预计时长**：[X]分钟

### 二、详细场景大纲（400-600字）
按照以下结构详细展开本场内容：

1. **开场画面**：
   - 场景视觉描述
   - 氛围营造
   - 初始状态

2. **核心动作**：
   - 主要事件
   - 人物行为
   - 冲突展开

3. **高潮时刻**：
   - 情感顶点或冲突顶点
   - 关键转折
   - 视觉焦点

4. **收尾画面**：
   - 场景结束状态
   - 过渡提示
   - 情绪留白

### 三、出场人物
列出本场出现的角色及其状态：
- **主要人物**：[角色名] - [本场状态/目的]
- **次要人物**：[角色名] - [作用]

### 四、关键动作描述
详细描述本场的核心动作段落（2-3个）：
1. **动作段落1**：[描述] - [时长估算]
2. **动作段落2**：[描述] - [时长估算]

### 五、对话重点
描述本场对话的核心内容和风格：
- **对话主题**：[本场对话围绕什么展开]
- **对话风格**：[紧张/轻松/幽默/沉重]
- **核心台词**：[1-2句关键台词示例]

### 六、视觉与声音设计
- **视觉重点**：[需要强调的视觉元素]
- **光影设计**：[光线如何服务情绪]
- **声音设计**：[环境音/音乐的考量]

### 七、转场提示
- **本场承接**：[如何从上一场过渡]
- **本场引出**：[如何为下一场铺垫]

【创作原则】
1. 严格遵循基础大纲的人物设定和世界观
2. 与前序场景保持连贯性
3. 注意电影叙事的视觉性
4. 保持场景节奏的紧凑性
5. 确保每场戏都有明确的叙事目的
6. ⚠️ 这是电影，使用"第X场"格式，绝不能出现"第X集"

请直接输出详细场景大纲，不要添加额外的前言或解释。
"""
