"""
质量修正生成器 - 使用LLM生成智能修正方案

功能:
1. 分析问题类型和位置
2. 结合全局大纲、人物设定、世界观生成修正内容
3. 确保修正内容与上下文逻辑自洽
4. 提供修正说明和置信度评估
5. v2.2新增：批量修正机制，一次性处理多个问题，显著提升效率
6. v2.3新增：AI视觉资源缺失检测与Seedance 2.0提示词规范检查
7. v2.4新增：视觉内容完整性保护，防止质控修正误删拍摄脚本和AI视觉资源
8. v2.5新增：视觉内容智能同步机制，正文修正后自动同步更新视觉资源提示词

@date: 2026-05-19
@version: v2.6.0
"""
import json
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_manager import get_llm_manager
from app.core.logger import get_logger

logger = get_logger("quality_control.fix_generator")


# ============================================================================
# v2.6: 按内容类型拆分提示词模板 — 小说与剧本完全隔离
# ============================================================================

# 小说专用修正提示词（不含任何影视/视觉相关内容）
QUALITY_FIX_PROMPT_NOVEL = """你是专业的小说创作编辑,擅长修正小说中的各种问题。

【问题描述】
{issue_description}

【问题类型】
{issue_category}

【原始内容】(第{chapter_number}单元)
{original_content}

【单元概述】（当前单元的原始规划，修正时应作为重要参考）
{unit_summary}

【知识图谱上下文】（项目中的实体状态、关系和剧情线索，修正时必须保持一致）
{knowledge_graph_context}

【人物设定】
{character_profiles}

【世界观设定】
{worldview_settings}

## 修正任务

请根据以上信息,生成修正后的内容。要求:

1. **逻辑自洽**: 修正内容必须与单元概述、知识图谱、人物设定、世界观保持一致
2. **人物状态一致性**: 必须严格遵循前文的人物状态信息（位置、身份、关系、能力等），不得出现瞬移、OOC等逻辑错误
3. **上下文连贯**: 与前后单元自然衔接
4. **问题解决**: 彻底解决指出的问题
5. **保持风格**: 维持原有的文风和叙事风格
6. **尊重原文**: 只做必要的修改,不要重写整个内容

## 重要原则

- **正向优化**: 修正是为了提升质量,不是重写。保留原文的核心情节、人物设定和精彩段落
- **适度修改**: 一般情况修改幅度建议不超过30%,但如遇情节重构等特殊情况可酌情突破限制
- **内容完整性**: 修正后的内容长度不应显著少于原文,避免大面积删减导致内容不完整
- **灵活处理**: 如果问题需要修改文本,请在fixed_content中返回修改后的完整内容;如果问题不需要修改文本(如逻辑性建议),请在fixed_content中返回原文,但在description中说明原因
- **保持创造性**: 不要过度保守,当问题确实需要较大修改时,应该大胆重构

## 输出格式

请严格按照以下JSON格式输出:

```json
{{
  "fixed_content": "修正后的完整内容(如果有修改)或原文(如果无需修改)",
  "description": "修正说明,详细解释做了什么修改或为什么不需要修改",
  "changes_made": ["修改点1", "修改点2"],
  "confidence": 0.95
}}
```

只输出JSON,不要其他内容。
"""


# 剧本专用修正提示词（保留完整的视觉内容保护指令）
QUALITY_FIX_PROMPT_SCRIPT = """你是专业的剧本创作编辑,擅长修正剧本中的各种问题。

【问题描述】
{issue_description}

【问题类型】
{issue_category}

【原始内容】(第{chapter_number}单元)
{original_content}

【单元概述】（当前单元的原始规划，修正时应作为重要参考）
{unit_summary}

【知识图谱上下文】（项目中的实体状态、关系和剧情线索，修正时必须保持一致）
{knowledge_graph_context}

【人物设定】
{character_profiles}

【世界观设定】
{worldview_settings}

## ⚠️ 【内容完整性铁律 — 最高优先级】

修正后的 fixed_content 必须包含原始内容的**所有结构性部分**，不得删除任何章节。请先识别原始内容中的结构分界：

原始内容可能包含以下结构化段落（请逐一识别并保留）：
1. **正文部分**：剧本主体内容
2. **拍摄脚本参考**：运镜设计、光影方案、演出指导、剪辑思路、连续性衔接等（如存在）
3. **AI视觉资源生成**：人物参考图提示词、场景参考图提示词、物品参考图提示词、Seedance 2.0视频生成提示词等（如存在）
4. **其他附属部分**：标注、注释、格式标记等

**严禁行为**：
- ❌ 严禁删除或截断「拍摄脚本参考」和「AI视觉资源生成」部分
- ❌ 严禁在 fixed_content 中只返回正文而丢弃后续章节
- ❌ 严禁将视觉提示词简化为"（提示词部分保持不变）"等占位符

**正确做法**：
- ✅ 只对正文中需要修正的部分进行修改
- ✅ 如果问题不涉及拍摄脚本或视觉资源部分，请原样完整保留
- ✅ 如果视觉资源部分需要根据正文修改进行调整，请在保留原有结构的基础上微调
- ✅ 修正后 fixed_content 的总长度不应显著少于原始内容

**视觉同步要求**（当正文修改涉及以下内容时必须同步更新）：
- ✅ 如果正文中角色外貌、服装、表情描述有变化 → 同步更新人物参考图提示词中的对应字段
- ✅ 如果正文中场景环境、时间、天气、氛围有变化 → 同步更新场景参考图提示词中的对应字段
- ✅ 如果正文中道具/物品描述有变化 → 同步更新物品参考图提示词中的对应字段
- ✅ 如果正文剧情/动作序列有变化 → 同步更新分镜设计表中的画面描述、情感意图、时长，以及视频提示词中的[主体动作]、[环境描述]、[运镜方式]等字段
- ✅ 确保视觉提示词中引用的角色名、场景名、物品名与修正后正文完全一致

## 修正任务

请根据以上信息,生成修正后的内容。要求:

1. **逻辑自洽**: 修正内容必须与单元概述、知识图谱、人物设定、世界观保持一致
2. **人物状态一致性**: 必须严格遵循前文的人物状态信息（位置、身份、关系、能力等），不得出现瞬移、OOC等逻辑错误
3. **上下文连贯**: 与前后单元自然衔接
4. **问题解决**: 彻底解决指出的问题
5. **保持风格**: 维持原有的文风和叙事风格
6. **尊重原文**: 只做必要的修改,不要重写整个内容
7. **AI视觉资源检查与同步**：请检查是否包含人物参考图提示词、场景参考图提示词和Seedance 2.0视频生成提示词。如正文修改影响了视觉描述（角色外貌、场景环境、动作设计等），必须同步更新对应的视觉资源提示词

## 重要原则

- **正向优化**: 修正是为了提升质量,不是重写。保留原文的核心情节、人物设定和精彩段落
- **适度修改**: 一般情况修改幅度建议不超过30%,但如遇情节重构等特殊情况可酌情突破限制
- **内容完整性**: 修正后的内容长度不应显著少于原文,避免大面积删减导致内容不完整
- **灵活处理**: 如果问题需要修改文本,请在fixed_content中返回修改后的完整内容;如果问题不需要修改文本(如逻辑性建议),请在fixed_content中返回原文,但在description中说明原因
- **保持创造性**: 不要过度保守,当问题确实需要较大修改时,应该大胆重构

## 输出格式

请严格按照以下JSON格式输出:

```json
{{
  "fixed_content": "修正后的完整内容(如果有修改)或原文(如果无需修改)",
  "description": "修正说明,详细解释做了什么修改或为什么不需要修改",
  "changes_made": ["修改点1", "修改点2"],
  "confidence": 0.95
}}
```

只输出JSON,不要其他内容。
"""


