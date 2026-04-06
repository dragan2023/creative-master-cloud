"""
GraphRAG增强的缺失单元上下文构建
在详细大纲生成时，利用知识图谱检索全局图谱，增强约束

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
from typing import Dict, Any, Optional, List


async def build_missing_unit_context_with_graphrag(
    self,
    outline: str,
    unit_number: int,
    content_type: str,
    existing_outlines: Dict[str, Any],
    project_id: Optional[int] = None,
    llm_provider=None
) -> str:
    """
    为缺失简略大纲的单元构建上下文提示（GraphRAG增强版）

    增强功能：
    1. 利用知识图谱检索全局设定（人物、世界观、核心冲突）
    2. 利用图谱关系网络确保角色一致性
    3. 利用事件时间线确保剧情连贯性

    Args:
        outline: 基础大纲内容
        unit_number: 当前单元编号
        content_type: 内容类型
        existing_outlines: 已生成的详细大纲字典
        project_id: 项目ID（用于知识图谱检索）
        llm_provider: LLM提供者

    Returns:
        增强后的推断性上下文提示
    """
    # 获取全局上下文（从大纲文本提取）
    global_context = self._extract_global_context_from_outline(
        outline, content_type)

    # 获取故事结构
    story_structure = self._extract_story_structure_from_outline(
        outline, content_type)

    # 计算置信度
    total_units = story_structure.get("total_units", unit_number)
    confidence_info = self._calculate_inference_confidence(
        existing_outlines, unit_number, total_units, outline
    )

    # 确定单元标签
    unit_label = self._get_unit_label(content_type)

    # 构建上下文提示
    context_parts = []

    # 0. 置信度提示
    confidence_level = confidence_info["level"]
    confidence_value = confidence_info["confidence"]
    if confidence_level == "high":
        confidence_hint = "（推断可信度较高，可放心参考）"
    elif confidence_level == "medium":
        confidence_hint = "（推断可信度中等，请谨慎创作）"
    else:
        confidence_hint = f"（推断可信度{confidence_level}，请务必与前文保持一致）"

    context_parts.append(
        f"**推断置信度：{confidence_level}（{confidence_value:.0%}）**{confidence_hint}"
    )

    # ========== GraphRAG增强部分 ==========
    graphrag_context = ""
    if project_id:
        try:
            from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase

            project_kb = ProjectKnowledgeBase(db=self.db)

            # 构建查询文本：基于前序章节的关键事件
            query_text = _build_graphrag_query(
                existing_outlines, unit_number, unit_label)

            # 检索全局图谱内容
            graphrag_result = await project_kb.retrieve_global_only(
                project_id=project_id,
                query_text=query_text,
                n_results=10
            )

            if graphrag_result and graphrag_result.get("combined_context"):
                graphrag_context = f"""
【知识图谱约束 - 必须遵守】
以下是从全局知识图谱中检索到的核心设定，请严格遵守：

{graphrag_result.get('combined_context', '')}

