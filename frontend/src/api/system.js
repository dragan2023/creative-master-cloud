/**
 * systemApi - API 模块
 */
import { api } from './_axios'

/** 本地桌面运行环境标识（与后端 settings.RUNTIME_ENV 约定一致） */
export const RUNTIME_ENV_LOCAL_DESKTOP = 'local_desktop'

export const systemApi = {
  // 退出程序
  exit: () => api.post('/api/v1/system/exit'),
  // 查询运行环境（local_desktop / server），前端据此决定是否展示退出入口
  getRuntimeEnvironment: () => api.get('/api/v1/system/environment')
}