# 小说专用批量修正提示词（不含任何影视/视觉相关内容）
BATCH_QUALITY_FIX_PROMPT_NOVEL = """你是专业的小说创作编辑,擅长综合修正小说中的多个问题。

【待修正的问题列表】（共{issue_count}个问题）
{all_issues_list}

【原始内容】(第{chapter_number}单元)
{original_content}

【单元概述】（当前单元的原始规划，修正时应作为重要参考）
{unit_summary}

【知识图谱上下文】（项目中的实体状态、关系和剧情线索，修正时必须保持一致）
{knowledge_graph_context}

【人物设定】
{character_profiles}

【世界观设定】
{worldview_settings}

## 修正任务

请综合分析以上所有问题,生成一次性的修正内容。要求:

1. **整体视角**: 不要逐个问题单独修正,而是综合分析所有问题后整体优化
2. **辩证思考**: 问题之间可能存在关联,修正时需要考虑问题A的修正是否会影响问题B
3. **逻辑自洽**: 修正内容必须与单元概述、知识图谱、人物设定、世界观保持一致
4. **人物状态一致性**: 必须严格遵循前文的人物状态信息（位置、身份、关系、能力等），不得出现瞬移、OOC等逻辑错误
5. **上下文连贯**: 与前后单元自然衔接
6. **彻底解决**: 确保所有列出的问题都得到解决
7. **保持风格**: 维持原有的文风和叙事风格
8. **尊重原文**: 只做必要的修改,不要重写整个内容

## 重要原则

- **正向优化**: 修正是为了提升质量,不是重写。保留原文的核心情节、人物设定和精彩段落
- **适度修改**: 一般情况修改幅度建议不超过30%,但如遇情节重构等特殊情况可酌情突破限制
- **内容完整性**: 修正后的内容长度不应显著少于原文,避免大面积删减导致内容不完整
- **灵活处理**: 如果某些问题不需要修改文本(如逻辑性建议),请在description中说明原因
- **保持创造性**: 不要过度保守,当问题确实需要较大修改时,应该大胆重构
- **避免冲突**: 如果问题之间存在冲突,请根据问题严重程度和上下文逻辑判断优先级

## 输出格式

请严格按照以下JSON格式输出:

```json
{{
  "fixed_content": "修正后的完整内容",
  "description": "综合修正说明,详细解释做了什么修改",
  "changes_made": ["修改点1", "修改点2", ...],
  "confidence": 0.90,
  "issues_addressed": ["issue_id1", "issue_id2", ...]
}}
```

只输出JSON,不要其他内容。
"""


