# -*- coding: utf-8 -*-
"""
小说文风知识库
包含45种经典文风的结构化数据，支持分类检索、多风格融合等功能
"""

from typing import Dict, List, Optional

STYLE_LIBRARY = {
    "version": "1.1.0",
    "total_styles": 61,
    "categories": {
        "traditional": {
            "name": "传统文学流派",
            "description": "经典文学流派的写作风格",
            "styles": [
                {
                    "id": "realism",
                    "name": "现实主义",
                    "description": "忠实描绘社会现实，关注普通人生活与社会矛盾",
                    "features": {
                        "vocabulary": {
                            "word_preference": "朴实、精确、贴近生活的词汇",
                            "avoid": ["过度华丽的辞藻", "空洞的抒情词"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["陈述句", "细节描写句", "对话句"],
                            "avg_length": "中等，20-40字"
                        },
                        "narrative_style": {
                            "perspective": "第三人称全知或限知视角",
                            "focus": "社会环境、人物心理、日常细节"
                        },
                        "description_style": "具体、客观、有质感的细节描写",
                        "dialogue_style": "口语化、符合人物身份，揭示性格",
                        "emotional_expression": "克制、通过行动和细节传达情感"
                    },
                    "examples": ["托尔斯泰", "巴尔扎克", "老舍", "路遥"],
                    "writing_guide": "以真实的社会生活为素材，通过典型人物和典型环境的塑造，反映社会本质。注重细节的真实性，避免主观臆造。人物性格应当复杂立体，行为有其社会根源。场景描写要有质感，让读者如临其境。对话要符合人物的社会地位、教育背景和性格特征。情感表达含蓄，通过行动和选择来体现人物内心世界。",
                    "avoid_patterns": ["脱离现实的浪漫化处理", "主观说教", "人物脸谱化", "情节过于巧合"]
                },
                {
                    "id": "romanticism",
                    "name": "浪漫主义",
                    "description": "强调情感、想象和个性，追求理想与自由",
                    "features": {
                        "vocabulary": {
                            "word_preference": "富于情感色彩、充满想象力的词汇",
                            "signature_words": ["自由", "激情", "灵魂", "永恒", "命运"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["感叹句", "排比句", "抒情长句"],
                            "avg_length": "较长，30-60字"
                        },
                        "narrative_style": {
                            "perspective": "第一人称或亲密第三人称",
                            "focus": "内心情感、理想追求、自然意象"
                        },
                        "description_style": "充满激情、色彩鲜明的意象描写",
                        "dialogue_style": "充满情感张力，表达内心渴望",
                        "emotional_expression": "直接、热烈、毫不掩饰的情感爆发"
                    },
                    "examples": ["雨果", "拜伦", "郭沫若", "徐志摩"],
                    "writing_guide": "释放情感，不受理性约束，追求理想的极致表达。大量运用比喻、拟人等修辞手法，将自然景物与人物情感融为一体。人物往往具有强烈的个性和崇高的理想，敢于挑战命运。语言富于音乐感和节奏感，多用排比和感叹。不回避激烈的情感冲突和戏剧性场面。",
                    "avoid_patterns": ["过于平淡的叙述", "冷静客观的分析", "琐碎的日常细节", "理性压制情感"]
                },
                {
                    "id": "magic_realism",
                    "name": "魔幻现实主义",
                    "description": "将奇幻元素与现实生活自然融合，神奇与平凡并置",
                    "features": {
                        "vocabulary": {
                            "word_preference": "日常词汇与奇幻描述的混合",
                            "signature_words": ["仿佛", "突然", "从来如此", "理所当然"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["平静陈述超自然事件", "细节描写魔幻场景"],
                            "avg_length": "中等，保持平静的叙事节奏"
                        },
                        "narrative_style": {
                            "perspective": "叙述者以平常心对待魔幻事件",
                            "focus": "时间的非线性、家族命运、历史与神话交织"
                        },
                        "description_style": "以写实笔法描写超自然现象，不加解释",
                        "dialogue_style": "自然口语，人物对魔幻事件习以为常",
                        "emotional_expression": "平静接受不可思议之事，情感深埋于叙述中"
                    },
                    "examples": ["马尔克斯", "略萨", "莫言", "陈忠实"],
                    "writing_guide": "关键在于'以平常心叙述非常之事'。奇幻元素不需要解释，人物和叙述者都将其视为日常。将现实的贫困、暴力、历史创伤与奇异的想象并置，揭示更深层的真实。时间可以循环、压缩或延伸。家族、土地、历史是常见的宏大主题。叙述语调始终保持平静，越是荒诞的事件越要用平淡语气描写。",
                    "avoid_patterns": ["解释魔幻现象", "表现惊讶或不适", "逻辑上自圆其说", "明确区分现实与幻想"]
                },
                {
                    "id": "modernism",
                    "name": "现代主义",
                    "description": "意识流、内心独白、非线性叙事，探索人的内在世界",
                    "features": {
                        "vocabulary": {
                            "word_preference": "感官意象、意识碎片、象征性词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["意识流长句", "不完整的句子", "意象并置"],
                            "avg_length": "长短不一，跟随意识流动"
                        },
                        "narrative_style": {
                            "perspective": "深度内视，多重视角",
                            "focus": "内心意识、时间感知、存在困境"
                        },
                        "description_style": "感官与意识交织，主客观界限模糊",
                        "dialogue_style": "内心独白为主，对话常被意识打断",
                        "emotional_expression": "通过意识流动间接呈现，非直接表达"
                    },
                    "examples": ["乔伊斯", "伍尔夫", "福克纳", "王蒙"],
                    "writing_guide": "打破线性时间，跟随人物意识自由流动。句子可以很长，思维跳跃，从一个联想到另一个联想。大量使用感官意象，把外部感知与内部情感混为一谈。对话不必符合社交逻辑，而是内心思维的外化。刻意制造叙事的破碎感和不确定性，让读者自行拼接。",
                    "avoid_patterns": ["线性因果叙事", "全知视角的客观描述", "逻辑连贯的对话", "清晰的情节结构"]
                },
                {
                    "id": "naturalism",
                    "name": "自然主义",
                    "description": "科学客观地描绘人类行为，强调遗传与环境的决定性影响",
                    "features": {
                        "vocabulary": {
                            "word_preference": "精确、科学、不加美化的词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["客观陈述", "细致观察式描写"]
                        },
                        "narrative_style": {
                            "perspective": "冷静旁观的第三人称",
                            "focus": "本能、欲望、社会环境对人的塑造"
                        },
                        "description_style": "不加粉饰、揭示丑陋真相的直接描写",
                        "dialogue_style": "粗粝、真实，反映底层生活",
                        "emotional_expression": "极度克制，以现象代替评判"
                    },
                    "examples": ["左拉", "莫泊桑", "德莱赛"],
                    "writing_guide": "像科学家一样观察人类社会，不加道德评判。关注底层人物受环境和本能驱动的行为。毫不回避丑陋、堕落、绝望的现实。叙述者保持冷静客观，不介入也不评价。通过积累细节来揭示真相，而非直接说明。",
                    "avoid_patterns": ["道德说教", "美化现实", "英雄主义", "浪漫化苦难"]
                },
                {
                    "id": "existentialism",
                    "name": "存在主义",
                    "description": "探索人的存在意义、荒诞处境和自由选择",
                    "features": {
                        "vocabulary": {
                            "word_preference": "存在、虚无、荒诞、自由、责任、选择"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["简短有力的陈述", "哲学性的追问", "重复强调"]
                        },
                        "narrative_style": {
                            "perspective": "第一人称，内省式",
                            "focus": "自我意识、死亡意识、选择的重量"
                        },
                        "description_style": "冷静、抽离、有时荒诞的场景描写",
                        "dialogue_style": "充满哲理思辨，揭示人物的精神困境",
                        "emotional_expression": "疏离感、压抑感、以及偶发的强烈情绪冲击"
                    },
                    "examples": ["加缪", "萨特", "卡夫卡", "余华早期"],
                    "writing_guide": "人物面对荒诞的世界，试图寻找或创造意义。叙述语调往往疏离甚至冷漠，与事件的严重性形成反差。重点不在情节的起伏，而在人物的内心挣扎和哲学思考。死亡、偶然、他人的凝视是常见主题。人物最终必须在没有外部依据的情况下做出选择。",
                    "avoid_patterns": ["轻松解决困境", "道德上的确定性", "神意或命运的安排", "圆满结局"]
                },
                {
                    "id": "gothic",
                    "name": "哥特式",
                    "description": "黑暗美学、神秘恐怖、衰败与死亡的文学氛围",
                    "features": {
                        "vocabulary": {
                            "word_preference": "阴暗、腐朽、神秘、恐惧相关词汇",
                            "signature_words": ["黑暗", "阴影", "腐朽", "幽灵", "诅咒", "秘密"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["悬念堆叠", "气氛渲染的长句", "不安的停顿"]
                        },
                        "narrative_style": {
                            "perspective": "受困于黑暗力量的视角",
                            "focus": "恐惧、死亡、禁忌、超自然力量"
                        },
                        "description_style": "浓重阴郁的氛围渲染，感官上的不适与恐惧",
                        "dialogue_style": "充满隐藏信息，预示厄运",
                        "emotional_expression": "恐惧、不安、迷恋与厌恶并存"
                    },
                    "examples": ["爱伦·坡", "布莱克伍德", "安妮·赖斯"],
                    "writing_guide": "营造压抑、阴暗的氛围是首要任务。古老的建筑、腐朽的花园、永夜的景色都是标志性场景。人物往往被黑暗力量吸引而无法自拔。语言要有节奏的张力，在平静叙述与恐惧爆发之间交替。死亡不是结束而是变化，爱与死往往纠缠在一起。",
                    "avoid_patterns": ["明亮轻松的场景", "快速解决的冲突", "理性驱散恐惧", "平凡的日常"]
                },
                {
                    "id": "surrealism",
                    "name": "超现实主义",
                    "description": "梦境逻辑、潜意识释放、打破理性边界",
                    "features": {
                        "vocabulary": {
                            "word_preference": "奇异组合、出人意料的意象并置"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["梦境式联想", "不合逻辑但感官真实的描写"]
                        },
                        "narrative_style": {
                            "perspective": "梦境视角，因果关系失效",
                            "focus": "潜意识、梦境、欲望的直接呈现"
                        },
                        "description_style": "将不相关事物并置，产生奇异的感官效果",
                        "dialogue_style": "非逻辑对话，遵循潜意识规律",
                        "emotional_expression": "原始欲望和恐惧的直接投射"
                    },
                    "examples": ["布勒东", "达利小说化", "博尔赫斯部分作品"],
                    "writing_guide": "放弃理性控制，让潜意识自由流淌。事物之间的联系基于情感和意象而非逻辑。时间和空间可以任意变形。将日常物品赋予异样的意义，将异样的事物描写得如此正常。创造陌生感和奇异感是核心目标。",
                    "avoid_patterns": ["逻辑因果", "合理解释", "日常叙事节奏", "可预测的情节"]
                },
                {
                    "id": "postmodernism",
                    "name": "后现代主义",
                    "description": "元叙事、戏仿、碎片化结构，质疑叙事本身",
                    "features": {
                        "vocabulary": {
                            "word_preference": "自我指涉、互文性引用、多层次语言游戏"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["元叙事（叙述者谈论写作行为）", "戏仿既有文类", "碎片拼贴"]
                        },
                        "narrative_style": {
                            "perspective": "不可靠叙述者，叙事本身成为主题",
                            "focus": "叙事的建构性、真相的不确定性"
                        },
                        "description_style": "戏谑、反讽、自我解构",
                        "dialogue_style": "引用、戏仿、反讽为主",
                        "emotional_expression": "疏离的幽默，或深层的绝望"
                    },
                    "examples": ["博尔赫斯", "纳博科夫", "卡尔维诺"],
                    "writing_guide": "打破第四堵墙，叙述者承认自己在写小说。混用不同文类、风格和时代的写法。意义是多元的、开放的，拒绝单一解读。互文引用、致敬、戏仿是常用手法。结构本身就是意义的一部分——碎片就是碎片，不需要整合。",
                    "avoid_patterns": ["单一权威叙事", "真相的确定性", "严肃的宏大主题", "线性完整情节"]
                },
                {
                    "id": "minimalism_lit",
                    "name": "极简主义文学",
                    "description": "省略胜于表达，留白创造张力，克制中蕴含深度",
                    "features": {
                        "vocabulary": {
                            "word_preference": "简单、日常、精准的词汇",
                            "avoid": ["形容词堆叠", "复杂比喻", "说教性语言"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["短句", "简单句", "对话"],
                            "avg_length": "短，10-20字"
                        },
                        "narrative_style": {
                            "perspective": "冷静旁观",
                            "focus": "表面之下的深层张力"
                        },
                        "description_style": "冰山原则：只写可见部分，意义在水面以下",
                        "dialogue_style": "简短、有时不完整，充满未说出的含义",
                        "emotional_expression": "完全不直接表达，通过场景和行动暗示"
                    },
                    "examples": ["海明威", "卡佛", "村上春树部分作品"],
                    "writing_guide": "删去一切可以删去的词。永远不要解释情感，让场景和行动说话。对话要简短，说出来的往往不是真正想说的。背景信息降到最低。句子要有力量感，避免任何多余的修饰。读者需要主动参与填补空白——这就是你留下的空间。",
                    "avoid_patterns": ["情感说明", "心理分析", "冗余细节", "过度修饰"]
                },
                {
                    "id": "stream_of_consciousness",
                    "name": "意识流",
                    "description": "跟随人物内心意识的自由流动，时间与空间任意穿梭",
                    "features": {
                        "vocabulary": {
                            "word_preference": "感官词、联想词、情绪词的混合流动"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["长句绵延", "思维跳跃不加过渡", "标点不规则"],
                            "avg_length": "极长或极短，跟随意识节奏"
                        },
                        "narrative_style": {
                            "perspective": "深度内视，时间错乱",
                            "focus": "当下感知、记忆闪回、无意识联想"
                        },
                        "description_style": "内外感知融合，无明确边界",
                        "dialogue_style": "内心独白与外部对话混杂",
                        "emotional_expression": "情绪直接嵌入意识流中，无需标注"
                    },
                    "examples": ["乔伊斯《尤利西斯》", "伍尔夫《到灯塔去》"],
                    "writing_guide": "让思维自由流动，不受时间和空间限制。一个感官刺激可以触发跨越多年的记忆。思维可以从眼前的现实跳到遥远的过去再回到当下。不需要'他想到……'这样的过渡，直接进入思维内容。标点可以非常规，长句不断延伸直到意识耗尽。",
                    "avoid_patterns": ["清晰的时间线", "逻辑过渡", "全知叙述者", "客观场景描述"]
                },
                {
                    "id": "satirical",
                    "name": "讽刺文学",
                    "description": "以幽默或讽刺揭露社会弊病、人性弱点",
                    "features": {
                        "vocabulary": {
                            "word_preference": "反讽词汇、夸张对比、故意错置的庄重用语"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["反讽式陈述", "夸张对比", "反高潮"]
                        },
                        "narrative_style": {
                            "perspective": "表面天真或过于正经的叙述者",
                            "focus": "社会制度、人类愚蠢、权力滥用"
                        },
                        "description_style": "用严肃笔调描写荒谬，夸大现实以揭示本质",
                        "dialogue_style": "充满言外之意，人物往往自我揭示",
                        "emotional_expression": "表面轻松，底层愤慨或悲悯"
                    },
                    "examples": ["斯威夫特", "奥威尔", "钱钟书"],
                    "writing_guide": "用最严肃的语气讲最荒诞的事。讽刺效果来自预期与实际的落差——越是正经地描写荒唐，越有讽刺力量。让人物自己说出揭穿自己的话，而叙述者保持表面的尊重或赞许。夸大但不失真，放大现实的某一方面直到荒谬显形。",
                    "avoid_patterns": ["直接批评", "明显的道德说教", "人物自我意识到讽刺", "过度温情"]
                },
                {
                    "id": "fable_allegory",
                    "name": "寓言/象征主义",
                    "description": "通过故事传达道德或哲学寓意，象征贯穿全文",
                    "features": {
                        "vocabulary": {
                            "word_preference": "具有象征意涵的词汇，每个意象都有深层含义"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["简洁明了的叙述", "有意重复的象征元素"]
                        },
                        "narrative_style": {
                            "perspective": "全知视角或简明旁观",
                            "focus": "象征体系的构建与发展"
                        },
                        "description_style": "每个场景细节都服务于寓意",
                        "dialogue_style": "富含隐喻，人物言行代表抽象概念",
                        "emotional_expression": "节制，情感服从于寓意的传达"
                    },
                    "examples": ["《动物农场》", "《小王子》", "《老人与海》"],
                    "writing_guide": "故事的每个元素都在两个层面上运作：字面层和象征层。建立清晰的象征体系，并在全文中保持一致。情节要独立成立，寓意不应强加给读者，而应从故事中自然浮现。",
                    "avoid_patterns": ["直白说出寓意", "象征体系不一致", "过于复杂的情节", "寓意凌驾于故事之上"]
                },
                {
                    "id": "detective_classic",
                    "name": "古典侦探小说",
                    "description": "以逻辑推理为核心，谜题设置与揭秘的智识游戏",
                    "features": {
                        "vocabulary": {
                            "word_preference": "精确、分析性、线索相关词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["逻辑推导", "证据列举", "悬念累积"]
                        },
                        "narrative_style": {
                            "perspective": "第一人称助手视角或第三人称有限视角",
                            "focus": "谜题、线索、推理过程"
                        },
                        "description_style": "细节精准，每个描写都可能是线索",
                        "dialogue_style": "信息量大，隐藏与揭示并行",
                        "emotional_expression": "智识的满足感，紧张感控制"
                    },
                    "examples": ["阿加莎·克里斯蒂", "柯南·道尔", "东野圭吾"],
                    "writing_guide": "公平游戏原则：线索都在文中，但经过伪装。叙述者（如果是侦探的助手）必须真实，不能主动隐瞒。节奏控制至关重要：谜题设置→调查→错误方向→正确方向→揭晓。每个人都有嫌疑，每个细节都可能相关。",
                    "avoid_patterns": ["事后才引入关键信息", "超自然解释", "偶然解决谜题", "忽视逻辑"]
                },
                {
                    "id": "epic_heroic",
                    "name": "史诗/英雄叙事",
                    "description": "宏大格局、英雄征途、命运与荣耀的史诗叙述",
                    "features": {
                        "vocabulary": {
                            "word_preference": "宏大、庄严、充满历史感的词汇",
                            "signature_words": ["命运", "荣耀", "征途", "传说", "不朽"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["宏大叙事的长句", "排比渲染气势", "史诗式开篇"]
                        },
                        "narrative_style": {
                            "perspective": "全知视角，宏观俯视",
                            "focus": "英雄成长、命运抗争、文明兴衰"
                        },
                        "description_style": "宏大壮阔的战场、山川、时代描写",
                        "dialogue_style": "庄严有力，体现人物的英雄气概",
                        "emotional_expression": "崇高感、悲壮感、宏大的历史情怀"
                    },
                    "examples": ["荷马史诗", "《三国演义》", "《指环王》"],
                    "writing_guide": "以宏大视角俯视人物命运。英雄的个人故事与时代、民族、命运交织。语言要有庄严的力量感，每个词都要有分量。战斗、旅程、考验是叙事骨架。英雄并非完美，但有超凡的意志和使命感。",
                    "avoid_patterns": ["琐碎的日常细节", "过于现代的语言", "英雄的平庸化", "缺乏宏大背景"]
                },
                {
                    "id": "pastoral",
                    "name": "田园/乡土文学",
                    "description": "描绘自然乡土之美，乡村生活与城市文明的对照",
                    "features": {
                        "vocabulary": {
                            "word_preference": "自然景物、农村生活、地方方言词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["舒缓的自然描写", "生活化的叙述", "方言融入"]
                        },
                        "narrative_style": {
                            "perspective": "亲切的本地人或归乡者视角",
                            "focus": "自然节律、乡土人情、传统与变迁"
                        },
                        "description_style": "细腻、温暖的自然和生活场景",
                        "dialogue_style": "地方口语，生动真实",
                        "emotional_expression": "对土地的眷恋，对逝去的乡土的哀愁"
                    },
                    "examples": ["沈从文", "汪曾祺", "陈忠实", "莫言部分"],
                    "writing_guide": "让土地有生命，让自然景物成为情感的容器。方言和地方特色是宝贵资产，不要抹去。人与土地的关系是核心主题。节奏要跟随乡村生活的节律，不急促。即使写贫苦也要有温度，乡土不是落后而是根。",
                    "avoid_patterns": ["城市化的快节奏", "标准普通话式的单一语言", "对乡村的俯视", "刻意的苦难渲染"]
                }
            ]
        },
        "personal": {
            "name": "作家个人风格",
            "description": "向经典作家风格致敬的写作方式",
            "styles": [
                {
                    "id": "hemingway_concise",
                    "name": "海明威式简洁",
                    "description": "硬汉文风，冰山理论，省略大于表达",
                    "features": {
                        "vocabulary": {
                            "word_preference": "简单动词、具体名词，避免副词和形容词",
                            "avoid": ["修饰词堆叠", "抽象概念", "情感直接表达"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["And连接的简单句", "动词主导的行动句", "极短对话"],
                            "avg_length": "短，15字以内"
                        },
                        "narrative_style": {
                            "perspective": "第三人称，外部观察",
                            "focus": "行动、对话、外部细节，回避内心剖析"
                        },
                        "description_style": "只写看得见的，意义在冰山水面以下",
                        "dialogue_style": "极简，充满言外之意，男人不说软话",
                        "emotional_expression": "完全不直接写情感，通过行动和省略暗示"
                    },
                    "examples": ["《老人与海》", "《永别了武器》", "《太阳照常升起》"],
                    "writing_guide": "每个句子只保留必要的词。用and而非逗号连接动作，产生节奏感。对话不要有'他悲伤地说'，只写说了什么。人物喝酒、钓鱼、打猎——行动代替心理。死亡和失去不直接写，只写周围人的反应和行动变化。",
                    "avoid_patterns": ["心理分析", "情感直白表达", "复杂从句", "修辞装饰", "解释和说明"]
                },
                {
                    "id": "yu_hua_cold",
                    "name": "余华式冷峻",
                    "description": "以冷静甚至冷漠的笔调描写极端苦难，形成强烈反差",
                    "features": {
                        "vocabulary": {
                            "word_preference": "平实词汇，有时刻意使用不合时宜的冷静词"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["简短直白的事件陈述", "不带情感的暴力描写"]
                        },
                        "narrative_style": {
                            "perspective": "冷静旁观，不介入评价",
                            "focus": "苦难、死亡、命运的偶然性"
                        },
                        "description_style": "用写天气的语气写死亡，用写流水账的方式写苦难",
                        "dialogue_style": "简短，透露人物的麻木或挣扎",
                        "emotional_expression": "叙述者零情感，读者情感爆发"
                    },
                    "examples": ["《活着》", "《许三观卖血记》", "《在细雨中呼喊》"],
                    "writing_guide": "最大的悲剧用最平静的语言写。'他死了'比'他悲惨地死去'更有力量。苦难一件接着一件，中间不加喘息，让读者被淹没。人物接受命运，不反抗，不控诉，只是活下去。叙述者像一台摄像机，记录一切，但不评价。",
                    "avoid_patterns": ["煽情表达", "命运的公平与正义", "英雄式反抗", "心理深度分析"]
                },
                {
                    "id": "mo_yan_surreal",
                    "name": "莫言式魔幻乡土",
                    "description": "高密东北乡的传奇，民间故事与历史混融，感官浓烈",
                    "features": {
                        "vocabulary": {
                            "word_preference": "浓烈的感官词汇，方言气息，民间俚语"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["长句连绵", "感官意象堆叠", "夸张与具体结合"]
                        },
                        "narrative_style": {
                            "perspective": "半虚构的民间叙事者",
                            "focus": "历史、欲望、生死、土地"
                        },
                        "description_style": "色彩浓烈，气味、声音、触感并举",
                        "dialogue_style": "民间口语，生猛直接",
                        "emotional_expression": "浓烈、原始、毫不掩饰"
                    },
                    "examples": ["《红高粱家族》", "《丰乳肥臀》", "《蛙》"],
                    "writing_guide": "调动所有感官，把读者浸入场景中。历史和传说可以混用，虚实边界模糊。欲望、死亡、土地是永恒主题。语言要有力量感，句子可以很长、很密、很浓。民间的生命力是最重要的东西，不要矫情。",
                    "avoid_patterns": ["雅致的语言", "城市化视角", "道德评判", "单薄的感官描写"]
                },
                {
                    "id": "zhang_ailing_delicate",
                    "name": "张爱玲式细腻",
                    "description": "精准的心理刻画，苍凉的人生底色，华丽而悲凉",
                    "features": {
                        "vocabulary": {
                            "word_preference": "精致的服饰器物描写，带有时代感的旧词",
                            "signature_words": ["苍凉", "参差", "荒凉", "月光", "镜子"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["比喻精准奇特", "心理分析细密", "时代感的描写"]
                        },
                        "narrative_style": {
                            "perspective": "全知但有悲悯距离的旁观",
                            "focus": "女性心理、世俗欲望、历史苍凉"
                        },
                        "description_style": "物质细节极为精确，每样东西都有象征意涵",
                        "dialogue_style": "充满心理博弈，每句话都有潜台词",
                        "emotional_expression": "悲悯而疏离，苍凉的人生感悟"
                    },
                    "examples": ["《金锁记》", "《倾城之恋》", "《红玫瑰与白玫瑰》"],
                    "writing_guide": "用服饰、家具、气味来写人物的处境和心理。比喻要奇特精准，让读者一愣后深觉真切。女性人物的心理要细密，但不是自怜，而是清醒的算计与妥协。历史的大背景让个人的悲欢显得苍凉渺小。每句对话背后都有真正想说的话。",
                    "avoid_patterns": ["简单化的人物动机", "直白的情感表达", "理想化的爱情", "缺乏物质感的描写"]
                },
                {
                    "id": "lu_xun_sharp",
                    "name": "鲁迅式锋利",
                    "description": "以解剖刀般的笔触批判国民性，讽刺中带悲悯",
                    "features": {
                        "vocabulary": {
                            "word_preference": "简洁有力，讽刺意味的词汇选择"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["反讽式陈述", "以小见大的细节", "精准的批判性描写"]
                        },
                        "narrative_style": {
                            "perspective": "既是局内人也是观察者，带着痛苦的清醒",
                            "focus": "国民性批判、知识分子处境、社会压迫"
                        },
                        "description_style": "以精准细节揭示人物的精神困境",
                        "dialogue_style": "充满讽刺，人物不自知地揭示自身弱点",
                        "emotional_expression": "悲悯与愤怒的交织，而非单纯的控诉"
                    },
                    "examples": ["《阿Q正传》", "《狂人日记》", "《祝福》"],
                    "writing_guide": "批判从不离开悲悯。阿Q是可笑的，但鲁迅不仅仅是在嘲笑他。用精准的细节让读者自己看见问题，而不是直接批判。叙述者有时是痛苦的参与者，而不只是旁观者。语言简练但每字有力。",
                    "avoid_patterns": ["单纯的说教", "纯粹的嘲讽", "脱离社会背景", "过于温情的处理"]
                },
                {
                    "id": "marquez_style",
                    "name": "马尔克斯式魔幻",
                    "description": "将奇幻事件用新闻报道式的平静语气叙述",
                    "features": {
                        "vocabulary": {
                            "word_preference": "新闻式准确，但描述的是荒诞事件"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["从结果开始的倒叙", "精确的时间地点标注", "绵长的叙事句"]
                        },
                        "narrative_style": {
                            "perspective": "全知视角，用新闻的确定性叙述不确定的事",
                            "focus": "时间循环、家族命运、政治寓言、孤独"
                        },
                        "description_style": "魔幻事件的精确描述，不加任何惊讶",
                        "dialogue_style": "人物以日常态度谈论超常之事",
                        "emotional_expression": "潜藏于平静叙述之下的深层孤独"
                    },
                    "examples": ["《百年孤独》", "《霍乱时期的爱情》"],
                    "writing_guide": "开篇直接进入核心，然后往回填充。用'多年以后'这样的时间跳跃建立宏大感。魔幻要用最准确的新闻语言描写，越准确越魔幻。孤独是所有人物的底色，用不同方式呈现。",
                    "avoid_patterns": ["解释魔幻", "惊讶反应", "线性叙事", "单一人物视角"]
                },
                {
                    "id": "kafka_absurd",
                    "name": "卡夫卡式荒诞",
                    "description": "荒诞处境中个体的异化与无力感，官僚体制的压迫",
                    "features": {
                        "vocabulary": {
                            "word_preference": "日常词汇描述非日常困境，行政和法律词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["平静描述荒诞", "无尽的程序和规定", "逻辑严密但前提荒唐"]
                        },
                        "narrative_style": {
                            "perspective": "困于荒诞体制中的第一人称或紧密第三人称",
                            "focus": "无法逃脱的困境、身份的消解、权力的无所不在"
                        },
                        "description_style": "细节精确，但整体荒诞",
                        "dialogue_style": "官僚式对话，看似合理实则毫无出路",
                        "emotional_expression": "压抑的无力感，偶尔爆发的荒诞幽默"
                    },
                    "examples": ["《变形记》", "《审判》", "《城堡》"],
                    "writing_guide": "主人公面对一个有自己逻辑的荒诞体制，试图弄清楚规则却总是失败。永远不要解释荒诞的来源——它就是存在的。叙述者用完全正式的语气描述荒诞，这种反差制造效果。没有出路，但人物仍然努力寻找——这本身就是荒诞所在。",
                    "avoid_patterns": ["解释荒诞的来源", "英雄式突破", "温情结局", "合理的解决方案"]
                },
                {
                    "id": "calvino_playful",
                    "name": "卡尔维诺式奇想",
                    "description": "哲学思辨与叙事游戏的结合，轻盈而深刻",
                    "features": {
                        "vocabulary": {
                            "word_preference": "精确、清晰、带哲学意味的词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["哲学假设的展开", "叙事实验", "元叙事插入"]
                        },
                        "narrative_style": {
                            "perspective": "游戏性的多视角，叙述者常自我指涉",
                            "focus": "可能性的探索、观察与存在的关系"
                        },
                        "description_style": "精确而轻盈，每个细节都开向无限",
                        "dialogue_style": "哲学性，但不失趣味",
                        "emotional_expression": "智识的喜悦，存在的轻盈感"
                    },
                    "examples": ["《如果在冬夜，一个旅人》", "《看不见的城市》"],
                    "writing_guide": "从一个奇特的假设出发，然后严格推演它的后果。叙事本身可以成为主题。轻盈不是浅薄，而是以轻盈的笔触触及沉重的主题。游戏和认真可以并存。",
                    "avoid_patterns": ["沉重的说教", "线性情节", "单一视角", "拒绝实验"]
                },
                {
                    "id": "shen_congwen_lyrical",
                    "name": "沈从文式抒情",
                    "description": "湘西世界的诗意书写，人性美与自然美的融合",
                    "features": {
                        "vocabulary": {
                            "word_preference": "自然清新、带有湘西地方色彩的词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["散文化的抒情长句", "自然与人交织的描写"]
                        },
                        "narrative_style": {
                            "perspective": "温柔的旁观者",
                            "focus": "自然之美、人性纯真、时间流逝"
                        },
                        "description_style": "水墨画式的自然描写，清淡而深远",
                        "dialogue_style": "质朴自然，带着湘西口语的节奏",
                        "emotional_expression": "温柔、惆怅、对美好的深情凝视"
                    },
                    "examples": ["《边城》", "《湘西散记》", "《长河》"],
                    "writing_guide": "让自然景物有呼吸、有情感。人物和自然融为一体，人的命运与水的流动同节奏。语言要有散文的节奏感，读起来像在听歌。写纯真的时候，要知道纯真终将逝去，这才是惆怅的根源。",
                    "avoid_patterns": ["城市化视角", "快节奏情节", "过于复杂的心理分析", "沉重的社会批判"]
                },
                {
                    "id": "wang_xiaobo_witty",
                    "name": "王小波式机智",
                    "description": "以智识幽默反抗愚昧，自由精神的文学表达",
                    "features": {
                        "vocabulary": {
                            "word_preference": "机智、反讽、带数学/逻辑气质的精确词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["逻辑推导式幽默", "出人意料的类比", "反讽性陈述"]
                        },
                        "narrative_style": {
                            "perspective": "睿智而幽默的第一人称",
                            "focus": "自由与压抑、智识与愚昧、人性与规训"
                        },
                        "description_style": "以精确的语言描写荒诞，以幽默揭示荒唐",
                        "dialogue_style": "机智、有哲理，常有意外的转折",
                        "emotional_expression": "自由的快乐与压抑的愤慨，用幽默包裹"
                    },
                    "examples": ["《黄金时代》", "《白银时代》", "《青铜时代》"],
                    "writing_guide": "用最聪明的方式讲故事。幽默不是目的，而是对抗愚昧的武器。性和自由可以并行，都是对束缚的反抗。逻辑和感性并用，让读者又笑又思考。语言要有节奏感，读起来像在和一个聪明朋友聊天。",
                    "avoid_patterns": ["严肃说教", "缺乏幽默感", "逻辑混乱", "对自由的绝望"]
                },
                {
                    "id": "gu_long_cold",
                    "name": "古龙式冷艳",
                    "description": "超短句切割，悬念迭起，武林的冷峻美学",
                    "features": {
                        "vocabulary": {
                            "word_preference": "简洁冷峻，带有江湖气的词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["一字句、两字句", "段落极短", "大量留白"],
                            "avg_length": "极短，3-10字"
                        },
                        "narrative_style": {
                            "perspective": "冷眼旁观，快速切换场景",
                            "focus": "悬念、人性、江湖的孤独"
                        },
                        "description_style": "简洁到极致，用最少的词制造最强的画面感",
                        "dialogue_style": "简短有力，充满暗示和威胁",
                        "emotional_expression": "冷峻，孤独，以极少的字传达极深的情感"
                    },
                    "examples": ["《绝代双骄》", "《小李飞刀》", "《楚留香传奇》"],
                    "writing_guide": "句子越短越有力。一个字可以是一段。删去所有不必要的连接词和过渡。悬念靠省略制造——不说的比说的更重要。江湖是孤独的，英雄是孤独的，就算有朋友和爱人。对话要简短，但要有力，每句话都可能是最后一句。",
                    "avoid_patterns": ["长句复句", "详细心理分析", "过渡段落", "啰嗦的描写"]
                },
                {
                    "id": "jin_yong_grand",
                    "name": "金庸式宏大",
                    "description": "家国情怀与武侠世界，历史与传奇的交织叙事",
                    "features": {
                        "vocabulary": {
                            "word_preference": "雅俗共赏，文白交融，武学典故丰富"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["情节密集的推进", "武打场面的细腻描写", "人物群像的宏观叙述"]
                        },
                        "narrative_style": {
                            "perspective": "全知视角，兼顾宏观格局与细腻情感",
                            "focus": "侠义精神、家国情怀、人性的复杂"
                        },
                        "description_style": "武功描写有画面感，历史背景丰富真实",
                        "dialogue_style": "符合人物身份，古典气息浓厚",
                        "emotional_expression": "深沉的家国情怀，侠者的担当与牺牲"
                    },
                    "examples": ["《射雕英雄传》", "《鹿鼎记》", "《笑傲江湖》"],
                    "writing_guide": "历史是大舞台，人物在历史中找到自己的位置。武功是性格的延伸，不同的功夫体现不同的人生哲学。情节要有起伏，悬念设置精心。人物群像要丰富，主角不能脸谱化。家国与个人情感并重，才是金庸式宏大。",
                    "avoid_patterns": ["脱离历史背景", "人物单薄", "武打描写套路化", "只有爱情没有家国"]
                }
            ]
        },
        "web_novel": {
            "name": "网络小说风格",
            "description": "适合网文平台的流行写作风格",
            "styles": [
                {
                    "id": "upgrade_flow",
                    "name": "升级流/爽文",
                    "description": "主角不断变强、打脸反派、读者获得爽感的核心逻辑",
                    "features": {
                        "vocabulary": {
                            "word_preference": "等级、境界、突破、碾压、实力等词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["实力展示", "他人惊叹", "等级跃升描写"]
                        },
                        "narrative_style": {
                            "perspective": "第三人称限知，紧跟主角",
                            "focus": "主角成长、实力突破、打脸反派"
                        },
                        "description_style": "战斗场面有冲击力，实力对比鲜明",
                        "dialogue_style": "反派嚣张→主角回应→反派崩溃",
                        "emotional_expression": "爽感优先，情绪简单直接"
                    },
                    "examples": ["《斗破苍穹》", "《完美世界》", "《凡人修仙传》"],
                    "writing_guide": "每章要有爽点。主角实力提升要有节奏，不能太快也不能卡关太久。反派要足够嚣张，这样打脸才够爽。世界体系要清晰，等级要让读者一目了然。支线不要太复杂，主线要清晰。节奏要快，每章有进展。",
                    "avoid_patterns": ["主角长期受挫", "实力设定模糊", "过多文学性描写", "节奏过慢"]
                },
                {
                    "id": "infinite_flow",
                    "name": "无限流",
                    "description": "主角在不同世界/副本中穿越，解任务、求生存",
                    "features": {
                        "vocabulary": {
                            "word_preference": "副本、任务、积分、技能、BUG等游戏化词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["系统提示框", "任务分析", "危机应对"]
                        },
                        "narrative_style": {
                            "perspective": "第一人称，主角视角",
                            "focus": "解谜、生存、规则利用"
                        },
                        "description_style": "恐怖/悬疑氛围与动作场面结合",
                        "dialogue_style": "团队协作、信息分享、危机决策",
                        "emotional_expression": "紧张刺激，求生欲望"
                    },
                    "examples": ["《我在末世有套房》", "《地球上线》"],
                    "writing_guide": "规则是核心，要设计清晰的副本规则让读者可以自己推理。恐怖氛围和紧张感是无限流的灵魂。主角要聪明，利用规则而不是蛮力。每个副本都要有独特的核心设定。",
                    "avoid_patterns": ["规则不清晰", "主角纯靠运气", "副本雷同", "节奏拖沓"]
                },
                {
                    "id": "rebirth_flow",
                    "name": "重生/穿越流",
                    "description": "主角带着记忆重来，利用先知优势改变命运",
                    "features": {
                        "vocabulary": {
                            "word_preference": "前世记忆、金手指、蝴蝶效应相关词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["现在与过去对比", "主角心理优势展示", "布局与揭晓"]
                        },
                        "narrative_style": {
                            "perspective": "第一人称，带前世记忆的上帝视角",
                            "focus": "改变命运、报仇雪恨、抢占先机"
                        },
                        "description_style": "过去与现在的对照，主角的从容与他人的慌乱对比",
                        "dialogue_style": "主角游刃有余，暗藏机锋",
                        "emotional_expression": "复仇的快意，改变命运的决心"
                    },
                    "examples": ["《庶女有毒》", "《凤凰涅槃》"],
                    "writing_guide": "利用前世记忆设置伏笔，让读者和主角一起期待揭晓。对比是核心手法：前世的绝望vs今生的从容。节奏要控制好，不要太快也不要拖沓。",
                    "avoid_patterns": ["金手指过于强大", "主角不利用前世知识", "节奏拖沓", "前世设定不清晰"]
                },
                {
                    "id": "system_flow",
                    "name": "系统流",
                    "description": "主角获得游戏系统辅助，系统提示与现实互动",
                    "features": {
                        "vocabulary": {
                            "word_preference": "系统提示、属性面板、技能、任务等游戏术语"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["系统框弹出", "属性成长", "任务完成奖励"]
                        },
                        "narrative_style": {
                            "perspective": "第一人称，与系统互动",
                            "focus": "成长、任务、系统能力的发掘"
                        },
                        "description_style": "游戏界面感的文字呈现",
                        "dialogue_style": "与系统的对话，系统有独特性格",
                        "emotional_expression": "升级的满足感，任务完成的成就感"
                    },
                    "examples": ["《从大学讲师到首席院士》", "《我的玩家都是演技派》"],
                    "writing_guide": "系统要有自己的声音和性格，不只是工具。属性成长要有可视化的呈现。任务设计要有创意，不要太套路。系统的规则要自洽。",
                    "avoid_patterns": ["系统规则前后矛盾", "属性无意义", "系统只是工具没有个性", "任务太简单"]
                },
                {
                    "id": "ancient_romance",
                    "name": "古言/宫斗",
                    "description": "古代背景下的爱情与权谋，精致的古典氛围",
                    "features": {
                        "vocabulary": {
                            "word_preference": "文言词汇、宫廷用语、诗词引用"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["典雅的对话", "宫斗博弈描写", "情感的含蓄表达"]
                        },
                        "narrative_style": {
                            "perspective": "第一人称女主视角",
                            "focus": "爱情、权谋、生存"
                        },
                        "description_style": "古典美学的场景描绘，服饰器物精致",
                        "dialogue_style": "含蓄、有深意，博弈式对话",
                        "emotional_expression": "含蓄克制的情感，偶尔的情绪爆发"
                    },
                    "examples": ["《甄嬛传》", "《锦绣未央》", "《芈月传》"],
                    "writing_guide": "古典美学要贯穿始终，服饰、饮食、礼仪都要有依据。宫斗逻辑要严密，动机要清晰。情感线和权谋线要并进。人物要立体，反派也有苦衷。",
                    "avoid_patterns": ["宫斗逻辑不通", "古典用语错误", "人物扁平化", "情节拖沓"]
                },
                {
                    "id": "urban_fantasy",
                    "name": "都市异能/玄幻",
                    "description": "现代都市中的超能力者，隐秘世界与现实交织",
                    "features": {
                        "vocabulary": {
                            "word_preference": "现代都市词汇与玄幻词汇混合"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["现实与玄幻的切换", "隐秘组织的揭示", "能力的展现"]
                        },
                        "narrative_style": {
                            "perspective": "第三人称，跟随主角",
                            "focus": "隐秘世界的规则、主角的觉醒与成长"
                        },
                        "description_style": "现代场景与异能场景的对比",
                        "dialogue_style": "现代口语与玄幻语境的融合",
                        "emotional_expression": "现代人的情感逻辑"
                    },
                    "examples": ["《全职高手》", "《择天记》", "《斗罗大陆》"],
                    "writing_guide": "现代感是关键，玄幻元素要与现代生活自然融合。世界设定要有深度，隐秘世界有自己的规则和历史。主角觉醒不要太突兀，要有铺垫。",
                    "avoid_patterns": ["现代感与玄幻脱节", "世界设定浅薄", "节奏失控", "人物动机不清"]
                },
                {
                    "id": "madness_literature",
                    "name": "发疯/发癫文学",
                    "description": "用荒诞对抗内耗，主角行为'不合逻辑'，带来精神宣泄的阅读快感",
                    "features": {
                        "vocabulary": {
                            "word_preference": "口语化、情绪化、网络流行语、感叹词",
                            "signature_words": ["癫", "疯了", "不管了", "随便吧", "毁灭吧"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["短促爆发句", "反问句", "感叹句", "自言自语"],
                            "avg_length": "偏短，10-25字，情绪激动时可突然变长"
                        },
                        "narrative_style": {
                            "perspective": "第一人称或亲密第三人称，紧跟主角情绪",
                            "focus": "情绪宣泄、荒诞行为、反差喜剧效果"
                        },
                        "description_style": "夸张、戏剧化、充满黑色幽默的场景描写",
                        "dialogue_style": "情绪化、出人意料、经常'语出惊人'",
                        "emotional_expression": "直接、激烈、毫不掩饰的情绪爆发，用荒诞对抗压力"
                    },
                    "examples": ["《癫，都癫，癫点好啊》", "《狂野寡妇，在线发癫》"],
                    "writing_guide": "核心是'用荒诞对抗现实压力'。主角行为看似不合逻辑，但背后有情感合理性。节奏要快，情绪要真，荒诞要有度。黑色幽默是关键手法，让读者在笑中获得精神宣泄。不要为疯而疯，每个'发癫'行为都要有情感触发点。反差是喜剧效果来源：严肃场景+荒诞反应。",
                    "avoid_patterns": ["为疯而疯没有情感支撑", "荒诞过度失去共鸣", "情绪单一重复", "缺乏喜剧节奏"]
                },
                {
                    "id": "game_theory_narrative",
                    "name": "博弈型叙事",
                    "description": "主角在有限空间与高压规则下，依靠智谋和人性洞察破局",
                    "features": {
                        "vocabulary": {
                            "word_preference": "博弈论、心理分析、策略推理词汇",
                            "signature_words": ["规则", "破局", "筹码", "心理战", "人性"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["策略分析句", "心理推理句", "反转揭示句"],
                            "avg_length": "中等偏长，25-45字，推理过程详细"
                        },
                        "narrative_style": {
                            "perspective": "第一人称或限知第三人称，保留悬念",
                            "focus": "智谋对决、规则利用、人性博弈"
                        },
                        "description_style": "紧张压抑的氛围营造，细节暗示伏笔",
                        "dialogue_style": "博弈式对话，话中有话，心理战",
                        "emotional_expression": "高压下的冷静与紧张，反转时的震撼"
                    },
                    "examples": ["《诸神愚戏》", "《十日终焉》"],
                    "writing_guide": "规则设计是核心，要清晰且有漏洞可钻。主角靠智谋而非武力，每次破局都要有逻辑支撑。人性洞察是关键，利用贪婪、恐惧、信任等心理。反转要合理，前面要有伏笔。'斗兽场'氛围要压抑，让读者感受到高压。每场博弈都要有不同策略，避免重复。",
                    "avoid_patterns": ["规则不清晰", "主角靠运气而非智谋", "反转突兀无铺垫", "博弈模式重复"]
                },
                {
                    "id": "no_cp_female_lead",
                    "name": "无CP大女主",
                    "description": "专注女性自我成长与事业，剥离传统情感依附，展现独立意识",
                    "features": {
                        "vocabulary": {
                            "word_preference": "职业、成长、力量、独立相关词汇",
                            "signature_words": ["事业", "成长", "力量", "独立", "目标"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["行动描写", "内心独白", "成长节点标记"],
                            "avg_length": "中等，20-35字"
                        },
                        "narrative_style": {
                            "perspective": "第一人称女主视角或亲密第三人称",
                            "focus": "自我成长、事业突破、友情与羁绊"
                        },
                        "description_style": "力量感与成长感并重，场景服务于人物发展",
                        "dialogue_style": "自信、果断、有目标感，女性间的互助与竞争",
                        "emotional_expression": "克制但坚定，成就感与自我认同优先"
                    },
                    "examples": ["《游戏入侵》", "《末日乐园》"],
                    "writing_guide": "核心是'女性不需要依附他人也能强大'。事业线和成长线是主线，感情线完全剥离或极度弱化。女主要有清晰的目标和强大的行动力。女性角色之间可以有竞争、有矛盾，但更要有互助和羁绊。成长过程要有挫折，但最终靠自己的力量站起来。避免'女强男弱'的简单反转，要真正展现独立。",
                    "avoid_patterns": ["暗中加入感情线", "女主成长靠男性帮助", "为强而强缺乏真实感", "女性角色脸谱化"]
                },
                {
                    "id": "research_based_transmigration",
                    "name": "考据式穿越",
                    "description": "将穿越文写出严谨的历史感，注重历史细节考证",
                    "features": {
                        "vocabulary": {
                            "word_preference": "历史术语、古代称谓、典章制度词汇",
                            "signature_words": ["据史载", "按制", "古法", "考据", "典籍"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["历史背景说明", "制度解释", "细节考证"],
                            "avg_length": "中等偏长，25-50字，包含考据信息"
                        },
                        "narrative_style": {
                            "perspective": "第三人称限知，穿越者视角",
                            "focus": "历史还原、生存发展、时代逻辑"
                        },
                        "description_style": "严谨的历史细节，服饰、饮食、礼仪都有依据",
                        "dialogue_style": "符合时代特征的对话，穿越者逐渐适应古代语境",
                        "emotional_expression": "对历史的敬畏感，融入时代的成就感"
                    },
                    "examples": ["《新宋》", "《晚明》", "《秦吏》"],
                    "writing_guide": "考据是核心竞争力，每个细节都要有历史依据。穿越者不是'万能现代人'，要受到时代限制。历史逻辑要自洽，不能用现代思维简单解决古代问题。可以适度'金手指'，但必须在合理范围内。时代氛围要浓厚，让读者感受到'真实的古代'。",
                    "avoid_patterns": ["历史常识错误", "穿越者过于全能", "现代思维简单套用", "考据堆砌影响节奏"]
                },
                {
                    "id": "road_trip_narrative",
                    "name": "公路文/公路求生",
                    "description": "以'在路上'的旅行为背景，融合冒险、探索与自我发现",
                    "features": {
                        "vocabulary": {
                            "word_preference": "地理、旅途、风景、生存相关词汇",
                            "signature_words": ["前方", "路途", "未知", "探索", "旅程"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["场景转换", "旅途见闻", "内心感悟"],
                            "avg_length": "中等，20-40字"
                        },
                        "narrative_style": {
                            "perspective": "第一人称或亲密第三人称",
                            "focus": "旅途冒险、人物成长、风景与文化"
                        },
                        "description_style": "壮丽的自然景观与人文风貌，路途中的奇遇",
                        "dialogue_style": "旅途中的相遇与告别，短暂但深刻的交流",
                        "emotional_expression": "孤独与自由的交织，对未知的期待与恐惧"
                    },
                    "examples": ["《迷路无人区》", "《搭车去柏林》"],
                    "writing_guide": "'在路上'是核心体验，每个站点都要有独特的风景和故事。旅途是外在冒险，也是内心成长。遇到的人和事要多样化，展现不同的人生。风景描写要有感染力，让读者向往。节奏要有张有弛，紧张冒险与平静感悟交替。",
                    "avoid_patterns": ["场景重复单调", "只有风景没有故事", "人物成长线断裂", "节奏单一"]
                },
                {
                    "id": "rule_horror",
                    "name": "规则怪谈",
                    "description": "主角身处由'规则'定义的诡异空间，必须通过解读矛盾规则求生",
                    "features": {
                        "vocabulary": {
                            "word_preference": "规则、禁忌、异常、矛盾、推理词汇",
                            "signature_words": ["规则", "禁忌", "违反", "矛盾", "解读"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["规则条文", "推理分析", "危机应对"],
                            "avg_length": "规则句简短有力，推理句中等，20-35字"
                        },
                        "narrative_style": {
                            "perspective": "第一人称，主角视角解谜",
                            "focus": "规则解读、矛盾发现、生存策略"
                        },
                        "description_style": "诡异压抑的氛围，规则与现实的冲突",
                        "dialogue_style": "极少或没有，主要是内心独白和规则分析",
                        "emotional_expression": "恐惧、困惑、发现真相的震撼"
                    },
                    "examples": ["《第二人格[规则怪谈]》", "《我加载了怪谈游戏》"],
                    "writing_guide": "规则设计是核心，要清晰、有逻辑、有矛盾点。恐怖氛围来自'未知'和'规则矛盾'，不是血腥暴力。主角要聪明，通过推理找出规则漏洞。规则要有层次，表面规则和隐藏规则。每次违反规则的后果要严重，制造紧张感。结局可以是逃离、理解或接受规则。",
                    "avoid_patterns": ["规则不清晰", "主角靠运气破解", "恐怖靠血腥堆砌", "矛盾规则无解"]
                },
                {
                    "id": "chinese_cthulhu",
                    "name": "中式克苏鲁",
                    "description": "西方未知恐怖与东方民俗怪谈融合，创造本土化的陌生恐怖体验",
                    "features": {
                        "vocabulary": {
                            "word_preference": "民俗术语、道教词汇、诡异描述词汇",
                            "signature_words": ["诡异", "不可名状", "民俗", "禁忌", "邪祟"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["民俗描述", "诡异现象", "恐惧心理"],
                            "avg_length": "中等偏长，25-45字，营造压抑感"
                        },
                        "narrative_style": {
                            "perspective": "第一人称或限知第三人称",
                            "focus": "未知恐惧、民俗诡异、人性扭曲"
                        },
                        "description_style": "东方美学与恐怖融合，民俗元素营造诡异感",
                        "dialogue_style": "方言、民俗用语，增加本土恐怖感",
                        "emotional_expression": "深层恐惧，对未知的敬畏与绝望"
                    },
                    "examples": ["《道诡异仙》", "《诡秘之主》", "《民俗调查员》"],
                    "writing_guide": "核心是'东方民俗+未知恐怖'。不要简单复制克苏鲁，要深度融合中国传统文化。民俗元素要真实，有考据支撑。恐怖来自'熟悉中的陌生'，日常事物的异化。不可名状的恐惧要通过侧面描写，不要直接描述怪物。人性在恐惧中的扭曲是重要主题。",
                    "avoid_patterns": ["简单复制西方克苏鲁", "民俗元素错误", "恐怖靠血腥", "缺乏文化底蕴"]
                },
                {
                    "id": "cyber_cultivation",
                    "name": "修仙2.0/赛博修仙",
                    "description": "对传统修仙题材的现代化重构，融合现代元素或科幻背景",
                    "features": {
                        "vocabulary": {
                            "word_preference": "修仙术语与现代/科幻词汇混合",
                            "signature_words": ["灵根", "算法", "金丹", "代码", "渡劫", "数据"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["传统修仙场景+现代解释", "科技与修仙的碰撞"],
                            "avg_length": "中等，20-40字"
                        },
                        "narrative_style": {
                            "perspective": "第三人称，跟随主角",
                            "focus": "传统与现代的碰撞、修仙体系的重构"
                        },
                        "description_style": "传统仙侠美学与科幻元素的融合",
                        "dialogue_style": "现代口语与修仙语境的自然融合",
                        "emotional_expression": "对传统的解构与创新，新旧碰撞的张力"
                    },
                    "examples": ["《没钱修什么仙？》", "《赛博剑仙铁雨》", "《修仙大学》"],
                    "writing_guide": "核心是'解构与重构'，不是简单拼贴。要思考修仙体系如果用现代逻辑会怎样。可以有金融修仙、程序员修仙等创意设定。传统修仙的核心要素（境界、功法、法宝）要保留，但表现形式要创新。现代元素的融入要自然，不要生硬。",
                    "avoid_patterns": ["简单拼贴不融合", "失去修仙核心", "现代元素突兀", "设定混乱"]
                },
                {
                    "id": "folk_horror",
                    "name": "民俗灵异",
                    "description": "深耕本土民间传说，营造极具代入感的中式惊悚氛围",
                    "features": {
                        "vocabulary": {
                            "word_preference": "民俗术语、地方方言、灵异描述词汇",
                            "signature_words": ["捞尸", "阴婚", "纸人", "风水", "民俗"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["民俗仪式描写", "灵异事件叙述", "恐惧心理"],
                            "avg_length": "中等，20-40字"
                        },
                        "narrative_style": {
                            "perspective": "第一人称或限知第三人称",
                            "focus": "民俗传统、灵异事件、乡土恐怖"
                        },
                        "description_style": "浓郁的乡土气息与诡异氛围，民俗细节真实",
                        "dialogue_style": "方言对话，增加真实感和地域特色",
                        "emotional_expression": "对传统的敬畏与恐惧，乡土情怀"
                    },
                    "examples": ["《捞尸人》", "《民间诡闻录》", "《乡村志异》"],
                    "writing_guide": "民俗是核心竞争力，要深入挖掘地方传说和民间禁忌。恐怖来自'传统中的未知'，不是西方恐怖元素。乡土气息要浓厚，让读者感受到真实的乡村。民俗仪式要详细描写，有仪式感。人物要接地气，是普通的村民、手艺人。",
                    "avoid_patterns": ["民俗知识错误", "西方恐怖元素混入", "脱离乡土背景", "恐怖靠血腥"]
                },
                {
                    "id": "fourth_disaster",
                    "name": "第四天灾流",
                    "description": "主角将真实世界伪装成游戏，召唤'玩家'实现目标，充满戏剧冲突",
                    "features": {
                        "vocabulary": {
                            "word_preference": "游戏术语与真实世界词汇的对比",
                            "signature_words": ["玩家", "NPC", "版本更新", "主线任务", "第四天灾"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["玩家视角与真实视角的对比", "搞笑互动", "幕后操控"],
                            "avg_length": "中等，20-35字"
                        },
                        "narrative_style": {
                            "perspective": "双视角：幕后主角+玩家群体",
                            "focus": "幕后操控、玩家行为不可预测性、喜剧效果"
                        },
                        "description_style": "游戏界面与真实世界的反差，玩家行为的荒诞",
                        "dialogue_style": "玩家之间的沙雕对话，主角的幕后吐槽",
                        "emotional_expression": "喜剧效果为主，幕后操控的成就感"
                    },
                    "examples": ["《地下城玩家》", "《这游戏也太真实了》", "《我的玩家都是演技派》"],
                    "writing_guide": "核心是'信息差带来的喜剧效果'。玩家不知道这是真实世界，主角在幕后操控。玩家行为要不可预测，经常'跑偏'制造笑点。游戏设定要有趣，任务设计要有创意。真实世界的NPC对玩家行为的反应是重要笑点。节奏要快，喜剧效果要密集。",
                    "avoid_patterns": ["玩家行为可预测", "喜剧效果单一", "幕后主角无趣", "游戏设定无聊"]
                },
                {
                    "id": "evolution_flow",
                    "name": "进化流",
                    "description": "聚焦主角通过基因解锁等方式实现生命层次的'进化'",
                    "features": {
                        "vocabulary": {
                            "word_preference": "生物学术语、进化、基因、变异相关词汇",
                            "signature_words": ["基因", "进化", "解锁", "变异", "生命层次"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["进化过程描写", "能力解锁", "形态变化"],
                            "avg_length": "中等，20-40字"
                        },
                        "narrative_style": {
                            "perspective": "第三人称，跟随主角",
                            "focus": "生命进化、能力成长、生物多样性"
                        },
                        "description_style": "进化过程的详细描写，形态变化的震撼感",
                        "dialogue_style": "科学解释与惊叹的结合",
                        "emotional_expression": "进化的震撼与期待，对生命奥秘的敬畏"
                    },
                    "examples": ["《吞噬星空》", "《全球进化》", "《进化之眼》"],
                    "writing_guide": "进化体系要清晰，让读者知道下一步会进化成什么。每次进化都要有代价或限制，不能无限变强。生物多样性是亮点，可以设计各种奇特的进化路线。科学依据要有一定支撑，不要完全脱离生物学。末日或危机背景能增加紧迫感。",
                    "avoid_patterns": ["进化体系混乱", "无限变强无代价", "缺乏科学依据", "进化过程单调"]
                },
                {
                    "id": "chat_group_flow",
                    "name": "聊天群流",
                    "description": "主角加入跨时空聊天群，与不同世界的成员互动，打破次元壁",
                    "features": {
                        "vocabulary": {
                            "word_preference": "网络聊天用语、各世界特色词汇混合",
                            "signature_words": ["群聊", "红包", "@某人", "跨世界", "次元壁"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["聊天界面", "群友互动", "跨世界交易"],
                            "avg_length": "聊天句简短，叙事句中等，15-30字"
                        },
                        "narrative_style": {
                            "perspective": "第一人称，主角视角",
                            "focus": "群友互动、跨世界交流、资源交换"
                        },
                        "description_style": "聊天界面感的文字呈现，各世界风情展示",
                        "dialogue_style": "网络聊天风格，各角色有独特说话方式",
                        "emotional_expression": "跨世界交流的新奇感，群友间的友情"
                    },
                    "examples": ["《修真聊天群》", "《万界聊天群》", "《我的仙界聊天群》"],
                    "writing_guide": "群友人设要鲜明，每个群友来自不同世界，有独特性格和能力。聊天内容要有趣，信息交流、资源交易、求助互动。跨世界设定要丰富，展现不同世界的风情。主角在群中要有独特价值，不是单纯的旁观者。节奏要轻松愉快，喜剧效果为主。",
                    "avoid_patterns": ["群友人设扁平", "聊天内容无聊", "跨世界设定单一", "主角无参与感"]
                },
                {
                    "id": "sky_screen_flow",
                    "name": "天幕文",
                    "description": "在历史时空中出现向古人直播未来影像的'天幕'，通过历史人物反应制造看点",
                    "features": {
                        "vocabulary": {
                            "word_preference": "历史术语与现代表述的对比",
                            "signature_words": ["天幕", "直播", "古人反应", "未来影像", "历史改变"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["天幕内容展示", "古人反应", "历史影响分析"],
                            "avg_length": "中等，20-40字"
                        },
                        "narrative_style": {
                            "perspective": "双视角：天幕内容+古人反应",
                            "focus": "历史人物对未来的震惊、历史走向的改变"
                        },
                        "description_style": "古今对比的戏剧性场面，历史人物的表情与心理",
                        "dialogue_style": "古人语境下的震惊讨论，现代内容的古代解读",
                        "emotional_expression": "古今碰撞的戏剧性，历史改变的震撼"
                    },
                    "examples": ["《给古人直播未来》", "《天幕降临》"],
                    "writing_guide": "核心是'古今碰撞的戏剧性'。天幕内容要精心选择，能引起古人强烈反应。历史人物的反应要符合其性格和时代背景。历史改变要合理，不能过于突兀。可以展现不同朝代人物的反应，增加多样性。",
                    "avoid_patterns": ["古人反应不符合历史", "天幕内容无聊", "历史改变不合理", "缺乏戏剧冲突"]
                },
                {
                    "id": "anti_cliche",
                    "name": "反套路",
                    "description": "在熟悉的情节上制造陌生化走向，对过度套路化创作的集体反叛",
                    "features": {
                        "vocabulary": {
                            "word_preference": "反讽、解构、打破常规的表述",
                            "signature_words": ["偏偏", "然而", "出乎意料", "不按套路", "反常"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["套路铺垫", "反转打破", "意外展开"],
                            "avg_length": "中等，20-40字"
                        },
                        "narrative_style": {
                            "perspective": "灵活多变，经常打破第四面墙",
                            "focus": "反套路设计、读者预期管理、创新叙事"
                        },
                        "description_style": "传统场景的非传统描写，打破读者预期",
                        "dialogue_style": "角色经常说出'不应该说的话'",
                        "emotional_expression": "意外感和新鲜感，对套路的解构乐趣"
                    },
                    "examples": ["《这个地下城长蘑菇了》", "《反套路修仙》"],
                    "writing_guide": "核心是'打破预期但要合理'。先建立套路预期，然后用合理的方式打破。反转不是为反而反，要有内在逻辑。可以适度打破第四面墙，与读者互动。反套路的目的是创新，不是单纯恶搞。要让读者觉得'意料之外，情理之中'。",
                    "avoid_patterns": ["为反而反不合理", "单纯恶搞无创新", "反转过多失去重点", "失去故事核心"]
                },
                {
                    "id": "short_zhihu_style",
                    "name": "短篇化/知乎风",
                    "description": "适应碎片化阅读，强悬念快节奏，在有限篇幅内迅速击中读者爽点",
                    "features": {
                        "vocabulary": {
                            "word_preference": "简洁有力、直击要点、悬念词汇",
                            "signature_words": ["真相", "反转", "没想到", "结局", "悬念"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["短句为主", "悬念设置", "快速推进"],
                            "avg_length": "偏短，15-25字"
                        },
                        "narrative_style": {
                            "perspective": "第一人称或限知第三人称",
                            "focus": "悬念推进、快速反转、紧凑节奏"
                        },
                        "description_style": "简洁精准，只写关键细节",
                        "dialogue_style": "简短有力，信息密度高",
                        "emotional_expression": "紧张刺激，反转时的震撼"
                    },
                    "examples": ["《鱼灯引魂记》", "知乎盐言故事系列"],
                    "writing_guide": "篇幅短（通常1-3万字），节奏必须快。开篇就要有悬念或冲突，不能有冗长铺垫。每千字至少一个小反转，结尾有大反转。信息密度要高，每句话都要有价值。结尾要有余韵，让读者回味。",
                    "avoid_patterns": ["节奏缓慢", "铺垫过长", "信息密度低", "结尾无力"]
                },
                {
                    "id": "oriental_aesthetics",
                    "name": "东方美学叙事",
                    "description": "回归中国传统文化，深度挖掘东方古典美学、哲学思想、神话体系",
                    "features": {
                        "vocabulary": {
                            "word_preference": "古典文学词汇、哲学概念、诗意表达",
                            "signature_words": ["道", "气", "韵", "意境", "天人合一"]
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["对仗句", "排比句", "诗意长句"],
                            "avg_length": "中等偏长，25-50字"
                        },
                        "narrative_style": {
                            "perspective": "第三人称全知或抒情性叙述者",
                            "focus": "东方哲学、古典美学、文化传承"
                        },
                        "description_style": "充满诗意的意象描写，中国古典美学意境",
                        "dialogue_style": "典雅含蓄，富有哲理",
                        "emotional_expression": "含蓄深远，意境悠长"
                    },
                    "examples": ["《长安十二时辰》", "《鹤唳华亭》", "《琅琊榜》"],
                    "writing_guide": "核心是'东方美学的现代表达'。深入理解中国古典哲学和美学，不是表面堆砌。诗词歌赋要自然融入，不要生硬引用。意境营造比情节推进更重要。人物要有文人气质，行为符合传统道德。场景描写要像中国画，留白与意境并重。",
                    "avoid_patterns": ["表面堆砌古典元素", "理解错误的传统文化", "意境空洞", "与现代脱节"]
                }
            ]
        },
        "narrative": {
            "name": "语言叙事特色",
            "description": "独特的语言风格和叙事技巧",
            "styles": [
                {
                    "id": "poetic_prose",
                    "name": "诗化/散文化",
                    "description": "语言具有诗歌的节奏和意象，叙事与抒情融合",
                    "features": {
                        "vocabulary": {
                            "word_preference": "意象丰富、音韵和谐的词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["跨行的意象延伸", "音韵节奏的控制", "意象并置"]
                        },
                        "narrative_style": {
                            "perspective": "抒情性的叙述者",
                            "focus": "感官体验、内心感受、时间与记忆"
                        },
                        "description_style": "意象叠加，制造诗意效果",
                        "dialogue_style": "少，且具有诗意",
                        "emotional_expression": "通过意象和节奏传达，非直接表达"
                    },
                    "examples": ["《呼兰河传》", "《湖光山色》", "川端康成"],
                    "writing_guide": "每个句子都要有节奏感，读出来像诗。意象要精准而独特，避免陈词滥调。情感通过意象传达，不直接说喜悦或悲伤。段落之间要有呼吸的空间。",
                    "avoid_patterns": ["直白的情感叙述", "信息性的功能语言", "快节奏情节", "缺乏意象"]
                },
                {
                    "id": "dramatic",
                    "name": "戏剧化",
                    "description": "强烈的冲突、高潮迭起、场景感极强",
                    "features": {
                        "vocabulary": {
                            "word_preference": "动作性强、情绪强烈的词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["行动句", "对话推动", "高潮堆叠"]
                        },
                        "narrative_style": {
                            "perspective": "戏剧化的全知视角",
                            "focus": "冲突、转折、情感爆发"
                        },
                        "description_style": "场景如舞台，有强烈的视觉感",
                        "dialogue_style": "充满冲突和情绪张力",
                        "emotional_expression": "直接、强烈、不加掩饰"
                    },
                    "examples": ["狄更斯", "雨果", "大仲马"],
                    "writing_guide": "每个场景都要有戏剧性的高点。对话推动冲突，每句话都让情况变化。情感要强烈，读者要能感受到人物的激情。转折要出人意料但在情理之中。",
                    "avoid_patterns": ["平淡叙事", "缺乏冲突", "情绪平稳", "节奏拖沓"]
                },
                {
                    "id": "humorous",
                    "name": "幽默风趣",
                    "description": "以轻松幽默的方式讲故事，笑中有泪有思考",
                    "features": {
                        "vocabulary": {
                            "word_preference": "轻松活泼、带有幽默感的词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["意外的转折", "自嘲式叙述", "荒诞的类比"]
                        },
                        "narrative_style": {
                            "perspective": "亲切有趣的第一或第三人称",
                            "focus": "生活的荒诞，人性的可爱与可笑"
                        },
                        "description_style": "以轻松笔调写严肃事，反差制造幽默",
                        "dialogue_style": "机智、出人意料、有包袱",
                        "emotional_expression": "轻盈，但深处有温情或思考"
                    },
                    "examples": ["钱钟书", "汪曾祺部分", "王朔", "周星驰式"],
                    "writing_guide": "幽默要有智识含量，不只是搞笑。反差是幽默的来源：用严肃写荒诞，用轻巧写沉重。不要解释笑点，如果需要解释就不好笑了。自嘲比嘲人更有力量。",
                    "avoid_patterns": ["解释笑点", "用力过猛", "低俗笑点", "全程搞笑无深度"]
                },
                {
                    "id": "suspense_thriller",
                    "name": "悬疑惊悚",
                    "description": "节奏紧张、悬念迭出、恐惧与不安的叙事氛围",
                    "features": {
                        "vocabulary": {
                            "word_preference": "紧张感词汇、感官刺激描写、不安的预兆"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["短句制造紧张", "悬念段落末尾", "信息的逐步揭示"]
                        },
                        "narrative_style": {
                            "perspective": "不可靠叙述者，或信息不完整的受害者视角",
                            "focus": "谜题、危险、心理压力"
                        },
                        "description_style": "感官细节强化恐惧，环境映射心理",
                        "dialogue_style": "充满张力，信息不对等",
                        "emotional_expression": "恐惧、偏执、紧迫感"
                    },
                    "examples": ["希区柯克式叙事", "斯蒂芬·金", "东野圭吾"],
                    "writing_guide": "紧张感靠节奏控制。短句加快心跳。每章结尾要有悬念。恐惧的来源要清晰，但揭示要缓慢。不可靠叙述者让读者质疑一切。",
                    "avoid_patterns": ["过早揭示谜底", "节奏松弛", "平淡场景", "突然的解决"]
                },
                {
                    "id": "lyrical_realism",
                    "name": "抒情现实主义",
                    "description": "现实题材与抒情笔法结合，有温度的社会书写",
                    "features": {
                        "vocabulary": {
                            "word_preference": "生活化但有温度的词汇"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["细节描写与情感融合", "回忆与现在穿插"]
                        },
                        "narrative_style": {
                            "perspective": "亲近的叙述者，有情感立场但不失客观",
                            "focus": "普通人的生活、情感、命运"
                        },
                        "description_style": "有温度的生活场景，细节承载情感",
                        "dialogue_style": "生活化，揭示人物性格和关系",
                        "emotional_expression": "克制而深情，在日常中蕴含深情"
                    },
                    "examples": ["《平凡的世界》", "《白鹿原》部分风格", "铁凝"],
                    "writing_guide": "现实是骨架，抒情是血肉。用细节传达温情，用普通人的挣扎揭示时代。不回避困境，但要有人性的温暖。语言要有质感，接地气又不失诗意。",
                    "avoid_patterns": ["过于冷酷", "过于浪漫化", "脱离现实", "情感廉价"]
                },
                {
                    "id": "epistolary",
                    "name": "书信/日记体",
                    "description": "通过书信、日记等私人文本构建叙事",
                    "features": {
                        "vocabulary": {
                            "word_preference": "私人化、有强烈个人色彩的表达"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["第一人称私密叙述", "时间标注", "情绪化的表达"]
                        },
                        "narrative_style": {
                            "perspective": "写信/日记者的主观视角",
                            "focus": "内心独白、人际关系、私人事件"
                        },
                        "description_style": "像真实的私人记录，细节真实",
                        "dialogue_style": "引用对话而非呈现对话",
                        "emotional_expression": "直接、私密、毫无防御"
                    },
                    "examples": ["《少年维特之烦恼》", "《达洛维夫人日记》"],
                    "writing_guide": "真实感是关键，要让读者相信这是真实的私人文本。叙述者是不完全可靠的，有自我欺骗和认知局限。时间标注要有规律但也有间隔，体现生活节奏。",
                    "avoid_patterns": ["过于文学化的表达", "全知视角", "完美的叙述", "脱离私人感"]
                },
                {
                    "id": "multiple_perspective",
                    "name": "多视角叙事",
                    "description": "不同人物视角轮换，呈现事件的多面性",
                    "features": {
                        "vocabulary": {
                            "word_preference": "每个视角人物有自己的语言特色"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["视角切换时的风格变化", "同一事件的不同呈现"]
                        },
                        "narrative_style": {
                            "perspective": "多个第一或第三限知视角",
                            "focus": "真相的多元性、人物理解的局限"
                        },
                        "description_style": "同一场景从不同角度描写",
                        "dialogue_style": "每个人对同一对话有不同理解",
                        "emotional_expression": "每个视角人物的情感都真实但可能偏颇"
                    },
                    "examples": ["《喧哗与骚动》", "《了不起的盖茨比》部分", "《云图》"],
                    "writing_guide": "每个视角人物要有明显不同的声音和关注点。同一事件从不同视角呈现时，要有新信息或新理解，而不只是重复。视角切换要让读者适应，可以用章节标题标注。",
                    "avoid_patterns": ["所有视角声音相同", "视角切换无意义", "信息重复而无新意", "视角人物不够立体"]
                },
                {
                    "id": "oral_storytelling",
                    "name": "口语化/说书体",
                    "description": "模拟口头讲述的叙事，亲切有趣，节奏生动",
                    "features": {
                        "vocabulary": {
                            "word_preference": "口语词汇，俚语，习语"
                        },
                        "sentence_structure": {
                            "preferred_patterns": ["说书腔调", "直接对读者说话", "口语节奏"]
                        },
                        "narrative_style": {
                            "perspective": "说书人视角，直接与读者互动",
                            "focus": "故事的趣味性，读者的代入感"
                        },
                        "description_style": "生动活泼，有声有色",
                        "dialogue_style": "原汁原味的口语对话",
                        "emotional_expression": "直接、热情、和读者共情"
                    },
                    "examples": ["《水浒传》", "金庸部分章节", "冯骥才"],
                    "writing_guide": "像在给朋友讲故事一样写。可以直接对读者说'话说……''且听下回分解'。节奏要有起伏，高潮处加快，舒缓处放慢。语言要活泼，不要书卷气。",
                    "avoid_patterns": ["书面语过重", "与读者距离感", "节奏单一", "缺乏临场感"]
                }
            ]
        }
    }
}


def get_style_by_id(style_id: str) -> Optional[Dict]:
    """根据ID获取文风详情"""
    for category in STYLE_LIBRARY["categories"].values():
        for style in category["styles"]:
            if style["id"] == style_id:
                return style
    return None


def get_styles_by_category(category: str) -> List[Dict]:
    """获取分类下的所有文风"""
    if category in STYLE_LIBRARY["categories"]:
        return STYLE_LIBRARY["categories"][category]["styles"]
    return []


def get_all_categories() -> Dict:
    """获取所有分类信息（不含具体风格数据）"""
    result = {}
    for cat_id, cat_data in STYLE_LIBRARY["categories"].items():
        result[cat_id] = {
            "name": cat_data["name"],
            "description": cat_data["description"],
            "count": len(cat_data["styles"])
        }
    return result


def build_style_guide(style_ids: List[str], intensity: float = 0.7) -> Dict:
    """
    构建风格指南（支持多风格融合）

    Args:
        style_ids: 风格ID列表（最多3个）
        intensity: 风格强度(0.0-1.0)

    Returns:
        融合后的风格指南字典
    """
    if not style_ids:
        return {}

    # 限制最多3个风格
    style_ids = style_ids[:3]

    styles = []
    for sid in style_ids:
        style = get_style_by_id(sid)
        if style:
            styles.append(style)

    if not styles:
        return {}

    # 单风格
    if len(styles) == 1:
        style = styles[0]
        return {
            "style_names": [style["name"]],
            "style_ids": style_ids,
            "intensity": intensity,
            "writing_guide": style["writing_guide"],
            "style_features": style["features"],
            "avoid_patterns": style["avoid_patterns"],
            "examples": style["examples"],
            "description": style["description"]
        }

    # 多风格融合
    # 主风格占60%，其余各占20%（如有2个辅风格则各占20%）
    weights = [0.6] + [0.4 / (len(styles) - 1)] * (len(styles) - 1)

    style_names = [s["name"] for s in styles]

    # 合并写作指南
    combined_guide_parts = []
    for i, (style, weight) in enumerate(zip(styles, weights)):
        if i == 0:
            combined_guide_parts.append(
                f"**主风格 - {style['name']}**（权重{int(weight*100)}%）：\n{style['writing_guide']}")
        else:
            combined_guide_parts.append(
                f"**辅风格 - {style['name']}**（权重{int(weight*100)}%）：\n{style['writing_guide']}")

    combined_guide = "\n\n".join(combined_guide_parts)

    # 合并避免模式（去重）
    all_avoid = []
    for style in styles:
        for pattern in style.get("avoid_patterns", []):
            if pattern not in all_avoid:
                all_avoid.append(pattern)

    # 检查风格兼容性
    compatibility_warnings = _check_style_compatibility(styles)

    return {
        "style_names": style_names,
        "style_ids": style_ids,
        "intensity": intensity,
        "writing_guide": combined_guide,
        "style_features": styles[0]["features"],  # 主风格特征为主
        "avoid_patterns": all_avoid,
        "examples": styles[0]["examples"],
        "description": f"融合风格：{'、'.join(style_names)}",
        "compatibility_warnings": compatibility_warnings
    }


def apply_style_to_project_metadata(project_metadata: Dict, style_ids: List[str], intensity: float = 0.7) -> Dict:
    """将文风配置应用到项目元数据中

    Args:
        project_metadata: 项目元数据字典
        style_ids: 文风ID列表
        intensity: 风格强度(0.0-1.0)

    Returns:
        更新后的项目元数据
    """
    if not style_ids:
        return project_metadata

    # 构建风格指南
    style_guide = build_style_guide(style_ids, intensity)
    if not style_guide:
        return project_metadata

    # 保存到项目元数据
    project_metadata["writing_styles"] = style_ids
    project_metadata["style_intensity"] = intensity
    project_metadata["style_library_guide"] = style_guide

    return project_metadata


def get_style_guide_from_project(project_metadata: Dict) -> Optional[Dict]:
    """从项目元数据中获取文风配置

    Args:
        project_metadata: 项目元数据字典

    Returns:
        style_library_guide字典,如果没有则返回None
    """
    return project_metadata.get("style_library_guide")


def _check_style_compatibility(styles: List[Dict]) -> List[str]:
    """检查风格兼容性"""
    warnings = []
    style_ids = [s["id"] for s in styles]

    # 已知不兼容的组合
    incompatible_pairs = [
        ("minimalism_lit", "romanticism", "极简主义与浪漫主义在语言密度上存在冲突，建议降低两者强度各50%"),
        ("stream_of_consciousness", "detective_classic", "意识流与古典侦探的逻辑性要求相互矛盾"),
        ("oral_storytelling", "modernism", "口语说书体与现代主义的破碎叙事难以融合"),
    ]

    for id1, id2, warning in incompatible_pairs:
        if id1 in style_ids and id2 in style_ids:
            warnings.append(warning)

    return warnings


def format_style_for_prompt(style_guide: Dict) -> str:
    """将风格指南格式化为提示词文本"""
    if not style_guide:
        return ""

    parts = []

    style_names = style_guide.get("style_names", [])
    if style_names:
        parts.append(f"**写作风格**: {'、'.join(style_names)}")

    description = style_guide.get("description", "")
    if description:
        parts.append(f"**风格简介**: {description}")

    intensity = style_guide.get("intensity", 0.7)
    intensity_desc = "淡入" if intensity < 0.4 else (
        "强烈" if intensity > 0.8 else "适中")
    parts.append(f"**风格强度**: {intensity_desc}({int(intensity * 100)}%)")

    # 核心特征
    features = style_guide.get("style_features", {})
    if features:
        parts.append("\n**核心风格特征**:")

        vocab = features.get("vocabulary", {})
        if vocab.get("word_preference"):
            parts.append(f"- 用词偏好: {vocab['word_preference']}")
        if vocab.get("avoid"):
            avoids = vocab["avoid"] if isinstance(
                vocab["avoid"], list) else [vocab["avoid"]]
            parts.append(f"- 避免用词: {', '.join(avoids)}")

        sentence = features.get("sentence_structure", {})
        if sentence.get("preferred_patterns"):
            parts.append(
                f"- 句式偏好: {', '.join(sentence['preferred_patterns'])}")
        if sentence.get("avg_length"):
            parts.append(f"- 句子长度: {sentence['avg_length']}")

        narrative = features.get("narrative_style", {})
        if narrative.get("perspective"):
            parts.append(f"- 叙事视角: {narrative['perspective']}")
        if narrative.get("focus"):
            parts.append(f"- 叙事重点: {narrative['focus']}")

        if features.get("description_style"):
            parts.append(f"- 描写风格: {features['description_style']}")

        if features.get("dialogue_style"):
            parts.append(f"- 对话风格: {features['dialogue_style']}")

        if features.get("emotional_expression"):
            parts.append(f"- 情感表达: {features['emotional_expression']}")

    # 写作指南
    writing_guide = style_guide.get("writing_guide", "")
    if writing_guide:
        parts.append(f"\n**写作指导**:\n{writing_guide}")

    # 避免模式
    avoid_patterns = style_guide.get("avoid_patterns", [])
    if avoid_patterns:
        parts.append(f"\n**必须避免**:\n" +
                     "\n".join(f"- {p}" for p in avoid_patterns))

    # 兼容性警告
    warnings = style_guide.get("compatibility_warnings", [])
    if warnings:
        parts.append(f"\n**风格融合注意事项**:\n" +
                     "\n".join(f"⚠️ {w}" for w in warnings))

    return "\n".join(parts)


def get_style_list_for_api(category: Optional[str] = None) -> List[Dict]:
    """获取文风列表（用于API返回，简化版）"""
    result = []

    categories_to_fetch = [category] if category else list(
        STYLE_LIBRARY["categories"].keys())

    for cat_id in categories_to_fetch:
        if cat_id not in STYLE_LIBRARY["categories"]:
            continue
        cat_data = STYLE_LIBRARY["categories"][cat_id]
        for style in cat_data["styles"]:
            result.append({
                "id": style["id"],
                "name": style["name"],
                "description": style["description"],
                "category": cat_id,
                "category_name": cat_data["name"],
                "examples": style.get("examples", [])
            })

    return result
