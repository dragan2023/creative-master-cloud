"""测试 JSON 解析中的键名问题"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 模拟 LLM 返回的 JSON（键名包含换行符和引号）
test_json = '''{
  "entities": [
    {
      "\\n  \\"text\\"": "晋升为监察御史",
      "\\n  \\"type\\"": "身份变化",
      "\\n  \\"character\\"": "范闲",
      "description": "从平民被皇帝任命为监察御史"
    }
  ],
  "relations": [],
  "summary": "测试"
}'''

print('=== 测试 JSON 解析 ===')
print(f'原始 JSON 长度: {len(test_json)}')

# 解析 JSON
result = json.loads(test_json)
print(f'解析成功，实体数: {len(result.get("entities", []))}')

# 检查第一个实体的键
entity = result['entities'][0]
print(f'第一个实体的键: {list(entity.keys())}')

# 尝试访问 text 字段
text_value = entity.get('text')
print(f'entity.get("text"): {text_value}')

# 尝试用原始键访问
print('\n原始键名和值:')
for key in entity.keys():
    print(f'  键名: {key!r}, 值: {entity[key]}')

# 测试 _normalize_key_name 方法
print('\n测试键名清理:')
from app.tools.novel_graph_rag import NovelEntityExtractor

class MockLogger:
    def debug(self, msg): print(f"[DEBUG] {msg}")
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARNING] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")

extractor = NovelEntityExtractor.__new__(NovelEntityExtractor)
extractor.logger = MockLogger()

# 测试键名规范化
test_keys = ['\n  "text"', '"text"', ' text ', 'text']
for key in test_keys:
    normalized = extractor._normalize_key_name(key)
    print(f'  {key!r} -> {normalized!r}')

# 测试 _fix_entity_keys 方法
print('\n测试 _fix_entity_keys 方法:')
fixed_result = extractor._fix_entity_keys(result)
print(f'修复后实体数: {len(fixed_result.get("entities", []))}')
if fixed_result.get('entities'):
    fixed_entity = fixed_result['entities'][0]
    print(f'修复后第一个实体的键: {list(fixed_entity.keys())}')
    print(f'修复后 text 值: {fixed_entity.get("text")}')
