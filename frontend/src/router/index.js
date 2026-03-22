import { createRouter, createWebHistory } from 'vue-router'

const routes = [
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
        path: 'novel-writer/:id',
        name: 'NovelWriterDetail',
        component: () => import('@/views/novel-writer/ProjectDetail.vue'),
        meta: { title: '项目详情' }
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

// 路由守卫（仅设置页面标题）
router.beforeEach((to, from, next) => {
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - 全能创意大师` : '全能创意大师'
  next()
})

export default router
