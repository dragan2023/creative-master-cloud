/**
 * useProjectForm.js - 项目创建/编辑表单管理组合式函数
 *
 * 处理 Index.vue 中项目表单的状态管理和 CRUD 操作
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'
import {
  DEFAULT_NOVEL_CONFIG,
  DEFAULT_SERIES_SCRIPT_CONFIG,
  DEFAULT_MOVIE_SCRIPT_CONFIG,
  updateSeriesDurationByType,
  updateMovieDurationByType
} from '../config/projectFormConfig'

/**
 * @param {Function} loadProjects - 刷新项目列表的回调
 */
export function useProjectForm(loadProjects) {
  const router = useRouter()

  // ==================== 对话框状态 ====================
  const dialogVisible = ref(false)
  const editingProject = ref(null)
  const saving = ref(false)

  // ==================== 表单数据 ====================
  const projectForm = ref({
    title: '',
    content_type: 'novel',
    genre: '',
    novel_config: { ...DEFAULT_NOVEL_CONFIG },
    series_script_config: { ...DEFAULT_SERIES_SCRIPT_CONFIG },
    movie_script_config: { ...DEFAULT_MOVIE_SCRIPT_CONFIG },
    kb_vertical_enabled: false,
    kb_user_specific_enabled: false,
    kb_manual_enabled: false,
    graphrag_enabled: true,
    // v4.2: 继承知识图谱的源项目ID
    inheritKbId: null
  })

  // ==================== 表单方法 ====================

  // 显示创建对话框
  function showCreateDialog() {
    editingProject.value = null
    resetForm()
    dialogVisible.value = true
  }

  // 编辑项目
  function editProject(project) {
    editingProject.value = project
    const contentType = project.content_type || (project.project_type === 'novel' ? 'novel' : 'series_script')

    projectForm.value = {
      title: project.title,
      content_type: contentType,
      genre: project.genre || '',
      novel_config: project.novel_config || { ...DEFAULT_NOVEL_CONFIG },
      series_script_config: project.series_script_config || { ...DEFAULT_SERIES_SCRIPT_CONFIG },
      movie_script_config: project.movie_script_config || { ...DEFAULT_MOVIE_SCRIPT_CONFIG },
      kb_vertical_enabled: project.knowledge_base_config?.kb_vertical_enabled || false,
      kb_user_specific_enabled: project.knowledge_base_config?.kb_user_specific_enabled || false,
      kb_manual_enabled: project.knowledge_base_config?.kb_manual_enabled || false,
      graphrag_enabled: project.knowledge_base_config?.graphrag_enabled !== false,
      // v4.2: 编辑模式下继承来源不可追溯，设为null
      inheritKbId: null
    }

    dialogVisible.value = true
  }

  // 保存项目
  async function saveProject() {
    if (!projectForm.value.title) {
      ElMessage.warning('请输入项目标题')
      return
    }

    saving.value = true
    try {
      const data = {
        title: projectForm.value.title,
        content_type: projectForm.value.content_type,
        genre: projectForm.value.genre,
        novel_config: projectForm.value.content_type === 'novel' ? projectForm.value.novel_config : null,
        series_script_config: projectForm.value.content_type === 'series_script' ? projectForm.value.series_script_config : null,
        movie_script_config: projectForm.value.content_type === 'movie_script' ? projectForm.value.movie_script_config : null,
        // v4.2: 知识图谱继承
        inherit_kb_from_project_id: projectForm.value.inheritKbId || null,
        knowledge_base_config: {
          kb_vertical_enabled: projectForm.value.kb_vertical_enabled,
          kb_user_specific_enabled: projectForm.value.kb_user_specific_enabled,
          kb_manual_enabled: projectForm.value.kb_manual_enabled,
          graphrag_enabled: projectForm.value.graphrag_enabled,
          kb_vertical_ids: [],
          kb_user_specific_ids: [],
          kb_manual_ids: []
        }
      }

      if (editingProject.value) {
        await novelWriterApi.updateProject(editingProject.value.id, data)
        ElMessage.success('项目已更新')
        dialogVisible.value = false
        loadProjects()
      } else {
        const res = await novelWriterApi.createProject(data)
        ElMessage.success('项目创建成功')
        dialogVisible.value = false
        await loadProjects()
        router.push(`/novel-writer/${res.data.id}`)
      }
    } catch (error) {
      ElMessage.error(editingProject.value ? '更新失败' : '创建失败')
    } finally {
      saving.value = false
    }
  }

  // 删除项目
  async function deleteProject(project) {
    try {
      await ElMessageBox.confirm(
        `确定要删除项目"${project.title}"吗？删除后无法恢复。`,
        '确认删除',
        { type: 'warning' }
      )

      await novelWriterApi.deleteProject(project.id)
      ElMessage.success('项目已删除')
      loadProjects()
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('删除失败')
      }
    }
  }

  // 内容类型变更处理
  function onContentTypeChange(contentType) {
    if (contentType === 'novel') {
      projectForm.value.novel_config = { ...DEFAULT_NOVEL_CONFIG }
    } else if (contentType === 'series_script') {
      projectForm.value.series_script_config = { ...DEFAULT_SERIES_SCRIPT_CONFIG }
      updateSeriesDurationByType(projectForm.value, projectForm.value.series_script_config.series_type)
    } else if (contentType === 'movie_script') {
      projectForm.value.movie_script_config = { ...DEFAULT_MOVIE_SCRIPT_CONFIG }
      updateMovieDurationByType(projectForm.value, projectForm.value.movie_script_config.movie_type)
    }
  }

  // 重置表单
  function resetForm() {
    projectForm.value = {
      title: '',
      content_type: 'novel',
      genre: '',
      novel_config: { ...DEFAULT_NOVEL_CONFIG },
      series_script_config: { ...DEFAULT_SERIES_SCRIPT_CONFIG },
      movie_script_config: { ...DEFAULT_MOVIE_SCRIPT_CONFIG },
      kb_vertical_enabled: false,
      kb_user_specific_enabled: false,
      kb_manual_enabled: false,
      graphrag_enabled: true,
      inheritKbId: null
    }
  }

  return {
    dialogVisible,
    editingProject,
    saving,
    projectForm,
    showCreateDialog,
    editProject,
    saveProject,
    deleteProject,
    onContentTypeChange,
    resetForm
  }
}
