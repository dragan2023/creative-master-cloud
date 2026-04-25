"""Agent编排器 - 同步生成入口Mixin"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict
from typing import List
from typing import Optional
from typing import Any
from datetime import datetime
import json
import re
import os
import time
import random
import base64
from app.core.logger import get_logger, LoggerAdapter


class GenerateSyncMixin:
    """同步生成入口"""

    async def generate(
        self,
        db: AsyncSession,
        module: str,
        user_id: int,
        input_params: Dict[str, Any],
        session_id: Optional[str] = None,
        enable_search: bool = False,
        enable_knowledge: bool = False,
        reference_urls: Optional[List[str]] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        执行创意生成（非流式）

        Args:
            db: 数据库会话
            module: 模块名称
            user_id: 用户ID
            input_params: 输入参数
            session_id: 会话ID
            enable_search: 是否启用联网搜索
            enable_knowledge: 是否启用知识库增强（三层检索：通用→垂直领域→官方手册）
            reference_urls: 参考网页URL列表
            provider: 指定LLM提供者
            temperature: 温度参数
            images: 图片URL列表（多模态支持）
            videos: 视频URL列表（多模态支持，仅部分模型支持）

        Returns:
            生成结果
        """
        logger = get_logger(str(user_id))
        start_time = time.time()

        try:
            # 1. 获取 LLM 提供者
            llm_provider = await self.llm_manager.get_provider_from_db(
                db=db,
                user_id=user_id,
                provider_name=provider
            )

            # 2. 处理输入参数中的文件URL（将文件内容提取出来）
            input_params = await extract_input_params_files(input_params, logger)

            # 3. 获取提示词模板
            prompt_template = await self.prompt_manager.get_prompt(db, module)

            # 4. 渲染提示词
            system_prompt = self.prompt_manager.render_prompt(
                prompt_template, input_params, module=module)

            # 3.1 添加创意变化引导（确保每次生成不同）
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
                settings.CREATIVE_ID_MIN, settings.CREATIVE_ID_MAX)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            system_prompt += f"""\n\n## 创意差异化指引
**本次创意编号**: #{creative_id}
**生成时间**: {current_time}
**风格倾向**: {creative_style_hint}

{creative_seed}

⚠️ 重要提示：本次创作必须与之前的创作有明显区别。请充分发挥创意，在保持主题一致的前提下，展现全新的创意思路和表达方式。避免重复使用相似的框架、句式和表达。"""

            # 4. 构建完整提示
            full_prompt = ""

            # 4.1 添加联网搜索结果
            if enable_search and input_params.get("topic"):
                # 使用降级策略搜索（免费优先）
                from app.tools.web_search import search_with_fallback

                async def get_user_search_key(provider: str):
                    """获取用户搜索API Key"""
                    try:
                        from app.models.user import UserAPIKey
                        result = await db.execute(
                            select(UserAPIKey).where(
                                UserAPIKey.user_id == user_id,
                                UserAPIKey.provider == provider,
                                UserAPIKey.is_valid == True
                            ).order_by(UserAPIKey.is_default.desc()).limit(1)
                        )
                        api_key_record = result.scalar_one_or_none()
                        if api_key_record:
                            from app.core.security import api_key_encryption
                            return api_key_encryption.decrypt(api_key_record.encrypted_key)
                    except Exception as e:
                        self.logger.warning(
                            f"获取用户{provider} API Key失败: {str(e)}")
                    return None

                search_results, engine_used = await search_with_fallback(
                    query=input_params["topic"],
                    num_results=3,
                    get_user_api_key=get_user_search_key
                )

                if search_results:
                    search_context = self.web_search.format_results(
                        search_results)
                    full_prompt += f"\n\n## 参考资料（联网搜索）\n{search_context}\n"
                    logger.info(
                        f"搜索完成，使用引擎: {engine_used}, 结果数: {len(search_results)}")

            # 4.2 三层检索知识库（通用→垂直领域→官方手册）
            if enable_knowledge:
                query_text = input_params.get(
                    "topic", "") or json.dumps(input_params)
                kb_contexts = await self._retrieve_classified_knowledge(
                    db=db,
                    user_id=user_id,
                    module=module,
                    query_text=query_text
                )

                # 将知识库内容添加到 prompt
                if kb_contexts["theory"].strip():
                    full_prompt += f"\n\n## 通用创意理论知识库\n{kb_contexts['theory']}\n"
                if kb_contexts["case"].strip():
                    full_prompt += f"\n\n## 垂直领域案例知识库\n{kb_contexts['case']}\n"
                if kb_contexts["manual"].strip():
                    full_prompt += f"\n\n## 官方规范手册\n{kb_contexts['manual']}\n"

            # 4.3 添加参考网页内容
            if reference_urls:
                webpage_contents = await self.webpage_reader.read_urls(reference_urls)
                if webpage_contents:
                    webpage_context = self.webpage_reader.format_for_context(
                        webpage_contents)
                    full_prompt += f"\n\n## 参考资料（网页链接）\n{webpage_context}\n"

            # 4.4 添加用户消息
            full_prompt += "\n\n请根据以上信息，按照要求的格式生成内容。"

            logger.info(f"开始生成 - 模块: {module}, 模型: {llm_provider.model_name}")

            # 转换图片URL为base64格式
            converted_images = convert_images_to_base64(images)
            if converted_images:
                logger.info(f"已转换 {len(converted_images)} 张图片为base64格式")

            # 处理视频URL
            if videos:
                logger.info(f"接收到 {len(videos)} 个视频URL: {videos}")

            # 5. 调用 LLM（支持多模态：文本、图片、视频）
            response = await llm_provider.generate(
                prompt=full_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                images=converted_images,
                videos=videos
            )

            # 6. 记录到会话
            if session_id:
                await self.memory_manager.add_message(
                    session_id=session_id,
                    role="user",
                    content=json.dumps(input_params, ensure_ascii=False)
                )
                await self.memory_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response.content
                )

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(f"生成完成 - 耗时: {duration_ms}ms")

            return {
                "success": True,
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "usage": response.usage,
                "duration_ms": duration_ms
            }

        except Exception as e:
            logger.exception("生成失败")
            return {
                "success": False,
                "error": str(e)
            }


