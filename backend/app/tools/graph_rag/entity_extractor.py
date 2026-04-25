"""规则和关键词实体提取器"""
from typing import List, Dict, Any
import re


class EntityExtractor:
    """实体提取器（基于规则和关键词）"""

    def __init__(self):
        # 预定义的实体类型和关键词
        self.entity_patterns = {
            "人物": [
                "导演", "编剧", "演员", "主角", "配角", "主持人", "创作者",
                "用户", "观众", "读者", "客户", "消费者", "目标受众"
            ],
            "作品": [
                "电影", "电视剧", "短视频", "小说", "剧本", "广告", "文案",
                "视频", "文章", "故事", "脚本", "作品"
            ],
            "风格": [
                "幽默", "搞笑", "温馨", "感人", "悬疑", "科幻", "爱情",
                "动作", "励志", "治愈", "反差", "复古", "现代"
            ],
            "平台": [
                "抖音", "快手", "B站", "小红书", "视频号", "微博",
                "YouTube", "TikTok", "微信公众号"
            ],
            "品牌": [
                "品牌", "产品", "服务", "公司", "企业", "商标"
            ],
            "场景": [
                "开场", "结尾", "高潮", "转折", "冲突", "悬念",
                "场景", "情节", "桥段"
            ],
            "情感": [
                "快乐", "悲伤", "愤怒", "恐惧", "惊讶", "期待",
                "共鸣", "感动", "紧张"
            ],
            "技术": [
                "运镜", "剪辑", "配乐", "特效", "字幕", "滤镜",
                "转场", "节奏", "画面"
            ]
        }

        # 关系模式
        self.relation_patterns = [
            (r"(.+?)是(.+?)的(.+)", "属性关系"),
            (r"(.+?)包含(.+)", "包含关系"),
            (r"(.+?)属于(.+)", "属于关系"),
            (r"(.+?)导致(.+)", "因果关系"),
            (r"(.+?)影响(.+)", "影响关系"),
            (r"(.+?)与(.+?)相关", "相关关系"),
        ]

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中提取实体

        Args:
            text: 输入文本

        Returns:
            实体列表 [{"text": "导演", "type": "人物", "start": 0, "end": 2}]
        """
        entities = []

        for entity_type, keywords in self.entity_patterns.items():
            for keyword in keywords:
                start = 0
                while True:
                    pos = text.find(keyword, start)
                    if pos == -1:
                        break
                    entities.append({
                        "text": keyword,
                        "type": entity_type,
                        "start": pos,
                        "end": pos + len(keyword)
                    })
                    start = pos + 1

        # 去重
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e["text"], e["start"])
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)

        return unique_entities

    def extract_relations(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从文本中提取实体间关系

        Args:
            text: 输入文本
            entities: 已提取的实体列表

        Returns:
            关系列表 [{"source": "实体1", "target": "实体2", "relation": "关系类型"}]
        """
        relations = []

        # 基于模式匹配
        for pattern, relation_type in self.relation_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    relations.append({
                        "source": groups[0].strip(),
                        "target": groups[-1].strip() if len(groups) > 2 else groups[1].strip(),
                        "relation": relation_type,
                        "context": match.group(0)
                    })

        # 基于实体共现（同一句中的实体存在关联）
        sentences = re.split(r'[。！？\n]', text)
        for sentence in sentences:
            sentence_entities = []
            for e in entities:
                if e["start"] >= text.find(sentence) and e["end"] <= text.find(sentence) + len(sentence):
                    sentence_entities.append(e["text"])

            # 句中相邻实体建立关联
            for i in range(len(sentence_entities) - 1):
                relations.append({
                    "source": sentence_entities[i],
                    "target": sentence_entities[i + 1],
                    "relation": "共现关系",
                    "context": sentence[:50]
                })

        return relations
