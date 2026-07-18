/**
 * useProjectList.js - 项目列表管理组合式函数
 *
 * 处理 Index.vue 中项目列表的加载、搜索、排序、筛选、分页和辅助显示函数。
 * 搜索输入 300ms 防抖；筛选/排序变化重置页码后只发一次请求；
 * 通过请求序号丢弃过期响应，组件卸载后取消待执行防抖并不再请求。
 */
import { ref, getCurrentInstance, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'

/** 搜索输入防抖时长（毫秒） */
export const SEARCH_DEBOUNCE_MS = 300

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
  const searchKeyword = ref('')
  const sortBy = ref('updated_at')
  const sortOrder = ref('desc')

  // ==================== 数据加载 ====================

  /** 项目列表加载失败的唯一用户提示（含重试建议）；请求以 silent 模式发出，拦截器不重复弹窗 */
  const LOAD_PROJECTS_FAILED_MESSAGE = '加载项目列表失败，请检查网络后重试'

  /** 请求序号：仅最新序号的响应允许写入状态，旧响应直接丢弃 */
  let latestRequestId = 0
  /** 搜索防抖定时器句柄 */
  let searchDebounceTimer = null
  /** 组件卸载标记：卸载后不再发起任何请求 */
  let isDisposed = false

  async function loadProjects() {
    if (isDisposed) return
    const requestId = ++latestRequestId
    loading.value = true
    try {
      const res = await novelWriterApi.getProjects({
        content_type: filterType.value,
        status: filterStatus.value,
        search: searchKeyword.value.trim() || undefined,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
        page: currentPage.value,
        page_size: pageSize.value
      }, { silent: true })

      if (requestId !== latestRequestId) return

      if (res.success) {
        projects.value = res.data.items
        total.value = res.data.total
      } else {
        ElMessage.error(res.message || LOAD_PROJECTS_FAILED_MESSAGE)
      }
    } catch (error) {
      if (requestId !== latestRequestId) return
      // 取消的请求保持静默（路由切换/组件卸载触发），其余失败仅提示一次
      const isCancelled = error?.cancelled === true || error?.normalized?.cancelled === true
      if (!isCancelled) {
        ElMessage.error(LOAD_PROJECTS_FAILED_MESSAGE)
      }
    } finally {
      if (requestId === latestRequestId) {
        loading.value = false
      }
    }
  }

  // ==================== 搜索 / 筛选 / 排序 ====================

  /** 取消尚未执行的搜索防抖任务 */
  function cancelPendingSearch() {
    if (searchDebounceTimer !== null) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
  }

  /** 重置页码为 1 并发起一次加载 */
  function resetPageAndReload() {
    if (isDisposed) return
    currentPage.value = 1
    loadProjects()
  }

  /** 搜索输入：300ms 防抖，仅保留最后一次输入触发的请求 */
  function onSearchInput() {
    cancelPendingSearch()
    searchDebounceTimer = setTimeout(() => {
      searchDebounceTimer = null
      resetPageAndReload()
    }, SEARCH_DEBOUNCE_MS)
  }

  /** 类型/状态/排序字段变化：取消待执行防抖，立即重置页码并只发一次请求 */
  function onFilterChange() {
    cancelPendingSearch()
    resetPageAndReload()
  }

  /** 切换升降序并立即刷新 */
  function toggleSortOrder() {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
    onFilterChange()
  }

  /** 清理：取消防抖并使全部在途响应过期（组件卸载或测试收尾调用） */
  function dispose() {
    isDisposed = true
    cancelPendingSearch()
    latestRequestId++
  }

  // 组件上下文中自动清理；纯函数环境（单元测试）由调用方显式 dispose
  if (getCurrentInstance()) {
    onBeforeUnmount(dispose)
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
    searchKeyword,
    sortBy,
    sortOrder,
    loadProjects,
    onSearchInput,
    onFilterChange,
    toggleSortOrder,
    dispose,
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
