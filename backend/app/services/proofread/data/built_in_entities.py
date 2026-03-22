"""
内置敏感实体库 - 简化版

数据来源：人工整理的核心数据集
- 地名：省级+主要城市（约100条）
- 名人：各领域知名人物（约200条）
- 历史事件：重大历史事件（约50条）

注意：此数据集仅供本地检测使用，不涉及外部API调用
"""
from typing import Dict, List, Any


# ==================== 中国地名库 ====================

CHINA_LOCATIONS: Dict[str, List[str]] = {
    # 直辖市
    "municipalities": [
        "北京市", "上海市", "天津市", "重庆市",
        "北京", "上海", "天津", "重庆"
    ],

    # 省级行政区
    "provinces": [
        "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
        "江苏省", "浙江省", "安徽省", "福建省", "江西省",
        "山东省", "河南省", "湖北省", "湖南省", "广东省",
        "海南省", "四川省", "贵州省", "云南省", "陕西省",
        "甘肃省", "青海省", "台湾省",
        "内蒙古自治区", "广西壮族自治区", "西藏自治区",
        "宁夏回族自治区", "新疆维吾尔自治区",
        "香港特别行政区", "澳门特别行政区",
        # 简称
        "河北", "山西", "辽宁", "吉林", "黑龙江",
        "江苏", "浙江", "安徽", "福建", "江西",
        "山东", "河南", "湖北", "湖南", "广东",
        "海南", "四川", "贵州", "云南", "陕西",
        "甘肃", "青海", "台湾",
        "内蒙古", "广西", "西藏", "宁夏", "新疆",
        "香港", "澳门"
    ],

    # 省会城市及主要城市
    "cities": [
        # 华北地区
        "石家庄市", "石家庄", "太原市", "太原", "呼和浩特市", "呼和浩特",
        # 东北地区
        "沈阳市", "沈阳", "长春市", "长春", "哈尔滨市", "哈尔滨", "大连市", "大连",
        # 华东地区
        "南京市", "南京", "杭州市", "杭州", "合肥市", "合肥", "福州市", "福州",
        "南昌市", "南昌", "济南市", "济南", "青岛市", "青岛", "宁波市", "宁波",
        "厦门市", "厦门", "苏州市", "苏州", "无锡市", "无锡", "常州市", "常州",
        "温州市", "温州", "南通市", "南通", "徐州市", "徐州",
        # 华中地区
        "郑州市", "郑州", "武汉市", "武汉", "长沙市", "长沙",
        # 华南地区
        "广州市", "广州", "深圳市", "深圳", "南宁市", "南宁", "海口市", "海口",
        "东莞市", "东莞", "佛山市", "佛山", "珠海市", "珠海", "中山市", "中山",
        "惠州市", "惠州", "汕头市", "汕头",
        # 西南地区
        "成都市", "成都", "贵阳市", "贵阳", "昆明市", "昆明", "拉萨市", "拉萨",
        # 西北地区
        "西安市", "西安", "兰州市", "兰州", "西宁市", "西宁", "银川市", "银川",
        "乌鲁木齐市", "乌鲁木齐"
    ],

    # 高频区县
    "districts": [
        "朝阳区", "海淀区", "丰台区", "东城区", "西城区",
        "浦东新区", "黄浦区", "静安区", "徐汇区", "长宁区",
        "南山区", "福田区", "罗湖区", "宝安区", "龙岗区", "龙华区",
        "天河区", "越秀区", "白云区", "番禺区", "海珠区",
        "西湖区", "江干区", "拱墅区", "余杭区", "萧山区",
        "玄武区", "秦淮区", "建邺区", "鼓楼区", "江宁区"
    ],

    # 著名景点/地标
    "landmarks": [
        "天安门", "故宫", "长城", "颐和园", "圆明园",
        "外滩", "东方明珠", "豫园",
        "西湖", "灵隐寺", "千岛湖",
        "兵马俑", "大雁塔", "华清池",
        "九寨沟", "峨眉山", "都江堰",
        "桂林", "漓江", "阳朔",
        "张家界", "凤凰古城",
        "黄山", "泰山", "华山", "衡山", "嵩山", "恒山",
        "布达拉宫", "大昭寺"
    ]
}


# ==================== 中国名人库 ====================

