"""CharacterStateTracker - check_consistencyMixin"""
from __future__ import annotations
from typing import Dict
from typing import Any
import re

# 🆕 生死状态关键词（用于检测"已死复生"冲突）
_DECEASE_KEYWORDS = ["死亡", "战死", "牺牲", "逝世", "离世", "被杀", "处决", "殒命", "毙命"]
_DEPARTURE_KEYWORDS = ["离开", "远走", "失踪", "退场", "暂别", "隐退", "消失"]
# 🆕 身份突变显著词（用于检测身份断崖式变化）
_IDENTITY_JUMP_INDICATORS = ["晋升", "登基", "即位", "册封", "废黜", "篡位", "入主"]


class CheckConsistencyMixin:
    """check_consistency功能域

    v2.0: 扩展到5个检查维度（位置/身份/关系/能力/生死），
    每个检查附带内容中的evidence引用。
    """

    def check_consistency(
        self,
        chapter_num: int,
        content: str
    ) -> Dict[str, Any]:
        """检查人物状态一致性

        检查以下方面：
        1. 人物位置是否合理（是否在合理时间内到达）
        2. 人物身份是否与设定一致（新增 v2.0）
        3. 人物关系变化是否合理（新增 v2.0）
        4. 人物能力是否跳跃过大（新增 v2.0）
        5. 已死亡/退场人物是否错误复出（新增 v2.0）
        6. 新人物是否有冲突

        Args:
            chapter_num: 章节号
            content: 章节内容

        Returns:
            检查结果，包含issues和warnings
        """
        result = {
            "issues": [],
            "warnings": [],
            "passed": True
        }

        # 获取前一章状态作为参考
        prev_snapshot = self._chapter_snapshots.get(chapter_num - 1)
        if not prev_snapshot:
            return result

        # 检查每个出场人物
        for name, prev_state in prev_snapshot.characters.items():
            if name not in content:
                continue

            current_state = self._character_states.get(name)
            if not current_state:
                continue

            # ---- 检查1: 位置合理性 ----
            if prev_state.location and current_state.location:
                if prev_state.location != current_state.location:
                    # 位置变化，检查是否有过渡
                    if prev_state.location not in content and current_state.location not in content:
                        result["warnings"].append({
                            "type": "location_transition_missing",
                            "character": name,
                            "from_location": prev_state.location,
                            "to_location": current_state.location,
                            "message": f"人物'{name}'从'{prev_state.location}'到'{current_state.location}'的位置变化缺少过渡描述",
                            "evidence": self._find_content_snippet(content, name, window=100)
                        })

            # ---- 检查2: 身份一致性 (新增 v2.0) ----
            if prev_state.identity and current_state.identity:
                if prev_state.identity != current_state.identity:
                    # 身份变化，检查内容中是否有明确的身份转变描述
                    identity_changed_in_content = any(
                        kw in content for kw in _IDENTITY_JUMP_INDICATORS
                    )
                    if not identity_changed_in_content:
                        result["warnings"].append({
                            "type": "identity_change_unexplained",
                            "character": name,
                            "from_identity": prev_state.identity,
                            "to_identity": current_state.identity,
                            "message": f"人物'{name}'的身份从'{prev_state.identity}'变为'{current_state.identity}'，但内容中未发现合理的身份转变描述",
                            "evidence": self._find_content_snippet(content, name, window=120)
                        })

            # ---- 检查3: 关系一致性 (新增 v2.0) ----
            prev_rels = prev_state.relationships or {}
            curr_rels = current_state.relationships or {}
            for rel_name, rel_type in curr_rels.items():
                prev_rel = prev_rels.get(rel_name)
                if prev_rel and prev_rel != rel_type:
                    # 关系从A变为B，检查是否有过渡事件
                    # 简化的乐观判断：仅当关系翻转（敌对↔友好）时报警
                    hostile_terms = ["敌对", "仇敌", "死敌", "敌人", "对手"]
                    friendly_terms = ["友好", "朋友", "盟友", "知己", "恋人", "亲人", "师徒"]
                    prev_is_hostile = any(t in prev_rel for t in hostile_terms) or not any(t in prev_rel for t in friendly_terms)
                    curr_is_friendly = any(t in rel_type for t in friendly_terms)
                    prev_is_friendly = any(t in prev_rel for t in friendly_terms)
                    curr_is_hostile = any(t in rel_type for t in hostile_terms)

                    if (prev_is_hostile and curr_is_friendly) or (prev_is_friendly and curr_is_hostile):
                        result["warnings"].append({
                            "type": "relationship_flip_unexplained",
                            "character": name,
                            "related_to": rel_name,
                            "from_relation": prev_rel,
                            "to_relation": rel_type,
                            "message": f"人物'{name}'与'{rel_name}'的关系从'{prev_rel}'突变为'{rel_type}'，建议确认是否有合理的情节铺垫",
                            "evidence": self._find_content_snippet(content, name, window=150)
                        })

            # ---- 检查4: 能力一致性 (新增 v2.0) ----
            prev_ability = prev_state.attributes.get("ability", "") if prev_state.attributes else ""
            curr_ability = current_state.attributes.get("ability", "") if current_state.attributes else ""
            if prev_ability and curr_ability and prev_ability != curr_ability:
                # 能力级别跳跃检测
                ability_levels = ["初窥", "入门", "小成", "精通", "大成", "圆满", "宗师", "超凡", "入圣"]
                prev_level_idx = _find_ability_level(prev_ability, ability_levels)
                curr_level_idx = _find_ability_level(curr_ability, ability_levels)
                if prev_level_idx >= 0 and curr_level_idx >= 0 and (curr_level_idx - prev_level_idx) >= 3:
                    result["warnings"].append({
                        "type": "ability_jump_too_large",
                        "character": name,
                        "from_ability": prev_ability,
                        "to_ability": curr_ability,
                        "message": f"人物'{name}'的能力从'{prev_ability}'跳至'{curr_ability}'，跨度超过3级，建议确认是否有充分铺垫",
                        "evidence": self._find_content_snippet(content, name, window=120)
                    })

            # ---- 检查5: 生死一致性 (新增 v2.0) ----
            from app.agents.writing.character_state_tracker.api import CharacterStatus
            # 前文已死亡或退场的人物不应再次出场（除非明确复活/回归）
            if prev_state.status in (CharacterStatus.DECEASED, CharacterStatus.DEPARTED):
                revival_keywords = ["复活", "重生", "归来", "重返", "回归", "再现"]
                has_revival = any(kw in content for kw in revival_keywords)
                if not has_revival:
                    status_label = "死亡" if prev_state.status == CharacterStatus.DECEASED else "退场"
                    result["issues"].append({
                        "type": "deceased_departed_reappear",
                        "character": name,
                        "prev_status": prev_state.status.value,
                        "message": f"人物'{name}'前文明确定{status_label}，但在本章重新出场且无复活/回归说明，存在严重逻辑冲突",
                        "evidence": self._find_content_snippet(content, name, window=100)
                    })

        if result["issues"]:
            result["passed"] = False

        return result

    # ---- 辅助方法 (v2.0 新增) ----

    @staticmethod
    def _find_content_snippet(content: str, keyword: str, window: int = 100) -> str:
        """从内容中提取包含关键词的上下文片段

        Args:
            content: 完整内容
            keyword: 要查找的关键词
            window: 上下文窗口大小（字符数）

        Returns:
            包含关键词的片段（最多 window*2 字符）
        """
        if not content or not keyword:
            return ""
        idx = content.find(keyword)
        if idx < 0:
            return ""
        start = max(0, idx - window // 2)
        end = min(len(content), idx + len(keyword) + window // 2)
        snippet = content[start:end].strip()
        if start > 0:
            snippet = "…" + snippet
        if end < len(content):
            snippet = snippet + "…"
        return snippet


def _find_ability_level(ability_str: str, levels: list) -> int:
    """从能力描述字符串中匹配等级索引

    Args:
        ability_str: 能力描述（如"剑术大成"、"修为入门"）
        levels: 等级关键词列表（从低到高）

    Returns:
        匹配到的等级索引，未匹配返回 -1
    """
    for i, level in enumerate(levels):
        if level in ability_str:
            return i
    return -1
