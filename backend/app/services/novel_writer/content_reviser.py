"""
内容修正服务
基于项目知识库对正文初稿进行智能修正
支持修正历史记录和版本管理
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.novel_project import NovelProject
from app.services.novel_writer.project_knowledge_base import ProjectKnowledgeBase


# 修正历史版本上限
MAX_REVISION_HISTORY = 10


# 正文修正提示词模板
CONTENT_REVISION_PROMPT = """【任务说明】
你是一位专业的小说/剧本编辑，负责对正文初稿进行智能修正。你需要基于知识库中的设定信息，检查并修正正文中的不一致之处。

【知识库参考信息】
{knowledge_context}

【待修正正文】
第{unit_number}单元 正文初稿：
{draft_content}

【修正规则】
1. **一致性检查**：
   - 人物设定是否与知识库中的描述一致（性格、外貌、能力等）
   - 人物关系是否与知识库中的关系网络一致
   - 世界观设定是否与全局设定一致

2. **设定冲突修正**：
   - 如果发现人物行为与其设定矛盾，调整行为描述或添加合理解释
   - 如果发现关系描述与设定不符，修正关系描述
   - 如果发现世界观元素冲突，按全局设定修正

3. **内容优化**：
   - 修正明显的逻辑漏洞
   - 补充缺失的关键细节
   - 优化叙事连贯性

4. **修正原则**：
   - 仅修正确实存在冲突的内容，不要过度修改
   - 保持原文的叙事风格和节奏
   - 修正后的内容要自然流畅，不露痕迹
   - 不要改变核心剧情走向

【输出要求】
请直接输出修正后的完整正文内容，不要输出任何修正说明或解释。
如果正文无需修正，直接输出原文即可。
"""


# 章节大纲逻辑修正提示词模板
OUTLINE_LOGIC_REVISION_PROMPT = """【任务说明】
你是一位专业的小说/剧本编辑，负责对章节大纲进行逻辑一致性检查和修正。你需要基于全局大纲设定和前序章节内容，检查并修正当前章节大纲中的逻辑问题。

【全局大纲设定】
{global_context}

【前序章节摘要】
{previous_context}

【当前章节大纲】
第{unit_number}章大纲：
{outline_content}

【检查与修正规则】
1. **设定冲突检查**：
   - 人物设定是否与全局大纲一致（性格、外貌、能力、身份等）
   - 世界观设定是否与全局设定矛盾
   - 时间线是否与前序章节连贯

2. **剧情衔接检查**：
   - 与前序章节的情节是否自然衔接
   - 是否存在突兀的剧情跳跃
   - 伏笔和悬念是否合理延续

3. **人物成长检查**：
   - 人物能力提升是否合理（避免过快成长）
   - 人物关系发展是否自然
   - 人物行为是否符合已建立的性格设定

4. **修正原则**：
   - 仅修正确实存在逻辑问题的内容
   - 保持原文的整体结构和核心剧情
   - 修正后的内容要自然流畅
   - 不要大幅改变章节的剧情走向

