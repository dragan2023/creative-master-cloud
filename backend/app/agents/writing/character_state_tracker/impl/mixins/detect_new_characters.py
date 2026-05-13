"""CharacterStateTracker - detect_new_charactersMixin"""
from __future__ import annotations
from typing import List
import re


class DetectNewCharactersMixin:
    """detect_new_characters功能域"""

    def detect_new_characters(self, content: str) -> List[str]:
        """从内容中检测新人物

        使用多种启发式规则检测可能的新人物：
        1. 引号中的对话归属人名（精确化）
        2. 特定格式的角色介绍（带身份描述）
        3. 人物动作描述模式（上下文验证）
        4. 姓名称谓结构
        5. 新增：人物介绍句型（增强版）
        6. 新增：首次提及标记

        Args:
            content: 章节内容

        Returns:
            检测到的新人物名称列表
        """
        new_characters = []

        # 模式1：对话归属 - "xxx"某人说道（更精确的模式）
        # 要求：引号内容后紧跟人物名，然后是对话动词
        dialogue_pattern = r'"[^"]*"[，。]?\s*([一-龥]{2,4})(说道|问道|答道|笑道|怒道|叹道|喊道|叫道|低声道|高声道|沉声道)'
        matches = re.findall(dialogue_pattern, content)
        for match in matches:
            name = match[0] if isinstance(match, tuple) else match
            if name not in self._character_names and self._is_likely_character_name(name):
                new_characters.append(name)

        # 模式2：人物出场描述 - 姓名（身份/介绍）
        # 例如："李明（京城市令）"、"张三，一位老者"
        intro_pattern = r'([一-龥]{2,4})[（\(]([^）\)]{2,20})[）\)]'
        matches = re.findall(intro_pattern, content)
        for match in matches:
            name = match[0] if isinstance(match, tuple) else match
            # 检查括号内容是否像身份描述
            description = match[1] if isinstance(match, tuple) else ""
            if self._is_identity_description(description):
                if name not in self._character_names and self._is_likely_character_name(name):
                    new_characters.append(name)

        # 模式3：人物动作描述 - 姓名后跟特定动作动词
        # 更严格的上下文要求：前面需要有句号或开头
        action_pattern = r'(?:^|。！？)\s*([一-龥]{2,4})(走上前|转过身|抬起头|低下头|开口道|笑着说道|皱眉道|点点头|摇摇头|站起身|坐下来)'
        matches = re.findall(action_pattern, content)
        for match in matches:
            name = match[0] if isinstance(match, tuple) else match
            if name not in self._character_names and self._is_likely_character_name(name):
                new_characters.append(name)

        # 模式4：姓名+称谓结构 - 例如"范大人"、"李公子"、"张将军"
        title_pattern = r'([一-龥]{2,3})(大人|公子|小姐|夫人|将军|王爷|丞相|大夫|掌柜|掌门|前辈|少侠)'
        matches = re.findall(title_pattern, content)
        for match in matches:
            name = match[0] if isinstance(match, tuple) else match
            if name not in self._character_names and self._is_likely_character_name(name):
                new_characters.append(name)

        # 模式5（新增）：人物介绍句型 - "名叫XXX"、"名为XXX"、"叫做XXX"
        intro_sentence_patterns = [
            r'名叫([一-龥]{2,4})',
            r'名为([一-龥]{2,4})',
            r'叫做([一-龥]{2,4})',
            r'名字叫([一-龥]{2,4})',
            r'名字是([一-龥]{2,4})',
            r'(一位|一名)([一-龥]{2,8})?名叫([一-龥]{2,4})',
            r'(有一|来了一)(位|名)([一-龥]{2,8})?，?名叫([一-龥]{2,4})'
        ]
        for pattern in intro_sentence_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # 根据捕获组数量确定名字位置
                if isinstance(match, tuple):
                    # 取最后一个元素（通常是名字）
                    name = match[-1]
                else:
                    name = match
                if name not in self._character_names and self._is_likely_character_name(name):
                    new_characters.append(name)

        # 模式6（新增）：“首次出现”、“第一次见到”等标记
        first_appearance_patterns = [
            r'([一-龥]{2,4})首次(出现|登场|露面)',
            r'([一-龥]{2,4})第一次(出现|登场)',
            r'新(来|出现)(的)?([一-龥]{2,4})',
            r'来了一位名叫([一-龥]{2,4})',
            r'走进(一位|一名)([一-龥]{2,8})?的?([一-龥]{2,4})'
        ]
        for pattern in first_appearance_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    # 取最后一个非空元素
                    name = [m for m in match if m][-1]
                else:
                    name = match
                if name not in self._character_names and self._is_likely_character_name(name):
                    new_characters.append(name)

        # 模式7（新增）：“是XXX”、“为XXX”人物判断句型
        judgement_patterns = [
            r'这位([一-龥]{2,4})(是|便是|正是)',
            r'来者正是([一-龥]{2,4})',
            r'来人是([一-龥]{2,4})',
            r'原来(他|她)是([一-龥]{2,4})'
        ]
        for pattern in judgement_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    # 取最后一个元素
                    name = match[-1] if match[-1] else match[0]
                else:
                    name = match
                if name not in self._character_names and self._is_likely_character_name(name):
                    new_characters.append(name)

        # 去重
        new_characters = list(set(new_characters))

        if new_characters:
            self.logger.info(f"检测到可能的新人物: {new_characters}")
        else:
            self.logger.debug("未检测到新人物")

        return new_characters


    def _is_identity_description(self, text: str) -> bool:
        """判断文本是否像身份描述

        Args:
            text: 括号内的文本

        Returns:
            是否为身份描述
        """
        # 身份描述通常包含以下特征
        identity_keywords = [
            "官", "职", "位", "人", "者", "员", "主", "长", "师",
            "大夫", "先生", "公子", "小姐", "夫人", "将军", "统领",
            "掌柜", "老板", "店小二", "侍女", "丫鬟", "管家"
        ]

        # 排除纯数字和纯时间描述
        if text.isdigit() or re.match(r'^第.+章$', text):
            return False

        # 检查是否包含身份关键词
        return any(kw in text for kw in identity_keywords)


    # 中文人名中几乎不可能出现的字符（虚词、语法功能字、标点类字符）
    # 这些字符在中文命名中不存在使用场景，可直接排除含此类字符的候选
    _NON_NAME_CHARACTERS: set = {
        # 结构助词 & 时态
        '的', '了', '着', '过', '得',
        # 介词 & 把字句/被字句
        '把', '被', '给', '让', '叫', '对', '向', '往', '朝', '跟', '比',
        '从', '自', '以', '在', '于', '与', '和', '同',
        # 否定 & 程度
        '不', '没', '很', '太', '更', '最', '非',
        # 疑问 & 代词
        '吗', '呢', '吧', '呀', '嘛', '啊', '哦', '嗯', '唉', '哎', '喂', '嘿', '嗨', '呵',
        '您', '咱', '谁', '哪', '怎', '啥', '咋',
        # 指示代词 & 限定
        '这', '那', '各', '每', '某', '些', '几', '什',
        # 连词 & 逻辑
        '且', '而', '但', '却', '或', '并', '虽', '因', '既', '若',
        # 副词（高频）
        '也', '都', '还', '又', '再', '就', '才', '刚', '已', '曾', '将', '要', '会', '能', '可', '应',
        # 方位词
        '上', '下', '里', '外', '中', '内',
    }

    def _is_likely_character_name(self, name: str) -> bool:
        """判断是否可能是人物名称

        使用多级启发式规则过滤误检：
        - 长度通常在2-4个字符
        - 不含不可能出现在人名中的功能字符
        - 不是常见的非人物词汇
        - 不是代词、动词、形容词等
        - 不含非人名特征词缀
        """
        # 长度检查
        if len(name) < 2 or len(name) > 4:
            return False

        # 检查是否全部是汉字（排除混合字符）
        if not all('\u4e00' <= char <= '\u9fff' for char in name):
            return False

        # 🔴 核心过滤：检查是否包含人名中不可能出现的功能字符
        # 中文人名几乎不会使用虚词、语法功能字、疑问字等
        for char in name:
            if char in self._NON_NAME_CHARACTERS:
                return False

        # 排除常见非人物词汇（大幅扩展）
        non_character_words = {
            # 时间词
            "此时", "这时", "那日", "今日", "当时", "那时", "此刻", "刚才", "现在",
            "之后", "之前", "后来", "原来", "开始", "结束", "终于", "正在",
            # 地点/方位词
            "这里", "那里", "哪里", "前面", "后面", "里面", "外面", "旁边",
            "京城", "城里", "宫中", "府中", "房中", "屋内", "门外",
            # 疑问/代词
            "什么", "怎么", "为何", "如何", "哪里", "谁人", "哪个", "多少",
            "某个", "这些", "那些", "其他", "别的",
            # 副词/连词
            "忽然", "突然", "只见", "只见得", "正是", "原来是", "也就是",
            "但是", "不过", "虽然", "如果", "因为", "所以", "而且",
            # 动词
            "想到", "看到", "听到", "感觉", "觉得", "知道", "明白", "发现",
            "转身", "抬头", "低头", "开口", "闭口", "出手", "动手",
            # 常见误检词汇
            "退烧药", "抗生素", "阿司匹林", "止痛药", "感冒药",  # 药物
            "高热", "发烧", "咳嗽", "头痛", "腹痛", "受伤", "生病",  # 症状
            "铁炮", "火炮", "长剑", "短刀", "弓箭", "盾牌",  # 武器
            "战马", "马车", "轿子", "船只", "汽车", "火车",  # 交通工具
            "终于", "重重", "轻轻", "慢慢", "渐渐", "微微", "暗暗",  # 副词
            "一路", "一起", "一块", "一边", "一面", "一声",  # 数量/状态
            "老者", "少妇", "青年", "少年", "少女", "孩童", "婴儿",  # 泛指人群（无具体名字）
            "大夫", "医生", "将军", "王爷", "丞相", "大人", "公子",  # 职业称呼（无具体名字）
            # ⬇️ false positive 修复：会话常见用语 & 非人名短语
            "恭喜", "多谢", "感谢", "参见", "拜见", "见过", "告辞", "告退",
            "请起", "免礼", "平身", "赐教", "领命", "遵命", "属下", "在下",
            "微臣", "末将", "小人", "臣等", "尔等", "诸位", "各位",
            "退下", "下去", "出去", "进来", "上前", "后退",
            "不负", "不愧", "不敢", "不必", "不用", "不愿",
            "土司", "各寨", "山寨", "衙门", "监牢", "城墙",
            # 多字常见短语（3-4字，易被模式误匹配）
            "一道道", "一阵阵", "一步步", "一点点",
            "臣多谢", "教土司", "臣告退", "微臣告退",
            "抬起头", "低下头", "转过身", "站起来", "坐下来",
            "走上前", "往后退", "朝外走", "往里看",
        }
        if name in non_character_words:
            return False

        # 排除纯代词
        pronouns = {"他", "她", "它", "我", "你", "谁", "某人", "自己", "咱们", "大家",
                     "别人", "旁人", "他人", "本人"}
        if name in pronouns:
            return False

        # 排除以动词后缀结尾的词
        verb_suffixes = ["得", "了", "着", "过", "起", "开", "出", "入", "来", "去"]
        if any(name.endswith(suffix) for suffix in verb_suffixes):
            return False

        # 排除以形容词后缀结尾的词
        adj_suffixes = ["然", "然地", "得很"]
        if any(name.endswith(suffix) for suffix in adj_suffixes):
            return False

        # 排除数字开头的词
        if name[0].isdigit():
            return False

        return True


