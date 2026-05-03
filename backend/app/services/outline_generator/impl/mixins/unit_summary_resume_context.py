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
        content_type: str
    ) -> str:
        """
        构建续生成的上下文（增强版 v2）

        提供三层上下文信息，确保续生成内容与前文高度连贯：
        1. 全局概览：开头3章 + 关键转折 + 最近章节的标题、一句话摘要和主要角色
        2. 详细参考：前5章完整梗概 + 结构化上下文（角色状态、情节线、情感基调、直接衔接点）
        3. 续生成指令：明确的接续起点、情节衔接、伏笔回收和连贯性要求
        """
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
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
                    summary_match = re.search(
                        r'\*\*本章梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
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

【续生成要求】
请从第{start_from_unit}{unit_label}开始继续生成后续章节概述。
关键要求：
1. 第{start_from_unit}{unit_label}必须与第{start_from_unit - 1}{unit_label}的情节自然衔接，从上一章结尾的情境继续发展
2. 人物状态和关系必须与「活跃角色状态」中描述的一致，不得出现状态矛盾
3. 「未解决的情节线索」中的伏笔和悬念必须在后续章节中继续发展或回收
4. 情感基调应从「{structured['emotion_tone']}」自然过渡，不宜突变
5. 参考全局大纲中第{start_from_unit}{unit_label}之后的情节分配
6. 保持与前文相同的叙事风格和节奏
"""
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
        unit_label: str = None  # 单元标签（新增）
    ) -> str:
        """构建续生成的提示词"""
        if not unit_label:
            unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
                content_type, "章"
            )

        units_to_generate = unit_count - start_from_unit + 1

        input_params = {
            "global_outline": global_outline + "\n\n" + context_prefix,
            "chapter_count": str(units_to_generate),
            "episode_count": str(units_to_generate),
            "series_type": series_type or "网剧",
            "episode_duration_range": episode_duration_range or "30-45分钟",
            "unit_label": unit_label  # 新增：单元标签变量
        }

        # 生成标题风格指导文本（新增）
        if content_type == "novel" and title_style:
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

## 全局大纲中的分章结构

全局大纲包含【分章大纲】部分，其中为每个章节分配了专属内容。在开始创作之前，请先做以下工作：

### 第一步：定位分章大纲
在全局大纲中找到【分章大纲】部分，这是每个章节最细粒度的内容分配。

### 第二步：建立章节内容映射
为每个章节建立明确的内容归属，例如：

| 章节范围 | 本章专属内容 |
|---------|------------|
| 第1-10章 | 主角初入江湖，结识伙伴 |
| 第11-30章 | 江湖历练，逐渐成长 |
| 第91-98章 | 战前部署，各方势力集结 |
| 第99-100章 | 平播之战一触即发。第一部完。 |

### 第三步：逐章细化原则
- 每一章只展开其编号范围内分章大纲分配的内容
- 第98章只写到"战前准备完毕，即将开战"为止
- 第99章开始才展开平播之战的实际过程
- 如果分章大纲中某个事件在第50章才出现，在第30章时仅为该事件做铺垫和伏笔

### 核心创作原则
你的创造性体现在**如何写**（场景描写、对话设计、情感渲染），而非**写什么**（事件、角色、结果——这些由分章大纲决定）。

---

# 全局大纲（请据此创作）

"""
        
        # 前置边界约束
        filled_prompt = boundary_constraint_resume + filled_prompt

        # 添加续生成指引（v4.0正向版）
        filled_prompt += f"""

---

## 续生成指引

### 当前进度
- **已完成**：第1-{start_from_unit - 1}{unit_label}（共{start_from_unit - 1}章）
- **本次任务**：生成第{start_from_unit}-{unit_count}{unit_label}（共{units_to_generate}章）

### 生成规则
1. 从第{start_from_unit}{unit_label}开始，按顺序逐章生成到第{unit_count}{unit_label}
2. 恰好生成{units_to_generate}个章节，编号连续：{start_from_unit}, {start_from_unit + 1}, {start_from_unit + 2}, ..., {unit_count}

### 衔接要求
- 第{start_from_unit}{unit_label}从上一章结尾情境自然延续发展
- 人物状态、关系发展与前文保持一致
- 前文埋下的伏笔和线索在后续章节中继续推进或回收
- 参考全局大纲中第{start_from_unit}-{unit_count}{unit_label}的情节分配

### 逐章细化指南

你的任务是**将分章大纲细化为详细的章节概述**，以下原则帮助你在正确的范围内创作：

1. **忠于大纲内容**
   - 分章大纲中已列出的事件，你负责细化、展开和丰富
   - 分章大纲中的人物、地点、事件走向均已确定，你负责将它们写得更生动

2. **尊重内容归属**
   - 每个章节只涵盖其编号范围内分章大纲分配的内容
   - 例如：分章大纲中"第99-100章：平播之战一触即发"意味着第98章写到"战前准备完毕"即可
   - 例如：分章大纲中某个事件在第50章才出现，在第5章时只需为该事件做铺垫

3. **创造性范围**
   - 你可以发挥创造力的地方：场景如何描写、对话如何设计、情感如何渲染
   - 由分章大纲决定的地方：发生什么事件、谁参与、事件的结果

4. **逐章自查指南**
   - 本章的编号范围在分章大纲中对应什么内容？
   - 我写的内容是否恰好覆盖了这些内容？
   - 下一章将展开的事件，本章是否做好了合理的铺垫和过渡？

### 输出完整性保障
- 当你感知到输出即将达到token上限时，确保最后一个章节概述是**完整**的
- 如果无法完成下一章完整概述，在当前章节完成后停止
- 未生成的章节可通过续生成机制补全

### 输出格式
```
第{start_from_unit}章 [章节标题]
梗概：[本章情节概述]
...

第{start_from_unit + 1}章 [章节标题]
梗概：[本章情节概述]
...

（继续直到第{unit_count}章）
```
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
        unit_label = {"novel": "章", "series_script": "集", "movie_script": "场"}.get(
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
            summary_match = re.search(
                r'\*\*本章梗概\*\*[：:]\s*(.+?)(?:\n\n|\n\*\*|$)',
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