【输出要求】
请直接输出修正后的完整章节大纲内容（保持原有的格式和结构），不要输出任何修正说明或解释。
如果大纲无需修正，直接输出原文即可。
"""


class ContentReviser:
    """内容修正服务

    基于项目知识库对正文初稿进行智能修正：
    1. 从知识库检索全局图谱+当前单元图谱
    2. 构建修正提示词
    3. 调用LLM进行修正
    4. 返回修正后的内容
    """

    def __init__(self, db: AsyncSession = None):
        """
        初始化内容修正服务

        Args:
            db: 数据库会话
        """
        self.db = db
        self.logger = get_logger("content_reviser")
        self.knowledge_base = ProjectKnowledgeBase(db=db)
        # 内存中的修正历史缓存（用于快速访问）
        self._revision_history_cache: Dict[int, List[Dict[str, Any]]] = {}

    def _build_revision_record(
        self,
        project_id: int,
        unit_number: int,
        original_content: str,
        revised_content: str,
        knowledge_used: Dict[str, Any],
        success: bool = True,
        error: str = None
    ) -> Dict[str, Any]:
        """
        构建修正历史记录

        Args:
            project_id: 项目ID
            unit_number: 单元号
            original_content: 原始内容
            revised_content: 修正后内容
            knowledge_used: 使用的知识库信息
            success: 是否成功
            error: 错误信息

        Returns:
            修正历史记录字典
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "project_id": project_id,
            "unit_number": unit_number,
            "original_length": len(original_content),
            "revised_length": len(revised_content),
            "change_ratio": abs(len(original_content) - len(revised_content)) / len(original_content) if original_content else 0,
            "knowledge_used": knowledge_used,
            "success": success,
            "error": error,
            # 保存内容摘要（不保存完整内容以节省空间）
            "original_preview": original_content[:500] + "..." if len(original_content) > 500 else original_content,
            "revised_preview": revised_content[:500] + "..." if len(revised_content) > 500 else revised_content,
        }

    def _save_revision_to_cache(
        self,
        project_id: int,
        unit_number: int,
        record: Dict[str, Any]
    ):
        """
        保存修正历史到内存缓存

        Args:
            project_id: 项目ID
            unit_number: 单元号
            record: 修正历史记录
        """
        cache_key = f"{project_id}_{unit_number}"
        if cache_key not in self._revision_history_cache:
            self._revision_history_cache[cache_key] = []

        self._revision_history_cache[cache_key].append(record)

        # 限制历史记录数量
        if len(self._revision_history_cache[cache_key]) > MAX_REVISION_HISTORY:
            self._revision_history_cache[cache_key] = \
                self._revision_history_cache[cache_key][-MAX_REVISION_HISTORY:]

    def get_revision_history(
        self,
        project_id: int,
        unit_number: int
    ) -> List[Dict[str, Any]]:
        """
        获取指定单元的修正历史

        Args:
            project_id: 项目ID
            unit_number: 单元号

        Returns:
            修正历史记录列表（按时间倒序）
        """
        cache_key = f"{project_id}_{unit_number}"
        history = self._revision_history_cache.get(cache_key, [])
        return list(reversed(history))  # 最新的在前

    async def revise_content(
        self,
        project: NovelProject,
        unit_number: int,
        draft_content: str,
        llm_provider=None,
        content_type: str = "novel"
    ) -> Dict[str, Any]:
        """
        对正文初稿进行智能修正

        Args:
            project: 项目对象
            unit_number: 当前单元号（章节号/集数/场景号）
            draft_content: 正文初稿内容
            llm_provider: LLM提供者
            content_type: 内容类型 (novel/series_script/movie_script)

        Returns:
            {
                "success": bool,
                "revised_content": str,  # 修正后的内容
                "original_content": str,  # 原始内容
                "knowledge_used": dict,   # 使用的知识库信息
                "error": str | None
            }
        """
        result = {
            "success": False,
            "revised_content": draft_content,  # 默认返回原文
            "original_content": draft_content,
            "knowledge_used": {},
            "error": None
        }

        try:
            # 1. 检查知识库是否可用
            if not project.kb_graphrag_enabled:
                self.logger.info(
                    f"项目未启用GraphRAG，跳过修正: project_id={project.id}")
                result["success"] = True
                result["error"] = "GraphRAG未启用"
                return result

            if project.kb_status != "ready":
                self.logger.info(
                    f"知识库未就绪，跳过修正: project_id={project.id}, status={project.kb_status}")
                result["success"] = True
                result["error"] = "知识库未就绪"
                return result

            # 2. 从知识库检索相关内容
            # 构建查询文本（使用正文初稿的前1000字作为查询）
            query_text = draft_content[:1000] if len(
                draft_content) > 1000 else draft_content

            retrieval_result = await self.knowledge_base.retrieve_for_revision(
                project_id=project.id,
                current_unit=unit_number,
                query_text=query_text,
                n_results=10
            )

            knowledge_context = retrieval_result.get("combined_context", "")

            if not knowledge_context:
                self.logger.info(f"知识库检索结果为空，跳过修正: project_id={project.id}")
                result["success"] = True
                result["error"] = "知识库检索结果为空"
                return result

            # 记录使用的知识库信息
            result["knowledge_used"] = {
                "global_entities": len(retrieval_result.get("global_entities", [])),
                "global_relations": len(retrieval_result.get("global_relations", [])),
                "unit_entities": len(retrieval_result.get("unit_entities", [])),
                "unit_relations": len(retrieval_result.get("unit_relations", []))
            }

            # 3. 构建修正提示词
            revision_prompt = CONTENT_REVISION_PROMPT.format(
                knowledge_context=knowledge_context,
                unit_number=unit_number,
                draft_content=draft_content
            )

            # 4. 调用LLM进行修正
            if llm_provider is None:
                self.logger.warning(f"未提供LLM提供者，跳过修正: project_id={project.id}")
                result["success"] = True
                result["error"] = "未提供LLM提供者"
                return result

            self.logger.info(
                f"开始内容修正: project_id={project.id}, unit={unit_number}, "
                f"knowledge_entities={result['knowledge_used']}"
            )

            # 调用LLM
            revised_content = await self._call_llm_for_revision(
                llm_provider=llm_provider,
                prompt=revision_prompt,
                content_type=content_type
            )

            if revised_content:
                result["success"] = True
                result["revised_content"] = revised_content

                # 计算修正统计
                original_len = len(draft_content)
                revised_len = len(revised_content)
                change_ratio = abs(original_len - revised_len) / \
                    original_len if original_len > 0 else 0

                # 保存修正历史记录
                revision_record = self._build_revision_record(
                    project_id=project.id,
                    unit_number=unit_number,
                    original_content=draft_content,
                    revised_content=revised_content,
                    knowledge_used=result["knowledge_used"],
                    success=True
                )
                self._save_revision_to_cache(
                    project.id, unit_number, revision_record)
                result["revision_record"] = revision_record

                self.logger.info(
                    f"内容修正完成: project_id={project.id}, unit={unit_number}, "
                    f"original_len={original_len}, revised_len={revised_len}, "
                    f"change_ratio={change_ratio:.2%}"
                )
            else:
                result["success"] = True
                result["error"] = "LLM返回空内容"

                # 记录失败历史
                revision_record = self._build_revision_record(
                    project_id=project.id,
                    unit_number=unit_number,
                    original_content=draft_content,
                    revised_content=draft_content,
                    knowledge_used=result["knowledge_used"],
                    success=False,
                    error="LLM返回空内容"
                )
                self._save_revision_to_cache(
                    project.id, unit_number, revision_record)

            return result

        except Exception as e:
            self.logger.error(
                f"内容修正失败: project_id={project.id}, unit={unit_number}, error={str(e)}")
            result["error"] = str(e)
            return result

    async def _call_llm_for_revision(
        self,
        llm_provider,
        prompt: str,
        content_type: str = "novel"
    ) -> Optional[str]:
        """
        调用LLM进行内容修正

        Args:
            llm_provider: LLM提供者
            prompt: 修正提示词
            content_type: 内容类型

        Returns:
            修正后的内容，失败返回None
        """
        import inspect

        try:
            # 根据LLM提供者类型调用不同的接口
            if hasattr(llm_provider, 'agenerate'):
                # LangChain风格的接口
                response = await llm_provider.agenerate([prompt])
                return response.generations[0][0].text

            elif hasattr(llm_provider, 'generate'):
                # 检查是否是异步方法（关键修复！）
                if inspect.iscoroutinefunction(llm_provider.generate):
                    # 异步方法 - 正确使用 await
                    response = await llm_provider.generate(
                        prompt,
                        temperature=0.3,  # 低温度保持稳定性
                        max_tokens=32000  # 模型最大支持32768，留余量
                    )
                else:
                    # 同步方法
                    response = llm_provider.generate(prompt)

                # 处理响应对象（支持多种返回类型）
                if hasattr(response, 'content'):
                    # LLMResponse 对象
                    return response.content
                elif isinstance(response, str):
                    return response
                elif isinstance(response, dict):
                    return response.get("text", response.get("content", ""))

            elif hasattr(llm_provider, 'chat'):
                # Chat风格接口
                messages = [{"role": "user", "content": prompt}]
                if inspect.iscoroutinefunction(llm_provider.chat):
                    response = await llm_provider.chat(messages)
                else:
                    response = llm_provider.chat(messages)

                if isinstance(response, str):
                    return response
                elif isinstance(response, dict):
                    return response.get("content", response.get("text", ""))

            elif hasattr(llm_provider, 'ainvoke'):
                # LangChain Runnable接口（异步）
                from langchain_core.messages import HumanMessage
                response = await llm_provider.ainvoke([HumanMessage(content=prompt)])
                return response.content

            elif hasattr(llm_provider, 'invoke'):
                # 同步Runnable接口
                from langchain_core.messages import HumanMessage
                response = llm_provider.invoke([HumanMessage(content=prompt)])
                return response.content

            else:
                self.logger.error(f"不支持的LLM提供者类型: {type(llm_provider)}")
                return None

        except Exception as e:
            self.logger.error(f"调用LLM失败: {str(e)}")
            return None

    async def quick_consistency_check(
        self,
        project: NovelProject,
        unit_number: int,
        content: str,
        llm_provider=None
    ) -> Dict[str, Any]:
        """
        快速一致性检查（轻量级，不进行完整修正）

        仅检查是否存在明显冲突，返回冲突列表

        Args:
            project: 项目对象
            unit_number: 单元号
            content: 待检查内容
            llm_provider: LLM提供者

        Returns:
            {
                "has_conflicts": bool,
                "conflicts": List[dict],
                "suggestions": List[str]
            }
        """
        result = {
            "has_conflicts": False,
            "conflicts": [],
            "suggestions": []
        }

        try:
            # 检索知识库
            query_text = content[:500] if len(content) > 500 else content
            retrieval_result = await self.knowledge_base.retrieve_for_revision(
                project_id=project.id,
                current_unit=unit_number,
                query_text=query_text,
                n_results=5
            )

            knowledge_context = retrieval_result.get("combined_context", "")

            if not knowledge_context:
                return result

            # 构建检查提示词
            check_prompt = f"""【快速一致性检查】

【知识库设定】
{knowledge_context}

【待检查内容】
{content}

【检查任务】
仅检查是否存在以下明显冲突：
1. 人物设定冲突（性格、外貌、能力等严重不符）
2. 关系设定冲突（人物关系与设定矛盾）
3. 世界观冲突（设定元素与全局设定矛盾）

【输出格式】
如果没有明显冲突，输出：无冲突
如果有冲突，按以下格式输出：
冲突类型: [类型]
冲突描述: [简短描述]
建议修改: [修改建议]
"""

            if llm_provider:
                response = await self._call_llm_for_revision(
                    llm_provider=llm_provider,
                    prompt=check_prompt,
                    content_type="check"
                )

                if response and "无冲突" not in response:
                    result["has_conflicts"] = True
                    # 简单解析冲突信息
                    result["conflicts"].append({
                        "raw_response": response
                    })

            return result

        except Exception as e:
            self.logger.error(f"快速一致性检查失败: {str(e)}")
            return result

    async def revise_outline_content(
        self,
        project: NovelProject,
        unit_number: int,
        outline_content: str,
        global_context: str = "",
        previous_context: str = "",
        llm_provider=None,
        content_type: str = "novel"
    ) -> Dict[str, Any]:
        """
        对章节大纲进行逻辑一致性修正

        Args:
            project: 项目对象
            unit_number: 当前单元号（章节号）
            outline_content: 章节大纲内容
            global_context: 全局大纲设定
            previous_context: 前序章节摘要
            llm_provider: LLM提供者
            content_type: 内容类型 (novel/series_script/movie_script)

        Returns:
            {
                "success": bool,
                "revised_content": str,  # 修正后的内容
                "original_content": str,  # 原始内容
                "has_changes": bool,      # 是否有实际修改
                "error": str | None
            }
        """
        result = {
            "success": False,
            "revised_content": outline_content,
            "original_content": outline_content,
            "has_changes": False,
            "error": None
        }

        try:
            # 1. 检查是否有足够的上下文信息
            if not global_context and not previous_context:
                self.logger.info(
                    f"缺少全局和前序上下文，跳过大纲修正: project_id={project.id}, unit={unit_number}")
                result["success"] = True
                result["error"] = "缺少上下文信息"
                return result

            # 2. 构建修正提示词
            revision_prompt = OUTLINE_LOGIC_REVISION_PROMPT.format(
                global_context=global_context or "（未提供全局大纲设定）",
                previous_context=previous_context or "（这是第一章，无前序章节）",
                unit_number=unit_number,
                outline_content=outline_content
            )

            # 3. 调用LLM进行修正
            if llm_provider is None:
                self.logger.warning(
                    f"未提供LLM提供者，跳过大纲修正: project_id={project.id}")
                result["success"] = True
                result["error"] = "未提供LLM提供者"
                return result

            self.logger.info(
                f"开始大纲逻辑修正: project_id={project.id}, unit={unit_number}"
            )

            # 调用LLM
            revised_content = await self._call_llm_for_revision(
                llm_provider=llm_provider,
                prompt=revision_prompt,
                content_type=content_type
            )

            if revised_content:
                # 检查是否有实际修改
                has_changes = revised_content.strip() != outline_content.strip()

                result["success"] = True
                result["revised_content"] = revised_content
                result["has_changes"] = has_changes

                # 计算修正统计
                original_len = len(outline_content)
                revised_len = len(revised_content)

                self.logger.info(
                    f"大纲逻辑修正完成: project_id={project.id}, unit={unit_number}, "
                    f"original_len={original_len}, revised_len={revised_len}, "
                    f"has_changes={has_changes}"
                )
            else:
                result["success"] = True
                result["error"] = "LLM返回空内容"

            return result

        except Exception as e:
            self.logger.error(
                f"大纲逻辑修正失败: project_id={project.id}, unit={unit_number}, error={str(e)}")
            result["error"] = str(e)
            return result


# 便捷函数
async def revise_content_with_knowledge_base(
    project: NovelProject,
    unit_number: int,
    draft_content: str,
    llm_provider=None,
    db: AsyncSession = None,
    content_type: str = "novel"
) -> Dict[str, Any]:
    """
    使用知识库修正正文内容的便捷函数

    Args:
        project: 项目对象
        unit_number: 单元号
        draft_content: 正文初稿
        llm_provider: LLM提供者
        db: 数据库会话
        content_type: 内容类型

    Returns:
        修正结果
    """
    reviser = ContentReviser(db=db)
    return await reviser.revise_content(
        project=project,
        unit_number=unit_number,
        draft_content=draft_content,
        llm_provider=llm_provider,
        content_type=content_type
    )
