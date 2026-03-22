"""
小说/剧本正文生成与知识库集成服务
实现三层检索、GraphRAG支持、内容规则应用
"""
import json
from typing import Dict, Any, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models import NovelProject


class NovelKnowledgeIntegration:
    """小说/剧本正文生成与知识库集成"""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id
        self.logger = get_logger("novel_knowledge")

    async def retrieve_knowledge_for_chapter(
        self,
        project: NovelProject,
        chapter_info: Dict[str, Any],
        kb_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        为章节生成检索知识库

        Args:
            project: 项目对象
            chapter_info: 章节信息
            kb_config: 知识库配置

        Returns:
            {
                "theory": "通用理论知识库内容",
                "case": "垂直领域知识库内容（小说/剧本案例）",
                "user_specific": "用户专属知识库内容",
                "manual": "官方手册内容",
                "filtered": "经过LLM过滤后的内容"
            }
        """
        result = {
            "theory": "",
            "case": "",
            "user_specific": "",
            "manual": "",
            "filtered": ""
        }

        if not kb_config:
            return result

        try:
            # 1. 构建检索查询
            query_text = self._build_search_query(chapter_info)

            # 2. 调用分层检索
            from app.agents.orchestrator import AgentOrchestrator
            orchestrator = AgentOrchestrator()

            kb_contexts = await orchestrator._retrieve_classified_knowledge(
                db=self.db,
                user_id=self.user_id,
                module="novel" if project.project_type.value == "novel" else "script",
                query_text=query_text,
                kb_vertical=kb_config.get("kb_vertical_enabled", False),
                kb_user_specific=kb_config.get(
                    "kb_user_specific_enabled", False),
                kb_manual=kb_config.get("kb_manual_enabled", False),
                kb_vertical_ids=kb_config.get("kb_vertical_ids"),
                kb_user_specific_ids=kb_config.get("kb_user_specific_ids"),
                kb_manual_ids=kb_config.get("kb_manual_ids")
            )

            result["theory"] = kb_contexts.get("theory", "")
            result["case"] = kb_contexts.get("case", "")
            result["user_specific"] = kb_contexts.get("user_specific", "")
            result["manual"] = kb_contexts.get("manual", "")

            return result

        except Exception as e:
            self.logger.error(f"知识库检索失败: {str(e)}")
            return result

    def _build_search_query(self, chapter_info: Dict[str, Any]) -> str:
        """构建知识库检索查询"""
        parts = []

        # 章节主题
        if chapter_info.get("chapter_summary"):
            parts.append(chapter_info["chapter_summary"])

        # 场景元素（剧本）
        scene_metadata = chapter_info.get("scene_metadata", {})
        if scene_metadata:
            if scene_metadata.get("location"):
                parts.append(f"场景：{scene_metadata['location']}")
            if scene_metadata.get("characters_present"):
                chars = scene_metadata["characters_present"]
                if isinstance(chars, list):
                    parts.append(f"角色：{', '.join(chars)}")
                else:
                    parts.append(f"角色：{chars}")

        # 伏笔/悬念元素
        if chapter_info.get("foreshadowing"):
            parts.append(f"伏笔：{chapter_info['foreshadowing']}")

        # 章节定位
        if chapter_info.get("chapter_role"):
            parts.append(f"章节类型：{chapter_info['chapter_role']}")

        return " ".join(parts)

    def apply_content_rules(
        self,
        retrieved_contexts: Dict[str, str],
        chapter_num: int,
        novel_number: int
    ) -> str:
        """
        应用内容规则（时间距离、相似度检测）

        复用原系统的规则：
        - 近2章: [SKIP] 跳过
        - 3-5章: [MOD40%] 需修改≥40%
        - 5章以上: [OK] 可引用核心

        Args:
            retrieved_contexts: 检索到的知识库内容
            chapter_num: 被引用的章节号
            novel_number: 当前章节号

        Returns:
            处理后的知识库内容
        """
        processed = []
        time_distance = novel_number - chapter_num

        for context_type, content in retrieved_contexts.items():
            if not content or not content.strip():
                continue

            if time_distance <= 2:
                # 近章跳过规则
                processed.append(
                    f"[SKIP] 跳过近章内容({context_type}): 距离{time_distance}章")
            elif 3 <= time_distance <= 5:
                # 需修改规则
                excerpt = content[:500] if len(content) > 500 else content
                processed.append(
                    f"[MOD40%] 需修改≥40%({context_type}):\n{excerpt}")
            else:
                # 可引用规则
                processed.append(f"[OK] 可引用核心({context_type}):\n{content}")

        return "\n\n".join(processed)

    async def filter_with_llm(
        self,
        chapter_info: Dict[str, Any],
        retrieved_contexts: str,
        llm_provider
    ) -> str:
        """
        使用LLM二次过滤知识库内容

        Args:
            chapter_info: 章节信息
            retrieved_contexts: 检索到的知识库内容
            llm_provider: LLM提供者

        Returns:
            过滤后的知识库内容
        """
        from app.services.novel_writer.prompt_templates import KNOWLEDGE_FILTER_PROMPT

        try:
            prompt = KNOWLEDGE_FILTER_PROMPT.format(
                chapter_info=json.dumps(
                    chapter_info, ensure_ascii=False, indent=2),
                retrieved_contexts=retrieved_contexts
            )

            filtered_result = await llm_provider.generate(
                prompt,
                temperature=0.3,
                max_tokens=30000
            )

            # 提取响应内容（LLMResponse是Pydantic模型）
            return filtered_result.content if hasattr(filtered_result, 'content') else str(filtered_result)

        except Exception as e:
            self.logger.warning(f"LLM过滤知识库失败: {str(e)}")
            return retrieved_contexts

    def format_knowledge_for_prompt(
        self,
        kb_result: Dict[str, Any],
        max_length: int = 3000
    ) -> str:
        """
        格式化知识库内容用于提示词注入

        Args:
            kb_result: 知识库检索结果
            max_length: 最大长度限制

        Returns:
            格式化后的知识库内容
        """
        sections = []

        # 理论知识
        if kb_result.get("theory") and kb_result["theory"].strip():
            theory = self._truncate_content(kb_result["theory"], 800)
            sections.append(f"【理论知识】\n{theory}")

        # 案例参考
        if kb_result.get("case") and kb_result["case"].strip():
            case = self._truncate_content(kb_result["case"], 800)
            sections.append(f"【案例参考】\n{case}")

        # 用户专属知识
        if kb_result.get("user_specific") and kb_result["user_specific"].strip():
            user_kb = self._truncate_content(kb_result["user_specific"], 600)
            sections.append(f"【用户知识】\n{user_kb}")

        # 官方手册
        if kb_result.get("manual") and kb_result["manual"].strip():
            manual = self._truncate_content(kb_result["manual"], 400)
            sections.append(f"【官方手册】\n{manual}")

        result = "\n\n".join(sections)

        # 限制总长度
        if len(result) > max_length:
            result = result[:max_length] + "\n...[内容已截断]"

        return result

    def _truncate_content(self, content: str, max_len: int) -> str:
        """截断内容"""
        if len(content) <= max_len:
            return content
        return content[:max_len] + "..."

    def get_default_kb_config(self) -> Dict[str, Any]:
        """获取默认知识库配置"""
        return {
            "kb_vertical_enabled": False,
            "kb_vertical_ids": [],
            "kb_user_specific_enabled": False,
            "kb_user_specific_ids": [],
            "kb_manual_enabled": False,
            "kb_manual_ids": [],
            "graphrag_enabled": True
        }

    def validate_kb_config(self, kb_config: Dict[str, Any]) -> Dict[str, Any]:
        """验证并规范化知识库配置"""
        default = self.get_default_kb_config()

        if not kb_config:
            return default

        # 确保所有字段存在
        for key in default:
            if key not in kb_config:
                kb_config[key] = default[key]

        # 验证ID列表
        for key in ["kb_vertical_ids", "kb_user_specific_ids", "kb_manual_ids"]:
            if not isinstance(kb_config.get(key), list):
                kb_config[key] = []

        return kb_config
