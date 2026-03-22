import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'
import router from '@/router'

export const useUserStore = defineStore('user', () => {
  // 用户信息
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))
  
  // Token
  const token = ref(localStorage.getItem('token') || null)

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
        localStorage.setItem('token', res.data.access_token)
        localStorage.setItem('userInfo', JSON.stringify(res.data.user))
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
        localStorage.setItem('token', res.data.access_token)
        localStorage.setItem('userInfo', JSON.stringify(res.data.user))
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
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    router.push('/login')
  }

  // 获取用户信息
  async function fetchProfile() {
    try {
      const res = await authApi.getProfile()
      userInfo.value = res.data || res
      localStorage.setItem('userInfo', JSON.stringify(res.data || res))
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

  // 初始化时检查登录状态
  if (token.value && !userInfo.value) {
    fetchProfile().catch(() => {
      // 获取用户信息失败，清除token
      logout()
    })
  }

  return {
    userInfo,
    token,
    isLoggedIn,
    isAdmin,
    isSuperAdmin,
    login,
    register,
    logout,
    fetchProfile
  }
})
