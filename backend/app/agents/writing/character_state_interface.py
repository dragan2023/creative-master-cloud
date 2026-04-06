"""
多Agent协作文学作品生成系统 - 人物状态数据交互接口

模块: agents.writing
文件: character_state_interface.py
功能: 提供人物状态更新模块与多agent正文生成系统之间的数据交互接口

依赖关系:
    - 依赖: character_state_tracker.py, base_agent.py
    - 被依赖: OrchestratorAgent, LogicEditorAgent

使用说明:
    interface = CharacterStateInterface(tracker)
    
    # 获取用于AgentContext的人物状态数据
    state_data = interface.get_state_data_for_context(chapter_num=5)
    
    # 从LogicEditorAgent结果中提取状态更新
    updates = interface.extract_state_updates_from_result(editor_result)
    
    # 应用状态更新到追踪器
    interface.apply_state_updates(updates, chapter_num=5)

创建时间: 2026-04-01
最后修改: 2026-04-01

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class CharacterStateData:
    """人物状态数据传输对象
    
    用于在模块间传递人物状态信息。
    """
    character_state_snapshot: str = ""
    relationship_summary: str = ""
    character_states: Dict[str, Any] = field(default_factory=dict)
    character_location_map: Dict[str, str] = field(default_factory=dict)
    character_identity_map: Dict[str, str] = field(default_factory=dict)
    active_characters: List[str] = field(default_factory=list)
    previous_chapter_characters: List[str] = field(default_factory=list)
    new_characters_detected: List[Dict[str, Any]] = field(default_factory=list)


class CharacterStateInterface:
    """人物状态数据交互接口
    
    提供以下核心功能：
    1. 从追踪器提取状态数据供Agent使用
    2. 从LogicEditorAgent结果中解析状态更新
    3. 将状态更新应用到追踪器
    4. 验证状态数据的一致性
    """
    
    def __init__(self, tracker=None):
        """初始化接口
        
        Args:
            tracker: CharacterStateTracker实例
        """
        self._tracker = tracker
        
        from app.core.logger import get_logger
        self.logger = get_logger("character_state_interface")
    
    def set_tracker(self, tracker) -> None:
        """设置追踪器实例
        
        Args:
            tracker: CharacterStateTracker实例
        """
        self._tracker = tracker
    
    def get_state_data_for_context(
        self, 
        chapter_num: int,
        include_history: bool = False
    ) -> CharacterStateData:
        """获取用于AgentContext的人物状态数据
        
        从追踪器中提取所有必要的状态信息，打包为传输对象。
        
        Args:
            chapter_num: 当前章节号
            include_history: 是否包含历史状态演变
            
        Returns:
            CharacterStateData: 状态数据传输对象
        """
        if not self._tracker:
            self.logger.warning("追踪器未初始化，返回空状态数据")
            return CharacterStateData()
        
        data = CharacterStateData()
        
        data.character_state_snapshot = self._tracker.get_state_for_prompt(chapter_num)
        
        data.relationship_summary = self._tracker.get_relationship_summary()
        
        all_states = self._tracker.get_all_characters()
        data.character_states = {name: state.to_dict() for name, state in all_states.items()}
        
        data.character_location_map = {
            name: state.location 
            for name, state in all_states.items() 
            if state.location
        }
        
        data.character_identity_map = {
            name: state.identity 
            for name, state in all_states.items() 
            if state.identity
        }
        
        from .character_state_tracker import CharacterStatus
        data.active_characters = [
            name for name, state in all_states.items()
            if state.status in [CharacterStatus.ACTIVE, CharacterStatus.MENTIONED]
        ]
        
        prev_snapshot = self._tracker.get_chapter_snapshot(chapter_num - 1)
        if prev_snapshot:
            data.previous_chapter_characters = list(prev_snapshot.characters.keys())
        
        if include_history:
            for name in data.active_characters[:5]:
                evolution = self._tracker.get_state_evolution(name)
                if evolution:
                    self.logger.debug(f"获取 {name} 的状态演变: {len(evolution)} 条记录")
        
        self.logger.info(
            f"获取章节 {chapter_num} 的状态数据: "
            f"{len(data.character_states)} 个人物, "
            f"{len(data.active_characters)} 个活跃"
        )
        
        return data
    
    def extract_state_updates_from_result(
        self, 
        editor_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """从LogicEditorAgent结果中提取状态更新
        
        解析逻辑编辑Agent返回的审查结果，提取人物状态更新信息。
        
        Args:
            editor_result: LogicEditorAgent的执行结果
            
        Returns:
            包含状态更新和新人物信息的字典
        """
        updates = {
            "character_state_updates": [],
            "new_characters": [],
            "relationship_changes": []
        }
        
        if not editor_result:
            return updates
        
        data = editor_result.get("data", editor_result)
        
        raw_updates = data.get("character_state_updates", [])
        for update in raw_updates:
            validated = self._validate_state_update(update)
            if validated:
                updates["character_state_updates"].append(validated)
        
        new_chars = data.get("new_characters", [])
        for char in new_chars:
            validated = self._validate_new_character(char)
            if validated:
                updates["new_characters"].append(validated)
        
        for update in raw_updates:
            if "relationships" in update.get("updates", {}):
                char_name = update.get("character", "")
                rels = update["updates"]["relationships"]
                for related_char, relation in rels.items():
                    updates["relationship_changes"].append({
                        "character1": char_name,
                        "character2": related_char,
                        "relation": relation
                    })
        
        self.logger.info(
            f"提取状态更新: {len(updates['character_state_updates'])} 个状态变化, "
            f"{len(updates['new_characters'])} 个新人物, "
            f"{len(updates['relationship_changes'])} 个关系变化"
        )
        
        return updates
    
    def _validate_state_update(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """验证状态更新数据
        
        Args:
            update: 原始状态更新数据
            
        Returns:
            验证后的数据，如果无效返回None
        """
        if not isinstance(update, dict):
            return None
        
        character = update.get("character", "")
        if not character:
            return None
        
        updates = update.get("updates", {})
        if not updates:
            return None
        
        valid_fields = {"location", "identity", "status_change", "relationships", "status"}
        filtered_updates = {k: v for k, v in updates.items() if k in valid_fields}
        
        if not filtered_updates:
            return None
        
        return {
            "character": character,
            "updates": filtered_updates,
            "evidence": update.get("evidence", "")
        }
    
    def _validate_new_character(self, char: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """验证新人物数据
        
        Args:
            char: 原始新人物数据
            
        Returns:
            验证后的数据，如果无效返回None
        """
        if not isinstance(char, dict):
            return None
        
        name = char.get("name", "")
        if not name:
            return None
        
        return {
            "name": name,
            "identity": char.get("identity", ""),
            "location": char.get("location", ""),
            "attributes": char.get("attributes", {}),
            "first_appearance_context": char.get("first_appearance_context", "")
        }
    
    def apply_state_updates(
        self,
        updates: Dict[str, Any],
        chapter_num: int,
        chapter_title: str = ""
    ) -> bool:
        """将状态更新应用到追踪器
        
        Args:
            updates: 状态更新数据（来自extract_state_updates_from_result）
            chapter_num: 当前章节号
            chapter_title: 章节标题
            
        Returns:
            是否应用成功
        """
        if not self._tracker:
            self.logger.warning("追踪器未初始化，无法应用状态更新")
            return False
        
        try:
            for update in updates.get("character_state_updates", []):
                char_name = update.get("character", "")
                char_updates = update.get("updates", {})
                
                if char_name and char_updates:
                    self._tracker.update_character_state(
                        name=char_name,
                        updates=char_updates,
                        chapter_num=chapter_num
                    )
                    self.logger.debug(f"更新人物状态: {char_name} -> {char_updates}")
            
            for new_char in updates.get("new_characters", []):
                name = new_char.get("name", "")
                if name:
                    self._tracker.update_character_state(
                        name=name,
                        updates={
                            "identity": new_char.get("identity", ""),
                            "location": new_char.get("location", ""),
                            "attributes": new_char.get("attributes", {})
                        },
                        chapter_num=chapter_num
                    )
                    self.logger.info(f"添加新人物: {name}")
            
            for rel_change in updates.get("relationship_changes", []):
                char1 = rel_change.get("character1", "")
                char2 = rel_change.get("character2", "")
                relation = rel_change.get("relation", "")
                
                if char1 and char2 and relation:
                    self._tracker.add_relationship_change(
                        chapter_num=chapter_num,
                        char1=char1,
                        char2=char2,
                        relationship_type="人物关系",
                        previous_state="",
                        new_state=relation,
                        description=relation
                    )
            
            self.logger.info(
                f"章节 {chapter_num} 状态更新已应用: "
                f"{len(updates.get('character_state_updates', []))} 个状态变化, "
                f"{len(updates.get('new_characters', []))} 个新人物"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"应用状态更新失败: {e}")
            return False
    
    def check_state_consistency(
        self,
        content: str,
        chapter_num: int
    ) -> Dict[str, Any]:
        """检查内容与人物状态的一致性
        
        Args:
            content: 章节内容
            chapter_num: 章节号
            
        Returns:
            一致性检查结果
        """
        if not self._tracker:
            return {"consistent": True, "issues": []}
        
        result = self._tracker.check_consistency(chapter_num, content)
        
        additional_issues = []
        
        location_map = self._tracker.get_all_characters()
        for name, state in location_map.items():
            if state.location and name in content:
                if state.location not in content:
                    prev_snapshot = self._tracker.get_chapter_snapshot(chapter_num - 1)
                    if prev_snapshot and name in prev_snapshot.characters:
                        prev_state = prev_snapshot.characters[name]
                        if prev_state.location and prev_state.location != state.location:
                            pass
            
        result["additional_issues"] = additional_issues
        
        return result
    
    def get_character_location_context(
        self,
        character_names: List[str]
    ) -> Dict[str, str]:
        """获取指定人物的当前位置上下文
        
        用于场景生成时确定人物的初始位置。
        
        Args:
            character_names: 人物名称列表
            
        Returns:
            人物位置映射字典
        """
        if not self._tracker:
            return {}
        
        location_map = {}
        all_states = self._tracker.get_all_characters()
        
        for name in character_names:
            if name in all_states:
                state = all_states[name]
                if state.location:
                    location_map[name] = state.location
        
        return location_map
    
    def get_character_identity_context(
        self,
        character_names: List[str]
    ) -> Dict[str, str]:
        """获取指定人物的当前身份上下文
        
        用于对话生成时确定人物的称呼和身份。
        
        Args:
            character_names: 人物名称列表
            
        Returns:
            人物身份映射字典
        """
        if not self._tracker:
            return {}
        
        identity_map = {}
        all_states = self._tracker.get_all_characters()
        
        for name in character_names:
            if name in all_states:
                state = all_states[name]
                if state.identity:
                    identity_map[name] = state.identity
        
        return identity_map
    
    def prepare_context_for_scene(
        self,
        scene_characters: List[str],
        scene_location: str = ""
    ) -> Dict[str, Any]:
        """为场景生成准备人物状态上下文
        
        整合场景所需的所有人物状态信息。
        
        Args:
            scene_characters: 场景出场人物
            scene_location: 场景地点
            
        Returns:
            场景人物状态上下文
        """
        context = {
            "characters": {},
            "location_conflicts": [],
            "relationship_hints": []
        }
        
        if not self._tracker:
            return context
        
        all_states = self._tracker.get_all_characters()
        
        for name in scene_characters:
            if name in all_states:
                state = all_states[name]
                context["characters"][name] = {
                    "identity": state.identity,
                    "location": state.location,
                    "status_change": state.status_change,
                    "relationships": state.relationships
                }
                
                if scene_location and state.location and state.location != scene_location:
                    context["location_conflicts"].append({
                        "character": name,
                        "current_location": state.location,
                        "scene_location": scene_location,
                        "suggestion": f"需要描述{state.location}到{scene_location}的移动过程"
                    })
        
        for i, char1 in enumerate(scene_characters):
            for char2 in scene_characters[i+1:]:
                if char1 in all_states and char2 in all_states:
                    state1 = all_states[char1]
                    if char2 in state1.relationships:
                        context["relationship_hints"].append({
                            "characters": [char1, char2],
                            "relationship": state1.relationships[char2]
                        })
        
        return context


def create_character_state_interface(tracker=None) -> CharacterStateInterface:
    """工厂函数：创建人物状态接口实例
    
    Args:
        tracker: CharacterStateTracker实例（可选）
        
    Returns:
        CharacterStateInterface实例
    """
    return CharacterStateInterface(tracker=tracker)
