"""
拆分 tools/style_library.py (1687行) → 包结构
策略：将大型STYLE_LIBRARY数据字典提取为JSON文件，代码逻辑保留为Python模块
"""
import json
import re
from pathlib import Path

BASE = Path(r"f:\python_project\全能创意大师（开发版）\backend\app\tools")
SOURCE = BASE / "style_library.py"
TARGET = BASE / "style_library"

content = SOURCE.read_text(encoding='utf-8')
lines = content.split('\n')
print(f"源文件: {len(lines)}行")

# 创建目标目录
TARGET.mkdir(parents=True, exist_ok=True)

# 1. 提取STYLE_LIBRARY数据
# 找到STYLE_LIBRARY定义的开始和结束
lib_start = None
lib_end = None
brace_count = 0

for i, line in enumerate(lines):
    if line.startswith('STYLE_LIBRARY = {'):
        lib_start = i
        brace_count = 1
        continue
    if lib_start is not None and brace_count > 0:
        brace_count += line.count('{') + line.count('[')
        brace_count -= line.count('}') + line.count(']')
        if brace_count <= 0:
            lib_end = i + 1
            break

print(f"STYLE_LIBRARY数据: L{lib_start+1}-L{lib_end}")

# 2. 识别各个分类的数据范围
categories = {}
current_category = None
for i in range(lib_start, lib_end):
    line = lines[i]
    # 检测分类键
    m = re.match(r'\s+"(\w+)":\s*\{', line)
    if m and i > lib_start + 5:
        # 可能是分类
        key = m.group(1)
        if key in ['traditional', 'modern', 'genre', 'network', 'custom']:
            current_category = key
            categories[current_category] = i

print(f"发现分类: {list(categories.keys())}")

# 3. 将整个STYLE_LIBRARY提取为JSON
# 执行原始Python代码来获取数据
# 创建数据目录
data_dir = TARGET / "data"
data_dir.mkdir(parents=True, exist_ok=True)

# 执行源文件中的STYLE_LIBRARY定义
style_lib_code = '\n'.join(lines[lib_start:lib_end])
local_vars = {}
try:
    exec(style_lib_code, {}, local_vars)
    style_data = local_vars.get('STYLE_LIBRARY', {})
    
    # 按分类保存为独立JSON文件
    if 'categories' in style_data:
        for cat_key, cat_data in style_data['categories'].items():
            cat_file = data_dir / f"{cat_key}.json"
            with open(cat_file, 'w', encoding='utf-8') as f:
                json.dump(cat_data, f, ensure_ascii=False, indent=2)
            print(f"  ✅ {cat_key}.json ({len(json.dumps(cat_data, ensure_ascii=False))} chars)")
    
    # 保存版本信息
    meta = {k: v for k, v in style_data.items() if k != 'categories'}
    with open(data_dir / "_meta.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  ✅ _meta.json")
    
except Exception as e:
    print(f"  ⚠️ 无法执行STYLE_LIBRARY: {e}")
    print(f"  将保留原始数据在源文件中")

# 4. 提取工具函数
func_starts = []
for i, line in enumerate(lines):
    m = re.match(r'^(def |async def )(\w+)\(', line)
    if m:
        func_starts.append((i, m.group(2)))

# 生成函数文件
func_groups = {
    "query": ["get_style_by_id", "get_styles_by_category", "get_all_categories"],
    "fusion": ["build_style_guide", "_check_style_compatibility"],
    "apply": ["apply_style_to_project_metadata", "get_style_guide_from_project"],
    "format": ["format_style_for_prompt", "get_style_list_for_api"],
}

for group_name, func_names in func_groups.items():
    func_lines = []
    for fname in func_names:
        for idx, (fline, fref) in enumerate(func_starts):
            if fref == fname:
                # 找函数结束位置
                end = len(lines)
                for j in range(fline + 1, len(lines)):
                    if lines[j] and not lines[j].startswith(' ') and not lines[j].startswith('@'):
                        end = j
                        break
                func_lines.extend(lines[fline:end])
                func_lines.append('')
                break
    
    if func_lines:
        group_content = f'"""文风库 - {group_name}工具函数"""\nfrom typing import Dict, List, Optional\nimport json\nimport os\n\n'
        group_content += '# 从数据目录加载文风数据\n_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")\n\n\n'
        group_content += '\n'.join(func_lines)
        
        group_file = TARGET / f"{group_name}.py"
        group_file.write_text(group_content, encoding='utf-8')
        total = len(group_content.split('\n'))
        print(f"  ✅ {group_name}.py ({total}行)")

