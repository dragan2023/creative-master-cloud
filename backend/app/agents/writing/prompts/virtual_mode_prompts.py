"""
虚拟模式 AIGC 提示词模板

在 virtual mode 下，剧本正文下方提供分镜设计 + AI素材提示词（图片/音频） + AI视频提示词。

视频模型（仅保留两个）：
- Seedance 2.0（豆包视频生成模型 2.0，支持全能参考/多模态参考）
- MiniMax H3（原生多模态理解与生成，支持文字+图片+音频+视频混合参考，音画同源生成）

分镜提示词规范：
- 每个分镜必须输出为「结构化整段提示词」，禁止拆成字段列表
- 时间轴精确到秒级（[0-3秒]、[3-7秒]…），明确运镜、场景变化、主体人物动作
- 涉及AI视频生成的，必须同时提供对应素材（图片/音频）的提示词或具体描述

@date: 2026-05-19
@version: v3.0.0 — 分镜改为结构化整段提示词；视频模型收敛为 Seedance 2.0 + MiniMax H3；
                   新增 MiniMax H3 多模态参考与音频素材提示词
"""

# ============================================================================
# 分镜设计模板（结构化整段提示词）
# ============================================================================

STORYBOARD_TEMPLATE = """## 分镜设计表

为以下关键场景生成分镜设计。**每个分镜必须输出为一段「结构化整段提示词」**，禁止拆分为字段列表。

### 整段提示词必须包含的要素（按顺序写在一段话内）
1. **秒级时间轴**：用 `[0-3秒]`、`[3-7秒]`、`[7-11秒]`、`[11-15秒]` 精确划分镜头节拍，各段时长合计必须等于镜头总时长
2. **景别与运镜**：起始景别、运镜方式及起止过程（如"从全景缓慢推至中景"）、运动速度
3. **主体人物动作**：人物位置、走位方向、肢体动作、表情变化
4. **场景变化**：环境元素、光影色调、天气时间的演变
5. **情绪意图与转场**：本镜头想传达的情绪、镜头结束时的画面状态与转场方式

### 分镜输出格式示例
```text
【分镜1】[0-3秒] 大远景、固定镜头：黄昏雨后的老街全景，女主撑着红伞独自站在巷口，雨滴从伞沿滑落；[3-7秒] 镜头缓慢推近至中景，女主低头看手表，随后快步走向画左的咖啡馆；[7-11秒] 切换近景、跟拍，女主推门进入咖啡馆，门铃轻响，暖黄灯光映在她脸上；[11-15秒] 镜头停留于全景，女主在窗边坐下望向窗外，画面定格。运镜整体平稳、节奏舒缓；情绪基调为"克制中带着期待"；转场方式为直切。

{storyboard_rows}
```

### 分镜时长规则
- 单镜头建议 3-15 秒，总时长必须与场景时长一致
- 15 秒镜头推荐四段式节拍：0-3秒 视觉Hook → 3-7秒 揭示主体 → 7-11秒 细节/动作 → 11-15秒 定格收尾
- 每个镜头的时间轴必须连续且无重叠；场景切换、人物更换、情绪转折处必须另起新镜头
"""

# ============================================================================
# 图片素材提示词模板（多模态参考所需的参考图）
# ============================================================================

IMAGE_PROMPT_INTRO = """## 🎬 AI素材提示词（图片）

AI视频生成必须基于素材，请为以下关键场景生成**图片素材提示词**（用于生成人物/场景/物品参考图，供 Seedance 2.0 与 MiniMax H3 多模态参考使用）。**所有提示词必须使用中文输出。**

### 图片素材提示词构建指南
公式：`[主体描述] + [动作姿态] + [地点环境] + [构图方式] + [风格标签] + [画幅比例]`

- **主体描述**：角色的外貌、服装、姿态、表情（中文描述）
- **动作姿态**：角色正在做什么，动作的状态（中文描述）
- **地点环境**：场景环境、时间、天气、氛围（中文描述）
- **构图方式**：景别（特写/近景/中景/全景/远景）、角度（低角度/高角度/平视）
- **风格标签**：写实/电影级/油画/动漫/3D渲染 等
- **画幅比例**：{aspect_ratio}

> 图片素材用途（多模态参考）：
> - Seedance 2.0 全能参考：参考人物/场景/物品图片锁定外观与环境
> - MiniMax H3 多模态参考：refers[] 可混合图片、视频、音频（最多9张图片+3段视频+3段音频，音频不能单独作为唯一参考）
"""

IMAGE_MATERIAL_PROMPT_FORMAT = """### 图片素材提示词（场景{scene_number}：{scene_name}）
```text
{subject}，{action}，位于{location}，{composition}，{style}，电影级布光，写实质感，{aspect_ratio}
```"""

