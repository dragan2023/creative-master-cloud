"""NovelEntityExtractor - 人物状态提取Mixin"""
import re
import asyncio
from typing import Dict, Any, Optional, List

from app.tools.novel_graph_rag.constants import (
    CHARACTER_STATE_MAX_ENTITIES,
    CHARACTER_STATE_MAX_RELATIONS,
)
from app.tools.novel_graph_rag.prompts import CHARACTER_STATE_EXTRACTION_PROMPT


class CharacterExtractionMixin:
    """人物状态提取功能域"""

    async def extract_character_states(
        self,
        chapter_content: str,
        chapter_num: int,
        known_characters: List[str] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        提取章节中的人物状态变化实体

        专门用于提取人物状态追踪相关的实体，支持写作工作台的人物状态追踪功能。
        使用专用的人物状态提取配置（更宽松的限制以捕获更多细节）

        Args:
            chapter_content: 章节内容
            chapter_num: 章节号
            known_characters: 已知人物列表（可选，帮助识别人物）
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...], "chapter": chapter_num}
        """
        last_error = None

        # === NEW_CODE_MARKER_2026_0404 === 唯一标识：确认代码加载
        self.logger.warning(
            "NEW_CODE_MARKER_2026_0404: extract_character_states 已加载最新代码")

        # 使用人物状态专用的宽松限制
        max_entities = CHARACTER_STATE_MAX_ENTITIES
        max_relations = CHARACTER_STATE_MAX_RELATIONS

        for attempt in range(max_retries):
            try:
                # 构建提示词，包含已知人物信息
                character_info = ""
                if known_characters:
                    character_info = f"\n**已知人物：** {', '.join(known_characters[:10])}"
                    if len(known_characters) > 10:
                        character_info += f" 等{len(known_characters)}个人物"

                prompt = CHARACTER_STATE_EXTRACTION_PROMPT.format(
                    max_entities=max_entities,
                    max_relations=max_relations,
                    chapter_num=chapter_num,
                    content=f"{character_info}\n\n{chapter_content}"
                )

                # 获取模型支持的最大输出token
                max_output_tokens = self.llm_provider.get_max_output_tokens()

                response = await self.llm_provider.generate(
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=max_output_tokens
                )

                if not response or not hasattr(response, 'content') or response.content is None:
                    self.logger.warning(
                        f"人物状态提取返回无效响应，尝试 {attempt+1}/{max_retries}")
                    continue

                # 确保response.content是字符串类型
                response_content = response.content
                if not isinstance(response_content, str):
                    self.logger.warning(
                        f"响应内容类型异常: {type(response_content).__name__}, 尝试转换")
                    try:
                        response_content = str(response_content)
                    except Exception as conv_error:
                        self.logger.error(f"响应内容转换失败: {conv_error}")
                        continue

                # 解析响应
                self.logger.info(
                    f"[DEBUG] 开始解析LLM响应, 长度={len(response_content)}")
                result = self._parse_llm_response(response_content)
                self.logger.info(
                    f"[DEBUG] _parse_llm_response 返回: {type(result).__name__ if result else 'None'}")
                if result:
                    self.logger.info(f"[DEBUG] 结果包含键: {list(result.keys())}")
                    entities = result.get('entities', [])
                    self.logger.info(f"[DEBUG] 实体数量: {len(entities)}")
                    if entities:
                        self.logger.info(
                            f"[DEBUG] 第一个实体的键: {list(entities[0].keys()) if isinstance(entities[0], dict) else type(entities[0]).__name__}")
                    # 为实体添加章节号，确保类型安全
                    for entity in result.get("entities", []):
                        if not isinstance(entity, dict):
                            self.logger.warning(
                                f"跳过非字典类型的实体: {type(entity).__name__}")
                            continue
                        if "chapter" not in entity:
                            entity["chapter"] = chapter_num

                    # 质量验证
                    validated_result = self._validate_character_state_result(
                        result, chapter_num, known_characters
                    )

                    self.logger.info(
                        f"人物状态提取成功: 章节{chapter_num}, "
                        f"实体数={len(validated_result.get('entities', []))}, "
                        f"关系数={len(validated_result.get('relations', []))}")

                    validated_result["chapter"] = chapter_num
                    return validated_result

                self.logger.warning(f"JSON解析失败，尝试 {attempt+1}/{max_retries}")

            except Exception as e:
                error_str = str(e)
                last_error = e

                # 检测429错误
                is_rate_limit = '429' in error_str or 'rate' in error_str.lower()

                import traceback
                self.logger.warning(
                    f"人物状态提取异常: {type(e).__name__}: {error_str[:200]}")
                self.logger.warning(f"异常堆栈:\n{traceback.format_exc()}")

                if is_rate_limit:
                    wait_time = 10 * (2 ** attempt)
                    self.logger.warning(
                        f"API限流，等待 {wait_time}秒 后重试...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                else:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)

        self.logger.error(
            f"人物状态提取失败: 章节{chapter_num}. 最后错误: {str(last_error)[:200] if last_error else 'None'}")

        # 不再使用规则提取回退方案，只使用LLM提取
        self.logger.warning(f"LLM人物状态提取失败，不启用规则回退: 章节{chapter_num}")
        return {
            "entities": [],
            "relations": [],
            "chapter": chapter_num,
            "summary": "",
            "_extraction_failed": True,
            "_error": str(last_error)[:200] if last_error else "Unknown error"
        }

    def _rule_based_character_extraction(
        self,
        content: str,
        chapter_num: int,
        known_characters: List[str] = None
    ) -> Dict[str, Any]:
        """
        基于规则的人物状态提取（回退方案）

        当LLM不可用或提取失败时，使用简单的规则匹配来提取基本的人物状态信息。
        """
        entities = []
        relations = []

        # 定义关键词模式
        patterns = {
            "身份变化": [
                r'([\u4e00-\u9fa5]{2,4})(?:被任命为|晋升为|封为|成为|担任)([\u4e00-\u9fa5]{2,6})',
                r'(?:任命|晋升|封|册封)([\u4e00-\u9fa5]{2,4})为([\u4e00-\u9fa5]{2,6})',
                r'([\u4e00-\u9fa5]{2,4})(?:不再是|卸任|辞去|失去)(?:了)?([\u4e00-\u9fa5]{2,6})'
            ],
            "位置变化": [
                r'([\u4e00-\u9fa5]{2,4})(?:前往|来到|到达|离开|返回|逃往|追至)([\u4e00-\u9fa5]{2,8})',
                r'(?:从)([\u4e00-\u9fa5]{2,8})(?:前往|赶往|逃到|转移到)([\u4e00-\u9fa5]{2,8})'
            ],
            "关系变化": [
                r'([\u4e00-\u9fa5]{2,4})与([\u4e00-\u9fa5]{2,4})(?:结盟|联盟|联手|合作|结拜)',
                r'([\u4e00-\u9fa5]{2,4})与([\u4e00-\u9fa5]{2,4})(?:决裂|反目|断交|翻脸)',
                r'([\u4e00-\u9fa5]{2,4})(?:背叛|出卖|背弃)(?:了)?([\u4e00-\u9fa5]{2,4})',
                r'([\u4e00-\u9fa5]{2,4})与([\u4e00-\u9fa5]{2,4})(?:和解|和好|重归于好)'
            ],
            "能力成长": [
                r'([\u4e00-\u9fa5]{2,4})(?:学会|掌握|领悟|修成|突破)(?:了)?([\u4e00-\u9fa5]{2,10})',
                r'([\u4e00-\u9fa5]{2,4})的(?:武功|实力|能力|修为)(?:大增|精进|提升|突破)'
            ],
            "心理状态": [
                r'([\u4e00-\u9fa5]{2,4})(?:感到|觉得|心中|内心)(?:绝望|恐惧|狂喜|愤怒|悲伤|释然|迷茫|坚定)',
                r'([\u4e00-\u9fa5]{2,4})(?:陷入|陷入于)(?:绝望|痛苦|沉思|疯狂)'
            ]
        }

        # 提取实体
        for entity_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, tuple) and len(match) >= 2:
                        char_name = match[0]
                        detail = match[1] if len(match) > 1 else ""

                        if known_characters and char_name not in known_characters:
                            is_known = any(char_name in kc or kc in char_name
                                           for kc in known_characters[:20])
                            if not is_known and len(match[0]) < 2:
                                continue

                        entity = {
                            "text": f"{entity_type}: {''.join(match)}",
                            "type": entity_type,
                            "character": char_name,
                            "chapter": chapter_num,
                            "description": f"在章节中{entity_type}：{''.join(match)}"
                        }

                        existing_texts = [e.get("text", "") for e in entities]
                        if entity.get("text", "") not in existing_texts:
                            entities.append(entity)

                            if entity_type in ["关系变化"] and len(match) >= 2:
                                relation_type = self._infer_relation_type(
                                    content, match[0], match[1])
                                relations.append({
                                    "source": match[0],
                                    "target": match[1],
                                    "relation": relation_type,
                                    "context": f"在第{chapter_num}章中发生{entity_type}"
                                })

        # 限制数量
        max_entities = min(len(entities), CHARACTER_STATE_MAX_ENTITIES // 2)
        max_relations = min(len(relations), CHARACTER_STATE_MAX_RELATIONS // 2)

        self.logger.debug(
            f"规则提取完成: 章节{chapter_num}, "
            f"找到{len(entities)}个候选实体, 保留{max_entities}个"
        )

        return {
            "entities": entities[:max_entities],
            "relations": relations[:max_relations],
            "chapter": chapter_num,
            "summary": f"基于规则提取的基本人物状态信息（共{len(entities[:max_entities])}个变化）",
            "_extraction_method": "rule_based_fallback"
        }

    def _infer_relation_type(
        self,
        content: str,
        char1: str,
        char2: str
    ) -> str:
        """根据上下文推断两个人物之间的关系类型"""
        context_pattern = f'{char1}.*?{char2}|{char2}.*?{char1}'
        context_match = re.search(context_pattern, content, re.DOTALL)

        if not context_match:
            return "关联"

        context_text = context_match.group()

        positive_keywords = ['盟', '友', '信任', '支持', '合作', '帮助', '爱']
        negative_keywords = ['敌', '仇', '恨', '杀', '攻击', '背叛', '敌对']

        positive_count = sum(
            1 for kw in positive_keywords if kw in context_text)
        negative_count = sum(
            1 for kw in negative_keywords if kw in context_text)

        if positive_count > negative_count:
            return "关系改善"
        elif negative_count > positive_count:
            return "关系恶化"
        else:
            return "关联"

    def _validate_character_state_result(
        self,
        result: Dict[str, Any],
        chapter_num: int,
        known_characters: List[str] = None
    ) -> Dict[str, Any]:
        """验证人物状态提取结果的质量"""
        validated_entities = []
        validated_relations = []
        issues_found = []

        valid_entity_types = {
            "身份变化", "位置变化", "关系变化", "性格发展",
            "能力成长", "心理状态", "行为模式"
        }

        # 验证实体
        for entity in result.get("entities", []):
            if not isinstance(entity, dict):
                issues_found.append(f"跳过非字典类型的实体: {type(entity).__name__}")
                self.logger.warning(
                    f"实体类型错误，跳过: {type(entity).__name__}, 值: {str(entity)[:50]}")
                continue

            try:
                cleaned_entity = {}
                has_fatal_error = False
                for key in list(entity.keys()):
                    if not isinstance(key, str):
                        self.logger.warning(
                            f"实体包含非字符串类型的键: {key!r} (类型: {type(key).__name__})")
                        has_fatal_error = True
                        break

                    cleaned_key = self._normalize_key_name(key)
                    if cleaned_key != key.strip():
                        self.logger.debug(
                            f"规范化实体键名: {key!r} -> {cleaned_key!r}")
                        issues_found.append(
                            f"规范化键名: '{str(key)[:20]}' -> '{cleaned_key[:20]}'")

                    if not cleaned_key:
                        self.logger.warning(f"清理后键名为空，跳过该键")
                        continue

                    value = entity.get(key)
                    if value is None:
                        self.logger.debug(f"键 {key!r} 的值为None，跳过")
                        continue
                    if isinstance(value, str):
                        cleaned_value = value.lstrip('\n\r ').rstrip()
                        if cleaned_value != value:
                            self.logger.debug(
                                f"清理实体值: 键={cleaned_key}, 原值前10字符={value[:10]!r}")
                        cleaned_entity[cleaned_key] = cleaned_value
                    else:
                        cleaned_entity[cleaned_key] = value

                if has_fatal_error:
                    issues_found.append(f"跳过键名异常的实体")
                    continue

            except KeyError as e:
                self.logger.error(f"实体键访问错误: {e!r}, 实体内容: {str(entity)[:200]}")
                issues_found.append(f"跳过键访问错误的实体: {e!r}")
                continue
            except Exception as e:
                self.logger.error(f"实体处理异常: {type(e).__name__}: {e!r}")
                issues_found.append(f"跳过处理异常的实体")
                continue

            entity = cleaned_entity

            # 检查1：必须有character字段
            if not entity.get("character"):
                char_name = self._extract_character_from_text(
                    entity.get("text", ""),
                    known_characters
                )
                if char_name:
                    entity["character"] = char_name
                    issues_found.append(f"自动补充人物名: {char_name}")
                else:
                    issues_found.append(
                        f"跳过无人物名的实体: {entity.get('text', '')[:30]}")
                    continue

            # 检查2：类型必须合法
            entity_type = entity.get("type", "")
            if entity_type not in valid_entity_types:
                mapped_type = self._map_entity_type(entity_type)
                if mapped_type:
                    entity["type"] = mapped_type
                    issues_found.append(
                        f"修正实体类型: {entity_type} → {mapped_type}")
                else:
                    issues_found.append(f"跳过非法类型实体: {entity_type}")
                    continue

            # 检查3：描述不能太简短
            description = entity.get("description", "")
            if len(description) < 10:
                entity["description"] = f"{entity.get('text', '')}。{description}"
                issues_found.append(f"补充描述: 实体'{entity.get('text', '')[:20]}'")

            # 检查4：必须有text字段
            if not entity.get("text"):
                entity["text"] = f"{entity.get('type', '未知变化')} - {entity.get('character', '未知人物')}"
                issues_found.append(f"补充text字段")

            validated_entities.append(entity)

        # 验证关系
        for relation in result.get("relations", []):
            if not isinstance(relation, dict):
                issues_found.append(f"跳过非字典类型的关系: {type(relation).__name__}")
                self.logger.warning(
                    f"关系类型错误，跳过: {type(relation).__name__}, 值: {str(relation)[:50]}")
                continue

            try:
                cleaned_relation = {}
                has_fatal_error = False
                for key in list(relation.keys()):
                    if not isinstance(key, str):
                        has_fatal_error = True
                        break
                    cleaned_key = self._normalize_key_name(key)
                    if not cleaned_key:
                        continue
                    value = relation.get(key)
                    if value is None:
                        continue
                    if isinstance(value, str):
                        cleaned_relation[cleaned_key] = value.lstrip(
                            '\n\r ').rstrip()
                    else:
                        cleaned_relation[cleaned_key] = value

                if has_fatal_error:
                    issues_found.append(f"跳过键名异常的关系")
                    continue

                relation = cleaned_relation

                if not relation.get("source") or not relation.get("target"):
                    issues_found.append(f"跳过不完整的关系")
                    continue

                context = relation.get("context", "")
                if len(context) < 5:
                    relation["context"] = f"{relation.get('source', '')}与{relation.get('target', '')}之间存在{relation.get('relation', '关联')}"

                validated_relations.append(relation)

            except KeyError as e:
                self.logger.error(
                    f"关系键访问错误: {e!r}, 关系内容: {str(relation)[:200]}")
                issues_found.append(f"跳过键访问错误的关系: {e!r}")
                continue
            except Exception as e:
                self.logger.error(f"关系处理异常: {type(e).__name__}: {e!r}")
                issues_found.append(f"跳过处理异常的关系")
                continue

        if issues_found:
            self.logger.info(
                f"人物状态质量验证完成: 章节{chapter_num}, "
                f"发现{len(issues_found)}个问题, "
                f"有效实体={len(validated_entities)}, 有效关系={len(validated_relations)}"
            )
            for issue in issues_found[:5]:
                self.logger.debug(f"  - {issue}")

        return {
            "entities": validated_entities,
            "relations": validated_relations,
            "summary": result.get("summary", ""),
            "_validation_issues": len(issues_found),
            "_original_count": {
                "entities": len(result.get("entities", [])),
                "relations": len(result.get("relations", []))
            }
        }

    def _extract_character_from_text(
        self,
        text: str,
        known_characters: List[str] = None
    ) -> Optional[str]:
        """从文本中提取人物名称"""
        if not text:
            return None

        # 方法1：在已知人物列表中查找
        if known_characters:
            for char_name in known_characters:
                if char_name in text:
                    return char_name

        # 方法2：使用简单的启发式规则
        patterns = [
            r'([^\s，。！？、；：""''（）【】]{2,4})(?:的|被|将|把|与|和|对|向|在)',
            r'(?:主角|人物|角色)([^\s，。！？、；：""''（）【】]{2,4})'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1)
                if len(name) >= 2 and len(name) <= 4:
                    return name

        return None

    def _map_entity_type(self, invalid_type: str) -> Optional[str]:
        """将非法或非标准的实体类型映射到标准类型"""
        type_mapping = {
            "身份": "身份变化", "职位": "身份变化", "地位": "身份变化",
            "官职": "身份变化", "称号": "身份变化", "角色": "身份变化",
            "位置": "位置变化", "地点": "位置变化", "场景": "位置变化",
            "移动": "位置变化", "迁移": "位置变化", "转移": "位置变化",
            "关系": "关系变化", "人际": "关系变化", "社交": "关系变化",
            "感情": "关系变化", "情感": "关系变化",
            "性格": "性格发展", "个性": "性格发展", "特质": "性格发展",
            "价值观": "性格发展", "观念": "性格发展",
            "能力": "能力成长", "技能": "能力成长", "武功": "能力成长",
            "实力": "能力成长", "知识": "能力成长", "水平": "能力成长",
            "心理": "心理状态", "情绪": "心理状态", "心情": "心理状态",
            "精神": "心理状态", "心态": "心理状态",
            "行为": "行为模式", "习惯": "行为模式", "方式": "行为模式",
            "策略": "行为模式", "决策": "行为模式"
        }

        if invalid_type in type_mapping:
            return type_mapping[invalid_type]

        for key, value in type_mapping.items():
            if key in invalid_type or invalid_type in key:
                return value

        return None
