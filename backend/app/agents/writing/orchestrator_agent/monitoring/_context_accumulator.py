"""
monitoring/_context_accumulator.py - 扩展上下文累积器

包含 ExtendedContextAccumulator 类，增量维护已知实体信息。

@date: 2026-04-24
@version: v3.0.0
"""
from typing import Any, Dict, List, Set

from app.core.logger import get_logger


class ExtendedContextAccumulator:
    """扩展上下文累积器

    增量维护已知实体信息，避免每次重新遍历所有前文章节。
    章节完成后增量更新，获取时直接返回累积结果。
    """

    def __init__(self):
        """初始化累积器"""
        self.known_facilities: Set[str] = set()
        self.known_groups: Set[str] = set()
        self.known_items: Set[str] = set()
        self.unfinished_events: Set[str] = set()
        self.pending_foreshadows: Set[str] = set()
        self._processed_chapters: Set[int] = set()
        self._logger = get_logger("context_accumulator")

    def update_from_graph(self, graph: "NovelKnowledgeGraph", chapter_num: int) -> None:
        """从图谱增量更新累积器"""
        if chapter_num in self._processed_chapters:
            self._logger.debug(f"章节{chapter_num}已处理，跳过更新")
            return

        try:
            extended_entities = graph.get_extended_state_entities()

            for facility in extended_entities.get("facilities", []):
                name = facility.get("text", "")
                if name:
                    self.known_facilities.add(name)

            for group in extended_entities.get("groups", []):
                name = group.get("text", "")
                if name:
                    self.known_groups.add(name)

            for item in extended_entities.get("items", []):
                name = item.get("text", "")
                if name:
                    self.known_items.add(name)

            for event in extended_entities.get("events", []):
                name = event.get("text", "")
                status = event.get("attributes", {}).get("状态", "")
                if name:
                    if status in ["已完成", "已结束", "已取消"]:
                        self.unfinished_events.discard(name)
                    else:
                        self.unfinished_events.add(name)

            for foreshadow in extended_entities.get("foreshadows", []):
                name = foreshadow.get("text", "")
                if name:
                    self.pending_foreshadows.add(name)

            self._processed_chapters.add(chapter_num)
            self._logger.debug(
                f"累积器更新完成: 章节{chapter_num}, "
                f"设施={len(self.known_facilities)}, "
                f"群体={len(self.known_groups)}, "
                f"道具={len(self.known_items)}"
            )
        except Exception as e:
            self._logger.warning(f"累积器更新失败: 章节{chapter_num}, 错误={e}")

    def sync_from_global_graph(self, graph: "NovelKnowledgeGraph") -> None:
        """从全局图谱同步所有已知实体"""
        try:
            extended_entities = graph.get_extended_state_entities()

            self.known_facilities = {
                f.get("text", "") for f in extended_entities.get("facilities", [])
                if f.get("text")
            }
            self.known_groups = {
                g.get("text", "") for g in extended_entities.get("groups", [])
                if g.get("text")
            }
            self.known_items = {
                i.get("text", "") for i in extended_entities.get("items", [])
                if i.get("text")
            }

            self.unfinished_events = set()
            for event in extended_entities.get("events", []):
                name = event.get("text", "")
                status = event.get("attributes", {}).get("状态", "")
                if name and status not in ["已完成", "已结束", "已取消"]:
                    self.unfinished_events.add(name)

            self.pending_foreshadows = {
                f.get("text", "") for f in extended_entities.get("foreshadows", [])
                if f.get("text")
            }

            self._logger.info(
                f"从全局图谱同步完成: 设施={len(self.known_facilities)}, "
                f"群体={len(self.known_groups)}, "
                f"道具={len(self.known_items)}, "
                f"事件={len(self.unfinished_events)}, "
                f"伏笔={len(self.pending_foreshadows)}"
            )
        except Exception as e:
            self._logger.warning(f"从全局图谱同步失败: {e}")

    def to_dict(self) -> Dict[str, List[str]]:
        """转换为字典格式"""
        return {
            "known_facilities": list(self.known_facilities),
            "known_groups": list(self.known_groups),
            "known_items": list(self.known_items),
            "unfinished_events": list(self.unfinished_events),
            "pending_foreshadows": list(self.pending_foreshadows)
        }

    def reset(self) -> None:
        """重置累积器状态"""
        self.known_facilities.clear()
        self.known_groups.clear()
        self.known_items.clear()
        self.unfinished_events.clear()
        self.pending_foreshadows.clear()
        self._processed_chapters.clear()
        self._logger.debug("累积器已重置")
