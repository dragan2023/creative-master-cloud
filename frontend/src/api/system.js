/**
 * systemApi - API 模块
 */
import { api } from './_axios'

export const systemApi = {
  // 退出程序
  exit: () => api.post('/api/v1/system/exit')
}