# 剧本专用批量修正提示词（保留完整的视觉内容保护指令）
BATCH_QUALITY_FIX_PROMPT_SCRIPT = """你是专业的剧本创作编辑,擅长综合修正剧本中的多个问题。

【待修正的问题列表】（共{issue_count}个问题）
{all_issues_list}

【原始内容】(第{chapter_number}单元)
{original_content}

【单元概述】（当前单元的原始规划，修正时应作为重要参考）
{unit_summary}

【知识图谱上下文】（项目中的实体状态、关系和剧情线索，修正时必须保持一致）
{knowledge_graph_context}

【人物设定】
{character_profiles}

【世界观设定】
{worldview_settings}

## ⚠️ 【内容完整性铁律 — 最高优先级】

修正后的 fixed_content 必须包含原始内容的**所有结构性部分**，不得删除任何章节。请先识别原始内容中的结构分界：

原始内容可能包含以下结构化段落（请逐一识别并保留）：
1. **正文部分**：剧本主体内容
2. **拍摄脚本参考**：运镜设计、光影方案、演出指导、剪辑思路、连续性衔接等（如存在）
3. **AI视觉资源生成**：人物参考图提示词、场景参考图提示词、物品参考图提示词、Seedance 2.0视频生成提示词等（如存在）
4. **其他附属部分**：标注、注释、格式标记等

**严禁行为**：
- ❌ 严禁删除或截断「拍摄脚本参考」和「AI视觉资源生成」部分
- ❌ 严禁在 fixed_content 中只返回正文而丢弃后续章节
- ❌ 严禁将视觉提示词简化为"（提示词部分保持不变）"等占位符

**正确做法**：
- ✅ 只对正文中需要修正的部分进行修改
- ✅ 如果问题不涉及拍摄脚本或视觉资源部分，请原样完整保留
- ✅ 如果视觉资源部分需要根据正文修改进行调整，请在保留原有结构的基础上微调
- ✅ 修正后 fixed_content 的总长度不应显著少于原始内容

**视觉同步要求**（当正文修改涉及以下内容时必须同步更新）：
- ✅ 如果正文中角色外貌、服装、表情描述有变化 → 同步更新人物参考图提示词中的对应字段
- ✅ 如果正文中场景环境、时间、天气、氛围有变化 → 同步更新场景参考图提示词中的对应字段
- ✅ 如果正文中道具/物品描述有变化 → 同步更新物品参考图提示词中的对应字段
- ✅ 如果正文剧情/动作序列有变化 → 同步更新分镜设计表中的画面描述、情感意图、时长，以及视频提示词中的[主体动作]、[环境描述]、[运镜方式]等字段
- ✅ 确保视觉提示词中引用的角色名、场景名、物品名与修正后正文完全一致

## 修正任务

请综合分析以上所有问题,生成一次性的修正内容。要求:

1. **整体视角**: 不要逐个问题单独修正,而是综合分析所有问题后整体优化
2. **辩证思考**: 问题之间可能存在关联,修正时需要考虑问题A的修正是否会影响问题B
3. **逻辑自洽**: 修正内容必须与单元概述、知识图谱、人物设定、世界观保持一致
4. **人物状态一致性**: 必须严格遵循前文的人物状态信息（位置、身份、关系、能力等），不得出现瞬移、OOC等逻辑错误
5. **上下文连贯**: 与前后单元自然衔接
6. **彻底解决**: 确保所有列出的问题都得到解决
7. **保持风格**: 维持原有的文风和叙事风格
8. **尊重原文**: 只做必要的修改,不要重写整个内容
9. **AI视觉资源检查与同步**：请检查是否包含人物/场景/物品参考图提示词和Seedance 2.0视频生成提示词。如正文修改影响了视觉描述，必须同步更新对应的视觉资源提示词

## 重要原则

- **正向优化**: 修正是为了提升质量,不是重写。保留原文的核心情节、人物设定和精彩段落
- **适度修改**: 一般情况修改幅度建议不超过30%,但如遇情节重构等特殊情况可酌情突破限制
- **内容完整性**: 修正后的内容长度不应显著少于原文,避免大面积删减导致内容不完整
- **灵活处理**: 如果某些问题不需要修改文本(如逻辑性建议),请在description中说明原因
- **保持创造性**: 不要过度保守,当问题确实需要较大修改时,应该大胆重构
- **避免冲突**: 如果问题之间存在冲突,请根据问题严重程度和上下文逻辑判断优先级

## 输出格式

请严格按照以下JSON格式输出:

```json
{{
  "fixed_content": "修正后的完整内容",
  "description": "综合修正说明,详细解释做了什么修改",
  "changes_made": ["修改点1", "修改点2", ...],
  "confidence": 0.90,
  "issues_addressed": ["issue_id1", "issue_id2", ...]
}}
```

只输出JSON,不要其他内容。
"""


# 内容类型 -> 提示词模板映射
_QUALITY_FIX_PROMPTS = {
    "novel": QUALITY_FIX_PROMPT_NOVEL,
    "series_script": QUALITY_FIX_PROMPT_SCRIPT,
    "movie_script": QUALITY_FIX_PROMPT_SCRIPT,
    "script": QUALITY_FIX_PROMPT_SCRIPT,
}

_BATCH_QUALITY_FIX_PROMPTS = {
    "novel": BATCH_QUALITY_FIX_PROMPT_NOVEL,
    "series_script": BATCH_QUALITY_FIX_PROMPT_SCRIPT,
    "movie_script": BATCH_QUALITY_FIX_PROMPT_SCRIPT,
    "script": BATCH_QUALITY_FIX_PROMPT_SCRIPT,
}


def _get_fix_prompt(content_type: str) -> str:
    """根据内容类型获取对应的修正提示词模板"""
    return _QUALITY_FIX_PROMPTS.get(content_type, QUALITY_FIX_PROMPT_NOVEL)


def _get_batch_fix_prompt(content_type: str) -> str:
    """根据内容类型获取对应的批量修正提示词模板"""
    return _BATCH_QUALITY_FIX_PROMPTS.get(content_type, BATCH_QUALITY_FIX_PROMPT_NOVEL)


# ============================================================================
# v2.5: 视觉内容同步提示词模板
# ============================================================================

