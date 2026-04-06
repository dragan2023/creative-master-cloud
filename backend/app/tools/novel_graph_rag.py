"""
正文板块专属知识图谱系统
完全独立于公共知识库，不复用任何公共知识库代码
确保实体类型、关系类型、提示词工程等方面完全隔离
"""
import os
import json
import re
import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
import networkx as nx
from collections import defaultdict

from app.core.logger import get_logger
from app.utils.json_parser import RobustJSONParser, parse_json

# 尝试导入json_repair作为终极回退方案
try:
    import json_repair
    HAS_JSON_REPAIR = True
except ImportError:
    HAS_JSON_REPAIR = False


# ============================================================================
# 正文板块专属配置（完全独立，不与公共知识库共享）
# ============================================================================

# 分块配置 - 更保守的策略确保JSON不被截断
NOVEL_CHUNK_SIZE = 1500  # 约1000 tokens，确保输出可控
NOVEL_MAX_ENTITIES_PER_CHUNK = 10  # 每个chunk最多提取10个实体
NOVEL_MAX_RELATIONS_PER_CHUNK = 15  # 每个chunk最多提取15个关系

# 人物状态提取专用配置（更宽松的限制以捕获更多细节）
CHARACTER_STATE_MAX_ENTITIES = 20   # 人物状态实体数量上限（提高以捕获多个人物的变化）
CHARACTER_STATE_MAX_RELATIONS = 25  # 人物状态关系数量上限（提高以捕获复杂关系网）

# 实体类型定义（正文板块专用）
NOVEL_ENTITY_TYPES = {
    # 宏观层实体
    "主题": {"level": "macro", "description": "小说核心主题、思想内核"},
    "世界观规则": {"level": "macro", "description": "世界设定、规则体系、背景设定"},
    "人物": {"level": "macro", "description": "故事中的角色人物"},
    "故事结构": {"level": "macro", "description": "整体叙事结构、情节框架"},
    "章节概要": {"level": "macro", "description": "章节/单元的故事概要"},
    "地点": {"level": "macro", "description": "故事发生的场景地点"},
    # 微观层实体
    "详细事件": {"level": "micro", "description": "具体的情节事件"},
    "核心冲突": {"level": "micro", "description": "矛盾冲突点"},
    "角色发展弧": {"level": "micro", "description": "角色的成长变化轨迹"},
    "关键对话": {"level": "micro", "description": "重要的对话内容"},
    "情节线": {"level": "micro", "description": "情节发展线索"},
    "场景": {"level": "micro", "description": "具体的场景描写"},
    # 人物状态追踪实体（微观层）
    "身份变化": {"level": "micro", "description": "人物的职位、身份、地位的变化，如升职、贬职、身份转变等"},
    "位置变化": {"level": "micro", "description": "人物所处地点的迁移和移动轨迹"},
    "关系变化": {"level": "micro", "description": "人物间关系的变化动态，如敌对、盟友、师生、知己等关系的建立、加强、恶化或破裂"},
    "性格发展": {"level": "micro", "description": "人物性格特征的变化、心理状态演变、行为模式改变"},
    "能力成长": {"level": "micro", "description": "人物的技能提升、知识增长、实力变化等成长轨迹"},
    "心理状态": {"level": "micro", "description": "人物在特定时刻的心理状态、情绪变化、内心冲突"},
    "行为模式": {"level": "micro", "description": "人物的行为习惯、决策模式、处事风格的转变"},

    # ==================== 扩展实体：设施状态追踪 ====================
    "设施": {"level": "macro", "description": "故事中具有特定功能的场所，如商铺、医馆、客栈、官府、作坊等"},
    "设施状态变化": {"level": "micro", "description": "设施运营状态的变化，如开放/关闭/暂停营业/扩建等"},
    "设施归属变更": {"level": "micro", "description": "设施所有权或管理权的变更，如转让、继承、查封等"},
    "设施物理状态": {"level": "micro", "description": "设施物理状态的变化，如完好/损坏/修缮/扩建/毁灭等"},

    # ==================== 扩展实体：事件发展追踪 ====================
    "事件": {"level": "macro", "description": "故事中发生的具体事件，具有起因、经过和结果"},
    "事件状态变化": {"level": "micro", "description": "事件发展阶段的变化，如筹备中/进行中/高潮/结束/取消等"},
    "事件影响": {"level": "micro", "description": "事件对其他实体产生的具体影响"},
    "事件因果链": {"level": "micro", "description": "事件之间的因果关联，形成事件链"},

    # ==================== 扩展实体：群体组织追踪 ====================
    "群体组织": {"level": "macro", "description": "故事中的组织、团体或势力，如军队、门派、帮会、家族、商帮等"},
    "群体状态变化": {"level": "micro", "description": "群体状态的变化，如活跃/休整/解散/重组/壮大/衰落等"},
    "群体成员变动": {"level": "micro", "description": "群体成员的加入、退出、晋升、死亡等变动"},
    "群体关系变化": {"level": "micro", "description": "群体间关系的变化，如结盟/敌对/吞并/分裂等"},

    # ==================== 扩展实体：道具物品追踪 ====================
    "道具物品": {"level": "macro", "description": "故事中的重要物品，包括武器、药品、信物、工具、秘籍等"},
    "道具状态变化": {"level": "micro", "description": "道具状态的变化，如完好/损坏/强化/消耗/遗失等"},
    "道具归属变更": {"level": "micro", "description": "道具所有权或持有权的变更，如获得/赠送/交易/遗失等"},
    "道具功能使用": {"level": "micro", "description": "道具功能的发挥或使用记录"},

    # ==================== 扩展实体：世界观一致性 ====================
    "世界规则": {"level": "macro", "description": "故事世界观中的核心规则，如武功体系、政治制度、地理规则等"},
    "规则引用": {"level": "micro", "description": "章节中对世界规则的具体引用或运用"},
    "规则例外": {"level": "micro", "description": "对已确立规则的突破或例外情况"},

    # ==================== 扩展实体：时间线追踪 ====================
    "时间节点": {"level": "macro", "description": "故事中的重要时间节点，如节日、季节、特殊日期等"},
    "时间流逝": {"level": "micro", "description": "故事中时间的流逝记录，用于维持时间一致性"},

    # ==================== 扩展实体：伏笔追踪 ====================
    "伏笔": {"level": "micro", "description": "埋下的伏笔或线索，需要在后续章节回收"},
    "伏笔回收": {"level": "micro", "description": "对已埋伏笔的回收或揭示"},

    # ==================== 扩展实体：剧本场景追踪（剧本专用）====================
    "剧本场景": {"level": "macro", "description": "剧本中的完整场景单元，包含场景头信息（地点/时间/内外景）、在场角色、场景目的等"},
    "场景转换": {"level": "micro", "description": "场景间的转换方式，如切、淡入淡出、叠化、划变等"},
    "场景氛围": {"level": "micro", "description": "场景的视觉氛围设定，如光影基调、色调、情绪氛围"},
    "拍摄要求": {"level": "micro", "description": "场景的特殊拍摄需求，如特效类型、绿幕需求、特殊设备、安全措施"},

    # ==================== 扩展实体：对白风格追踪（剧本专用）====================
    "对白风格": {"level": "macro", "description": "角色的台词风格特征，包括口癖、语气特点、用词习惯、语言风格等"},
    "对白变化": {"level": "micro", "description": "角色对白风格的转变，如从正式到随意、从冷淡到热情、从粗鲁到礼貌等"},
    "口头禅": {"level": "micro", "description": "角色特有的口头禅、常用表达、标志性台词"},
    "语言特点": {"level": "micro", "description": "角色的语言习惯，如方言口音、专业术语偏好、俚语使用、句式特点"}
}

# 关系类型定义（正文板块专用，与公共知识库完全不同）
NOVEL_RELATION_TYPES = {
    # 宏观层内部关系
    "体现于": "主题/规则体现于具体内容",
    "属于": "实体属于某个类别或整体",
    "包含": "整体包含部分",
    "影响": "一个实体对另一个实体产生影响",
    # 宏观与微观之间的桥梁关系
    "经历": "人物经历某个事件",
    "参与": "人物参与某个活动/事件",
    "展开为": "宏观概念展开为具体内容",
    "约束": "规则约束具体行为",
    "渗透于": "主题渗透于具体情节",
    "定位": "确定位置或关系",
    "发生于": "事件发生的地点/时间",
    # 微观层内部关系
    "前序": "事件的前序事件",
    "导致": "一个事件导致另一个事件",
    "包含冲突": "事件包含的冲突",
    "触发于": "由某事触发",
    "发生于事件": "在某事件中发生",
    "包含事件": "包含的具体事件",
    "关联": "一般关联关系",
    "关联人物": "与人物相关",
    # 人物状态追踪关系
    "身份转变为": "人物身份从一个状态转变为另一个状态",
    "迁移至": "人物从一个位置移动到另一个位置",
    "关系建立": "人物间建立某种关系",
    "关系恶化": "人物间关系恶化",
    "关系改善": "人物间关系改善",
    "关系破裂": "人物间关系破裂",
    "性格转变": "人物性格发生转变",
    "能力提升": "人物能力得到提升",
    "心理变化": "人物心理状态发生变化",
    "行为转变": "人物行为模式发生转变",
    "发生于章节": "状态变化发生的章节",
    "导致变化": "某个事件导致人物状态变化",
    "影响人物": "某因素对人物产生影响",
    "前后状态": "人物状态的前后变化关系",

    # ==================== 扩展关系：设施相关 ====================
    "设施位于": "设施位于某地点",
    "设施归属": "设施归属某人/组织",
    "设施状态变为": "设施状态从一个状态变为另一个",
    "设施转让": "设施所有权从一方转让给另一方",
    "设施损坏": "设施遭受损坏",
    "设施修复": "设施被修复",
    "设施扩建": "设施进行扩建",
    "设施关闭": "设施关闭停止运营",
    "设施重开": "设施重新开放",
    "使用设施": "人物使用某设施",
    "管理设施": "人物管理某设施",

    # ==================== 扩展关系：事件相关 ====================
    "事件发生": "事件发生在某地点/时间",
    "事件参与": "人物参与某事件",
    "事件发起": "人物发起某事件",
    "事件影响实体": "事件影响某人/物/地点",
    "事件导致事件": "事件导致另一事件",
    "事件解决": "事件被某人/方式解决",
    "事件升级": "事件升级为更大事件",
    "事件平息": "事件被平息",
    "处于阶段": "事件处于某阶段",

    # ==================== 扩展关系：群体相关 ====================
    "群体隶属": "人物隶属于某群体",
    "群体领导": "人物领导某群体",
    "群体敌对": "群体之间敌对",
    "群体结盟": "群体之间结盟",
    "群体吞并": "群体吞并另一群体",
    "群体分裂": "群体分裂出子群体",
    "群体合作": "群体之间合作",
    "群体解散": "群体解散",
    "群体重组": "群体重组",
    "成员加入": "人物加入群体",
    "成员退出": "人物退出群体",
    "成员晋升": "人物在群体中晋升",
    "群体领地": "群体占据某领地",

    # ==================== 扩展关系：道具相关 ====================
    "物品持有": "人物持有某物品",
    "物品获得": "人物获得某物品",
    "物品遗失": "人物遗失某物品",
    "物品赠送": "人物赠送物品给另一人物",
    "物品交易": "人物交易某物品",
    "物品使用": "人物使用某物品",
    "物品损坏": "物品损坏",
    "物品修复": "物品被修复",
    "物品强化": "物品被强化提升",
    "物品消耗": "物品被消耗",
    "物品归属": "物品归属于某人",

    # ==================== 扩展关系：世界观一致性 ====================
    "遵循规则": "某行为遵循世界规则",
    "突破规则": "某行为突破世界规则",
    "规则限制": "规则限制某行为",
    "规则确立": "规则在某章节确立",
    "引用规则": "章节引用某规则",

    # ==================== 扩展关系：时间线 ====================
    "发生在时间": "某事发生在某时间",
    "时间先后": "两个时间的先后关系",
    "时间跨度": "时间流逝的跨度",
    "时间周期": "时间的周期规律",

    # ==================== 扩展关系：伏笔 ====================
    "埋设伏笔": "在某处埋设伏笔",
    "回收伏笔": "回收已埋的伏笔",
    "伏笔关联": "伏笔与后续情节的关联",
    "伏笔对应": "伏笔与回收点对应",

    # ==================== 扩展关系：通用一致性 ====================
    "导致结果": "某原因导致某结果",
    "产生影响": "某因素产生影响",
    "状态延续": "状态从前文延续",
    "状态改变": "状态发生改变",
    "互相关联": "实体之间互相关联",
    "存在依赖": "某实体依赖于另一实体",

    # ==================== 扩展关系：剧本场景相关（剧本专用）====================
    "场景前序": "场景的前序场景，表示场景播放顺序",
    "场景后续": "场景的后续场景，表示场景播放顺序",
    "场景包含": "场景包含人物/事件/对话等内容",
    "场景发生于": "场景发生的地点和时间",
    "场景转换至": "一个场景转换到另一个场景的方式",
    "人物出场于": "人物出场于某场景",
    "人物退场于": "人物退场于某场景",
    "场景氛围设定": "场景的氛围设定描述",
    "场景拍摄需求": "场景的特殊拍摄需求",
    "场景内外景": "场景是内景还是外景",
    "场景时间设定": "场景的时间设定（日/夜/晨/暮）",

    # ==================== 扩展关系：对白风格相关（剧本专用）====================
    "拥有风格": "角色拥有某种对白风格",
    "风格转变": "对白风格从一种转变为另一种",
    "影响台词": "某因素影响角色台词风格",
    "风格体现于": "对白风格体现于具体台词",
    "口头禅使用": "角色使用某口头禅",
    "语言习惯": "角色具有某语言习惯",
    "台词风格继承": "角色的台词风格继承自某人物/背景"
}

