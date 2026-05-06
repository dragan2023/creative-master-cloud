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
