"""
虚拟模式 AIGC 提示词模板

在 virtual mode 下，剧本正文下方提供分镜设计 + AI场景图提示词 + AI视频提示词。
使用新一代 AI 模型最佳实践：
- 场景图：Gemini (Nano Banana 2) / 豆包 AI 绘图
- 视频：Seedance 2.0 / Veo

@date: 2026-05-06
@version: v1.0.0
"""

# ============================================================================
# 分镜设计模板
# ============================================================================

STORYBOARD_TEMPLATE = """## 分镜设计表

为以下关键场景生成分镜设计：

| 序号 | 景别 | 镜头运动 | 画面描述 | 情感意图 | 时长(秒) |
|------|------|----------|----------|----------|----------|
{storyboard_rows}

### 分镜说明
- **景别**：特写 / 近景 / 中景 / 全景 / 远景 / 大远景
- **镜头运动**：推 / 拉 / 摇 / 移 / 跟 / 升降 / 固定 / 手持
- **情感意图**：该镜头想传达的情感或叙事目的
- **时长**：建议3-15秒/镜头，根据内容节奏调整
"""

# ============================================================================
# 场景图生成提示词模板（Gemini / 豆包）
# ============================================================================

IMAGE_PROMPT_INTRO = """## 🎬 AI场景图生成提示词

基于以上剧本内容，为以下关键场景生成AI图片提示词。

### 提示词构建指南

#### Gemini (Nano Banana 2) 最佳实践
公式：`[Subject] + [Action] + [Location/Context] + [Composition] + [Style]`

- **Subject（主体）**：角色的外貌、服装、姿态、表情
- **Action（动作）**：角色正在做什么，动作的状态
- **Location/Context（地点/背景）**：场景环境、时间、天气、氛围
- **Composition（构图）**：景别（close-up/medium/wide）、角度（low angle/high angle/eye level）
- **Style（风格）**：photorealistic / cinematic / oil painting / anime / 3D render

#### 豆包 AI 绘图 最佳实践
公式：`主体描述 + 环境 + 光线 + 风格 + 质量标签`

- **主体描述**：角色外貌、服装、动作姿态（具体落地，忌模糊）
- **环境**：场景环境、背景元素、空间关系
- **光线**：光源方向（侧光/逆光/顶光）、色温（暖/冷/中性）、强度
- **风格**：视觉风格关键词（如：写实/厚涂/水墨/赛博朋克）
- **质量标签**：高质量、精细、{aspect_ratio}比例
"""

GEMINI_IMAGE_PROMPT_FORMAT = """### Gemini Prompt（场景{scene_number}：{scene_name}）
```
{subject} {action} at {location}, {composition}, {style}, cinematic lighting, photorealistic
```"""

DOUBAO_IMAGE_PROMPT_FORMAT = """### 豆包 Prompt（场景{scene_number}：{scene_name}）
```
{subject_desc}，{environment}，{lighting}，{style}风格，高质量，{aspect_ratio}
```"""

IMAGE_PROMPT_EXAMPLE = """### 示例

**场景：黄昏决斗**
- Gemini：`A middle-aged warrior in worn leather armor stands at the edge of a cliff at sunset, wide shot with dramatic backlighting, golden hour lighting, cinematic composition, photorealistic, 8K`
- 豆包：`中年战士穿着破损皮甲站在悬崖边缘，夕阳逆光，金色光线洒落，远处有山峦剪影，黄昏天空云层绚丽，电影写实风格，高质量，16:9`"""

# ============================================================================
# 视频生成提示词模板（Seedance 2.0 / Veo）
# ============================================================================

VIDEO_PROMPT_INTRO = """## 🎥 AI视频生成提示词

基于以上分镜设计，为每个镜头生成AI视频提示词。

### 提示词构建指南

#### Seedance 2.0 最佳实践（6步公式）
```
[镜头类型]：[描述景别和运动方式]
[主体]：[描述角色外貌、服装、状态]
[动作]：[精确描述动作和运动轨迹]
[环境]：[场景环境、天气、时间]
[风格]：[视觉风格、色调、氛围]
[运镜]：[摄像机运动方式]
[负面提示词]：[不希望出现的元素]
```

#### Veo 最佳实践（管道符分隔格式）
```
[主体]：[描述] | [动作]：[描述] | [场景]：[描述]
[运镜]：[描述] | [风格]：[描述] | [音频]：[描述]
[负面提示词]：[描述]
```

### 关键注意事项
- Seedance 2.0 支持首帧/尾帧描述，可用于控制运动起止状态
- Veo 使用管道符 `|` 分隔不同维度，每个维度保持简洁
- 动作描述要精确到位，避免"走来走去"等模糊表达
- 负面提示词用于排除不希望出现的元素（如：模糊、抖动、变形）
"""

