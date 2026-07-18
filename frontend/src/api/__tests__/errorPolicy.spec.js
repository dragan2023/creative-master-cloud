/**
 * API 错误策略纯函数测试
 *
 * 验证 normalizeApiError 对各类错误的规范化结果：
 * 状态码、用户消息、是否全局提示（notify）、是否为取消（cancelled）。
 */
import { describe, it, expect } from 'vitest'
import { normalizeApiError } from '../errorPolicy'

/** 构造 Axios 风格错误对象 */
function buildAxiosError({ status, detail, config = {}, message } = {}) {
  return {
    response: status !== undefined ? { status, data: { detail } } : undefined,
    config,
    message
  }
}

describe('normalizeApiError', () => {
  it('should_keep_silent_for_401_and_let_router_handle_auth', () => {
    const result = normalizeApiError(
      buildAxiosError({ status: 401, detail: '未授权' })
    )
    expect(result.status).toBe(401)
    expect(result.notify).toBe(false)
    expect(result.cancelled).toBe(false)
  })

  it('should_keep_silent_and_mark_cancelled_for_499', () => {
    const result = normalizeApiError(
      buildAxiosError({ status: 499, detail: '请求被取消' })
    )
    expect(result.status).toBe(499)
    expect(result.notify).toBe(false)
    expect(result.cancelled).toBe(true)
  })

  it('should_keep_silent_and_mark_cancelled_for_local_abort_without_response', () => {
    // AbortController 本地取消：无 HTTP 响应，仅有 code: 'ERR_CANCELED'
    const result = normalizeApiError({ code: 'ERR_CANCELED', message: 'canceled', config: {} })
    expect(result.status).toBeUndefined()
    expect(result.notify).toBe(false)
    expect(result.cancelled).toBe(true)
  })

  it('should_render_field_paths_for_422_array_detail', () => {
    const detail = [
      { loc: ['body', 'title'], msg: '标题不能为空' },
      { loc: ['body', 'word_count'], msg: '必须为正整数' }
    ]
    const result = normalizeApiError(buildAxiosError({ status: 422, detail }))
    expect(result.notify).toBe(true)
    expect(result.message).toContain('参数校验失败')
    expect(result.message).toContain('body.title : 标题不能为空')
    expect(result.message).toContain('body.word_count : 必须为正整数')
  })

  it('should_use_placeholder_when_422_item_has_no_loc', () => {
    const detail = [{ msg: '未知字段错误' }]
    const result = normalizeApiError(buildAxiosError({ status: 422, detail }))
    expect(result.message).toContain('? : 未知字段错误')
  })

  it('should_not_notify_when_request_config_is_silent', () => {
    const result = normalizeApiError(
      buildAxiosError({ status: 500, detail: '服务器内部错误', config: { silent: true } })
    )
    expect(result.status).toBe(500)
    expect(result.message).toBe('服务器内部错误')
    expect(result.notify).toBe(false)
  })

  it('should_notify_string_detail_for_common_business_error', () => {
    const result = normalizeApiError(
      buildAxiosError({ status: 400, detail: '知识库不存在' })
    )
    expect(result.notify).toBe(true)
    expect(result.message).toBe('知识库不存在')
  })

  it('should_fallback_to_unified_message_for_network_error', () => {
    // 网络错误：无 response，仅有 axios message
    const result = normalizeApiError({ config: {}, message: 'Network Error' })
    expect(result.status).toBeUndefined()
    expect(result.notify).toBe(true)
    expect(result.message).toBe('Network Error')
  })

  it('should_use_default_text_when_no_detail_and_no_message', () => {
    const result = normalizeApiError({ config: {} })
    expect(result.message).toBe('请求失败')
    expect(result.notify).toBe(true)
  })
})
