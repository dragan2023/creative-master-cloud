"""
为单元质控分析器添加LLM重试机制
批量替换所有 llm_provider.generate 调用
"""
import re


def add_retry_to_unit_analyzer(file_path):
    """为单元质控分析器文件添加重试机制"""

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 在文件开头添加导入
    if 'from app.services.quality_control.llm_retry_helper import llm_call_with_retry' not in content:
        # 找到第一个import语句的位置
        import_pattern = r'(from app\.core\.logger import get_logger\n)'
        replacement = r'\1from app.services.quality_control.llm_retry_helper import llm_call_with_retry\n'
        content = re.sub(import_pattern, replacement, content, count=1)

    # 2. 替换所有 llm_provider.generate 调用
    # 匹配模式: response = await llm_provider.generate(prompt=prompt, temperature=0.2)
    pattern = r'response = await llm_provider\.generate\(prompt=prompt, temperature=([\d.]+)\)'

    # 需要统计替换次数
    count = 0

    def replace_with_retry(match):
        nonlocal count
        count += 1
        temperature = match.group(1)
        return f'response = await llm_call_with_retry(llm_provider, prompt=prompt, temperature={temperature}, context="单元质控分析")'

    content = re.sub(pattern, replace_with_retry, content)

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return count


if __name__ == '__main__':
    file_path = r'f:\python_project\全能创意大师（开发版）\backend\app\services\quality_control\analyzers\unit_quality_analyzer.py'
    count = add_retry_to_unit_analyzer(file_path)
    print(f"成功替换 {count} 处LLM调用")
