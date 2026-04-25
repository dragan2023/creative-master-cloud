"""
多Agent协作文学作品生成系统 - 合规审查Agent

模块: agents.writing
文件: compliance_agent.py
功能: 双层合规审查（Trie树本地检测 + LLM辅助判断）

依赖关系:
    - 依赖: app.agents.writing.base_agent, app.services.proofread.checkers.sensitive_checker
    - 被依赖: 总线Agent、内容发布流程

创建时间: 2026-03-27
最后修改: 2026-03-27

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import json
import re
from typing import Any, Dict, List, Optional
from dataclasses import asdict

from app.agents.writing.base_agent import BaseWritingAgent, AgentRole, AgentContext, AgentResult
from app.agents.writing.prompts.compliance_prompts import COMPLIANCE_PROMPTS
from app.core.logger import get_logger

logger = get_logger(__name__)


class SensitiveCheckerAdapter:
    """敏感词检测器适配器
    
    用于适配现有的SensitiveChecker，提供统一的检测接口。
    包装Trie树敏感词检测功能。
    """
    
    def __init__(self, compliance_level: str = "normal"):
        """初始化适配器
        
        Args:
            compliance_level: 合规检查等级 (strict/normal/loose)
        """
        self._checker = None
        self.compliance_level = compliance_level
    
    def _get_checker(self):
        """获取敏感词检测器实例（懒加载）"""
        if self._checker is None:
            try:
                from app.services.proofread.checkers.sensitive_checker import SensitiveChecker
                self._checker = SensitiveChecker(compliance_level=self.compliance_level)
                self._checker.initialize()
            except ImportError as e:
                logger.warning(f"导入SensitiveChecker失败: {e}")
                self._checker = None
            except Exception as e:
                logger.warning(f"初始化SensitiveChecker失败: {e}")
                self._checker = None
        return self._checker
    
    async def check(self, content: str) -> List[Dict]:
        """检测敏感词
        
        Args:
            content: 待检测内容
            
        Returns:
            检测结果列表，每项包含:
                - text: 检测到的文本
                - type: 问题类型
                - severity: 严重程度
                - position_start: 起始位置
                - position_end: 结束位置
                - description: 问题描述
                - suggestion: 修改建议
        """
        checker = self._get_checker()
        if checker is None:
            return []
        
        try:
            # 调用SensitiveChecker的check方法
            issues = checker.check(content)
            
            # 将SensitiveIssue转换为字典列表
            result = []
            for issue in issues:
                if hasattr(issue, '__dataclass_fields__'):
                    # 如果是dataclass，使用asdict转换
                    issue_dict = asdict(issue)
                else:
                    # 如果已经是字典
                    issue_dict = issue
                
                # 标准化字段名
                result.append({
                    "text": issue_dict.get("text", ""),
                    "type": issue_dict.get("issue_type", "sensitive_content"),
                    "severity": issue_dict.get("severity", "medium"),
                    "position_start": issue_dict.get("position_start", 0),
                    "position_end": issue_dict.get("position_end", 0),
                    "description": issue_dict.get("description", ""),
                    "suggestion": issue_dict.get("suggestion", "")
                })
            
            return result
            
        except Exception as e:
            logger.warning(f"敏感词检测失败: {e}")
            return []
    
    def update_compliance_level(self, level: str):
        """更新合规检查等级
        
        Args:
            level: 新的检查等级 (strict/normal/loose)
        """
        self.compliance_level = level
        if self._checker:
            self._checker.update_compliance_level(level)


class ComplianceAgent(BaseWritingAgent):
    """合规审查Agent
    
    负责双层合规审查：
    1. 第一层：Trie树本地敏感词检测（快速、无网络开销）
    2. 第二层：LLM辅助判断（处理上下文相关的敏感内容）
    
    Attributes:
        agent_name: Agent名称
        agent_role: Agent角色类型
        default_model: 默认使用模型
        default_temperature: 默认温度参数
    """
    
    agent_name = "合规审查Agent"
    agent_role = AgentRole.COMPLIANCE
    default_model = ""
    default_temperature = 0.1
    
    def __init__(self, config=None):
        """初始化合规审查Agent
        
        Args:
            config: Agent配置对象
        """
        super().__init__(config)
        self._sensitive_checker_adapter = None
    
    def _get_sensitive_checker(self) -> SensitiveCheckerAdapter:
        """获取敏感词检测器适配器（懒加载）"""
        if self._sensitive_checker_adapter is None:
            self._sensitive_checker_adapter = SensitiveCheckerAdapter()
        return self._sensitive_checker_adapter
    
    async def execute(self, context: AgentContext) -> AgentResult:
        """双层合规审查
        
        先使用Trie树进行本地敏感词检测，
        如有可疑内容或需要深度审查，再调用LLM辅助判断。
        
        Args:
            context: Agent执行上下文
            
        Returns:
            AgentResult: 包含以下data字段:
                - violations: 违规列表
                - trie_hits: Trie树检测命中数
                - llm_flags: LLM标记数
                - approved: 是否通过
                - score: 合规评分0-100
        """
        start_time = self._get_timestamp()
        
        try:
            # 获取待审查内容
            content = context.extra.get("draft_content", "")
            if not content:
                return self._build_error_result(
                    "缺少待审查内容",
                    error_type="missing_content"
                )
            
            # 第一层：Trie树本地敏感词检测
            self.logger.info(f"开始Trie树敏感词检测 - Task: {context.task_id}")
            trie_results = await self._check_with_trie(content)
            
            # 第二层：LLM辅助判断
            llm_results = []
            deep_check = context.extra.get("deep_check", False)
            
            # 当Trie树检测到可疑内容或需要深度审查时调用LLM
            if trie_results or deep_check:
                self.logger.info(
                    f"开始LLM辅助合规检查 - Task: {context.task_id}, "
                    f"Trie hits: {len(trie_results)}, Deep check: {deep_check}"
                )
                llm_results = await self._check_with_llm(content, context, trie_results)
            
            # 合并结果
            all_violations = self._merge_violations(trie_results, llm_results)
            
            # 计算合规评分
            score = self._calculate_compliance_score(all_violations)
            
            # 判断是否通过（score >= 80 且没有high级别违规）
            high_severity = [v for v in all_violations if v.get("severity") == "high"]
            approved = score >= 80 and len(high_severity) == 0
            
            duration_ms = self._get_timestamp() - start_time
            
            self.logger.info(
                f"合规审查完成 - Task: {context.task_id}, "
                f"Score: {score}, Violations: {len(all_violations)}, "
                f"Approved: {approved}"
            )
            
            return self._build_success_result(
                content="",  # 合规审查不返回内容
                duration_ms=duration_ms,
                violations=all_violations,
                trie_hits=len(trie_results),
                llm_flags=len(llm_results),
                approved=approved,
                score=score
            )
            
        except Exception as e:
            self.logger.error(f"合规审查执行失败: {e}")
            return self._build_error_result(str(e))
    
    async def _check_with_trie(self, content: str) -> List[Dict]:
        """Trie树敏感词检测
        
        Args:
            content: 待检测内容
            
        Returns:
            检测结果列表
        """
        checker = self._get_sensitive_checker()
        return await checker.check(content)
    
    async def _check_with_llm(
        self,
        content: str,
        context: AgentContext,
        trie_results: List[Dict]
    ) -> List[Dict]:
        """LLM辅助合规检查
        
        使用LLM检查上下文相关的敏感内容。
        
        Args:
            content: 待检测内容
            context: Agent执行上下文
            trie_results: Trie树检测结果（作为参考）
            
        Returns:
            LLM检测结果列表
        """
        try:
            # 构建提示词
            system_prompt = COMPLIANCE_PROMPTS["system"]
            user_prompt = COMPLIANCE_PROMPTS["llm_check"].format(
                content=content,
                trie_findings=self._format_trie_results(trie_results),
                content_type=context.extra.get("content_type", "文学作品")
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # 调用LLM（不传递max_tokens，让LLM自主控制）
            llm_result = await self.call_llm(
                messages=messages,
                task_id=context.task_id
            )
            
            # 解析结果
            try:
                result_data = self._parse_llm_response(llm_result["content"])
                return result_data.get("violations", [])
            except Exception as e:
                self.logger.error(f"LLM合规检查结果解析失败: {e}")
                return []
                
        except Exception as e:
            self.logger.error(f"LLM合规检查失败: {e}")
            return []
    
    def _format_trie_results(self, results: List[Dict]) -> str:
        """格式化Trie树检测结果
        
        Args:
            results: Trie树检测结果列表
            
        Returns:
            格式化后的字符串
        """
        if not results:
            return "Trie树未检测到敏感内容"
        
        formatted = []
        for i, result in enumerate(results, 1):
            text = result.get("text", "")
            issue_type = result.get("type", "")
            severity = result.get("severity", "")
            description = result.get("description", "")
            
            lines = [f"{i}. [{severity.upper()}] {issue_type}"]
            lines.append(f"   文本: 「{text}」")
            if description:
                lines.append(f"   说明: {description}")
            
            formatted.append("\n".join(lines))
        
        return "\n\n".join(formatted)
    
    def _merge_violations(
        self,
        trie_results: List[Dict],
        llm_results: List[Dict]
    ) -> List[Dict]:
        """合并Trie树和LLM的检测结果
        
        Args:
            trie_results: Trie树检测结果
            llm_results: LLM检测结果
            
        Returns:
            合并后的违规列表
        """
        violations = []
        
        # 添加Trie树结果
        for result in trie_results:
            violations.append({
                "source": "trie",
                "text": result.get("text", ""),
                "type": result.get("type", ""),
                "severity": result.get("severity", "medium"),
                "description": result.get("description", ""),
                "suggestion": result.get("suggestion", ""),
                "position": {
                    "start": result.get("position_start", 0),
                    "end": result.get("position_end", 0)
                }
            })
        
        # 添加LLM结果（去重）
        existing_texts = {v["text"] for v in violations}
        for result in llm_results:
            text = result.get("text", "")
            # 如果LLM检测到的内容与Trie树重复，合并信息
            if text in existing_texts:
                for v in violations:
                    if v["text"] == text:
                        v["source"] = "both"
                        # 如果LLM认为更严重，更新严重程度
                        if result.get("severity") == "high":
                            v["severity"] = "high"
                        break
            else:
                violations.append({
                    "source": "llm",
                    "text": text,
                    "type": result.get("type", ""),
                    "severity": result.get("severity", "medium"),
                    "description": result.get("description", ""),
                    "suggestion": result.get("suggestion", ""),
                    "position": result.get("position", {})
                })
        
        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        violations.sort(key=lambda x: severity_order.get(x["severity"], 3))
        
        return violations
    
    def _calculate_compliance_score(self, violations: List[Dict]) -> int:
        """计算合规评分
        
        Args:
            violations: 违规列表
            
        Returns:
            合规评分0-100
        """
        if not violations:
            return 100
        
        # 计算扣分
        high_count = sum(1 for v in violations if v["severity"] == "high")
        medium_count = sum(1 for v in violations if v["severity"] == "medium")
        low_count = sum(1 for v in violations if v["severity"] == "low")
        
        # 扣分规则：high=30分, medium=10分, low=5分
        deduction = high_count * 30 + medium_count * 10 + low_count * 5
        
        score = max(0, 100 - deduction)
        return score
    
    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """解析LLM返回的JSON响应
        
        Args:
            content: LLM返回的原始内容
            
        Returns:
            解析后的字典
        """
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.debug("直接JSON解析失败，尝试从Markdown代码块提取")
        
        # 尝试从Markdown代码块中提取
        import re
        json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(json_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                logger.debug("Markdown代码块JSON解析失败，跳过")
                continue

        # 尝试查找JSON对象
        json_pattern2 = r'\{[\s\S]*?"violations"[\s\S]*?\}'
        matches2 = re.findall(json_pattern2, content)
        
        for match in matches2:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                logger.debug("JSON对象正则解析失败，跳过")
                continue

        # 如果都失败了，返回默认结构
        self.logger.warning("无法解析LLM返回的JSON，使用默认结构")
        return {"violations": []}
    
    def _get_timestamp(self) -> int:
        """获取当前时间戳（毫秒）"""
        import time
        return int(time.time() * 1000)