SEEDANCE_VIDEO_PROMPT_FORMAT = """### Seedance 2.0 Prompt（镜头{shot_number}）
```
[镜头类型]：{shot_type}
[主体]：{subject}
[动作]：{action}
[环境]：{environment}
[风格]：{style}
[运镜]：{camera}
[负面提示词]：{negative_prompt}
```"""

VEO_VIDEO_PROMPT_FORMAT = """### Veo Prompt（镜头{shot_number}）
```
[主体]：{subject} | [动作]：{action} | [场景]：{environment}
[运镜]：{camera} | [风格]：{style} | [音频]：{audio}
[负面提示词]：{negative_prompt}
```"""

# ============================================================================
# 聚合模板：虚拟模式完整输出
# ============================================================================

VIRTUAL_MODE_FULL_TEMPLATE = """{storyboard_section}

---

{image_prompt_section}

---

{video_prompt_section}

---

> 💡 **提示**：以上为 AI 生成参考提示词。实际使用时请根据具体角色设定和场景需求调整参数。
> 场景图建议使用 Gemini 或豆包生成后筛选最佳结果；
> 视频建议使用 Seedance 2.0 或 Veo 生成后手动剪辑拼接。
"""

# ============================================================================
# Seedance 2.0 全能参考模式 (Comprehensive Reference Mode)
# ============================================================================
# 全能参考模式假定用户已准备人物参考图、场景参考图、物品参考图，
# AI需提供：1) 这些参考图的图像生成提示词 2) 基于已有参考图的视频生成提示词

SEEDANCE_COMPREHENSIVE_REFERENCE_INTRO = """## 🎬 Seedance 2.0 全能参考模式（Comprehensive Reference Mode）

**核心理念**：Seedance 2.0 支持多模态输入（文本+图片+音频+视频），全能参考模式假定用户已完成以下准备工作：
- **人物参考图**：主要角色的定妆照或概念图（通过AI图像工具生成）
- **场景参考图**：关键场景的概念图/氛围图（通过AI图像工具生成）
- **物品参考图**：重要道具或物品的概念图（通过AI图像工具生成）

在此模式下，你需要生成以下三类内容：

### 1. 参考图生成提示词
请根据剧本内容，为每个人物、场景、物品生成可直接用于 AI 图像工具（Gemini / DALL·E / 豆包）的提示词。
- **关键要求**：提示词必须具体、可操作、无需二次加工。每个提示词应包含完整的外观描述、环境细节、光影氛围和风格标签。
- **知识补充**：如需确定特定历史时期服饰、建筑风格、器物形制等视觉细节，请根据你的知识库进行精确推理。若有不确定的历史/文化细节，请在提示词中使用通用的视觉描述而非编造专有名词。

### 2. 视频生成提示词
基于上述已生成的参考图，为每个关键镜头提供 Seedance 2.0 全能参考模式的视频生成提示词。
- **12字段完整性**：每个视频提示词必须包含全部12个字段，不可遗漏。
- **参考图引用**：在视频提示词中明确引用对应的人物参考图、场景参考图和物品参考图名称。

### 3. 输出质量要求
- 所有提示词必须使用英文专业视觉术语（角色名/场景名/物品名可保留中文）
- 视频提示词遵循 Seedance 2.0 官方格式规范
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
- **图像生成提示词**（请LLM根据以上人物信息，生成可直接用于 Gemini / DALL·E / 豆包 的英文/中文混合提示词）：
```
[角色名] character concept art, {subject_desc}, {costume_desc}, {pose_desc}, {lighting}, {style} style, portrait, high quality, character design sheet, {aspect_ratio}
```
> 请LLM将上述模板中的占位符替换为剧本中具体的人物描写，确保提示词能准确还原角色的视觉形象。"""

# 场景参考图提示词模板（指令式：请LLM根据剧本场景描述生成完整提示词）
SEEDANCE_SCENE_REF_PROMPT_FORMAT = """#### 场景参考图：{scene_name}
- **场景类型**：{scene_type}（日/夜景，室内/室外）
- **场景氛围**：{atmosphere}
- **关键元素**：{key_elements}
- **图像生成提示词**（请LLM根据以上场景信息，生成可直接用于 Gemini / DALL·E / 豆包 的英文/中文混合提示词）：
```
[场景名] environment concept art, {location_desc}, {time_weather}, {atmosphere_desc}, {composition}, {style} style, cinematic, high quality, {aspect_ratio}
```
> 请LLM将上述模板中的占位符替换为剧本中具体的场景描写，构图建议使用电影级术语（wide shot / medium shot / close-up / low angle 等）。"""

