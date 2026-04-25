"""大纲生成器 - 知识库修正与逻辑性修正Mixin"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
from typing import Optional
from typing import Any
import json
import re
import os
from app.agents.orchestrator import get_agent_orchestrator
from app.services.outline_generator.api.constants import MIN_REVISION_LENGTH
from app.services.outline_generator.api.constants import OUTLINE_REVISION_PROMPT
from app.services.outline_generator.api.constants import LOGIC_CHECK_PROMPT


class RevisionMixin:
    """知识库修正与逻辑性修正"""

    async def _revise_with_knowledge_base(
        self,
        llm_provider,
        original_content: str,
        input_params: Dict[str, Any],
        temperature: float = 0.7,
        db: AsyncSession = None,
        user_id: int = None,
        content_type: str = "script"
    ) -> Optional[str]:
        """
        使用知识库修正大纲内容

        直接生成修正后的完整内容，替换原始内容

        Args:
            llm_provider: LLM提供者
            original_content: 原始大纲内容
            input_params: 输入参数
            temperature: 温度参数
            db: 数据库会话（用于知识库检索）
            user_id: 用户ID（用于知识库检索）
            content_type: 内容类型（用于确定检索模块）

        Returns:
            修正后的内容，如果修正失败返回None
        """
        # 常量定义 - 已禁用截断
        MIN_REVISION_LENGTH = 100  # 修正结果最小长度阈值

        try:
            # 检查是否有必要的参数进行知识库检索
            if not db or not user_id:
                self.logger.info("[知识库修正] 缺少db或user_id参数，跳过知识库修正")
                return None

            # 获取 orchestrator 实例（用于知识库检索）
            orchestrator = get_agent_orchestrator()

            # 构建查询文本（使用原始内容的关键信息）
            # 注意：input_params 的值可能是列表，需要转换为字符串
            def _safe_get_str(params, key, default=''):
                """安全获取字符串值，处理列表类型"""
                val = params.get(key, default)
                if isinstance(val, list):
                    return ' '.join(str(v) for v in val)
                return str(val) if val else default

            query_text = (_safe_get_str(input_params, 'title') + " " +
                          _safe_get_str(input_params, 'theme') + " " +
                          _safe_get_str(input_params, 'genre')).strip()

            # 不再截断查询文本
            if not query_text.strip():
                query_text = original_content  # 使用完整内容

            # 确定模块名称
            module_name = f"{content_type}_global_outline"

            # 使用 orchestrator 的知识库检索方法（检索三类知识库）
            kb_contexts = await orchestrator._retrieve_classified_knowledge(
                db=db,
                user_id=user_id,
                module=module_name,
                query_text=query_text,
                kb_vertical=True,  # 启用垂直领域知识库
                kb_user_specific=False,  # 暂不启用用户专属
                kb_manual=True  # 启用官方手册
            )

            # 检查是否有知识库内容
            theory_context = kb_contexts.get('theory', '').strip()
            case_context = kb_contexts.get('case', '').strip()
            manual_context = kb_contexts.get('manual', '').strip()

            if not theory_context and not case_context and not manual_context:
                self.logger.info("[知识库修正] 无相关知识点，跳过修正")
                return None

            # 不再截断大纲内容，直接使用完整内容

            # 构建修正提示词
            revision_prompt = OUTLINE_REVISION_PROMPT.format(
                original_outline=original_content,  # 使用完整内容
                theory_context=theory_context or "无相关理论",
                case_context=case_context or "无相关案例",
                manual_context=manual_context or "无规范手册"
            )

            # 调用LLM进行修正
            response = await llm_provider.generate(
                prompt=revision_prompt,
                temperature=temperature
            )

            revised_content = response.content if hasattr(
                response, 'content') else str(response)

            # 验证修正后的内容
            if revised_content and len(revised_content) > MIN_REVISION_LENGTH:
                self.logger.info(
                    f"[知识库修正] 修正成功，原长度={len(original_content)}，新长度={len(revised_content)}")
                return revised_content
            else:
                self.logger.warning(
                    f"[知识库修正] 修正结果长度不足（{len(revised_content) if revised_content else 0}字符），使用原始内容")
                return None

        except Exception as e:
            self.logger.error(f"[知识库修正] 修正失败: {str(e)}")
            return None


    async def check_and_fix_logic_issues(
        self,
        global_outline: str,
        unit_summaries: Dict[str, Dict[str, Any]],
        content_type: str,
        provider: str = None,
        temperature: float = 0.7,
        user_id: int = None
    ) -> Dict[str, Any]:
        """
        检测并修正单元概述中的逻辑问题

        Args:
            global_outline: 全局大纲内容
            unit_summaries: 单元概述字典
            content_type: 内容类型 (novel/script)
            provider: LLM提供商
            temperature: 温度参数
            user_id: 用户ID

        Returns:
            修正结果，包含问题列表和修正后的单元概述
        """
        result = {
            "has_issues": False,
            "issues": [],
            "revised_units": {},
            "original_units": {},  # 保存原始单元内容，用于前端差异对比
            "error": None
        }

        try:
            # 格式化单元概述列表
            formatted_units = self._format_unit_summaries_for_check(
                unit_summaries)

            if not formatted_units:
                self.logger.info("[逻辑检测] 无单元概述内容，跳过检测")
                return result

            # 构建检测提示词
            check_prompt = LOGIC_CHECK_PROMPT.format(
                global_outline=global_outline,  # 使用完整内容
                unit_summaries=formatted_units
            )

            self.logger.info(f"[逻辑检测] 开始检测，单元数: {len(unit_summaries)}")

            # 获取LLM提供商
            llm_provider = await self.llm_manager.get_provider_from_db(
                self.db, user_id, provider
            )
            if not llm_provider:
                raise ValueError(f"未找到LLM提供商: {provider}")

            # 调用LLM进行检测
            response = await llm_provider.generate(
                prompt=check_prompt,
                temperature=temperature
            )

            response_content = response.content if hasattr(
                response, 'content') else str(response)

            # 记录响应内容以便调试
            self.logger.debug(f"[逻辑检测] LLM响应长度: {len(response_content)}")
            self.logger.debug(f"[逻辑检测] LLM响应前500字符: {response_content[:500]}")

            # 解析JSON响应
            parsed_result = self._parse_logic_check_response(response_content)

            if parsed_result:
                result["has_issues"] = parsed_result.get("has_issues", False)

                # 规范化 issues 中的 unit_number
                issues = parsed_result.get("issues", [])
                for issue in issues:
                    if "unit_number" in issue:
                        # 提取 unit_number 中的数字部分
                        num_match = re.search(
                            r'(\d+)', str(issue["unit_number"]))
                        if num_match:
                            issue["unit_number"] = num_match.group(1)
                result["issues"] = issues

                revised_units = parsed_result.get("revised_units", {})

                # 规范化 revised_units 的 key（确保是纯数字字符串）
                normalized_revised_units = {}
                for key, value in revised_units.items():
                    # 提取 key 中的数字部分
                    num_match = re.search(r'(\d+)', str(key))
                    if num_match:
                        normalized_key = num_match.group(1)
                        normalized_revised_units[normalized_key] = value
                        self.logger.debug(
                            f"[逻辑检测] 规范化 key: '{key}' -> '{normalized_key}'")
                    else:
                        # 如果没有数字，保留原始 key
                        normalized_revised_units[str(key)] = value
                        self.logger.warning(f"[逻辑检测] 无法从 key '{key}' 中提取数字")
                result["revised_units"] = normalized_revised_units

                # 保存被修正单元的原始内容，用于前端差异对比
                if normalized_revised_units:
                    original_units = {}
                    unit_summaries_keys = list(unit_summaries.keys())
                    self.logger.debug(
                        f"[逻辑检测] unit_summaries 的 keys: {unit_summaries_keys[:10]}...")
                    for unit_num in normalized_revised_units.keys():
                        self.logger.debug(
                            f"[逻辑检测] 检查 unit_num '{unit_num}' 是否在 unit_summaries 中: {unit_num in unit_summaries}")
                        if unit_num in unit_summaries:
                            original_units[unit_num] = {
                                "title": unit_summaries[unit_num].get("title", ""),
                                "summary": unit_summaries[unit_num].get("summary", "")
                            }
                    result["original_units"] = original_units
                    self.logger.info(
                        f"[逻辑检测] 保存了 {len(original_units)} 个原始单元内容")

                if result["has_issues"]:
                    self.logger.info(
                        f"[逻辑检测] 检测到 {len(result['issues'])} 个问题，"
                        f"修正 {len(result['revised_units'])} 个单元"
                    )
                else:
                    self.logger.info("[逻辑检测] 未检测到逻辑问题")
            else:
                self.logger.warning("[逻辑检测] 响应解析失败")

        except Exception as e:
            import traceback
            self.logger.error(f"[逻辑检测] 检测失败: {str(e)}")
            self.logger.error(f"[逻辑检测] 异常类型: {type(e).__name__}")
            self.logger.error(f"[逻辑检测] 堆栈跟踪: {traceback.format_exc()}")
            result["error"] = str(e)

        return result


    def _format_unit_summaries_for_check(
        self,
        unit_summaries: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        格式化单元概述用于逻辑检测

        Args:
            unit_summaries: 单元概述字典

        Returns:
            格式化后的文本
        """
        lines = []
        for unit_num in sorted(unit_summaries.keys(), key=lambda x: int(x) if x.isdigit() else 0):
            unit = unit_summaries[unit_num]
            title = unit.get("title", "")
            summary = unit.get("summary", "")
            lines.append(f"### 单元 {unit_num}: {title}")
            lines.append(summary)
            lines.append("")
        return "\n".join(lines)


    def _parse_logic_check_response(self, response_content: str) -> Optional[Dict[str, Any]]:
        """
        解析逻辑检测响应

        Args:
            response_content: LLM响应内容

        Returns:
            解析后的结果字典
        """
        try:
            # 记录原始响应以便调试
            self.logger.debug(f"[逻辑检测] 原始响应长度: {len(response_content)}")

            # 尝试提取JSON块
            json_match = re.search(
                r'```json\s*([\s\S]*?)\s*```',
                response_content
            )
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试查找JSON对象的开始和结束
                start_idx = response_content.find('{')
                end_idx = response_content.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = response_content[start_idx:end_idx + 1]
                else:
                    json_str = response_content

            # 清理可能的注释和多余空白
            json_str = json_str.strip()

            # 记录提取的JSON字符串前200字符
            self.logger.debug(f"[逻辑检测] 提取的JSON前200字符: {json_str[:200]}")

            # 解析JSON
            parsed = json.loads(json_str)

            # 验证必要字段
            if "has_issues" in parsed:
                return {
                    "has_issues": parsed.get("has_issues", False),
                    "issues": parsed.get("issues", []),
                    "revised_units": parsed.get("revised_units", {})
                }

            return None

        except json.JSONDecodeError as e:
            self.logger.error(
                f"[逻辑检测] JSON解析失败: {str(e)}, 位置: {e.pos if hasattr(e, 'pos') else 'unknown'}")
            self.logger.error(
                f"[逻辑检测] 问题JSON片段: {json_str[max(0, e.pos-50):e.pos+50] if hasattr(e, 'pos') and e.pos else json_str[:100]}")
            return None
        except Exception as e:
            self.logger.error(f"[逻辑检测] 响应解析失败: {str(e)}")
            return None


