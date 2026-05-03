/**
 * updateApi - API 模块
 */
import { api } from './_axios'

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
