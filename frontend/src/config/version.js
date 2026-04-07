/**
 * 版本号配置
 * 
 * 此文件由 version-bump.py 脚本自动更新
 * 请勿手动修改此文件中的版本号
 */

// 当前应用版本号（与 version.json 保持同步）
export const APP_VERSION = '3.1.4'

// 获取版本号的 API 端点
export const VERSION_API = '/api/v1/update/current-version'

/**
 * 获取当前版本号
 * 优先从后端 API 获取，失败时返回本地版本号
 */
export async function fetchCurrentVersion() {
  try {
    const response = await fetch(VERSION_API)
    if (response.ok) {
      const data = await response.json()
      return data.version || APP_VERSION
    }
  } catch (error) {
    console.warn('获取版本号失败，使用本地版本:', error)
  }
  return APP_VERSION
}

export default APP_VERSION
