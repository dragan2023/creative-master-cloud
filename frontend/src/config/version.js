/**
 * 版本号配置
 * 
 * 此文件由 version-bump.py 脚本自动更新
 * 构建时通过 Vite 的 define 注入 __APP_VERSION__ 全局常量
 */

// 当前应用版本号（构建时从 version.json 动态注入）
// __APP_VERSION__ 由 vite.config.js 在构建时定义
export const APP_VERSION = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '3.1.5'

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