# 禁止使用的关系类型（这些是公共知识库专用的）
FORBIDDEN_RELATION_TYPES = {
    "体现了", "应用了", "符合", "违背了",
    "衍生自", "互补于", "应用于", "限制于",
    "基于", "理论依据", "科学基础", "核心技能支撑",
    "理论基础", "方法论", "实践应用", "案例"
}

# 正文板块专用提取提示词（精简版，减少token消耗）
# 人物状态追踪专用提取提示词
CHARACTER_STATE_EXTRACTION_PROMPT = """你是资深的小说人物状态追踪专家，擅长从文学作品中精准识别人物的状态变化。

## 核心任务
从章节内容中提取**关键的人物状态变化实体和关系**，用于构建人物状态档案。

## 提取原则（重要）

### 0. 【最重要】只提取实际出场人物
- **严格限定**：只为本章中**实际出场并有行动/对话**的人物提取状态变化
- **禁止提取**：仅在已知人物列表中但本章未出场的人物
- **禁止幻觉**：不要根据人物设定猜测其状态，必须有文本依据
- 判断是否出场的标准：人物在本章中有明确的动作、对话、心理描写
- 反例："秦良凤"仅出现在人物列表中，本章未提及→**不提取**

### 1. 只提取实质性变化
- ✅ 提取：明确的状态变化（升职、受伤、关系破裂、学会新技能）
- ❌ 不提取：静态描述、重复信息、无关细节

### 2. 变化必须可验证
每个变化都必须在文本中有明确的依据：
- 直接描述："他被任命为将军" → 身份变化
- 间接暗示但明确："从此他背负起了家族的重担" → 心理/责任变化
- ❌ 猜测性内容不提取

### 3. 优先级排序
**高优先级（必提取）：**
- 身份/地位的根本性转变
- 人物间关系的质变（敌→友、友→敌、恋人→陌生人）
- 关键能力突破
- 重要位置转移

**中优先级（建议提取）：**
- 性格特征的明显演变
- 心理状态的重大转折
- 行为模式的显著改变

**低优先级（可选）：**
- 情绪波动（除非影响后续情节）
- 次要关系调整

## 实体类型与识别标准

### 身份变化
**定义：** 社会角色、职位、地位的正式或非正式改变
**识别关键词：** 任命、晋升、贬谪、继承、放弃、成为、不再是、封号、称号
**示例：**
```json
{{
  "text": "晋升为监察御史",
  "type": "身份变化",
  "character": "范闲",
  "description": "从平民被皇帝任命为监察御史，获得官方身份"
}}
```

### 位置变化
**定义：** 物理位置的迁移，特别是跨区域的移动
**识别关键词：** 前往、离开、到达、返回、逃亡、追击、潜入、转移
**示例：**
```json
{{
  "text": "从京城前往北齐",
  "type": "位置变化",
  "character": "范闲",
  "description": "接受秘密任务，从京城出发前往北齐边境"
}}
```

### 关系变化
**定义：** 人际关系性质的改变（建立/恶化/改善/破裂）
**识别关键词：** 结盟、决裂、背叛、和解、相识、反目、信任、怀疑、爱慕、仇恨
**示例：**
```json
{{
  "text": "与二皇子从盟友变为对手",
  "type": "关系变化",
  "character": "范闲",
  "description": "发现二皇子参与刺杀阴谋，政治立场对立"
}}
```

### 性格发展
**定义：** 性格特征、价值观、世界观的渐进式改变
**识别关键词：** 成熟、变得、不再、开始懂得、意识到、蜕变、成长
**示例：**
```json
{{
  "text": "从天真变得深沉谨慎",
  "type": "性格发展",
  "character": "范闲",
  "description": "经历多次暗杀后，不再轻信他人，行事更加谨慎"
}}
```

### 能力成长
**定义：** 技能、知识、实力、权力的提升或丧失
**识别关键词：** 学会、掌握、突破、领悟、获得、失去、实力大增、武功精进
**示例：**
```json
{{
  "text": "真气修为达到九品巅峰",
  "type": "能力成长",
  "character": "范闲",
  "description": "苦练霸道真气，实力接近大宗师境界"
}}
```

### 心理状态
**定义：** 特定时刻的情绪、心理状态的显著变化
**识别关键词：** 绝望、狂喜、恐惧、释然、迷茫、坚定、崩溃、觉醒
**示例：**
```json
{{
  "text": "从绝望中重燃希望",
  "type": "心理状态",
  "character": "林婉儿",
  "description": "得知范闲未死的消息后，从悲伤转为希望"
}}
```

### 行为模式
**定义：** 决策方式、行为习惯、应对策略的转变
**识别关键词：** 开始习惯、不再犹豫、学会了、改变了、策略、方式
**示例：**
```json
{{
  "text": "从冲动行事变为谋定而后动",
  "type": "行为模式",
  "character": "范若若",
  "description": "跟随范闲学习后，遇事更加冷静理智"
}}
```

## 关系类型与使用场景

| 关系类型 | 使用场景 | 示例 |
|---------|---------|------|
| **导致变化** | 事件A直接引发状态B | 刺杀事件 → 导致范闲心理变化 |
| **身份转变为** | 身份从一个状态变为另一个 | 平民 → 身份转变为 → 监察御史 |
| **迁移至** | 位置从一个地点到另一个 | 京城 → 迁移至 → 北齐 |
| **关系建立** | 新的关系形成 | 范闲 ↔ 五竹：关系建立（师徒） |
| **关系恶化** | 关系变差 | 范闲 ↔ 二皇子：关系恶化 |
| **关系改善** | 关系变好 | 范闲 ↔ 林婉儿：关系改善 |
| **关系破裂** | 彻底断绝关系 | 某人 ↔ 某人：关系破裂 |
| **性格转变为** | 性格特征改变 | 天真 → 性格转变为 → 谨慎 |
| **能力提升** | 能力增强 | 武功初阶 → 能力提升 → 九品 |
| **心理变化** | 心理状态改变 | 绝望 → 心理变化 → 希望 |
| **行为转变** | 行为模式改变 | 冲动 → 行为转变 → 理智 |
| **影响人物** | 外部因素对人的影响 | 权力 → 影响人物 → 范闲 |
| **前后状态** | 状态的前后对比 | 之前状态 ↔ 之后状态 |

## 输出格式（严格JSON）

```json
{{
  "entities": [
    {{
      "text": "变化的具体描述（20字以内）",
      "type": "必须是上述7种类型之一",
      "character": "人物名称（必须填写）",
      "chapter": {chapter_num},
      "description": "详细描述变化的原因、过程和意义（50-100字）",
      "before_state": "变化前的状态（可选）",
      "after_state": "变化后的状态（可选）",
      "trigger_event": "触发变化的关键事件（可选）"
    }}
  ],
  "relations": [
    {{
      "source": "实体A的text或事件描述",
      "target": "实体B的text或人物名称",
      "relation": "从上述关系类型中选择最准确的",
      "context": "关系的详细背景和原因（30-50字）"
    }}
  ],
  "summary": "本章节人物状态变化的整体概述（2-3句话）"
}}
```

## 质量检查清单

输出前请确认：
- [ ] 每个entity都有`character`字段且不为空
- [ ] `type`字段严格是7种类型之一
- [ ] `description`详细且有文本依据（不是猜测）
- [ ] 实体数量不超过{max_entities}个（优先保留高优先级）
- [ ] 关系数量不超过{max_relations}个
- [ ] 避免提取重复或过于相似的变化

## 待分析的章节内容（第{chapter_num}章）

{content}

## 【再次强调】出场人物约束

**已知人物列表仅供参考，你必须严格遵守以下规则：**
1. 只为本章中**实际出场**的人物提取状态变化
2. 如果某个人物在本章内容中没有被提及或没有行动，**绝对不要为其生成任何实体**
3. 空的entities数组是完全可以接受的（如果本章没有状态变化）

**重要：请严格按照JSON格式输出，输出必须是合法的JSON字符串，不要添加任何markdown标记、注释或其他说明文字。直接输出JSON对象，不要用代码块包裹。**

**格式要求（非常重要）：**
1. 每个键名必须是纯英文，不要包含换行符、空格或引号
2. 正确示例："text": "晋升为监察御史"
3. 错误示例："\n  \"text\"": "晋升为监察御史"（键名包含换行符和引号）
4. 所有字符串值必须用双引号包裹，不要使用单引号
5. 确保JSON格式正确，可以被Python json.loads()直接解析"""

# 扩展状态提取提示词（设施、事件、群体、道具、世界规则、时间线、伏笔）
EXTENDED_STATE_EXTRACTION_PROMPT = """你是资深的小说一致性追踪专家，擅长从文学作品中识别所有影响后续一致性的实体和关系。

## 核心任务
从章节内容中提取**所有需要追踪的一致性相关实体和关系**，包括：
1. 人物状态（身份、位置、关系、能力等）- 已有专用提取器
2. 设施状态（场所的运营、归属、物理状态等）
3. 事件发展（事件阶段、影响、因果链等）
4. 群体动态（组织状态、成员变动、群体关系等）
5. 道具物品（持有、状态、归属等）
6. 世界规则（规则引用、例外情况等）
7. 时间线（重要时间节点、时间流逝等）
8. 伏笔线索（埋设和回收）

## 提取原则

### 1. 一致性优先
只提取对后续章节有一致性影响的信息：
- ✓ 提取：会影响后续情节的状态（设施关闭、人物受伤、道具损坏等）
- ✓ 提取：需要后续呼应的内容（伏笔、未解决的事件等）
- ✗ 不提取：一次性描述、无关细节

### 2. 状态变化导向
重点关注**变化**而非静态描述：
- 设施从“营业中”变为“暂停营业”
- 道具从“完好”变为“损坏”
- 群体从“三百人”变为“五百人”

### 3. 可追踪性
每个实体都需要有足够的信息用于后续追踪：
- 设施：需要名称、位置、负责人
- 事件：需要名称、类型、关键人物
- 群体：需要名称、规模、领导者
- 道具：需要名称、类型、持有者

## 实体类型详解

### 设施相关实体

| 类型 | 描述 | 必填字段 | 示例 |
|-----|------|---------|-----|
| 设施 | 功能场所 | text, 位置, 负责人 | 锦绣坊 |
| 设施状态变化 | 运营状态变化 | facility, 变化类型 | 暂停营业 |
| 设施归属变更 | 所有权变更 | facility, 原归属, 新归属 | 转让给李家 |
| 设施物理状态 | 物理状态变化 | facility, 状态类型 | 遭火灾焚毁 |

### 事件相关实体

| 类型 | 描述 | 必填字段 | 示例 |
|-----|------|---------|-----|
| 事件 | 具体事件 | text, 涉及人物, 发生地点 | 悬壶堂中毒案 |
| 事件状态变化 | 事件阶段变化 | event, 当前阶段 | 进入调查阶段 |
| 事件影响 | 事件产生的后果 | event, 受影响实体, 影响类型 | 悬壶堂声誉受损 |
| 事件因果链 | 事件关联 | 前序事件, 后续事件 | 导致后续抓捕行动 |

### 群体相关实体

| 类型 | 描述 | 必填字段 | 示例 |
|-----|------|---------|-----|
| 群体组织 | 组织团体 | text, 规模, 性质 | 娄山众 |
| 群体状态变化 | 群体状态变化 | group, 变化类型 | 规模壮大到五百人 |
| 群体成员变动 | 成员进出 | group, 成员名称, 变动类型 | 杨英龙加入 |
| 群体关系变化 | 群体间关系 | 群体1, 群体2, 关系类型 | 与黑风寨结盟 |

### 道具相关实体

| 类型 | 描述 | 必填字段 | 示例 |
|-----|------|---------|-----|
| 道具物品 | 重要物品 | text, 物品类型, 持有者 | 手术刀 |
| 道具状态变化 | 物品状态变化 | item, 状态类型 | 磨损变钝 |
| 道具归属变更 | 所有权变更 | item, 原持有者, 新持有者 | 赠送给张三 |
| 道具功能使用 | 使用记录 | item, 使用场景, 效果 | 用于救治伤者 |

### 其他实体

| 类型 | 描述 | 必填字段 | 示例 |
|-----|------|---------|-----|
| 世界规则 | 核心规则 | text, 规则类型 | 武功等级体系 |
| 规则引用 | 规则运用 | rule, 引用章节 | 达到九品境界 |
| 伏笔 | 埋设的伏笔 | text, 埋设章节, 重要程度 | 神秘人的身份 |
| 伏笔回收 | 伏笔揭示 | foreshadowing, 回收章节 | 真相大白 |
| 时间节点 | 重要时间 | text, 时间类型 | 中秋节 |

## 关系类型

### 设施关系
- 设施位于、设施归属、设施状态变为、设施转让、使用设施

### 事件关系
- 事件发生、事件参与、事件发起、事件影响实体、事件导致事件、处于阶段

### 群体关系
- 群体隶属、群体领导、群体敌对、群体结盟、成员加入、成员退出

### 道具关系
- 物品持有、物品获得、物品遗失、物品赠送、物品使用、物品损坏

### 通用关系
- 导致结果、产生影响、状态延续、状态改变

## 输出格式

```json
{{
  "entities": [
    {{
      "text": "实体名称",
      "type": "实体类型",
      "level": "macro或micro",
      "chapter": {chapter_num},
      "attributes": {{}},
      "description": "描述"
    }}
  ],
  "relations": [
    {{
      "source": "实体A",
      "target": "实体B",
      "relation": "关系类型",
      "context": "关系背景",
      "chapter": {chapter_num}
    }}
  ],
  "consistency_notes": [
    "需要注意的一致性问题，如'悬壶堂中毒案尚未解决'"
  ]
}}
```

## 质量检查清单

输出前请确认：
- [ ] 每个实体都有明确的类型，且类型在定义范围内
- [ ] 设施/事件/群体/道具实体有足够的追踪属性
- [ ] 描述详细且有文本依据
- [ ] 实体数量不超过{max_entities}个
- [ ] 关系数量不超过{max_relations}个

## 待分析内容（第{chapter_num}章）

{content}

请严格按照JSON格式输出："""

