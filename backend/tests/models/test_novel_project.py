"""NovelProject 模型业务方法测试"""
import pytest
from app.models.novel_project import NovelProject, ProjectType, ProjectStatus


class TestNovelProjectModel:
    """NovelProject 模型业务方法测试"""
    
    # ==================== 生成任务状态管理测试 ====================
    
    def test_mark_generation_started(self):
        project = NovelProject()
        project.generation_task_status = None
        project.mark_generation_started()
        assert project.generation_task_status == "running"
    
    def test_mark_generation_completed(self):
        project = NovelProject()
        project.generation_task_status = "running"
        project.mark_generation_completed()
        assert project.generation_task_status == "completed"
    
    def test_mark_generation_failed(self):
        project = NovelProject()
        project.generation_task_status = "running"
        project.mark_generation_failed("生成失败原因")
        assert project.generation_task_status == "failed"
        assert project.error_message == "生成失败原因"
    
    def test_mark_generation_failed_no_message(self):
        project = NovelProject()
        project.mark_generation_failed()
        assert project.generation_task_status == "failed"
        assert project.error_message is None
    
    def test_is_generation_running_true(self):
        project = NovelProject()
        project.generation_task_status = "running"
        assert project.is_generation_running() is True
    
    def test_is_generation_running_false(self):
        project = NovelProject()
        project.generation_task_status = "completed"
        assert project.is_generation_running() is False
    
    def test_is_generation_completed_true(self):
        project = NovelProject()
        project.generation_task_status = "completed"
        assert project.is_generation_completed() is True
    
    def test_is_generation_completed_false(self):
        project = NovelProject()
        project.generation_task_status = "running"
        assert project.is_generation_completed() is False
    
    def test_is_generation_failed_true(self):
        project = NovelProject()
        project.generation_task_status = "failed"
        assert project.is_generation_failed() is True
    
    def test_is_generation_failed_false(self):
        project = NovelProject()
        project.generation_task_status = "running"
        assert project.is_generation_failed() is False
    
    # ==================== 知识库状态管理测试 ====================
    
    def test_mark_kb_ready(self):
        project = NovelProject()
        project.kb_status = "building"
        project.mark_kb_ready()
        assert project.kb_status == "ready"
    
    def test_mark_kb_building(self):
        project = NovelProject()
        project.kb_status = "pending"
        project.mark_kb_building()
        assert project.kb_status == "building"
    
    def test_mark_kb_failed(self):
        project = NovelProject()
        project.kb_status = "building"
        project.mark_kb_failed()
        assert project.kb_status == "failed"
    
    def test_is_kb_ready_true(self):
        project = NovelProject()
        project.kb_status = "ready"
        assert project.is_kb_ready() is True
    
    def test_is_kb_ready_false(self):
        project = NovelProject()
        project.kb_status = "building"
        assert project.is_kb_ready() is False
    
    def test_is_kb_building_true(self):
        project = NovelProject()
        project.kb_status = "building"
        assert project.is_kb_building() is True
    
    def test_is_kb_failed_true(self):
        project = NovelProject()
        project.kb_status = "failed"
        assert project.is_kb_failed() is True
    
    # ==================== 风格分析状态管理测试 ====================
    
    def test_is_style_analysis_pending_true(self):
        project = NovelProject()
        project.style_analysis_status = "pending"
        assert project.is_style_analysis_pending() is True
    
    def test_is_style_analysis_running_true(self):
        project = NovelProject()
        project.style_analysis_status = "analyzing"
        assert project.is_style_analysis_running() is True
    
    def test_is_style_analysis_completed_true(self):
        project = NovelProject()
        project.style_analysis_status = "completed"
        assert project.is_style_analysis_completed() is True
    
    def test_is_style_analysis_failed_true(self):
        project = NovelProject()
        project.style_analysis_status = "failed"
        assert project.is_style_analysis_failed() is True
    
    def test_mark_style_analysis_started(self):
        project = NovelProject()
        project.style_analysis_status = "pending"
        project.mark_style_analysis_started()
        assert project.style_analysis_status == "analyzing"
    
    def test_mark_style_analysis_completed(self):
        project = NovelProject()
        project.style_analysis_status = "analyzing"
        project.mark_style_analysis_completed()
        assert project.style_analysis_status == "completed"
    
    def test_mark_style_analysis_failed(self):
        project = NovelProject()
        project.style_analysis_status = "analyzing"
        project.mark_style_analysis_failed("分析失败原因")
        assert project.style_analysis_status == "failed"
        assert project.style_analysis_error == "分析失败原因"
    
    # ==================== 业务流程检查测试 ====================
    
    def test_can_start_writing_true(self):
        project = NovelProject()
        project.outline_content = "有大纲内容"
        assert project.can_start_writing() is True
    
    def test_can_start_writing_false(self):
        project = NovelProject()
        project.outline_content = None
        assert project.can_start_writing() is False
    
    def test_can_start_writing_empty(self):
        project = NovelProject()
        project.outline_content = ""
        assert project.can_start_writing() is False  # 空字符串被视为无效值

    def test_can_start_writing_whitespace_only(self):
        """仅空白字符的大纲必须被拒绝"""
        project = NovelProject()
        project.outline_content = "   \n\t  "
        assert project.can_start_writing() is False

    def test_restart_after_failure_then_start_clears_error(self):
        """失败后允许重启，重新开始后不得遗留上一次失败信息"""
        project = NovelProject()
        project.mark_generation_failed("上次失败原因")
        assert project.can_restart_generation() is True
        project.mark_generation_started()
        assert project.generation_task_status == "running"
        assert project.error_message is None

    def test_completion_clears_previous_error(self):
        """生成成功后必须清除上一次失败信息"""
        project = NovelProject()
        project.mark_generation_failed("上次失败原因")
        project.mark_generation_completed()
        assert project.generation_task_status == "completed"
        assert project.error_message is None
    
    def test_can_restart_generation_pending(self):
        project = NovelProject()
        project.generation_task_status = "pending"
        assert project.can_restart_generation() is True
    
    def test_can_restart_generation_failed(self):
        project = NovelProject()
        project.generation_task_status = "failed"
        assert project.can_restart_generation() is True
    
    def test_can_restart_generation_completed(self):
        project = NovelProject()
        project.generation_task_status = "completed"
        assert project.can_restart_generation() is True
    
    def test_can_restart_generation_none(self):
        project = NovelProject()
        project.generation_task_status = None
        assert project.can_restart_generation() is True
    
    def test_can_restart_generation_running(self):
        project = NovelProject()
        project.generation_task_status = "running"
        assert project.can_restart_generation() is False
    
    # ==================== 其他方法测试 ====================
    
    def test_get_progress_percentage_zero(self):
        project = NovelProject()
        project.total_chapters = 0
        project.completed_chapters = 0
        assert project.get_progress_percentage() == 0.0
    
    def test_get_progress_percentage_50(self):
        project = NovelProject()
        project.total_chapters = 10
        project.completed_chapters = 5
        assert project.get_progress_percentage() == 50.0
    
    def test_get_progress_percentage_100(self):
        project = NovelProject()
        project.total_chapters = 10
        project.completed_chapters = 10
        assert project.get_progress_percentage() == 100.0
    
    def test_repr(self):
        project = NovelProject()
        project.id = 1
        project.title = "测试项目"
        project.project_type = ProjectType.NOVEL
        project.status = ProjectStatus.INIT
        repr_str = repr(project)
        assert "NovelProject" in repr_str
        assert "测试项目" in repr_str
