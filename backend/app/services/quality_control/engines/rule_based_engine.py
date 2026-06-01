"""
规则引擎 - 基于正则和统计的文本分析

零Token消耗,快速执行基础质量检查:
- 词频统计(N-gram分析)
- 感官词汇分类
- 段落结构分析
- 时空跳跃检测
- 被动语态检测
- 高频词标记

@date: 2026-04-12
@version: v3.1.0
@author: 周金磊
"""
import re
from collections import Counter
from typing import Dict, List, Any, Tuple

from app.core.logger import get_logger

logger = get_logger("quality_control.rule_engine")


# ==================== 词库定义 ====================

# 感官词汇库
SENSORY_WORDS = {
    "visual": ["看见", "望", "瞧", "盯", "瞥", "瞄", "瞻仰", "环顾", "扫视", "凝视", "注视",
               "红", "蓝", "绿", "黄", "白", "黑", "紫", "橙", "亮", "暗", "明", "晦",
               "大", "小", "高", "低", "长", "短", "圆", "方", "扁"],
    "auditory": ["听", "闻", "声音", "响声", "噪音", "沉默", "寂静", "喧哗", "嘈杂",
                 "喊", "叫", "吼", "啸", "吟", "唱", "说", "讲", "谈", "论", "语", "言",
                 "叮咚", "哗啦", "轰隆", "噼啪", "咕噜", "咕咚"],
    "olfactory": ["嗅", "闻", "气味", "香", "臭", "腥", "膻", "芬芳", "清香", "浓烈",
                  "腐烂", "发霉", "焦糊", "烟味", "血腥"],
    "gustatory": ["尝", " taste", "味道", "甜", "苦", "酸", "辣", "咸", "涩", "麻",
                  "鲜美", "可口", "难吃", "苦涩", "甘甜"],
    "tactile": ["触", "摸", "碰", "撞", "拍", "打", "捏", "掐", "抓", "挠",
                "冷", "热", "温", "凉", "冰", "烫", "软", "硬", "粗糙", "光滑",
                "湿润", "干燥", "粘腻", "清爽"]
}

# 时空跳跃词
TIME_JUMP_WORDS = ["第二天", "第三天", "次日", "隔天", "过了几天", "数日后", "数周后",
                   "数月后", "数年后", "转眼间", "一晃", "忽然", "突然", "霎时", "瞬间",
                   "与此同时", "此时", "那时", "后来", "随后", "接着", "然后"]

SPACE_JUMP_WORDS = ["另一边", "与此同时", "此时", "在那边", "远处", "近处", "前方", "后方",
                    "左侧", "右侧", "楼上", "楼下", "屋内", "屋外", "城里", "城外"]

# 被动语态标记
PASSIVE_PATTERNS = [
    r"被[^\s]{1,10}(?:所)?(?:吓|惊|震|打|骂|批评|表扬|认可|接受|拒绝|发现|告知)",
    r"为[^\s]{1,10}所",
    r"让[^\s]{1,10}(?:给|了)",
    r"叫[^\s]{1,10}(?:给|了)"
]

# 弱动词
WEAK_VERBS = ["进行", "作出", "加以", "给予", "予以", "实施", "开展", "执行", "完成"]

# 常见高频虚词(需要监控但不一定是问题)
COMMON_FILLER_WORDS = ["然后", "接着", "于是", "顿时", "突然", "忽然", "仿佛", "似乎",
                       "微微", "轻轻", "缓缓", "渐渐", "慢慢", "静静", "默默"]


