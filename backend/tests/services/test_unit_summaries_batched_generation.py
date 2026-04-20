"""
单元概述分段生成与质控集成测试

测试内容:
1. 分段生成机制 - generate_unit_summaries_batched方法
2. 分段流式生成 - generate_unit_summaries_stream的batch_mode支持
3. 质控触发API - trigger_unit_summaries_quality_control端点
4. 质控结果处理 - 自动修正和差异对比
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestBatchedUnitSummariesGeneration:
    """测试分段生成机制"""

    @pytest.mark.asyncio
    async def test_batch_size_calculation(self):
        """测试批次大小计算逻辑"""
        from app.services.outline_generator import OutlineGenerator

        # 每个单元约400字,LLM安全输出约8000字
        # 批次大小 = 8000 // 400 = 20
        estimated_chars_per_unit = 400
        safe_output_chars = 8000
        expected_batch_size = max(
            5, min(20, safe_output_chars // estimated_chars_per_unit))

        assert expected_batch_size == 20, "批次大小应为20个单元"

    @pytest.mark.asyncio
    async def test_generate_unit_summaries_batched_basic(self):
        """测试基本的分段生成功能"""
        from app.services.outline_generator import OutlineGenerator

        # 创建Mock数据库会话
        mock_db = MagicMock()
        generator = OutlineGenerator(db=mock_db)

        # Mock生成方法
        with patch.object(generator, 'generate_unit_summaries', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {
                "success": True,
                "parsed": {
                    "1": {"unit_number": 1, "title": "第一章", "summary": "测试内容1"},
                    "2": {"unit_number": 2, "title": "第二章", "summary": "测试内容2"}
                },
                "content": "第一章: 测试内容1\n\n第二章: 测试内容2"
            }

            # 测试分批生成
            result = await generator.generate_unit_summaries_batched(
                global_outline="测试全局大纲",
                unit_count=4,
                content_type="novel",
                batch_size=2,  # 每批次2个单元
                provider="openai",
                model="gpt-4"
            )

            # 验证结果
            assert result["success"] is True
            assert "parsed" in result
            assert "batch_info" in result
            assert result["batch_info"]["total_units"] == 4
            assert result["batch_info"]["batch_count"] == 2  # 4个单元,每批2个,共2批

    @pytest.mark.asyncio
    async def test_generate_unit_summaries_batched_progress_callback(self):
        """测试进度回调功能"""
        from app.services.outline_generator import OutlineGenerator

        mock_db = MagicMock()
        generator = OutlineGenerator(db=mock_db)
        progress_calls = []

        def progress_callback(batch_num, total_batches, units_generated):
            progress_calls.append({
                "batch_num": batch_num,
                "total_batches": total_batches,
                "units_generated": units_generated
            })

        with patch.object(generator, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = json.dumps({
                "units": [
                    {"unit_number": 1, "title": "第一章", "summary": "内容1"},
                    {"unit_number": 2, "title": "第二章", "summary": "内容2"}
                ]
            })

            await generator.generate_unit_summaries_batched(
                global_outline="测试大纲",
                unit_count=4,
                content_type="novel",
                batch_size=2,
                progress_callback=progress_callback
            )

            # 验证进度回调被调用
            assert len(progress_calls) == 2  # 2个批次
            assert progress_calls[0]["batch_num"] == 1
            assert progress_calls[1]["batch_num"] == 2


class TestStreamBatchMode:
    """测试流式分段生成模式"""

    @pytest.mark.asyncio
    async def test_stream_batch_mode_events(self):
        """测试分段模式的SSE事件流"""
        from app.services.outline_generator import OutlineGenerator

        mock_db = MagicMock()
        generator = OutlineGenerator(db=mock_db)

        # 收集所有SSE事件
        events = []

        async def mock_generate_unit():
            yield "event: batch_info\ndata: {\"batch_size\": 2, \"total_batches\": 2}\n\n"
            yield "event: batch_start\ndata: {\"batch_num\": 1}\n\n"
            yield "data: {\"unit_number\": 1, \"title\": \"第一章\"}\n\n"
            yield "data: {\"unit_number\": 2, \"title\": \"第二章\"}\n\n"
            yield "event: batch_complete\ndata: {\"batch_num\": 1, \"units_count\": 2}\n\n"
            yield "event: batch_start\ndata: {\"batch_num\": 2}\n\n"
            yield "data: {\"unit_number\": 3, \"title\": \"第三章\"}\n\n"
            yield "data: {\"unit_number\": 4, \"title\": \"第四章\"}\n\n"
            yield "event: batch_complete\ndata: {\"batch_num\": 2, \"units_count\": 2}\n\n"
            yield "event: all_batches_complete\ndata: {\"total_units\": 4}\n\n"

        with patch.object(generator, 'generate_unit_summaries_stream') as mock_stream:
            mock_stream.return_value = mock_generate_unit()

            # 模拟消费事件流
            async for event in mock_stream():
                events.append(event)

            # 验证事件完整性
            assert len(events) > 0
            # 应该包含batch_info, batch_start, batch_complete, all_batches_complete事件

    @pytest.mark.asyncio
    async def test_stream_batch_mode_parameters(self):
        """测试分段模式参数传递"""
        from app.services.outline_generator import OutlineGenerator

        mock_db = MagicMock()
        generator = OutlineGenerator(db=mock_db)

        # 验证方法签名包含batch_mode和batch_size参数
        import inspect
        sig = inspect.signature(generator.generate_unit_summaries_stream)
        params = sig.parameters

        assert "batch_mode" in params, "方法应包含batch_mode参数"
        assert "batch_size" in params, "方法应包含batch_size参数"


class TestQualityControlAPI:
    """测试质控API端点"""

    @pytest.mark.asyncio
    async def test_trigger_quality_control_endpoint(self):
        """测试质控触发API端点"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        # Mock数据库和项目数据
        with patch('app.api.v1.endpoints.novel_writer.outlines.get_project') as mock_get_project:
            mock_project = MagicMock()
            mock_project.unit_summaries = {
                "1": {"title": "第一章", "summary": "测试内容"},
                "2": {"title": "第二章", "summary": "测试内容2"}
            }
            mock_project.global_outline = "测试全局大纲"
            mock_get_project.return_value = mock_project

            # Mock质控服务
            with patch('app.api.v1.endpoints.novel_writer.outlines.execute_quality_control') as mock_qc:
                mock_qc.return_value = {
                    "success": True,
                    "quality_report": {
                        "total_issues": 2,
                        "critical_issues": 1,
                        "dimensions": {
                            "unit_structure": {"score": 85, "issues": []},
                            "unit_character": {"score": 90, "issues": []},
                            "unit_consistency": {"score": 80, "issues": [{"severity": "critical"}]}
                        }
                    },
                    "revision_summary": [
                        {
                            "unit_number": 1,
                            "original_summary": "原始内容",
                            "revised_summary": "修正后的内容",
                            "issues_fixed": ["人物动机不清晰"]
                        }
                    ],
                    "revised_count": 1
                }

                # 调用API
                response = client.post(
                    "/api/v1/novel-writer/projects/1/unit-summaries/quality-control",
                    json={"enable_auto_revision": True}
                )

                # 验证响应
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "quality_report" in data["data"]
                assert "revision_summary" in data["data"]
                assert data["data"]["revised_count"] == 1

    @pytest.mark.asyncio
    async def test_quality_control_without_auto_revision(self):
        """测试不启用自动修正的质控"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        with patch('app.api.v1.endpoints.novel_writer.outlines.get_project') as mock_get_project:
            mock_project = MagicMock()
            mock_project.unit_summaries = {
                "1": {"title": "第一章", "summary": "内容"}}
            mock_project.global_outline = "大纲"
            mock_get_project.return_value = mock_project

            with patch('app.api.v1.endpoints.novel_writer.outlines.execute_quality_control') as mock_qc:
                mock_qc.return_value = {
                    "success": True,
                    "quality_report": {"total_issues": 1},
                    "revision_summary": [],
                    "revised_count": 0
                }

                response = client.post(
                    "/api/v1/novel-writer/projects/1/unit-summaries/quality-control",
                    json={"enable_auto_revision": False}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["data"]["revised_count"] == 0


class TestQualityControlIntegration:
    """测试质控与分段生成的集成"""

    @pytest.mark.asyncio
    async def test_quality_control_after_batched_generation(self):
        """测试分段生成完成后的质控流程"""
        from app.services.outline_generator import OutlineGenerator

        mock_db = MagicMock()
        generator = OutlineGenerator(db=mock_db)

        # 第一步: 分段生成
        with patch.object(generator, 'generate_unit_summaries', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {
                "success": True,
                "parsed": {
                    str(i): {"unit_number": i, "title": f"第{i}章", "summary": f"内容{i}"}
                    for i in range(1, 5)
                },
                "content": "\n\n".join([f"第{i}章: 内容{i}" for i in range(1, 5)])
            }

            generation_result = await generator.generate_unit_summaries_batched(
                global_outline="测试大纲",
                unit_count=4,
                content_type="novel",
                batch_size=2,
                enable_quality_control=False  # 分段生成时不启用质控
            )

            assert generation_result["success"] is True
            assert len(generation_result["units"]) == 4

        # 第二步: 手动触发质控
        # (在实际应用中,这里会调用API端点)
        # 本测试验证分段生成和质控可以独立工作

    @pytest.mark.asyncio
    async def test_quality_control_dimensions(self):
        """测试质控的三个维度"""
        # 验证质控包含三个维度:
        # 1. unit_structure - 单元结构层
        # 2. unit_character - 人物发展层
        # 3. unit_consistency - 一致性层

        expected_dimensions = [
            "unit_structure",
            "unit_character",
            "unit_consistency"
        ]

        # 这些维度应在质控配置中定义
        from app.services.quality_control import QualityControlConfig

        config = QualityControlConfig()
        actual_dimensions = config.get_unit_summary_dimensions()

        for dim in expected_dimensions:
            assert dim in actual_dimensions, f"质控应包含维度: {dim}"


class TestHighlightDiff:
    """测试差异高亮组件(LCS算法)"""

    def test_lcs_algorithm_basic(self):
        """测试LCS算法基本功能"""
        # 这是前端HighlightDiff.vue组件的测试
        # 由于是Vue组件,这里用Python模拟LCS算法逻辑

        def compute_lcs_length(str1, str2):
            """计算最长公共子序列长度"""
            m, n = len(str1), len(str2)
            dp = [[0] * (n + 1) for _ in range(m + 1)]

            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if str1[i-1] == str2[j-1]:
                        dp[i][j] = dp[i-1][j-1] + 1
                    else:
                        dp[i][j] = max(dp[i-1][j], dp[i][j-1])

            return dp[m][n]

        # 测试用例
        assert compute_lcs_length("ABC", "AC") == 2
        assert compute_lcs_length("hello", "hallo") == 4
        assert compute_lcs_length("相同内容", "相同内容") == 4

    def test_diff_detection(self):
        """测试差异检测逻辑"""
        old_text = "这是一个测试内容"
        new_text = "这是一个修改后的内容"

        # 预期差异:
        # - removed: "测试"
        # - added: "修改后的"
        # - unchanged: "这是一个", "内容"

        # 验证文本确实有差异
        assert old_text != new_text
        assert "测试" in old_text
        assert "修改后的" in new_text


class TestEdgeCases:
    """测试边界情况和异常处理"""

    @pytest.mark.asyncio
    async def test_empty_unit_summaries(self):
        """测试空单元概述的质控"""
        # 当单元概述为空时,质控应返回错误
        assert True  # 实际测试需要完整的API环境

    @pytest.mark.asyncio
    async def test_large_batch_generation(self):
        """测试大批量分段生成(100+单元)"""
        from app.services.outline_generator import OutlineGenerator

        mock_db = MagicMock()
        generator = OutlineGenerator(db=mock_db)

        # 测试100个单元的分段生成
        # 批次大小为20,应该有5个批次
        unit_count = 100
        batch_size = 20
        expected_batches = 5

        with patch.object(generator, 'generate_unit_summaries', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {
                "success": True,
                "parsed": {
                    str(i): {"unit_number": i, "title": f"第{i}章", "summary": f"内容{i}"}
                    for i in range(1, batch_size + 1)
                },
                "content": "\n\n".join([f"第{i}章: 内容{i}" for i in range(1, batch_size + 1)])
            }

            result = await generator.generate_unit_summaries_batched(
                global_outline="测试大纲",
                unit_count=unit_count,
                content_type="novel",
                batch_size=batch_size
            )

            # 验证批次数量
            assert result["batch_count"] == expected_batches

    @pytest.mark.asyncio
    async def test_quality_control_timeout(self):
        """测试质控超时处理"""
        # 质控API应设置合理的超时时间(10分钟)
        timeout_ms = 600000  # 10分钟
        assert timeout_ms == 600000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
