"""基于LLM的实体提取器"""
from typing import List, Dict, Any, Optional
import json
import re

from app.core.logger import get_logger


class LLMEntityExtractor:
    """基于LLM的实体提取器 - 用于深度理解知识库内容

    支持双轨知识库架构：
    - 通用知识库（创意理论层）
    - 垂直领域知识库（应用案例层）
    - 主动建立垂直实体与通用理论的连接
    """

    def __init__(self, llm_provider, kb_category: str = "general"):
        """
        初始化LLM实体提取器

        Args:
            llm_provider: LLM提供者实例
            kb_category: 知识库类别 (general/short-video/script/novel/print-ad/tvc)
        """
        self.llm_provider = llm_provider
        self.kb_category = kb_category
        self.logger = get_logger("llm_entity_extractor")

        # 导入配置
        from app.tools.graph_rag_config import get_extraction_prompt
        self.get_extraction_prompt = get_extraction_prompt

    def _get_prompt(self, text: str) -> str:
        """根据知识库类别获取对应的提取提示词"""
        return self.get_extraction_prompt(self.kb_category, text)

    async def extract_with_llm(self, text: str, max_retries: int = 2) -> Dict[str, Any]:
        """
        使用LLM提取实体和关系

        Args:
            text: 输入文本
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...]}
        """
        # 不再截断，直接处理完整文本
        # 如果文本超长，LLM会自然处理
        return await self._extract_single_chunk(text, max_retries)

    async def _extract_from_long_text(self, text: str, chunk_size: int) -> Dict[str, Any]:
        """
        处理长文本，分段提取后合并

        Args:
            text: 长文本
            chunk_size: 分段大小

        Returns:
            合并后的实体和关系
        """
        all_entities = []
        all_relations = []
        success_count = 0
        fail_count = 0

        # 改进的分块逻辑：支持多种分割方式
        chunks = self._smart_split_text(text, chunk_size)
        total_chunks = len(chunks)

        self.logger.info(
            f"长文本分块: 总长度={len(text)}, chunk大小={chunk_size}, 分成{total_chunks}块")

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            self.logger.debug(f"处理第 {i+1}/{total_chunks} 块, 长度={len(chunk)}")
            result = await self._extract_single_chunk(chunk)
            if result.get("entities") or result.get("relations"):
                all_entities.extend(result.get("entities", []))
                all_relations.extend(result.get("relations", []))
                success_count += 1
            else:
                fail_count += 1

        # 去重
        unique_entities = self._deduplicate_entities(all_entities)
        unique_relations = self._deduplicate_relations(all_relations)

        # 输出总结日志
        self.logger.info(
            f"长文本处理完成: {total_chunks}个chunk, 成功{success_count}个, 失败{fail_count}个")

        return {
            "entities": unique_entities,
            "relations": unique_relations
        }

    def _smart_split_text(self, text: str, chunk_size: int) -> List[str]:
        """
        智能分块：优先按段落分割，如果段落过长则按句子分割

        Args:
            text: 输入文本
            chunk_size: 目标块大小

        Returns:
            分块列表
        """
        chunks = []

        # 1. 首先尝试按双换行符分割（段落）
        paragraphs = text.split('\n\n')

        # 如果只有一个段落（没有双换行符），尝试单换行符
        if len(paragraphs) == 1:
            paragraphs = text.split('\n')
            self.logger.debug(f"使用单换行符分割，得到 {len(paragraphs)} 个段落")
        else:
            self.logger.debug(f"使用双换行符分割，得到 {len(paragraphs)} 个段落")

        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前段落加上新段落不超过限制，合并
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                if current_chunk:
                    current_chunk += "\n" + para
                else:
                    current_chunk = para
            else:
                # 当前块已满，保存并开始新块
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果单个段落超过限制，需要进一步分割
                if len(para) > chunk_size:
                    sub_chunks = self._split_long_paragraph(para, chunk_size)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = para

        # 保存最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        # 如果仍然没有分块（极端情况），强制按字符数分割
        if not chunks:
            for i in range(0, len(text), chunk_size):
                chunks.append(text[i:i+chunk_size])

        return chunks

    def _split_long_paragraph(self, para: str, chunk_size: int) -> List[str]:
        """
        分割过长的段落（按句子分割）

        Args:
            para: 过长的段落
            chunk_size: 目标块大小

        Returns:
            分割后的块列表
        """
        chunks = []

        # 按中文句号、问号、感叹号分割句子
        sentences = re.split(r'([。！？!?\.]+)', para)

        # 重新组合句子和标点
        combined_sentences = []
        for i in range(0, len(sentences)-1, 2):
            if i+1 < len(sentences):
                combined_sentences.append(sentences[i] + sentences[i+1])
            else:
                combined_sentences.append(sentences[i])
        if len(sentences) % 2 == 1 and sentences[-1]:
            combined_sentences.append(sentences[-1])

        current_chunk = ""

        for sentence in combined_sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # 如果单个句子超过限制，强制截断
                if len(sentence) > chunk_size:
                    for i in range(0, len(sentence), chunk_size):
                        chunks.append(sentence[i:i+chunk_size])
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def _extract_single_chunk(self, text: str, max_retries: int = 2) -> Dict[str, Any]:
        """
        提取单个文本块的实体和关系（内部方法，不检查长度）

        Args:
            text: 输入文本
            max_retries: 最大重试次数

        Returns:
            {"entities": [...], "relations": [...]}
        """
        import asyncio
        import time

        for attempt in range(max_retries):
            try:
                prompt = self._get_prompt(text)
                # 使用模型支持的最大输出token数，避免截断
                max_output_tokens = self.llm_provider.get_max_output_tokens()

                # 知识图谱提取需要大量token，确保设置为最大值
                # 如果模型支持超过30000，使用模型的最大值；否则使用30000
                safe_max_tokens = max(max_output_tokens, 30000)

                self.logger.debug(
                    f"知识图谱提取 - 模型最大token: {max_output_tokens}, "
                    f"实际使用: {safe_max_tokens}"
                )

                response = await self.llm_provider.generate(
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=safe_max_tokens
                )

                # 调试：打印 LLM 原始响应（增加输出长度）
                self.logger.info(f"=== LLM RAW RESPONSE START ===")
                if response and hasattr(response, 'content'):
                    content_preview = response.content[
                        :2000] if response.content else 'None'
                    self.logger.info(
                        f"Content length: {len(response.content) if response.content else 0}")
                    self.logger.info(f"Content preview: {content_preview}")
                else:
                    self.logger.info(f"Response: {response}")
                self.logger.info(f"=== LLM RAW RESPONSE END ===")

                # 检查响应是否有效
                if not response:
                    self.logger.warning(
                        f"LLM返回None，尝试 {attempt+1}/{max_retries}")
                    continue

                if not hasattr(response, 'content') or response.content is None:
                    self.logger.warning(
                        f"LLM响应格式错误，尝试 {attempt+1}/{max_retries}")
                    continue

                content = response.content
                if not content or not content.strip():
                    self.logger.warning(
                        f"LLM返回空内容，尝试 {attempt+1}/{max_retries}")
                    continue

                # 解析JSON响应
                result = self._parse_llm_response(content)

                if result and isinstance(result, dict) and (result.get("entities") or result.get("relations")):
                    entity_count = len(result.get("entities", []))
                    relation_count = len(result.get("relations", []))
                    self.logger.info(
                        f"JSON解析成功: {entity_count}个实体, {relation_count}个关系")
                    return result
                else:
                    # 记录解析失败的原因
                    self.logger.warning(
                        f"JSON解析结果无效，尝试 {attempt+1}/{max_retries}")
                    # 尝试打印响应中的JSON对象候选
                    self.logger.debug(f"响应内容: {content[:1000]}")

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)[:200]

                # 对429错误（RateLimitError）进行延迟重试
                if 'RateLimitError' in error_type or '429' in error_msg or 'TooManyRequests' in error_msg:
                    retry_delay = 5 * (attempt + 1)  # 递增延迟：5s, 10s, 15s...
                    self.logger.warning(
                        f"API限流(429)，等待 {retry_delay}秒 后重试... (尝试 {attempt+1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    continue

                import traceback
                self.logger.warning(
                    f"LLM实体提取异常({error_type}): {error_msg}\n{traceback.format_exc()}")

        self.logger.warning(f"所有重试失败，返回空结果")
        return {"entities": [], "relations": []}

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析LLM响应，提取JSON"""
        if not response:
            return None

        # 清理响应内容
        response = response.strip()

        def validate_result(result):
            """验证结果是否为有效字典"""
            if not isinstance(result, dict):
                return None
            if "entities" in result or "relations" in result:
                return result
            return None

        def clean_json_string(json_str: str) -> str:
            """清理JSON字符串中的常见问题"""
            # 移除控制字符（除了换行、制表符、回车）
            json_str = re.sub(
                r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_str)

            # 关键修复：处理JSON字符串值内部的中文引号
            # 中文引号在JSON字符串值内部会导致解析失败，因为解析器会误认为字符串边界
            # 使用Unicode码点精确指定字符，避免编码混淆
            # 英文双引号: U+0022 (") - 这是JSON结构字符，不能替换
            # 中文左引号: U+201C (") - 需要替换
            # 中文右引号: U+201D (") - 需要替换
            # 中文左单引号: U+2018 (') - 需要替换
            # 中文右单引号: U+2019 (') - 需要替换

            json_str = json_str.replace('\u201c', '「')  # 中文左引号 " -> 「
            json_str = json_str.replace('\u201d', '」')  # 中文右引号 " -> 」
            json_str = json_str.replace('\u2018', '『')  # 中文左单引号 ' -> 『
            json_str = json_str.replace('\u2019', '』')  # 中文右单引号 ' -> 』

            return json_str

        # 1. 先清理响应中的中文引号问题，再尝试直接解析
        try:
            cleaned_response = clean_json_string(response)
            result = json.loads(cleaned_response)
            validated = validate_result(result)
            if validated:
                self.logger.info("直接解析JSON成功（已清理中文引号）")
                return validated
        except json.JSONDecodeError as e:
            self.logger.debug(f"直接解析失败: {str(e)[:100]}")

        # 2. 尝试提取markdown代码块中的JSON
        code_block_patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # ```json ... ```
            r'```\s*([\s\S]*?)\s*```',  # ``` ... ```
        ]
        for pattern in code_block_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                try:
                    cleaned = clean_json_string(match.strip())
                    result = json.loads(cleaned)
                    validated = validate_result(result)
                    if validated:
                        self.logger.info("从markdown代码块提取JSON成功（已清理中文引号）")
                        return validated
                except json.JSONDecodeError as e:
                    self.logger.debug(f"markdown代码块解析失败: {str(e)[:100]}")
                    continue

        # 3. 改进的JSON对象提取逻辑
        # 使用栈来匹配嵌套的大括号，找到所有完整的JSON对象
        def extract_json_objects(text):
            """提取所有完整的JSON对象"""
            objects = []
            stack = []
            start = -1
            in_string = False
            escape_next = False

            for i, char in enumerate(text):
                # 处理字符串内的内容
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\' and in_string:
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue

                # 只在非字符串状态下匹配括号
                if not in_string:
                    if char == '{':
                        if not stack:
                            start = i
                        stack.append(char)
                    elif char == '}':
                        if stack:
                            stack.pop()
                            if not stack and start != -1:
                                # 找到一个完整的JSON对象
                                objects.append(text[start:i+1])
                                start = -1

            # 如果遍历结束后仍在字符串状态，说明有未闭合的字符串
            # 尝试从第一个 { 开始截取到文本末尾
            if in_string and not objects:
                first_brace = text.find('{')
                if first_brace != -1:
                    # 尝试截取并修复
                    incomplete = text[first_brace:]
                    objects.append(incomplete)

            return objects

        # 先清理响应中的中文引号，再提取JSON对象
        # 这样可以避免中文引号干扰字符串边界检测
        cleaned_response_for_extract = clean_json_string(response)
        json_objects = extract_json_objects(cleaned_response_for_extract)
        self.logger.info(f"找到 {len(json_objects)} 个JSON对象候选")

        for i, json_str in enumerate(json_objects):
            try:
                # 清理JSON字符串（包括中文引号处理）
                cleaned = clean_json_string(json_str)
                result = json.loads(cleaned)
                validated = validate_result(result)
                if validated:
                    self.logger.info(
                        f"第 {i+1} 个JSON对象解析成功，包含 {len(result.get('entities', []))} 个实体")
                    return validated
            except json.JSONDecodeError as e:
                self.logger.warning(f"第 {i+1} 个JSON对象解析失败: {str(e)}")
                self.logger.debug(
                    f"JSON长度: {len(json_str)}, 前100字符: {json_str[:100]}, 后100字符: {json_str[-100:]}")
                # 尝试修复常见的JSON格式问题
                try:
                    # 先清理中文引号，再尝试修复
                    cleaned_for_fix = clean_json_string(json_str)
                    # 尝试修复未闭合的字符串
                    fixed = self._try_fix_json(cleaned_for_fix)
                    if fixed and fixed != cleaned_for_fix:
                        self.logger.info(
                            f"尝试修复JSON: 原长度={len(json_str)}, 修复后长度={len(fixed)}")
                        result = json.loads(fixed)
                        validated = validate_result(result)
                        if validated:
                            self.logger.info(f"第 {i+1} 个JSON对象修复后解析成功")
                            return validated
                except json.JSONDecodeError as fix_error:
                    self.logger.debug(f"修复后仍然失败: {str(fix_error)}")
                except Exception as ex:
                    self.logger.debug(f"修复过程异常: {str(ex)}")
                continue

        # 4. 尝试修复常见的JSON格式问题
        try:
            # 移除可能的前后文本
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx+1]
                # 先清理中文引号
                cleaned = clean_json_string(json_str)
                try:
                    result = json.loads(cleaned)
                    validated = validate_result(result)
                    if validated:
                        self.logger.info("修复JSON格式后解析成功（已清理中文引号）")
                        return validated
                except json.JSONDecodeError:
                    # 尝试进一步修复
                    fixed = self._try_fix_json(cleaned)
                    if fixed:
                        try:
                            result = json.loads(fixed)
                            validated = validate_result(result)
                            if validated:
                                self.logger.info("修复JSON格式后解析成功")
                                return validated
                        except json.JSONDecodeError as e:
                            self.logger.debug(f"修复后JSON仍解析失败: {e}")
        except Exception as e:
            self.logger.debug(f"修复过程出错: {str(e)[:100]}")

        # 5. 最后尝试：记录响应的前2000字符用于调试
        self.logger.warning(f"无法解析LLM响应为有效JSON，响应长度: {len(response)}")
        self.logger.debug(f"响应内容预览: {response[:2000]}")
        return None

    def _try_fix_json(self, json_str: str) -> Optional[str]:
        """尝试修复常见的JSON格式问题，特别是被截断的JSON"""
        # 1. 移除控制字符（但保留换行和制表符）
        json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_str)

        # 2. 关键修复：处理在字符串值中间被截断的情况
        # 检测最后一个实体是否完整，如果不完整则删除
        json_str = self._remove_incomplete_last_entity(json_str)

        # 3. 移除末尾的逗号（在对象或数组末尾）
        json_str = json_str.rstrip()
        if json_str.endswith(','):
            json_str = json_str[:-1]

        # 4. 再次移除可能产生的控制字符
        json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_str)

        # 4. 检查是否缺少闭合括号
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')

        # 5. 智能闭合：针对包含 entities 和 relations 的结构
        if open_braces > close_braces or open_brackets > close_brackets:
            # 尝试找到 entities 和 relations 数组的位置
            entities_start = json_str.find('"entities"')
            relations_start = json_str.find('"relations"')

            if entities_start != -1:
                # 尝试找到 entities 数组的完整部分
                entities_array_start = json_str.find('[', entities_start)
                if entities_array_start != -1:
                    # 解析 entities 数组，找到最后一个完整的元素
                    entities_result = self._extract_complete_array(
                        json_str, entities_array_start
                    )

                    if relations_start != -1 and relations_start > entities_start:
                        # 有 relations 数组，尝试提取
                        relations_array_start = json_str.find(
                            '[', relations_start)
                        if relations_array_start != -1:
                            relations_result = self._extract_complete_array(
                                json_str, relations_array_start
                            )
                            # 构建完整的 JSON
                            fixed_json = (
                                '{' +
                                '"entities": ' + entities_result +
                                ', "relations": ' + relations_result +
                                '}'
                            )
                            return fixed_json
                    else:
                        # 只有 entities 数组
                        fixed_json = '{"entities": ' + \
                            entities_result + ', "relations": []}'
                        return fixed_json

            # 回退到简单修复
            last_complete = -1
            depth = 0
            in_string = False
            escape_next = False

            for i, char in enumerate(json_str):
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
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 1:
                            last_complete = i
                    elif char == '[':
                        depth += 1
                    elif char == ']':
                        depth -= 1

            if last_complete > 0:
                self.logger.info(f"尝试截断到完整元素: 位置 {last_complete}")
                json_str = json_str[:last_complete + 1]
                json_str += ']'
                json_str += '}'
        else:
            # 简单添加缺少的闭合括号
            if open_braces > close_braces:
                json_str += '}' * (open_braces - close_braces)
            if open_brackets > close_brackets:
                json_str += ']' * (open_brackets - close_brackets)

        return json_str

    def _remove_incomplete_last_entity(self, json_str: str) -> str:
        """
        移除最后一个不完整的实体对象

        当LLM响应在字符串值中间被截断时（如 {"text": "），
        需要删除这个不完整的实体，保留前面完整的实体。

        Args:
            json_str: JSON字符串

        Returns:
            修复后的JSON字符串
        """
        # 查找 entities 数组
        entities_match = re.search(r'"entities"\s*:\s*\[', json_str)
        if not entities_match:
            return json_str

        entities_array_start = entities_match.end() - 1  # '[' 的位置

        # 从 entities 数组开始位置解析，找到最后一个完整的实体对象
        depth = 0
        in_string = False
        escape_next = False
        last_complete_entity_end = -1
        entity_start = -1
        has_incomplete_entity = False  # 标记是否有不完整的实体

        for i in range(entities_array_start, len(json_str)):
            char = json_str[i]

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
                if char == '{':
                    if depth == 1:  # 实体对象开始
                        entity_start = i
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 1 and entity_start >= 0:  # 实体对象结束
                        last_complete_entity_end = i
                        entity_start = -1
                elif char == ']' and depth == 0:  # 数组正常结束
                    return json_str  # JSON完整，无需修复

        # 如果遍历结束后仍在字符串内或depth > 0，说明有不完整的实体
        if in_string or depth > 0:
            has_incomplete_entity = True

        # 如果有不完整的实体，截断到最后一个完整实体
        if has_incomplete_entity:
            if last_complete_entity_end > entities_array_start:
                # 有完整的实体，截断到最后一个完整实体
                self.logger.info(
                    f"检测到不完整的实体对象，截断到位置 {last_complete_entity_end}"
                )
                truncated = json_str[:last_complete_entity_end + 1]

                # 查找 relations 数组，如果存在且完整则保留
                relations_match = re.search(r'"relations"\s*:\s*\[', json_str)
                if relations_match:
                    relations_array_start = relations_match.end() - 1
                    relations_result = self._extract_complete_array(
                        json_str, relations_array_start
                    )
                    truncated += ', "relations": ' + relations_result

                truncated += ']}'  # 闭合 entities 数组和根对象
                return truncated
            else:
                # 没有完整的实体，返回空数组
                self.logger.warning("LLM响应被严重截断，没有完整实体，返回空数组")
                return '{"entities": [], "relations": []}'

        return json_str

    def _extract_complete_array(self, json_str: str, array_start: int) -> str:
        """
        从JSON字符串中提取完整的数组内容

        Args:
            json_str: JSON字符串
            array_start: 数组开始位置（'['的位置）

        Returns:
            完整的数组字符串，如 '[{"text": "..."}, ...]'
        """
        depth = 0
        in_string = False
        escape_next = False
        last_complete_pos = array_start  # 数组开始位置

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
                    depth += 1
                elif char == ']':
                    depth -= 1
                    if depth == 0:
                        # 数组完整闭合
                        return json_str[array_start:i+1]
                elif char == '}':
                    # 记录最后一个完整对象的位置
                    if depth == 1:
                        last_complete_pos = i

        # 数组不完整，截断到最后一个完整元素
        if last_complete_pos > array_start:
            # 找到最后一个完整对象后的逗号位置（如果有）
            truncated = json_str[array_start:last_complete_pos+1]
            # 移除末尾逗号
            truncated = truncated.rstrip().rstrip(',')
            return truncated + ']'

        # 没有完整元素，返回空数组
        return '[]'

    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """实体去重"""
        seen = set()
        result = []
        for e in entities:
            key = (e.get("name", ""), e.get("type", ""))
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
