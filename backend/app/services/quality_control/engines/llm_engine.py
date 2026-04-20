"""
LLM分析引擎 - 基于大语言模型的深度语义分析

支持:
- 情节节奏分析
- 角色一致性检测
- 章末悬念评估
- 伏笔回收追踪
- 动作逻辑校验

效率优化:
- 批量处理: 多章节打包分析
- 精准提示词: 仅传入关键信息
- 结构化输出: JSON格式减少冗余

@date: 2026-04-12
@version: v3.1.0
@author: 周金磊
"""
import json
import re
from typing import Dict, List, Any, Optional

from app.core.logger import get_logger
from app.services.quality_control.prompts.quality_prompts import QUALITY_PROMPTS

logger = get_logger("quality_control.llm_engine")


class LLMAnalysisEngine:
    """
    LLM分析引擎

    调用LLM执行深度语义分析
    支持批量处理和结构化输出
    """

    def __init__(self, llm_manager, db=None, user_id=0):
        self.llm_manager = llm_manager
        self.db = db
        self.user_id = user_id

    async def analyze_with_llm(
        self,
        prompt: str,
        system_prompt: str = "你是一个专业的文学分析助手。",
        model: str = "deepseek-chat",
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> Dict:
        """
        执行LLM分析

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            分析结果字典
        """
        try:
            # 获取LLM提供者
            provider = await self.llm_manager.get_provider_from_db(
                db=self.db,
                user_id=self.user_id,
                provider_name="deepseek"
            )

            # 调用LLM
            response = await provider.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )

            # 解析JSON输出
            content = response.content if hasattr(
                response, 'content') else str(response)
            result = self._parse_json_response(content)

            return {
                "success": True,
                "data": result,
                "tokens": response.usage.get("total_tokens", 0) if hasattr(response, 'usage') else 0
            }

        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "tokens": 0
            }

    async def analyze_pacing_batch(
        self,
        chapter_summaries: List[Dict],
        batch_size: int = 10
    ) -> Dict:
        """
        批量分析情节节奏

        Args:
            chapter_summaries: 章节摘要列表 [{"chapter_number": 1, "summary": "..."}]
            batch_size: 批次大小

        Returns:
            节奏分析结果
        """
        all_scores = {}
        total_tokens = 0

        # 分批处理
        for i in range(0, len(chapter_summaries), batch_size):
            batch = chapter_summaries[i:i+batch_size]

            # 构建提示词
            prompt = QUALITY_PROMPTS["pacing_analysis"].format(
                chapters=json.dumps(batch, ensure_ascii=False, indent=2)
            )

            result = await self.analyze_with_llm(
                prompt=prompt,
                max_tokens=1500
            )

            if result["success"]:
                all_scores.update(result["data"])
                total_tokens += result["tokens"]

        return {
            "scores": all_scores,
            "tokens": total_tokens
        }

    async def analyze_character_consistency(
        self,
        character_profile: Dict,
        character_actions: List[Dict]
    ) -> Dict:
        """
        分析角色一致性

        Args:
            character_profile: 角色设定 {"name": "张三", "traits": ["勇敢", "冲动"]}
            character_actions: 角色行为列表 [{"chapter": 1, "action": "..."}]

        Returns:
            一致性分析结果
        """
        prompt = QUALITY_PROMPTS["character_consistency"].format(
            profile=json.dumps(character_profile,
                               ensure_ascii=False, indent=2),
            actions=json.dumps(
                # 最多20个行为
                character_actions[:20], ensure_ascii=False, indent=2)
        )

        result = await self.analyze_with_llm(
            prompt=prompt,
            max_tokens=2000
        )

        return result

    async def analyze_chapter_hooks(
        self,
        chapter_endings: List[Dict]
    ) -> Dict:
        """
        分析章末悬念

        Args:
            chapter_endings: 章末内容列表 [{"chapter": 1, "ending": "..."}]

        Returns:
            悬念分析结果
        """
        prompt = QUALITY_PROMPTS["chapter_hooks"].format(
            endings=json.dumps(chapter_endings, ensure_ascii=False, indent=2)
        )

        result = await self.analyze_with_llm(
            prompt=prompt,
            max_tokens=1500
        )

        return result

    async def analyze_foreshadowing(
        self,
        full_text_summary: str,
        identified_foreshadows: List[Dict]
    ) -> Dict:
        """
        分析伏笔回收

        Args:
            full_text_summary: 全文摘要
            identified_foreshadows: 已识别的伏笔列表

        Returns:
            伏笔分析结果
        """
        prompt = QUALITY_PROMPTS["foreshadowing_tracking"].format(
            summary=full_text_summary[:3000],  # 限制长度
            foreshadows=json.dumps(
                identified_foreshadows, ensure_ascii=False, indent=2)
        )

        result = await self.analyze_with_llm(
            prompt=prompt,
            max_tokens=2000
        )

        return result

    async def analyze_action_logic(
        self,
        action_scenes: List[Dict]
    ) -> Dict:
        """
        分析动作逻辑

        Args:
            action_scenes: 动作场景列表

        Returns:
            动作逻辑分析结果
        """
        prompt = QUALITY_PROMPTS["action_logic"].format(
            scenes=json.dumps(
                action_scenes[:5], ensure_ascii=False, indent=2)  # 最多5个场景
        )

        result = await self.analyze_with_llm(
            prompt=prompt,
            max_tokens=1500
        )

        return result

    def _parse_json_response(self, content: str) -> Dict:
        """解析LLM的JSON响应"""
        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取JSON块
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except:
                    pass

            # 尝试查找{}块
            brace_match = re.search(r'\{[\s\S]*\}', content)
            if brace_match:
                try:
                    return json.loads(brace_match.group())
                except:
                    pass

            # 解析失败,返回原始内容
            logger.warning(f"JSON解析失败,返回原始内容: {content[:200]}")
            return {"raw_content": content}
