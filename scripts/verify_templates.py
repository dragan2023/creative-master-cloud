"""Verify templates import"""
import sys
sys.path.insert(0, '.')
from app.agents.prompt_manager.templates import DEFAULT_PROMPTS
print(f'DEFAULT_PROMPTS loaded, {len(DEFAULT_PROMPTS)} templates:')
for k, v in DEFAULT_PROMPTS.items():
    print(f'  {k:30s} -> name={v["name"]}')
