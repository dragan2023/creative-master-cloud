import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiKeyApi } from '@/api'

export const useApiKeyStore = defineStore('apiKey', () => {
  const apiKeys = ref([])
  const defaultKey = ref(null)
  const loading = ref(false)

  // 获取API Key列表
  async function fetchApiKeys() {
    loading.value = true
    try {
      const res = await apiKeyApi.list()
      // 后端返回 {code, message, data} 结构
      apiKeys.value = res.data || []
      defaultKey.value = apiKeys.value.find(k => k.is_default) || null
    } finally {
      loading.value = false
    }
  }

  // 添加API Key
  async function addApiKey(data) {
    const res = await apiKeyApi.create(data)
    await fetchApiKeys()
    return res
  }

  // 删除API Key
  async function removeApiKey(id) {
    await apiKeyApi.delete(id)
    await fetchApiKeys()
  }

  // 设置默认Key
  async function setDefaultKey(id) {
    await apiKeyApi.setDefault(id)
    await fetchApiKeys()
  }

  // 获取默认Key的提供商
  function getDefaultProvider() {
    return defaultKey.value?.provider || null
  }

  // 获取默认Key的模型
  function getDefaultModel() {
    return defaultKey.value?.model_name || null
  }

  return {
    apiKeys,
    defaultKey,
    loading,
    fetchApiKeys,
    addApiKey,
    removeApiKey,
    setDefaultKey,
    getDefaultProvider,
    getDefaultModel
  }
})
