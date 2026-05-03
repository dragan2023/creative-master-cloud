"""Agent编排器 - 输入参数处理与上下文构建Mixin"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import AsyncGenerator
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
from datetime import datetime
import json
import re
import time
import random
from app.tools.creative_search import get_creative_search, OptimizedCreativeSearch
from app.agents.orchestrator.api import extract_input_params_files, GenerateStreamContext
from app.core.config import get_settings


class ContextUtilsMixin:
    """输入参数处理与上下文构建"""

    async def _prepare_input_params(
        self,
        db: AsyncSession,
        module: str,
        input_params: Dict[str, Any],
        logger
    ) -> tuple:
        """
        准备输入参数和系统提示词

        Args:
            db: 数据库会话
            module: 模块名称
            input_params: 输入参数
            logger: 日志记录器

        Returns:
            (processed_input_params, system_prompt) 元组
        """
        # 处理输入参数中的文件URL
        processed_params = await extract_input_params_files(input_params, logger)

        # 获取提示词模板
        prompt_template = await self.prompt_manager.get_prompt(db, module)

        # 渲染提示词
        system_prompt = self.prompt_manager.render_prompt(
            prompt_template, processed_params, module=module
        )

        # 添加创意变化引导
        creative_angles = [
            "请从一个独特的角度来诠释这个创意，避免常规套路",
            "请在创作中融入一些出人意料的元素，让人眼前一亮",
            "请尝试用新鲜的叙事方式来呈现，打破传统模式",
            "请在细节处理上有一些独到的巧思，增加记忆点",
            "请赋予作品一些独特的情感色彩，形成差异化风格",
            "请从逆向思维出发，挑战常规认知，带来新颖的视角",
            "请在结构上有一些创新设计，让整体更有层次感",
            "请在开篇设计一个吸引人的钩子，迅速抓住读者注意力",
            "请在结尾留下深刻印象，形成强烈的情感共鸣或思考",
            "请在中间段落设置一些反转或惊喜，增加戏剧张力"
        ]
        creative_styles = [
            "幽默风趣", "温馨感人", "悬疑紧张", "清新文艺",
            "热血励志", "轻松治愈", "反差萌", "情感共鸣"
        ]
        creative_seed = random.choice(creative_angles)
        creative_style_hint = random.choice(creative_styles)
        creative_id = random.randint(
            get_settings().CREATIVE_ID_MIN, get_settings().CREATIVE_ID_MAX)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        system_prompt += f"""

## 创意差异化指引
**本次创意编号**: #{creative_id}
**生成时间**: {current_time}
**风格倾向**: {creative_style_hint}

{creative_seed}

