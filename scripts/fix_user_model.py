"""修复 user.py - 添加 novel_projects relationship"""
import os

user_py_path = r'F:\python_project\writer_master\backend\app\models\user.py'

with open(user_py_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'from sqlalchemy import Column, String, Boolean',
    'from sqlalchemy import Column, String, Boolean\nfrom sqlalchemy.orm import relationship'
).replace(
    '    def __repr__(self):',
    '    novel_projects = relationship("NovelProject", back_populates="user")\n\n    def __repr__(self):'
)

with open(user_py_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed user.py - added novel_projects relationship')
