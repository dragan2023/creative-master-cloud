#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证提示词模板修改"""

from app.agents.prompt_manager.templates import DEFAULT_PROMPTS
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))


def verify_template():
    """验证模板修改"""
    print("=" * 60)
    print("提示词模板验证")
    print("=" * 60)

    # 获取模板
    template = DEFAULT_PROMPTS.get('novel_unit_summaries')

    if not template:
        print("❌ 错误: 找不到 novel_unit_summaries 模板")
        return False

    print(f"✅ 模板加载成功")
    print(f"模板名称: {template['name']}")
    print(f"变量: {template['variables']}")
    print(f"内容长度: {len(template['content'])} 字符")
    print()

    # 检查关键改进点
    checks = [
        ('绝对红线', '绝对红线' in template['content']),
        ('人物设定核对清单', '人物设定核对清单' in template['content']),
        ('绝对禁止的行为', '绝对禁止的行为' in template['content']),
        ('称谓准确性', '称谓准确性' in template['content']),
        ('输出前强制检查', '输出前强制检查' in template['content']),
        ('最终完整性验证', '最终完整性验证' in template['content']),
        ('全局大纲是绝对权威', '全局大纲是绝对权威' in template['content']),
    ]

    print("关键改进点检查:")
    all_passed = True
    for name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("=" * 60)
        print("✅ 所有检查通过！提示词模板修改成功！")
        print("=" * 60)
        return True
    else:
        print("=" * 60)
        print("❌ 部分检查未通过，请检查模板内容")
        print("=" * 60)
        return False


if __name__ == '__main__':
    success = verify_template()
    sys.exit(0 if success else 1)