⚠️ 注意：上述内容来自已建立的知识图谱，是故事的基石设定，不得随意更改或违背。
"""
                self.logger.info(
                    f"[GraphRAG增强] 第{unit_number}{unit_label}检索到{len(graphrag_result.get('entities', []))}个实体")
        except Exception as e:
            self.logger.warning(f"[GraphRAG增强] 知识图谱检索失败: {e}")

    # 添加GraphRAG上下文
    if graphrag_context:
        context_parts.append(graphrag_context)

    # 1. 故事阶段定位
    phase_info = ""
    for phase in story_structure.get("story_phases", []):
        if phase["range"].startswith(f"第{unit_number}{unit_label}") or \
           f"第{unit_number}{unit_label}" in phase["range"]:
            phase_info = f"【故事阶段】本{unit_label}处于故事{phase['phase']}阶段（{phase['range']}），应侧重：{phase['purpose']}"
            break

    if phase_info:
        context_parts.append(phase_info)

    # 2. 人物设定参考（优先使用GraphRAG结果，否则使用文本提取）
    if not graphrag_context and global_context.get("characters"):
        context_parts.append(
            f"【人物设定参考】\n{global_context['characters'][:500]}")

    # 3. 世界观参考
    if not graphrag_context and global_context.get("world_setting"):
        context_parts.append(
            f"【世界观设定】\n{global_context['world_setting'][:300]}")

    # 4. 核心冲突参考
    if global_context.get("core_conflict"):
        context_parts.append(
            f"【核心冲突】{global_context['core_conflict'][:200]}")

    # 5. 故事主线参考
    if global_context.get("main_plot"):
        context_parts.append(
            f"【故事主线】\n{global_context['main_plot'][:300]}")

    # 6. 滑动窗口摘要
    sliding_summary = self._get_sliding_window_summary(
        existing_outlines, unit_number, content_type
    )
    if sliding_summary:
        context_parts.append(
            f"【前序{unit_label}摘要（滑动窗口）】\n{sliding_summary}")

    # 7. 前后单元衔接提示
    next_unit_info = None
    for unit in story_structure.get("existing_units", []):
        if unit["number"] == unit_number + 1:
            next_unit_info = unit
            break

    connection_hints = []
    if next_unit_info:
        connection_hints.append(
            f"后{unit_label}概要：{next_unit_info.get('title', '')}（需要为后续剧情做好铺垫）")

    if connection_hints:
        context_parts.append(
            f"【后续{unit_label}衔接】\n" + "\n".join(connection_hints))

    # 8. 最近单元的关键事件
    prev_unit = existing_outlines.get(str(unit_number - 1), {})
    if prev_unit and prev_unit.get("detailed_outline"):
        key_events = self._extract_key_events_from_outline(
            prev_unit.get("detailed_outline", ""))
        if key_events:
            context_parts.append(f"【前{unit_label}关键事件】{key_events[:200]}")

    # 组合最终提示
    chain_info = ""
    if confidence_info["chain_length"] > 0:
        chain_info = f"\n⚠️ 本{unit_label}为第{confidence_info['chain_length']+1}个连续推断单元，请特别注意与前文一致性。"

    final_prompt = f"""
**注意：基础大纲中缺少第{unit_number}{unit_label}的详细概要，请基于以下信息进行创作推断：**{chain_info}

{chr(10).join(context_parts)}

**创作要求：**
1. 确保与前文剧情逻辑连贯
2. 人物性格与设定保持一致
3. 情节发展符合故事整体走向
4. 为后续剧情预留合理的发展空间
5. 保持故事的张力和节奏感
6. 避免引入与前文矛盾的新设定
7. 【重要】严格遵守知识图谱中的核心设定，不得违背已建立的人物关系和世界观
"""
    return final_prompt


def _build_graphrag_query(
    existing_outlines: Dict[str, Any],
    unit_number: int,
    unit_label: str,
    lookback: int = 5
) -> str:
    """
    构建GraphRAG查询文本

    基于前序章节的关键事件和角色发展构建查询，
    用于检索知识图谱中相关的实体和关系

    Args:
        existing_outlines: 已生成的详细大纲字典
        unit_number: 当前单元编号
        unit_label: 单元标签
        lookback: 回看章节数

    Returns:
        查询文本
    """
    query_parts = []

    # 收集前序章节的关键事件
    for u in range(max(1, unit_number - lookback), unit_number):
        unit_data = existing_outlines.get(str(u), {})
        if unit_data:
            # 添加章节概要
            summary = (
                unit_data.get("chapter_summary", "") or
                unit_data.get("episode_summary", "") or
                unit_data.get("scene_summary", "")
            )
            if summary:
                query_parts.append(summary[:200])

            # 添加关键事件
            key_events = unit_data.get("key_events", [])
            if key_events:
                query_parts.extend(key_events[:3])

            # 添加角色发展
            character_arcs = unit_data.get("character_arcs", "")
            if character_arcs:
                query_parts.append(character_arcs[:100])

    # 如果没有前序章节，返回通用查询
    if not query_parts:
        return "人物设定 世界观 核心冲突 故事主线"

    return " ".join(query_parts[:10])  # 限制长度


# 将此方法添加到 NovelChapterGenerator 类中
# 需要修改 _build_missing_unit_context 方法调用此增强版本