# 物品参考图提示词模板（指令式：请LLM根据剧本文本中的道具描述生成完整提示词）
SEEDANCE_PROP_REF_PROMPT_FORMAT = """#### 物品参考图：{prop_name}
- **物品描述**：{prop_description}
- **物品意义**：{prop_significance}
- **图像生成提示词**（请LLM根据以上道具信息，生成可直接用于 Gemini / DALL·E / 豆包 的英文/中文混合提示词）：
```
[道具名] prop concept art, {prop_desc}, {material}, {lighting}, {style} style, product photography, high quality, white background, {aspect_ratio}
```
> 请LLM将上述模板中的占位符替换为剧本文本中具体的道具描写，材质光影描述尽可能具体（如：磨砂金属、抛光玉石、做旧皮革等）。"""

# 基于参考图的视频生成提示词模板（指令式：请LLM根据剧本镜头设计生成完整12字段提示词）
SEEDANCE_VIDEO_FROM_REF_FORMAT = """#### Seedance 2.0 视频生成：{shot_name}
- **使用参考图**：
  - 人物参考：{character_refs}
  - 场景参考：{scene_ref}
  - 物品参考：{prop_refs}
- **Seedance 2.0 全能参考模式视频生成提示词**（请LLM根据剧本中的具体镜头设计，填写以下12字段）：
```
[参考模式]：全能参考
[人物参考图]：{character_refs}
[场景参考图]：{scene_ref}
[物品参考图]：{prop_refs}
[镜头类型]：{shot_type}
[主体动作]：{action}
[环境描述]：{environment}
[运镜方式]：{camera}
[风格要求]：{style}
[首帧描述]：{first_frame}
[尾帧描述]：{last_frame}
[负面提示词]：{negative_prompt}
```
> 请LLM确保12字段全部填写完整，首帧/尾帧描述要形成清晰的视觉起止点，运镜方式描述要具体（如：从全景缓慢推至中景，同时向右横摇45度）。"""

# 全能参考模式聚合模板（指令式引导版）
SEEDANCE_COMPREHENSIVE_TEMPLATE = """{reference_intro}

### 一、人物参考图生成提示词
请LLM根据当前单元剧本中出场的每位主要角色，按以下要求生成角色概念图提示词：
- 每位角色1-3张（正面全身、半身特写、动态姿势各一张）
- 提示词需包含：外貌特征、服装风格、姿态动作、光影氛围、风格标签、画幅比例
- 使用英文专业术语（角色名可保留中文），确保可直接用于AI图像工具

{character_refs_section}

### 二、场景参考图生成提示词
请LLM根据当前单元剧本中的每个关键场景，按以下要求生成场景概念图提示词：
- 每个场景1-2张（广角全景 + 局部特写各一张）
- 提示词需包含：地点描述、时间/天气、氛围基调、电影级构图术语、风格标签、画幅比例
- 构图描述使用英文电影术语（wide shot / medium shot / close-up / dutch angle 等）

{scene_refs_section}

### 三、物品参考图生成提示词
请LLM根据当前单元剧本中出现的重要道具/物品，按以下要求生成道具概念图提示词：
- 每个物品1张，白底产品图风格
- 提示词需包含：外观描述、材质质感、光影、风格标签、画幅比例
- 材质描述具体化（如：磨砂金属、抛光玉石、做旧皮革等）

{prop_refs_section}

### 四、基于参考图的视频生成提示词（Seedance 2.0 全能参考模式）
请LLM基于上述已生成的参考图，为当前单元的每个关键镜头生成 Seedance 2.0 全能参考模式的12字段视频提示词：
- 明确引用对应的人物/场景/物品参考图名称
- 每个镜头包含首帧/尾帧描述，形成清晰的视觉起止点
- 运镜方式具体描述（推拉摇移跟升降的具体参数）
- 动作描述精确到位，避免模糊表达

{video_refs_section}

---
> 💡 **使用说明**：
> 1. 先用参考图生成提示词通过 Gemini/DALL·E/豆包 生成对应的参考图
> 2. 将生成的参考图上传至 Seedance 2.0 作为参考输入
> 3. 使用视频生成提示词进行视频生成，Seedance 2.0 将自动融合参考图中的角色、场景和物品特征
> 4. 建议先测试关键镜头，确认效果后再批量生成
> 5. 如遇需要特定历史/文化知识的视觉细节，请利用已有知识进行推理补充，不确定时使用通用视觉描述
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
        完整的虚拟模式提示词段落
    """
    style_names = style_names or []
    unit_label = "集" if content_type == "series" else "场"
    style_tags = "、".join(style_names) if style_names else "通用"

    parts = []

    # 分镜设计引导
    placeholder_row = "| 1 | — | — | 待LLM根据剧本内容生成 | — | — |\n| ... | ... | ... | ... | ... | ... |"
    parts.append(f"""### 虚拟模式 — AI视频生成分镜设计

## 分镜设计要求
为当前{unit_label}的{scene_count}个关键场景设计分镜表，每个场景拆分为3-8个镜头。
风格参考：{style_tags}

{STORYBOARD_TEMPLATE.format(storyboard_rows=placeholder_row)}""")

    # 场景图提示词
    parts.append(IMAGE_PROMPT_INTRO)
    parts.append(IMAGE_PROMPT_EXAMPLE)

    # 视频提示词
    parts.append(VIDEO_PROMPT_INTRO)

    parts.append(f"""
请为每一场关键场景分别生成上述格式的生成提示词，确保视觉风格与已选风格维度（{style_tags}）保持一致。
""")

    return "\n".join(parts)