IMAGE_PROMPT_EXAMPLE = """### 示例

**场景：黄昏决斗**
```text
中年战士身着磨损皮甲立于悬崖边缘，手握长剑垂于身侧，黄昏时分，广角远景、戏剧性逆光构图，金色时光布光，电影级构图，写实质感，8K，16:9
```"""

# ============================================================================
# 音频素材提示词模板（音效/BGM，多模态参考所需）
# ============================================================================

AUDIO_PROMPT_INTRO = """## 🎵 AI素材提示词（音频）

AI视频生成必须配套音频素材。请根据剧本内容与分镜设计，为关键镜头生成**音频素材提示词或具体描述**，用于生成/检索音效与BGM，作为 Seedance 2.0 与 MiniMax H3 多模态参考的音频输入。

### BGM 智能判断规则（AI 自行决策）
1. **是否需要BGM**：根据场景情绪与叙事节奏自行判断——情绪强烈、需要氛围烘托的关键场景配BGM；纯对白或纪实段落可不配BGM或仅用环境音，不得机械地为每个镜头都配乐
2. **BGM起始点**：明确标注在哪个镜头、第几秒进入/淡出（如"第2镜头 3秒处进入，12秒处渐弱"），与分镜秒级时间轴对齐
3. **纯音乐 or 人声**：氛围烘托类用纯音乐（instrumental / no vocals）；剧情歌曲、片尾曲、角色演唱等场景用有人声歌唱的（female vocalist / male vocal / choir / 哼唱 humming）；两类 Suno 均可覆盖

**BGM/音乐类素材遵循 Suno AI 提示词最佳实践**（Suno 风格标签使用英文国际通用术语，附加说明使用中文）：

### Suno 风格 BGM 提示词公式
```
[流派/子流派] + [情绪/氛围] + [速度BPM] + [核心乐器] + [人声方向] + [制作质感] + [结构标签] + [排除标签]
```

- **流派/子流派**：如 cinematic orchestral / lo-fi hip hop / electronic ambient / traditional Chinese folk
- **情绪/氛围**：2-3个情绪词，如 emotional / mysterious / uplifting / melancholic
- **速度BPM**：直接用数值锁定（如 60-90 BPM 抒情、120-140 BPM 流行/摇滚），或用速度词（Slow / Medium / Upbeat）
- **核心乐器**：3-6个，如 strings, piano, electric guitar, synth, erhu
- **人声方向**：如 female vocalist / male vocal / choir / no vocals（纯音乐）
- **制作质感**：如 hall reverb, clean production, vinyl crackle, raw
- **结构标签**：Suno 在歌词栏用方括号结构标签控制段落：[Intro] [Verse] [Chorus] [Bridge] [Outro] [Instrumental Break]；可配合秒级时间轴（如 [Chorus] 8-12秒 管弦渐强）
- **排除标签**：如 no drums, no vocals, no distortion

### 音频素材提示词构建指南
每个音频素材提示词必须包含：
1. **音频类型**：环境音 / 拟音 / 人声 / BGM
2. **具体描述**：声音内容的完整描述
3. **出现时间**：在哪个镜头、哪个秒级节点进入/淡出（如"第2镜头 3-7秒：脚步声由远及近"）
4. **情绪与画面配合**：与当前画面情绪的关系
5. **素材来源**：BGM 给出可直接粘贴到 Suno 的风格标签；环境音/拟音给出音效库检索关键词

### 输出格式示例
```text
【音频素材1】环境音+拟音：雨夜街道环境音（雨声、远处车流），第1镜头全程；[3-5秒] 加入女主高跟鞋脚步声（由远及近）；情绪：克制、紧张；素材来源：音效库检索 rainy night street ambience, footsteps
```
```text
【音频素材2】BGM：电影感悬疑配乐；Suno风格标签：cinematic orchestral, mysterious, building tension, 90 BPM, strings, piano, no vocals, hall reverb；结构标签：[Intro] 0-3秒 弦乐铺底，[Verse] 3-8秒 钢琴主旋律，[Chorus] 8-12秒 管弦渐强，[Outro] 12-15秒 渐弱定格；情绪配合：紧张中带希望；素材来源：Suno Custom Mode
```"""

AUDIO_PROMPT_FORMAT = """### 音频素材提示词（镜头{shot_number}）
```text
{audio_type}：{audio_description}；出现时间：{audio_timing}；情绪配合：{audio_mood}；素材来源：{audio_source}
```"""

# ============================================================================
# 视频生成提示词模板（Seedance 2.0 / MiniMax H3）
# ============================================================================

