/**
 * useConfigPersistence - 用户配置持久化工具
 *
 * 提供统一的 localStorage 持久化能力，用于保存和恢复用户在各模块中的配置选择。
 * 特性：
 * - 版本兼容：内置版本号，应用更新时可自动清理旧格式数据
 * - 安全过滤：支持排除敏感字段（如 API Key）
 * - 自动过期：可配置过期时间，默认 7 天
 *
 * 使用方式：
 *   const { saveConfig, restoreConfig, removeConfig } = useConfigPersistence()
 *   saveConfig('my_config_key', { option1: 'value1' })  // 保存
 *   const saved = restoreConfig('my_config_key')         // 恢复
 *   removeConfig('my_config_key')                        // 清除
 */

/** 当前持久化格式版本 - 变更此值会触发旧数据自动清理 */
const CONFIG_VERSION = 1

/** 默认过期时间：7 天 */
const DEFAULT_EXPIRE_MS = 7 * 24 * 60 * 60 * 1000

export function useConfigPersistence() {
  /**
   * 保存配置到 localStorage
   * @param {string} key - 存储键名
   * @param {*} data - 要保存的配置数据
   * @param {Object} [options] - 可选配置
   * @param {string[]} [options.excludeKeys] - 要排除的顶层字段名（如 ['api_key']）
   * @param {number} [options.expireMs] - 过期时间（毫秒），默认 7 天
   */
  function saveConfig(key, data, options = {}) {
    try {
      let dataToSave = data

      // 过滤敏感字段
      if (options.excludeKeys && options.excludeKeys.length > 0) {
        dataToSave = { ...data }
        for (const field of options.excludeKeys) {
          delete dataToSave[field]
        }
      }

      const payload = {
        version: CONFIG_VERSION,
        timestamp: Date.now(),
        data: dataToSave,
      }
      localStorage.setItem(key, JSON.stringify(payload))
    } catch (e) {
      console.warn('[ConfigPersistence] 保存配置失败:', key, e)
    }
  }

  /**
   * 从 localStorage 恢复配置
   * @param {string} key - 存储键名
   * @param {Object} [options] - 可选配置
   * @param {number} [options.expireMs] - 过期时间（毫秒），默认 7 天
   * @returns {*|null} 恢复的配置数据，若不存在/已过期/版本不兼容则返回 null
   */
  function restoreConfig(key, options = {}) {
    try {
      const raw = localStorage.getItem(key)
      if (!raw) return null

      const payload = JSON.parse(raw)

      // 版本不兼容 → 清理并返回 null
      if (payload.version !== CONFIG_VERSION) {
        localStorage.removeItem(key)
        console.log('[ConfigPersistence] 配置版本已更新，旧数据已清理:', key)
        return null
      }

      // 过期检查
      const expireMs = options.expireMs ?? DEFAULT_EXPIRE_MS
      if (payload.timestamp && Date.now() - payload.timestamp > expireMs) {
        localStorage.removeItem(key)
        console.log('[ConfigPersistence] 配置已过期，已清理:', key)
        return null
      }

      return payload.data
    } catch (e) {
      console.warn('[ConfigPersistence] 恢复配置失败:', key, e)
      localStorage.removeItem(key)
      return null
    }
  }

  /**
   * 清除指定配置
   * @param {string} key - 存储键名
   */
  function removeConfig(key) {
    try {
      localStorage.removeItem(key)
    } catch (e) {
      console.warn('[ConfigPersistence] 清除配置失败:', key, e)
    }
  }

  return { saveConfig, restoreConfig, removeConfig }
}
