# -*- coding: utf-8 -*-
"""验证新风格集成"""
from app.tools.style_library import STYLE_LIBRARY, get_styles_by_category, get_style_by_id
import sys
sys.path.insert(0, 'backend')


print("=" * 60)
print("验证新增网络小说风格集成")
print("=" * 60)

print(f"\n总风格数: {STYLE_LIBRARY['total_styles']}")
print(f"版本号: {STYLE_LIBRARY['version']}")

web_novel = get_styles_by_category('web_novel')
print(f"网络小说风格数: {len(web_novel)}")

# 验证几个关键的新风格
test_ids = ['madness_literature', 'chinese_cthulhu', 'oriental_aesthetics']
print("\n验证关键新风格:")
for style_id in test_ids:
    style = get_style_by_id(style_id)
    if style:
        print(f"  ✅ {style_id}: {style['name']}")
    else:
        print(f"  ❌ {style_id}: 未找到")

print("\n✅ 验证完成！")