VIDEO_PROMPT_INTRO = """## 🎥 AI视频生成提示词

基于以上分镜设计与素材，为每个分镜生成可直接使用的AI视频生成提示词。**所有提示词必须使用中文输出，且为结构化整段提示词（一个分镜一段话，禁止 [字段]：值 堆叠）。**

### 通用整段式结构（Seedance 2.0 / MiniMax H3 均适用）
一段话内依次包含：
1. **主体锚定**：引用对应素材（人物/场景/物品参考图、音频）锁定身份与环境
2. **秒级时间轴**：`[0-3秒]`、`[3-7秒]` 等精确描述每段时间的画面内容、人物动作、场景变化
3. **运镜语言**：明确起始景别、运镜方式、运动过程与终点（如"从全景缓慢推至中景，随后向右横摇45度跟拍"）
4. **光影色调**：光源方向、色温、氛围
5. **音频指令**：环境音、人声、BGM 的进入时间点（MiniMax H3 原生生成音轨，必须写明）
6. **负面约束**：避免模糊、抖动、变形、水印、多余文字等

### Seedance 2.0 最佳实践
- 15秒四段式时间轴：0-3秒视觉Hook → 3-7秒揭示 → 7-11秒细节/动作 → 11-15秒定格收尾
- 运镜词要具体：推/拉/摇/移/跟/升降/环绕/手持，标注起止与速度
- 动作描述精确到位，避免"走来走去"等模糊表达
- 多模态参考：使用 `参考图片N中的[主体/场景]，生成……` 引用素材

### MiniMax H3 最佳实践（六段式结构）
MiniMax H3 官方亮点：原生多模态理解与生成（文字+图片+音频+视频混合输入）、多模态精准编辑与控制、商用级多场景内容生成；音画同源生成，最高15秒2K。

每个提示词按以下六段组织（仍为整段文字，不拆字段）：
1. **风格契约**：媒介、质感、调色板、时代、不可丢失的外观
2. **时间线**：`[0s-2s]`、`[2s-4s]` 等带具体动作的时间切片，精确命中每个节拍
3. **摄像机**：运动方式，或明确拒绝运动（如"锁定机位、静态广角、无推近"）
4. **音频**：每个声音及其进入时间（H3 同次生成音轨，必须写明，如"6秒处爵士贝斯律动进入"）
5. **文字**：需要可读的文字逐个拼写（标题、标语等），避免乱码
6. **否定列表**：拒绝的转场、对象、陈词滥调（如"无软溶解、无字幕、无多余文字"）

### MiniMax H3 多模态参考
- 通过 `refers[]` 混合引用素材：最多9张图片、3段视频、3段音频（共12个文件）；音频不能单独作为唯一参考
- 每个参考素材必须在提示词开头明确其任务（如"图片1是整体氛围和风格参考，图片2是主角参考"）
- 可选用 image-to-video（首帧 + 可选尾帧 end_image）锁定起止画面
"""

SEEDANCE_VIDEO_PROMPT_FORMAT = """### Seedance 2.0 提示词（镜头{shot_number}）
```text
参考图片{ref_number}中的{subject}，{timeline_paragraph}。运镜：{camera}；光影：{lighting}；音频：{audio}；负面约束：{negative_prompt}
```"""

MINIMAX_VIDEO_PROMPT_FORMAT = """### MiniMax H3 提示词（镜头{shot_number}）
```text
图片1为整体氛围与风格参考，图片2为人物/主体参考；{style_contract}。{timeline_paragraph}。摄像机：{camera}；音频：{audio}；{text_requirement}；否定列表：{negative_prompt}
```"""

# ============================================================================
# 聚合模板：虚拟模式完整输出
# ============================================================================

VIRTUAL_MODE_FULL_TEMPLATE = """{storyboard_section}

---

{image_prompt_section}

---

{audio_prompt_section}

---

{video_prompt_section}

---

> 💡 **提示**：以上为 AI 生成参考提示词。实际使用时请根据具体角色设定和场景需求调整参数。
> 1. 先用「图片素材提示词」生成人物/场景/物品参考图；
> 2. 按「音频素材提示词」准备或生成音效/BGM 素材；
> 3. 将图片、音频素材上传至 Seedance 2.0 或 MiniMax H3 作为多模态参考输入；
> 4. 使用「视频生成提示词」逐镜生成，建议先测试关键镜头再批量生成。
"""

# ============================================================================
# 多模态参考模式（Seedance 2.0 全能参考 / MiniMax H3 多模态参考）
# ============================================================================
# 多模态参考假定用户已准备人物参考图、场景参考图、物品参考图与音频素材，
# AI需提供：1) 这些素材的生成提示词 2) 基于已有素材的视频生成提示词

