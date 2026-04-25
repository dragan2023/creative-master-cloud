"""NovelEntityExtractor - JSON解析Mixin"""
import json
from typing import Dict, Any, Optional, List

from app.utils.json_parser import RobustJSONParser

# 尝试导入json_repair作为终极回退方案
try:
    import json_repair
    HAS_JSON_REPAIR = True
except ImportError:
    HAS_JSON_REPAIR = False


class JsonParsingMixin:
    """JSON解析和修复功能域"""

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析LLM响应为JSON

        使用多层解析策略处理LLM返回的各种异常格式：
        1. 先尝试内置RobustJSONParser
        2. 如果失败，尝试json_repair库（终极回退）
        3. 最后尝试修复实体键名问题
        """
        if not response:
            return None

        def validate_result_internal(result):
            """验证结果是否为有效字典"""
            if not isinstance(result, dict):
                return False
            if "entities" not in result:
                return False
            if not isinstance(result["entities"], list):
                return False
            for entity in result["entities"]:
                if not isinstance(entity, dict):
                    self.logger.warning(
                        f"实体类型错误: {type(entity).__name__}, 值: {str(entity)[:50]}")
                    return False
            if "relations" in result:
                if not isinstance(result["relations"], list):
                    return False
                for relation in result["relations"]:
                    if not isinstance(relation, dict):
                        self.logger.warning(
                            f"关系类型错误: {type(relation).__name__}, 值: {str(relation)[:50]}")
                        return False
            return True

        # 策略1: 使用健壮JSON解析器
        result, logs = RobustJSONParser.parse(
            response, default=None, repair_truncated=True)

        # 记录解析日志
        if logs:
            self.logger.debug(f"JSON解析日志: {'; '.join(logs)}")

        # 关键修复：解析成功后，立即修复键名问题！
        if result and isinstance(result, dict):
            result = self._fix_entity_keys(result)

        # 验证解析结果
        if result and validate_result_internal(result):
            self.logger.info(
                f"JSON解析成功，实体数={len(result.get('entities', []))}, 关系数={len(result.get('relations', []))}")
            return result

        # 策略2: 使用json_repair库（终极回退）
        if HAS_JSON_REPAIR:
            try:
                self.logger.info("尝试使用json_repair库修复JSON...")
                result = json_repair.loads(response, skip_json_loads=True)
                if result and isinstance(result, dict):
                    # 修复键名问题
                    result = self._fix_entity_keys(result)
                    if validate_result_internal(result):
                        self.logger.info("json_repair修复成功！")
                        return result
            except Exception as e:
                self.logger.warning(f"json_repair修复失败: {e}")

        # 策略3: 如果RobustJSONParser解析成功但验证失败，尝试修复实体键名问题
        if result and isinstance(result, dict) and "entities" in result:
            self.logger.info("JSON解析成功但验证失败，尝试修复实体格式...")
            fixed_result = self._fix_entity_keys(result)
            if validate_result_internal(fixed_result):
                self.logger.info("修复实体格式成功")
                return fixed_result

        self.logger.warning(f"无法解析LLM响应为有效JSON，响应长度: {len(response)}")
        self.logger.debug(f"响应内容预览: {response[:500]}")
        return None

    def _fix_entity_keys(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """修复实体中的键名问题

        处理解析后实体字典中可能存在的异常键名，如包含换行符、引号等。
        """
        if not result or not isinstance(result, dict):
            return result

        self.logger.info(
            f"[DEBUG] _fix_entity_keys 开始处理, 实体数={len(result.get('entities', []))}")

        fixed_entities = []
        fixed_count = 0

        for entity in result.get("entities", []):
            if not isinstance(entity, dict):
                continue

            # 修复键名
            fixed_entity = {}
            for key, value in entity.items():
                if not isinstance(key, str):
                    continue

                original_key = key
                # 第一步：移除所有换行符和回车符
                cleaned_key = key.replace('\n', '').replace('\r', '')
                # 第二步：去除首尾空格
                cleaned_key = cleaned_key.strip()
                # 第三步：移除可能存在的外层引号
                if cleaned_key.startswith('"') and cleaned_key.endswith('"'):
                    cleaned_key = cleaned_key[1:-1]
                elif cleaned_key.startswith("'") and cleaned_key.endswith("'"):
                    cleaned_key = cleaned_key[1:-1]
                # 第四步：再次去除空格
                cleaned_key = cleaned_key.strip()
                # 第五步：尝试映射到标准键名
                cleaned_key = self._normalize_key_name(cleaned_key)

                # 记录修复日志
                if cleaned_key != original_key:
                    fixed_count += 1
                    self.logger.debug(
                        f"键名修复: {original_key!r} -> {cleaned_key!r}")

                # 清理值
                if isinstance(value, str):
                    cleaned_value = value.lstrip('\n\r ').rstrip()
                else:
                    cleaned_value = value

                if cleaned_key:  # 确保键名不为空
                    fixed_entity[cleaned_key] = cleaned_value

            if fixed_entity:
                fixed_entities.append(fixed_entity)

        if fixed_count > 0:
            self.logger.info(f"实体键名修复完成: 共修复 {fixed_count} 个异常键名")

        result["entities"] = fixed_entities

        # 同样修复 relations 中的键名
        fixed_relations = []
        relation_fix_count = 0
        for relation in result.get("relations", []):
            if not isinstance(relation, dict):
                continue

            fixed_relation = {}
            for key, value in relation.items():
                if not isinstance(key, str):
                    continue

                original_key = key
                cleaned_key = key.replace('\n', '').replace(
                    '\r', '').strip().strip('"').strip("'").strip()
                cleaned_key = self._normalize_key_name(cleaned_key)

                if cleaned_key != original_key:
                    relation_fix_count += 1
                    self.logger.debug(
                        f"关系键名修复: {original_key!r} -> {cleaned_key!r}")

                if isinstance(value, str):
                    cleaned_value = value.lstrip('\n\r ').rstrip()
                else:
                    cleaned_value = value

                if cleaned_key:
                    fixed_relation[cleaned_key] = cleaned_value

            if fixed_relation:
                fixed_relations.append(fixed_relation)

        if relation_fix_count > 0:
            self.logger.info(f"关系键名修复完成: 共修复 {relation_fix_count} 个异常键名")

        result["relations"] = fixed_relations

        return result

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """验证解析结果"""
        if not isinstance(result, dict):
            return False
        if "entities" not in result:
            return False
        if not isinstance(result["entities"], list):
            return False
        for entity in result["entities"]:
            if not isinstance(entity, dict):
                self.logger.warning(
                    f"实体类型错误: {type(entity).__name__}, 值: {str(entity)[:50]}")
                return False
        if "relations" in result:
            if not isinstance(result["relations"], list):
                return False
            for relation in result["relations"]:
                if not isinstance(relation, dict):
                    self.logger.warning(
                        f"关系类型错误: {type(relation).__name__}, 值: {str(relation)[:50]}")
                    return False
        return True

    def _try_fix_truncated_json(self, response: str) -> Optional[str]:
        """尝试修复被截断的JSON"""
        def validate_parsed_result(parsed):
            """验证解析结果是否有效"""
            if not isinstance(parsed, dict):
                return False
            if "entities" not in parsed:
                return False
            if not isinstance(parsed["entities"], list):
                return False
            for entity in parsed["entities"]:
                if not isinstance(entity, dict):
                    return False
            return True

        # 找到entities和relations数组
        entities_start = response.find('"entities"')
        relations_start = response.find('"relations"')

        if entities_start == -1:
            return None

        # 提取entities数组
        entities_array_start = response.find('[', entities_start)
        if entities_array_start == -1:
            return None

        entities_result = self._extract_complete_array(
            response, entities_array_start)

        if relations_start != -1:
            relations_array_start = response.find('[', relations_start)
            if relations_array_start != -1:
                relations_result = self._extract_complete_array(
                    response, relations_array_start)
                fixed_json = '{"entities": ' + entities_result + \
                    ', "relations": ' + relations_result + '}'
                try:
                    parsed = json.loads(fixed_json)
                    if validate_parsed_result(parsed):
                        return fixed_json
                except json.JSONDecodeError:
                    pass

        fixed_json = '{"entities": ' + entities_result + ', "relations": []}'
        try:
            parsed = json.loads(fixed_json)
            if validate_parsed_result(parsed):
                return fixed_json
        except json.JSONDecodeError:
            return None

        return None

    def _extract_complete_array(self, json_str: str, array_start: int) -> str:
        """从JSON字符串中提取完整的数组内容"""
        depth = 0
        in_string = False
        escape_next = False
        last_complete_pos = array_start
        complete_elements = []
        element_start = None

        for i, char in enumerate(json_str[array_start:], start=array_start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\' and in_string:
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == '[':
                    if depth == 0:
                        element_start = None
                    depth += 1
                elif char == ']':
                    depth -= 1
                    if depth == 0:
                        return json_str[array_start:i+1]
                elif char == '{':
                    if depth == 1 and element_start is None:
                        element_start = i
                elif char == '}':
                    if depth == 1:
                        last_complete_pos = i
                        if element_start is not None:
                            complete_elements.append((element_start, i))
                            element_start = None

        # 数组不完整，截断到最后一个完整元素
        if complete_elements:
            last_elem_start, last_elem_end = complete_elements[-1]
            truncated = json_str[array_start:last_elem_end+1]
            truncated = truncated.rstrip().rstrip(',')
            return truncated + ']'

        return '[]'

    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """实体去重"""
        seen = set()
        result = []
        for e in entities:
            key = (e.get("text", ""), e.get("type", ""))
            if key not in seen:
                seen.add(key)
                result.append(e)
        return result

    def _deduplicate_relations(self, relations: List[Dict]) -> List[Dict]:
        """关系去重"""
        seen = set()
        result = []
        for r in relations:
            key = (r.get("source", ""), r.get(
                "target", ""), r.get("relation", ""))
            if key not in seen:
                seen.add(key)
                result.append(r)
        return result

    # 键名模糊映射表
    _KEY_NAME_FUZZY_MAP = {
        "text": ["text", "文本", "内容", "名称", "name", "标题", "title"],
        "type": ["type", "类型", "类别", "category", "种类"],
        "character": ["character", "人物", "角色", "角色名", "char", "人物名"],
        "description": ["description", "描述", "说明", "详情", "detail", "desc"],
        "chapter": ["chapter", "章节", "章号", "chapter_num"],
        "before_state": ["before_state", "之前状态", "原状态", "旧状态", "before"],
        "after_state": ["after_state", "之后状态", "新状态", "现状态", "after"],
        "trigger_event": ["trigger_event", "触发事件", "起因", "cause", "trigger"],
        "source": ["source", "源", "来源", "起始实体"],
        "target": ["target", "目标", "终点", "目的实体"],
        "relation": ["relation", "关系", "关联", "relationship", "rel"],
    }

    def _normalize_key_name(self, raw_key: str) -> str:
        """将非标准键名映射到标准键名"""
        normalized = raw_key.strip().replace(
            '\n', '').replace('\r', '').strip('"').lower()
        for standard_key, variants in self._KEY_NAME_FUZZY_MAP.items():
            if normalized in [v.lower() for v in variants] or normalized == standard_key:
                return standard_key
        return raw_key.strip().replace('\n', '').replace('\r', '').strip('"')
