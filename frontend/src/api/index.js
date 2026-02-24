import axios from 'axios'
import { API_BASE_URL } from '@/config'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'

// 创建axios实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 1800000, // 30分钟超时，用于大文件上传和文档处理
  maxContentLength: 200 * 1024 * 1024, // 200MB
  maxBodyLength: 200 * 1024 * 1024, // 200MB
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.detail || '请求失败'
    
    if (status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      ElMessage.error('登录已过期，请重新登录')
    } else {
      ElMessage.error(message)
    }
    
    return Promise.reject(error)
  }
)

// 认证API
export const authApi = {
  register: (data) => api.post('/api/v1/auth/register', data),
  login: (data) => api.post('/api/v1/auth/login', data),
  getProfile: () => api.get('/api/v1/auth/me'),
  updateProfile: (data) => api.put('/api/v1/auth/me', data)
}

// API Key管理
export const apiKeyApi = {
  list: () => api.get('/api/v1/auth/api-keys'),
  create: (data) => api.post('/api/v1/auth/api-keys', data),
  delete: (id) => api.delete(`/api/v1/auth/api-keys/${id}`),
  setDefault: (id) => api.put(`/api/v1/auth/api-keys/${id}/default`),
  // 测试新添加的API Key（添加时调用）
  test: (data) => api.post('/api/v1/auth/api-keys/test', data),
  // 测试已保存的API Key（列表中调用）
  testSaved: (id) => api.post(`/api/v1/auth/api-keys/${id}/test`)
}

// 创意生成API
export const generateApi = {
  // 短视频脚本
  shortVideo: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/short-video/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 剧本大纲
  script: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/script/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 小说大纲
  novel: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/novel/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 平面广告
  printAd: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/print-ad/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // TVC广告
  tvc: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/tvc/stream', data, onMessage, onWorkflow, onStreamStart, sessionId)
}

// SSE流式生成
function streamGenerate(endpoint, data, onMessage, onWorkflow, onStreamStart, sessionId) {
  return new Promise((resolve, reject) => {
    const userStore = useUserStore()
    
    // 构建 URL 查询参数
    const params = new URLSearchParams()
    
    // 如果提供了sessionId，添加到参数中
    if (sessionId) {
      params.append('session_id', sessionId)
    }
    
    // 复制 data 对象，避免修改原始对象
    const requestBody = { ...data }
    
    // 从 requestBody 中提取 enable_knowledge 并作为查询参数传递
    // 后端期望这个参数在 URL 查询参数中，而不是请求体中
    if (requestBody.enable_knowledge !== undefined) {
      params.append('enable_knowledge', requestBody.enable_knowledge)
      // 从请求体中移除，避免重复
      delete requestBody.enable_knowledge
    }
    
    // 构建完整 URL
    let url = `${API_BASE_URL}${endpoint}`
    const paramString = params.toString()
    if (paramString) {
      url += `?${paramString}`
    }
    
    console.log('[API] Request URL:', url)  // 调试日志
    
    // 使用 POST 请求发送 JSON 数据
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userStore.token}`
      },
      body: JSON.stringify(requestBody)
    }).then(response => {
      // 检查 HTTP 状态码
      if (!response.ok) {
        // 尝试解析错误信息
        response.json().then(errData => {
          const errorMsg = errData?.detail || `请求失败: ${response.status}`
          reject(new Error(errorMsg))
        }).catch(() => {
          reject(new Error(`请求失败: ${response.status}`))
        })
        return
      }
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''
      let generationId = null
      let currentEventType = ''
      let durationMs = null
      
      // 创建一个可中断的对象
      const abortController = {
        reader,
        abort: () => {
          reader.cancel()
        }
      }
      
      // 通知外部可以中断
      if (onStreamStart) {
        onStreamStart(abortController)
      }
      
      function readChunk() {
        reader.read().then(({ done, value }) => {
          if (done) {
            resolve({ content: fullContent, generation_id: generationId, duration_ms: durationMs })
            return
          }
          
          const text = decoder.decode(value, { stream: true })
          const lines = text.split('\n')
          
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEventType = line.slice(7).trim()
              continue
            }
            if (line.startsWith('data: ')) {
              try {
                const jsonStr = line.slice(6)
                if (jsonStr.trim()) {
                  const eventData = JSON.parse(jsonStr)
                  
                  // 处理 workflow 事件
                  if (currentEventType === 'workflow' && onWorkflow) {
                    onWorkflow(eventData)
                  }
                  
                  // 处理 done 事件 - 获取耗时
                  if (currentEventType === 'done') {
                    if (eventData.duration_ms) {
                      durationMs = eventData.duration_ms
                    }
                    if (eventData.generation_id) {
                      generationId = eventData.generation_id
                    }
                  }
                  
                  // 处理 content 事件
                  if (eventData.text) {
                    fullContent += eventData.text
                    onMessage(fullContent, eventData.text)
                  }
                  if (eventData.generation_id) {
                    generationId = eventData.generation_id
                  }
                }
              } catch (e) {
                // 忽略解析错误
              }
            }
          }
          
          readChunk()
        })
      }
      
      readChunk()
    }).catch(error => {
      reject(error)
    })
  })
}

// 知识库API
export const knowledgeApi = {
  list: (params) => api.get('/api/v1/knowledge', { params }),
  upload: (formData) => api.post('/api/v1/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  update: (id, data) => api.put(`/api/v1/knowledge/${id}`, data),
  delete: (id) => api.delete(`/api/v1/knowledge/${id}`),
  getProgress: (id) => api.get(`/api/v1/knowledge/${id}/progress`),
  getAllProcessing: () => api.get('/api/v1/knowledge/processing/all'),
  stopProcessing: (id) => api.post(`/api/v1/knowledge/${id}/stop`),
  getGraph: (id, maxNodes = 100) => api.get(`/api/v1/knowledge/${id}/graph`, { params: { max_nodes: maxNodes } }),
  getGlobalGraph: (maxNodes = 100) => api.get('/api/v1/knowledge/graph/global', { params: { max_nodes: maxNodes } })
}

// 历史记录API
export const historyApi = {
  list: (params) => api.get('/api/v1/generate/history', { params }),
  get: (id) => api.get(`/api/v1/generate/history/${id}`),
  delete: (id) => api.delete(`/api/v1/generate/history/${id}`)
}

// 用户行为追踪API
export const actionApi = {
  // 记录行为
  track: (data) => api.post('/api/v1/generate/action', data),
  // 获取行为统计
  getStats: () => api.get('/api/v1/generate/action/stats')
}

// 用户个人配置API（普通用户可用）
export const userConfigApi = {
  // 代理配置（用户级别）
  getProxyConfig: () => api.get('/api/v1/auth/config/proxy'),
  setProxyConfig: (data) => api.post('/api/v1/auth/config/proxy', data),
  testProxy: () => api.post('/api/v1/auth/config/proxy/test'),

  // 文档预处理配置（用户级别）
  getPreprocessorConfig: () => api.get('/api/v1/auth/config/preprocessor'),
  setPreprocessorConfig: (data) => api.post('/api/v1/auth/config/preprocessor', data)
}

// 软件更新API
export const updateApi = {
  // 检查更新
  check: (currentVersion) => api.post('/api/v1/update/check', { current_version: currentVersion, platform: 'windows' }),
  // 获取下载信息
  getDownloadInfo: () => api.get('/api/v1/update/download'),
  // 获取更新日志
  getChangelog: () => api.get('/api/v1/update/changelog'),
  // 获取当前版本
  getCurrentVersion: () => api.get('/api/v1/update/current-version')
}

export default api