MULTIMODAL_REFERENCE_INTRO = """## 🎬 多模态参考模式（Seedance 2.0 全能参考 / MiniMax H3 多模态参考）

**核心理念**：Seedance 2.0 与 MiniMax H3 均支持多模态输入（文字+图片+视频+音频）。多模态参考模式假定用户已完成以下素材准备：
- **人物参考图**：主要角色的定妆照或概念图（通过AI绘图工具生成）
- **场景参考图**：关键场景的概念图/氛围图（通过AI绘图工具生成）
- **物品参考图**：重要道具或物品的概念图（通过AI绘图工具生成）
- **音频素材**：音效/BGM（通过AI音乐工具生成或版权库检索）

在此模式下，你需要生成以下四类内容：

### 1. 素材生成提示词
请根据剧本内容，为每个人物、场景、物品、音频生成可直接用于 AI 工具（AI绘图 / AI音乐）的中文提示词。
- **关键要求**：提示词必须具体、可操作、无需二次加工。每个提示词应包含完整的外观描述、环境细节、光影氛围和风格标签；音频提示词需包含音乐风格、情绪基调、乐器配置、节奏特点与出现时间。
- **语言要求**：所有提示词必须使用中文输出，使用中文视觉/听觉描述术语（如"特写""广角""逆光""电影级质感""低沉弦乐"等）。

### 2. 视频生成提示词
基于上述已生成的素材，为每个关键镜头提供 Seedance 2.0 / MiniMax H3 的结构化整段视频提示词。
- **整段式完整性**：每个视频提示词必须为一段完整中文自然语句，含秒级时间轴（[0-3秒]、[3-7秒]…）、运镜、主体动作、场景变化、音频指令与负面约束，不可遗漏。
- **素材引用**：在视频提示词中明确引用对应的人物参考图、场景参考图、物品参考图和音频素材名称，并写明每个素材承担的任务。

### 3. 音频素材
为每个视频片段提供对应的音频素材提示词或具体描述（环境音/拟音/人声/BGM），并标注进入与淡出时间。

### 4. 输出质量要求
- 所有提示词必须使用中文专业视觉/听觉术语输出
- 视频提示词遵循整段式 + 秒级时间轴规范
- 风格标签需与已选的创作风格维度保持一致
- 如需补充特定知识以提升提示词质量，请积极利用你的知识储备进行推理和补充

---
"""

# 人物参考图提示词模板（指令式：请LLM根据剧本人物设定生成完整提示词）
SEEDANCE_CHARACTER_REF_PROMPT_FORMAT = """#### 人物参考图：{character_name}
- **角色定位**：{character_role}
- **外貌特征**：{appearance}
- **服装风格**：{costume}
- **表情气质**：{expression}
- **图片素材提示词**（请根据以上人物信息，生成可直接用于 AI绘图工具 的中文提示词）：
```text
{character_name}角色概念图，{subject_desc}，{costume_desc}，{pose_desc}，{lighting}，{style}风格，人物肖像，高质量，角色设定图，{aspect_ratio}
```
> 请将上述模板中的占位符替换为剧本中具体的人物描写（使用中文），确保提示词能准确还原角色的视觉形象。"""

# 场景参考图提示词模板（指令式：请LLM根据剧本场景描述生成完整提示词）
SEEDANCE_SCENE_REF_PROMPT_FORMAT = """#### 场景参考图：{scene_name}
- **场景类型**：{scene_type}（日/夜景，室内/室外）
- **场景氛围**：{atmosphere}
- **关键元素**：{key_elements}
- **图片素材提示词**（请根据以上场景信息，生成可直接用于 AI绘图工具 的中文提示词）：
```text
{scene_name}场景概念图，{location_desc}，{time_weather}，{atmosphere_desc}，{composition}，{style}风格，电影级质感，高质量，{aspect_ratio}
```
> 请将上述模板中的占位符替换为剧本中具体的场景描写（使用中文），构图使用中文电影术语（广角全景 / 中景 / 特写 / 低角度 / 俯拍 等）。"""

# 物品参考图提示词模板（指令式：请LLM根据剧本文本中的道具描述生成完整提示词）
SEEDANCE_PROP_REF_PROMPT_FORMAT = """#### 物品参考图：{prop_name}
- **物品描述**：{prop_description}
- **物品意义**：{prop_significance}
- **图片素材提示词**（请根据以上道具信息，生成可直接用于 AI绘图工具 的中文提示词）：
```text
{prop_name}道具概念图，{prop_desc}，{material}，{lighting}，{style}风格，产品摄影，高质量，白底图，{aspect_ratio}
```
> 请将上述模板中的占位符替换为剧本文本中具体的道具描写（使用中文），材质光影描述尽可能具体（如：磨砂金属、抛光玉石、做旧皮革等）。"""

