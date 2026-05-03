"""
提示词模板 - 格式化和分发函数

包含 get_chapter_prompt, get_episode_prompt, get_scene_script_prompt 等主函数。
"""

from typing import Dict, Any, Optional

from ._novel import NOVEL_CHAPTER_PROMPT, DIRECTORY_GENERATE_PROMPT, CHAPTER_NAMES_GENERATE_PROMPT, CHAPTER_DETAILED_OUTLINE_PROMPT
from ._series import (
    SERIES_SCRIPT_SCENE_PROMPT, SERIES_SCRIPT_EPISODE_PROMPT,
    EPISODE_NAMES_GENERATE_PROMPT, SCRIPT_DIRECTORY_PROMPT, EPISODE_DETAILED_OUTLINE_PROMPT
)
from ._movie import (
    MOVIE_SCRIPT_SCENE_PROMPT, MOVIE_DIRECTORY_PROMPT,
    MOVIE_SCENE_NAMES_PROMPT, SCENE_DETAILED_OUTLINE_PROMPT
)
from ._virtual import SERIES_SCRIPT_VIRTUAL_PROMPT, MOVIE_SCRIPT_VIRTUAL_PROMPT


def get_chapter_prompt(
    content_type: str,
    chapter_number: int,
    chapter_title: str,
    chapter_metadata: Dict[str, Any],
    context: Dict[str, Any],
    generation_config: Dict[str, Any],
    type_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    获取章节生成提示词
    """
    if content_type == "novel":
        target_platform = ""
        words_per_chapter = 3000
        tone = "正剧"
        narrative_perspective = "第三人称"

        if type_config:
            target_platform = type_config.get("target_platform", "")
            words_per_chapter = type_config.get("words_per_chapter", 3000)
            tone = type_config.get("tone", "正剧")
            narrative_perspective = type_config.get("narrative_perspective", "第三人称")

        return NOVEL_CHAPTER_PROMPT.format(
            outline_metadata=context.get("outline_metadata", ""),
            chapter_detailed_outline=context.get("chapter_detailed_outline", ""),
            current_unit_outline=context.get("current_unit_outline", ""),
            previous_content_summaries=context.get("previous_content_summaries", ""),
            previous_outline_summaries=context.get("previous_outline_summaries", ""),
            global_summary=context.get("global_summary", ""),
            character_state=context.get("character_state", ""),
            short_summary=context.get("short_summary", ""),
            knowledge_context=context.get("knowledge_context", ""),
            vector_context=context.get("vector_context", ""),
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_role=chapter_metadata.get("chapter_role", ""),
            chapter_purpose=chapter_metadata.get("chapter_purpose", ""),
            suspense_level=chapter_metadata.get("suspense_level", ""),
            foreshadowing=chapter_metadata.get("foreshadowing", ""),
            plot_twist_level=chapter_metadata.get("plot_twist_level", ""),
            chapter_summary=chapter_metadata.get("chapter_summary", ""),
            words_per_chapter=words_per_chapter,
            tone=tone,
            narrative_perspective=narrative_perspective,
            target_platform=target_platform
        )

    elif content_type == "series_script":
        series_type = "电视剧"
        format_standard = "标准格式"
        dialogue_narration_ratio = "均衡"
        target_broadcast = ""

        if type_config:
            series_type = type_config.get("series_type", "电视剧")
            format_standard = type_config.get("format_standard", "标准格式")
            dialogue_narration_ratio = type_config.get("dialogue_narration_ratio", "均衡")
            target_broadcast = type_config.get("target_broadcast", "")

        scene_metadata = chapter_metadata.get("scene_metadata", {})

        return SERIES_SCRIPT_SCENE_PROMPT.format(
            outline_metadata=context.get("outline_metadata", ""),
            episode_outline=context.get("episode_outline", ""),
            previous_episodes_summary=context.get("previous_episodes_summary", ""),
            previous_content_summaries=context.get("previous_content_summaries", ""),
            current_unit_outline=context.get("current_unit_outline", ""),
            series_type=series_type,
            format_standard=format_standard,
            dialogue_narration_ratio=dialogue_narration_ratio,
            target_broadcast=target_broadcast,
            episode_number=chapter_metadata.get("episode_number", 1),
            scene_number=scene_metadata.get("scene_number", chapter_number),
            location=scene_metadata.get("location", "未指定"),
            interior_exterior=scene_metadata.get("interior_exterior", "内"),
            time_of_day=scene_metadata.get("time_of_day", "日"),
            characters_present=", ".join(scene_metadata.get("characters_present", [])),
            scene_purpose=chapter_metadata.get("chapter_summary", ""),
            previous_scene_ending=context.get("previous_scene_ending", ""),
            character_states=context.get("character_states", ""),
            knowledge_context=context.get("knowledge_context", ""),
            duration_minutes=scene_metadata.get("duration_minutes") or 3,
            dialogue_style=generation_config.get("dialogue_style", "自然对话"),
            narrative_rhythm=generation_config.get("narrative_rhythm", "紧凑")
        )

    elif content_type == "movie_script":
        movie_type = "院线电影"
        total_duration = 90
        format_standard = "标准格式"
        dialogue_narration_ratio = "均衡"
        target_platform = ""

        if type_config:
            movie_type = type_config.get("movie_type", "院线电影")
            total_duration = type_config.get("total_duration", 90)
            format_standard = type_config.get("format_standard", "标准格式")
            dialogue_narration_ratio = type_config.get("dialogue_narration_ratio", "均衡")
            target_platform = type_config.get("target_platform", "")

        scene_metadata = chapter_metadata.get("scene_metadata", {})

        return MOVIE_SCRIPT_SCENE_PROMPT.format(
            outline_content=context.get("outline_content", ""),
            current_unit_outline=context.get("current_unit_outline", ""),
            movie_type=movie_type,
            total_duration=total_duration,
            format_standard=format_standard,
            dialogue_narration_ratio=dialogue_narration_ratio,
            target_platform=target_platform,
            scene_number=scene_metadata.get("scene_number", chapter_number),
            location=scene_metadata.get("location", "未指定"),
            interior_exterior=scene_metadata.get("interior_exterior", "内"),
            time_of_day=scene_metadata.get("time_of_day", "日"),
            characters_present=", ".join(scene_metadata.get("characters_present", [])),
            scene_purpose=chapter_metadata.get("chapter_summary", ""),
            previous_scene_ending=context.get("previous_scene_ending", ""),
            previous_scenes_summary=context.get("previous_scenes_summary", ""),
            global_summary=context.get("global_summary", ""),
            vector_context=context.get("vector_context", ""),
            character_states=context.get("character_states", ""),
            knowledge_context=context.get("knowledge_context", ""),
            duration_minutes=scene_metadata.get("duration_minutes") or 3,
            estimated_words=int((scene_metadata.get("duration_minutes") or 3) * 250),
            dialogue_style=generation_config.get("dialogue_style", "自然对话"),
            narrative_rhythm=generation_config.get("narrative_rhythm", "紧凑")
        )

    else:
        if content_type in ("script", "series_script", "movie_script"):
            format_standard = "标准格式"
            dialogue_narration_ratio = "均衡"

            if type_config:
                format_standard = type_config.get("format_standard", "标准格式")
                dialogue_narration_ratio = type_config.get("dialogue_narration_ratio", "均衡")

            return SERIES_SCRIPT_SCENE_PROMPT.format(
                outline_content=context.get("outline_content", ""),
                episode_outline=context.get("episode_outline", ""),
                previous_episodes_summary=context.get("previous_episodes_summary", ""),
                current_unit_outline=context.get("current_unit_outline", ""),
                series_type="电视剧",
                format_standard=format_standard,
                dialogue_narration_ratio=dialogue_narration_ratio,
                target_broadcast="",
                episode_number=1,
                scene_number=chapter_number,
                location=chapter_metadata.get("scene_metadata", {}).get("location", "未指定"),
                interior_exterior=chapter_metadata.get("scene_metadata", {}).get("interior_exterior", "内"),
                time_of_day=chapter_metadata.get("scene_metadata", {}).get("time_of_day", "日"),
                characters_present=", ".join(chapter_metadata.get("scene_metadata", {}).get("characters_present", [])),
                scene_purpose=chapter_metadata.get("chapter_summary", ""),
                previous_scene_ending=context.get("previous_scene_ending", ""),
                character_states=context.get("character_states", ""),
                knowledge_context=context.get("knowledge_context", ""),
                duration_minutes=chapter_metadata.get("scene_metadata", {}).get("duration_minutes", 3),
                dialogue_style=generation_config.get("dialogue_style", "自然对话"),
                narrative_rhythm=generation_config.get("narrative_rhythm", "紧凑")
            )
        else:
            return NOVEL_CHAPTER_PROMPT.format(
                outline_content=context.get("outline_content", ""),
                current_unit_outline=context.get("current_unit_outline", ""),
                global_summary=context.get("global_summary", ""),
                character_state=context.get("character_state", ""),
                short_summary=context.get("short_summary", ""),
                knowledge_context=context.get("knowledge_context", ""),
                vector_context=context.get("vector_context", ""),
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_role=chapter_metadata.get("chapter_role", ""),
                chapter_purpose=chapter_metadata.get("chapter_purpose", ""),
                suspense_level=chapter_metadata.get("suspense_level", ""),
                foreshadowing=chapter_metadata.get("foreshadowing", ""),
                plot_twist_level=chapter_metadata.get("plot_twist_level", ""),
                chapter_summary=chapter_metadata.get("chapter_summary", ""),
                words_per_chapter=generation_config.get("words_per_chapter", 3000),
                tone=generation_config.get("tone", "正剧"),
                narrative_perspective=generation_config.get("narrative_perspective", "第三人称"),
                target_platform=""
            )


def get_episode_prompt(
    episode_number: int,
    episode_title: str,
    episode_outline: Dict[str, Any],
    context: Dict[str, Any],
    type_config: Optional[Dict[str, Any]] = None,
    generation_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    获取连续剧单集正文生成提示词（新版：一集完整正文）
    """
    generation_config = generation_config or {}

    series_type = "电视剧"
    format_standard = "标准格式"
    dialogue_narration_ratio = "均衡"
    target_broadcast = ""
    words_per_episode = 5000
    script_mode = "real"

    if type_config:
        series_type = type_config.get("series_type", "电视剧")
        format_standard = type_config.get("format_standard", "标准格式")
        dialogue_narration_ratio = type_config.get("dialogue_narration_ratio", "均衡")
        target_broadcast = type_config.get("target_broadcast", "")
        words_per_episode = type_config.get("words_per_episode", 5000)
        script_mode = type_config.get("script_mode", "real")

    scenes = episode_outline.get("scenes", [])
    scenes_info = ""
    if scenes:
        scenes_lines = []
        for scene in scenes:
            scene_num = scene.get("scene_number", "")
            location = scene.get("location", "未指定")
            int_ext = scene.get("interior_exterior", "内")
            time_of_day = scene.get("time_of_day", "日")
            core_content = scene.get("core_content", scene.get("scene_purpose", ""))
            main_chars = scene.get("main_characters", scene.get("characters_present", ""))
            duration = scene.get("estimated_duration") or scene.get("duration_minutes") or 3
            scenes_lines.append(
                f"第{scene_num}场 {int_ext}景 {location} {time_of_day} | {core_content} | {main_chars} | {duration}分钟"
            )
        scenes_info = "\n".join(scenes_lines)
    else:
        scenes_info = "（未提供场景规划，请根据剧情大纲自行设计场景）"

    if script_mode == "virtual":
        prompt_template = SERIES_SCRIPT_VIRTUAL_PROMPT
    else:
        prompt_template = SERIES_SCRIPT_EPISODE_PROMPT

    return prompt_template.format(
        outline_metadata=context.get("outline_metadata", ""),
        outline_content=context.get("outline_content", ""),
        episode_outline=context.get("episode_outline", ""),
        previous_episodes_summary=context.get("previous_episodes_summary", ""),
        previous_content_summaries=context.get("previous_content_summaries", ""),
        global_summary=context.get("global_summary", ""),
        previous_scene_ending=context.get("previous_scene_ending", ""),
        vector_context=context.get("vector_context", ""),
        current_unit_outline=context.get("current_unit_outline", ""),
        episode_number=episode_number,
        episode_title=episode_title,
        core_conflict=episode_outline.get("core_conflict", "未指定"),
        emotional_curve=episode_outline.get("emotional_curve", "未指定"),
        estimated_duration=episode_outline.get("estimated_duration") or 40,
        scenes_info=scenes_info,
        scene_number=1,
        location=episode_outline.get("location", "未指定"),
        interior_exterior=episode_outline.get("interior_exterior", "内"),
        time_of_day=episode_outline.get("time_of_day", "日"),
        characters_present=episode_outline.get("main_characters", "未指定"),
        scene_purpose=episode_outline.get("core_content", ""),
        series_type=series_type,
        format_standard=format_standard,
        dialogue_narration_ratio=dialogue_narration_ratio,
        target_broadcast=target_broadcast,
        key_dialogues=episode_outline.get("key_dialogues", "未提供"),
        character_states=context.get("character_states", ""),
        knowledge_context=context.get("knowledge_context", ""),
        dialogue_style=generation_config.get("dialogue_style", "自然对话"),
        narrative_rhythm=generation_config.get("narrative_rhythm", "紧凑"),
        words_per_episode=words_per_episode
    )


def get_scene_script_prompt(
    scene_number: int,
    scene_title: str,
    scene_outline: Dict[str, Any],
    context: Dict[str, Any],
    type_config: Optional[Dict[str, Any]] = None,
    generation_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    获取电影单场景正文生成提示词
    """
    generation_config = generation_config or {}

    movie_type = "院线电影"
    format_standard = "标准格式"
    dialogue_narration_ratio = "均衡"
    target_platform = "院线"
    total_duration = 120
    script_mode = "real"

    if type_config:
        movie_type = type_config.get("movie_type", "院线电影")
        format_standard = type_config.get("format_standard", "标准格式")
        dialogue_narration_ratio = type_config.get("dialogue_narration_ratio", "均衡")
        target_platform = type_config.get("target_platform", "院线")
        total_duration = type_config.get("total_duration", 120)
        script_mode = type_config.get("script_mode", "real")

    location = scene_outline.get("location", "未指定")
    interior_exterior = scene_outline.get("interior_exterior", scene_outline.get("int_ext", "内"))
    time_of_day = scene_outline.get("time_of_day", scene_outline.get("time", "日"))
    characters_present = scene_outline.get("characters_present", scene_outline.get("main_characters", "未指定"))
    scene_purpose = scene_outline.get("scene_purpose", scene_outline.get("core_content", "未指定"))
    duration_minutes = scene_outline.get("estimated_duration") or scene_outline.get("duration_minutes") or 3
    estimated_words = int(duration_minutes * 250)

    if script_mode == "virtual":
        prompt_template = MOVIE_SCRIPT_VIRTUAL_PROMPT
    else:
        prompt_template = MOVIE_SCRIPT_SCENE_PROMPT

    return prompt_template.format(
        outline_content=context.get("outline_content", ""),
        current_unit_outline=context.get("scene_outline", ""),
        previous_scene_ending=context.get("previous_scene_ending", ""),
        previous_scenes_summary=context.get("previous_scenes_summary", ""),
        global_summary=context.get("global_summary", ""),
        vector_context=context.get("vector_context", ""),
        scene_number=scene_number,
        scene_title=scene_title,
        location=location,
        interior_exterior=interior_exterior,
        time_of_day=time_of_day,
        characters_present=characters_present,
        scene_purpose=scene_purpose,
        duration_minutes=duration_minutes,
        estimated_words=estimated_words,
        movie_type=movie_type,
        total_duration=total_duration,
        format_standard=format_standard,
        dialogue_narration_ratio=dialogue_narration_ratio,
        target_platform=target_platform,
        character_states=context.get("character_states", ""),
        knowledge_context=context.get("knowledge_context", ""),
        dialogue_style=generation_config.get("dialogue_style", "自然对话"),
        narrative_rhythm=generation_config.get("narrative_rhythm", "紧凑")
    )