NOVEL_EXTRACTION_PROMPT = """你是小说知识图谱专家。从以下内容中提取实体和关系。

**严格限制：**
- 实体数量不超过{max_entities}个
- 关系数量不超过{max_relations}个
- 只提取最核心、最重要的实体和关系

**【重要】实体消歧规则（必须严格遵守）：**

1. **同一人物的不同称谓必须统一为正式名称：**
   - 如果文本中出现"现代医生"但明确指代某个人物（如"孙昭龙"），则只提取正式名称"孙昭龙"
   - 职业称谓（医生、将军、皇帝等）+ 身份描述（现代人、穿越者等）如果指代已知人物，使用人物本名
   - 示例："现代医生孙昭龙穿越到古代" → 实体="孙昭龙"，不单独创建"现代医生"实体

2. **识别指代关系的判断标准：**
   - 同一句子或相邻句子中同时出现两个名称，且存在从属/等同关系
   - 格式1："称谓 + 人名"（如"现代医生孙昭龙"、"将军李明"）
   - 格式2："人名，人称谓"（如"孙昭龙，一个现代医生"）
   - 格式3："作为/担任/是 + 称谓 + 的 + 人名"

3. **禁止创建的重复实体类型：**
   - ❌ 不要同时创建"现代医生"和"孙昭龙"
   - ❌ 不要将职业/身份作为独立实体（除非是抽象概念）
   - ✅ 应该只保留人物的正式名称作为实体

4. **实体命名规范：**
   - 人物类实体：使用最完整的正式名称
   - 地点类实体：使用标准地名
   - 抽象概念：使用简洁明确的表述

**禁止使用的关系类型：** 体现了、应用了、符合、违背了、衍生自、互补于、应用于、限制于、基于、理论依据

**实体类型：**
- 宏观层：主题、世界观规则、人物、故事结构、章节概要、地点
- 微观层：详细事件、核心冲突、角色发展弧、关键对话、情节线、场景
- 人物状态追踪：身份变化、位置变化、关系变化、性格发展、能力成长、心理状态、行为模式

**关系类型：**
- 宏观层：体现于、属于、包含、影响
- 桥梁：经历、参与、展开为、约束、渗透于、定位、发生于
- 微观层：前序、导致、包含冲突、触发于、发生于事件、包含事件、关联、关联人物
- 人物状态追踪：身份转变为、迁移至、关系建立、关系恶化、关系改善、关系破裂、性格转变、能力提升、心理变化、行为转变、导致变化、影响人物、前后状态

**输出格式（严格JSON）：**
```json
{{
  "entities": [
    {{"text": "名称", "type": "类型", "level": "macro或micro", "description": "简短描述", "character": "关联人物（仅人物状态实体需要）", "chapter": 章节号（仅人物状态实体需要）}}
  ],
  "relations": [
    {{"source": "实体A", "target": "实体B", "relation": "关系类型"}}
  ]
}}
```

待分析内容：
{content}

请直接输出JSON，不要有其他说明："""


# ============================================================================
# 正文板块专属知识图谱类
# ============================================================================