VISUAL_SYNC_PROMPT = """你是专业的剧本视觉内容同步编辑。你的任务是根据已修正的剧本正文，智能同步更新后续的AI视觉资源生成提示词和拍摄脚本。

【原始正文】（修正前，仅供参考了解修改了什么）
{original_content}

【修正后完整内容】（正文已被质控修正，视觉资源部分需要同步更新）
{fixed_content}

## 核心任务

请仔细对比原始正文和修正后正文之间的差异，然后**只更新**视觉资源部分，使它们与修正后的正文保持一致。**严禁修改正文部分**。

## 同步检查清单

### 1. 人物外貌/设定变化 → 更新人物参考图提示词
如果正文中以下内容有变化：
- 角色的外貌描述（发型、服饰、年龄特征等）
- 角色的情绪状态或表情
- 角色的身份或定位
→ 同步更新「人物参考图生成提示词」中的 subject_desc、costume_desc、pose_desc、expression 等字段

### 2. 场景环境变化 → 更新场景参考图提示词
如果正文中以下内容有变化：
- 场景地点、环境描述
- 时间（日/夜）、天气、季节
- 场景氛围、色调
→ 同步更新「场景参考图生成提示词」中的 location_desc、time_weather、atmosphere_desc、composition 等字段

### 3. 道具/物品变化 → 更新物品参考图提示词
如果正文中以下内容有变化：
- 道具的外观、材质、用途描述
- 新增或删除重要道具
→ 同步更新「物品参考图生成提示词」中的 prop_desc、material 等字段

### 4. 剧情/动作变化 → 更新分镜设计和视频提示词
如果正文中以下内容有变化：
- 关键场景的动作序列
- 角色之间的互动方式
- 场景的戏剧张力和情感走向
→ 同步更新：
  - 分镜设计表中的「画面描述」「情感意图」「时长」
  - Seedance 2.0 视频提示词中的 [镜头类型]、[主体动作]、[环境描述]、[运镜方式]、[首帧描述]、[尾帧描述]

### 5. 拍摄脚本变化
如果正文的剧情节奏、情感基调有变化：
→ 同步更新「拍摄脚本参考」中的运镜设计、光影方案、演出指导

## 重要约束

- **严禁修改正文**：只更新视觉资源部分，正文部分一个字都不要改
- **保持格式**：所有视觉资源部分的格式、结构、字段顺序、Markdown标题层级完全不变
- **保持中文**：所有提示词保持中文输出
- **完整输出**：返回完整内容（正文 + 所有视觉资源部分），不要省略任何内容
- **精确同步**：只更新确实受到正文修改影响的视觉内容，未受影响的部分保持原样
- **一致性命名**：确保视觉提示词中引用的角色名、场景名、物品名与修正后正文完全一致

## 输出格式

请严格按以下JSON格式输出：

```json
{{
  "synced_content": "完整内容（正文完全不变 + 已同步的视觉资源部分）",
  "body_changes_detected": ["检测到的正文修改点1", "修改点2"],
  "visual_updates_applied": ["已更新的视觉部分1", "部分2"],
  "no_changes_needed": false
}}
```

只输出JSON，不要其他内容。
"""


