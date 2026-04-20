import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  // 登录注册路由（无需认证）
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { title: '登录', public: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { title: '注册', public: true }
  },
  // 主应用路由
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
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
      },
      {
        path: 'novel-writer',
        name: 'NovelWriter',
        component: () => import('@/views/novel-writer/Index.vue'),
        meta: { title: '小说/剧本生成' }
      },
      {
        path: 'novel-writer/model-config',
        name: 'NovelWriterModelConfig',
        component: () => import('@/views/novel-writer/ModelConfigPage.vue'),
        meta: { title: 'LLM模型配置' }
      },
      {
        path: 'novel-writer/:id',
        name: 'NovelWriterDetail',
        component: () => import('@/views/novel-writer/WritingWorkbench.vue'),
        meta: { title: '写作工作台' }
      },
      {
        path: 'novel-writer/:projectId/quality',
        name: 'QualityAnalysis',
        component: () => import('@/views/novel-writer/QualityAnalysis.vue'),
        meta: { title: 'AI质量分析' }
      },
      // 管理员后台路由
      {
        path: 'admin',
        name: 'AdminDashboard',
        component: () => import('@/views/admin/Dashboard.vue'),
        meta: { title: '管理后台', requiresAdmin: true }
      },
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/UserManagement.vue'),
        meta: { title: '用户管理', requiresAdmin: true }
      },
      {
        path: 'admin/tenants',
        name: 'AdminTenants',
        component: () => import('@/views/admin/TenantManagement.vue'),
        meta: { title: '租户管理', requiresSuperAdmin: true }
      },
      {
        path: 'admin/logs',
        name: 'AdminLogs',
        component: () => import('@/views/admin/Logs.vue'),
        meta: { title: '操作日志', requiresAdmin: true }
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
  
  // 公开页面直接访问
  if (to.meta.public) {
    // 已登录用户访问登录/注册页，重定向到首页
    if (userStore.isLoggedIn && (to.path === '/login' || to.path === '/register')) {
      next('/')
      return
    }
    next()
    return
  }
  
  // 需要认证的页面
  if (!to.meta.public && !userStore.isLoggedIn) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }
  
  // 需要管理员权限（改为仅超级管理员可访问）
  if (to.meta.requiresAdmin && !userStore.isSuperAdmin) {
    next('/')
    return
  }
  
  // 需要超级管理员权限
  if (to.meta.requiresSuperAdmin && !userStore.isSuperAdmin) {
    next('/admin')
    return
  }
  
  next()
})

export default router