# 音频素材提示词模板（指令式：请LLM根据剧本配乐需求生成完整提示词）
MULTIMODAL_AUDIO_REF_PROMPT_FORMAT = """#### 音频素材：{audio_name}
- **音频类型**：{audio_type}（环境音/拟音/人声/BGM）
- **出现时间**：{audio_timing}
- **情绪配合**：{audio_mood}
- **音频素材提示词**（BGM 遵循 Suno AI 提示词最佳实践，风格标签用英文、附加说明用中文）：
```text
{audio_type_desc}；Suno风格标签：{audio_style}, {audio_mood_en}, {audio_rhythm} BPM, {audio_instruments}；结构标签：[Intro] {audio_timing_intro}，[Verse] {audio_timing_verse}，[Chorus] {audio_timing_chorus}，[Outro] {audio_timing_outro}；排除标签：{audio_exclude}；情绪配合：{audio_mood}
```
> 请将上述模板中的占位符替换为剧本配乐参考中的具体需求：风格标签用英文国际通用术语（如 cinematic orchestral, emotional, 90 BPM, strings, piano），结构标签配合秒级时间轴，排除标签写明不希望出现的元素（如 no drums, no vocals）。"""

# 基于素材的视频生成提示词模板（指令式：请LLM根据剧本镜头设计生成完整整段提示词）
SEEDANCE_VIDEO_FROM_REF_FORMAT = """#### Seedance 2.0 视频生成：{shot_name}
- **使用素材**：
  - 人物参考：{character_refs}
  - 场景参考：{scene_ref}
  - 物品参考：{prop_refs}
  - 音频参考：{audio_refs}
- **Seedance 2.0 全能参考模式视频生成提示词**（请根据剧本中的具体镜头设计，用中文写成一段完整自然语句，含秒级时间轴）：
```text
参考图片1中的{character_refs}，参考图片2中的{scene_ref}，{timeline_paragraph}。运镜：{camera}；光影：{lighting}；音频：{audio}；负面约束：{negative_prompt}
```
> 请确保提示词为一段完整中文自然语句：首帧/尾帧描述形成清晰的视觉起止点，运镜方式具体（如：从全景缓慢推至中景，同时向右横摇45度），时间轴精确到秒。"""

MINIMAX_VIDEO_FROM_REF_FORMAT = """#### MiniMax H3 视频生成：{shot_name}
- **使用素材**：
  - 图片参考：{image_refs}
  - 视频参考：{video_refs}
  - 音频参考：{audio_refs}
- **MiniMax H3 多模态参考视频生成提示词**（请根据剧本中的具体镜头设计，用中文写成一段完整自然语句，遵循六段式结构：风格契约→时间线→摄像机→音频→文字→否定列表）：
```text
图片1为整体氛围与风格参考，图片2为{character_refs}参考，图片3为{scene_ref}参考；{style_contract}。[0s-2s] {timeline_paragraph_start}；[2s-5s] {timeline_paragraph_mid}；[5s-8s] {timeline_paragraph_end}。摄像机：{camera}；音频：{audio}；文字：{text_requirement}；否定列表：{negative_prompt}
```
> 请确保提示词为一段完整中文自然语句：时间切片精确到秒，音频必须写明每个声音的进入时间（H3 同次生成音轨），需要可读的文字逐个拼写，并用否定列表约束转场与多余元素。"""

