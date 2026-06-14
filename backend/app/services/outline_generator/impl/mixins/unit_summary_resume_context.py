"""大纲生成器 - 续生成上下文构建与提示词Mixin"""
from typing import Dict
from typing import Any
import re


class UnitSummaryResumeContextMixin:
    """续生成上下文构建与提示词"""

    def _build_resume_context(
        self,
        existing_parsed: Dict[str, Dict[str, Any]],
        start_from_unit: int,
        content_type: str,
        narrative_mode: str = "serialized"
    ) -> str:
        """
        构建续生成的上下文（增强版 v2）

        提供三层上下文信息，确保续生成内容与前文高度连贯：
        1. 全局概览：开头3章 + 关键转折 + 最近章节的标题、一句话摘要和主要角色
        2. 详细参考：前5章完整梗概 + 结构化上下文（角色状态、情节线、情感基调、直接衔接点）
        3. 续生成指令：明确的接续起点、情节衔接、伏笔回收和连贯性要求
        """
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场",
                      "movie_outline": "场", "series_outline": "集"}.get(
            content_type, "章"
        )

        existing_count = len(existing_parsed)

        # ===== 提取结构化上下文信息 =====
        structured = self._extract_structured_context(
            existing_parsed, start_from_unit, content_type
        )

        # ===== 第一层：全局概览（所有章节的标题+一句话摘要+角色）=====
        overview_units = []
        for num in range(1, start_from_unit):
            if str(num) in existing_parsed:
                unit = existing_parsed[str(num)]
                title = unit.get('title', f'第{num}{unit_label}')
                summary = unit.get('summary', '')
                # 一句话摘要：取summary的前80字
                one_liner = summary[:80] + \
                    '...' if len(summary) > 80 else summary
                overview_entry = f"第{num}{unit_label}《{title}》：{one_liner}"
                overview_units.append(overview_entry)

        # 如果章节过多，只取开头3章 + 中间关键转折 + 最后5章的概览
        if len(overview_units) > 20:
            head = overview_units[:3]
            tail = overview_units[-5:]
            mid_start = len(overview_units) // 2 - 1
            mid = overview_units[mid_start:mid_start + 2]
            overview_display = head + \
                ['...（中间章节省略）...'] + mid + ['...（中间章节省略）...'] + tail
        else:
            overview_display = overview_units

        overview_text = chr(10).join(
            overview_display) if overview_display else "（无前文）"

        # ===== 第二层：详细参考（前5章完整梗概 + 结构化上下文）=====
        context_units = []
        start_num = max(1, start_from_unit - 5)
        for num in range(start_num, start_from_unit):
            if str(num) in existing_parsed:
                unit = existing_parsed[str(num)]
                title = unit.get('title', '')
                summary = unit.get('summary', '')
                full_content = unit.get('full_content', '')

                # 使用更丰富的内容作为参考
                # 优先使用 full_content 中的梗概部分
                if full_content and len(full_content) > len(summary) + 50:
                    import re
                    # [2026-05-05] 修复：根据 content_type 使用正确的梗概标签
                    # novel→本章梗概, series→本集梗概, movie→本场梗概
                    summary_label = {"novel": "本章", "series_script": "本集", "series_outline": "本集",
                                     "movie_script": "本场", "movie_outline": "本场"}.get(content_type, "本章")
                    summary_match = re.search(
                        rf'\*\*{summary_label}梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
                        full_content, re.DOTALL
                    )
                    if summary_match:
                        summary = summary_match.group(1).strip()

                context_entry = f"第{num}{unit_label}《{title}》\n梗概：{summary}"
                context_units.append(context_entry)

        detail_text = chr(10).join(
            context_units) if context_units else "（无详细参考）"

        # ===== 构建结构化上下文补充信息 =====
        # 角色信息
        characters_text = chr(10).join(
            f"  - {c}" for c in structured['active_characters']
        ) if structured['active_characters'] else "  （未检测到活跃角色）"

        # 情节线信息
        plot_lines_text = chr(10).join(
            f"  - {p}" for p in structured['open_plot_lines']
        ) if structured['open_plot_lines'] else "  （无明确的未解决情节线）"

        # 最后一章衔接点
        last_chapter_info = ""
        if structured['last_chapter_title']:
            last_chapter_info = (
                f"第{start_from_unit - 1}{unit_label}《{structured['last_chapter_title']}》\n"
                f"完整梗概：{structured['last_chapter_summary']}"
            )
        else:
            last_chapter_info = "（无前文章节）"

        # ===== 第三层：续生成指令（增强版）=====
        # 根据叙事模式调整续生成要求
        if narrative_mode == "episodic":
            requirements_text = f"""【续生成要求】
请从第{start_from_unit}{unit_label}开始继续生成后续章节概述。
关键要求：
1. 每{unit_label}为独立故事单元，不需要与前一{unit_label}的情节直接衔接
2. 每{unit_label}应有独立完整的故事结构（开端、发展、高潮、结尾）
3. 人物基本设定保持一致，但每{unit_label}的故事情节独立
4. 参考全局大纲中第{start_from_unit}{unit_label}之后的情节分配
5. 保持与前文相同的叙事风格和基调
"""
        elif narrative_mode == "episodic_with_arc":
            requirements_text = f"""【续生成要求 — 主线串联单元剧模式】
请从第{start_from_unit}{unit_label}开始继续生成后续章节概述。
关键要求：
1. 每{unit_label}为独立故事单元，应有独立完整的故事结构
2. 在每{unit_label}中自然融入主线线索或与常驻角色的互动
3. 人物基本设定和主线相关角色状态保持一致
4. 主线伏笔和线索应在后续{unit_label}中继续推进
5. 参考全局大纲中第{start_from_unit}{unit_label}之后的情节分配
6. 保持与前文相同的叙事风格和基调
"""
        else:
            requirements_text = f"""【续生成要求】
请从第{start_from_unit}{unit_label}开始继续生成后续章节概述。
关键要求：
1. 第{start_from_unit}{unit_label}必须与第{start_from_unit - 1}{unit_label}的情节自然衔接，从上一章结尾的情境继续发展
2. 人物状态和关系必须与「活跃角色状态」中描述的一致，不得出现状态矛盾
3. 「未解决的情节线索」中的伏笔和悬念必须在后续章节中继续发展或回收
4. 情感基调应从「{structured['emotion_tone']}」自然过渡，不宜突变
5. 参考全局大纲中第{start_from_unit}{unit_label}之后的情节分配
6. 保持与前文相同的叙事风格和节奏
"""

        context = f"""【全局概览（已生成第1-{existing_count}{unit_label}）】
{overview_text}

【前文详细参考（最后{len(context_units)}{unit_label}）】
{detail_text}

【直接衔接点（第{start_from_unit - 1}{unit_label}完整梗概）】
{last_chapter_info}

【活跃角色状态】
{characters_text}

【未解决的情节线索】
{plot_lines_text}

【当前情感基调】
{structured['emotion_tone']}

{requirements_text}"""
        return context


    def _build_resume_prompt(
        self,
        module_name: str,
        global_outline: str,
        context_prefix: str,
        start_from_unit: int,
        unit_count: int,
        content_type: str,
        series_type: str = None,
        episode_duration_range: str = None,
        title_style: str = None,  # 标题风格ID（新增）
        title_style_name: str = None,  # 标题风格名称（新增）
        unit_label: str = None,  # 单元标签（新增）
        narrative_mode: str = "serialized"  # 叙事模式（新增）
    ) -> str:
        """构建续生成的提示词"""
        if not unit_label:
            unit_label = {"novel": "章", "series_script": "集", "movie_script": "场",
                          "movie_outline": "场", "series_outline": "集"}.get(
                content_type, "章"
            )

        units_to_generate = unit_count - start_from_unit + 1

        input_params = {
            "global_outline": global_outline + "\n\n" + context_prefix,
            "chapter_count": str(units_to_generate),
            "episode_count": str(units_to_generate),
            "scene_count": str(units_to_generate),
            "series_type": series_type or "网剧",
            "movie_type": series_type or "电影",
            "episode_duration_range": episode_duration_range or "30-45分钟",
            "duration_range": episode_duration_range or "90-120分钟",
            "script_mode": "virtual",
            "unit_label": unit_label  # 新增：单元标签变量
        }

        # 生成标题风格指导文本（新增）
        if title_style:
            from app.agents.writing.prompts.title_style_guidance import get_title_style_guidance
            title_style_guidance = get_title_style_guidance(
                title_style, title_style_name or "")
            input_params["title_style_guidance"] = title_style_guidance
            self.logger.info(
                f"[单元概述续生成] 使用标题风格: {title_style_name} ({title_style})")
        else:
            input_params["title_style_guidance"] = ""

        prompt_template = self.prompt_manager.get_default_prompt(module_name)
        filled_prompt = self.prompt_manager.render_prompt(
            prompt_template, input_params, module_name
        )

        # 章节边界识别机制（v4.0正向版）- 放在全局大纲之前
        boundary_constraint_resume = f"""# 章节边界指引（请首先阅读）

## 全局大纲中的单元内容规划

全局大纲包含【单元内容规划】部分，其中为每个单元分配了专属内容。在开始创作之前，请先做以下工作：

### 第一步：定位单元内容规划
在全局大纲中找到【单元内容规划】部分，这是每个单元最细粒度的内容分配。

### 第二步：建立单元内容映射
为每个单元建立明确的内容归属，例如：

| 单元范围 | 本单元专属内容 |
|---------|------------|
| 第1-10章 | 主角初入江湖，结识伙伴 |
| 第11-30章 | 江湖历练，逐渐成长 |
| 第91-98章 | 战前部署，各方势力集结 |
| 第99-100章 | 平播之战一触即发。第一部完。 |

### 第三步：逐单元细化原则
- 每个单元只展开其编号范围内【单元内容规划】分配的内容
- 第98章只写到"战前准备完毕，即将开战"为止
- 第99章开始才展开平播之战的实际过程
- 如果【单元内容规划】中某个事件在第50章才出现，在第30章时仅为该事件做铺垫和伏笔

### 核心创作原则
你的创造性体现在**如何写**（场景描写、对话设计、情感渲染），而非**写什么**（事件、角色、结果——这些由【单元内容规划】决定）。

---

# 全局大纲（请据此创作）

"""
        
        # 前置边界约束
        filled_prompt = boundary_constraint_resume + filled_prompt

        # 添加续生成指引（v4.0正向版）
        # [2026-05-05] 修复：输出格式中硬编码"章"改为使用 unit_label，
        # 确保剧集/电影续生成时 LLM 输出正确的格式术语（集/场）
        # 构建内容类型特定的输出格式
        is_movie = content_type in ("movie_script", "movie_outline")
        is_series = content_type in ("series_script", "series_outline")

        if is_movie:
            output_format = f"""```
**第{start_from_unit}{unit_label}：[场景标题]**

**场景信息**：
- 地点：[内景/外景 具体地点]
- 时间：[日/夜/晨/暮]
- 在场角色：[主要角色]

**本场梗概**：[本场情节概述]

**情节要点**：
- 开篇情境：[本场开头的场景/情境]
- 核心冲突：[本场的主要矛盾]
- 关键转折：[本场的重要转折点]

**本场看点**：[吸引观众的关键点]

**情感基调**：[本场的情感氛围]

**时长估算**：约[X]分钟

**🎥 影视化指导**：
- **镜头语言**：[本场推荐的拍摄手法和摄影机运动，如：开场用推轨建立空间/对峙用正反打特写/高潮用手持摄影增加紧张感]
- **场景转场**：[本场与前后场的转换方式，如：切/淡入/声音先入/匹配剪辑]
- **视觉色调**：[本场视觉风格与色调，如：冷蓝色调+低饱和度/暖金色逆光/暗绿色阴影]
- **声音设计**：[本场声音/配乐的情感方向，如：低音弦乐营造不安/钢琴独奏烘托温情]

**🔴 人物状态变化标注**：
> 如本场有角色状态发生重要变化，必须在此明确标注：

| 角色 | 变化类型 | 变化前 | 变化后 | 变化原因/事件 | 视觉呈现建议 |
|-----|---------|-------|-------|-------------|------------|
| [角色名] | [能力/身份/地点/性格/关系/称呼/台词风格] | [变化前] | [变化后] | [触发变化的本场情节] | [如何通过摄影/表演呈现] |

*注：如本场无重要状态变化，可写"本场无重要人物状态变化"*

---

**第{start_from_unit + 1}{unit_label}：[场景标题]**

**场景信息**：
- 地点：...
- 时间：...
- 在场角色：...

**本场梗概**：...

**情节要点**：
- ...

**本场看点**：...

**情感基调**：...

**时长估算**：...

**🎥 影视化指导**：
- **镜头语言**：...
- **场景转场**：...
- **视觉色调**：...
- **声音设计**：...

**🔴 人物状态变化标注**：...

---

（继续直到第{unit_count}{unit_label}）
```"""
        elif is_series:
            output_format = f"""```
**第{start_from_unit}{unit_label}：[{unit_label}节标题]**

**本集梗概**：[本集情节概述]

**情节要点**：
- 开篇情境：[本集开头的场景/情境]
- 核心冲突：[本集的主要矛盾]
- 关键转折：[本集的重要转折点]

**本集看点**：[吸引观众的关键点]

**结尾钩子**：[如何引发观众继续观看的欲望——必须设计为强悬念]

**情感基调**：[本集的情感氛围]

**时长分配**：约[X]分钟（必须在「{episode_duration_range or "30-45分钟"}」范围内）

**🎬 影视化指导**：
- **镜头语言**：[本集关键场景推荐的拍摄手法，如：开场用航拍建立空间感/对峙用特写+浅景深/追逐用跟拍+快速剪辑]
- **场景转场**：[本集关键场景转换方式，如：从室内到室外用门框匹配剪辑/时间跳跃用叠化/情绪转折用声音先入]
- **视觉色调**：[本集主视觉风格，如：冷蓝色调+高对比度/暖金色调+柔光/暗绿色调+低饱和度]
- **节奏分配**：开场[X]分钟 → 发展[X]分钟 → 高潮[X]分钟 → 结尾[X]分钟

**🔴 人物状态变化标注**：
> 如本集有角色状态发生重要变化，必须在此明确标注：

| 角色 | 变化类型 | 变化前 | 变化后 | 变化原因/事件 | 视觉呈现建议 |
|-----|---------|-------|-------|-------------|------------|
| [角色名] | [能力/身份/地点/性格/关系/称呼/台词风格] | [变化前] | [变化后] | [触发变化的本集情节] | [如何通过画面/表演呈现] |

*注：如本集无重要状态变化，可写"本集无重要人物状态变化"*

---

**第{start_from_unit + 1}{unit_label}：[{unit_label}节标题]**

**本集梗概**：...

**情节要点**：
- 开篇情境：...
- 核心冲突：...
- 关键转折：...

**本集看点**：...

**结尾钩子**：...

**情感基调**：...

**时长分配**：...

**🎬 影视化指导**：
- **镜头语言**：...
- **场景转场**：...
- **视觉色调**：...
- **节奏分配**：...

**🔴 人物状态变化标注**：...

---

（继续直到第{unit_count}{unit_label}）
```"""
        else:
            # novel: 简洁格式但保持**标记
            output_format = f"""```
**第{start_from_unit}{unit_label}：[{unit_label}节标题]**

**本章梗概**：[本章情节概述]

---

**第{start_from_unit + 1}{unit_label}：[{unit_label}节标题]**

**本章梗概**：[本章情节概述]

---

（继续直到第{unit_count}{unit_label}）
```"""

        filled_prompt += f"""

---

## 续生成指引

### 当前进度
- **已完成**：第1-{start_from_unit - 1}{unit_label}（共{start_from_unit - 1}{unit_label}）
- **本次任务**：生成第{start_from_unit}-{unit_count}{unit_label}（共{units_to_generate}{unit_label}）

### 生成规则
1. 从第{start_from_unit}{unit_label}开始，按顺序逐{unit_label}生成到第{unit_count}{unit_label}
2. 恰好生成{units_to_generate}个{unit_label}节，编号连续：{start_from_unit}, {start_from_unit + 1}, {start_from_unit + 2}, ..., {unit_count}

### 衔接要求
{self._build_resume_connection_requirements(narrative_mode, start_from_unit, unit_label, unit_count)}

### 逐{unit_label}细化指南

你的任务是**将【单元内容规划】细化为详细的单元概述**，以下原则帮助你在正确的范围内创作：

1. **忠于大纲内容**
   - 【单元内容规划】中已列出的事件，你负责细化、展开和丰富
   - 【单元内容规划】中的人物、地点、事件走向均已确定，你负责将它们写得更生动

2. **尊重内容归属**
   - 每个单元只涵盖其编号范围内【单元内容规划】分配的内容
   - 例如：【单元内容规划】中"第99-100{unit_label}：平播之战一触即发"意味着第98{unit_label}写到"战前准备完毕"即可
   - 例如：【单元内容规划】中某个事件在第50{unit_label}才出现，在第5{unit_label}时只需为该事件做铺垫

3. **创造性范围**
   - 你可以发挥创造力的地方：场景如何描写、对话如何设计、情感如何渲染
   - 由【单元内容规划】决定的地方：发生什么事件、谁参与、事件的结果

4. **逐单元自查指南**
   - 本单元的编号范围在【单元内容规划】中对应什么内容？
   - 我写的内容是否恰好覆盖了这些内容？
   - 下一单元将展开的事件，本单元是否做好了合理的铺垫和过渡？

### 输出完整性保障
- 当你感知到输出即将达到token上限时，确保最后一个单元概述是**完整**的
- 如果无法完成下一单元完整概述，在当前单元完成后停止
- 未生成的单元可通过续生成机制补全

### 输出格式
{output_format}
"""

        return filled_prompt

    # ==================== 分层质量管控方法 ====================


    def _extract_structured_context(
        self,
        existing_parsed: Dict[str, Dict[str, Any]],
        start_from_unit: int,
        content_type: str
    ) -> Dict[str, Any]:
        """
        从已有章节中提取结构化上下文信息

        提取四类关键信息，用于增强续生成的连贯性：
        1. 角色追踪：主要角色及其最新状态
        2. 情节线追踪：活跃的和已关闭的情节线
        3. 情感基调追踪：最后一章的情感基调
        4. 直接衔接点：最后一章的完整梗概

        Args:
            existing_parsed: 已解析的单元数据
            start_from_unit: 续生成起始章节号
            content_type: 内容类型

        Returns:
            结构化上下文字典
        """
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场",
                      "movie_outline": "场", "series_outline": "集"}.get(
            content_type, "章"
        )

        existing_count = len(existing_parsed)

        # ===== 1. 角色追踪 =====
        # 从最后5章的 full_content 中提取角色出场信息
        character_mentions = {}  # {角色名: 最近出现章节号}
        character_states = {}    # {角色名: 最新状态描述}

        recent_start = max(1, start_from_unit - 5)
        for num in range(recent_start, start_from_unit):
            if str(num) not in existing_parsed:
                continue
            unit = existing_parsed[str(num)]
            full_content = unit.get(
                'full_content', '') or unit.get('summary', '')
            summary = unit.get('summary', '')

            # 从梗概中提取角色名（简单启发式：中文人名通常是2-3字）
            # 使用常见的角色引出词匹配
            import re
            # 匹配格式如：张三、李四 或 张三与李四 或 张三被/将/把/在
            name_patterns = re.findall(
                r'[\u4e00-\u9fff]{2,4}(?=[，。、与和被将把在从向对给让又或者的])',
                summary
            )
            # 过滤常见非人名词汇
            stop_words = {'这时', '此时', '然而', '但是', '因此', '于是', '虽然',
                          '尽管', '不过', '而且', '并且', '或者', '同时', '随后',
                          '最终', '突然', '原来', '终于', '忽然', '显然', '似乎',
                          '正在', '已经', '即将', '渐渐', '默默', '缓缓', '悄悄',
                          '此刻', '随后', '后来', '之后', '之前', '期间', '当中',
                          '其中', '这里', '那里', '这个', '那个', '一个', '另一'}
            for name in name_patterns:
                if name not in stop_words and len(name) >= 2:
                    character_mentions[name] = num

            # 从梗概中提取角色状态变化（格式如：张三...变得/发现/决定/意识到...）
            state_patterns = re.findall(
                r'([\u4e00-\u9fff]{2,4})(?:变得|发现|决定|意识到|终于|开始|逐渐|学会了|成长为|蜕变为|转变为)([^，。！？]{2,20})',
                summary
            )
            for char_name, state_desc in state_patterns:
                if char_name not in stop_words and len(char_name) >= 2:
                    character_states[char_name] = state_desc.strip()

        # 构建角色信息列表（按最近出现排序）
        active_characters = []
        for name, last_chapter in sorted(
            character_mentions.items(), key=lambda x: x[1], reverse=True
        )[:10]:  # 最多追踪10个角色
            char_info = f"{name}（最近出现于第{last_chapter}{unit_label}）"
            if name in character_states:
                char_info += f" - {character_states[name]}"
            active_characters.append(char_info)

        # ===== 2. 情节线追踪 =====
        # 从所有章节中提取关键情节线索（基于梗概中的关键词）
        plot_keywords = ['伏笔', '悬念', '秘密', '谜团', '阴谋', '真相', '线索',
                         '承诺', '约定', '使命', '目标', '计划', '预言', '诅咒']
        open_plot_lines = []  # 未解决的情节线

        # 检查最后5章中是否有引入但未解决的情节线
        for num in range(recent_start, start_from_unit):
            if str(num) not in existing_parsed:
                continue
            unit = existing_parsed[str(num)]
            summary = unit.get('summary', '')
            for keyword in plot_keywords:
                if keyword in summary:
                    # 提取包含关键词的句子
                    sentences = re.split(r'[。！？]', summary)
                    for sentence in sentences:
                        if keyword in sentence and len(sentence.strip()) > 5:
                            open_plot_lines.append(
                                f"第{num}{unit_label}: {sentence.strip()[:60]}"
                            )
                            break  # 每章每个关键词只取一个

        # 去重，最多保留8条
        seen = set()
        unique_plot_lines = []
        for line in open_plot_lines:
            if line not in seen:
                seen.add(line)
                unique_plot_lines.append(line)
        unique_plot_lines = unique_plot_lines[:8]

        # ===== 3. 情感基调追踪 =====
        # 从最后一章提取情感基调
        last_unit = existing_parsed.get(str(start_from_unit - 1), {})
        last_summary = last_unit.get('summary', '')

        emotion_keywords = {
            '紧张': ['紧张', '危机', '危险', '威胁', '紧迫', '焦虑'],
            '悲伤': ['悲伤', '痛苦', '失去', '牺牲', '离别', '绝望'],
            '愤怒': ['愤怒', '暴怒', '仇恨', '报复', '不甘', '愤慨'],
            '温馨': ['温馨', '感动', '温暖', '守护', '陪伴', '关怀'],
            '欢乐': ['欢乐', '喜悦', '庆祝', '胜利', '团聚', '欢笑'],
            '悬疑': ['悬疑', '疑惑', '未知', '谜团', '暗藏', '诡异'],
            '壮阔': ['壮阔', '史诗', '壮观', '宏大', '磅礴', '震撼']
        }

        detected_emotions = []
        for emotion, keywords in emotion_keywords.items():
            for kw in keywords:
                if kw in last_summary:
                    detected_emotions.append(emotion)
                    break

        emotion_desc = '、'.join(
            detected_emotions) if detected_emotions else '平稳'

        # ===== 4. 直接衔接点 =====
        # 最后一章的完整梗概
        last_chapter_title = last_unit.get('title', '')
        last_chapter_summary = last_summary
        # 如果有 full_content 且比 summary 更丰富，使用 full_content 的前200字
        last_full_content = last_unit.get('full_content', '')
        if last_full_content and len(last_full_content) > len(last_summary) + 50:
            # full_content 更丰富，提取梗概部分作为衔接参考
            # [2026-05-05] 修复：根据 content_type 使用正确的梗概标签
            summary_label = {"novel": "本章", "series_script": "本集", "series_outline": "本集",
                             "movie_script": "本场", "movie_outline": "本场"}.get(content_type, "本章")
            summary_match = re.search(
                rf'\*\*{summary_label}梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
                last_full_content, re.DOTALL
            )
            if summary_match:
                last_chapter_summary = summary_match.group(1).strip()

        return {
            'active_characters': active_characters,
            'open_plot_lines': unique_plot_lines,
            'emotion_tone': emotion_desc,
            'last_chapter_title': last_chapter_title,
            'last_chapter_summary': last_chapter_summary,
            'existing_count': existing_count
        }

    def _build_resume_connection_requirements(
        self,
        narrative_mode: str,
        start_from_unit: int,
        unit_label: str,
        unit_count: int
    ) -> str:
        """构建续生成的衔接要求文本

        根据叙事模式返回不同的衔接要求：
        - serialized: 强制跨集连续性（原有行为）
        - episodic: 每集完全独立，不强制衔接
        - episodic_with_arc: 各集独立故事，但保持主线线索和常驻角色一致性
        """
        if narrative_mode == "episodic":
            return (
                f"- 每{unit_label}为独立故事单元，不强制与前一{unit_label}的情节衔接\n"
                f"- 每{unit_label}应有独立完整的故事结构\n"
                f"- 人物基本设定保持一致，但各{unit_label}情节独立\n"
                f"- 参考全局大纲中第{start_from_unit}-{unit_count}{unit_label}的情节分配"
            )
        if narrative_mode == "episodic_with_arc":
            return (
                f"- 每{unit_label}为独立故事单元，不强制与前一{unit_label}的情节衔接\n"
                f"- 每{unit_label}应有独立完整的故事结构\n"
                f"- 在每{unit_label}中自然融入主线线索或常驻角色互动\n"
                f"- 人物基本设定和主线相关角色状态保持一致\n"
                f"- 主线伏笔和线索应在后续{unit_label}中继续推进或回收\n"
                f"- 参考全局大纲中第{start_from_unit}-{unit_count}{unit_label}的情节分配"
            )
        return (
            f"- 第{start_from_unit}{unit_label}从前一{unit_label}结尾情境自然延续发展\n"
            f"- 人物状态、关系发展与前文保持一致\n"
            f"- 前文埋下的伏笔和线索在后续{unit_label}节中继续推进或回收\n"
            f"- 参考全局大纲中第{start_from_unit}-{unit_count}{unit_label}的情节分配"
        )