class QualityFixGenerator:
    """质量修正生成器 - 使用LLM生成智能修正方案"""

    def __init__(self):
        self.llm_manager = get_llm_manager()

    async def generate_fix(
        self,
        issue: Dict,
        chapter_content: str,
        unit_summary: str = "",
        character_profiles: List[Dict] = None,
        worldview_settings: Dict = None,
        knowledge_graph_context: str = "",  # 知识图谱上下文
        content_type: str = "novel",  # v2.6: 内容类型,用于选择提示词模板
        db: AsyncSession = None,
        user_id: int = 0
    ) -> Dict:
        """
        生成智能修正方案

        Args:
            issue: 问题字典,包含category, description, location等
            chapter_content: 当前单元内容
            unit_summary: 单元概述
            character_profiles: 人物设定列表
            worldview_settings: 世界观设定
            knowledge_graph_context: 知识图谱上下文
            content_type: 内容类型 (novel/series_script/movie_script)，用于选择提示词
            db: 数据库会话
            user_id: 用户ID

        Returns:
            修正方案字典,包含:
            - original: 原始内容
            - fixed: 修正后内容
            - description: 修正说明
            - changes_made: 修改点列表
            - confidence: 置信度(0-1)
            - tokens_used: 消耗的token数
        """
        try:
            chapter_number = issue.get("location", {}).get("chapter_number", 0)
            category = issue.get("category", "未知问题")
            description = issue.get("description", "")

            logger.info(
                f"开始生成修正方案: issue={issue.get('id')}, "
                f"category={category}, chapter={chapter_number}, content_type={content_type}"
            )

            # 构建人物设定文本
            character_text = self._format_character_profiles(
                character_profiles or [])

            # 构建世界观设定文本
            worldview_text = self._format_worldview_settings(
                worldview_settings or {})

            # v2.6: 根据内容类型选择对应的提示词模板
            fix_prompt = _get_fix_prompt(content_type)

            # 构建提示词（不再静默截断内容，LLM 上下文由模型自行处理）
            prompt = fix_prompt.format(
                issue_description=description,
                issue_category=category,
                chapter_number=chapter_number,
                original_content=chapter_content,
                unit_summary=unit_summary if unit_summary else "无",
                knowledge_graph_context=knowledge_graph_context if knowledge_graph_context else "暂无知识图谱数据",
                character_profiles=character_text if character_text else "无",
                worldview_settings=worldview_text if worldview_text else "无"
            )

            # 获取用户的默认LLM provider
            if db and user_id:
                llm_provider = await self.llm_manager.get_provider_from_db(db, user_id)
            else:
                # 如果没有db或user_id，使用系统默认
                llm_provider = await self.llm_manager.get_system_provider("qianwen")

            # 调用LLM生成修正内容
            response = await llm_provider.generate(
                prompt=prompt,
                temperature=0.3,  # 较低温度确保稳定性
                max_tokens=30000,  # v2.1: 统一设置为30000确保输出完整
                module_name="qc_fix_generator"
            )

            # 解析LLM响应
            fix_result = self._parse_llm_response(
                response.content, chapter_content)

            # 添加原始内容和token消耗
            fix_result["original"] = chapter_content
            # LLMResponse.usage 是 Dict[str, int]，包含 prompt_tokens, completion_tokens, total_tokens
            usage = response.usage or {}
            fix_result["tokens_used"] = usage.get("total_tokens", 0)

            logger.info(
                f"修正方案生成成功: confidence={fix_result.get('confidence', 0):.2f}, "
                f"tokens={fix_result.get('tokens_used', 0)}"
            )

            return fix_result

        except Exception as e:
            logger.error(f"生成修正方案失败: {str(e)}", exc_info=True)
            # 返回降级方案
            return self._fallback_fix(issue, chapter_content, str(e))

    async def generate_batch_fix(
        self,
        issues: List[Dict],
        chapter_content: str,
        unit_summary: str = "",
        character_profiles: List[Dict] = None,
        worldview_settings: Dict = None,
        knowledge_graph_context: str = "",
        content_type: str = "novel",  # v2.6: 内容类型,用于选择提示词模板
        db: AsyncSession = None,
        user_id: int = 0
    ) -> Dict:
        """
        批量修正：一次性处理同一章节的多个问题（v2.2新增）

        Args:
            issues: 同一章节的所有问题列表
            chapter_content: 当前单元内容
            unit_summary: 单元概述
            character_profiles: 人物设定列表
            worldview_settings: 世界观设定
            knowledge_graph_context: 知识图谱上下文
            content_type: 内容类型 (novel/series_script/movie_script)，用于选择提示词
            db: 数据库会话
            user_id: 用户ID

        Returns:
            批量修正方案字典,包含:
            - original: 原始内容
            - fixed: 修正后内容
            - description: 综合修正说明
            - changes_made: 修改点列表
            - confidence: 置信度(0-1)
            - issues_addressed: 已处理的问题ID列表
            - tokens_used: 消耗的token数
        """
        try:
            if not issues:
                logger.warning("批量修正：问题列表为空")
                return {
                    "fixed": chapter_content,
                    "description": "无需修正",
                    "changes_made": [],
                    "confidence": 1.0,
                    "issues_addressed": [],
                    "original": chapter_content,
                    "tokens_used": 0,
                    "type": "no_issues"
                }

            chapter_number = issues[0].get("location", {}).get("chapter_number", 0)
            issue_count = len(issues)

            logger.info(
                f"开始批量修正: chapter={chapter_number}, "
                f"issue_count={issue_count}, content_type={content_type}"
            )

            # 构建问题列表文本
            all_issues_list = self._format_issues_list(issues)

            # 构建人物设定文本
            character_text = self._format_character_profiles(
                character_profiles or [])

            # 构建世界观设定文本
            worldview_text = self._format_worldview_settings(
                worldview_settings or {})

            # v2.6: 根据内容类型选择对应的提示词模板
            batch_fix_prompt = _get_batch_fix_prompt(content_type)

            # 构建批量修正提示词
            prompt = batch_fix_prompt.format(
                issue_count=issue_count,
                all_issues_list=all_issues_list,
                chapter_number=chapter_number,
                original_content=chapter_content,
                unit_summary=unit_summary if unit_summary else "无",
                knowledge_graph_context=knowledge_graph_context if knowledge_graph_context else "暂无知识图谱数据",
                character_profiles=character_text if character_text else "无",
                worldview_settings=worldview_text if worldview_text else "无"
            )

            # 获取用户的默认LLM provider
            if db and user_id:
                llm_provider = await self.llm_manager.get_provider_from_db(db, user_id)
            else:
                llm_provider = await self.llm_manager.get_system_provider("qianwen")

            # 调用LLM生成批量修正内容
            response = await llm_provider.generate(
                prompt=prompt,
                temperature=0.3,  # 较低温度确保稳定性
                max_tokens=30000,
                module_name="qc_batch_fix"
            )

            # 解析LLM响应
            fix_result = self._parse_batch_llm_response(
                response.content, chapter_content, issues)

            # 添加原始内容和token消耗
            fix_result["original"] = chapter_content
            usage = response.usage or {}
            fix_result["tokens_used"] = usage.get("total_tokens", 0)

            logger.info(
                f"批量修正方案生成成功: issues_addressed={len(fix_result.get('issues_addressed', []))}, "
                f"confidence={fix_result.get('confidence', 0):.2f}, "
                f"tokens={fix_result.get('tokens_used', 0)}"
            )

            return fix_result

        except Exception as e:
            logger.error(f"批量修正失败: {str(e)}", exc_info=True)
            # 降级为逐个修正
            return await self._fallback_batch_fix(issues, chapter_content, str(e), db, user_id, content_type)

    def _format_character_profiles(self, profiles: List[Dict]) -> str:
        """格式化人物设定为文本"""
        if not profiles:
            return ""

        lines = []
        for profile in profiles:
            name = profile.get("name", "未知人物")
            lines.append(f"人物: {name}")

            # 添加关键属性
            for key in ["personality", "role", "background", "goals"]:
                if key in profile and profile[key]:
                    key_name = {
                        "personality": "性格",
                        "role": "角色",
                        "background": "背景",
                        "goals": "目标"
                    }.get(key, key)
                    lines.append(f"  {key_name}: {profile[key]}")

            lines.append("")

        return "\n".join(lines)

    def _format_issues_list(self, issues: List[Dict]) -> str:
        """格式化问题列表为文本（v2.2新增）"""
        if not issues:
            return "无问题"

        lines = []
        for idx, issue in enumerate(issues, 1):
            issue_id = issue.get("id", f"issue_{idx}")
            category = issue.get("category", "未知类型")
            severity = issue.get("severity", "未知严重程度")
            description = issue.get("description", "无描述")
            suggestion = issue.get("suggestion", "")

            lines.append(f"问题{idx} [{issue_id}]")
            lines.append(f"  类型: {category}")
            lines.append(f"  严重程度: {severity}")
            lines.append(f"  描述: {description}")
            if suggestion:
                lines.append(f"  建议: {suggestion}")
            lines.append("")

        return "\n".join(lines)

    def _parse_batch_llm_response(self, content: str, original_content: str, issues: List[Dict]) -> Dict:
        """解析批量修正LLM响应（v2.2新增）"""
        try:
            # 尝试提取JSON
            json_start = content.find("```json")
            if json_start != -1:
                json_start = content.find("{", json_start)
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            else:
                json_str = content

            # 解析JSON
            data = json.loads(json_str)

            # 验证必要字段
            if "fixed_content" not in data:
                raise ValueError("缺少fixed_content字段")

            return {
                "fixed": data.get("fixed_content", original_content),
                "description": data.get("description", "已根据问题描述生成修正内容"),
                "changes_made": data.get("changes_made", []),
                "confidence": min(max(float(data.get("confidence", 0.7)), 0.0), 1.0),
                "issues_addressed": data.get("issues_addressed", [issue.get("id") for issue in issues]),
                "type": "batch_llm_generated"
            }

        except json.JSONDecodeError as e:
            logger.warning(f"批量修正LLM响应JSON解析失败: {str(e)}")
            # 尝试从内容中提取
            return self._extract_fix_from_text(content, original_content)
        except Exception as e:
            logger.error(f"解析批量修正LLM响应失败: {str(e)}")
            raise

    async def _fallback_batch_fix(
        self,
        issues: List[Dict],
        chapter_content: str,
        error: str,
        db: AsyncSession = None,
        user_id: int = 0,
        content_type: str = "novel"
    ) -> Dict:
        """批量修正降级方案：逐个修正（v2.2新增）"""
        logger.warning(f"批量修正失败，降级为逐个修正: {error}")

        # 尝试逐个修正第一个问题
        if issues:
            first_issue = issues[0]
            fallback_result = await self.generate_fix(
                issue=first_issue,
                chapter_content=chapter_content,
                content_type=content_type,
                db=db,
                user_id=user_id
            )
            fallback_result["issues_addressed"] = [first_issue.get("id")]
            fallback_result["type"] = "fallback_single"
            return fallback_result

        # 如果连逐个修正都失败，返回原文
        return {
            "fixed": chapter_content,
            "description": f"批量修正和逐个修正均失败({error}),保持原内容",
            "changes_made": [],
            "confidence": 0.0,
            "issues_addressed": [],
            "original": chapter_content,
            "tokens_used": 0,
            "type": "fallback_failed"
        }

    def _format_worldview_settings(self, settings: Dict) -> str:
        """格式化世界观设定为文本"""
        if not settings:
            return ""

        lines = []
        for key, value in settings.items():
            key_name = {
                "time_period": "时代背景",
                "location": "地点设定",
                "rules": "世界规则",
                "magic_system": "魔法体系",
                "technology": "科技水平",
                "social_structure": "社会结构"
            }.get(key, key)

            if isinstance(value, str):
                lines.append(f"{key_name}: {value}")
            elif isinstance(value, list):
                lines.append(f"{key_name}:")
                for item in value:
                    lines.append(f"  - {item}")
            lines.append("")

        return "\n".join(lines)

    def _parse_llm_response(self, content: str, original_content: str) -> Dict:
        """解析LLM响应,提取修正方案"""
        try:
            # 尝试提取JSON
            json_start = content.find("```json")
            if json_start != -1:
                json_start = content.find("{", json_start)
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            else:
                # 直接尝试解析整个内容
                json_str = content

            # 解析JSON
            data = json.loads(json_str)

            # 验证必要字段
            if "fixed_content" not in data:
                raise ValueError("缺少fixed_content字段")

            return {
                "fixed": data.get("fixed_content", original_content),
                "description": data.get("description", "已根据问题描述生成修正内容"),
                "changes_made": data.get("changes_made", []),
                "confidence": min(max(float(data.get("confidence", 0.7)), 0.0), 1.0),
                "type": "llm_generated"
            }

        except json.JSONDecodeError as e:
            logger.warning(f"LLM响应JSON解析失败: {str(e)}")
            # 尝试从内容中提取
            return self._extract_fix_from_text(content, original_content)
        except Exception as e:
            logger.error(f"解析LLM响应失败: {str(e)}")
            raise

    def _extract_fix_from_text(self, text: str, original_content: str) -> Dict:
        """从文本中提取修正内容(降级方案)"""
        # 如果文本包含"修正后的内容"等关键词,尝试提取
        keywords = ["修正后的内容", "修正后内容", "fixed_content", "修正内容"]

        for keyword in keywords:
            pos = text.find(keyword)
            if pos != -1:
                # 提取关键词后的内容
                fixed_content = text[pos + len(keyword):].strip()
                # 移除可能的冒号
                if fixed_content.startswith(":") or fixed_content.startswith("："):
                    fixed_content = fixed_content[1:].strip()

                if len(fixed_content) > 50:  # 确保内容有意义
                    return {
                        "fixed": fixed_content,  # 不再截断修正内容
                        "description": "从LLM响应中提取的修正内容",
                        "changes_made": [],
                        "confidence": 0.6,
                        "type": "extracted"
                    }

        # 无法提取,返回原始内容
        return {
            "fixed": original_content,
            "description": "LLM生成失败,保持原内容",
            "changes_made": [],
            "confidence": 0.0,
            "type": "fallback"
        }

    def _fallback_fix(self, issue: Dict, chapter_content: str, error: str) -> Dict:
        """降级修正方案(LLM失败时使用)

        v2.3: 新增 AI视觉资源缺失 和 Seedance提示词格式 两种降级修正类型
        """
        category = issue.get("category", "")

        # 根据问题类型提供简单的修正建议
        fallback_suggestions = {
            "单元衔接": {
                "fixed": chapter_content + "\n\n然而,这仅仅是开始,更大的挑战还在后面...",
                "description": "添加了过渡句以增强单元衔接",
                "confidence": 0.5
            },
            "节奏平淡": {
                "fixed": chapter_content.replace("。", "。突然,", 1) if "。" in chapter_content else chapter_content,
                "description": "在开头添加了突发事件以增强节奏",
                "confidence": 0.4
            },
            "单元过短": {
                "fixed": chapter_content + "\n\n这个决定带来了深远的影响,故事的走向从此改变。",
                "description": "补充了情节发展以丰富单元内容",
                "confidence": 0.5
            },
            "AI视觉资源缺失": {
                "fixed": chapter_content,
                "description": "检测到剧集/电影内容可能缺少AI视觉资源（参考图提示词、Seedance 2.0视频提示词），建议在后续版本中补充图像参考资源和Seedance 2.0全能参考模式的视频生成提示词",
                "confidence": 0.3
            },
            "Seedance提示词格式": {
                "fixed": chapter_content,
                "description": "检测到Seedance 2.0视频生成提示词格式可能不符合全能参考模式规范，建议检查是否包含[参考模式]、[人物参考图]、[场景参考图]、[物品参考图]等必要字段",
                "confidence": 0.3
            },
        }

        fallback = fallback_suggestions.get(category, {
            "fixed": chapter_content,
            "description": f"LLM生成失败({error}),建议手动修改",
            "confidence": 0.0
        })

        fallback.update({
            "original": chapter_content,
            "changes_made": [],
            "tokens_used": 0,
            "type": "fallback"
        })

        return fallback

    # ========================================================================
    # v2.5: 视觉内容同步方法
    # ========================================================================

    # 视觉内容段落标记关键词（用于检测是否需要同步）
    _VISUAL_MARKERS = [
        "拍摄脚本参考", "运镜设计", "光影方案", "演出指导", "剪辑思路", "连续性衔接",
        "AI视觉资源生成", "Seedance", "人物参考图生成提示词", "场景参考图生成提示词",
        "物品参考图生成提示词", "视频生成提示词", "参考模式", "人物参考图",
        "场景参考图", "物品参考图", "镜头类型", "主体动作", "环境描述",
        "运镜方式", "风格要求", "首帧描述", "尾帧描述", "负面提示词",
        "AI生成提示词", "六要素", "主视觉提示词", "备选方案提示词",
        "分镜设计", "故事板", "storyboard",
    ]

    async def sync_visual_sections(
        self,
        original_content: str,
        fixed_content: str,
        db: AsyncSession = None,
        user_id: int = 0
    ) -> Dict:
        """
        同步视觉资源内容与修正后的正文（v2.5新增）

        当质控修正了正文内容后，此方法调用LLM确保后续的视觉资源提示词、
        分镜设计、拍摄脚本等与修正后的正文保持一致。

        检测流程：
        1. 快速检查：内容中是否有视觉资源标记
        2. 差异分析：对比原始与修正后正文的差异
        3. 同步执行：调用LLM更新受影响的视觉资源部分
        4. 安全回退：失败时返回未同步的修正内容

        Args:
            original_content: 修正前的原始内容
            fixed_content: 修正后的内容（正文已更新，视觉部分可能未同步）
            db: 数据库会话
            user_id: 用户ID

        Returns:
            同步结果字典:
            - synced_content: 同步后的完整内容
            - body_changes_detected: 检测到的正文修改
            - visual_updates_applied: 已应用的视觉更新
            - tokens_used: 消耗的token数
            - skipped: 是否跳过（无视觉内容）
            - fallback: 是否因错误回退
        """
        try:
            # 快速检查：如果没有视觉内容标记，跳过同步
            has_visual = any(
                marker in fixed_content
                for marker in self._VISUAL_MARKERS
            )
            if not has_visual:
                logger.debug("[视觉同步] 内容中无视觉资源部分，跳过同步")
                return {
                    "synced_content": fixed_content,
                    "body_changes_detected": [],
                    "visual_updates_applied": [],
                    "tokens_used": 0,
                    "skipped": True
                }

            # 快速检查：如果内容没有实质变化，跳过同步
            if original_content == fixed_content:
                logger.debug("[视觉同步] 内容无变化，跳过同步")
                return {
                    "synced_content": fixed_content,
                    "body_changes_detected": [],
                    "visual_updates_applied": [],
                    "tokens_used": 0,
                    "skipped": True
                }

            logger.info(
                f"[视觉同步] 开始同步视觉资源内容 "
                f"(original={len(original_content)}chars, fixed={len(fixed_content)}chars)"
            )

            # 构建同步提示词（v2.5.1: 限制内容长度，避免超token）
            # 对于超长内容，截取正文主体+视觉部分，而不是全文
            max_content_chars = 30000
            orig_for_prompt = original_content
            fixed_for_prompt = fixed_content
            if len(original_content) > max_content_chars or len(fixed_content) > max_content_chars:
                logger.warning(
                    f"[视觉同步] 内容过长，将截取关键部分 "
                    f"(original={len(original_content)}, fixed={len(fixed_content)})"
                )
                # 保留前1/4正文 + 视觉资源部分
                orig_for_prompt = self._truncate_for_visual_sync(original_content, max_content_chars)
                fixed_for_prompt = self._truncate_for_visual_sync(fixed_content, max_content_chars)

            prompt = VISUAL_SYNC_PROMPT.format(
                original_content=orig_for_prompt,
                fixed_content=fixed_for_prompt
            )

            # 获取LLM provider
            if db and user_id:
                llm_provider = await self.llm_manager.get_provider_from_db(db, user_id)
            else:
                llm_provider = await self.llm_manager.get_system_provider("qianwen")

            # 调用LLM进行视觉内容同步
            response = await llm_provider.generate(
                prompt=prompt,
                temperature=0.3,  # 低温度确保精确同步
                max_tokens=30000,
                module_name="qc_visual_sync"
            )

            # 解析同步响应
            sync_result = self._parse_sync_response(response.content, fixed_content)
            usage = response.usage or {}
            sync_result["tokens_used"] = usage.get("total_tokens", 0)

            # 验证同步结果的完整性
            synced = sync_result.get("synced_content", fixed_content)
            if len(synced) < len(fixed_content) * 0.5:
                logger.warning(
                    f"[视觉同步] 同步后内容长度异常缩短 "
                    f"(before={len(fixed_content)}, after={len(synced)})，回退到修正后内容"
                )
                sync_result["synced_content"] = fixed_content
                sync_result["fallback"] = True

            logger.info(
                f"[视觉同步] 完成: 检测到{len(sync_result.get('body_changes_detected', []))}处正文修改, "
                f"更新了{len(sync_result.get('visual_updates_applied', []))}处视觉内容, "
                f"tokens={sync_result.get('tokens_used', 0)}"
            )

            return sync_result

        except Exception as e:
            logger.error(f"[视觉同步] 同步失败: {str(e)}", exc_info=True)
            return {
                "synced_content": fixed_content,
                "body_changes_detected": [],
                "visual_updates_applied": [],
                "tokens_used": 0,
                "error": str(e),
                "fallback": True
            }

    def _truncate_for_visual_sync(self, content: str, max_chars: int) -> str:
        """
        为视觉同步截取关键内容部分（v2.5.1新增）

        策略：保留正文前1/4 + 完整的视觉资源部分，
        确保LLM能看到正文足够上下文 + 完整的视觉结构。
        """
        if len(content) <= max_chars:
            return content

        # 寻找视觉资源的起始标记
        visual_start_idx = -1
        visual_start_markers = [
            "### AI视觉资源生成", "## AI视觉资源生成", "# AI视觉资源生成",
            "### 拍摄脚本参考", "## 拍摄脚本参考", "# 拍摄脚本参考",
            "### 一、人物参考图", "## 一、人物参考图",
            "### 四、", "## 四、",
            "### 分镜设计", "## 分镜设计",
            "### AI视觉资源", "## AI视觉资源",
            "---\n\n## 🎬", "---\n\n## 🎥",
        ]
        for marker in visual_start_markers:
            idx = content.find(marker)
            if idx > 0:
                visual_start_idx = idx
                break

        if visual_start_idx > 0:
            # 正文部分: 保留前1/3
            body_part = content[:visual_start_idx]
            body_keep = min(len(body_part), max_chars // 2)
            # 视觉部分: 从起始位置全部保留
            visual_part = content[visual_start_idx:]
            visual_keep = min(len(visual_part), max_chars - body_keep)
            truncated = content[:body_keep] + "\n\n...[正文中间部分已省略]...\n\n" + visual_part[:visual_keep]
            logger.info(
                f"[视觉同步] 内容截取: {len(content)} -> {len(truncated)} chars "
                f"(正文{body_keep} + 视觉{visual_keep})"
            )
            return truncated
        else:
            # 没有视觉标记，保留前后各一半
            half = max_chars // 2
            return content[:half] + "\n\n...[中间部分已省略]...\n\n" + content[-half:]

    def _parse_sync_response(self, content: str, fallback_content: str) -> Dict:
        """解析视觉同步LLM响应（v2.5新增）"""
        try:
            # 提取JSON
            json_start = content.find("```json")
            if json_start != -1:
                json_start = content.find("{", json_start)
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            else:
                json_str = content

            data = json.loads(json_str)

            if "synced_content" not in data:
                raise ValueError("缺少 synced_content 字段")

            return {
                "synced_content": data.get("synced_content", fallback_content),
                "body_changes_detected": data.get("body_changes_detected", []),
                "visual_updates_applied": data.get("visual_updates_applied", []),
                "no_changes_needed": data.get("no_changes_needed", False),
            }

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[视觉同步] JSON解析失败: {e}")
            return {
                "synced_content": fallback_content,
                "body_changes_detected": [],
                "visual_updates_applied": [],
                "parse_error": str(e),
            }
