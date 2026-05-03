/**
 * 剧集风格选择器数据
 * 数据来源：长篇电视剧艺术风格全景一览表.md + 网络短剧风格流派.md
 * 按类型分为两大类：长篇电视剧、网络短剧
 * 每类包含：风格流派、导演风格、叙事风格、镜头剪辑风格、演绎风格等维度
 */

// ==================== 长篇电视剧数据 ====================

export const longSeriesDimensions = [
  {
    id: 'genre',
    name: '风格流派',
    description: '长篇电视剧的类型流派（按国别分类）',
    styles: [
      // 中国
      { id: 'cn_spy', name: '谍战剧 [中]', description: '以卧底、潜伏、情报战为主要情节，充满悬疑、智斗和反转，常置于特定历史背景中。', examples: ['《潜伏》《伪装者》《风筝》'], country: '中' },
      { id: 'cn_military', name: '军旅剧 [中]', description: '以军人生活、军事训练、战争为主要内容，弘扬爱国主义和英雄主义精神。', examples: ['《士兵突击》《我的团长我的团》《亮剑》'], country: '中' },
      { id: 'cn_historical', name: '历史正剧 [中]', description: '遵循"大事不虚，小事不拘"原则，展现特定历史时期的重大事件和人物，风格厚重、严肃。', examples: ['《大明王朝1566》《雍正王朝》《汉武大帝》'], country: '中' },
      { id: 'cn_family_saga', name: '家族剧 [中]', description: '以一个或几个家族的兴衰沉浮为主线，折射时代变迁与社会百态，叙事格局宏大。', examples: ['《大宅门》《白鹿原》《乔家大院》'], country: '中' },
      { id: 'cn_family_ethics', name: '家庭伦理剧 [中]', description: '聚焦普通家庭的婚姻、情感、代际关系，贴近现实生活，引发观众共鸣。', examples: ['《金婚》《父母爱情》《都挺好》'], country: '中' },
      { id: 'cn_urban_romance', name: '都市情感剧 [中]', description: '以都市生活为背景，描写现代人的爱情、友情、职场与生活困境，风格时尚、轻快。', examples: ['《欢乐颂》《三十而已》《装腔启示录》'], country: '中' },
      { id: 'cn_medical', name: '医疗剧 [中]', description: '以医院为背景，展现医护人员的职业挑战与人文关怀，情节专业，节奏紧张。', examples: ['《白色巨塔》《实习医生格蕾》'], country: '中' },
      { id: 'cn_sitcom', name: '情景喜剧 [中]', description: '场景固定，角色固定，每集故事相对独立，以幽默对话和夸张表演制造笑点。', examples: ['《我爱我家》《武林外传》'], country: '中' },
      { id: 'cn_wuxia', name: '武侠剧/古装传奇剧 [中]', description: '以江湖恩怨、侠义精神或古代传奇人物为叙事核心，融合动作、爱情等元素。', examples: ['《射雕英雄传》《天龙八部》《琅琊榜》'], country: '中' },
      { id: 'cn_rural', name: '农村剧 [中]', description: '反映农村生活、农民问题与乡村变革，风格朴实，具有浓郁的地域特色。', examples: ['《山海情》《乡村爱情》'], country: '中' },
      { id: 'cn_avant_garde', name: '网络自制剧/先锋剧 [中]', description: '打破传统类型边界，在叙事、美学上进行大胆探索，风格独特，极具导演个人色彩。', examples: ['《漫长的季节》《平原上的摩西》《欢颜》'], country: '中' },
      // 美国
      { id: 'us_procedural', name: '程序剧 [美]', description: '结构高度模式化，遵循"罪案发生-调查取证-抓获罪犯"的流程，每集独立成篇。', examples: ['《犯罪现场调查》《法律与秩序》'], country: '美' },
      { id: 'us_anthology', name: '诗选剧 [美]', description: '每季讲述一个完整独立的故事，拥有全新的角色和设定，品质极高。', examples: ['《冰血暴》《真探》《美国恐怖故事》'], country: '美' },
      { id: 'us_miniseries', name: '迷你剧 [美]', description: '篇幅极短，一季讲述一个完整、闭合的故事，叙事紧凑，制作精良。', examples: ['《兄弟连》《切尔诺贝利》'], country: '美' },
      // 英国
      { id: 'uk_literary', name: '文学改编 [英]', description: '忠于或创新性地改编经典文学作品，台词考究，戏剧结构严谨，常有浓厚的书卷气。', examples: ['BBC版《傲慢与偏见》《神探夏洛克》'], country: '英' },
      { id: 'uk_political_satire', name: '政治讽刺喜剧 [英]', description: '以冷幽默和辛辣的讽刺手法，揭露和批判官僚体制与政治乱象。', examples: ['《是，大臣》《是，首相》'], country: '英' },
      { id: 'uk_period_drama', name: '时代剧 [英]', description: '制作精良，从服装、道具到社会风貌都力求精确还原特定历史时期。', examples: ['《唐顿庄园》'], country: '英' },
      { id: 'uk_scifi', name: '科幻寓言 [英]', description: '设定在近未来或平行时空，通过高度概念化的科技故事探讨人性与伦理。', examples: ['《黑镜》'], country: '英' },
      // 日本
      { id: 'jp_taiga', name: '大河剧 [日]', description: '以日本历史人物或家族为主轴的长篇电视剧，叙事宏大，兼具史诗感与戏剧性。', examples: ['《葵 德川三代》《真田丸》'], country: '日' },
      { id: 'jp_morning', name: '晨间剧 [日]', description: '多为励志故事，以坚韧的女性为主角，基调积极向上，叙事平稳而细腻。', examples: ['《阿信》《海女》'], country: '日' },
      { id: 'jp_trendy', name: '趋势剧 [日]', description: '紧跟社会热点，题材广泛，情感细腻，是日剧中最主流的类型。', examples: ['《东京爱情故事》《悠长假期》'], country: '日' },
      { id: 'jp_social', name: '社会派剧集 [日]', description: '深入探讨当代社会的顽疾和争议性议题，反映现实，引人深思。', examples: ['《半泽直树》《非自然死亡》'], country: '日' },
      { id: 'jp_healing', name: '治愈系 [日]', description: '节奏舒缓，通过描绘日常生活中的温情瞬间达到温暖人心、抚慰情感的效果。', examples: ['《深夜食堂》《面包和汤和猫咪好天气》'], country: '日' },
      // 韩国
      { id: 'kr_family', name: '家庭剧 [韩]', description: '围绕家庭成员之间的亲情、爱情和矛盾展开，情节贴近生活，篇幅较长。', examples: ['《澡堂老板家的男人们》《请回答1988》'], country: '韩' },
      { id: 'kr_historical', name: '古装剧 [韩]', description: '涵盖严肃史剧和"Fusion史剧"，服饰华丽，画面精美。', examples: ['《大长今》《拥抱太阳的月亮》'], country: '韩' },
      { id: 'kr_romance', name: '爱情偶像剧 [韩]', description: '以青年男女的爱情为主线，营造浪漫唯美的梦幻感。', examples: ['《来自星星的你》《太阳的后裔》'], country: '韩' },
      { id: 'kr_revenge', name: '复仇爽剧 [韩]', description: '以"以恶治恶"为设定，剧情反转密集，节奏明快，让观众获得情绪宣泄。', examples: ['《黑暗荣耀》《顶楼》'], country: '韩' },
      { id: 'kr_survival', name: '生存/博弈剧 [韩]', description: '设定极端环境中的生存博弈，深挖社会阶层与人性百态。', examples: ['《鱿鱼游戏》'], country: '韩' }
    ]
  },
  {
    id: 'director',
    name: '导演风格',
    description: '电视剧导演的独特个人风格',
    styles: [
      { id: 'dir_auteur', name: '"作者化"风格 [中]', description: '导演在影像美学、故事风格和主题演绎上具有鲜明的个人印记，甚至实现编导合一。', examples: ['辛爽（《漫长的季节》）、张大磊（《平原上的摩西》）'] },
      { id: 'dir_realistic', name: '现实/纪实风格 [中]', description: '追求真实感，淡化戏剧冲突，镜头语言冷静克制。', examples: ['《人世间》'] },
      { id: 'dir_commercial', name: '商业/类型化风格 [中]', description: '精准把握市场脉搏，熟练运用类型剧的叙事公式，追求强情节、快节奏。', examples: ['刘江（《媳妇的美好时代》《咱们结婚吧》）'] },
      { id: 'dir_classic', name: '"正剧"品格 [中]', description: '力求赋予作品厚重的质感、深刻的主题和严谨的制作。', examples: ['孔笙（《父母爱情》《山海情》）'] },
      { id: 'dir_crossover', name: '"跨界"导演风格 [中]', description: '电影导演跨界执导电视剧，带来电影化的视听语言和审美标准。', examples: ['张大磊（《平原上的摩西》）'] },
      { id: 'dir_tech', name: '技术流风格 [中]', description: '高度注重镜头语言、剪辑手法和场面调度的创新性与实验性。', examples: ['辛爽（《漫长的季节》）、阿方索·卡隆（《免责声明》）'] },
      { id: 'dir_showrunner', name: '主导创作者体系 [美]', description: '整季或整剧由一位主导创作者统一把控，追求文学式的深度、氛围和主题连贯性。', examples: ['尼克·皮佐拉托（《真探》第一季）'] }
    ]
  },
  {
    id: 'narrative',
    name: '叙事风格',
    description: '剧集叙事结构与手法',
    styles: [
      { id: 'nar_chronological', name: '编年体叙事 [中]', description: '按照时间顺序，以"一年一集"的方式讲述故事。', examples: ['《金婚》'] },
      { id: 'nar_multi_protagonist', name: '"组合式"/"抽屉式"叙事 [中]', description: '以多位人物为主角，从多个角度展现社会图景，结构清晰。', examples: ['《欢乐颂》《小别离》'] },
      { id: 'nar_emotional', name: '"情绪叙事"/"生活流" [中]', description: '弱化戏剧性的强情节，注重氛围感营造和人物内心世界开掘。', examples: ['《平原上的摩西》'] },
      { id: 'nar_storm', name: '"风暴式"叙事 [中]', description: '打破舒缓的线性节奏，开篇即抛出核心事件，通过密集的矛盾冲突吸引观众。', examples: ['《生万物》'] },
      { id: 'nar_nonlinear', name: '非线性/多线叙事 [中/美]', description: '运用倒叙、插叙、闪回等手法，打乱时间线，制造悬念，深化主题。', examples: ['《漫长的季节》《迷失》《西部世界》'] },
      { id: 'nar_road', name: '公路片叙事 [中]', description: '以一段旅程作为故事主线，主角在路途中获得成长或感悟。', examples: ['《欢颜》'] },
      { id: 'nar_serial', name: '连续性/系列剧叙事 [中/美]', description: '连续性叙事：故事线连续发展；系列剧叙事：每集故事相对独立。', examples: ['《人世间》(连续性)；《老友记》(系列剧)'] },
      { id: 'nar_antihero', name: '反英雄叙事 [美]', description: '以道德上存在缺陷的角色作为核心主角，深入挖掘人性的复杂性。', examples: ['《黑道家族》《绝命毒师》'] },
      { id: 'nar_fast_paced', name: '快节奏叙事 [美]', description: '剧情推进迅速，反转不断，通常在每集或每几分钟内就有一个小高潮。', examples: ['《24小时》《越狱》'] },
      { id: 'nar_slow_burn', name: '慢热型叙事 [美]', description: '节奏平缓，更注重氛围的营造、人物内心世界的挖掘和细节的铺陈。', examples: ['《风骚律师》《冰血暴》'] },
      { id: 'nar_novelistic', name: '小说式电视 [美]', description: '整季围绕一个核心主题展开，追求文学式的深度和主题连贯性。', examples: ['《真探》（第一季）'] },
      { id: 'nar_three_unities', name: '"三一律"式叙事 [英]', description: '在时间和空间上高度集中，矛盾冲突强烈，剧情紧凑，张力十足。', examples: ['《罪恶之家》'] },
      { id: 'nar_episodic', name: '单元式叙事 [日]', description: '一集或几集解决一个事件，同时主线人物的故事作为暗线贯穿始终。', examples: ['《胜者即是正义》《非自然死亡》'] },
      { id: 'nar_manzai', name: '"漫才"式喜剧风格 [日]', description: '大量使用夸张的表情、肢体动作和快速、无厘头的对白。', examples: ['福田雄一（《我是大哥大》）'] },
      { id: 'nar_kr_old', name: '"旧三宝"悲情叙事 [韩]', description: '依赖"车祸、癌症、治不好"等极端情节来制造戏剧冲突和悲剧感。', examples: ['《蓝色生死恋》《天国的阶梯》'] },
      { id: 'nar_kr_new', name: '"新三宝"时尚叙事 [韩]', description: '主打"长腿、养眼、土豪"，以高颜值演员和时尚造型为卖点。', examples: ['《继承者们》'] }
    ]
  },
  {
    id: 'cinematography',
    name: '镜头剪辑风格',
    description: '摄影与剪辑风格',
    styles: [
      { id: 'cine_filmic', name: '电影化镜头语言 [中/美]', description: '运用复杂的场面调度、精美的构图和富有设计感的镜头运动。', examples: ['《长安十二时辰》《权力的游戏》'] },
      { id: 'cine_long_take', name: '长镜头/一镜到底 [中/英]', description: '使用时间较长的单镜头完成叙事，增强观众的沉浸感和现场感。', examples: ['《漫长的季节》《Adolescence》'] },
      { id: 'cine_handheld', name: '手持摄影风格 [中/美]', description: '通过手持摄影带来的晃动感，营造紧张、不安、纪实或真实的第一视角感受。', examples: ['《微暗之火》《无耻之徒》'] },
      { id: 'cine_fast_cut', name: '快节奏/凌厉剪辑 [中]', description: '使用大量短镜头和高频剪辑，制造紧张、兴奋的观感。', examples: ['《暗夜行者》'] },
      { id: 'cine_poetic', name: '时空叠加式/诗意剪辑 [中]', description: '通过跳跃、非连贯的剪辑方式连接不同时空的镜头，创造象征、隐喻或诗意的表达。', examples: ['《平原上的摩西》'] },
      { id: 'cine_mtv', name: '"MTV式"视觉语言 [美]', description: '将音乐录像带中的快速剪辑、动感镜头、风格化色彩等技巧融入电视剧。', examples: ['丹尼·博伊尔（《手枪》）'] },
      { id: 'cine_mockumentary', name: '伪纪录片风格 [美]', description: '采用手持摄影、直接对观众说话等纪录片拍摄手法，模拟非虚构的真实感。', examples: ['《摩登家庭》《办公室》'] },
      { id: 'cine_dark', name: '黑暗/不饱和色调 [美]', description: '使用去饱和的色彩，营造压抑、冷峻或严肃的氛围。', examples: ['大卫·芬奇（《心灵猎人》）、剧集《雷普利》'] },
      { id: 'cine_vibrant', name: '艳丽/极繁主义 [美]', description: '画面色彩饱和、光线明快，创造出充满活力和视觉冲击力的影像世界。', examples: ['《亢奋》'] },
      { id: 'cine_classical', name: '古典构图 [英]', description: '镜头语言工整、精致，构图严谨考究，充满古典绘画般的美感。', examples: ['《唐顿庄园》'] },
      { id: 'cine_precise', name: '精准的戏剧节奏 [英]', description: '剪辑服务于剧情和人物，节奏张弛有度，精准控制观众的情绪。', examples: ['BBC剧集普遍风格'] },
      { id: 'cine_aesthetic', name: '唯美主义视觉 [日]', description: '注重画面构图、色彩和光影，擅长通过唯美的画面营造浪漫或清新氛围。', examples: ['冢原亚由子（《为了N》《最爱》）'] },
      { id: 'cine_anime', name: '视觉系/漫改风格 [日]', description: '忠实于漫画原作的视觉风格，妆造、场景、分镜高度还原。', examples: ['《交响情人梦》《银魂》'] },
      { id: 'cine_smooth', name: '平稳连续性剪辑 [日]', description: '剪辑服务于舒缓的叙事节奏，追求自然、流畅的观影体验。', examples: ['多数治愈系和家庭剧'] },
      { id: 'cine_romantic', name: '浪漫主义镜头语言 [韩]', description: '大量运用柔光、慢镜头、浅景深、多机位拍摄等手段营造唯美氛围。', examples: ['普遍存在于爱情题材韩剧中'] },
      { id: 'cine_emotional_mv', name: '情绪化/音乐MV式剪辑 [韩]', description: '根据背景音乐的节奏和情感进行剪辑，配合特写和慢镜头放大角色内心感受。', examples: ['普遍存在于爱情题材韩剧中'] }
    ]
  },
  {
    id: 'performance',
    name: '演绎风格',
    description: '演员表演方法与风格',
    styles: [
      { id: 'perf_life_flow', name: '生活流演技 [中]', description: '表演风格极度贴近生活，细腻自然，消解表演痕迹。', examples: ['孙千（年代剧）、董勇'] },
      { id: 'perf_theatrical', name: '"戏剧感"演技 [中]', description: '表演风格外放、夸张，带有明显的舞台痕迹，角色塑造更符号化。', examples: ['关晓彤（部分作品）'] },
      { id: 'perf_method', name: '方法派演技 [中/美]', description: '演员深度体验角色情感，力求与角色"合二为一"，表演极具爆发力和真实感。', examples: ['范伟（《漫长的季节》）、马修·麦康纳（《真探》）'] },
      { id: 'perf_signature', name: '标签化/个人符号式演绎 [中/韩]', description: '表演带有强烈的个人特质或习惯性表演方式，形成独特的"流派"和观众辨识度。', examples: ['黄晓明、各类"霸道总裁""灰姑娘"形象'] },
      { id: 'perf_crazy', name: '"疯批"式演绎 [中]', description: '通过极端的情绪、夸张的言行或偏离常规的行为来塑造角色，充满颠覆性和戏剧张力。', examples: ['《欢颜》'] },
      { id: 'perf_realistic_ensemble', name: '写实主义群像 [美]', description: '表演风格自然、生活化，强调用细腻的肢体语言和台词展现人物的真实状态。', examples: ['《火线》'] },
      { id: 'perf_shakespearean', name: '莎剧式演绎 [英]', description: '台词功底扎实，肢体语言和声音控制极具张力，富有戏剧感染力。', examples: ['《空王冠》系列'] },
      { id: 'perf_stage', name: '舞台剧式表演 [日]', description: '表演更具戏剧性，台词功底扎实，部分表演可能在镜头前显得夸张。', examples: ['部分舞台剧演员参与的日剧'] },
      { id: 'perf_kr_realistic', name: '写实主义演绎 [韩]', description: '追求贴近生活的真实感，表演风格细腻自然，尤其在长篇家庭剧中。', examples: ['《请回答1988》'] }
    ]
  }
]