# 5. 生成加载器模块
loader_content = '''"""文风库 - 数据加载器"""
import json
import os
from typing import Dict, List, Optional

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_style_library() -> Dict:
    """加载完整的文风库数据"""
    meta_path = os.path.join(_DATA_DIR, "_meta.json")
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    
    categories = {}
    for cat_file in os.listdir(_DATA_DIR):
        if cat_file.endswith('.json') and cat_file != '_meta.json':
            cat_key = cat_file[:-5]  # 去掉.json
            with open(os.path.join(_DATA_DIR, cat_file), 'r', encoding='utf-8') as f:
                categories[cat_key] = json.load(f)
    
    return {
        **meta,
        "categories": categories
    }


# 模块级缓存
_STYLE_LIBRARY = None


def get_style_library() -> Dict:
    """获取文风库数据（带缓存）"""
    global _STYLE_LIBRARY
    if _STYLE_LIBRARY is None:
        _STYLE_LIBRARY = _load_style_library()
    return _STYLE_LIBRARY


# 兼容性：保持STYLE_LIBRARY可导入
STYLE_LIBRARY = property(lambda self: get_style_library())
'''

(TARGET / "loader.py").write_text(loader_content, encoding='utf-8')
print(f"  ✅ loader.py")

# 6. 生成 __init__.py (保持向后兼容)
init_content = '''"""小说文风知识库

此包替代原 style_library.py 单文件，保持完全向后兼容。

使用方式不变：
    from app.tools.style_library import STYLE_LIBRARY, get_style_by_id
"""
import os
from typing import Dict, List, Optional

# 数据目录
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_style_library() -> Dict:
    """懒加载文风库数据"""
    import json
    meta_path = os.path.join(_DATA_DIR, "_meta.json")
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    
    categories = {}
    if os.path.isdir(_DATA_DIR):
        for cat_file in os.listdir(_DATA_DIR):
            if cat_file.endswith('.json') and cat_file != '_meta.json':
                cat_key = cat_file[:-5]
                with open(os.path.join(_DATA_DIR, cat_file), 'r', encoding='utf-8') as f:
                    categories[cat_key] = json.load(f)
    
    return {**meta, "categories": categories}


# 兼容原模块的STYLE_LIBRARY变量
# 首次访问时自动加载
_STYLE_LIBRARY_CACHE = None


def _get_style_library():
    global _STYLE_LIBRARY_CACHE
    if _STYLE_LIBRARY_CACHE is None:
        _STYLE_LIBRARY_CACHE = _load_style_library()
    return _STYLE_LIBRARY_CACHE


class _StyleLibraryProxy(dict):
    """代理dict，首次访问时自动加载"""
    def __init__(self):
        super().__init__()
        self._loaded = False
    
    def _ensure_loaded(self):
        if not self._loaded:
            self.update(_get_style_library())
            self._loaded = True
    
    def __getitem__(self, key):
        self._ensure_loaded()
        return super().__getitem__(key)
    
    def __contains__(self, key):
        self._ensure_loaded()
        return super().__contains__(key)
    
    def keys(self):
        self._ensure_loaded()
        return super().keys()
    
    def values(self):
        self._ensure_loaded()
        return super().values()
    
    def items(self):
        self._ensure_loaded()
        return super().items()
    
    def get(self, key, default=None):
        self._ensure_loaded()
        return super().get(key, default)


STYLE_LIBRARY = _StyleLibraryProxy()


# 导出工具函数
from app.tools.style_library.query import get_style_by_id, get_styles_by_category, get_all_categories
from app.tools.style_library.fusion import build_style_guide, _check_style_compatibility
from app.tools.style_library.apply import apply_style_to_project_metadata, get_style_guide_from_project
from app.tools.style_library.format import format_style_for_prompt, get_style_list_for_api

__all__ = [
    "STYLE_LIBRARY",
    "get_style_by_id", "get_styles_by_category", "get_all_categories",
    "build_style_guide", "_check_style_compatibility",
    "apply_style_to_project_metadata", "get_style_guide_from_project",
    "format_style_for_prompt", "get_style_list_for_api",
]
'''

(TARGET / "__init__.py").write_text(init_content, encoding='utf-8')
print(f"  ✅ __init__.py")

# 验证
try:
    import ast
    ast.parse((TARGET / "__init__.py").read_text(encoding='utf-8'))
    ast.parse((TARGET / "loader.py").read_text(encoding='utf-8'))
    for f in TARGET.glob("*.py"):
        if f.name not in ['__init__.py', 'loader.py']:
            ast.parse(f.read_text(encoding='utf-8'))
    print(f"\n✅ 语法验证通过")
except SyntaxError as e:
    print(f"\n❌ 语法错误: {e}")