⚠️ 重要提示：本次创作必须与之前的创作有明显区别。请充分发挥创意，在保持主题一致的前提下，展现全新的创意思路和表达方式。避免重复使用相似的框架、句式和表达。"""

        return processed_params, system_prompt


    async def _gather_context(
        self,
        ctx: GenerateStreamContext,
        db: AsyncSession,
        user_id: int,
        module: str,
        enable_knowledge: bool,
        kb_vertical: bool,
        kb_user_specific: bool,
        kb_manual: bool,
        kb_vertical_ids: Optional[List[int]],
        kb_user_specific_ids: Optional[List[int]],
        kb_manual_ids: Optional[List[int]],
        actual_enable_creative_search: bool,
        search_keywords: Optional[List[str]],
        search_depth: str,
        actual_enable_trending: bool,
        reference_urls: Optional[List[str]],
        logger
    ) -> AsyncGenerator[str, None]:
        """
        收集上下文信息（搜索+知识库+热点）

        Yields:
            SSE 格式的事件字符串
        """
        full_prompt = ""

        # 1. 创作辅助搜索
        if actual_enable_creative_search:
            is_user_initiated_search = bool(search_keywords)

            if is_user_initiated_search:
                yield self._format_sse("workflow", {"type": "step", "step": "creative_search", "status": "running", "message": f"正在搜索创作素材，关键词：{', '.join(search_keywords)}...", "icon": "Search"})
            else:
                yield self._format_sse("workflow", {"type": "step", "step": "creative_search", "status": "running", "message": "正在智能分析是否需要搜索创作素材...", "icon": "Search"})

            try:
                creative_search = get_creative_search()
                search_result = await creative_search.search(
                    input_params=ctx.input_params,
                    module=module,
                    user_keywords=search_keywords,
                    force_search=is_user_initiated_search,
                    search_depth=search_depth,
                    user_id=user_id,
                    db=db
                )

                if search_result["searched"] and search_result["results"]:
                    full_prompt += f"\n\n{search_result['formatted_context']}\n"
                    cache_status = "（来自缓存）" if search_result["cached"] else ""
                    search_type = "用户指定" if is_user_initiated_search else "智能"
                    yield self._format_sse("workflow", {
                        "type": "step",
                        "step": "creative_search",
                        "status": "done",
                        "message": f"{search_type}搜索完成，找到 {len(search_result['results'])} 条参考资料{cache_status}，关键词：{', '.join(search_result['keywords'])}"
                    })
                    logger.info(
                        f"创作辅助搜索完成: keywords={search_result['keywords']}, results={len(search_result['results'])}, reason={search_result['reason']}")
                elif search_result["searched"] and not search_result["results"]:
                    search_type = "用户指定" if is_user_initiated_search else "智能"
                    keywords_info = f"，关键词：{', '.join(search_result['keywords'])}" if search_result.get(
                        'keywords') else ""
                    yield self._format_sse("workflow", {"type": "step", "step": "creative_search", "status": "done", "message": f"{search_type}搜索未返回结果{keywords_info}"})
                else:
                    yield self._format_sse("workflow", {"type": "step", "step": "creative_search", "status": "done", "message": f"跳过搜索：{search_result['reason']}"})

            except Exception as e:
                self.logger.exception("创作辅助搜索失败")
                logger.exception(f"创作辅助搜索异常: {str(e)}")
                yield self._format_sse("workflow", {"type": "step", "step": "creative_search", "status": "done", "message": "搜索服务暂时不可用，跳过"})

        # 2. 知识库检索
        kb_contexts = {"theory": "", "case": "",
                       "user_specific": "", "manual": ""}
        query_text = ctx.input_params.get(
            "topic", "") or json.dumps(ctx.input_params)

        logger.info(
            f"知识库增强状态: enable_knowledge={enable_knowledge}, kb_vertical={kb_vertical}, kb_user_specific={kb_user_specific}, kb_manual={kb_manual}")

        if enable_knowledge:
            kb_types = ["通用"]
            if kb_vertical:
                kb_types.append("垂直领域")
            if kb_user_specific:
                kb_types.append("用户专属")
            if kb_manual:
                kb_types.append("官方手册")
            yield self._format_sse("workflow", {"type": "step", "step": "kb_retrieve", "status": "running", "message": f"正在检索知识库（{' → '.join(kb_types)})...", "icon": "Collection"})

            kb_contexts = await self._retrieve_classified_knowledge(
                db=db,
                user_id=user_id,
                module=module,
                query_text=query_text,
                kb_vertical=kb_vertical,
                kb_user_specific=kb_user_specific,
                kb_manual=kb_manual,
                kb_vertical_ids=kb_vertical_ids,
                kb_user_specific_ids=kb_user_specific_ids,
                kb_manual_ids=kb_manual_ids
            )

            # 统计检索结果
            theory_count = len(
                [1 for line in kb_contexts["theory"].split("\n") if line.startswith("###")])
            case_count = len(
                [1 for line in kb_contexts["case"].split("\n") if line.startswith("###")])
            user_specific_count = len(
                [1 for line in kb_contexts["user_specific"].split("\n") if line.startswith("###")])
            manual_count = len(
                [1 for line in kb_contexts["manual"].split("\n") if line.startswith("###")])

            result_parts = [f"通用:{theory_count}个"]
            if kb_vertical:
                result_parts.append(f"垂直领域:{case_count}个")
            if kb_user_specific:
                result_parts.append(f"用户专属:{user_specific_count}个")
            if kb_manual:
                result_parts.append(f"官方手册:{manual_count}个")
            yield self._format_sse("workflow", {"type": "step", "step": "kb_retrieve", "status": "done", "message": f"已检索知识库（{', '.join(result_parts)}）"})

            # 将知识库内容添加到 prompt
            if kb_contexts["theory"].strip():
                full_prompt += f"\n\n## 通用创意理论知识库\n{kb_contexts['theory']}\n"
            if kb_contexts["case"].strip():
                full_prompt += f"\n\n## 垂直领域案例知识库\n{kb_contexts['case']}\n"
            if kb_contexts["user_specific"].strip():
                full_prompt += f"\n\n## 用户专属知识库\n{kb_contexts['user_specific']}\n"
            if kb_contexts["manual"].strip():
                full_prompt += f"\n\n## 官方规范手册\n{kb_contexts['manual']}\n"

        # 更新上下文中的知识库内容
        ctx.kb_contexts = kb_contexts

        # 3. 添加参考网页内容
        if reference_urls:
            yield self._format_sse("workflow", {"type": "step", "step": "webpage", "status": "running", "message": "智能体正在访问参考链接...", "icon": "Link"})
            webpage_contents = await self.webpage_reader.read_urls(reference_urls)
            if webpage_contents:
                webpage_context = self.webpage_reader.format_for_context(
                    webpage_contents)
                full_prompt += f"\n\n## 参考资料（网页链接）\n{webpage_context}\n"
            yield self._format_sse("workflow", {"type": "step", "step": "webpage", "status": "done", "message": f"已读取 {len(reference_urls)} 个链接"})

        # 4. 添加实时热点数据
        if actual_enable_trending:
            yield self._format_sse("workflow", {"type": "step", "step": "trending", "status": "running", "message": "正在聚合实时热点（通过搜索引擎获取）...", "icon": "TrendCharts"})
            try:
                logger.info(f"热点聚合开始: user_id={user_id}")
                trending_result = await self.mcp_client.get_trending_topics(
                    platforms=None,
                    provider="search_hotnews",
                    limit=15,
                    use_cache=True,
                    db_session=db,
                    user_id=user_id
                )
                logger.info(
                    f"热点聚合结果: success={trending_result.success}, total_items={trending_result.total_items}, platforms={trending_result.platforms_count}")

                if trending_result.success and trending_result.data:
                    trending_context = self.mcp_client.format_for_context(
                        trending_result, max_items=15)
                    hot_items_count = sum(len(p.items)
                                          for p in trending_result.data if p.items)
                    full_prompt += f"\n\n{trending_context}"
                    full_prompt += f"\n\n**🔥 热点融合创作指令**："
                    full_prompt += f"\n当前已获取 {hot_items_count} 条实时热点。你必须："
                    full_prompt += f"\n1. 从热点列表中选择1-3个与创作主题最相关的话题"
                    full_prompt += f"\n2. 将热点元素自然融入你的创作内容（可以是话题、事件、人物等）"
                    full_prompt += f"\n3. 在内容末尾添加\"📌 参考热点：[具体热点名称]\"标注"
                    full_prompt += f"\n4. 如果没有任何热点与主题相关，请说明原因并在内容中体现时效性"

                    total_items = sum(len(p.items)
                                      for p in trending_result.data if p.items)
                    platform_count = len(
                        [p for p in trending_result.data if p.items])
                    yield self._format_sse("workflow", {"type": "step", "step": "trending", "status": "done", "message": f"已获取 {total_items} 条热点（来自{platform_count}个平台）"})
                else:
                    error_msg = trending_result.error.message if trending_result.error else "未知错误"
                    logger.warning(f"热点聚合失败或无数据: {error_msg}")
                    yield self._format_sse("workflow", {"type": "step", "step": "trending", "status": "done", "message": "暂无热点数据"})

            except Exception as e:
                self.logger.exception("获取热点数据失败")
                logger.exception("热点聚合异常")
                yield self._format_sse("workflow", {"type": "step", "step": "trending", "status": "done", "message": "热点数据获取失败，跳过"})

        # 5. 添加用户消息
        full_prompt += "\n\n请根据以上信息，按照要求的格式生成内容。"

        # 更新上下文
        ctx.full_prompt = full_prompt


    async def _get_user_graphrag_config(
        self,
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """
        获取用户的 GraphRAG 配置

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            是否启用 GraphRAG，默认为 True
        """
        try:
            from app.models import SystemConfig
            import json

            config_key = f"user_preprocessor_config_{user_id}"
            result = await db.execute(
                select(SystemConfig).where(SystemConfig.id == config_key)
            )
            config_record = result.scalar_one_or_none()

            if config_record and config_record.config_value:
                config_data = json.loads(config_record.config_value)
                return config_data.get("graphrag_enabled", True)

            return True  # 默认启用
        except Exception as e:
            self.logger.exception("获取 GraphRAG 配置失败")
            return True  # 出错时默认启用


