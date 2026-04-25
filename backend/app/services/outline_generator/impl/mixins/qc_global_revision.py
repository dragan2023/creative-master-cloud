"""大纲生成器 - 全局大纲质量修正Mixin"""
from typing import Dict
from typing import List
from typing import Any
import re
from app.agents.llm_manager import get_llm_manager


class QcGlobalRevisionMixin:
    """全局大纲质量修正"""

    async def revise_global_outline_by_quality(
        self,
        original_outline: str,
        quality_report: Dict,
        issues_to_fix: List[str],
        project,
        user_id: int
    ) -> Dict[str, Any]:
        """
        根据质控报告修正全局大纲

        Args:
            original_outline: 原始大纲内容
            quality_report: 质控报告
            issues_to_fix: 需要修正的问题ID列表
            project: 项目对象
            user_id: 用户ID

        Returns:
            修正结果 {"success": bool, "revised_content": str, "changes": []}
        """
        result = {
            "success": False,
            "revised_content": None,
            "changes": [],
            "error": None
        }

        try:
            # 1. 筛选需要修正的问题
            issues = quality_report.get("issues", [])
            issues_to_fix_list = [
                issue for issue in issues
                if issue.get("id") in issues_to_fix
            ]

            if not issues_to_fix_list:
                result["error"] = "没有选择需要修正的问题"
                return result

            self.logger.info(
                f"[全局大纲修正] 开始修正,问题数: {len(issues_to_fix_list)}"
            )

            # 2. 获取LLM提供者
            from app.agents.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_provider = await llm_manager.get_provider_from_db(self.db, user_id)

            if not llm_provider:
                result["error"] = "无法获取LLM提供者"
                return result

            # 3. 构建修正提示词
            revision_prompt = self._build_global_outline_revision_prompt(
                original_outline=original_outline,
                issues=issues_to_fix_list
            )

            # 4. 调用LLM执行修正 - 超时1200秒(20分钟),带429重试
            self.logger.info("[全局大纲修正] 调用LLM执行修正...")

            # 添加429重试机制
            import asyncio
            max_retries = 3
            retry_delay = 5
            response = None

            for attempt in range(max_retries):
                try:
                    response = await llm_provider.generate(
                        prompt=revision_prompt,
                        temperature=0.3,
                        timeout=1200  # ✅ 20分钟超时
                    )
                    break  # 成功则跳出
                except Exception as e:
                    error_str = str(e)
                    if '429' in error_str or 'TooManyRequests' in error_str or 'ServerOverloaded' in error_str:
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (2 ** attempt)
                            self.logger.warning(
                                f"[全局大纲修正] LLM返回429错误,第{attempt+1}次重试,"
                                f"等待{wait_time}秒..."
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            self.logger.error(
                                f"[全局大纲修正] LLM 429错误,已重试{max_retries}次")
                            raise
                    else:
                        raise  # 其他错误直接抛出

            # ✅ 安全访问response
            revised_content = response.content if hasattr(
                response, 'content') else str(response)

            # 5. 清理修正内容（移除可能的Markdown标记）
            revised_content = self._clean_revised_content(revised_content)

            # v2.4优化：直接使用LLM输出的完整大纲，不再增量合并
            # LLM已经基于整体视角输出了完整的修正后大纲
            revision_effective = False  # 标记修正是否真正生效

            if revised_content and len(revised_content) > 100:
                # 验证输出是否有效（至少包含基本的大纲结构）
                if '##' in revised_content or '###' in revised_content:
                    revision_effective = True
                    self.logger.info(
                        f"[全局大纲修正] v2.4整体修正完成, 原始长度: {len(original_outline)}, "
                        f"修正后长度: {len(revised_content)}"
                    )
                else:
                    # 如果输出不包含大纲结构，可能LLM输出异常，使用原始内容
                    self.logger.warning(
                        "[全局大纲修正] LLM输出缺少大纲结构，保留原始内容"
                    )
                    revised_content = original_outline
                    result["revision_skipped"] = True
                    result["skip_reason"] = "LLM输出缺少大纲结构"
            else:
                # 输出过短，可能是异常
                self.logger.warning(
                    f"[全局大纲修正] LLM输出过短({len(revised_content) if revised_content else 0}字)，保留原始内容"
                )
                revised_content = original_outline
                result["revision_skipped"] = True
                result["skip_reason"] = f"LLM输出过短({len(revised_content) if revised_content else 0}字)"

            # 7. 构建变更说明
            changes = []
            if revision_effective:
                for issue in issues_to_fix_list:
                    changes.append({
                        "issue_id": issue.get("id"),
                        "category": issue.get("category"),
                        "description": issue.get("description"),
                        "suggestion": issue.get("suggestion")
                    })

            result["success"] = True
            result["revised_content"] = revised_content
            result["changes"] = changes
            # v2.4.1: 明确标记修正是否生效
            result["revision_effective"] = revision_effective

            if revision_effective:
                self.logger.info(
                    f"[全局大纲修正] 修正完成,原始长度: {len(original_outline)}, "
                    f"修正后长度: {len(revised_content)}"
                )
            else:
                self.logger.warning(
                    f"[全局大纲修正] 修正未生效,保留原始内容,长度: {len(original_outline)}"
                )

        except Exception as e:
            self.logger.error(f"[全局大纲修正] 修正失败: {e!r}")
            result["error"] = str(e)

        return result


    def _build_global_outline_revision_prompt(
        self,
        original_outline: str,
        issues: List[Dict]
    ) -> str:
        """构建全局大纲修正提示词 - v2.4优化：辩证性整体修正模式

        核心改进：
        1. LLM一次性获取所有问题信息
        2. 基于整体视角进行辩证性修正
        3. 考虑问题之间的相互关系和整体协调性
        4. 输出完整的修正后大纲
        """
        # 构建问题列表
        issues_text = "\n".join([
            f"- [{issue.get('id')}] [{issue.get('dimension', '未知维度')}] {issue.get('category', '未知分类')}\n"
            f"  问题描述: {issue.get('description', '无描述')}\n"
            f"  修正建议: {issue.get('suggestion', '请根据专业判断修正')}"
            + (f"\n  相关证据: {issue.get('evidence', '')[:300]}" if issue.get('evidence') else "")
            for issue in issues
        ])

        # 提取问题维度统计
        dimensions = {}
        for issue in issues:
            dim = issue.get('dimension', '未知维度')
            dimensions[dim] = dimensions.get(dim, 0) + 1

        dimension_summary = "\n".join([
            f"- {dim}: {count}个问题"
            for dim, count in dimensions.items()
        ])

        prompt = f"""你是一位资深的小说主编，拥有丰富的创作指导和内容审核经验。现在需要你基于质控报告，对全局大纲进行辩证性整体修正。

【重要原则】
1. **整体视角**：不要逐个问题单独修正，而是综合分析所有问题后，从整体协调性出发进行修正
2. **辩证思考**：问题之间可能存在关联，修正时需要考虑问题A的修正是否会影响问题B
3. **一致性保证**：确保修正后的内容在逻辑、人物、世界观、情节线上保持一致
4. **保留优点**：修正问题的同时，保留原始大纲的优点和特色

【原始全局大纲】
{original_outline}

【质控报告摘要】
共检测到 {len(issues)} 个问题，分布如下：
{dimension_summary}

【详细问题列表】
{issues_text}

【修正要求】
1. 首先阅读并理解所有问题，分析问题之间的关联性
2. 识别哪些问题是核心问题，哪些是衍生问题（解决核心问题可能同时解决衍生问题）
3. 制定整体修正策略，而非逐个问题打补丁
4. 输出完整的修正后全局大纲（保持原有格式和结构）
5. 确保修正后的内容：
   - 逻辑自洽，前后呼应
   - 人物性格和发展弧线一致
   - 世界观设定无矛盾
   - 情节推进合理、节奏得当

【输出格式】
请直接输出修正后的完整全局大纲，不要添加额外说明。
使用与原文相同的Markdown格式结构。

【修正后的全局大纲】
"""
        return prompt


    def _clean_revised_content(self, content: str) -> str:
        """清理修正后的内容(移除Markdown标记等)"""
        import re

        # 移除可能的```标记
        content = re.sub(r'^```\s*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^```[a-z]*\s*$', '', content, flags=re.MULTILINE)

        # 移除开头和结尾的空白
        content = content.strip()

        return content

    # ==================== v2.3新增：自动质控修正方法 ====================