CHINA_CELEBRITIES: Dict[str, List[Dict[str, str]]] = {
    # 演员
    "actors": [
        {"name": "成龙", "aliases": ["Jackie Chan", "陈港生"]},
        {"name": "周星驰", "aliases": ["Stephen Chow", "星爷"]},
        {"name": "刘德华", "aliases": ["Andy Lau", "华仔"]},
        {"name": "周润发", "aliases": ["发哥", "Chow Yun-fat"]},
        {"name": "李连杰", "aliases": ["Jet Li"]},
        {"name": "甄子丹", "aliases": ["Donnie Yen"]},
        {"name": "梁朝伟", "aliases": ["Tony Leung"]},
        {"name": "张国荣", "aliases": ["Leslie Cheung", "哥哥"]},
        {"name": "葛优", "aliases": []},
        {"name": "黄渤", "aliases": []},
        {"name": "沈腾", "aliases": []},
        {"name": "吴京", "aliases": []},
        {"name": "章子怡", "aliases": ["Zhang Ziyi"]},
        {"name": "巩俐", "aliases": ["Gong Li"]},
        {"name": "张曼玉", "aliases": ["Maggie Cheung"]},
        {"name": "刘亦菲", "aliases": ["Crystal Liu", "神仙姐姐"]},
        {"name": "杨幂", "aliases": []},
        {"name": "赵丽颖", "aliases": []},
        {"name": "范冰冰", "aliases": ["Bingbing Fan"]},
        {"name": "李冰冰", "aliases": ["Li Bingbing"]},
        {"name": "周迅", "aliases": []},
        {"name": "汤唯", "aliases": []},
        {"name": "孙俪", "aliases": []},
        {"name": "刘涛", "aliases": []},
        {"name": "胡歌", "aliases": []},
        {"name": "王凯", "aliases": []},
        {"name": "邓超", "aliases": []},
        {"name": "黄晓明", "aliases": []},
        {"name": "陈坤", "aliases": []},
        {"name": "吴彦祖", "aliases": ["Daniel Wu"]}
    ],

    # 导演
    "directors": [
        {"name": "张艺谋", "aliases": []},
        {"name": "陈凯歌", "aliases": []},
        {"name": "冯小刚", "aliases": []},
        {"name": "姜文", "aliases": []},
        {"name": "贾樟柯", "aliases": []},
        {"name": "王家卫", "aliases": ["Wong Kar-wai"]},
        {"name": "李安", "aliases": ["Ang Lee"]},
        {"name": "徐克", "aliases": []},
        {"name": "吴宇森", "aliases": ["John Woo"]},
        {"name": "宁浩", "aliases": []},
        {"name": "郭帆", "aliases": []},
        {"name": "文牧野", "aliases": []},
        {"name": "管虎", "aliases": []},
        {"name": "林超贤", "aliases": []}
    ],

    # 歌手
    "singers": [
        {"name": "周杰伦", "aliases": ["Jay Chou"]},
        {"name": "林俊杰", "aliases": ["JJ Lin"]},
        {"name": "王力宏", "aliases": ["Wang Leehom"]},
        {"name": "陈奕迅", "aliases": ["Eason Chan"]},
        {"name": "薛之谦", "aliases": []},
        {"name": "毛不易", "aliases": []},
        {"name": "李荣浩", "aliases": []},
        {"name": "华晨宇", "aliases": []},
        {"name": "张杰", "aliases": []},
        {"name": "王菲", "aliases": ["Faye Wong"]},
        {"name": "邓紫棋", "aliases": ["G.E.M."]},
        {"name": "张惠妹", "aliases": ["A-Mei"]},
        {"name": "蔡依林", "aliases": ["Jolin Tsai"]},
        {"name": "李宇春", "aliases": ["Chris Lee"]},
        {"name": "张学友", "aliases": ["Jacky Cheung", "歌神"]},
        {"name": "刘德华", "aliases": ["Andy Lau"]},
        {"name": "郭富城", "aliases": ["Aaron Kwok"]},
        {"name": "黎明", "aliases": ["Leon Lai"]}
    ],

    # 作家
    "writers": [
        {"name": "莫言", "aliases": []},
        {"name": "余华", "aliases": []},
        {"name": "刘慈欣", "aliases": []},
        {"name": "韩寒", "aliases": []},
        {"name": "郭敬明", "aliases": []},
        {"name": "金庸", "aliases": ["查良镛"]},
        {"name": "古龙", "aliases": []},
        {"name": "琼瑶", "aliases": []},
        {"name": "三毛", "aliases": []},
        {"name": "王小波", "aliases": []},
        {"name": "贾平凹", "aliases": []},
        {"name": "陈忠实", "aliases": []},
        {"name": "路遥", "aliases": []},
        {"name": "钱钟书", "aliases": []},
        {"name": "鲁迅", "aliases": ["周树人"]},
        {"name": "老舍", "aliases": ["舒庆春"]},
        {"name": "巴金", "aliases": []},
        {"name": "茅盾", "aliases": []}
    ],

    # 政治人物（历史人物为主，敏感度高）
    "politicians": [
        {"name": "毛泽东", "aliases": [], "severity": "high"},
        {"name": "邓小平", "aliases": [], "severity": "high"},
        {"name": "周恩来", "aliases": [], "severity": "high"},
        {"name": "孙中山", "aliases": [], "severity": "high"},
        {"name": "蒋介石", "aliases": [], "severity": "high"},
        {"name": "江泽民", "aliases": [], "severity": "high"},
        {"name": "胡锦涛", "aliases": [], "severity": "high"},
        {"name": "习近平", "aliases": [], "severity": "high"},
        {"name": "温家宝", "aliases": [], "severity": "high"},
        {"name": "李克强", "aliases": [], "severity": "high"}
    ],

    # 运动员
    "athletes": [
        {"name": "姚明", "aliases": ["Yao Ming"]},
        {"name": "刘翔", "aliases": []},
        {"name": "李娜", "aliases": ["Na Li"]},
        {"name": "孙杨", "aliases": []},
        {"name": "林丹", "aliases": ["超级丹"]},
        {"name": "马龙", "aliases": []},
        {"name": "张继科", "aliases": []},
        {"name": "丁宁", "aliases": []},
        {"name": "朱婷", "aliases": []},
        {"name": "郎平", "aliases": ["铁榔头"]},
        {"name": "谷爱凌", "aliases": ["Eileen Gu"]},
        {"name": "苏炳添", "aliases": []},
        {"name": "武大靖", "aliases": []},
        {"name": "全红婵", "aliases": []}
    ],

    # 企业家
    "entrepreneurs": [
        {"name": "马云", "aliases": ["Jack Ma"]},
        {"name": "马化腾", "aliases": ["Pony Ma"]},
        {"name": "任正非", "aliases": []},
        {"name": "雷军", "aliases": []},
        {"name": "刘强东", "aliases": []},
        {"name": "王健林", "aliases": []},
        {"name": "董明珠", "aliases": []},
        {"name": "李彦宏", "aliases": ["Robin Li"]},
        {"name": "张一鸣", "aliases": []},
        {"name": "黄峥", "aliases": []}
    ],

    # 科学家/学者
    "scientists": [
        {"name": "袁隆平", "aliases": []},
        {"name": "屠呦呦", "aliases": []},
        {"name": "钟南山", "aliases": []},
        {"name": "杨振宁", "aliases": []},
        {"name": "钱学森", "aliases": []},
        {"name": "邓稼先", "aliases": []},
        {"name": "华罗庚", "aliases": []},
        {"name": "陈景润", "aliases": []}
    ]
}


