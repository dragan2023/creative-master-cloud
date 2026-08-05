/**
 * 单元测试：修订流式接口 SSE 解析（全文修订方案）
 *
 * 覆盖：
 *   - event: content 逐块累积并回调完整内容
 *   - event: diff_complete 回调完成事件
 *   - event: error 回调错误
 *   - 数据跨 chunk 拆分时的拼接处理
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('@/utils/authStorage', () => ({
  getToken: () => 'mock-token'
}))

vi.mock('@/config', () => ({
  API_BASE_URL: ''
}))

vi.mock('../src/api/_axios', () => ({
  api: {}
}))

const { revisionApi } = await import('@/api/revision')

/** 将 SSE 文本按指定偏移拆成多个 Uint8Array chunk，模拟网络分包 */
function buildStream(sseText, splitPoints) {
  const encoder = new TextEncoder()
  const bytes = encoder.encode(sseText)
  const chunks = []
  let start = 0
  for (const point of splitPoints) {
    chunks.push(bytes.slice(start, point))
    start = point
  }
  chunks.push(bytes.slice(start))

  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(chunk)
      }
      controller.close()
    }
  })
}

function mockFetchResponse(stream) {
  return {
    ok: true,
    body: {
      getReader: () => stream.getReader()
    }
  }
}

describe('revisionApi.revise - 全文流式解析', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('逐块累积 content，并在 diff_complete 时回调完成事件', async () => {
    const sse = [
      'event: content\ndata: {"text":"第一段"}\n\n',
      'event: content\ndata: {"text":"第二段"}\n\n',
      'event: diff_complete\ndata: {"summary":"已根据用户意见完成修订"}\n\n'
    ].join('')

    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse(buildStream(sse, [25, 60])))
    vi.stubGlobal('fetch', fetchMock)

    const contentCalls = []
    const doneCalls = []
    const errorCalls = []

    const result = await revisionApi.revise(
      158,
      {
        generation_id: 158,
        user_feedback: '分镜太少',
        current_content: '原文',
        module: 'tvc',
        round_number: 1
      },
      (fullContent, chunk) => contentCalls.push({ fullContent, chunk }),
      (event) => doneCalls.push(event),
      (error) => errorCalls.push(error)
    )

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/generate/revision/158/stream')

    // content 回调：先收到“第一段”，再收到完整“第一段第二段”
    expect(contentCalls.length).toBe(2)
    expect(contentCalls[0].fullContent).toBe('第一段')
    expect(contentCalls[0].chunk).toBe('第一段')
    expect(contentCalls[1].fullContent).toBe('第一段第二段')

    // diff_complete 回调
    expect(doneCalls.length).toBe(1)
    expect(doneCalls[0].type).toBe('diff_complete')
    expect(doneCalls[0].data.summary).toBe('已根据用户意见完成修订')

    expect(errorCalls.length).toBe(0)
    expect(result.success).toBe(true)
    expect(result.content).toBe('第一段第二段')
  })

  it('error 事件同时触发 onDone 与 onError', async () => {
    const sse = 'event: error\ndata: {"data":"修订生成失败"}\n\n'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockFetchResponse(buildStream(sse, []))))

    const doneCalls = []
    const errorCalls = []

    await revisionApi.revise(
      158,
      { generation_id: 158, user_feedback: 'x', current_content: 'y', module: 'tvc', round_number: 1 },
      () => {},
      (event) => doneCalls.push(event),
      (error) => errorCalls.push(error)
    )

    expect(doneCalls.length).toBe(1)
    expect(doneCalls[0].type).toBe('error')
    expect(errorCalls.length).toBe(1)
    expect(errorCalls[0].message).toBe('修订生成失败')
  })

  it('HTTP 非 200 时 reject 错误', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: '服务器错误' })
    }))

    await expect(
      revisionApi.revise(158, { generation_id: 158 }, () => {}, () => {}, () => {})
    ).rejects.toThrow('服务器错误')
  })
})