# 多模态参考模式聚合模板（指令式引导版）
SEEDANCE_COMPREHENSIVE_TEMPLATE = """{reference_intro}

### 一、人物参考图生成提示词
请根据当前单元剧本中出场的每位主要角色，按以下要求生成角色概念图提示词：
- 每位角色1-3张（正面全身、半身特写、动态姿势各一张）
- 提示词需包含：外貌特征、服装风格、姿态动作、光影氛围、风格标签、画幅比例
- **使用中文输出**，使用中文视觉描述术语，确保可直接用于AI绘图工具

{character_refs_section}

### 二、场景参考图生成提示词
请根据当前单元剧本中的每个关键场景，按以下要求生成场景概念图提示词：
- 每个场景1-2张（广角全景 + 局部特写各一张）
- 提示词需包含：地点描述、时间/天气、氛围基调、电影级构图术语、风格标签、画幅比例
- **使用中文输出**，构图使用中文电影术语（广角全景 / 中景 / 特写 / 低角度 / 俯拍 / 跟拍 等）

{scene_refs_section}

### 三、物品参考图生成提示词
请根据当前单元剧本中出现的重要道具/物品，按以下要求生成道具概念图提示词：
- 每个物品1张，白底产品图风格
- 提示词需包含：外观描述、材质质感、光影、风格标签、画幅比例
- 材质描述具体化（如：磨砂金属、抛光玉石、做旧皮革等），**使用中文输出**

{prop_refs_section}

### 四、音频素材生成提示词
请根据当前单元剧本的配乐需求与分镜设计，为每个关键镜头生成音频素材提示词：
- 每个视频片段至少1条音频提示词（环境音/拟音/人声/BGM）
- 提示词需包含：音频类型、出现时间（精确到秒）、情绪配合、素材来源建议
- BGM需注明音乐风格、乐器配置、节奏特点（建议标注BPM），**使用中文输出**

{audio_refs_section}

### 五、基于素材的视频生成提示词（Seedance 2.0 / MiniMax H3）
请基于上述已生成的素材，为当前单元的每个关键镜头生成结构化整段视频提示词：
- 明确引用对应的人物/场景/物品/音频素材名称，并写明每个素材承担的任务
- 每个镜头包含秒级时间轴（[0-3秒]、[3-7秒]…），形成清晰的视觉起止点
- 运镜方式具体描述（推拉摇移跟升降的具体参数），动作描述精确到位
- MiniMax H3 需按六段式结构（风格契约→时间线→摄像机→音频→文字→否定列表）组织
- **所有提示词必须为一段完整中文自然语句输出**

{video_refs_section}

---
> 💡 **使用说明**：
> 1. 先用素材生成提示词通过 AI绘图/AI音乐工具 生成对应的人物、场景、物品参考图与音频素材
> 2. 将素材上传至 Seedance 2.0（全能参考）或 MiniMax H3（多模态参考 refers[]）作为参考输入
> 3. 使用视频生成提示词进行视频生成，模型将自动融合素材中的角色、场景、物品与音频特征
> 4. 建议先测试关键镜头，确认效果后再批量生成
> 5. MiniMax H3 音频不能单独作为唯一参考，需至少搭配一张图片或一段视频
> 6. 如遇需要特定历史/文化知识的视觉细节，请利用已有知识进行推理补充，不确定时使用通用视觉描述
"""

# ============================================================================
# 辅助函数
# ============================================================================


def build_virtual_mode_prompt(
    content_type: str,
    scene_count: int,
    style_names: list = None,
    aspect_ratio: str = "16:9",
) -> str:
    """构建完整的虚拟模式AIGC提示词段落

    Args:
        content_type: "series"（剧集）或 "movie"（电影）
        scene_count: 关键场景数量
        style_names: 已选风格名称列表
        aspect_ratio: 画面比例，默认16:9

    Returns:
        完整的虚拟模式提示词段落（分镜设计 + 图片素材 + 音频素材 + 视频提示词）
    """
    style_names = style_names or []
    unit_label = "集" if content_type == "series" else "场"
    style_tags = "、".join(style_names) if style_names else "通用"

    parts = []

    # 分镜设计引导（结构化整段提示词）
    example_row = "【分镜2】[0-3秒] …（其余分镜按相同整段格式继续输出）"
    parts.append(f"""### 虚拟模式 — AI视频生成分镜设计

为当前{unit_label}的{scene_count}个关键场景设计分镜，每个场景拆分为3-8个镜头。
风格参考：{style_tags}
所有分镜必须使用「结构化整段提示词」输出，时间轴精确到秒。

{STORYBOARD_TEMPLATE.format(storyboard_rows=example_row)}""")

    # 图片素材提示词
    parts.append(IMAGE_PROMPT_INTRO.format(aspect_ratio=aspect_ratio))
    parts.append(IMAGE_PROMPT_EXAMPLE)

    # 音频素材提示词
    parts.append(AUDIO_PROMPT_INTRO)

    # 视频提示词
    parts.append(VIDEO_PROMPT_INTRO)

    parts.append(f"""
请为每一场关键场景分别生成上述格式的素材与视频提示词，确保视觉风格与已选风格维度（{style_tags}）保持一致，并保证：
1. 每个分镜提示词为一段完整中文自然语句，含秒级时间轴
2. 每个视频提示词配套对应的图片素材提示词与音频素材提示词
""")

    return "\n".join(parts)


def get_image_prompt_templates() -> dict:
    """获取图片素材提示词模板"""
    return {
        "gemini_format": IMAGE_MATERIAL_PROMPT_FORMAT,
        "doubao_format": IMAGE_MATERIAL_PROMPT_FORMAT,
        "material_format": IMAGE_MATERIAL_PROMPT_FORMAT,
        "intro": IMAGE_PROMPT_INTRO,
        "example": IMAGE_PROMPT_EXAMPLE,
    }