# ==================== 中国历史事件库 ====================

CHINA_HISTORICAL_EVENTS: List[Dict[str, Any]] = [
    {"name": "鸦片战争", "period": "1840-1842",
        "severity": "high", "description": "第一次鸦片战争"},
    {"name": "太平天国运动", "period": "1851-1864",
        "severity": "medium", "description": "太平天国农民起义"},
    {"name": "甲午战争", "period": "1894-1895",
        "severity": "high", "description": "中日甲午战争"},
    {"name": "戊戌变法", "period": "1898", "severity": "medium", "description": "百日维新"},
    {"name": "义和团运动", "period": "1899-1901",
        "severity": "medium", "description": "义和团反帝爱国运动"},
    {"name": "八国联军侵华", "period": "1900",
        "severity": "high", "description": "八国联军攻占北京"},
    {"name": "辛亥革命", "period": "1911", "severity": "medium", "description": "推翻清朝统治"},
    {"name": "五四运动", "period": "1919",
        "severity": "medium", "description": "反帝反封建爱国运动"},
    {"name": "北伐战争", "period": "1926-1928",
        "severity": "medium", "description": "国民革命军北伐"},
    {"name": "南昌起义", "period": "1927",
        "severity": "medium", "description": "中国共产党武装起义"},
    {"name": "九一八事变", "period": "1931", "severity": "high", "description": "日本侵占东北"},
    {"name": "长征", "period": "1934-1936",
        "severity": "medium", "description": "红军战略转移"},
    {"name": "西安事变", "period": "1936",
        "severity": "medium", "description": "张学良杨虎城兵谏"},
    {"name": "七七事变", "period": "1937", "severity": "high",
        "description": "卢沟桥事变，全面抗战开始"},
    {"name": "南京大屠杀", "period": "1937", "severity": "high", "description": "日军南京大屠杀"},
    {"name": "抗日战争", "period": "1937-1945",
        "severity": "high", "description": "中国人民抗日战争"},
    {"name": "百团大战", "period": "1940",
        "severity": "medium", "description": "八路军大规模破袭战"},
    {"name": "解放战争", "period": "1946-1949",
        "severity": "high", "description": "国共内战"},
    {"name": "新中国成立", "period": "1949",
        "severity": "medium", "description": "中华人民共和国成立"},
    {"name": "抗美援朝", "period": "1950-1953",
        "severity": "medium", "description": "中国人民志愿军赴朝作战"},
    {"name": "三大改造", "period": "1953-1956",
        "severity": "low", "description": "社会主义改造"},
    {"name": "大跃进", "period": "1958-1960",
        "severity": "medium", "description": "经济建设冒进运动"},
    {"name": "文化大革命", "period": "1966-1976",
        "severity": "high", "description": "十年动乱"},
    {"name": "改革开放", "period": "1978", "severity": "low", "description": "经济体制改革"},
    {"name": "香港回归", "period": "1997", "severity": "low", "description": "香港特别行政区成立"},
    {"name": "澳门回归", "period": "1999", "severity": "low", "description": "澳门特别行政区成立"},
    {"name": "汶川地震", "period": "2008", "severity": "medium", "description": "四川汶川大地震"},
    {"name": "北京奥运会", "period": "2008",
        "severity": "low", "description": "第29届夏季奥林匹克运动会"}
]


