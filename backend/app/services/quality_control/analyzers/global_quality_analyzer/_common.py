"""
全局大纲质控 - 公共工具函数

@date: 2026-04-24
@version: v1.1.0
"""
from typing import Dict, Any
import asyncio
from app.core.logger import get_logger

logger = get_logger("quality_control.analyzers.global_quality")


def clean_json_string(json_str: str) -> str:
    """
    清理和修复LLM返回的JSON字符串

    处理常见问题:
    1. 移除markdown代码块标记
    2. 替换中文引号为英文引号
    3. 处理截断的JSON(移除最后一个不完整的字段)
    4. 修复常见的JSON格式错误

    Args:
        json_str: 原始JSON字符串

    Returns:
        清理后的JSON字符串
    """
    import re

    # 1. 移除markdown代码块标记
    json_str = re.sub(r'^```json\s*', '', json_str, flags=re.MULTILINE)
    json_str = re.sub(r'\s*```$', '', json_str, flags=re.MULTILINE)
    json_str = json_str.strip()

    # 2. 替换中文引号（避免干扰JSON结构）
    # 将中文双引号替换为书名号（避免与JSON字符串边界冲突）
    json_str = json_str.replace('\u201c', '\u300c').replace('\u201d', '\u300d')
    # 将中文单引号替换为书名号
    json_str = json_str.replace('\u2018', '\u300e').replace('\u2019', '\u300f')

    # 3. 处理截断的JSON - 移除最后一个不完整的字段
    # 查找最后一个完整的逗号位置
    last_comma = json_str.rfind(',')
    last_colon = json_str.rfind(':')

    # 如果最后一个冒号在最后一个逗号之后，说明最后一个字段不完整
    if last_colon > last_comma:
        # 找到最后一个逗号，截断后面的内容
        json_str = json_str[:last_comma] + '\n  }'

    # 4. 确保JSON以大括号结尾
    json_str = json_str.rstrip()
    if not json_str.endswith('}'):
        json_str = json_str.rstrip(',') + '\n}'

    # 5. 修复转义字符问题
    # 移除无效的转义序列
    json_str = re.sub(r'\\([^"\\/bfnrtu])', r'\1', json_str)

    return json_str


def parse_llm_json_response(response_text: str, logger, context: str = "") -> Dict:
    """
    解析LLM返回的JSON响应（带三级修复机制）

    Args:
        response_text: LLM响应文本
        logger: 日志对象
        context: 上下文标识（用于日志）

    Returns:
        解析后的字典，如果解析失败返回{"issues": []}
    """
    import re
    import json

    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
    if not json_match:
        logger.warning(
            f"[{context}] 未找到JSON代码块, "
            f"响应前500字: {response_text[:500]}"
        )
        return {"issues": []}

    json_str = json_match.group(1)

    # 第一次尝试：直接解析
    try:
        result = json.loads(json_str)
        return result
    except json.JSONDecodeError as e1:
        # 第二次尝试：清理后解析
        logger.info(f"[{context}] 首次JSON解析失败，尝试清理修复: {e1}")
        json_str = clean_json_string(json_str)

        try:
            result = json.loads(json_str)
            logger.info(f"[{context}] JSON清理修复成功")
            return result
        except json.JSONDecodeError as e2:
            # 第三次尝试：移除最后一个不完整对象后解析
            logger.warning(f"[{context}] 清理后仍失败，尝试移除不完整字段: {e2}")

            # 找到最后一个完整的issue对象
            last_complete_brace = json_str.rfind('}')
            if last_complete_brace > 0:
                # 截断到最后一个完整的对象
                json_str = json_str[:last_complete_brace + 1]
                # 确保issues数组闭合
                if ']' not in json_str[last_complete_brace:]:
                    json_str = json_str.rstrip('}') + ']}'

                try:
                    result = json.loads(json_str)
                    logger.info(f"[{context}] 移除不完整字段后解析成功")
                    return result
                except json.JSONDecodeError as e3:
                    logger.warning(
                        f"[{context}] 所有修复尝试均失败: {e3}, "
                        f"响应前500字: {response_text[:500]}"
                    )
                    return {"issues": []}
            else:
                logger.warning(
                    f"[{context}] JSON结构严重损坏，无法修复: {e2}"
                )
                return {"issues": []}


async def call_llm_with_retry(llm_provider, prompt: str, temperature: float = 0.3,
                              timeout: int = 1200, max_retries: int = 3,
                              retry_delay: int = 5, context: str = "") -> Any:
    """
    带重试机制的LLM调用辅助函数

    Args:
        llm_provider: LLM提供者实例
        prompt: 提示词
        temperature: 温度参数
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
        retry_delay: 初始重试延迟(秒)
        context: 上下文标识(用于日志)

    Returns:
        LLM响应对象

    Raises:
        Exception: 非429错误或重试耗尽后的错误
    """
    response = None
    for attempt in range(max_retries):
        try:
            response = await llm_provider.generate(
                prompt=prompt,
                temperature=temperature,
                timeout=timeout,
                module_name="qc_global_analyzer"
            )
            return response  # 成功则返回
        except Exception as e:
            error_str = str(e)
            if '429' in error_str or 'TooManyRequests' in error_str or 'ServerOverloaded' in error_str:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * \
                        (2 ** attempt)  # 指数退避: 5s, 10s, 20s
                    logger.warning(
                        f"[{context}] LLM返回429错误,第{attempt+1}次重试,"
                        f"等待{wait_time}秒..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"[{context}] LLM 429错误,已重试{max_retries}次,放弃")
                    raise  # 重试耗尽,抛出错误
            else:
                raise  # 其他错误直接抛出

    return response
