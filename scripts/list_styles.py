# -*- coding: utf-8 -*-
"""快速查看网络小说风格列表"""

from app.tools.style_library import get_styles_by_category
import sys
from pathlib import Path

backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))


styles = get_styles_by_category('web_novel')
print(f'总数: {len(styles)}\n')
for i, s in enumerate(styles, 1):
    print(f'{i}. {s["id"]}: {s["name"]}')
