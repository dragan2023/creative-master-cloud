/**
 * 电影风格选择器数据
 * 数据来源：电影风格参考总表.md
 * 包含六大维度：风格流派、导演风格、叙事风格、剪辑/蒙太奇流派、演绎/表演风格、台词风格
 */

export const movieStyleDimensions = [
  {
    id: 'genre',
    name: '电影风格流派',
    description: '电影史上重要的风格流派与运动',
    styles: [
      { id: 'german_expressionism', name: '德国表现主义', description: '扭曲场景、夸张光影、强调主观心理的外化呈现，风格黑暗、不安。', examples: ['《卡里加利博士的小屋》'] },
      { id: 'soviet_montage', name: '苏联蒙太奇学派', description: '通过镜头/场景的冲突性并置创造新的意义，服务于意识形态表达。', examples: ['《战舰波将金号》'] },
      { id: 'surrealism', name: '超现实主义', description: '打破逻辑与理性，表现梦境、潜意识与欲望的非理性拼贴。', examples: ['《一条安达鲁狗》'] },
      { id: 'dadaism', name: '达达主义电影', description: '反艺术、反逻辑，追求荒诞、虚无与破坏性，无连贯叙事。', examples: ['《幕间休息》'] },
      { id: 'poetic_realism', name: '诗意现实主义', description: '描绘底层社会，在写实中融入抒情、感伤与宿命感，灰暗浪漫。', examples: ['《天色破晓》'] },
      { id: 'italian_neorealism', name: '意大利新现实主义', description: '实景拍摄、非职业演员感、关注战后底层生活，纪实风格强烈。', examples: ['《偷自行车的人》'] },
      { id: 'french_new_wave', name: '法国新浪潮', description: '反传统叙事、跳切、存在主义主题、强调导演个人风格与即兴感。', examples: ['《筋疲力尽》《四百击》'] },
      { id: 'cahiers_du_cinema', name: '电影手册派', description: '法国新浪潮的理论核心，"作者论"的提出者与实践者。', examples: ['特吕弗、戈达尔等'] },
      { id: 'kitchen_sink', name: '英国厨房水槽现实主义', description: '聚焦工薪阶层青年的日常生活与愤怒情绪，风格粗粝、批判现实。', examples: ['《上流社会》'] },
      { id: 'polish_school', name: '波兰学派', description: '阴郁视觉、象征性叙事，探讨二战创伤与存在主义困境。', examples: ['《灰烬与钻石》'] },
      { id: 'brazil_new_cinema', name: '巴西新电影', description: '"饥饿的美学"，低成本、粗糙影像，揭露底层社会的贫穷与压迫。', examples: ['《贫瘠的生活》'] },
      { id: 'czech_new_wave', name: '捷克新浪潮', description: '黑色幽默、荒诞感、非职业演员，含蓄批判极权体制。', examples: ['《消防员舞会》《雏菊》'] },
      { id: 'german_new_cinema', name: '德国新电影', description: '突破传统，强调个人表达与社会批判，关注战后德国精神困境。', examples: ['法斯宾德、文德斯等'] },
      { id: 'new_hollywood', name: '新好莱坞电影', description: '受新浪潮影响，打破片厂制度，强调反叛精神与导演个人表达。', examples: ['《逍遥骑士》《出租车司机》'] },
      { id: 'film_noir', name: '黑色电影', description: '高反差光影、道德模糊、蛇蝎美人、充满宿命感的悲观氛围。', examples: ['《双重赔偿》'] },
      { id: 'magic_realism', name: '魔幻现实主义', description: '将魔幻元素当作日常来写，现实与幻想无缝衔接，用于政治或历史隐喻。', examples: ['《潘神的迷宫》《大鱼》'] },
      { id: 'dogme95', name: '丹麦道格玛95', description: '遵循"纯洁誓言"，手持摄影、实景自然光、拒绝虚假特效。', examples: ['《家宴》'] },
      { id: 'american_indie', name: '美国独立电影运动', description: '低成本、关注边缘人群与亚文化，叙事与风格先锋个性化。', examples: ['《性、谎言和录像带》'] },
      { id: 'realism', name: '现实主义', description: '强调对现实的忠实再现，结构松散，提供大量生活细节。', examples: ['纪录片风格剧情片'] },
      { id: 'formalism', name: '形式主义', description: '强调艺术形式本身的创造性，通过风格化技巧传达内涵。', examples: ['先锋派及实验电影'] }
    ]
  },
  {
    id: 'director',
    name: '导演风格',
    description: '知名导演的独特电影风格',
    styles: [
      { id: 'zhang_yimou', name: '张艺谋', description: '强烈的视觉造型与色彩叙事，宏大场景，中国文化符号的影像化。', examples: ['《英雄》《大红灯笼高高挂》《影》'] },
      { id: 'feng_xiaogang', name: '冯小刚', description: '冯氏冷幽默、自我调侃、京味调侃与主流文化的温和对抗。', examples: ['《甲方乙方》《大腕》'] },
      { id: 'quentin_tarantino', name: '昆汀·塔伦蒂诺', description: '话痨对白、章回体非线性叙事、暴力美学、流行文化引用。', examples: ['《低俗小说》《无耻混蛋》'] },
      { id: 'jiang_wen', name: '姜文', description: '荷尔蒙满溢、密集金句、隐喻狂欢、雄性叙事与权力批判。', examples: ['《让子弹飞》《阳光灿烂的日子》'] },
      { id: 'wong_kar_wai', name: '王家卫', description: '碎片化叙事、极致视听风格、文学化独白、时间与疏离主题。', examples: ['《重庆森林》《花样年华》'] },
      { id: 'akira_kurosawa', name: '黑泽明', description: '动静结合、强力构图（天气运用）、史诗感与英雄主义叙事。', examples: ['《七武士》《罗生门》'] },
      { id: 'ingmar_bergman', name: '英格玛·伯格曼', description: '特写捕捉精神痛苦，深入探讨信仰、死亡与存在主义隔绝。', examples: ['《第七封印》《假面》'] },
      { id: 'andrei_tarkovsky', name: '安德烈·塔可夫斯基', description: '诗性长镜头，通过自然意象（水、火、雾）雕刻时光与记忆。', examples: ['《乡愁》《潜行者》'] },
      { id: 'federico_fellini', name: '费德里科·费里尼', description: '从新现实主义转向梦境、狂欢与马戏团式自传想象。', examples: ['《八部半》《甜蜜的生活》'] },
      { id: 'ozu_yasujiro', name: '小津安二郎', description: '低机位固定镜头、极简构图、家庭聚散与日常韵律。', examples: ['《东京物语》'] },
      { id: 'stanley_kubrick', name: '斯坦利·库布里克', description: '极端完美主义、对称构图、古典配乐营造冰冷疏离的哲学感。', examples: ['《2001太空漫游》《发条橙》'] },
      { id: 'jean_luc_godard', name: '让-吕克·戈达尔', description: '激进"跳切"、打破第四堵墙、声画对位，持续颠覆电影语言。', examples: ['《筋疲力尽》《法外之徒》'] },
      { id: 'agnes_varda', name: '阿涅斯·瓦尔达', description: '纪录片观察与个人散文结合，轻盈温柔又具政治参与感。', examples: ['《天涯沦落女》'] },
      { id: 'pedro_almodovar', name: '佩德罗·阿莫多瓦', description: '色彩浓烈奔放、情节剧叙事，聚焦女性、欲望与西班牙社会。', examples: ['《关于我母亲的一切》'] },
      { id: 'hirokazu_koreeda', name: '是枝裕和', description: '纪录片式旁观视角，非戏剧化表演，描绘家庭日常裂痕与微光。', examples: ['《小偷家族》《步履不停》'] },
      { id: 'bong_joon_ho', name: '奉俊昊', description: '类型混合大师，以高度娱乐性叙事揭示尖锐的社会阶级矛盾。', examples: ['《寄生虫》《杀人回忆》'] },
      { id: 'hou_hsiao_hsien', name: '侯孝贤', description: '长镜头、固定远景，营造凝练疏离的诗意历史感。', examples: ['《刺客聂隐娘》《悲情城市》'] },
      { id: 'edward_yang', name: '杨德昌', description: '手术刀般冷静的都市解剖，多线叙事呈现中产家庭的疏离困境。', examples: ['《一一》《牯岭街少年杀人事件》'] },
      { id: 'ang_lee', name: '李安', description: '学贯中西，深挖人物情感，在文化冲突中寻找普世人性平衡。', examples: ['《卧虎藏龙》《断背山》'] },
      { id: 'alfonso_cuaron', name: '阿方索·卡隆', description: '运动长镜头创造沉浸空间，技术服务于宏大情感与历史记忆。', examples: ['《罗马》《人类之子》'] },
      { id: 'christopher_nolan', name: '克里斯托弗·诺兰', description: '迷恋时间与记忆的复杂叙事迷宫，在商业大片中探讨理性与情感。', examples: ['《奥本海默》《盗梦空间》'] },
      { id: 'wes_anderson', name: '韦斯·安德森', description: '强迫症式对称构图、高饱和童话色彩、冷幽默旁白与平移镜头。', examples: ['《布达佩斯大饭店》'] }
    ]
  },
  {
    id: 'narrative',
    name: '叙事风格',
    description: '电影叙事结构与手法',
    styles: [
      { id: 'linear_single', name: '线性单线叙事', description: '单一主人公，严格按时间顺序展开（开端-发展-高潮-结局）。', examples: ['《肖申克的救赎》'] },
      { id: 'linear_multiple', name: '线性复线叙事', description: '同一时间流程，多线索、多空间并行推进。', examples: ['《教父2》双线'] },
      { id: 'nonlinear_single', name: '非线性单线叙事', description: '包含倒叙、插叙、闪回，或表现同一主人公的不同选择可能性。', examples: ['《记忆碎片》《罗拉快跑》'] },
      { id: 'multi_line_interweave', name: '多线交织叙事', description: '多条看似独立的故事线在关键节点意外交汇，强调命运与张力。', examples: ['《撞车》'] },
      { id: 'theme_juxtaposition', name: '主题并置叙事', description: '多个时空不相关的主人公，通过高度一致的主题平行并置。', examples: ['《云图》《党同伐异》'] },
      { id: 'multi_timeline', name: '多重时空叙事', description: '不同时间层面的故事交叉叙述，探索时间对人物命运的影响。', examples: ['《星际穿越》《你的名字。》'] },
      { id: 'nested_narrative', name: '套层叙事（戏中戏）', description: '故事里嵌套故事，形成俄罗斯套娃般的多层结构。', examples: ['《布达佩斯大饭店》《罗生门》'] },
      { id: 'counterpoint_polyphonic', name: '对位式复调叙事', description: '多组人物故事相对独立但相互关联，拼贴式组合。', examples: ['《重庆森林》《低俗小说》'] },
      { id: 'dialogic_polyphonic', name: '对话式复调叙事', description: '一组人物对另一组人物的讲述与评论，以主观闪回为特色。', examples: ['《公民凯恩》'] },
      { id: 'tree_narrative', name: '树状叙事', description: '一个关键事件发散出多种可能性，探索偶然与宿命。', examples: ['《罗拉快跑》'] },
      { id: 'circular_narrative', name: '环形/回环叙事', description: '故事终点即是起点，形成闭环，强调循环、轮回与宿命。', examples: ['《暴雨将至》《恐怖游轮》'] },
      { id: 'chain_narrative', name: '连锁叙事', description: '一个故事引发下一个，环环相扣如多米诺骨牌。', examples: ['《毒品网络》'] },
      { id: 'fragmented_narrative', name: '碎片化叙事', description: '叙事线被打碎成无序片段，模拟记忆、创伤或迷失心理。', examples: ['《穆赫兰道》'] },
      { id: 'multi_perspective', name: '多视角叙事', description: '同一事件由多个角色的主观视角反复讲述，呈现真相的相对性。', examples: ['《刺杀据点》'] },
      { id: 'epistolary_narrative', name: '日记体/书信体叙事', description: '以第一人称口述、日记或书信为叙事框架，带有强烈主观色彩。', examples: ['《潜水钟与蝴蝶》'] },
      { id: 'psychological_narrative', name: '心理叙事', description: '摒弃外部逻辑，跟随角色的潜意识、梦境与幻觉流动。', examples: ['《去年在马里昂巴德》'] },
      { id: 'poetic_narrative', name: '诗意叙事', description: '弱化戏剧冲突，强调视觉隐喻、情绪氛围与意象堆叠。', examples: ['《镜子》'] },
      { id: 'chapter_narrative', name: '章回体叙事', description: '模仿小说章节结构，用明确标题划分独立段落。', examples: ['《低俗小说》'] },
      { id: 'essay_narrative', name: '散文式/生活流叙事', description: '看似松散无目的，通过大量生活细节铺陈情绪与时间质感。', examples: ['《天水围的日与夜》'] },
      { id: 'o_henry_ending', name: '欧亨利式结尾', description: '结尾出人意料又在情理之中，以反转制造戏剧性冲击。', examples: ['《第六感》'] }
    ]
  },
  {
    id: 'editing',
    name: '剪辑/蒙太奇流派',
    description: '电影剪辑与蒙太奇风格',
    styles: [
      { id: 'soviet_montage_edit', name: '苏联蒙太奇学派', description: '场景设计需具有冲突性与隐喻性，通过并置产生新意义。', examples: ['《战舰波将金号》'] },
      { id: 'continuity_editing', name: '连续性剪辑（好莱坞式）', description: '场景衔接流畅自然，严格遵循因果关系，服务于清晰叙事。', examples: ['主流商业大片'] },
      { id: 'jump_cut', name: '跳切（法国新浪潮式）', description: '剧本结构包含刻意的时空跳跃、省略与情绪断层。', examples: ['《筋疲力尽》'] },
      { id: 'attraction_montage', name: '杂耍蒙太奇', description: '脱离叙事主线，插入具有强烈情绪冲击力的象征性段落。', examples: ['爱森斯坦作品'] },
      { id: 'parallel_cross_montage', name: '平行/交叉蒙太奇', description: '两条或多条线索交替呈现，最后汇聚，制造悬念与紧张感。', examples: ['《教父》洗礼片段'] },
      { id: 'rational_montage', name: '理性蒙太奇', description: '场景组合的目的在于引发观众理性思考与观念变革。', examples: ['表达政治哲学理念的影片'] },
      { id: 'long_take_aesthetics', name: '长镜头美学/段落镜头', description: '强调时空完整与真实感，大段连续时空内的动作与调度。', examples: ['《1917》《鸟人》'] }
    ]
  },
  {
    id: 'performance',
    name: '演绎/表演风格',
    description: '演员表演方法与风格',
    styles: [
      { id: 'stanislavski', name: '斯坦尼斯拉夫斯基体系（体验派）', description: '演员完全化身为角色，深入角色心理动机与情感逻辑。', examples: ['马龙·白兰度《教父》'] },
      { id: 'method_acting', name: '方法派', description: '调动演员个人情感记忆代入角色，追求极致的真实感。', examples: ['阿尔·帕西诺《热天午后》'] },
      { id: 'brechtian', name: '布莱希特体系（间离派）', description: '演员与角色保持距离，可对观众说话，打破幻觉引导理性批判。', examples: ['戈达尔作品、《狗镇》'] },
      { id: 'chinese_opera', name: '中国戏曲程式化表演', description: '建立在写意、程式化的舞台美学上，不追求完全写实。', examples: ['《霸王别姬》'] },
      { id: 'naturalistic', name: '自然主义表演', description: '极度日常化、生活化，拒绝戏剧化夸张，还原真实状态。', examples: ['肯·洛奇《我是布莱克》'] },
      { id: 'stylized', name: '风格化/机械感表演', description: '服务于导演整体美学的符号化、夸张或刻意克制的表演。', examples: ['韦斯·安德森作品、《发条橙》'] },
      { id: 'improvisational', name: '即兴表演', description: '演员在设定情境中即兴发挥，追求不可预知的真实火花。', examples: ['约翰·卡萨维茨《权势下的女人》'] },
      { id: 'genre_acting', name: '类型化表演', description: '根据类型片程式进行表演，强调标志性动作与节奏。', examples: ['巴斯特·基顿（冷面笑匠）'] },
      { id: 'minimalist', name: '极简主义表演', description: '抑制外部表情和动作，用细微眼神与呼吸传达复杂情感。', examples: ['高仓健《幸福的黄手帕》'] },
      { id: 'expressionist_acting', name: '表现主义表演', description: '为表达内心而对外部形体、表情和声音进行夸张扭曲处理。', examples: ['罗伯特·德尼罗《愤怒的公牛》'] },
      { id: 'mime_acting', name: '哑剧式表演', description: '完全依赖精准的肢体控制与面部表情叙事，超越语言。', examples: ['卓别林《城市之光》'] },
      { id: 'collective_improvisation', name: '集体即兴创作', description: '导演带领全体演员即兴创作，追求整体真实生活质感。', examples: ['迈克·李《秘密与谎言》'] },
      { id: 'non_professional', name: '非职业演员本色出演', description: '启用无表演经验的素人，呈现未经雕琢的真实状态。', examples: ['达内兄弟《孩子》'] },
      { id: 'anti_genre_acting', name: '反类型化表演', description: '刻意违背角色刻板印象，以反常、内敛或矛盾方式演绎。', examples: ['达斯汀·霍夫曼《稻草狗》'] },
      { id: 'physical_acting', name: '身体性表演', description: '将演员身体作为核心媒介，通过极端训练外化角色心理。', examples: ['夏洛特·甘斯布《反基督者》'] }
    ]
  },
  {
    id: 'dialogue',
    name: '台词风格',
    description: '对白与台词写作风格',
    styles: [
      { id: 'garrulous', name: '话痨/知识份子式', description: '对话密集，包含大量双关、讽刺、哲理与流行文化引用。', examples: ['昆汀·塔伦蒂诺、伍迪·艾伦'] },
      { id: 'poetic_monologue', name: '文学化/诗意独白', description: '独白如现代诗，重情绪与意象渲染，淡化信息传递。', examples: ['王家卫《重庆森林》'] },
      { id: 'life_flow_dialogue', name: '生活流/口语化', description: '对话琐碎、有停顿、充满无意义语气词，追求极度真实感。', examples: ['是枝裕和、达内兄弟'] },
      { id: 'subtext', name: '潜台词/冰山理论', description: '表面客套平淡，真实意图与冲突全在不言中。', examples: ['《色，戒》《教父》'] },
      { id: 'aphoristic', name: '金句/荷尔蒙式', description: '台词充满暗喻、双关与戏剧张力，节奏快、信息密度大。', examples: ['姜文《让子弹飞》'] },
      { id: 'deadpan', name: '冷幽默/机械感', description: '面无表情的平淡语调，通过极度克制制造反差冷感幽默。', examples: ['韦斯·安德森《布达佩斯大饭店》'] },
      { id: 'dialect', name: '方言/地方特色', description: '深度结合地域方言，用市井语言塑造底层人物的鲜活感。', examples: ['冯小刚、宁浩《疯狂的石头》'] },
      { id: 'philosophical', name: '哲理/存在主义', description: '人物对话进行大段哲学与神学辩论，台词作为思想载体。', examples: ['伯格曼《第七封印》'] },
      { id: 'minimalist_dialogue', name: '极简/留白', description: '刻意减少台词，用沉默、眼神与环境音替代语言。', examples: ['《刺客聂隐娘》《2001太空漫游》'] },
      { id: 'theatrical', name: '戏剧化/舞台腔', description: '经过高度文学提炼的抑扬顿挫，具有朗诵与仪式感。', examples: ['莎士比亚改编电影《哈姆雷特》'] }
    ]
  }
]

/**
 * 获取扁平化的风格列表（用于搜索等功能）
 */
export function getAllMovieStyles() {
  return movieStyleDimensions.flatMap(dim =>
    dim.styles.map(s => ({ ...s, dimension: dim.name, dimensionId: dim.id }))
  )
}

/**
 * 根据维度ID获取该维度下的所有风格
 */
export function getMovieStylesByDimension(dimensionId) {
  const dim = movieStyleDimensions.find(d => d.id === dimensionId)
  return dim ? dim.styles : []
}
