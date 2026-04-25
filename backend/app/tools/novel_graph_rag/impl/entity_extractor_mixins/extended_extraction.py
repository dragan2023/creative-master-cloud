"""NovelEntityExtractor - 扩展状态提取Mixin"""
import asyncio
from typing import Dict, Any, List

from app.tools.novel_graph_rag.constants import (
    CHARACTER_STATE_MAX_ENTITIES,
    CHARACTER_STATE_MAX_RELATIONS,
)
from app.tools.novel_graph_rag.prompts import EXTENDED_STATE_EXTRACTION_PROMPT


class ExtendedExtractionMixin:
    """扩展状态提取功能域"""

    async def extract_extended_states(
        self,
        chapter_content: str,
        chapter_num: int,
        context_info: Dict[str, Any] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        提取章节中的扩展状态实体（设施、事件、群体、道具、世界规则、时间线、伏笔）

        用于提取除人物状态外的一致性相关实体，支持更全面的一致性追踪。

        Args:
            chapter_content: 章节内容
            chapter_num: 章节号
            context_info: 上下文信息（可选，包含已知实体列表等）
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...], "consistency_notes": [...], "chapter": chapter_num}
        """
        last_error = None

        # 使用扩展状态提取的配置
        max_entities = CHARACTER_STATE_MAX_ENTITIES + 10
        max_relations = CHARACTER_STATE_MAX_RELATIONS + 15

        for attempt in range(max_retries):
            try:
                # 构建上下文提示
                context_prompt = ""
                if context_info:
                    if context_info.get("known_facilities"):
                        context_prompt += f"\n**已知设施：** {', '.join(context_info['known_facilities'][:5])}"
                    if context_info.get("known_groups"):
                        context_prompt += f"\n**已知群体：** {', '.join(context_info['known_groups'][:5])}"
                    if context_info.get("known_items"):
                        context_prompt += f"\n**已知道具：** {', '.join(context_info['known_items'][:5])}"
                    if context_info.get("unfinished_events"):
                        context_prompt += f"\n**未完成事件：** {', '.join(context_info['unfinished_events'][:5])}"
                    if context_info.get("pending_foreshadows"):
                        context_prompt += f"\n**待回收伏笔：** {', '.join(context_info['pending_foreshadows'][:5])}"

                prompt = EXTENDED_STATE_EXTRACTION_PROMPT.format(
                    max_entities=max_entities,
                    max_relations=max_relations,
                    chapter_num=chapter_num,
                    content=f"{context_prompt}\n\n{chapter_content}"
                )

                max_output_tokens = self.llm_provider.get_max_output_tokens()

                response = await self.llm_provider.generate(
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=max_output_tokens
                )

                if not response or not hasattr(response, 'content') or response.content is None:
                    self.logger.warning(
                        f"扩展状态提取返回无效响应，尝试 {attempt+1}/{max_retries}")
                    continue

                # 解析响应
                result = self._parse_llm_response(response.content)
                if result:
                    # 为实体添加章节号
                    for entity in result.get("entities", []):
                        if "chapter" not in entity:
                            entity["chapter"] = chapter_num

                    # 质量验证
                    validated_result = self._validate_extended_state_result(
                        result, chapter_num
                    )

                    self.logger.info(
                        f"扩展状态提取成功: 章节{chapter_num}, "
                        f"实体数={len(validated_result.get('entities', []))}, "
                        f"关系数={len(validated_result.get('relations', []))}, "
                        f"一致性提示={len(validated_result.get('consistency_notes', []))}")

                    validated_result["chapter"] = chapter_num
                    return validated_result

                self.logger.warning(f"JSON解析失败，尝试 {attempt+1}/{max_retries}")

            except Exception as e:
                error_str = str(e)
                last_error = e

                is_rate_limit = '429' in error_str or 'rate' in error_str.lower()

                if is_rate_limit:
                    wait_time = 10 * (2 ** attempt)
                    self.logger.warning(
                        f"API限流，等待 {wait_time}秒 后重试...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                else:
                    self.logger.warning(f"扩展状态提取异常: {error_str[:200]}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)

        self.logger.error(
            f"扩展状态提取失败: 章节{chapter_num}. 最后错误: {str(last_error)[:200] if last_error else 'None'}")

        return {
            "entities": [],
            "relations": [],
            "consistency_notes": [],
            "chapter": chapter_num,
            "_extraction_failed": True
        }

    def _validate_extended_state_result(
        self,
        result: Dict[str, Any],
        chapter_num: int
    ) -> Dict[str, Any]:
        """验证扩展状态提取结果的质量"""
        validated_entities = []
        validated_relations = []
        consistency_notes = result.get("consistency_notes", [])
        issues_found = []

        extended_entity_types = {
            # 设施相关
            "设施", "设施状态变化", "设施归属变更", "设施物理状态",
            # 事件相关
            "事件", "事件状态变化", "事件影响", "事件因果链",
            # 群体相关
            "群体组织", "群体状态变化", "群体成员变动", "群体关系变化",
            # 道具相关
            "道具物品", "道具状态变化", "道具归属变更", "道具功能使用",
            # 世界规则
            "世界规则", "规则引用", "规则例外",
            # 时间线
            "时间节点", "时间流逝",
            # 伏笔
            "伏笔", "伏笔回收"
        }

        # 验证实体
        for entity in result.get("entities", []):
            if not isinstance(entity, dict):
                issues_found.append(f"跳过非字典类型的实体: {type(entity).__name__}")
                self.logger.warning(
                    f"扩展状态实体类型错误，跳过: {type(entity).__name__}, 值: {str(entity)[:50]}")
                continue

            entity_type = entity.get("type", "")

            if entity_type not in extended_entity_types:
                issues_found.append(f"跳过非扩展类型实体: {entity_type}")
                continue

            if not entity.get("text"):
                entity["text"] = f"{entity_type} - 章节{chapter_num}"
                issues_found.append("补充text字段")

            if not entity.get("description") or len(entity.get("description", "")) < 5:
                entity["description"] = entity.get("text", "")
            if "level" not in entity:
                macro_types = {"设施", "事件", "群体组织", "道具物品", "世界规则", "时间节点"}
                entity["level"] = "macro" if entity_type in macro_types else "micro"

            validated_entities.append(entity)

        # 验证关系
        for relation in result.get("relations", []):
            if not isinstance(relation, dict):
                issues_found.append(f"跳过非字典类型的关系: {type(relation).__name__}")
                self.logger.warning(
                    f"扩展状态关系类型错误，跳过: {type(relation).__name__}, 值: {str(relation)[:50]}")
                continue

            if not relation.get("source") or not relation.get("target"):
                issues_found.append("跳过不完整的关系")
                continue

            if not relation.get("relation"):
                relation["relation"] = "关联"

            validated_relations.append(relation)

        if issues_found:
            self.logger.debug(
                f"扩展状态质量验证: 章节{chapter_num}, "
                f"问题数={len(issues_found)}, "
                f"有效实体={len(validated_entities)}, 有效关系={len(validated_relations)}")

        return {
            "entities": validated_entities,
            "relations": validated_relations,
            "consistency_notes": consistency_notes,
            "_validation_issues": len(issues_found)
        }
