"""CharacterStateTracker包 - 替代原单文件，保持向后兼容"""
from app.agents.writing.character_state_tracker.impl import CharacterStateTracker
from app.agents.writing.character_state_tracker.impl.generator import get_character_state_tracker
from app.agents.writing.character_state_tracker.api import CharacterState
from app.agents.writing.character_state_tracker.api import ChapterSnapshot
from app.agents.writing.character_state_tracker.api import RelationshipChange

__all__ = ['CharacterStateTracker', 'get_character_state_tracker', 'CharacterState', 'ChapterSnapshot', 'RelationshipChange']