class NovelKnowledgeGraph:
    """
    正文板块专属知识图谱
    完全独立于公共知识库的KnowledgeGraph类
    """

    def __init__(self, persist_path: str = None):
        """
        初始化知识图谱

        Args:
            persist_path: 持久化文件路径
        """
        self.graph = nx.DiGraph()
        self.persist_path = persist_path
        self.logger = get_logger("novel_knowledge_graph")
        self.entity_index = {}  # 实体文本到节点ID的映射

    def load(self) -> bool:
        """加载图谱"""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return False

        try:
            with open(self.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.graph.clear()
            self.entity_index.clear()

            # 加载节点
            for node in data.get("nodes", []):
                node_id = node.get("id")
                self.graph.add_node(
                    node_id, **{k: v for k, v in node.items() if k != "id"})
                # 建立索引
                text = node.get("text", "")
                if text:
                    self.entity_index[text] = node_id

            # 加载边
            for edge in data.get("edges", []):
                source = edge.get("source")
                target = edge.get("target")
                if source and target:
                    self.graph.add_edge(
                        source, target, **{k: v for k, v in edge.items() if k not in ["source", "target"]})

            self.logger.debug(
                f"正文板块图谱已加载: {os.path.basename(self.persist_path)}, 节点数: {self.graph.number_of_nodes()}, 边数: {self.graph.number_of_edges()}")
            return True

        except Exception as e:
            self.logger.error(f"加载正文板块图谱失败: {e}")
            return False

    def save(self) -> bool:
        """保存图谱"""
        if not self.persist_path:
            return False

        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)

            data = {
                "nodes": [
                    {"id": node_id, **data}
                    for node_id, data in self.graph.nodes(data=True)
                ],
                "edges": [
                    {"source": source, "target": target, **data}
                    for source, target, data in self.graph.edges(data=True)
                ]
            }

            with open(self.persist_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.debug(
                f"正文板块图谱已保存: {os.path.basename(self.persist_path)}, 节点数: {self.graph.number_of_nodes()}, 边数: {self.graph.number_of_edges()}")
            return True

        except Exception as e:
            self.logger.error(f"保存正文板块图谱失败: {e}")
            return False

    def add_entity(self, entity_data: Dict[str, Any], doc_id: str = "") -> str:
        """
        添加实体到图谱

        Args:
            entity_data: 实体数据，包含 text, type, level, description 等
            doc_id: 文档ID

        Returns:
            节点ID
        """
        import uuid

        text = entity_data.get("text", "")

        # 检查是否已存在相同文本的实体
        if text in self.entity_index:
            # 更新现有节点
            node_id = self.entity_index[text]
            # 合并属性
            existing_data = dict(self.graph.nodes[node_id])
            existing_data.update(entity_data)
            existing_data["doc_ids"] = existing_data.get("doc_ids", [])
            if doc_id and doc_id not in existing_data["doc_ids"]:
                existing_data["doc_ids"].append(doc_id)
            self.graph.nodes[node_id].update(existing_data)
            return node_id

        # 创建新节点
        node_id = str(uuid.uuid4())
        node_data = {
            **entity_data,
            "doc_ids": [doc_id] if doc_id else []
        }
        self.graph.add_node(node_id, **node_data)
        self.entity_index[text] = node_id

        return node_id

    def add_relation(self, relation_data: Dict[str, Any], doc_id: str = "") -> bool:
        """
        添加关系到图谱

        Args:
            relation_data: 关系数据，包含 source, target, relation 等
            doc_id: 文档ID

        Returns:
            是否成功
        """
        source_text = relation_data.get("source", "")
        target_text = relation_data.get("target", "")
        relation_type = relation_data.get("relation", "关联")

        # 过滤禁止的关系类型
        if relation_type in FORBIDDEN_RELATION_TYPES:
            self.logger.warning(f"过滤禁止的关系类型: {relation_type}")
            return False

        # 查找或创建节点
        if source_text not in self.entity_index:
            self.add_entity({"text": source_text, "type": "未知"}, doc_id)
        if target_text not in self.entity_index:
            self.add_entity({"text": target_text, "type": "未知"}, doc_id)

        source_id = self.entity_index[source_text]
        target_id = self.entity_index[target_text]

        # 添加边
        edge_data = {
            "relation": relation_type,
            "context": relation_data.get("context", ""),
            "doc_ids": [doc_id] if doc_id else []
        }

        # 如果边已存在，更新doc_ids
        if self.graph.has_edge(source_id, target_id):
            existing_data = self.graph.edges[source_id, target_id]
            edge_data["doc_ids"] = list(
                set(existing_data.get("doc_ids", []) + edge_data["doc_ids"]))

        self.graph.add_edge(source_id, target_id, **edge_data)
        return True

    def get_entity_by_text(self, text: str) -> Optional[Dict[str, Any]]:
        """根据文本获取实体"""
        if text in self.entity_index:
            node_id = self.entity_index[text]
            return {"id": node_id, **self.graph.nodes[node_id]}
        return None

    def get_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """根据类型获取所有实体

        Args:
            entity_type: 实体类型（如"人物"、"地点"、"世界观规则"等）

        Returns:
            该类型的所有实体列表
        """
        entities = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") == entity_type:
                entities.append({
                    "id": node_id,
                    "name": data.get("text", ""),
                    "type": data.get("type", ""),
                    "description": data.get("description", ""),
                    "attributes": data.get("attributes", {}),
                    "level": data.get("level", "")
                })
        return entities

    def get_character_profiles(self) -> List[Dict[str, Any]]:
        """获取所有人物档案

        将知识图谱中的"人物"类型实体转换为角色设定格式，
        供写手Agent使用。

        Returns:
            角色设定列表，每个元素包含 name, role, personality, background 等
        """
        characters = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") == "人物":
                attrs = data.get("attributes", {})
                character = {
                    "name": data.get("text", ""),
                    "role": attrs.get("role", attrs.get("身份", "")),
                    "personality": attrs.get("personality", attrs.get("性格", "")),
                    "background": attrs.get("background", attrs.get("背景", "")),
                    "description": data.get("description", ""),
                    "age": attrs.get("age", attrs.get("年龄", "")),
                    "gender": attrs.get("gender", attrs.get("性别", "")),
                    "appearance": attrs.get("appearance", attrs.get("外貌", "")),
                    "goals": attrs.get("goals", attrs.get("目标", "")),
                    "relationships": []
                }
                # 过滤空值
                character = {k: v for k, v in character.items() if v}
                characters.append(character)
        return characters

    def get_world_settings(self) -> Dict[str, Any]:
        """获取世界观设定

        从知识图谱中提取"世界观规则"和"地点"类型的实体，
        构建世界观设定字典。

        Returns:
            世界观设定字典
        """
        settings = {
            "rules": [],
            "locations": [],
            "time_period": "",
            "social_background": ""
        }

        for node_id, data in self.graph.nodes(data=True):
            entity_type = data.get("type", "")
            attrs = data.get("attributes", {})

            if entity_type == "世界观规则":
                settings["rules"].append({
                    "name": data.get("text", ""),
                    "description": data.get("description", "")
                })
            elif entity_type == "地点":
                settings["locations"].append({
                    "name": data.get("text", ""),
                    "description": data.get("description", "")
                })
            elif entity_type == "主题":
                settings["theme"] = data.get("text", "")
                settings["theme_description"] = data.get("description", "")

        return settings

    def get_related_entities(self, entity_text: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """获取相关实体"""
        if entity_text not in self.entity_index:
            return []

        node_id = self.entity_index[entity_text]
        related = []
        visited = {node_id}

        # BFS遍历
        current_level = [node_id]
        for depth in range(max_depth):
            next_level = []
            for current_id in current_level:
                # 出边
                for _, target, edge_data in self.graph.edges(current_id, data=True):
                    if target not in visited:
                        visited.add(target)
                        target_data = self.graph.nodes[target]
                        related.append({
                            "id": target,
                            "text": target_data.get("text", ""),
                            "type": target_data.get("type", ""),
                            "relation": edge_data.get("relation", ""),
                            "depth": depth + 1
                        })
                        next_level.append(target)

                # 入边
                for source, _, edge_data in self.graph.edges(data=True):
                    if source == current_id and source not in visited:
                        continue
                    # 简化处理，只查出边

            current_level = next_level

        return related

    def get_character_state_entities(self, character_name: str = None, chapter_num: int = None) -> Dict[str, List[Dict[str, Any]]]:
        """获取人物状态追踪实体

        从知识图谱中提取人物状态相关的实体，用于支持人物状态追踪器。

        Args:
            character_name: 人物名称（可选，筛选特定人物的实体）
            chapter_num: 章节号（可选，筛选特定章节的实体）

        Returns:
            按类型分组的人物状态实体字典
        """
        # 人物状态相关的实体类型
        state_entity_types = {
            "身份变化", "位置变化", "关系变化", "性格发展",
            "能力成长", "心理状态", "行为模式"
        }

        result = {
            "identity_changes": [],    # 身份变化
            "location_changes": [],    # 位置变化
            "relationship_changes": [],  # 关系变化
            "character_development": [],  # 性格发展
            "ability_growth": [],       # 能力成长
            "mental_states": [],        # 心理状态
            "behavior_patterns": []     # 行为模式
        }

        # 类型映射
        type_mapping = {
            "身份变化": "identity_changes",
            "位置变化": "location_changes",
            "关系变化": "relationship_changes",
            "性格发展": "character_development",
            "能力成长": "ability_growth",
            "心理状态": "mental_states",
            "行为模式": "behavior_patterns"
        }

        for node_id, data in self.graph.nodes(data=True):
            entity_type = data.get("type", "")
            if entity_type not in state_entity_types:
                continue

            # 筛选特定人物
            if character_name:
                entity_character = data.get("character", "")
                if entity_character and entity_character != character_name:
                    continue
                # 也检查实体文本中是否包含人物名称
                if not entity_character and character_name not in data.get("text", ""):
                    continue

            # 筛选特定章节
            if chapter_num is not None:
                entity_chapter = data.get("chapter")
                if entity_chapter is not None and entity_chapter != chapter_num:
                    continue

            # 添加到对应的分类
            result_key = type_mapping.get(entity_type)
            if result_key:
                result[result_key].append({
                    "id": node_id,
                    "text": data.get("text", ""),
                    "type": entity_type,
                    "character": data.get("character", ""),
                    "chapter": data.get("chapter"),
                    "description": data.get("description", ""),
                    "attributes": data.get("attributes", {})
                })

        return result

    def get_character_evolution(self, character_name: str) -> Dict[str, Any]:
        """获取人物完整演变轨迹

        综合获取指定人物的所有状态变化实体，构建演变轨迹。

        Args:
            character_name: 人物名称

        Returns:
            人物演变轨迹字典，包含各类型的状态变化按章节排序
        """
        state_entities = self.get_character_state_entities(
            character_name=character_name)

        evolution = {
            "character_name": character_name,
            "identity_evolution": [],  # 身份演变轨迹
            "location_evolution": [],   # 位置演变轨迹
            "relationship_evolution": [],  # 关系演变轨迹
            "ability_evolution": [],    # 能力演变轨迹
            "psychological_evolution": [],  # 心理演变轨迹
            "total_changes": 0
        }

        # 按章节排序整理身份变化
        for entity in sorted(state_entities["identity_changes"],
                             key=lambda x: x.get("chapter") or 0):
            evolution["identity_evolution"].append({
                "chapter": entity.get("chapter"),
                "change": entity.get("text"),
                "description": entity.get("description")
            })

        # 按章节排序整理位置变化
        for entity in sorted(state_entities["location_changes"],
                             key=lambda x: x.get("chapter") or 0):
            evolution["location_evolution"].append({
                "chapter": entity.get("chapter"),
                "location": entity.get("text"),
                "description": entity.get("description")
            })

        # 按章节排序整理关系变化
        for entity in sorted(state_entities["relationship_changes"],
                             key=lambda x: x.get("chapter") or 0):
            evolution["relationship_evolution"].append({
                "chapter": entity.get("chapter"),
                "change": entity.get("text"),
                "description": entity.get("description")
            })

        # 按章节排序整理能力成长
        for entity in sorted(state_entities["ability_growth"],
                             key=lambda x: x.get("chapter") or 0):
            evolution["ability_evolution"].append({
                "chapter": entity.get("chapter"),
                "ability": entity.get("text"),
                "description": entity.get("description")
            })
        # 按章节排序整理心理状态
        for entity in sorted(state_entities["mental_states"],
                             key=lambda x: x.get("chapter") or 0):
            evolution["psychological_evolution"].append({
                "chapter": entity.get("chapter"),
                "state": entity.get("text"),
                "description": entity.get("description")
            })

        # 计算总变化数
        evolution["total_changes"] = (
            len(evolution["identity_evolution"]) +
            len(evolution["location_evolution"]) +
            len(evolution["relationship_evolution"]) +
            len(evolution["ability_evolution"]) +
            len(evolution["psychological_evolution"])
        )

        return evolution

    def format_character_state_for_prompt(self, character_name: str, chapter_num: int = None) -> str:
        """格式化人物状态为提示词格式

        将人物状态追踪实体格式化为可读的文本，供写作Agent使用。

        Args:
            character_name: 人物名称
            chapter_num: 章节号（可选，只显示到该章节为止的状态）

        Returns:
            格式化的人物状态文本
        """
        state_entities = self.get_character_state_entities(
            character_name=character_name,
            chapter_num=chapter_num
        )

        lines = [f"## {character_name} 状态追踪", ""]

        if state_entities["identity_changes"]:
            lines.append("### 身份变化")
            for entity in state_entities["identity_changes"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
                if entity.get("description"):
                    lines.append(f"  {entity.get('description')}")
            lines.append("")

        if state_entities["location_changes"]:
            lines.append("### 位置变化")
            for entity in state_entities["location_changes"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
            lines.append("")

        if state_entities["relationship_changes"]:
            lines.append("### 关系变化")
            for entity in state_entities["relationship_changes"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
                if entity.get("description"):
                    lines.append(f"  {entity.get('description')}")
            lines.append("")
        if state_entities["ability_growth"]:
            lines.append("### 能力成长")
            for entity in state_entities["ability_growth"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
            lines.append("")
        if state_entities["mental_states"]:
            lines.append("### 心理状态")
            for entity in state_entities["mental_states"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
            lines.append("")
        if state_entities["character_development"]:
            lines.append("### 性格发展")
            for entity in state_entities["character_development"]:
                chapter_info = f"第{entity.get('chapter')}章" if entity.get(
                    'chapter') else ""
                lines.append(f"- [{chapter_info}] {entity.get('text')}")
                if entity.get("description"):
                    lines.append(f"  {entity.get('description')}")
            lines.append("")
        return "\n".join(lines)

    # ==================== 扩展一致性追踪方法 ====================

    def get_extended_state_entities(
        self,
        entity_type: str = None,
        chapter_num: int = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取扩展状态追踪实体（设施、事件、群体、道具等）

        从知识图谱中提取扩展状态相关的实体，支持全面的一致性追踪。

        Args:
            entity_type: 实体类型（可选，筛选特定类型的实体）
            chapter_num: 章节号（可选，筛选特定章节的实体）

        Returns:
            按类型分组的扩展状态实体字典
        """
        # 扩展状态相关的实体类型
        extended_entity_types = {
            # 设施相关
            "设施", "设施状态变化", "设施归属变更", "设施物理状态",
            # 事件相关
            "事件", "事件状态变化", "事件影响", "事件因果链",
            # 群体相关
            "群体组织", "群体状态变化", "群体成员变动", "群体关系变化",
            # 道具相关
            "道具物品", "道具状态变化", "道具归属变更", "道具功能使用",
            # 世界规则
            "世界规则", "规则引用", "规则例外",
            # 时间线
            "时间节点", "时间流逝",
            # 伏笔
            "伏笔", "伏笔回收"
        }

        result = {
            "facilities": [],          # 设施实体
            "facility_states": [],     # 设施状态变化
            "events": [],              # 事件实体
            "event_states": [],        # 事件状态变化
            "event_effects": [],       # 事件影响
            "groups": [],              # 群体组织
            "group_states": [],        # 群体状态变化
            "group_members": [],       # 群体成员变动
            "items": [],               # 道具物品
            "item_states": [],         # 道具状态变化
            "item_ownerships": [],     # 道具归属变更
            "world_rules": [],         # 世界规则
            "rule_references": [],     # 规则引用
            "time_nodes": [],          # 时间节点
            "time_flows": [],          # 时间流逝
            "foreshadows": [],         # 伏笔
            "foreshadow_resolutions": []  # 伏笔回收
        }

        # 类型映射
        type_mapping = {
            "设施": "facilities",
            "设施状态变化": "facility_states",
            "设施归属变更": "facility_states",
            "设施物理状态": "facility_states",
            "事件": "events",
            "事件状态变化": "event_states",
            "事件影响": "event_effects",
            "事件因果链": "event_effects",
            "群体组织": "groups",
            "群体状态变化": "group_states",
            "群体成员变动": "group_members",
            "群体关系变化": "group_states",
            "道具物品": "items",
            "道具状态变化": "item_states",
            "道具归属变更": "item_ownerships",
            "道具功能使用": "item_states",
            "世界规则": "world_rules",
            "规则引用": "rule_references",
            "规则例外": "rule_references",
            "时间节点": "time_nodes",
            "时间流逝": "time_flows",
            "伏笔": "foreshadows",
            "伏笔回收": "foreshadow_resolutions"
        }

        for node_id, data in self.graph.nodes(data=True):
            entity_type_val = data.get("type", "")

            # 筛选扩展类型
            if entity_type_val not in extended_entity_types:
                continue

            # 筛选特定类型
            if entity_type and entity_type_val != entity_type:
                continue

            # 筛选特定章节
            if chapter_num is not None:
                entity_chapter = data.get("chapter")
                if entity_chapter is not None and entity_chapter != chapter_num:
                    continue

            # 添加到对应的分类
            result_key = type_mapping.get(entity_type_val)
            if result_key:
                result[result_key].append({
                    "id": node_id,
                    "text": data.get("text", ""),
                    "type": entity_type_val,
                    "chapter": data.get("chapter"),
                    "description": data.get("description", ""),
                    "attributes": data.get("attributes", {}),
                    "level": data.get("level", "")
                })

        return result

    def get_consistency_report(self, chapter_num: int = None) -> Dict[str, Any]:
        """
        获取一致性报告，供写作Agent参考

        返回所有需要保持一致性的实体状态摘要，包括：
        - 人物状态摘要
        - 设施状态摘要
        - 未完成事件
        - 群体动态
        - 道具归属
        - 待回收伏笔
        - 规则约束

        Args:
            chapter_num: 章节号（可选，只显示到该章节为止的状态）

        Returns:
            一致性报告字典
        """
        report = {
            "chapter": chapter_num,
            "character_states": {},
            "facility_states": {},
            "unfinished_events": [],
            "group_states": {},
            "item_ownership": {},
            "pending_foreshadows": [],
            "active_rules": [],
            "time_context": {},
            "consistency_warnings": []
        }

        # 1. 获取人物状态摘要
        report["character_states"] = self._get_character_states_summary(
            chapter_num)

        # 2. 获取设施状态摘要
        report["facility_states"] = self._get_facility_states_summary(
            chapter_num)

        # 3. 获取未完成事件
        report["unfinished_events"] = self._get_unfinished_events(chapter_num)

        # 4. 获取群体动态
        report["group_states"] = self._get_group_states_summary(chapter_num)

        # 5. 获取道具归属
        report["item_ownership"] = self._get_item_ownership_summary(
            chapter_num)

        # 6. 获取待回收伏笔
        report["pending_foreshadows"] = self._get_pending_foreshadows(
            chapter_num)

        # 7. 获取规则约束
        report["active_rules"] = self._get_active_rules(chapter_num)

        # 8. 获取时间上下文
        report["time_context"] = self._get_time_context(chapter_num)

        # 9. 生成一致性警告
        report["consistency_warnings"] = self._generate_consistency_warnings(
            report)

        return report

    def _get_character_states_summary(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取人物状态摘要"""
        state_entities = self.get_character_state_entities(
            chapter_num=chapter_num)

        summary = {}
        # 按人物整理状态
        all_entities = (
            state_entities["identity_changes"] +
            state_entities["location_changes"] +
            state_entities["relationship_changes"] +
            state_entities["ability_growth"] +
            state_entities["mental_states"] +
            state_entities["character_development"] +
            state_entities["behavior_patterns"]
        )

        for entity in all_entities:
            char_name = entity.get("character", "")
            if not char_name:
                continue

            if char_name not in summary:
                summary[char_name] = {
                    "latest_identity": None,
                    "latest_location": None,
                    "key_relationships": [],
                    "abilities": [],
                    "mental_state": None,
                    "character_development": [],
                    "behavior_patterns": []
                }

            entity_type = entity.get("type", "")
            if entity_type == "身份变化":
                summary[char_name]["latest_identity"] = entity.get("text", "")
            elif entity_type == "位置变化":
                summary[char_name]["latest_location"] = entity.get("text", "")
            elif entity_type == "关系变化":
                summary[char_name]["key_relationships"].append(
                    entity.get("text", ""))
            elif entity_type == "能力成长":
                summary[char_name]["abilities"].append(entity.get("text", ""))
            elif entity_type == "心理状态":
                summary[char_name]["mental_state"] = entity.get("text", "")
            elif entity_type == "性格发展":
                summary[char_name]["character_development"].append(
                    entity.get("text", ""))
            elif entity_type == "行为模式":
                summary[char_name]["behavior_patterns"].append(
                    entity.get("text", ""))

        return summary

    def _get_facility_states_summary(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取设施状态摘要"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        summary = {}

        # 处理设施实体
        for facility in extended_entities["facilities"]:
            name = facility.get("text", "")
            if name:
                summary[name] = {
                    "type": facility.get("attributes", {}).get("功能类型", ""),
                    "location": facility.get("attributes", {}).get("位置", ""),
                    "manager": facility.get("attributes", {}).get("负责人", ""),
                    "status": "正常运营",  # 默认状态
                    "status_changes": []
                }

        # 更新设施状态变化
        for state in extended_entities["facility_states"]:
            facility_name = state.get("attributes", {}).get("设施名称", "")
            if facility_name and facility_name in summary:
                summary[facility_name]["status"] = state.get("text", "")
                summary[facility_name]["status_changes"].append({
                    "chapter": state.get("chapter"),
                    "change": state.get("text", "")
                })

        return summary

    def _get_unfinished_events(self, chapter_num: int = None) -> List[Dict[str, Any]]:
        """获取未完成事件"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        unfinished = []

        # 处理事件实体
        for event in extended_entities["events"]:
            event_info = {
                "name": event.get("text", ""),
                "type": event.get("attributes", {}).get("事件类型", ""),
                "status": "进行中",  # 默认状态
                "involved_characters": event.get("attributes", {}).get("涉及人物", []),
                "location": event.get("attributes", {}).get("发生地点", "")
            }
            unfinished.append(event_info)

        # 更新事件状态
        for state in extended_entities["event_states"]:
            event_name = state.get("attributes", {}).get("事件名称", "")
            for event in unfinished:
                if event["name"] == event_name:
                    event["status"] = state.get(
                        "attributes", {}).get("当前阶段", "")
                    break

        # 只返回未完成的事件
        unfinished = [e for e in unfinished if e["status"]
                      not in ["已完成", "已结束", "已取消"]]

        return unfinished

    def _get_group_states_summary(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取群体动态摘要"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        summary = {}

        # 处理群体组织
        for group in extended_entities["groups"]:
            name = group.get("text", "")
            if name:
                summary[name] = {
                    "scale": group.get("attributes", {}).get("规模", ""),
                    "nature": group.get("attributes", {}).get("性质", ""),
                    "leader": None,
                    "status": "活跃",
                    "members": [],
                    "allies": [],
                    "enemies": []
                }

        # 更新成员变动
        for member in extended_entities["group_members"]:
            group_name = member.get("attributes", {}).get("群体名称", "")
            if group_name and group_name in summary:
                member_name = member.get("attributes", {}).get("成员名称", "")
                变动类型 = member.get("attributes", {}).get("变动类型", "")
                if 变动类型 in ["加入", "晋升"]:
                    summary[group_name]["members"].append(member_name)
                elif 变动类型 == "领导":
                    summary[group_name]["leader"] = member_name

        return summary

    def _get_item_ownership_summary(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取道具归属摘要"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        summary = {}

        # 处理道具物品
        for item in extended_entities["items"]:
            name = item.get("text", "")
            if name:
                summary[name] = {
                    "type": item.get("attributes", {}).get("物品类型", ""),
                    "owner": item.get("attributes", {}).get("持有者", ""),
                    "status": "完好",
                    "description": item.get("description", "")
                }

        # 更新归属变更
        for ownership in extended_entities["item_ownerships"]:
            item_name = ownership.get("attributes", {}).get("物品名称", "")
            if item_name and item_name in summary:
                new_owner = ownership.get("attributes", {}).get("新持有者", "")
                if new_owner:
                    summary[item_name]["owner"] = new_owner

        # 更新状态变化
        for state in extended_entities["item_states"]:
            item_name = state.get("attributes", {}).get("物品名称", "")
            if item_name and item_name in summary:
                summary[item_name]["status"] = state.get("text", "")

        return summary

    def _get_pending_foreshadows(self, chapter_num: int = None) -> List[Dict[str, Any]]:
        """获取待回收伏笔"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        pending = []
        resolved = set()

        # 先收集已回收的伏笔
        for resolution in extended_entities["foreshadow_resolutions"]:
            foreshadow_name = resolution.get("attributes", {}).get("伏笔名称", "")
            if foreshadow_name:
                resolved.add(foreshadow_name)

        # 再收集未回收的伏笔
        for foreshadow in extended_entities["foreshadows"]:
            name = foreshadow.get("text", "")
            if name and name not in resolved:
                pending.append({
                    "name": name,
                    "planted_chapter": foreshadow.get("chapter"),
                    "importance": foreshadow.get("attributes", {}).get("重要程度", "普通"),
                    "description": foreshadow.get("description", "")
                })

        return pending

    def _get_active_rules(self, chapter_num: int = None) -> List[Dict[str, Any]]:
        """获取规则约束"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        rules = []

        for rule in extended_entities["world_rules"]:
            rules.append({
                "name": rule.get("text", ""),
                "type": rule.get("attributes", {}).get("规则类型", ""),
                "description": rule.get("description", "")
            })

        return rules

    def _get_time_context(self, chapter_num: int = None) -> Dict[str, Any]:
        """获取时间上下文"""
        extended_entities = self.get_extended_state_entities(
            chapter_num=chapter_num)

        context = {
            "current_time": None,
            "time_nodes": [],
            "time_elapsed": []
        }

        for node in extended_entities["time_nodes"]:
            context["time_nodes"].append({
                "name": node.get("text", ""),
                "type": node.get("attributes", {}).get("时间类型", "")
            })

        for flow in extended_entities["time_flows"]:
            context["time_elapsed"].append({
                "description": flow.get("text", ""),
                "chapter": flow.get("chapter")
            })

        return context

    def _generate_consistency_warnings(self, report: Dict[str, Any]) -> List[str]:
        """生成一致性警告"""
        warnings = []

        # 检查未完成事件
        if report["unfinished_events"]:
            for event in report["unfinished_events"]:
                warnings.append(
                    f"未完成事件: {event['name']} - 当前状态: {event['status']}")

        # 检查待回收伏笔
        if report["pending_foreshadows"]:
            for foreshadow in report["pending_foreshadows"]:
                importance = foreshadow.get("importance", "普通")
                if importance == "重要":
                    warnings.append(
                        f"重要伏笔待回收: {foreshadow['name']} (埋设于第{foreshadow.get('planted_chapter', '?')}章)")

        # 检查设施状态
        for name, state in report["facility_states"].items():
            if state.get("status") in ["关闭", "暂停营业", "损坏"]:
                warnings.append(f"设施状态异常: {name} - {state.get('status')}")

        return warnings

    def format_consistency_report_for_prompt(self, chapter_num: int = None) -> str:
        """
        格式化一致性报告为提示词格式

        将一致性报告格式化为可读的文本，供写作Agent使用。

        Args:
            chapter_num: 章节号（可选）

        Returns:
            格式化的一致性报告文本
        """
        report = self.get_consistency_report(chapter_num)

        lines = ["# 一致性追踪报告", ""]

        # 人物状态
        if report["character_states"]:
            lines.append("## 人物状态")
            for char_name, state in report["character_states"].items():
                lines.append(f"### {char_name}")
                if state.get("latest_identity"):
                    lines.append(f"- 当前身份: {state['latest_identity']}")
                if state.get("latest_location"):
                    lines.append(f"- 当前位置: {state['latest_location']}")
                if state.get("abilities"):
                    lines.append(f"- 能力: {', '.join(state['abilities'][-3:])}")
                if state.get("mental_state"):
                    lines.append(f"- 心理状态: {state['mental_state']}")
            lines.append("")

        # 设施状态
        if report["facility_states"]:
            lines.append("## 设施状态")
            for name, state in report["facility_states"].items():
                status_info = f"{name}: {state.get('status', '未知')}"
                if state.get('manager'):
                    status_info += f" (负责人: {state['manager']})"
                lines.append(f"- {status_info}")
            lines.append("")

        # 未完成事件
        if report["unfinished_events"]:
            lines.append("## 未完成事件")
            for event in report["unfinished_events"]:
                lines.append(f"- {event['name']}: {event['status']}")
                if event.get('involved_characters'):
                    lines.append(
                        f"  涉及人物: {', '.join(event['involved_characters'])}")
            lines.append("")

        # 群体动态
        if report["group_states"]:
            lines.append("## 群体动态")
            for name, state in report["group_states"].items():
                lines.append(f"- {name}: {state.get('status', '活跃')}")
                if state.get('leader'):
                    lines.append(f"  领导者: {state['leader']}")
                if state.get('scale'):
                    lines.append(f"  规模: {state['scale']}")
            lines.append("")

        # 道具归属
        if report["item_ownership"]:
            lines.append("## 道具归属")
            for name, state in report["item_ownership"].items():
                lines.append(
                    f"- {name}: 持有者={state.get('owner', '未知')}, 状态={state.get('status', '完好')}")
            lines.append("")
        # 待回收伏笔
        if report["pending_foreshadows"]:
            lines.append("## 待回收伏笔")
            for foreshadow in report["pending_foreshadows"]:
                importance = foreshadow.get("importance", "普通")
                lines.append(
                    f"- [{importance}] {foreshadow['name']} (第{foreshadow.get('planted_chapter', '?')}章)")
            lines.append("")

        # 一致性警告
        if report["consistency_warnings"]:
            lines.append("## ⚠️ 一致性警告")
            for warning in report["consistency_warnings"]:
                lines.append(f"- {warning}")
            lines.append("")

        return "\n".join(lines)


# ============================================================================
# 正文板块专属实体提取器
# ============================================================================

class NovelEntityExtractor:
    """
    正文板块专属实体提取器
    完全独立于公共知识库的LLMEntityExtractor类
    """

    def __init__(self, llm_provider):
        """
        初始化提取器

        Args:
            llm_provider: LLM提供者
        """
        self.llm_provider = llm_provider
        self.logger = get_logger("novel_entity_extractor")

        # 使用正文板块专属配置
        self.chunk_size = NOVEL_CHUNK_SIZE
        self.max_entities_per_chunk = NOVEL_MAX_ENTITIES_PER_CHUNK
        self.max_relations_per_chunk = NOVEL_MAX_RELATIONS_PER_CHUNK

    async def extract_with_llm(self, text: str, max_retries: int = 2) -> Dict[str, Any]:
        """
        使用LLM提取实体和关系

        Args:
            text: 输入文本
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...]}
        """
        # 检查文本长度，决定是否分块
        if len(text) > self.chunk_size:
            return await self._extract_from_long_text(text)

        return await self._extract_single_chunk(text, max_retries)

    async def _extract_from_long_text(self, text: str) -> Dict[str, Any]:
        """
        处理长文本，分段提取后合并
        """
        all_entities = []
        all_relations = []
        success_count = 0
        fail_count = 0

        # 智能分块
        chunks = self._smart_split_text(text)
        total_chunks = len(chunks)

        self.logger.info(
            f"正文板块长文本分块: 总长度={len(text)}, chunk大小={self.chunk_size}, 分成{total_chunks}块")

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            self.logger.debug(f"处理第 {i+1}/{total_chunks} 块, 长度={len(chunk)}")
            result = await self._extract_single_chunk(chunk)

            if result.get("entities") or result.get("relations"):
                all_entities.extend(result.get("entities", []))
                all_relations.extend(result.get("relations", []))
                success_count += 1
            else:
                fail_count += 1

        # 去重
        unique_entities = self._deduplicate_entities(all_entities)
        unique_relations = self._deduplicate_relations(all_relations)

        self.logger.info(
            f"正文板块长文本处理完成: {total_chunks}个chunk, 成功{success_count}个, 失败{fail_count}个")

        return {
            "entities": unique_entities,
            "relations": unique_relations
        }

    def _smart_split_text(self, text: str) -> List[str]:
        """
        智能分块：优先按段落分割，如果段落过长则按句子分割
        """
        chunks = []

        # 1. 首先尝试按双换行符分割（段落）
        paragraphs = text.split('\n\n')

        # 如果只有一个段落（没有双换行符），尝试单换行符
        if len(paragraphs) == 1:
            paragraphs = text.split('\n')
            self.logger.debug(f"使用单换行符分割，得到 {len(paragraphs)} 个段落")
        else:
            self.logger.debug(f"使用双换行符分割，得到 {len(paragraphs)} 个段落")

        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前段落加上新段落不超过限制，合并
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n" + para
                else:
                    current_chunk = para
            else:
                # 当前块已满，保存并开始新块
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果单个段落超过限制，需要进一步分割
                if len(para) > self.chunk_size:
                    sub_chunks = self._split_long_paragraph(para)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = para

        # 保存最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        # 如果仍然没有分块（极端情况），强制按字符数分割
        if not chunks:
            for i in range(0, len(text), self.chunk_size):
                chunks.append(text[i:i+self.chunk_size])

        return chunks

    def _split_long_paragraph(self, para: str) -> List[str]:
        """分割过长的段落（按句子分割）"""
        chunks = []

        # 按中文句号、问号、感叹号分割句子
        sentences = re.split(r'([。！？!?\.]+)', para)

        # 重新组合句子和标点
        combined_sentences = []
        for i in range(0, len(sentences)-1, 2):
            if i+1 < len(sentences):
                combined_sentences.append(sentences[i] + sentences[i+1])
            else:
                combined_sentences.append(sentences[i])
        if len(sentences) % 2 == 1 and sentences[-1]:
            combined_sentences.append(sentences[-1])

        current_chunk = ""

        for sentence in combined_sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # 如果单个句子超过限制，强制截断
                if len(sentence) > self.chunk_size:
                    for i in range(0, len(sentence), self.chunk_size):
                        chunks.append(sentence[i:i+self.chunk_size])
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def _extract_single_chunk(self, text: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        提取单个文本块的实体和关系

        增强的重试机制：
        - 针对429错误（服务器过载）使用指数退避
        - 区分不同类型的错误
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                # 使用正文板块专用提示词
                prompt = NOVEL_EXTRACTION_PROMPT.format(
                    max_entities=self.max_entities_per_chunk,
                    max_relations=self.max_relations_per_chunk,
                    content=text
                )

                # 获取模型支持的最大输出token
                max_output_tokens = self.llm_provider.get_max_output_tokens()

                response = await self.llm_provider.generate(
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=max_output_tokens
                )

                # 调试日志
                self.logger.debug(
                    f"LLM响应长度: {len(response.content) if response and hasattr(response, 'content') and response.content else 0}")

                if not response or not hasattr(response, 'content') or response.content is None:
                    self.logger.warning(
                        f"LLM返回无效响应，尝试 {attempt+1}/{max_retries}")
                    continue

                # 解析响应
                result = self._parse_llm_response(response.content)
                if result:
                    return result

                self.logger.warning(f"JSON解析失败，尝试 {attempt+1}/{max_retries}")

            except Exception as e:
                error_str = str(e)
                last_error = e

                # 检测429错误（服务器过载/限流）
                is_rate_limit = '429' in error_str or 'rate' in error_str.lower(
                ) or 'overload' in error_str.lower()

                if is_rate_limit:
                    # 指数退避：10秒 -> 20秒 -> 40秒
                    wait_time = 10 * (2 ** attempt)
                    self.logger.warning(
                        f"API限流/服务器过载(429)，等待 {wait_time}秒 后重试... (尝试 {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                else:
                    # 其他错误：较短等待
                    self.logger.warning(f"LLM实体提取异常: {error_str[:200]}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)

        self.logger.error(
            f"所有重试失败，返回空结果。最后错误: {str(last_error)[:200] if last_error else 'None'}")
        return {"entities": [], "relations": []}

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析LLM响应为JSON

        使用多层解析策略处理LLM返回的各种异常格式：
        1. 先尝试内置RobustJSONParser
        2. 如果失败，尝试json_repair库（终极回退）
        3. 最后尝试修复实体键名问题
        """
        if not response:
            return None

        def validate_result_internal(result):
            """验证结果是否为有效字典"""
            if not isinstance(result, dict):
                return False
            if "entities" not in result:
                return False
            if not isinstance(result["entities"], list):
                return False
            for entity in result["entities"]:
                if not isinstance(entity, dict):
                    self.logger.warning(
                        f"实体类型错误: {type(entity).__name__}, 值: {str(entity)[:50]}")
                    return False
            if "relations" in result:
                if not isinstance(result["relations"], list):
                    return False
                for relation in result["relations"]:
                    if not isinstance(relation, dict):
                        self.logger.warning(
                            f"关系类型错误: {type(relation).__name__}, 值: {str(relation)[:50]}")
                        return False
            return True

        # 策略1: 使用健壮JSON解析器
        result, logs = RobustJSONParser.parse(
            response, default=None, repair_truncated=True)

        # 记录解析日志
        if logs:
            self.logger.debug(f"JSON解析日志: {'; '.join(logs)}")

        # 关键修复：解析成功后，立即修复键名问题！
        if result and isinstance(result, dict):
            result = self._fix_entity_keys(result)

        # 验证解析结果
        if result and validate_result_internal(result):
            self.logger.info(
                f"JSON解析成功，实体数={len(result.get('entities', []))}, 关系数={len(result.get('relations', []))}")
            return result

        # 策略2: 使用json_repair库（终极回退）
        if HAS_JSON_REPAIR:
            try:
                self.logger.info("尝试使用json_repair库修复JSON...")
                # json_repair可以处理各种异常格式
                result = json_repair.loads(response, skip_json_loads=True)
                if result and isinstance(result, dict):
                    # 修复键名问题
                    result = self._fix_entity_keys(result)
                    if validate_result_internal(result):
                        self.logger.info("json_repair修复成功！")
                        return result
            except Exception as e:
                self.logger.warning(f"json_repair修复失败: {e}")

        # 策略3: 如果RobustJSONParser解析成功但验证失败，尝试修复实体键名问题
        if result and isinstance(result, dict) and "entities" in result:
            self.logger.info("JSON解析成功但验证失败，尝试修复实体格式...")
            fixed_result = self._fix_entity_keys(result)
            if validate_result_internal(fixed_result):
                self.logger.info("修复实体格式成功")
                return fixed_result

        self.logger.warning(f"无法解析LLM响应为有效JSON，响应长度: {len(response)}")
        self.logger.debug(f"响应内容预览: {response[:500]}")
        return None

    def _fix_entity_keys(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """修复实体中的键名问题

        处理解析后实体字典中可能存在的异常键名，如包含换行符、引号等。
        常见的异常格式：
        - '\n  "text"' - 换行符+空格+引号包裹的键名
        - '"text"' - 被引号包裹的键名
        - ' text ' - 包含空格的键名

        Args:
            result: 原始解析结果

        Returns:
            修复后的结果
        """
        if not result or not isinstance(result, dict):
            return result

        self.logger.info(
            f"[DEBUG] _fix_entity_keys 开始处理, 实体数={len(result.get('entities', []))}")

        fixed_entities = []
        fixed_count = 0

        for entity in result.get("entities", []):
            if not isinstance(entity, dict):
                continue

            # 修复键名
            fixed_entity = {}
            for key, value in entity.items():
                if not isinstance(key, str):
                    continue

                original_key = key
                # 第一步：移除所有换行符和回车符
                cleaned_key = key.replace('\n', '').replace('\r', '')
                # 第二步：去除首尾空格
                cleaned_key = cleaned_key.strip()
                # 第三步：移除可能存在的外层引号（如 '"text"' -> 'text'）
                if cleaned_key.startswith('"') and cleaned_key.endswith('"'):
                    cleaned_key = cleaned_key[1:-1]
                elif cleaned_key.startswith("'") and cleaned_key.endswith("'"):
                    cleaned_key = cleaned_key[1:-1]
                # 第四步：再次去除空格（引号内可能有空格）
                cleaned_key = cleaned_key.strip()
                # 第五步：尝试映射到标准键名
                cleaned_key = self._normalize_key_name(cleaned_key)

                # 记录修复日志
                if cleaned_key != original_key:
                    fixed_count += 1
                    self.logger.debug(
                        f"键名修复: {original_key!r} -> {cleaned_key!r}")

                # 清理值
                if isinstance(value, str):
                    cleaned_value = value.lstrip('\n\r ').rstrip()
                else:
                    cleaned_value = value

                if cleaned_key:  # 确保键名不为空
                    fixed_entity[cleaned_key] = cleaned_value

            if fixed_entity:
                fixed_entities.append(fixed_entity)

        if fixed_count > 0:
            self.logger.info(f"实体键名修复完成: 共修复 {fixed_count} 个异常键名")

        result["entities"] = fixed_entities

        # 同样修复 relations 中的键名
        fixed_relations = []
        relation_fix_count = 0
        for relation in result.get("relations", []):
            if not isinstance(relation, dict):
                continue

            fixed_relation = {}
            for key, value in relation.items():
                if not isinstance(key, str):
                    continue

                original_key = key
                cleaned_key = key.replace('\n', '').replace(
                    '\r', '').strip().strip('"').strip("'").strip()
                cleaned_key = self._normalize_key_name(cleaned_key)

                if cleaned_key != original_key:
                    relation_fix_count += 1
                    self.logger.debug(
                        f"关系键名修复: {original_key!r} -> {cleaned_key!r}")

                if isinstance(value, str):
                    cleaned_value = value.lstrip('\n\r ').rstrip()
                else:
                    cleaned_value = value

                if cleaned_key:
                    fixed_relation[cleaned_key] = cleaned_value

            if fixed_relation:
                fixed_relations.append(fixed_relation)

        if relation_fix_count > 0:
            self.logger.info(f"关系键名修复完成: 共修复 {relation_fix_count} 个异常键名")

        result["relations"] = fixed_relations

        return result

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """验证解析结果"""
        if not isinstance(result, dict):
            return False
        if "entities" not in result:
            return False
        if not isinstance(result["entities"], list):
            return False
        # 检查每个实体是否为字典类型
        for entity in result["entities"]:
            if not isinstance(entity, dict):
                self.logger.warning(
                    f"实体类型错误: {type(entity).__name__}, 值: {str(entity)[:50]}")
                return False
        # 检查relations如果存在
        if "relations" in result:
            if not isinstance(result["relations"], list):
                return False
            for relation in result["relations"]:
                if not isinstance(relation, dict):
                    self.logger.warning(
                        f"关系类型错误: {type(relation).__name__}, 值: {str(relation)[:50]}")
                    return False
        return True

    def _try_fix_truncated_json(self, response: str) -> Optional[str]:
        """
        尝试修复被截断的JSON

        改进版本：在返回前验证构建的JSON是否有效，且entities中的元素必须是字典
        """
        def validate_parsed_result(parsed):
            """验证解析结果是否有效"""
            if not isinstance(parsed, dict):
                return False
            if "entities" not in parsed:
                return False
            if not isinstance(parsed["entities"], list):
                return False
            # 关键检查：确保每个entity都是字典类型
            for entity in parsed["entities"]:
                if not isinstance(entity, dict):
                    return False
            return True

        # 找到entities和relations数组
        entities_start = response.find('"entities"')
        relations_start = response.find('"relations"')

        if entities_start == -1:
            return None

        # 提取entities数组
        entities_array_start = response.find('[', entities_start)
        if entities_array_start == -1:
            return None

        entities_result = self._extract_complete_array(
            response, entities_array_start)

        if relations_start != -1:
            relations_array_start = response.find('[', relations_start)
            if relations_array_start != -1:
                relations_result = self._extract_complete_array(
                    response, relations_array_start)
                fixed_json = '{"entities": ' + entities_result + \
                    ', "relations": ' + relations_result + '}'
                # 验证JSON是否有效
                try:
                    parsed = json.loads(fixed_json)
                    if validate_parsed_result(parsed):
                        return fixed_json
                except json.JSONDecodeError:
                    pass  # 继续尝试其他方案

        fixed_json = '{"entities": ' + entities_result + ', "relations": []}'
        # 验证JSON是否有效
        try:
            parsed = json.loads(fixed_json)
            if validate_parsed_result(parsed):
                return fixed_json
        except json.JSONDecodeError:
            return None

        return None

    def _extract_complete_array(self, json_str: str, array_start: int) -> str:
        """从JSON字符串中提取完整的数组内容

        改进版本：确保只返回包含完整有效元素的数组
        """
        depth = 0
        in_string = False
        escape_next = False
        last_complete_pos = array_start
        complete_elements = []  # 记录完整元素的结束位置
        element_start = None

        for i, char in enumerate(json_str[array_start:], start=array_start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\' and in_string:
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == '[':
                    if depth == 0:
                        element_start = None  # 重置元素开始位置
                    depth += 1
                elif char == ']':
                    depth -= 1
                    if depth == 0:
                        return json_str[array_start:i+1]
                elif char == '{':
                    if depth == 1 and element_start is None:
                        element_start = i  # 记录对象开始位置
                elif char == '}':
                    if depth == 1:
                        last_complete_pos = i
                        if element_start is not None:
                            complete_elements.append((element_start, i))
                            element_start = None

        # 数组不完整，截断到最后一个完整元素
        if complete_elements:
            # 使用最后一个完整元素的位置
            last_elem_start, last_elem_end = complete_elements[-1]
            truncated = json_str[array_start:last_elem_end+1]
            truncated = truncated.rstrip().rstrip(',')
            return truncated + ']'

        # 没有完整元素，返回空数组
        return '[]'

    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """实体去重"""
        seen = set()
        result = []
        for e in entities:
            key = (e.get("text", ""), e.get("type", ""))
            if key not in seen:
                seen.add(key)
                result.append(e)
        return result

    def _deduplicate_relations(self, relations: List[Dict]) -> List[Dict]:
        """关系去重"""
        seen = set()
        result = []
        for r in relations:
            key = (r.get("source", ""), r.get(
                "target", ""), r.get("relation", ""))
            if key not in seen:
                seen.add(key)
                result.append(r)
        return result

    async def extract_character_states(
        self,
        chapter_content: str,
        chapter_num: int,
        known_characters: List[str] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        提取章节中的人物状态变化实体

        专门用于提取人物状态追踪相关的实体，支持写作工作台的人物状态追踪功能。

        使用专用的人物状态提取配置（更宽松的限制以捕获更多细节）

        Args:
            chapter_content: 章节内容
            chapter_num: 章节号
            known_characters: 已知人物列表（可选，帮助识别人物）
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...], "chapter": chapter_num}
        """
        last_error = None

        # === NEW_CODE_MARKER_2026_0404 === 唯一标识：确认代码加载
        self.logger.warning(
            "NEW_CODE_MARKER_2026_0404: extract_character_states 已加载最新代码")

        # 使用人物状态专用的宽松限制
        max_entities = CHARACTER_STATE_MAX_ENTITIES   # 20个实体（比默认的10个更宽松）
        max_relations = CHARACTER_STATE_MAX_RELATIONS  # 25个关系（比默认的15个更宽松）

        for attempt in range(max_retries):
            try:
                # 构建提示词，包含已知人物信息
                character_info = ""
                if known_characters:
                    character_info = f"\n**已知人物：** {', '.join(known_characters[:10])}"
                    if len(known_characters) > 10:
                        character_info += f" 等{len(known_characters)}个人物"

                prompt = CHARACTER_STATE_EXTRACTION_PROMPT.format(
                    max_entities=max_entities,
                    max_relations=max_relations,
                    chapter_num=chapter_num,
                    content=f"{character_info}\n\n{chapter_content}"
                )

                # 获取模型支持的最大输出token
                max_output_tokens = self.llm_provider.get_max_output_tokens()

                response = await self.llm_provider.generate(
                    prompt=prompt,
                    temperature=0.1,  # 低温度确保输出稳定
                    max_tokens=max_output_tokens
                )

                if not response or not hasattr(response, 'content') or response.content is None:
                    self.logger.warning(
                        f"人物状态提取返回无效响应，尝试 {attempt+1}/{max_retries}")
                    continue

                # 确保response.content是字符串类型
                response_content = response.content
                if not isinstance(response_content, str):
                    self.logger.warning(
                        f"响应内容类型异常: {type(response_content).__name__}, 尝试转换")
                    try:
                        response_content = str(response_content)
                    except Exception as conv_error:
                        self.logger.error(f"响应内容转换失败: {conv_error}")
                        continue

                # 解析响应
                self.logger.info(
                    f"[DEBUG] 开始解析LLM响应, 长度={len(response_content)}")
                result = self._parse_llm_response(response_content)
                self.logger.info(
                    f"[DEBUG] _parse_llm_response 返回: {type(result).__name__ if result else 'None'}")
                if result:
                    self.logger.info(f"[DEBUG] 结果包含键: {list(result.keys())}")
                    entities = result.get('entities', [])
                    self.logger.info(f"[DEBUG] 实体数量: {len(entities)}")
                    if entities:
                        self.logger.info(
                            f"[DEBUG] 第一个实体的键: {list(entities[0].keys()) if isinstance(entities[0], dict) else type(entities[0]).__name__}")
                    # 为实体添加章节号，确保类型安全
                    for entity in result.get("entities", []):
                        # 安全检查：确保entity是字典类型
                        if not isinstance(entity, dict):
                            self.logger.warning(
                                f"跳过非字典类型的实体: {type(entity).__name__}")
                            continue
                        if "chapter" not in entity:
                            entity["chapter"] = chapter_num

                    # 质量验证
                    validated_result = self._validate_character_state_result(
                        result, chapter_num, known_characters
                    )

                    self.logger.info(
                        f"人物状态提取成功: 章节{chapter_num}, "
                        f"实体数={len(validated_result.get('entities', []))}, "
                        f"关系数={len(validated_result.get('relations', []))}")

                    validated_result["chapter"] = chapter_num
                    return validated_result

                self.logger.warning(f"JSON解析失败，尝试 {attempt+1}/{max_retries}")

            except Exception as e:
                error_str = str(e)
                last_error = e

                # 检测429错误
                is_rate_limit = '429' in error_str or 'rate' in error_str.lower()

                # 记录更详细的错误信息，包括异常类型和堆栈
                import traceback
                self.logger.warning(
                    f"人物状态提取异常: {type(e).__name__}: {error_str[:200]}")
                self.logger.warning(f"异常堆栈:\n{traceback.format_exc()}")

                if is_rate_limit:
                    wait_time = 10 * (2 ** attempt)
                    self.logger.warning(
                        f"API限流，等待 {wait_time}秒 后重试...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                else:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)

        self.logger.error(
            f"人物状态提取失败: 章节{chapter_num}. 最后错误: {str(last_error)[:200] if last_error else 'None'}")

        # 不再使用规则提取回退方案，只使用LLM提取
        # 返回空结果，让系统知道提取失败
        self.logger.warning(f"LLM人物状态提取失败，不启用规则回退: 章节{chapter_num}")
        return {
            "entities": [],
            "relations": [],
            "chapter": chapter_num,
            "summary": "",
            "_extraction_failed": True,
            "_error": str(last_error)[:200] if last_error else "Unknown error"
        }

    def _rule_based_character_extraction(
        self,
        content: str,
        chapter_num: int,
        known_characters: List[str] = None
    ) -> Dict[str, Any]:
        """
        基于规则的人物状态提取（回退方案）

        当LLM不可用或提取失败时，使用简单的规则匹配来提取基本的人物状态信息。
        虽然精度不如LLM，但能确保系统不会完全丢失人物状态信息。

        Args:
            content: 章节内容
            chapter_num: 章节号
            known_characters: 已知人物列表

        Returns:
            基本的人物状态提取结果
        """
        import re

        entities = []
        relations = []

        # 定义关键词模式
        patterns = {
            "身份变化": [
                r'([\u4e00-\u9fa5]{2,4})(?:被任命为|晋升为|封为|成为|担任)([\u4e00-\u9fa5]{2,6})',
                r'(?:任命|晋升|封|册封)([\u4e00-\u9fa5]{2,4})为([\u4e00-\u9fa5]{2,6})',
                r'([\u4e00-\u9fa5]{2,4})(?:不再是|卸任|辞去|失去)(?:了)?([\u4e00-\u9fa5]{2,6})'
            ],
            "位置变化": [
                r'([\u4e00-\u9fa5]{2,4})(?:前往|来到|到达|离开|返回|逃往|追至)([\u4e00-\u9fa5]{2,8})',
                r'(?:从)([\u4e00-\u9fa5]{2,8})(?:前往|赶往|逃到|转移到)([\u4e00-\u9fa5]{2,8})'
            ],
            "关系变化": [
                r'([\u4e00-\u9fa5]{2,4})与([\u4e00-\u9fa5]{2,4})(?:结盟|联盟|联手|合作|结拜)',
                r'([\u4e00-\u9fa5]{2,4})与([\u4e00-\u9fa5]{2,4})(?:决裂|反目|断交|翻脸)',
                r'([\u4e00-\u9fa5]{2,4})(?:背叛|出卖|背弃)(?:了)?([\u4e00-\u9fa5]{2,4})',
                r'([\u4e00-\u9fa5]{2,4})与([\u4e00-\u9fa5]{2,4})(?:和解|和好|重归于好)'
            ],
            "能力成长": [
                r'([\u4e00-\u9fa5]{2,4})(?:学会|掌握|领悟|修成|突破)(?:了)?([\u4e00-\u9fa5]{2,10})',
                r'([\u4e00-\u9fa5]{2,4})的(?:武功|实力|能力|修为)(?:大增|精进|提升|突破)'
            ],
            "心理状态": [
                r'([\u4e00-\u9fa5]{2,4})(?:感到|觉得|心中|内心)(?:绝望|恐惧|狂喜|愤怒|悲伤|释然|迷茫|坚定)',
                r'([\u4e00-\u9fa5]{2,4})(?:陷入|陷入于)(?:绝望|痛苦|沉思|疯狂)'
            ]
        }

        # 提取实体
        for entity_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, tuple) and len(match) >= 2:
                        char_name = match[0]
                        detail = match[1] if len(match) > 1 else ""

                        # 验证人物名是否合理（如果提供了已知人物列表）
                        if known_characters and char_name not in known_characters:
                            # 检查是否是已知人物的子串或相似名称
                            is_known = any(char_name in kc or kc in char_name
                                           for kc in known_characters[:20])
                            if not is_known and len(match[0]) < 2:
                                continue

                        entity = {
                            "text": f"{entity_type}: {''.join(match)}",
                            "type": entity_type,
                            "character": char_name,
                            "chapter": chapter_num,
                            "description": f"在章节中{entity_type}：{''.join(match)}"
                        }

                        # 避免重复
                        existing_texts = [e.get("text", "") for e in entities]
                        if entity.get("text", "") not in existing_texts:
                            entities.append(entity)

                            # 如果是二元关系类型，自动创建关系
                            if entity_type in ["关系变化"] and len(match) >= 2:
                                relation_type = self._infer_relation_type(
                                    content, match[0], match[1])
                                relations.append({
                                    "source": match[0],
                                    "target": match[1],
                                    "relation": relation_type,
                                    "context": f"在第{chapter_num}章中发生{entity_type}"
                                })

        # 限制数量
        max_entities = min(len(entities), CHARACTER_STATE_MAX_ENTITIES // 2)
        max_relations = min(len(relations), CHARACTER_STATE_MAX_RELATIONS // 2)

        self.logger.debug(
            f"规则提取完成: 章节{chapter_num}, "
            f"找到{len(entities)}个候选实体, 保留{max_entities}个"
        )

        return {
            "entities": entities[:max_entities],
            "relations": relations[:max_relations],
            "chapter": chapter_num,
            "summary": f"基于规则提取的基本人物状态信息（共{len(entities[:max_entities])}个变化）",
            "_extraction_method": "rule_based_fallback"
        }

    def _infer_relation_type(
        self,
        content: str,
        char1: str,
        char2: str
    ) -> str:
        """
        根据上下文推断两个人物之间的关系类型

        Args:
            content: 章节内容
            char1: 人物1
            char2: 人物2

        Returns:
            关系类型字符串
        """
        import re

        context_pattern = f'{char1}.*?{char2}|{char2}.*?{char1}'
        context_match = re.search(context_pattern, content, re.DOTALL)

        if not context_match:
            return "关联"

        context_text = context_match.group()

        # 根据关键词推断关系类型
        positive_keywords = ['盟', '友', '信任', '支持', '合作', '帮助', '爱']
        negative_keywords = ['敌', '仇', '恨', '杀', '攻击', '背叛', '敌对']

        positive_count = sum(
            1 for kw in positive_keywords if kw in context_text)
        negative_count = sum(
            1 for kw in negative_keywords if kw in context_text)

        if positive_count > negative_count:
            return "关系改善"
        elif negative_count > positive_count:
            return "关系恶化"
        else:
            return "关联"

    _KEY_NAME_FUZZY_MAP = {
        "text": ["text", "文本", "内容", "名称", "name", "标题", "title"],
        "type": ["type", "类型", "类别", "category", "种类"],
        "character": ["character", "人物", "角色", "角色名", "char", "人物名"],
        "description": ["description", "描述", "说明", "详情", "detail", "desc"],
        "chapter": ["chapter", "章节", "章号", "chapter_num"],
        "before_state": ["before_state", "之前状态", "原状态", "旧状态", "before"],
        "after_state": ["after_state", "之后状态", "新状态", "现状态", "after"],
        "trigger_event": ["trigger_event", "触发事件", "起因", "cause", "trigger"],
        "source": ["source", "源", "来源", "起始实体"],
        "target": ["target", "目标", "终点", "目的实体"],
        "relation": ["relation", "关系", "关联", "relationship", "rel"],
    }

    def _normalize_key_name(self, raw_key: str) -> str:
        """将非标准键名映射到标准键名

        处理LLM返回的中英文键名变体，统一为标准英文键名。
        支持处理：换行符、空格、嵌入引号、中英文变体。

        Args:
            raw_key: 原始键名

        Returns:
            标准化后的键名
        """
        normalized = raw_key.strip().replace(
            '\n', '').replace('\r', '').strip('"').lower()
        for standard_key, variants in self._KEY_NAME_FUZZY_MAP.items():
            if normalized in [v.lower() for v in variants] or normalized == standard_key:
                return standard_key
        return raw_key.strip().replace('\n', '').replace('\r', '').strip('"')

    def _validate_character_state_result(
        self,
        result: Dict[str, Any],
        chapter_num: int,
        known_characters: List[str] = None
    ) -> Dict[str, Any]:
        """
        验证人物状态提取结果的质量

        检查并修复提取结果中的常见问题：
        1. 缺少必要字段
        2. 实体类型不正确
        3. 人物名称为空
        4. 描述过于简短
        5. 重复实体

        Args:
            result: LLM提取的原始结果
            chapter_num: 章节号
            known_characters: 已知人物列表

        Returns:
            验证和清理后的结果
        """
        validated_entities = []
        validated_relations = []
        issues_found = []

        # 定义合法的实体类型
        valid_entity_types = {
            "身份变化", "位置变化", "关系变化", "性格发展",
            "能力成长", "心理状态", "行为模式"
        }

        # 验证实体
        for entity in result.get("entities", []):
            # 检查0：实体必须是字典类型
            if not isinstance(entity, dict):
                issues_found.append(f"跳过非字典类型的实体: {type(entity).__name__}")
                self.logger.warning(
                    f"实体类型错误，跳过: {type(entity).__name__}, 值: {str(entity)[:50]}")
                continue

            try:
                # 检查并清理实体的键名异常问题（如换行符、空格）
                cleaned_entity = {}
                has_fatal_error = False
                for key in list(entity.keys()):
                    if not isinstance(key, str):
                        self.logger.warning(
                            f"实体包含非字符串类型的键: {key!r} (类型: {type(key).__name__})")
                        has_fatal_error = True
                        break

                    # 清理键名中的换行符和外层空格
                    cleaned_key = self._normalize_key_name(key)
                    if cleaned_key != key.strip():
                        self.logger.debug(
                            f"规范化实体键名: {key!r} -> {cleaned_key!r}")
                        issues_found.append(
                            f"规范化键名: '{str(key)[:20]}' -> '{cleaned_key[:20]}'")

                    if not cleaned_key:
                        self.logger.warning(f"清理后键名为空，跳过该键")
                        continue

                    # 清理字符串类型的值中的前导换行符
                    value = entity.get(key)  # 使用get方法避免KeyError
                    if value is None:
                        self.logger.debug(f"键 {key!r} 的值为None，跳过")
                        continue
                    if isinstance(value, str):
                        cleaned_value = value.lstrip('\n\r ').rstrip()
                        if cleaned_value != value:
                            self.logger.debug(
                                f"清理实体值: 键={cleaned_key}, 原值前10字符={value[:10]!r}")
                        cleaned_entity[cleaned_key] = cleaned_value
                    else:
                        cleaned_entity[cleaned_key] = value

                if has_fatal_error:
                    issues_found.append(f"跳过键名异常的实体")
                    continue

            except KeyError as e:
                # 捕获键访问错误，记录详细信息后跳过该实体
                self.logger.error(f"实体键访问错误: {e!r}, 实体内容: {str(entity)[:200]}")
                issues_found.append(f"跳过键访问错误的实体: {e!r}")
                continue
            except Exception as e:
                self.logger.error(f"实体处理异常: {type(e).__name__}: {e!r}")
                issues_found.append(f"跳过处理异常的实体")
                continue

            # 使用清理后的实体
            entity = cleaned_entity

            # 检查1：必须有character字段
            if not entity.get("character"):
                # 尝试从text或description中提取人物名
                char_name = self._extract_character_from_text(
                    entity.get("text", ""),
                    known_characters
                )
                if char_name:
                    entity["character"] = char_name
                    issues_found.append(f"自动补充人物名: {char_name}")
                else:
                    issues_found.append(
                        f"跳过无人物名的实体: {entity.get('text', '')[:30]}")
                    continue

            # 检查2：类型必须合法
            entity_type = entity.get("type", "")
            if entity_type not in valid_entity_types:
                # 尝试映射到最接近的类型
                mapped_type = self._map_entity_type(entity_type)
                if mapped_type:
                    entity["type"] = mapped_type
                    issues_found.append(
                        f"修正实体类型: {entity_type} → {mapped_type}")
                else:
                    issues_found.append(f"跳过非法类型实体: {entity_type}")
                    continue

            # 检查3：描述不能太简短
            description = entity.get("description", "")
            if len(description) < 10:
                # 使用text作为description的补充
                entity["description"] = f"{entity.get('text', '')}。{description}"
                issues_found.append(f"补充描述: 实体'{entity.get('text', '')[:20]}'")

            # 检查4：必须有text字段
            if not entity.get("text"):
                entity["text"] = f"{entity.get('type', '未知变化')} - {entity.get('character', '未知人物')}"
                issues_found.append(f"补充text字段")

            validated_entities.append(entity)

        # 验证关系
        for relation in result.get("relations", []):
            # 检查0：关系必须是字典类型
            if not isinstance(relation, dict):
                issues_found.append(f"跳过非字典类型的关系: {type(relation).__name__}")
                self.logger.warning(
                    f"关系类型错误，跳过: {type(relation).__name__}, 值: {str(relation)[:50]}")
                continue

            try:
                # 清理关系字典的键名和值
                cleaned_relation = {}
                has_fatal_error = False
                for key in list(relation.keys()):
                    if not isinstance(key, str):
                        has_fatal_error = True
                        break
                    cleaned_key = self._normalize_key_name(key)
                    if not cleaned_key:
                        continue
                    value = relation.get(key)  # 使用get方法避免KeyError
                    if value is None:
                        continue
                    if isinstance(value, str):
                        cleaned_relation[cleaned_key] = value.lstrip(
                            '\n\r ').rstrip()
                    else:
                        cleaned_relation[cleaned_key] = value

                if has_fatal_error:
                    issues_found.append(f"跳过键名异常的关系")
                    continue

                relation = cleaned_relation

                # 检查1：必须有source和target
                if not relation.get("source") or not relation.get("target"):
                    issues_found.append(f"跳过不完整的关系")
                    continue

                # 检查2：context不能太简短
                context = relation.get("context", "")
                if len(context) < 5:
                    relation["context"] = f"{relation.get('source', '')}与{relation.get('target', '')}之间存在{relation.get('relation', '关联')}"

                validated_relations.append(relation)

            except KeyError as e:
                self.logger.error(
                    f"关系键访问错误: {e!r}, 关系内容: {str(relation)[:200]}")
                issues_found.append(f"跳过键访问错误的关系: {e!r}")
                continue
            except Exception as e:
                self.logger.error(f"关系处理异常: {type(e).__name__}: {e!r}")
                issues_found.append(f"跳过处理异常的关系")
                continue

        # 记录验证结果
        if issues_found:
            self.logger.info(
                f"人物状态质量验证完成: 章节{chapter_num}, "
                f"发现{len(issues_found)}个问题, "
                f"有效实体={len(validated_entities)}, 有效关系={len(validated_relations)}"
            )
            for issue in issues_found[:5]:  # 只记录前5个问题
                self.logger.debug(f"  - {issue}")

        return {
            "entities": validated_entities,
            "relations": validated_relations,
            "summary": result.get("summary", ""),
            "_validation_issues": len(issues_found),
            "_original_count": {
                "entities": len(result.get("entities", [])),
                "relations": len(result.get("relations", []))
            }
        }

    def _extract_character_from_text(
        self,
        text: str,
        known_characters: List[str] = None
    ) -> Optional[str]:
        """
        从文本中提取人物名称

        Args:
            text: 包含人物信息的文本
            known_characters: 已知人物列表

        Returns:
            提取到的人物名称，如果无法提取则返回None
        """
        if not text:
            return None

        # 方法1：在已知人物列表中查找
        if known_characters:
            for char_name in known_characters:
                if char_name in text:
                    return char_name

        # 方法2：使用简单的启发式规则（查找常见的人物命名模式）
        import re
        patterns = [
            r'([^\s，。！？、；：""''（）【】]{2,4})(?:的|被|将|把|与|和|对|向|在)',
            r'(?:主角|人物|角色)([^\s，。！？、；：""''（）【】]{2,4})'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1)
                if len(name) >= 2 and len(name) <= 4:
                    return name

        return None

    def _map_entity_type(self, invalid_type: str) -> Optional[str]:
        """
        将非法或非标准的实体类型映射到标准类型

        Args:
            invalid_type: 非标准类型名称

        Returns:
            标准类型名称，如果无法映射则返回None
        """
        type_mapping = {
            # 身份变化的变体
            "身份": "身份变化", "职位": "身份变化", "地位": "身份变化",
            "官职": "身份变化", "称号": "身份变化", "角色": "身份变化",

            # 位置变化的变体
            "位置": "位置变化", "地点": "位置变化", "场景": "位置变化",
            "移动": "位置变化", "迁移": "位置变化", "转移": "位置变化",

            # 关系变化的变体
            "关系": "关系变化", "人际": "关系变化", "社交": "关系变化",
            "感情": "关系变化", "情感": "关系变化",

            # 性格发展的变体
            "性格": "性格发展", "个性": "性格发展", "特质": "性格发展",
            "价值观": "性格发展", "观念": "性格发展",

            # 能力成长的变体
            "能力": "能力成长", "技能": "能力成长", "武功": "能力成长",
            "实力": "能力成长", "知识": "能力成长", "水平": "能力成长",

            # 心理状态的变体
            "心理": "心理状态", "情绪": "心理状态", "心情": "心理状态",
            "精神": "心理状态", "心态": "心理状态",

            # 行为模式的变体
            "行为": "行为模式", "习惯": "行为模式", "方式": "行为模式",
            "策略": "行为模式", "决策": "行为模式"
        }

        # 精确匹配
        if invalid_type in type_mapping:
            return type_mapping[invalid_type]

        # 模糊匹配（包含关键词）
        for key, value in type_mapping.items():
            if key in invalid_type or invalid_type in key:
                return value

        return None

    async def extract_extended_states(
        self,
        chapter_content: str,
        chapter_num: int,
        context_info: Dict[str, Any] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        提取章节中的扩展状态实体（设施、事件、群体、道具、世界规则、时间线、伏笔）

        用于提取除人物状态外的一致性相关实体，支持更全面的一致性追踪。

        Args:
            chapter_content: 章节内容
            chapter_num: 章节号
            context_info: 上下文信息（可选，包含已知实体列表等）
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...], "consistency_notes": [...], "chapter": chapter_num}
        """
        last_error = None

        # 使用扩展状态提取的配置
        max_entities = CHARACTER_STATE_MAX_ENTITIES + 10   # 30个实体
        max_relations = CHARACTER_STATE_MAX_RELATIONS + 15  # 40个关系

        for attempt in range(max_retries):
            try:
                # 构建上下文提示
                context_prompt = ""
                if context_info:
                    # 已知设施
                    if context_info.get("known_facilities"):
                        context_prompt += f"\n**已知设施：** {', '.join(context_info['known_facilities'][:5])}"
                    # 已知群体
                    if context_info.get("known_groups"):
                        context_prompt += f"\n**已知群体：** {', '.join(context_info['known_groups'][:5])}"
                    # 已知道具
                    if context_info.get("known_items"):
                        context_prompt += f"\n**已知道具：** {', '.join(context_info['known_items'][:5])}"
                    # 未完成事件
                    if context_info.get("unfinished_events"):
                        context_prompt += f"\n**未完成事件：** {', '.join(context_info['unfinished_events'][:5])}"
                    # 待回收伏笔
                    if context_info.get("pending_foreshadows"):
                        context_prompt += f"\n**待回收伏笔：** {', '.join(context_info['pending_foreshadows'][:5])}"

                prompt = EXTENDED_STATE_EXTRACTION_PROMPT.format(
                    max_entities=max_entities,
                    max_relations=max_relations,
                    chapter_num=chapter_num,
                    content=f"{context_prompt}\n\n{chapter_content}"
                )

                # 获取模型支持的最大输出token
                max_output_tokens = self.llm_provider.get_max_output_tokens()

                response = await self.llm_provider.generate(
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=max_output_tokens
                )

                if not response or not hasattr(response, 'content') or response.content is None:
                    self.logger.warning(
                        f"扩展状态提取返回无效响应，尝试 {attempt+1}/{max_retries}")
                    continue

                # 解析响应
                result = self._parse_llm_response(response.content)
                if result:
                    # 为实体添加章节号
                    for entity in result.get("entities", []):
                        if "chapter" not in entity:
                            entity["chapter"] = chapter_num

                    # 质量验证
                    validated_result = self._validate_extended_state_result(
                        result, chapter_num
                    )

                    self.logger.info(
                        f"扩展状态提取成功: 章节{chapter_num}, "
                        f"实体数={len(validated_result.get('entities', []))}, "
                        f"关系数={len(validated_result.get('relations', []))}, "
                        f"一致性提示={len(validated_result.get('consistency_notes', []))}")

                    validated_result["chapter"] = chapter_num
                    return validated_result

                self.logger.warning(f"JSON解析失败，尝试 {attempt+1}/{max_retries}")

            except Exception as e:
                error_str = str(e)
                last_error = e

                # 检测429错误
                is_rate_limit = '429' in error_str or 'rate' in error_str.lower()

                if is_rate_limit:
                    wait_time = 10 * (2 ** attempt)
                    self.logger.warning(
                        f"API限流，等待 {wait_time}秒 后重试...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                else:
                    self.logger.warning(f"扩展状态提取异常: {error_str[:200]}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)

        self.logger.error(
            f"扩展状态提取失败: 章节{chapter_num}. 最后错误: {str(last_error)[:200] if last_error else 'None'}")

        # 返回空结果而非失败
        return {
            "entities": [],
            "relations": [],
            "consistency_notes": [],
            "chapter": chapter_num,
            "_extraction_failed": True
        }

    def _validate_extended_state_result(
        self,
        result: Dict[str, Any],
        chapter_num: int
    ) -> Dict[str, Any]:
        """
        验证扩展状态提取结果的质量

        Args:
            result: LLM提取的原始结果
            chapter_num: 章节号

        Returns:
            验证和清理后的结果
        """
        validated_entities = []
        validated_relations = []
        consistency_notes = result.get("consistency_notes", [])
        issues_found = []

        # 定义扩展实体的合法类型
        extended_entity_types = {
            # 设施相关
            "设施", "设施状态变化", "设施归属变更", "设施物理状态",
            # 事件相关
            "事件", "事件状态变化", "事件影响", "事件因果链",
            # 群体相关
            "群体组织", "群体状态变化", "群体成员变动", "群体关系变化",
            # 道具相关
            "道具物品", "道具状态变化", "道具归属变更", "道具功能使用",
            # 世界规则
            "世界规则", "规则引用", "规则例外",
            # 时间线
            "时间节点", "时间流逝",
            # 伏笔
            "伏笔", "伏笔回收"
        }

        # 验证实体
        for entity in result.get("entities", []):
            # 检查0：实体必须是字典类型
            if not isinstance(entity, dict):
                issues_found.append(f"跳过非字典类型的实体: {type(entity).__name__}")
                self.logger.warning(
                    f"扩展状态实体类型错误，跳过: {type(entity).__name__}, 值: {str(entity)[:50]}")
                continue

            entity_type = entity.get("type", "")

            # 检查类型合法性
            if entity_type not in extended_entity_types:
                issues_found.append(f"跳过非扩展类型实体: {entity_type}")
                continue

            # 检查必要字段
            if not entity.get("text"):
                entity["text"] = f"{entity_type} - 章节{chapter_num}"
                issues_found.append("补充text字段")

            # 检查描述
            if not entity.get("description") or len(entity.get("description", "")) < 5:
                entity["description"] = entity.get("text", "")
            # 确保有level字段
            if "level" not in entity:
                # 根据类型推断level
                macro_types = {"设施", "事件", "群体组织", "道具物品", "世界规则", "时间节点"}
                entity["level"] = "macro" if entity_type in macro_types else "micro"

            validated_entities.append(entity)

        # 验证关系
        for relation in result.get("relations", []):
            # 检查0：关系必须是字典类型
            if not isinstance(relation, dict):
                issues_found.append(f"跳过非字典类型的关系: {type(relation).__name__}")
                self.logger.warning(
                    f"扩展状态关系类型错误，跳过: {type(relation).__name__}, 值: {str(relation)[:50]}")
                continue

            if not relation.get("source") or not relation.get("target"):
                issues_found.append("跳过不完整的关系")
                continue

            if not relation.get("relation"):
                relation["relation"] = "关联"

            validated_relations.append(relation)

        # 记录验证结果
        if issues_found:
            self.logger.debug(
                f"扩展状态质量验证: 章节{chapter_num}, "
                f"问题数={len(issues_found)}, "
                f"有效实体={len(validated_entities)}, 有效关系={len(validated_relations)}")

        return {
            "entities": validated_entities,
            "relations": validated_relations,
            "consistency_notes": consistency_notes,
            "_validation_issues": len(issues_found)
        }
