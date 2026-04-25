"""
大纲生成器 - API层接口定义
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncGenerator


class OutlineGeneratorProtocol(ABC):
    """大纲生成器协议接口"""

    @abstractmethod
    async def generate_global_outline(
        self,
        content_type: str,
        input_params: Dict[str, Any],
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_quality_control: bool = True,
        cancel_event=None,
    ) -> Dict[str, Any]:
        """生成全局大纲"""
        ...

    @abstractmethod
    async def generate_global_outline_stream(
        self,
        content_type: str,
        input_params: Dict[str, Any],
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_quality_control: bool = True,
        cancel_event=None,
    ) -> AsyncGenerator[str, None]:
        """流式生成全局大纲"""
        ...

    @abstractmethod
    async def generate_unit_summaries(
        self,
        global_outline: str,
        unit_count: int,
        content_type: str,
        series_type: str = None,
        episode_duration_range: str = None,
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_quality_control: bool = True,
        qc_mode: str = "manual",
        cancel_event=None,
    ) -> Dict[str, Any]:
        """生成单元概述"""
        ...

    @abstractmethod
    async def generate_unit_summaries_stream(
        self,
        global_outline: str,
        unit_count: int,
        content_type: str,
        series_type: str = None,
        episode_duration_range: str = None,
        provider: str = None,
        model: str = None,
        temperature: float = 0.7,
        user_id: int = None,
        enable_quality_control: bool = True,
        qc_mode: str = "manual",
        cancel_event=None,
    ) -> AsyncGenerator[str, None]:
        """流式生成单元概述"""
        ...

    @abstractmethod
    def parse_unit_summaries(
        self,
        content: str,
        expected_count: int,
        content_type: str
    ) -> Dict[str, Dict[str, Any]]:
        """解析单元概述内容"""
        ...

    @abstractmethod
    async def continue_unit_summaries_generation(
        self,
        global_outline: str,
        existing_parsed: Dict[str, Dict[str, Any]],
        content_type: str,
        provider: str = None,
        temperature: float = 0.7,
        user_id: int = None,
    ) -> Dict[str, Any]:
        """接续生成单元概述"""
        ...

    @abstractmethod
    async def check_and_fix_logic_issues(
        self,
        global_outline: str,
        unit_summaries: Dict[str, Dict[str, Any]],
        content_type: str,
        provider: str = None,
        temperature: float = 0.7,
        user_id: int = None,
    ) -> Dict[str, Any]:
        """检测并修正逻辑问题"""
        ...

    @abstractmethod
    async def analyze_global_outline_quality(
        self,
        global_outline_content: str,
        project,
        user_id: int,
        dimensions: List[str] = None,
        depth: str = "standard",
        task_id: str = None,
    ) -> Dict[str, Any]:
        """全局大纲质量分析"""
        ...

    @abstractmethod
    async def revise_global_outline_by_quality(
        self,
        original_outline: str,
        quality_report: Dict[str, Any],
        issues_to_fix: List[str] = None,
        project=None,
        user_id: int = None,
    ) -> Dict[str, Any]:
        """基于质量报告修正全局大纲"""
        ...

    @abstractmethod
    async def analyze_unit_summaries_quality_manual(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        global_outline: str,
        content_type: str,
        user_id: int = None,
    ) -> Dict[str, Any]:
        """手动触发单元概述质量检测"""
        ...

    @abstractmethod
    async def revise_unit_summaries_quality(
        self,
        unit_summaries: Dict[str, Dict[str, Any]],
        quality_report: Dict[str, Any],
        global_outline: str,
        content_type: str,
        temperature: float = 0.7,
        user_id: int = None,
    ) -> Dict[str, Any]:
        """对单元概述执行质量修正"""
        ...
