/**
 * API 入口 - 重新导出所有领域模块
 */

export { api } from './_axios'

export { authApi } from './auth'
export { apiKeyApi } from './api-key'
export { generateApi } from './generate'
export { knowledgeApi } from './knowledge'
export { historyApi } from './history'
export { actionApi } from './action'
export { userConfigApi } from './user-config'
export { updateApi } from './update'
export { systemApi } from './system'
export { mcpApi } from './mcp'
export { novelWriterApi } from './novel-writer'
export { revisionApi } from './revision'
export { qualityControlApi } from './quality-control'
export { globalOutlineQCApi } from './quality-control'
export { unitSummariesQCApi } from './quality-control'

// 保持向后兼容 - default export 为 api 实例
import { api } from './_axios'
export default api