def get_video_prompt_templates() -> dict:
    """获取视频提示词模板"""
    return {
        "seedance_format": SEEDANCE_VIDEO_PROMPT_FORMAT,
        "veo_format": MINIMAX_VIDEO_PROMPT_FORMAT,
        "minimax_format": MINIMAX_VIDEO_PROMPT_FORMAT,
        "intro": VIDEO_PROMPT_INTRO,
    }


def get_audio_prompt_templates() -> dict:
    """获取音频素材提示词模板"""
    return {
        "audio_format": AUDIO_PROMPT_FORMAT,
        "intro": AUDIO_PROMPT_INTRO,
    }


def get_comprehensive_ref_templates() -> dict:
    """获取多模态参考模式模板"""
    return {
        "reference_intro": MULTIMODAL_REFERENCE_INTRO,
        "character_ref_format": SEEDANCE_CHARACTER_REF_PROMPT_FORMAT,
        "scene_ref_format": SEEDANCE_SCENE_REF_PROMPT_FORMAT,
        "prop_ref_format": SEEDANCE_PROP_REF_PROMPT_FORMAT,
        "audio_ref_format": MULTIMODAL_AUDIO_REF_PROMPT_FORMAT,
        "video_from_ref_format": SEEDANCE_VIDEO_FROM_REF_FORMAT,
        "minimax_video_from_ref_format": MINIMAX_VIDEO_FROM_REF_FORMAT,
        "comprehensive_template": SEEDANCE_COMPREHENSIVE_TEMPLATE,
    }


