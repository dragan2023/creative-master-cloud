import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userInfo.value?.role === 'admin')

  // 登录
  async function login(credentials) {
    const res = await authApi.login(credentials)
    // 后端返回格式: { code, message, data: { access_token, user } }
    const loginData = res.data || res
    token.value = loginData.access_token
    userInfo.value = loginData.user
    localStorage.setItem('token', loginData.access_token)
    localStorage.setItem('userInfo', JSON.stringify(loginData.user))
    return res
  }

  // 注册
  async function register(data) {
    const res = await authApi.register(data)
    return res
  }

  // 登出
  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }

  // 获取用户信息
  async function fetchProfile() {
    const res = await authApi.getProfile()
    userInfo.value = res.data || res
    localStorage.setItem('userInfo', JSON.stringify(res.data || res))
    return res
  }

  // 更新用户信息
  async function updateProfile(data) {
    const res = await authApi.updateProfile(data)
    userInfo.value = res.data || res
    localStorage.setItem('userInfo', JSON.stringify(res.data || res))
    return res
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    isAdmin,
    login,
    register,
    logout,
    fetchProfile,
    updateProfile
  }
})
