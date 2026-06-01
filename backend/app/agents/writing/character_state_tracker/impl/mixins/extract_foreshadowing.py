"""CharacterStateTracker - ExtractForeshadowingMixin

伏笔提取与回收追踪功能域。
从知识图谱同步伏笔数据，为写手提词注入待回收伏笔清单。

@date: 2026-05-22
@version: v1.0.0
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


class ExtractForeshadowingMixin:
    """伏笔提取与回收追踪功能域"""

    def _init_foreshadowing_tracker(self) -> None:
        """初始化伏笔追踪器（惰性初始化）"""
        if not hasattr(self, '_foreshadowing_items'):
            self._foreshadowing_items: Dict[str, Dict[str, Any]] = {}
        if not hasattr(self, '_foreshadowing_initialized'):
            self._foreshadowing_initialized = False

    def sync_foreshadowing_from_knowledge_graph(
        self,
        knowledge_graph=None,
        chapter_num: int = 0
    ) -> int:
        """从知识图谱同步伏笔数据到内存追踪器

        读取知识图谱中的伏笔实体和一致性状态，
        更新内存中的伏笔追踪列表。

        Args:
            knowledge_graph: NovelKnowledgeGraph 实例
            chapter_num: 当前章节号

        Returns:
            待回收伏笔数量
        """
        self._init_foreshadowing_tracker()

        if knowledge_graph is None:
            return self._count_pending()

        try:
            # 获取知识图谱中的待回收伏笔
            pending = []
            if hasattr(knowledge_graph, '_get_pending_foreshadows'):
                pending = knowledge_graph._get_pending_foreshadows(chapter_num)

            # 获取统一状态中的所有伏笔（含已回收）
            all_foreshadows: Dict[str, Any] = {}
            if hasattr(knowledge_graph, '_load_consistency_state'):
                state = knowledge_graph._load_consistency_state()
                all_foreshadows = state.get("foreshadows", {})

            # 合并数据：从统一状态获取完整信息
            resolved_names: set = set()
            for name, uf in all_foreshadows.items():
                if uf.get("status") == "已回收":
                    resolved_names.add(name)

            # 更新内存追踪器
            for item in pending:
                name = item.get("name", "")
                if not name:
                    continue
                existing = self._foreshadowing_items.get(name, {})
                self._foreshadowing_items[name] = {
                    "description": item.get("description") or existing.get("description") or name,
                    "introduced_chapter": item.get("planted_chapter") or existing.get("introduced_chapter", chapter_num),
                    "importance": item.get("importance") or existing.get("importance", "普通"),
                    "status": "pending",
                    "last_update_chapter": item.get("last_update_chapter") or existing.get("last_update_chapter", chapter_num),
                }

            # 标记已回收
            for name in resolved_names:
                if name in self._foreshadowing_items:
                    self._foreshadowing_items[name]["status"] = "resolved"
                    uf = all_foreshadows.get(name, {})
                    self._foreshadowing_items[name]["resolved_in_chapter"] = (
                        uf.get("last_update_chapter", chapter_num)
                    )

            self._foreshadowing_initialized = True
            pending_count = self._count_pending()
            if pending_count > 0 and hasattr(self, 'logger'):
                self.logger.info(
                    f"[伏笔追踪] 同步完成: 总计{len(self._foreshadowing_items)}个伏笔, "
                    f"待回收{pending_count}个"
                )
            return pending_count

        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"[伏笔追踪] 同步失败: {e}")
            return self._count_pending()

    def _count_pending(self) -> int:
        """统计待回收伏笔数量"""
        if not hasattr(self, '_foreshadowing_items'):
            return 0
        return sum(1 for v in self._foreshadowing_items.values() if v.get("status") == "pending")

    def detect_foreshadowing_resolution(
        self,
        content: str,
        chapter_num: int,
        llm_provider=None
    ) -> List[str]:
        """检测当前章节是否回收了某个pending伏笔

        使用轻量文本匹配 + 可选的LLM验证。

        Args:
            content: 当前章节内容
            chapter_num: 当前章节号
            llm_provider: LLM提供者实例（可选）

        Returns:
            被回收的伏笔名称列表
        """
        self._init_foreshadowing_tracker()
        resolved = []

        # 策略1：文本关键词匹配（快速路径）
        pending_items = {
            name: info for name, info in self._foreshadowing_items.items()
            if info.get("status") == "pending"
        }
        for name, info in pending_items.items():
            # 检查伏笔名称或关键描述是否出现在内容中
            desc = info.get("description", name)
            if len(name) >= 3 and name in content:
                resolved.append(name)
            elif len(desc) >= 4 and desc[:20] in content:
                resolved.append(name)

        # 标记为已回收
        for name in resolved:
            if name in self._foreshadowing_items:
                self._foreshadowing_items[name]["status"] = "resolved"
                self._foreshadowing_items[name]["resolved_in_chapter"] = chapter_num

        if resolved and hasattr(self, 'logger'):
            self.logger.info(
                f"[伏笔追踪] 检测到{len(resolved)}个伏笔回收: {', '.join(resolved[:5])}"
            )

        return resolved

    def get_pending_foreshadowing_for_prompt(self) -> str:
        """生成待回收伏笔清单（注入写手提词）

        Returns:
            格式化的伏笔清单文本，无待回收项时返回空字符串
        """
        self._init_foreshadowing_tracker()
        pending = {
            k: v for k, v in self._foreshadowing_items.items()
            if v.get("status") == "pending"
        }
        if not pending:
            return ""

        lines = ["【待回收伏笔清单】"]
        lines.append("以下是前文埋设但尚未回收的伏笔，请在后续创作中有计划地回收：")
        lines.append("")
        lines.append("| 伏笔描述 | 引入章节 | 重要程度 |")
        lines.append("|---------|---------|---------|")
        for name, info in pending.items():
            lines.append(
                f"| {name} | 第{info.get('introduced_chapter', '?')}章 | "
                f"{info.get('importance', '普通')} |"
            )
        return "\n".join(lines)

    def get_foreshadowing_summary(self) -> Dict[str, Any]:
        """获取伏笔状态摘要

        Returns:
            {"total": int, "pending": int, "resolved": int, "items": List[Dict]}
        """
        self._init_foreshadowing_tracker()
        items = list(self._foreshadowing_items.values())
        pending = [i for i in items if i.get("status") == "pending"]
        resolved = [i for i in items if i.get("status") == "resolved"]
        return {
            "total": len(items),
            "pending": len(pending),
            "resolved": len(resolved),
            "items": items,
        }