# ==================== 敏感词库（基础） ====================

SENSITIVE_WORDS: List[str] = [
    # 政治敏感词（示例，实际使用时需要更完整的词库）
    # 这里只放一些基础的、必须检测的词

    # 暴力恐怖相关
    "恐怖袭击", "爆炸袭击", "自杀式袭击",

    # 毒品相关
    "毒品交易", "贩毒", "制毒",

    # 赌博相关
    "赌博网站", "网络赌博", "地下赌场",

    # 诈骗相关
    "电信诈骗", "网络诈骗", "集资诈骗"
]


# ==================== 辅助函数 ====================

def get_all_locations() -> List[str]:
    """获取所有地名"""
    all_locations = []
    for category in CHINA_LOCATIONS.values():
        all_locations.extend(category)
    return all_locations


def get_all_celebrities() -> List[str]:
    """获取所有名人姓名"""
    all_names = []
    for category in CHINA_CELEBRITIES.values():
        for person in category:
            all_names.append(person["name"])
            # 添加别名
            if person.get("aliases"):
                all_locations.extend(person["aliases"])
    return all_names


def get_all_historical_events() -> List[str]:
    """获取所有历史事件名称"""
    return [event["name"] for event in CHINA_HISTORICAL_EVENTS]


def get_entity_data() -> Dict[str, List]:
    """
    获取格式化的实体数据，用于构建Trie树

    Returns:
        {
            "locations": [...],
            "persons": [...],
            "events": [...],
            "sensitive_words": [...]
        }
    """
    persons = []
    for category, people in CHINA_CELEBRITIES.items():
        for person in people:
            persons.append({
                "name": person["name"],
                "category": category,
                "severity": person.get("severity", "medium"),
                "aliases": person.get("aliases", [])
            })

    events = []
    for event in CHINA_HISTORICAL_EVENTS:
        events.append({
            "name": event["name"],
            "period": event.get("period", ""),
            "severity": event.get("severity", "medium"),
            "description": event.get("description", "")
        })

    return {
        "locations": get_all_locations(),
        "persons": persons,
        "events": events,
        "sensitive_words": SENSITIVE_WORDS
    }
