"""ProjectKnowledgeBase - get_all_character_states_for_chapterMixin"""
from typing import Dict
from typing import List
from typing import Any
import re
import os


class GetAllCharacterStatesForChapterMixin:
    """get_all_character_states_for_chapter功能域"""

    def get_all_character_states_for_chapter(
        self,
        project_id: int,
        current_unit: int
    ) -> str:
        """
        获取所有人物的状态摘要，用于章节写作提示词

        Args:
            project_id: 项目ID
            current_unit: 当前章节号

        Returns:
            所有人物的状态摘要文本
        """
        try:
            # 1. 从全局图谱获取所有人物
            global_graph_path = self.get_graph_path(
                project_id, unit_number=None)
            if not os.path.exists(global_graph_path):
                return ""

            global_graph = NovelKnowledgeGraph(persist_path=global_graph_path)
            if not global_graph.load():
                return ""

            characters = global_graph.get_entities_by_type("人物")
            if not characters:
                return ""

            # 2. 获取每个人物的状态摘要
            context_parts = ["# 人物状态追踪摘要", ""]
            context_parts.append("以下是各主要人物到目前为止的状态变化，请在写作时保持一致性：")
            context_parts.append("")

            for char in characters[:10]:  # 最多10个人物
                char_name = char.get("name", "")
                if not char_name:
                    continue

                state_text = self.get_character_states_for_writing(
                    project_id, char_name, current_unit
                )
                if state_text and len(state_text) > 50:  # 有实质内容
                    context_parts.append(state_text)
                    context_parts.append("---")
                    context_parts.append("")

            return "\n".join(context_parts)

        except Exception as e:
            self.logger.error(
                f"获取所有人物状态失败: project_id={project_id}, error={str(e)}")
            return ""


    def _resolve_entity_coreference(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        context_content: str = None
    ) -> Dict[str, Any]:
        """
        实体消歧和指代关系解析（后处理步骤）

        解决LLM提取时未能正确处理的指代关系问题：
        - "现代医生" 和 "孙昭龙" 应该是同一个实体
        - 职业称谓 + 人名 格式应该合并为单一实体
        - 同一人物的不同称谓应该统一

        Args:
            entities: LLM提取的实体列表
            relations: LLM提取的关系列表
            context_content: 原始文本内容（可选，用于辅助判断）

        Returns:
            {
                "entities": 消歧后的实体列表,
                "relations": 更新后的关系列表（source/target已更新）,
                "merge_log": 合并日志
            }
        """
        import re

        merge_log = []
        entity_map = {}  # 原始text -> 规范化后的text
        canonical_names = {}  # 规范化text -> 实体数据

        # 第一步：识别人物实体并建立候选合并组
        person_entities = []
        non_person_entities = []

        for entity in entities:
            entity_text = entity.get("text", "")
            entity_type = entity.get("type", "")

            if entity_type == "人物":
                person_entities.append(entity)
            else:
                non_person_entities.append(entity)

        self.logger.info(
            f"实体消歧开始: 人物实体={len(person_entities)}, 非人物实体={len(non_person_entities)}")

        # 第二步：识别需要合并的称谓实体
        alias_patterns = [
            r'^现代医生$',
            r'^古代医生$',
            r'^穿越者$',
            r'^现代人$',
            r'^(?:将军|皇帝|王爷|太子|公主|尚书|丞相|大夫|郎中|秀才|举人|进士|状元)$',
            r'^(?:医生|护士|老师|学生|商人|农民|工匠|武士|侠客|刺客|间谍)$',
            r'^(?:少爷|小姐|夫人|老爷|太太|公子|千金|掌柜|店小二)$',
            r'^[A-Za-z\s]+$'
        ]

        to_merge = []  # (alias_entity, target_entity) 对
        aliases_to_remove = set()

        for i, person_a in enumerate(person_entities):
            text_a = person_a.get("text", "").strip()

            if not text_a or text_a in aliases_to_remove:
                continue

            # 检查是否为称谓/别名模式
            is_alias = False
            for pattern in alias_patterns:
                if re.match(pattern, text_a):
                    is_alias = True
                    break

            if not is_alias:
                continue

            # 查找可能的目标实体（正式名称）
            best_match = None
            best_score = 0

            for j, person_b in enumerate(person_entities):
                if i == j:
                    continue

                text_b = person_b.get("text", "").strip()

                if not text_b or text_b in aliases_to_remove:
                    continue

                # 排除其他别名
                is_b_alias = False
                for pattern in alias_patterns:
                    if re.match(pattern, text_b):
                        is_b_alias = True
                        break

                if is_b_alias:
                    continue

                # 计算匹配分数
                score = self._calculate_alias_match_score(
                    text_a, text_b, context_content)

                if score > best_score and score > 0.3:  # 阈值
                    best_score = score
                    best_match = person_b

            if best_match:
                to_merge.append((person_a, best_match))
                aliases_to_remove.add(text_a)
                merge_log.append(
                    f"合并别名 '{text_a}' → '{best_match.get('text', '')}' (置信度={best_score:.2f})"
                )

        # 第三步：执行合并
        merged_entities = list(non_person_entities)  # 先加入非人物实体

        # 加入未被合并的人物实体
        merged_target_ids = set()
        for _, target in to_merge:
            merged_target_ids.add(id(target))

        for entity in person_entities:
            if entity.get("text", "").strip() not in aliases_to_remove:
                merged_entities.append(entity)

        # 第四步：更新关系的 source/target
        updated_relations = []
        alias_to_canonical = {}

        for alias, target in to_merge:
            alias_text = alias.get("text", "").strip()
            target_text = target.get("text", "").strip()
            alias_to_canonical[alias_text] = target_text

        for relation in relations:
            source = relation.get("source", relation.get("head", ""))
            target = relation.get("target", relation.get("tail", ""))

            # 更新 source
            if source in alias_to_canonical:
                old_source = source
                source = alias_to_canonical[source]
                merge_log.append(f"更新关系源: {old_source} → {source}")

            # 更新 target
            if target in alias_to_canonical:
                old_target = target
                target = alias_to_canonical[target]
                merge_log.append(f"更新关系目标: {old_target} → {target}")

            # 更新关系字典
            if "source" in relation:
                relation["source"] = source
            elif "head" in relation:
                relation["head"] = source

            if "target" in relation:
                relation["target"] = target
            elif "tail" in relation:
                relation["tail"] = target

            updated_relations.append(relation)

        # 第五步：记录结果
        if merge_log:
            self.logger.info(f"实体消歧完成: 合并了{len(to_merge)}个别名实体")
            for log_entry in merge_log[:10]:  # 只记录前10条
                self.logger.debug(f"  - {log_entry}")
        else:
            self.logger.info("实体消歧完成: 未发现需要合并的别名实体")

        return {
            "entities": merged_entities,
            "relations": updated_relations,
            "merge_count": len(to_merge),
            "merge_log": merge_log
        }


    def _calculate_alias_match_score(
        self,
        alias_text: str,
        candidate_text: str,
        context_content: str = None
    ) -> float:
        """
        计算别名与候选实体的匹配分数

        基于以下特征计算：
        1. 文本共现（是否在原文中相邻出现）
        2. 语义相似度（基于关键词）
        3. 实体类型一致性

        Args:
            alias_text: 别名文本（如"现代医生"）
            candidate_text: 候选正式名称（如"孙昭龙"）
            context_content: 原始文本内容

        Returns:
            匹配分数 (0.0 - 1.0)
        """
        score = 0.0

        # 特征1：文本共现检查
        if context_content:
            cooccurrence_patterns = [
                f"{alias_text}{candidate_text}",
                f"{candidate_text}{alias_text}",
                f"{alias_text}，{candidate_text}",
                f"{candidate_text}，{alias_text}",
                f"{alias_text}（{candidate_text}",
                f"{candidate_text}（{alias_text}",
                f"{alias_text}的{candidate_text}",
                f"{alias_text}名为{candidate_text}"
            ]

            for pattern in cooccurrence_patterns:
                if pattern in context_content:
                    score += 0.4
                    break

            # 同一句子中出现
            sentences = re.split(r'[。！？；\n]', context_content)
            for sentence in sentences:
                if alias_text in sentence and candidate_text in sentence:
                    score += 0.3
                    break

        # 特征2：长度合理性（正式名称通常比别长）
        if len(candidate_text) >= len(alias_text):
            score += 0.1

        # 特征3：候选名称不是通用词
        common_words = {"人", "物", "事", "地", "时"}
        if candidate_text not in common_words:
            score += 0.1

        return min(score, 1.0)


