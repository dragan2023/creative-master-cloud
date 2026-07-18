/**
 * useProjectList 搜索防抖 / 页码重置 / 竞态与卸载清理测试
 *
 * 覆盖验收场景：
 * - 299ms 不请求、300ms 恰好一次
 * - 连续输入只保留最后一次搜索
 * - 筛选 / 排序变化把页码重置为 1 且只发一次请求
 * - 过期响应不得覆盖新响应
 * - 卸载（dispose）后不再请求
 * - 列表加载失败 ElMessage.error 总调用次数严格等于 1，取消请求零提示
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const getProjectsMock = vi.hoisted(() => vi.fn())
const elMessageErrorMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/novel-writer', () => ({
  novelWriterApi: { getProjects: getProjectsMock }
}))

vi.mock('element-plus', () => ({
  ElMessage: { error: elMessageErrorMock }
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() })
}))

import { useProjectList, SEARCH_DEBOUNCE_MS } from '../useProjectList'

/** 构造成功响应载荷 */
function buildSuccessResponse(items = [], total = items.length) {
  return { success: true, data: { items, total } }
}

beforeEach(() => {
  vi.useFakeTimers()
  getProjectsMock.mockReset()
  elMessageErrorMock.mockReset()
  getProjectsMock.mockResolvedValue(buildSuccessResponse())
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useProjectList 搜索防抖', () => {
  it('should_not_request_before_300ms_debounce_window', () => {
    const list = useProjectList()
    list.searchKeyword.value = '修真'
    list.onSearchInput()

    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS - 1)

    expect(getProjectsMock).not.toHaveBeenCalled()
    list.dispose()
  })

  it('should_request_exactly_once_at_300ms', () => {
    const list = useProjectList()
    list.searchKeyword.value = '修真'
    list.onSearchInput()

    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS)

    expect(getProjectsMock).toHaveBeenCalledTimes(1)
    expect(getProjectsMock.mock.calls[0][0].search).toBe('修真')
    expect(getProjectsMock.mock.calls[0][1]).toEqual({ silent: true })
    list.dispose()
  })

  it('should_keep_only_last_search_when_typing_continuously', () => {
    const list = useProjectList()

    list.searchKeyword.value = '修'
    list.onSearchInput()
    vi.advanceTimersByTime(200)

    list.searchKeyword.value = '修真'
    list.onSearchInput()
    vi.advanceTimersByTime(200)

    list.searchKeyword.value = '修真世'
    list.onSearchInput()
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS)

    expect(getProjectsMock).toHaveBeenCalledTimes(1)
    expect(getProjectsMock.mock.calls[0][0].search).toBe('修真世')
    list.dispose()
  })

  it('should_reset_page_to_first_when_search_fires', () => {
    const list = useProjectList()
    list.currentPage.value = 3

    list.searchKeyword.value = '悬疑'
    list.onSearchInput()
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS)

    expect(list.currentPage.value).toBe(1)
    expect(getProjectsMock.mock.calls[0][0].page).toBe(1)
    list.dispose()
  })
})

describe('useProjectList 筛选与排序', () => {
  it('should_reset_page_and_request_once_when_filter_changes', () => {
    const list = useProjectList()
    list.currentPage.value = 5
    list.filterType.value = 'novel'

    list.onFilterChange()

    expect(list.currentPage.value).toBe(1)
    expect(getProjectsMock).toHaveBeenCalledTimes(1)
    expect(getProjectsMock.mock.calls[0][0].content_type).toBe('novel')
    list.dispose()
  })

  it('should_cancel_pending_search_when_filter_changes', () => {
    const list = useProjectList()
    list.onSearchInput()

    list.onFilterChange()
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS * 2)

    // 防抖任务已被取消：仅 onFilterChange 触发的一次请求
    expect(getProjectsMock).toHaveBeenCalledTimes(1)
    list.dispose()
  })

  it('should_toggle_sort_order_and_reset_page', () => {
    const list = useProjectList()
    list.currentPage.value = 2

    list.toggleSortOrder()

    expect(list.sortOrder.value).toBe('asc')
    expect(list.currentPage.value).toBe(1)
    expect(getProjectsMock).toHaveBeenCalledTimes(1)
    expect(getProjectsMock.mock.calls[0][0].sort_order).toBe('asc')

    list.toggleSortOrder()
    expect(list.sortOrder.value).toBe('desc')
    expect(getProjectsMock).toHaveBeenCalledTimes(2)
    list.dispose()
  })
})

describe('useProjectList 竞态与卸载清理', () => {
  it('should_ignore_stale_response_arriving_after_newer_one', async () => {
    let resolveStale
    const staleResponse = new Promise((resolve) => { resolveStale = resolve })
    getProjectsMock
      .mockReturnValueOnce(staleResponse)
      .mockResolvedValueOnce(buildSuccessResponse([{ id: 2, title: '新结果' }]))

    const list = useProjectList()
    const stalePromise = list.loadProjects()
    const freshPromise = list.loadProjects()
    await freshPromise

    expect(list.projects.value.map(p => p.id)).toEqual([2])

    // 旧请求晚于新请求返回：不得覆盖新结果
    resolveStale(buildSuccessResponse([{ id: 1, title: '旧结果' }]))
    await stalePromise

    expect(list.projects.value.map(p => p.id)).toEqual([2])
    expect(list.loading.value).toBe(false)
    list.dispose()
  })

  it('should_not_request_after_dispose_even_if_timer_fires', () => {
    const list = useProjectList()
    list.onSearchInput()

    list.dispose()
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS * 2)

    expect(getProjectsMock).not.toHaveBeenCalled()
  })

  it('should_not_apply_inflight_response_after_dispose', async () => {
    let resolveInflight
    getProjectsMock.mockReturnValueOnce(
      new Promise((resolve) => { resolveInflight = resolve })
    )

    const list = useProjectList()
    const inflight = list.loadProjects()

    list.dispose()
    resolveInflight(buildSuccessResponse([{ id: 9, title: '迟到结果' }]))
    await inflight

    expect(list.projects.value).toEqual([])
  })
})

describe('useProjectList 失败提示所有权', () => {
  it('should_show_error_message_exactly_once_when_request_fails', async () => {
    getProjectsMock.mockRejectedValueOnce({
      normalized: { status: 500, message: '服务器内部错误', notify: false, cancelled: false }
    })

    const list = useProjectList()
    await list.loadProjects()

    expect(elMessageErrorMock).toHaveBeenCalledTimes(1)
    expect(elMessageErrorMock).toHaveBeenCalledWith('加载项目列表失败，请检查网络后重试')
    list.dispose()
  })

  it('should_show_error_message_exactly_once_for_business_failure', async () => {
    getProjectsMock.mockResolvedValueOnce({ success: false, message: '查询失败' })

    const list = useProjectList()
    await list.loadProjects()

    expect(elMessageErrorMock).toHaveBeenCalledTimes(1)
    expect(elMessageErrorMock).toHaveBeenCalledWith('查询失败')
    list.dispose()
  })

  it('should_stay_silent_when_request_is_cancelled', async () => {
    getProjectsMock.mockRejectedValueOnce({
      cancelled: true,
      normalized: { cancelled: true, notify: false, message: 'canceled' }
    })

    const list = useProjectList()
    await list.loadProjects()

    expect(elMessageErrorMock).not.toHaveBeenCalled()
    list.dispose()
  })
})
