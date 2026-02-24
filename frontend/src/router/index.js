import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { requiresAuth: false, title: '登录' }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { requiresAuth: false, title: '注册' }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Home',
        component: () => import('@/views/home/Index.vue'),
        meta: { title: '首页' }
      },
      {
        path: 'generate',
        name: 'Generate',
        component: () => import('@/views/generate/Index.vue'),
        meta: { title: '创意生成' }
      },
      {
        path: 'generate/:type',
        name: 'GenerateType',
        component: () => import('@/views/generate/GenerateForm.vue'),
        meta: { title: '创意生成' }
      },
      {
        path: 'api-keys',
        name: 'ApiKeys',
        component: () => import('@/views/api-keys/Index.vue'),
        meta: { title: 'API Key管理' }
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/Index.vue'),
        meta: { title: '知识库' }
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/history/Index.vue'),
        meta: { title: '历史记录' }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/Index.vue'),
        meta: { title: '个人设置' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '页面未找到' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - 全能创意大师` : '全能创意大师'
  
  const userStore = useUserStore()
  
  // 需要认证的页面
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }
  
  // 需要管理员权限
  if (to.meta.requiresAdmin && !userStore.isAdmin) {
    next({ name: 'Home' })
    return
  }
  
  // 已登录用户访问登录/注册页
  if ((to.name === 'Login' || to.name === 'Register') && userStore.isLoggedIn) {
    next({ name: 'Home' })
    return
  }
  
  next()
})

export default router
