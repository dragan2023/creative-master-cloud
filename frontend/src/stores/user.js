import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'
import router from '@/router'
import { getToken as getStoredToken, getUserInfo as getStoredUserInfo, saveAuthData, clearAuth } from '@/utils/authStorage'

export const useUserStore = defineStore('user', () => {
  // 用户信息（从集中化存储层初始化）
  const userInfo = ref(getStoredUserInfo())
  
  // Token（从集中化存储层初始化）
  const token = ref(getStoredToken())

  // 登录状态
  const isLoggedIn = computed(() => !!token.value && !!userInfo.value)
  
  // 是否是管理员（租户管理员或超级管理员）
  const isAdmin = computed(() => {
    const role = userInfo.value?.role
    return role === 'tenant_admin' || role === 'super_admin'
  })
  
  // 是否是超级管理员
  const isSuperAdmin = computed(() => userInfo.value?.role === 'super_admin')

  // 登录
  async function login(credentials) {
    try {
      const res = await authApi.login(credentials)
      if (res.data) {
        token.value = res.data.access_token
        userInfo.value = res.data.user
        saveAuthData(res.data.access_token, res.data.user)
      }
      return res
    } catch (error) {
      console.error('登录失败:', error)
      throw error
    }
  }

  // 注册
  async function register(data) {
    try {
      const res = await authApi.register(data)
      if (res.data) {
        token.value = res.data.access_token
        userInfo.value = res.data.user
        saveAuthData(res.data.access_token, res.data.user)
      }
      return res
    } catch (error) {
      console.error('注册失败:', error)
      throw error
    }
  }

  // 登出
  function logout() {
    token.value = null
    userInfo.value = null
    clearAuth()
    router.push('/login')
  }

  // 获取用户信息
  async function fetchProfile() {
    try {
      const res = await authApi.getProfile()
      userInfo.value = res.data || res
      // 通过集中化存储层更新
      saveAuthData(token.value, res.data || res)
      return res
    } catch (error) {
      console.error('获取用户信息失败:', error)
      // Token无效，清除登录状态
      if (error.response?.status === 401) {
        logout()
      }
      throw error
    }
  }

  /** 获取当前 Token（供非组件上下文使用） */
  function getToken() {
    return token.value
  }

  // 注意：移除了自动检查登录状态的代码
  // 原因：在 store 模块初始化时执行异步操作可能导致问题
  // 登录状态检查应该在组件的生命周期钩子（如 onMounted）中进行
  // 如果需要在组件中检查登录状态，请手动调用 fetchProfile()

  return {
    userInfo,
    token,
    isLoggedIn,
    isAdmin,
    isSuperAdmin,
    login,
    register,
    logout,
    fetchProfile,
    getToken
  }
})