// ==================== 网络短剧数据 ====================

export const shortSeriesDimensions = [
  {
    id: 'genre',
    name: '风格流派（1.0时代）',
    description: '网络短剧经典类型流派',
    styles: [
      { id: 'ss_god_of_war', name: '战神/龙王流', description: '主角隐姓埋名却身怀绝技，被羞辱后亮明身份打脸全场。核心公式：压制的张力 + 身份揭晓的爽感爆破。', examples: ['《镇国战神》《龙王殿》'] },
      { id: 'ss_son_in_law', name: '赘婿逆袭流', description: '主角入赘豪门受尽白眼，隐忍后爆发。爽感来自对势利亲属的反转碾压。', examples: ['《赘婿》《狂飙吧赘婿》'] },
      { id: 'ss_sweet_romance', name: '极致甜宠流', description: '弱化外部冲突，无限放大男女主的亲密互动。每集至少一个"心动时刻"。', examples: ['《顾少的替嫁新娘》《闪婚后傅先生马甲藏不住了》'] },
      { id: 'ss_abuse_chase', name: '虐恋追妻流', description: '女主被男主伤害后离开，男主追悔莫及。爽感来自"虐一时、爽一世"的延迟补偿。', examples: ['《蚀骨危情》《薄爷夫人又去虐渣了》'] },
      { id: 'ss_tycoon', name: '豪门/神豪流', description: '财富权力的极致想象。主角或隐藏富豪身份打脸拜金者，或挥金如土解决一切问题。', examples: ['《首富归来》《神豪从签到开始》'] },
      { id: 'ss_rebirth', name: '穿越/重生流', description: '赋予主角"先知"能力，利用信息差改写命运。爽感来自修正过去、预判未来的掌控感。', examples: ['《重生90之这个村姑不好惹》《穿书后我成了反派大佬》'] },
      { id: 'ss_career_rise', name: '职场/行业逆袭流', description: '将专业能力转化为"爽点"，如医生一眼看出隐疾、律师法庭绝杀。专业即权力是核心逻辑。', examples: ['《了不起的儿科医生》《外卖小哥的逆袭人生》'] },
      { id: 'ss_xuanhuan', name: '玄幻/修真流', description: '网文修仙体系在短剧的浓缩移植。筑基、金丹、元婴等境界突破构成天然节奏点，升级即爽点。', examples: ['《凡人修仙传（短剧版）》《仙王的日常生活》'] },
      { id: 'ss_system', name: '都市异能/系统流', description: '主角获得超能力或"系统"辅助。系统任务和奖励构成强叙事引擎，天然适配短剧的快节奏。', examples: ['《我的系统是全能高手》《透视医圣》'] },
      { id: 'ss_cute_baby', name: '萌宝/带球跑流', description: '女主带天才萌宝归来，萌宝助攻父母复合或帮母亲打脸渣男。萌娃的"神助攻"是核心看点。', examples: ['《萌宝来袭总裁爹地请签收》《天才萌宝妈咪超厉害》'] },
      { id: 'ss_strong_female', name: '大女主/女强流', description: '女性独立叙事，女主不依附男性，凭借自身能力逆袭。自我价值实现替代"被爱"成为核心驱动力。', examples: ['《当家小娘子》《夫人你马甲又掉了》'] }
    ]
  },
  {
    id: 'genre_v2',
    name: '风格流派（2.0前沿）',
    description: '网络短剧新兴类型探索',
    styles: [
      { id: 'sv2_suspense', name: '悬疑短剧', description: '将悬疑类型压缩至短剧长度，每集抛出悬念。"钩子密度"远超长剧，但开始注重逻辑闭环而非单纯猎奇。', examples: ['《她和她的她》《开端》短剧化趋势'] },
      { id: 'sv2_realism', name: '现实主义流', description: '跳出"爽感"逻辑，关注真实生活议题。聚焦普通人的困境与温情，用真实取代夸张。', examples: ['《逃出大英博物馆》《我的阿勒泰》'] },
      { id: 'sv2_regional', name: '地域文化流', description: '方言叙事 + 地域文化符号，将故事锚定于特定地理文化语境。文化质感成为差异化竞争力。', examples: ['《家里家外》（四川方言）、《繁花》短剧化影响'] },
      { id: 'sv2_comedy', name: '喜剧/荒诞流', description: '继承早期网剧喜剧基因，但表达更精准。用幽默消解类型套路，在爽感中注入自反性。', examples: ['《这个杀手不改需求》《大妈的世界》'] },
      { id: 'sv2_anthology', name: '单元/诗选流', description: '一集一故事，或每几集一个独立篇章。降低追剧门槛，适合碎片化消费。', examples: ['《深夜食堂》短剧化、《怪奇物语》短剧化探索'] },
      { id: 'sv2_interactive', name: '互动/实验流', description: '探索竖屏的形式边界，尝试主观镜头、监控视角、桌面叙事等非常规语法。', examples: ['抖音平台部分实验性作品'] },
      { id: 'sv2_ip_universe', name: 'IP衍生/宇宙流', description: '长剧IP的短剧化衍生，或短剧自身构建角色宇宙。角色复用和世界观共享形成流量复利。', examples: ['《庆余年》衍生短剧、《唐朝诡事录》短剧版'] },
      { id: 'sv2_anti_trope', name: '反套路/解构流', description: '对"战神""霸总"等1.0类型的自我调侃。主角意识到自己是套路中角色并试图反抗，用元叙事制造新鲜感。', examples: ['《穿成虐文女主我反杀了》《反派觉醒系统》'] },
      { id: 'sv2_cultural', name: '文化传承流', description: '将非遗、戏曲、诗词等传统文化元素作为叙事核心。文化价值成为内容增量。', examples: ['《东栏雪》（围棋文化）、《江南时节》（节气美学）'] }
    ]
  },
  {
    id: 'director',
    name: '导演风格（短剧）',
    description: '网络短剧导演的个人风格',
    styles: [
      { id: 'sd_tech', name: '技术流', description: '导演以技术手段建立辨识度。转场设计、运镜创意、特效应用成为风格标签，追求"每一秒都有技术含量"。', examples: ['部分抖音头部导演'] },
      { id: 'sd_atmosphere', name: '氛围流', description: '弱化强情节，强化视听氛围。光影、色彩、声音设计优先于戏剧冲突，营造沉浸式情绪体验。', examples: ['《三更雪》《盛夏芬德拉》导演'] },
      { id: 'sd_hybrid', name: '类型杂糅者', description: '将多种类型元素糅合于短剧长度。喜剧+悬疑、甜宠+职场、玄幻+商战等组合产生化学反应。', examples: ['行业新兴趋势'] }
    ]
  },
  {
    id: 'narrative',
    name: '叙事风格（短剧）',
    description: '网络短剧叙事手法',
    styles: [
      { id: 'sn_hook_first', name: '"钩子先行"模式', description: '1.0时代的极致叙事策略。前三秒必须抛出一个强悬念、强冲突或强感官刺激，确保用户不划走。', examples: ['几乎所有小程序剧的标准配置'] },
      { id: 'sn_reversal_addiction', name: '"反转上瘾"模式', description: '每集结尾设计反转，下一集开头再反转回来。双重反转结构制造"连续追看"的心理机制。', examples: ['大量付费短剧的叙事设计'] },
      { id: 'sn_blank_narrative', name: '"留白叙事"探索', description: '2.0新兴方向。不再填满每一秒，用省略和暗示替代直接呈现，给观众想象和讨论空间。', examples: ['部分文艺向短剧的尝试'] },
      { id: 'sn_empathy_first', name: '"共情前置"模式', description: '在爽感之前先建立情感连接。先让观众"心疼"或"共情"主角，再释放爽感，效果加倍。', examples: ['《我在八零年代当后妈》等成功案例'] }
    ]
  },
  {
    id: 'cinematography',
    name: '镜头剪辑风格（短剧）',
    description: '网络短剧摄影与剪辑风格',
    styles: [
      { id: 'sc_info_bomb', name: '"信息轰炸"式剪辑', description: '1.0时代的极致语法。多画面分屏、快速跳切、字幕强化、音效强调，每秒信息密度最大化。', examples: ['抖音快手大量短剧'] },
      { id: 'sc_breathing', name: '"呼吸感"剪辑探索', description: '2.0反向趋势。长镜头、固定机位、慢节奏切换，用留白对冲信息过载，给观众喘息和感受的空间。', examples: ['《我的阿勒泰》等精品化作品'] },
      { id: 'sc_rhetoric_lens', name: '"镜头作为修辞"', description: '镜头不再只是记录工具，而成为叙事修辞。倾斜构图表达失衡、俯拍表达压迫、手持表达焦虑。', examples: ['知竹、周九钦等导演的实践'] }
    ]
  },
  {
    id: 'performance',
    name: '演绎风格（短剧）',
    description: '网络短剧表演风格',
    styles: [
      { id: 'sp_spectacle', name: '"奇观化"表演', description: '1.0时代的极致表达。表演本身就是一种可供剪辑的"名场面"奇观：扇耳光、下跪、雨中怒吼、机场狂奔。', examples: ['大量小程序剧的"名场面"'] },
      { id: 'sp_micro_expression', name: '"微相学"表演', description: '2.0精品化方向。瞳孔的颤动、嘴角的抽动、呼吸节奏的变化成为情感传达的核心载体。', examples: ['《少夫人来自东北》《北往》等作品的表演特征'] },
      { id: 'sp_amateur', name: '"素人感"表演', description: '反"表演腔"的趋势。生活化的语速、日常的肢体动作、非精致的形象，营造"这就是你我身边的故事"的亲近感。', examples: ['《家里家外》《回乡的诱惑》等生活流作品'] }
    ]
  }
]

// ==================== 导出函数 ====================

/**
 * 获取所有维度（根据类型）
 * @param {'long'|'short'} type - 长篇或短剧
 */
export function getSeriesDimensionsByType(type) {
  return type === 'long' ? longSeriesDimensions : shortSeriesDimensions
}

/**
 * 获取扁平化的风格列表
 * @param {'long'|'short'} type
 */
export function getAllSeriesStyles(type) {
  const dims = getSeriesDimensionsByType(type)
  return dims.flatMap(dim =>
    dim.styles.map(s => ({ ...s, dimension: dim.name, dimensionId: dim.id, category: type }))
  )
}

/**
 * 类型选项
 */
export const seriesTypeOptions = [
  { value: 'long', label: '长篇电视剧' },
  { value: 'short', label: '网络短剧' }
]