def build_seedance_comprehensive_prompt(
    content_type: str,
    character_names: list = None,
    scene_names: list = None,
    prop_names: list = None,
    audio_names: list = None,
    style_names: list = None,
    aspect_ratio: str = "16:9",
) -> str:
    """构建多模态参考模式的完整提示词段落（Seedance 2.0 / MiniMax H3）

    多模态参考假设用户已拥有角色参考图、场景参考图、物品参考图与音频素材，
    AI需要提供：
    1. 这些素材的生成提示词（用于生成参考素材）
    2. 基于已有素材的视频生成提示词（Seedance 2.0 / MiniMax H3 格式）

    Args:
        content_type: "series"（剧集）或 "movie"（电影）
        character_names: 出场人物名称列表
        scene_names: 关键场景名称列表
        prop_names: 重要道具名称列表
        audio_names: 音频素材名称列表
        style_names: 已选风格名称列表
        aspect_ratio: 画面比例，默认16:9

    Returns:
        完整的多模态参考模式提示词段落
    """
    character_names = character_names or []
    scene_names = scene_names or []
    prop_names = prop_names or []
    audio_names = audio_names or []
    style_names = style_names or []
    unit_label = "集" if content_type == "series" else "场"
    style_tags = "、".join(style_names) if style_names else "通用"

    parts = [MULTIMODAL_REFERENCE_INTRO]

    # 一、人物参考图生成提示词
    if character_names:
        parts.append("### 一、人物参考图生成提示词")
        parts.append(f"（为当前{unit_label}出场人物生成角色概念图提示词，建议每位主要角色1-3张，含正面全身、半身特写、动态姿势）")
        parts.append("")
        for char_name in character_names:
            parts.append(SEEDANCE_CHARACTER_REF_PROMPT_FORMAT.format(
                character_name=char_name,
                character_role="待LLM根据剧本内容填写",
                appearance="待LLM根据人物设定填写",
                costume="待LLM根据背景设定填写",
                expression="待LLM根据剧情情绪填写",
                subject_desc=f"{char_name}的人物概念图",
                costume_desc="待补充",
                pose_desc="待补充",
                lighting="电影级布光",
                style=style_tags,
                aspect_ratio=aspect_ratio,
            ))
            parts.append("")
    else:
        parts.append("### 一、人物参考图生成提示词")
        parts.append(f"（请LLM根据当前{unit_label}剧本内容，识别出场人物并生成对应的角色概念图提示词）")
        parts.append("")

    # 二、场景参考图生成提示词
    if scene_names:
        parts.append("### 二、场景参考图生成提示词")
        parts.append(f"（为当前{unit_label}关键场景生成场景概念图提示词，建议每个场景1-2张，含广角全景、局部特写）")
        parts.append("")
        for scene_name in scene_names:
            parts.append(SEEDANCE_SCENE_REF_PROMPT_FORMAT.format(
                scene_name=scene_name,
                scene_type="待LLM根据剧本填写（日/夜景，室内/室外）",
                atmosphere="待LLM根据剧本氛围填写",
                key_elements="待LLM根据剧本提取",
                location_desc=f"{scene_name}的场景概念图",
                time_weather="待补充",
                atmosphere_desc="待补充",
                composition="电影级构图",
                style=style_tags,
                aspect_ratio=aspect_ratio,
            ))
            parts.append("")
    else:
        parts.append("### 二、场景参考图生成提示词")
        parts.append(f"（请LLM根据当前{unit_label}剧本内容，识别关键场景并生成对应的场景概念图提示词）")
        parts.append("")

    # 三、物品参考图生成提示词
    if prop_names:
        parts.append("### 三、物品参考图生成提示词")
        parts.append(f"（为当前{unit_label}重要道具/物品生成物品概念图提示词，建议每个物品1张，白底产品图风格）")
        parts.append("")
        for prop_name in prop_names:
            parts.append(SEEDANCE_PROP_REF_PROMPT_FORMAT.format(
                prop_name=prop_name,
                prop_description="待LLM根据剧本填写",
                prop_significance="待LLM根据剧情填写",
                prop_desc=f"{prop_name}的道具概念图",
                material="待补充",
                lighting="专业产品布光",
                style=style_tags,
                aspect_ratio=aspect_ratio,
            ))
            parts.append("")
    else:
        parts.append("### 三、物品参考图生成提示词")
        parts.append(f"（请LLM根据当前{unit_label}剧本内容，识别重要道具并生成对应的物品概念图提示词）")
        parts.append("")

    # 四、音频素材生成提示词
    if audio_names:
        parts.append("### 四、音频素材生成提示词")
        parts.append(f"（为当前{unit_label}关键镜头生成音频素材提示词，每个视频片段至少1条：环境音/拟音/人声/BGM）")
        parts.append("")
        for audio_name in audio_names:
            parts.append(MULTIMODAL_AUDIO_REF_PROMPT_FORMAT.format(
                audio_name=audio_name,
                audio_type="待LLM根据剧本填写（环境音/拟音/人声/BGM）",
                audio_timing="待LLM根据分镜时间轴填写（精确到秒）",
                audio_mood="待LLM根据剧情情绪填写",
                audio_type_desc=f"{audio_name}的音频素材",
                audio_style="待LLM填写流派/子流派（英文，如 cinematic orchestral）",
                audio_mood_en="待LLM填写情绪词（英文，如 emotional）",
                audio_rhythm="待LLM填写速度BPM（如 90）",
                audio_instruments="待LLM填写核心乐器（英文，如 strings, piano）",
                audio_timing_intro="待LLM填写（如 0-3秒 弦乐铺底）",
                audio_timing_verse="待LLM填写（如 3-8秒 钢琴主旋律）",
                audio_timing_chorus="待LLM填写（如 8-12秒 管弦渐强）",
                audio_timing_outro="待LLM填写（如 12-15秒 渐弱定格）",
                audio_exclude="待LLM填写排除标签（如 no drums, no vocals）",
            ))
            parts.append("")
    else:
        parts.append("### 四、音频素材生成提示词")
        parts.append(f"（请LLM根据当前{unit_label}剧本的配乐需求与分镜设计，为每个关键镜头生成音频素材提示词）")
        parts.append("")

    # 五、基于素材的视频生成提示词
    parts.append("### 五、基于素材的视频生成提示词（Seedance 2.0 / MiniMax H3）")
    parts.append(f"（基于上述已生成的人物/场景/物品/音频素材，为每个镜头提供结构化整段视频生成提示词）")
    parts.append("")
    parts.append(f"> 请LLM为每个关键场景的每个镜头，在视频提示词中明确引用对应素材名称，并写明每个素材承担的任务。")
    parts.append(f"> 视频风格参考：{style_tags}")
    parts.append("")

    # 使用说明
    parts.append("---")
    parts.append("> 💡 **使用说明**：")
    parts.append("> 1. 先用素材生成提示词通过 AI绘图/AI音乐工具 生成对应的参考图与音频素材")
    parts.append("> 2. 将素材上传至 Seedance 2.0（全能参考）或 MiniMax H3（多模态参考 refers[]）作为参考输入")
    parts.append("> 3. 使用视频生成提示词进行视频生成，模型将自动融合素材中的角色、场景、物品与音频特征")
    parts.append("> 4. 建议先测试关键镜头，确认效果后再批量生成")
    parts.append("> 5. MiniMax H3 音频不能单独作为唯一参考，需至少搭配一张图片或一段视频")

    return "\n".join(parts)