class RuleBasedEngine:
    """
    规则引擎

    基于正则表达式和统计方法执行快速文本分析
    零Token消耗,响应时间<100ms/章
    """

    def __init__(self):
        self._compiled_patterns = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译正则表达式"""
        self._compiled_patterns["passive"] = [
            re.compile(p) for p in PASSIVE_PATTERNS]
        self._compiled_patterns["time_jump"] = re.compile(
            "|".join(TIME_JUMP_WORDS))
        self._compiled_patterns["space_jump"] = re.compile(
            "|".join(SPACE_JUMP_WORDS))

    async def analyze_all(self, chapters_data: List[Dict], dimensions: List[str]) -> Dict[str, Dict]:
        """
        对所有章节执行规则引擎分析

        Args:
            chapters_data: 章节数据列表
            dimensions: 需要分析的维度

        Returns:
            各维度分析结果
        """
        results = {}

        #  prose维度 - 文笔分析
        if "prose" in dimensions:
            results["prose"] = await self._analyze_prose(chapters_data)

        # scene维度 - 场景分析
        if "scene" in dimensions:
            results["scene"] = await self._analyze_scene(chapters_data)

        # technical维度 - 技术排雷(部分)
        if "technical" in dimensions:
            results["technical"] = await self._analyze_technical_rules(chapters_data)

        return results

    async def _analyze_prose(self, chapters_data: List[Dict]) -> Dict:
        """文笔与修辞分析"""
        all_issues = []
        total_words = 0
        word_counter = Counter()
        passive_count = 0
        weak_verb_count = 0

        for chapter in chapters_data:
            content = chapter.get("content", "")
            if not content:
                continue

            total_words += len(content)

            # 1. 词频统计
            words = self._extract_words(content)
            word_counter.update(words)

            # 2. 被动语态检测
            passive_issues = self._detect_passive_voice(content, chapter)
            all_issues.extend(passive_issues)
            passive_count += len(passive_issues)

            # 3. 弱动词检测
            weak_verb_issues = self._detect_weak_verbs(content, chapter)
            all_issues.extend(weak_verb_issues)
            weak_verb_count += len(weak_verb_issues)

            # 4. 段落长度分析
            paragraph_issues = self._analyze_paragraph_length(content, chapter)
            all_issues.extend(paragraph_issues)

        # 5. 高频词分析
        top_words = word_counter.most_common(50)
        filler_issues = self._detect_filler_words(top_words, total_words)
        all_issues.extend(filler_issues)

        # 计算得分
        score = self._calculate_prose_score(
            total_words=total_words,
            passive_count=passive_count,
            weak_verb_count=weak_verb_count,
            filler_issues=len(filler_issues)
        )

        return {
            "score": score,
            "issues": all_issues,
            "statistics": {
                "total_words": total_words,
                "passive_count": passive_count,
                "weak_verb_count": weak_verb_count,
                "top_words": [{"word": w, "count": c} for w, c in top_words[:20]]
            },
            "tokens": 0  # 规则引擎零Token
        }

    async def _analyze_scene(self, chapters_data: List[Dict]) -> Dict:
        """场景与感官分析"""
        all_issues = []
        total_sensory = {"visual": 0, "auditory": 0,
                         "olfactory": 0, "gustatory": 0, "tactile": 0}

        for chapter in chapters_data:
            content = chapter.get("content", "")
            if not content:
                continue

            # 1. 感官词汇统计
            sensory_counts = self._count_sensory_words(content)
            for sense, count in sensory_counts.items():
                total_sensory[sense] += count

            # 2. 时空跳跃检测
            jump_issues = self._detect_time_space_jumps(content, chapter)
            all_issues.extend(jump_issues)

        # 计算感官平衡得分
        sensory_score = self._calculate_sensory_balance(total_sensory)

        # 生成建议
        sensory_issues = self._generate_sensory_suggestions(
            total_sensory, chapters_data)
        all_issues.extend(sensory_issues)

        overall_score = (sensory_score + (100 if not all_issues else 80)) / 2

        return {
            "score": overall_score,
            "issues": all_issues,
            "statistics": {
                "sensory_distribution": total_sensory,
                "sensory_score": sensory_score
            },
            "tokens": 0
        }

    async def _analyze_technical_rules(self, chapters_data: List[Dict]) -> Dict:
        """技术性排雷(规则部分)"""
        all_issues = []

        for chapter in chapters_data:
            content = chapter.get("content", "")
            if not content:
                continue

            # 视角越界检测(基础规则)
            pov_issues = self._detect_pov_violations(content, chapter)
            all_issues.extend(pov_issues)

        score = 100 if not all_issues else max(50, 100 - len(all_issues) * 10)

        return {
            "score": score,
            "issues": all_issues,
            "statistics": {"pov_violations": len(all_issues)},
            "tokens": 0
        }

    # ==================== 具体检测方法 ====================

    def _extract_words(self, text: str) -> List[str]:
        """提取中文词语(简化版,按2-4字分组)"""
        # 移除标点
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z]', '', text)

        # 提取2-4字词组
        words = []
        for i in range(len(text) - 1):
            words.append(text[i:i+2])  # 2字词
            if i < len(text) - 2:
                words.append(text[i:i+3])  # 3字词

        return words

    def _detect_passive_voice(self, content: str, chapter: Dict) -> List[Dict]:
        """检测被动语态"""
        issues = []

        for pattern in self._compiled_patterns["passive"]:
            for match in pattern.finditer(content):
                start = max(0, match.start() - 20)
                end = min(len(content), match.end() + 20)
                context = content[start:end]

                issues.append({
                    "id": f"PAS-{len(issues)+1}",
                    "dimension": "prose",
                    "category": "被动语态",
                    "severity": "info",
                    "location": {"chapter_id": chapter["id"], "chapter_number": chapter["chapter_number"]},
                    "description": "检测到被动语态,建议改为主动语态以增强表现力",
                    "evidence": context,
                    "suggestion": f"将'{match.group()}'改为主动语态,如'他突然感到恐惧'→'恐惧如潮水般涌来'",
                    "metadata": {"position": match.start()}
                })

        return issues[:10]  # 最多返回10个

    def _detect_weak_verbs(self, content: str, chapter: Dict) -> List[Dict]:
        """检测弱动词"""
        issues = []

        for verb in WEAK_VERBS:
            pattern = re.compile(re.escape(verb))
            for match in pattern.finditer(content):
                start = max(0, match.start() - 15)
                end = min(len(content), match.end() + 15)
                context = content[start:end]

                issues.append({
                    "id": f"WV-{len(issues)+1}",
                    "dimension": "prose",
                    "category": "弱动词",
                    "severity": "info",
                    "location": {"chapter_id": chapter["id"], "chapter_number": chapter["chapter_number"]},
                    "description": f"检测到弱动词'{verb}',建议使用更具体的动作词",
                    "evidence": context,
                    "suggestion": f"将'进行攻击'改为'发起攻击'或直接使用'攻击'",
                    "metadata": {"verb": verb, "position": match.start()}
                })

        return issues[:10]

    def _analyze_paragraph_length(self, content: str, chapter: Dict) -> List[Dict]:
        """分析段落长度"""
        issues = []
        paragraphs = content.split("\n\n")

        for i, para in enumerate(paragraphs):
            para_len = len(para.strip())
            if para_len > 400:  # 超过400字为大段落
                issues.append({
                    "id": f"PL-{len(issues)+1}",
                    "dimension": "prose",
                    "category": "段落过长",
                    "severity": "warning",
                    "location": {
                        "chapter_id": chapter["id"],
                        "chapter_number": chapter["chapter_number"],
                        "paragraph": i + 1
                    },
                    "description": f"检测到{para_len}字的长段落,手机端阅读体验不佳",
                    "evidence": para[:100] + "...",
                    "suggestion": "建议在对话处、动作切换处分段,增加留白",
                    "metadata": {"paragraph_length": para_len}
                })

        return issues[:5]

    def _detect_filler_words(self, top_words: List[Tuple[str, int]], total_words: int) -> List[Dict]:
        """检测高频虚词"""
        issues = []

        for word, count in top_words:
            if word in COMMON_FILLER_WORDS and count > 10:
                frequency = count / max(total_words / 1000, 1)  # 每千字频率

                if frequency > 3:  # 每千字超过3次
                    issues.append({
                        "id": f"FW-{word}",
                        "dimension": "prose",
                        "category": "高频词疲劳",
                        "severity": "warning",
                        "location": {},
                        "description": f"词汇'{word}'出现{count}次,每千字{frequency:.1f}次,使用过于频繁",
                        "evidence": f"全文出现{count}次",
                        "suggestion": f"建议将50%的'{word}'替换为具体描写或其他表达方式",
                        "metadata": {"word": word, "count": count, "frequency": frequency}
                    })

        return issues

    def _count_sensory_words(self, content: str) -> Dict[str, int]:
        """统计感官词汇"""
        counts = {sense: 0 for sense in SENSORY_WORDS}

        for sense, words in SENSORY_WORDS.items():
            for word in words:
                counts[sense] += content.count(word)

        return counts

    def _detect_time_space_jumps(self, content: str, chapter: Dict) -> List[Dict]:
        """检测时空跳跃"""
        issues = []

        # 检测时间跳跃
        time_matches = list(
            self._compiled_patterns["time_jump"].finditer(content))
        space_matches = list(
            self._compiled_patterns["space_jump"].finditer(content))

        # 检查跳跃前后是否有过渡
        for match in time_matches[:5]:  # 最多检查5个
            pos = match.start()
            # 检查前后50字是否有过渡词
            context_start = max(0, pos - 50)
            context_end = min(len(content), pos + 50)
            context = content[context_start:context_end]

            # 简单判断:如果跳跃词前后都是独立段落,可能缺少过渡
            if "\n\n" in context:
                issues.append({
                    "id": f"TSJ-{len(issues)+1}",
                    "dimension": "scene",
                    "category": "时空跳跃",
                    "severity": "warning",
                    "location": {"chapter_id": chapter["id"], "chapter_number": chapter["chapter_number"]},
                    "description": f"检测到时间跳跃词'{match.group()}',可能缺少过渡",
                    "evidence": context,
                    "suggestion": "建议增加过渡句或分隔符(***)帮助读者理解时空转换",
                    "metadata": {"jump_word": match.group(), "position": pos}
                })

        return issues

    def _detect_pov_violations(self, content: str, chapter: Dict) -> List[Dict]:
        """基础视角越界检测"""
        issues = []

        # 第一人称中检测第三人称心理描写
        if "我" in content[:1000]:  # 简单判断是否为第一人称
            pov_patterns = [
                r"他心想[：:]",
                r"她暗自思忖",
                r"他想到了",
                r"她觉得"
            ]

            for pattern in pov_patterns:
                for match in re.finditer(pattern, content):
                    issues.append({
                        "id": f"POV-{len(issues)+1}",
                        "dimension": "technical",
                        "category": "视角越界",
                        "severity": "critical",
                        "location": {"chapter_id": chapter["id"], "chapter_number": chapter["chapter_number"]},
                        "description": "第一人称叙事中检测到第三人称心理描写",
                        "evidence": match.group(),
                        "suggestion": "第一人称'我'无法得知他人心理,建议改为通过动作/表情暗示",
                        "metadata": {"violation": match.group()}
                    })

        return issues

    # ==================== 评分计算 ====================

    def _calculate_prose_score(self, total_words: int, passive_count: int,
                               weak_verb_count: int, filler_issues: int) -> float:
        """计算文笔得分"""
        if total_words == 0:
            return 50.0

        score = 100.0

        # 被动语态扣分
        passive_rate = passive_count / max(total_words / 1000, 1)
        score -= min(20, passive_rate * 5)

        # 弱动词扣分
        weak_verb_rate = weak_verb_count / max(total_words / 1000, 1)
        score -= min(15, weak_verb_rate * 3)

        # 高频词扣分
        score -= min(15, filler_issues * 3)

        return max(0, min(100, score))

    def _calculate_sensory_balance(self, sensory_counts: Dict[str, int]) -> float:
        """计算感官平衡得分"""
        total = sum(sensory_counts.values())
        if total == 0:
            return 30.0

        # 计算各感官占比
        ratios = {sense: count / total for sense,
                  count in sensory_counts.items()}

        # 理想状态: 视觉40%, 听觉25%, 其他各10-15%
        ideal = {"visual": 0.4, "auditory": 0.25,
                 "olfactory": 0.12, "gustatory": 0.10, "tactile": 0.13}

        # 计算偏差
        deviation = sum(abs(ratios.get(s, 0) - ideal[s]) for s in ideal)

        # 偏差越小得分越高
        score = max(0, 100 - deviation * 100)

        return score

    def _generate_sensory_suggestions(self, sensory_counts: Dict[str, int],
                                      chapters_data: List[Dict]) -> List[Dict]:
        """生成感官描写建议"""
        issues = []
        total = sum(sensory_counts.values())

        if total == 0:
            return issues

        # 检查缺失的感官
        # 感官分析是跨章节的全局分析，以第一个章节的 chapter_number 作为参考定位
        reference_chapter = chapters_data[0] if chapters_data else {}
        ref_chapter_number = reference_chapter.get("chapter_number", 0)
        ref_chapter_id = reference_chapter.get("id", 0)

        for sense, count in sensory_counts.items():
            if count == 0:
                sense_names = {
                    "visual": "视觉",
                    "auditory": "听觉",
                    "olfactory": "嗅觉",
                    "gustatory": "味觉",
                    "tactile": "触觉"
                }

                location_data = {}
                if ref_chapter_number:
                    location_data["chapter_number"] = ref_chapter_number
                if ref_chapter_id:
                    location_data["chapter_id"] = ref_chapter_id

                issues.append({
                    "id": f"SENS-{sense}",
                    "dimension": "scene",
                    "category": "感官缺失",
                    "severity": "warning",
                    "location": location_data,
                    "description": f"全文缺乏{sense_names[sense]}描写",
                    "evidence": f"{sense_names[sense]}词汇出现0次",
                    "suggestion": f"建议添加2-3处{sense_names[sense]}描写增强沉浸感",
                    "metadata": {"sense": sense}
                })

        return issues