def get_image_prompt_templates() -> dict:
    """获取场景图提示词模板"""
    return {
        "gemini_format": GEMINI_IMAGE_PROMPT_FORMAT,
        "doubao_format": DOUBAO_IMAGE_PROMPT_FORMAT,
        "intro": IMAGE_PROMPT_INTRO,
        "example": IMAGE_PROMPT_EXAMPLE,
    }


def get_video_prompt_templates() -> dict:
    """获取视频提示词模板"""
    return {
        "seedance_format": SEEDANCE_VIDEO_PROMPT_FORMAT,
        "veo_format": VEO_VIDEO_PROMPT_FORMAT,
        "intro": VIDEO_PROMPT_INTRO,
    }


def get_comprehensive_ref_templates() -> dict:
    """获取Seedance 2.0全能参考模式模板"""
    return {
        "reference_intro": SEEDANCE_COMPREHENSIVE_REFERENCE_INTRO,
        "character_ref_format": SEEDANCE_CHARACTER_REF_PROMPT_FORMAT,
        "scene_ref_format": SEEDANCE_SCENE_REF_PROMPT_FORMAT,
        "prop_ref_format": SEEDANCE_PROP_REF_PROMPT_FORMAT,
        "video_from_ref_format": SEEDANCE_VIDEO_FROM_REF_FORMAT,
        "comprehensive_template": SEEDANCE_COMPREHENSIVE_TEMPLATE,
    }


def build_seedance_comprehensive_prompt(
    content_type: str,
    character_names: list = None,
    scene_names: list = None,
    prop_names: list = None,
    style_names: list = None,
    aspect_ratio: str = "16:9",
) -> str:
    """构建Seedance 2.0全能参考模式的完整提示词段落

    全能参考模式假设用户已拥有角色参考图、场景参考图、物品参考图，
    AI需要提供：
    1. 这些参考图的图像生成提示词（用于生成参考图）
    2. 基于已有参考图的视频生成提示词（Seedance 2.0格式）

    Args:
        content_type: "series"（剧集）或 "movie"（电影）
        character_names: 出场人物名称列表
        scene_names: 关键场景名称列表
        prop_names: 重要道具名称列表
        style_names: 已选风格名称列表
        aspect_ratio: 画面比例，默认16:9

    Returns:
        完整的全能参考模式提示词段落
    """
    character_names = character_names or []
    scene_names = scene_names or []
    prop_names = prop_names or []
    style_names = style_names or []
    unit_label = "集" if content_type == "series" else "场"
    style_tags = "、".join(style_names) if style_names else "通用"

    parts = [SEEDANCE_COMPREHENSIVE_REFERENCE_INTRO]

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

    # 四、基于参考图的视频生成提示词
    parts.append("### 四、基于参考图的视频生成提示词（Seedance 2.0 全能参考模式）")
    parts.append(f"（基于上述已生成的人物/场景/物品参考图，为每个镜头提供 Seedance 2.0 全能参考模式格式的视频生成提示词）")
    parts.append("")
    parts.append(f"> 请LLM为每个关键场景的每个镜头，在视频提示词中明确引用对应的人物参考图名称、场景参考图名称和物品参考图名称。")
    parts.append(f"> 视频风格参考：{style_tags}")
    parts.append("")

    # 使用说明
    parts.append("---")
    parts.append("> 💡 **使用说明**：")
    parts.append("> 1. 先用参考图生成提示词通过 Gemini/DALL·E/豆包 生成对应的参考图")
    parts.append("> 2. 将生成的参考图上传至 Seedance 2.0 作为参考输入")
    parts.append("> 3. 使用视频生成提示词进行视频生成，Seedance 2.0 将自动融合参考图中的角色、场景和物品特征")
    parts.append("> 4. 建议先测试关键镜头，确认效果后再批量生成")

    return "\n".join(parts)
