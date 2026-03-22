import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'

export const useUserStore = defineStore('user', () => {
  // 用户信息（从后端获取默认用户）
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))

  // 始终返回已登录状态（系统无需认证）
  const isLoggedIn = computed(() => true)
  const isAdmin = computed(() => userInfo.value?.role === 'admin')

  // 获取用户信息（默认用户）
  async function fetchProfile() {
    try {
      const res = await authApi.getProfile()
      userInfo.value = res.data || res
      localStorage.setItem('userInfo', JSON.stringify(res.data || res))
      return res
    } catch (error) {
      console.error('获取用户信息失败:', error)
      // 如果获取失败，使用默认用户信息
      userInfo.value = {
        id: 1,
        username: 'default',
        nickname: '默认用户',
        email: 'default@local.host',
        role: 'user'
      }
      return { data: userInfo.value }
    }
  }

  // 初始化时获取用户信息
  if (!userInfo.value) {
    fetchProfile()
  }

  return {
    userInfo,
    isLoggedIn,
    isAdmin,
    fetchProfile
  }
})
