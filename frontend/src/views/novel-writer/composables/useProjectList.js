/**
 * useProjectList.js - 项目列表管理组合式函数
 *
 * 处理 Index.vue 中项目列表的加载、筛选、分页和辅助显示函数
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'

export function useProjectList() {
  const router = useRouter()

  // ==================== 列表状态 ====================
  const projects = ref([])
  const loading = ref(false)
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(12)
  const filterType = ref('')
  const filterStatus = ref('')

  // ==================== 数据加载 ====================

  async function loadProjects() {
    loading.value = true
    try {
      const res = await novelWriterApi.getProjects({
        content_type: filterType.value,
        status: filterStatus.value,
        page: currentPage.value,
        page_size: pageSize.value
      })

      if (res.success) {
        projects.value = res.data.items
        total.value = res.data.total
      } else {
        ElMessage.error(res.message || '加载项目列表失败')
      }
    } catch (error) {
      ElMessage.error('加载项目列表失败')
    } finally {
      loading.value = false
    }
  }

  // ==================== 导航 ====================

  function goToProject(projectId) {
    router.push(`/novel-writer/${projectId}`)
  }

  function goToModelConfig() {
    router.push('/novel-writer/model-config')
  }

  // ==================== 下拉菜单命令处理 ====================

  function handleCommand(command, project, formMethods) {
    if (command === 'edit') {
      formMethods.editProject(project)
    } else if (command === 'delete') {
      formMethods.deleteProject(project)
    }
  }

  // ==================== 辅助函数 ====================

  function getTypeLabel(contentType) {
    const labels = {
      'novel': '小说',
      'series_script': '剧集',
      'movie_script': '电影',
      'script': '剧本'
    }
    return labels[contentType] || '未知'
  }

  function getTypeClass(contentType) {
    const classes = {
      'novel': 'novel',
      'series_script': 'series-script',
      'movie_script': 'movie-script',
      'script': 'script'
    }
    return classes[contentType] || 'novel'
  }

  function getUnitLabel(contentType) {
    const labels = {
      'novel': '章',
      'series_script': '集',
      'movie_script': '场',
      'script': '章'
    }
    return labels[contentType] || '章'
  }

  function getStatusType(status) {
    const types = {
      init: 'info',
      directory: 'warning',
      generating: 'primary',
      completed: 'success',
      failed: 'danger',
      paused: 'warning'
    }
    return types[status] || 'info'
  }

  function getStatusText(status) {
    const texts = {
      init: '初始化',
      directory: '目录生成中',
      generating: '生成中',
      completed: '已完成',
      failed: '失败',
      paused: '已暂停'
    }
    return texts[status] || status
  }

  function getProgressStatus(status) {
    if (status === 'completed') return 'success'
    if (status === 'failed') return 'exception'
    return null
  }

  function formatTime(timeStr) {
    if (!timeStr) return ''
    const date = new Date(timeStr)
    const now = new Date()
    const diff = now - date

    if (diff < 60000) return '刚刚'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`

    return date.toLocaleDateString()
  }

  return {
    projects,
    loading,
    total,
    currentPage,
    pageSize,
    filterType,
    filterStatus,
    loadProjects,
    goToProject,
    goToModelConfig,
    handleCommand,
    getTypeLabel,
    getTypeClass,
    getUnitLabel,
    getStatusType,
    getStatusText,
    getProgressStatus,
    formatTime
  }
}
