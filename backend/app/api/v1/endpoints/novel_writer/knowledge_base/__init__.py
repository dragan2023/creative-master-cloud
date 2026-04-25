"""知识库管理 API 端点包

从 knowledge_base.py (1447行) 拆分为以下模块：
- _kb_crud.py: 知识库 CRUD（构建/状态/配置/删除）
- _kg.py: 知识图谱（获取/构建/批量/状态）
- _consistency.py: 一致性检查（报告/人物/实体/内容检查/历史）

所有端点注册到 novel_writer/utils.py 的共享 router
"""
from . import _kb_crud   # 注册知识库 CRUD 端点
from . import _kg        # 注册知识图谱端点
from . import _consistency  # 注册一致性检查端点
