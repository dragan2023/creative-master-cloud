"""生成 writer_master 前端项目文件"""
import os
import json

BASE = r'F:\python_project\writer_master\frontend'


def write_file(rel_path, content):
    full_path = os.path.join(BASE, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')
    print(f'  Created: {rel_path}')


def write_json(rel_path, data):
    full_path = os.path.join(BASE, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(f'  Created: {rel_path}')


# ==================== package.json ====================
write_json('package.json', {
    "name": "writer-master-frontend",
    "private": True,
    "version": "1.0.0",
    "type": "module",
    "scripts": {
        "dev": "vite",
        "build": "vite build",
        "preview": "vite preview"
    },
    "dependencies": {
        "@element-plus/icons-vue": "^2.3.2",
        "axios": "^1.13.5",
        "diff": "^9.0.0",
        "dompurify": "^3.0.6",
        "element-plus": "^2.13.2",
        "marked": "^17.0.2",
        "pinia": "^2.1.7",
        "sse.js": "^2.8.0",
        "vue": "^3.5.25",
        "vue-router": "^4.4.5"
    },
    "devDependencies": {
        "@vitejs/plugin-vue": "^6.0.2",
        "sass": "^1.97.3",
        "terser": "^5.31.0",
        "vite": "^5.4.11"
    }
})

# ==================== vite.config.js ====================
write_file('vite.config.js', '''
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      }
    }
  }
})
''')

# ==================== index.html ====================
write_file('index.html', '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Writer Master - 小说剧本创作系统</title>
  <link rel="icon" href="/favicon.ico" />
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
''')

# ==================== .env ====================
write_file('.env', '''
VITE_APP_TITLE=Writer Master
VITE_API_BASE_URL=http://127.0.0.1:8001
''')

# ==================== src/main.js ====================
write_file('src/main.js', '''
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.mount('#app')
''')

# ==================== src/App.vue ====================
write_file('src/App.vue', '''
<template>
  <router-view />
</template>

<script setup>
</script>

<style>
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', Arial, sans-serif;
}
</style>
''')

# ==================== constants/contentTypes.js ====================
write_file('src/constants/contentTypes.js', '''
/**
 * 内容类型常量 - 替代所有硬编码字面量
 */
export const ContentTypes = Object.freeze({
  NOVEL: 'novel',
  SERIES_SCRIPT: 'series_script',
  MOVIE_SCRIPT: 'movie_script',
})

export const ContentTypeLabels = Object.freeze({
  [ContentTypes.NOVEL]: '小说',
  [ContentTypes.SERIES_SCRIPT]: '剧集剧本',
  [ContentTypes.MOVIE_SCRIPT]: '电影剧本',
})

export const ContentTypeUnitLabels = Object.freeze({
  [ContentTypes.NOVEL]: '章',
  [ContentTypes.SERIES_SCRIPT]: '集',
  [ContentTypes.MOVIE_SCRIPT]: '场',
})

export const ContentTypeRoutes = Object.freeze({
  [ContentTypes.NOVEL]: {
    outline: '/novel-outline-generator',
    workbench: '/novel-workbench',
  },
  [ContentTypes.SERIES_SCRIPT]: {
    outline: '/series-outline-generator',
    workbench: '/series-workbench',
  },
  [ContentTypes.MOVIE_SCRIPT]: {
    outline: '/movie-outline-generator',
    workbench: '/movie-workbench',
  },
})

export const ContentTypeConfig = Object.freeze({
  [ContentTypes.NOVEL]: {
    defaultWordsPerChapter: 3000,
    minWordsPerChapter: 500,
    maxWordsPerChapter: 10000,
    outlineFields: ['global_outline', 'unit_summaries', 'chapter_outlines'],
  },
  [ContentTypes.SERIES_SCRIPT]: {
    defaultWordsPerChapter: 2500,
    minWordsPerChapter: 500,
    maxWordsPerChapter: 8000,
    outlineFields: ['global_outline', 'unit_summaries', 'episode_outlines'],
  },
  [ContentTypes.MOVIE_SCRIPT]: {
    defaultWordsPerChapter: 250,
    minWordsPerChapter: 100,
    maxWordsPerChapter: 2000,
    outlineFields: ['global_outline', 'unit_summaries', 'scene_outlines'],
  },
})
''')

# ==================== constants/projectStatus.js ====================
write_file('src/constants/projectStatus.js', '''
/**
 * 项目状态常量
 */
export const ProjectStatus = Object.freeze({
  INIT: 'init',
  DIRECTORY: 'directory',
  GENERATING: 'generating',
  COMPLETED: 'completed',
  FAILED: 'failed',
  PAUSED: 'paused',
})

export const ProjectStatusLabels = Object.freeze({
  [ProjectStatus.INIT]: '初始化',
  [ProjectStatus.DIRECTORY]: '目录生成中',
  [ProjectStatus.GENERATING]: '正文生成中',
  [ProjectStatus.COMPLETED]: '已完成',
  [ProjectStatus.FAILED]: '失败',
  [ProjectStatus.PAUSED]: '已暂停',
})

export const ProjectStatusColors = Object.freeze({
  [ProjectStatus.INIT]: '#909399',
  [ProjectStatus.DIRECTORY]: '#E6A23C',
  [ProjectStatus.GENERATING]: '#409EFF',
  [ProjectStatus.COMPLETED]: '#67C23A',
  [ProjectStatus.FAILED]: '#F56C6C',
  [ProjectStatus.PAUSED]: '#E6A23C',
})
''')

# ==================== constants/chapterStatus.js ====================
write_file('src/constants/chapterStatus.js', '''
/**
 * 章节状态常量
 */
export const ChapterStatus = Object.freeze({
  PENDING: 'pending',
  DRAFTING: 'drafting',
  REVIEWING: 'reviewing',
  COMPLETED: 'completed',
  FAILED: 'failed',
})

export const ChapterStatusLabels = Object.freeze({
  [ChapterStatus.PENDING]: '待生成',
  [ChapterStatus.DRAFTING]: '生成中',
  [ChapterStatus.REVIEWING]: '质控中',
  [ChapterStatus.COMPLETED]: '已完成',
  [ChapterStatus.FAILED]: '生成失败',
})
''')

# ==================== constants/generationDefaults.js ====================
write_file('src/constants/generationDefaults.js', '''
/**
 * 生成相关默认值常量
 */
export const GenerationDefaults = Object.freeze({
  TEMPERATURE: 0.7,
  MAX_TOKENS: 4096,
  RECENT_CHAPTERS_COUNT: 3,
  BATCH_SIZE: 5,
  MAX_RETRY: 3,
  STREAMING_TIMEOUT: 300,
})

export const QualityDefaults = Object.freeze({
  MIN_SCORE: 0,
  MAX_SCORE: 100,
  PASS_THRESHOLD: 60,
  EXCELLENT_THRESHOLD: 80,
  WEIGHT_CONSISTENCY: 0.4,
  WEIGHT_COHERENCE: 0.35,
  WEIGHT_STYLE_MATCH: 0.25,
})

export const OutlineDefaults = Object.freeze({
  GLOBAL_OUTLINE_MIN_CHARS: 2000,
  UNIT_SUMMARY_MIN_CHARS: 100,
  UNIT_SUMMARY_MAX_CHARS: 300,
})
''')

# ==================== constants/index.js ====================
write_file('src/constants/index.js', '''
/**
 * 常量统一导出
 */
export {
  ContentTypes, ContentTypeLabels, ContentTypeUnitLabels,
  ContentTypeRoutes, ContentTypeConfig
} from './contentTypes'

export {
  ProjectStatus, ProjectStatusLabels, ProjectStatusColors
} from './projectStatus'

export {
  ChapterStatus, ChapterStatusLabels
} from './chapterStatus'

export {
  GenerationDefaults, QualityDefaults, OutlineDefaults
} from './generationDefaults'
''')

# ==================== factories/strategyRegistry.js ====================
write_file('src/factories/strategyRegistry.js', '''
/**
 * 策略注册表 - 按内容类型注册不同的策略实现
 * 遵循策略模式规范，所有内容类型特定逻辑通过注册表分发
 */
import { ContentTypes } from '@/constants/contentTypes'

class StrategyRegistry {
  constructor() {
    this._strategies = new Map()
  }

  register(contentType, strategy) {
    this._strategies.set(contentType, strategy)
  }

  get(contentType) {
    const strategy = this._strategies.get(contentType)
    if (!strategy) {
      throw new Error(`未注册的内容类型策略: ${contentType}`)
    }
    return strategy
  }

  has(contentType) {
    return this._strategies.has(contentType)
  }

  getAllTypes() {
    return Array.from(this._strategies.keys())
  }
}

// 大纲生成策略注册表
export const outlineStrategyRegistry = new StrategyRegistry()

// 工作台策略注册表
export const workbenchStrategyRegistry = new StrategyRegistry()

// 提示词策略注册表
export const promptStrategyRegistry = new StrategyRegistry()
''')

# ==================== factories/outlineFactory.js ====================
write_file('src/factories/outlineFactory.js', '''
/**
 * 大纲生成工厂 - 为不同内容类型提供大纲生成策略
 */
import { ContentTypes, ContentTypeConfig, ContentTypeLabels } from '@/constants'
import { outlineStrategyRegistry } from './strategyRegistry'

/**
 * 小说大纲生成策略
 */
const novelOutlineStrategy = {
  contentType: ContentTypes.NOVEL,
  label: ContentTypeLabels[ContentTypes.NOVEL],

  getOutlineFields() {
    return ContentTypeConfig[ContentTypes.NOVEL].outlineFields
  },

  getUnitLabel() {
    return '章'
  },

  getDetailedOutlineField() {
    return 'chapter_outlines'
  },

  getDetailTitleTemplate(unitNum, unitData) {
    return unitData.title || `第${unitNum}章`
  },

  getDefaultWordsPerUnit() {
    return ContentTypeConfig[ContentTypes.NOVEL].defaultWordsPerChapter
  }
}

/**
 * 剧集剧本大纲生成策略
 */
const seriesOutlineStrategy = {
  contentType: ContentTypes.SERIES_SCRIPT,
  label: ContentTypeLabels[ContentTypes.SERIES_SCRIPT],

  getOutlineFields() {
    return ContentTypeConfig[ContentTypes.SERIES_SCRIPT].outlineFields
  },

  getUnitLabel() {
    return '集'
  },

  getDetailedOutlineField() {
    return 'episode_outlines'
  },

  getDetailTitleTemplate(unitNum, unitData) {
    return unitData.title || `第${unitNum}集`
  },

  getDefaultWordsPerUnit() {
    return ContentTypeConfig[ContentTypes.SERIES_SCRIPT].defaultWordsPerChapter
  }
}

/**
 * 电影剧本大纲生成策略
 */
const movieOutlineStrategy = {
  contentType: ContentTypes.MOVIE_SCRIPT,
  label: ContentTypeLabels[ContentTypes.MOVIE_SCRIPT],

  getOutlineFields() {
    return ContentTypeConfig[ContentTypes.MOVIE_SCRIPT].outlineFields
  },

  getUnitLabel() {
    return '场'
  },

  getDetailedOutlineField() {
    return 'scene_outlines'
  },

  getDetailTitleTemplate(unitNum, unitData) {
    return unitData.title || `场景${unitNum}`
  },

  getDefaultWordsPerUnit() {
    return ContentTypeConfig[ContentTypes.MOVIE_SCRIPT].defaultWordsPerChapter
  }
}

// 注册策略
outlineStrategyRegistry.register(ContentTypes.NOVEL, novelOutlineStrategy)
outlineStrategyRegistry.register(ContentTypes.SERIES_SCRIPT, seriesOutlineStrategy)
outlineStrategyRegistry.register(ContentTypes.MOVIE_SCRIPT, movieOutlineStrategy)

/**
 * 获取大纲策略
 */
export function getOutlineStrategy(contentType) {
  return outlineStrategyRegistry.get(contentType)
}
''')

# ==================== factories/workbenchFactory.js ====================
write_file('src/factories/workbenchFactory.js', '''
/**
 * 工作台工厂 - 为不同内容类型提供创作台策略
 */
import { ContentTypes, ContentTypeConfig, ContentTypeLabels } from '@/constants'
import { workbenchStrategyRegistry } from './strategyRegistry'

/**
 * 小说创作台策略
 */
const novelWorkbenchStrategy = {
  contentType: ContentTypes.NOVEL,
  label: ContentTypeLabels[ContentTypes.NOVEL],

  getUnitLabel() { return '章' },
  getUnitNumberField() { return 'chapter_number' },
  getUnitTitleField() { return 'chapter_title' },
  getContentField() { return 'final_content' },
  getOutlineField() { return 'chapter_outlines' },

  getDefaultWordsPerUnit() {
    return ContentTypeConfig[ContentTypes.NOVEL].defaultWordsPerChapter
  },

  getProgressLabel(completed, total) {
    return `已完成 ${completed}/${total} 章`
  },

  getGenerationPrompt(chapterNum, chapterTitle) {
    return `正在生成第${chapterNum}章: ${chapterTitle}`
  }
}

/**
 * 剧集创作台策略
 */
const seriesWorkbenchStrategy = {
  contentType: ContentTypes.SERIES_SCRIPT,
  label: ContentTypeLabels[ContentTypes.SERIES_SCRIPT],

  getUnitLabel() { return '集' },
  getUnitNumberField() { return 'episode_number' },
  getUnitTitleField() { return 'chapter_title' },
  getContentField() { return 'final_content' },
  getOutlineField() { return 'episode_outlines' },

  getDefaultWordsPerUnit() {
    return ContentTypeConfig[ContentTypes.SERIES_SCRIPT].defaultWordsPerChapter
  },

  getProgressLabel(completed, total) {
    return `已完成 ${completed}/${total} 集`
  },

  getGenerationPrompt(episodeNum, episodeTitle) {
    return `正在生成第${episodeNum}集: ${episodeTitle}`
  }
}

/**
 * 电影剧本创作台策略
 */
const movieWorkbenchStrategy = {
  contentType: ContentTypes.MOVIE_SCRIPT,
  label: ContentTypeLabels[ContentTypes.MOVIE_SCRIPT],

  getUnitLabel() { return '场' },
  getUnitNumberField() { return 'scene_number' },
  getUnitTitleField() { return 'chapter_title' },
  getContentField() { return 'final_content' },
  getOutlineField() { return 'scene_outlines' },

  getDefaultWordsPerUnit() {
    return ContentTypeConfig[ContentTypes.MOVIE_SCRIPT].defaultWordsPerChapter
  },

  getProgressLabel(completed, total) {
    return `已完成 ${completed}/${total} 场`
  },

  getGenerationPrompt(sceneNum, sceneTitle) {
    return `正在生成场景${sceneNum}: ${sceneTitle}`
  }
}

// 注册策略
workbenchStrategyRegistry.register(ContentTypes.NOVEL, novelWorkbenchStrategy)
workbenchStrategyRegistry.register(ContentTypes.SERIES_SCRIPT, seriesWorkbenchStrategy)
workbenchStrategyRegistry.register(ContentTypes.MOVIE_SCRIPT, movieWorkbenchStrategy)

/**
 * 获取工作台策略
 */
export function getWorkbenchStrategy(contentType) {
  return workbenchStrategyRegistry.get(contentType)
}
''')

# ==================== factories/index.js ====================
write_file('src/factories/index.js', '''
/**
 * 工厂模块统一导出
 */
export { outlineStrategyRegistry, workbenchStrategyRegistry, promptStrategyRegistry } from './strategyRegistry'
export { getOutlineStrategy } from './outlineFactory'
export { getWorkbenchStrategy } from './workbenchFactory'
''')

# ==================== api/request.js ====================
write_file('src/api/request.js', '''
/**
 * Axios 请求封装
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    const { data } = response
    if (data.success === false) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }
    return data
  },
  (error) => {
    const message = error.response?.data?.message || error.message || '网络错误'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default request
''')

# ==================== api/project.js ====================
write_file('src/api/project.js', '''
/**
 * 项目API
 */
import request from './request'

export const projectApi = {
  list(contentType) {
    const params = {}
    if (contentType) params.content_type = contentType
    return request.get('/api/v1/projects', { params })
  },

  get(id) {
    return request.get(`/api/v1/projects/${id}`)
  },

  create(data) {
    return request.post('/api/v1/projects', data)
  },

  update(id, data) {
    return request.put(`/api/v1/projects/${id}`, data)
  },

  delete(id) {
    return request.delete(`/api/v1/projects/${id}`)
  }
}
''')

# ==================== api/chapter.js ====================
write_file('src/api/chapter.js', '''
/**
 * 章节API
 */
import request from './request'

export const chapterApi = {
  list(projectId) {
    return request.get(`/api/v1/chapters/project/${projectId}`)
  },

  get(id) {
    return request.get(`/api/v1/chapters/${id}`)
  },

  create(projectId, data) {
    return request.post(`/api/v1/chapters/project/${projectId}`, data)
  },

  update(id, data) {
    return request.put(`/api/v1/chapters/${id}`, data)
  }
}
''')

# ==================== api/auth.js ====================
write_file('src/api/auth.js', '''
/**
 * 认证API
 */
import request from './request'

export const authApi = {
  login(data) {
    return request.post('/api/v1/auth/login', data)
  },

  register(data) {
    return request.post('/api/v1/auth/register', data)
  }
}
''')

# ==================== api/index.js ====================
write_file('src/api/index.js', '''
/**
 * API统一导出
 */
export { projectApi } from './project'
export { chapterApi } from './chapter'
export { authApi } from './auth'
''')

# ==================== stores/project.js ====================
write_file('src/stores/project.js', '''
/**
 * 项目状态管理
 */
import { defineStore } from 'pinia'
import { projectApi } from '@/api'
import { ContentTypes } from '@/constants'

export const useProjectStore = defineStore('project', {
  state: () => ({
    projects: [],
    currentProject: null,
    loading: false,
  }),

  getters: {
    novelProjects: (state) => state.projects.filter(p => p.content_type === ContentTypes.NOVEL),
    seriesProjects: (state) => state.projects.filter(p => p.content_type === ContentTypes.SERIES_SCRIPT),
    movieProjects: (state) => state.projects.filter(p => p.content_type === ContentTypes.MOVIE_SCRIPT),
  },

  actions: {
    async fetchProjects(contentType) {
      this.loading = true
      try {
        const res = await projectApi.list(contentType)
        this.projects = res.data?.items || []
      } finally {
        this.loading = false
      }
    },

    async fetchProject(id) {
      this.loading = true
      try {
        const res = await projectApi.get(id)
        this.currentProject = res.data
        return res.data
      } finally {
        this.loading = false
      }
    },

    async createProject(data) {
      const res = await projectApi.create(data)
      if (res.data) {
        this.projects.unshift(res.data)
      }
      return res.data
    },

    async updateProject(id, data) {
      const res = await projectApi.update(id, data)
      if (res.data && this.currentProject?.id === id) {
        this.currentProject = res.data
      }
      return res.data
    },

    async deleteProject(id) {
      await projectApi.delete(id)
      this.projects = this.projects.filter(p => p.id !== id)
      if (this.currentProject?.id === id) {
        this.currentProject = null
      }
    },

    setCurrentProject(project) {
      this.currentProject = project
    }
  }
})
''')

# ==================== stores/auth.js ====================
write_file('src/stores/auth.js', '''
/**
 * 认证状态管理
 */
import { defineStore } from 'pinia'
import { authApi } from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null,
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
  },

  actions: {
    async login(credentials) {
      const res = await authApi.login(credentials)
      const data = res.data
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('token', data.access_token)
      return data
    },

    async register(userData) {
      const res = await authApi.register(userData)
      const data = res.data
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('token', data.access_token)
      return data
    },

    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
    }
  }
})
''')

# ==================== stores/index.js ====================
write_file('src/stores/index.js', '''
/**
 * Store统一导出
 */
export { useProjectStore } from './project'
export { useAuthStore } from './auth'
''')

# ==================== router/index.js ====================
write_file('src/router/index.js', '''
/**
 * 路由配置
 */
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/projects'
  },
  {
    path: '/projects',
    name: 'ProjectList',
    component: () => import('@/views/ProjectList/Index.vue'),
    meta: { title: '项目列表' }
  },
  // 小说大纲生成
  {
    path: '/novel-outline-generator',
    name: 'NovelOutlineGenerator',
    component: () => import('@/views/NovelOutlineGenerator/Index.vue'),
    meta: { title: '小说大纲生成', contentType: 'novel' }
  },
  // 剧集剧本大纲生成
  {
    path: '/series-outline-generator',
    name: 'SeriesOutlineGenerator',
    component: () => import('@/views/SeriesOutlineGenerator/Index.vue'),
    meta: { title: '剧集剧本大纲生成', contentType: 'series_script' }
  },
  // 电影剧本大纲生成
  {
    path: '/movie-outline-generator',
    name: 'MovieOutlineGenerator',
    component: () => import('@/views/MovieOutlineGenerator/Index.vue'),
    meta: { title: '电影剧本大纲生成', contentType: 'movie_script' }
  },
  // 小说创作台
  {
    path: '/novel-workbench',
    name: 'NovelWorkbench',
    component: () => import('@/views/NovelWorkbench/Index.vue'),
    meta: { title: '小说创作台', contentType: 'novel' }
  },
  // 剧集创作台
  {
    path: '/series-workbench',
    name: 'SeriesWorkbench',
    component: () => import('@/views/SeriesWorkbench/Index.vue'),
    meta: { title: '剧集创作台', contentType: 'series_script' }
  },
  // 电影剧本创作台
  {
    path: '/movie-workbench',
    name: 'MovieWorkbench',
    component: () => import('@/views/MovieWorkbench/Index.vue'),
    meta: { title: '电影剧本创作台', contentType: 'movie_script' }
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  document.title = to.meta.title
    ? `${to.meta.title} - Writer Master`
    : 'Writer Master'
  next()
})

export default router
''')

# ==================== views/ProjectList/Index.vue ====================
write_file('src/views/ProjectList/Index.vue', '''
<template>
  <div class="project-list-page">
    <el-container>
      <el-header class="page-header">
        <h1>Writer Master</h1>
        <div class="header-actions">
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon> 新建项目
          </el-button>
        </div>
      </el-header>
      <el-main>
        <el-tabs v-model="activeTab" @tab-change="handleTabChange">
          <el-tab-pane label="小说" name="novel" />
          <el-tab-pane label="剧集剧本" name="series_script" />
          <el-tab-pane label="电影剧本" name="movie_script" />
        </el-tabs>

        <el-row :gutter="20" v-loading="projectStore.loading">
          <el-col :span="8" v-for="project in filteredProjects" :key="project.id">
            <el-card shadow="hover" class="project-card" @click="goToWorkbench(project)">
              <template #header>
                <div class="card-header">
                  <span>{{ project.title }}</span>
                  <el-tag :type="statusTagType(project.status)" size="small">
                    {{ statusLabel(project.status) }}
                  </el-tag>
                </div>
              </template>
              <p class="card-genre">{{ project.genre || '未分类' }}</p>
              <p class="card-progress">
                进度: {{ project.completed_chapters }}/{{ project.total_chapters }}
              </p>
            </el-card>
          </el-col>
          <el-col :span="24" v-if="filteredProjects.length === 0">
            <el-empty description="暂无项目" />
          </el-col>
        </el-row>
      </el-main>
    </el-container>

    <!-- 创建项目对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建项目" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="项目标题" required>
          <el-input v-model="createForm.title" placeholder="请输入项目标题" />
        </el-form-item>
        <el-form-item label="内容类型" required>
          <el-select v-model="createForm.content_type" style="width: 100%">
            <el-option label="小说" value="novel" />
            <el-option label="剧集剧本" value="series_script" />
            <el-option label="电影剧本" value="movie_script" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型标签">
          <el-input v-model="createForm.genre" placeholder="如：玄幻、都市、科幻" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores'
import { ContentTypes, ProjectStatusLabels, ContentTypeRoutes } from '@/constants'

const router = useRouter()
const projectStore = useProjectStore()

const activeTab = ref('novel')
const showCreateDialog = ref(false)
const createForm = ref({
  title: '',
  content_type: 'novel',
  genre: '',
})

const filteredProjects = computed(() => {
  return projectStore.projects.filter(p => p.content_type === activeTab.value)
})

function statusLabel(status) {
  return ProjectStatusLabels[status] || status
}

function statusTagType(status) {
  const map = { completed: 'success', generating: 'primary', failed: 'danger', paused: 'warning' }
  return map[status] || 'info'
}

function handleTabChange(type) {
  projectStore.fetchProjects(type)
}

async function handleCreate() {
  if (!createForm.value.title) return
  await projectStore.createProject(createForm.value)
  showCreateDialog.value = false
  createForm.value = { title: '', content_type: 'novel', genre: '' }
  projectStore.fetchProjects(activeTab.value)
}

function goToWorkbench(project) {
  const routes = ContentTypeRoutes[project.content_type]
  if (routes) {
    router.push({ path: routes.workbench, query: { id: project.id } })
  }
}

onMounted(() => {
  projectStore.fetchProjects(activeTab.value)
})
</script>

<style scoped>
.project-list-page { min-height: 100vh; background: #f5f7fa; }
.page-header { display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid #e4e7ed; }
.page-header h1 { font-size: 20px; color: #303133; }
.project-card { margin-bottom: 20px; cursor: pointer; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-genre { color: #909399; font-size: 13px; margin: 8px 0; }
.card-progress { color: #606266; font-size: 13px; }
</style>
''')

# ==================== views/NovelOutlineGenerator/Index.vue ====================
write_file('src/views/NovelOutlineGenerator/Index.vue', '''
<template>
  <OutlineGeneratorPage content-type="novel" />
</template>

<script setup>
import OutlineGeneratorPage from '@/views/components/OutlineGeneratorPage.vue'
</script>
''')

# ==================== views/SeriesOutlineGenerator/Index.vue ====================
write_file('src/views/SeriesOutlineGenerator/Index.vue', '''
<template>
  <OutlineGeneratorPage content-type="series_script" />
</template>

<script setup>
import OutlineGeneratorPage from '@/views/components/OutlineGeneratorPage.vue'
</script>
''')

# ==================== views/MovieOutlineGenerator/Index.vue ====================
write_file('src/views/MovieOutlineGenerator/Index.vue', '''
<template>
  <OutlineGeneratorPage content-type="movie_script" />
</template>

<script setup>
import OutlineGeneratorPage from '@/views/components/OutlineGeneratorPage.vue'
</script>
''')

# ==================== views/NovelWorkbench/Index.vue ====================
write_file('src/views/NovelWorkbench/Index.vue', '''
<template>
  <WorkbenchPage content-type="novel" />
</template>

<script setup>
import WorkbenchPage from '@/views/components/WorkbenchPage.vue'
</script>
''')

# ==================== views/SeriesWorkbench/Index.vue ====================
write_file('src/views/SeriesWorkbench/Index.vue', '''
<template>
  <WorkbenchPage content-type="series_script" />
</template>

<script setup>
import WorkbenchPage from '@/views/components/WorkbenchPage.vue'
</script>
''')

# ==================== views/MovieWorkbench/Index.vue ====================
write_file('src/views/MovieWorkbench/Index.vue', '''
<template>
  <WorkbenchPage content-type="movie_script" />
</template>

<script setup>
import WorkbenchPage from '@/views/components/WorkbenchPage.vue'
</script>
''')

# ==================== views/components/OutlineGeneratorPage.vue ====================
write_file('src/views/components/OutlineGeneratorPage.vue', '''
<template>
  <div class="outline-generator-page">
    <el-page-header @back="goBack" :content="pageTitle" />
    <div class="page-content" v-loading="loading">
      <!-- 步骤条 -->
      <el-steps :active="currentStep" align-center class="step-bar">
        <el-step title="全局大纲" />
        <el-step title="单元概述" />
        <el-step title="详细大纲" />
      </el-steps>

      <!-- 步骤1: 全局大纲 -->
      <div v-if="currentStep === 0" class="step-content">
        <el-input
          v-model="globalOutline"
          type="textarea"
          :rows="15"
          placeholder="请输入或生成全局大纲..."
        />
        <div class="step-actions">
          <el-button type="primary" @click="generateGlobalOutline">
            生成全局大纲
          </el-button>
          <el-button @click="currentStep = 1" :disabled="!globalOutline">
            下一步：单元概述
          </el-button>
        </div>
      </div>

      <!-- 步骤2: 单元概述 -->
      <div v-if="currentStep === 1" class="step-content">
        <div v-for="(unit, idx) in unitSummaries" :key="idx" class="unit-item">
          <h4>{{ strategy.getDetailTitleTemplate(idx + 1, unit) }}</h4>
          <el-input v-model="unit.summary" type="textarea" :rows="3" />
        </div>
        <div class="step-actions">
          <el-button @click="currentStep = 0">上一步</el-button>
          <el-button type="primary" @click="generateUnitSummaries">
            生成单元概述
          </el-button>
          <el-button @click="currentStep = 2" :disabled="unitSummaries.length === 0">
            下一步：详细大纲
          </el-button>
        </div>
      </div>

      <!-- 步骤3: 详细大纲 -->
      <div v-if="currentStep === 2" class="step-content">
        <el-collapse v-model="activeOutlines">
          <el-collapse-item
            v-for="(unit, idx) in unitSummaries"
            :key="idx"
            :title="strategy.getDetailTitleTemplate(idx + 1, unit)"
            :name="idx"
          >
            <el-input
              v-model="unit.detailed_outline"
              type="textarea"
              :rows="5"
              :placeholder="`请生成${strategy.getUnitLabel()}详细大纲...`"
            />
          </el-collapse-item>
        </el-collapse>
        <div class="step-actions">
          <el-button @click="currentStep = 1">上一步</el-button>
          <el-button type="primary" @click="generateDetailedOutlines">
            生成详细大纲
          </el-button>
          <el-button type="success" @click="saveProject">
            保存项目
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/stores'
import { getOutlineStrategy } from '@/factories'
import { ContentTypeLabels } from '@/constants'

const props = defineProps({
  contentType: { type: String, required: true }
})

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()
const strategy = getOutlineStrategy(props.contentType)

const loading = ref(false)
const currentStep = ref(0)
const globalOutline = ref('')
const unitSummaries = ref([])
const activeOutlines = ref([0])

const pageTitle = computed(() => {
  return `${ContentTypeLabels[props.contentType]}大纲生成`
})

function goBack() {
  router.push('/projects')
}

async function generateGlobalOutline() {
  loading.value = true
  try {
    // TODO: 调用后端API生成全局大纲
    ElMessage.info('全局大纲生成功能将对接后端API')
  } finally {
    loading.value = false
  }
}

async function generateUnitSummaries() {
  loading.value = true
  try {
    // TODO: 调用后端API生成单元概述
    ElMessage.info('单元概述生成功能将对接后端API')
  } finally {
    loading.value = false
  }
}

async function generateDetailedOutlines() {
  loading.value = true
  try {
    // TODO: 调用后端API生成详细大纲
    ElMessage.info('详细大纲生成功能将对接后端API')
  } finally {
    loading.value = false
  }
}

async function saveProject() {
  // TODO: 保存项目数据
  ElMessage.success('项目已保存')
}

onMounted(async () => {
  const projectId = route.query.id
  if (projectId) {
    await projectStore.fetchProject(projectId)
    if (projectStore.currentProject) {
      globalOutline.value = projectStore.currentProject.global_outline_content || ''
    }
  }
})
</script>

<style scoped>
.outline-generator-page { padding: 20px; max-width: 1200px; margin: 0 auto; }
.step-bar { margin: 20px 0; }
.step-content { margin-top: 20px; }
.step-actions { margin-top: 20px; display: flex; gap: 10px; }
.unit-item { margin-bottom: 15px; }
.unit-item h4 { margin-bottom: 8px; color: #303133; }
</style>
''')

# ==================== views/components/WorkbenchPage.vue ====================
write_file('src/views/components/WorkbenchPage.vue', '''
<template>
  <div class="workbench-page">
    <el-container>
      <!-- 左侧：章节/场景列表 -->
      <el-aside width="280px" class="chapter-sidebar">
        <div class="sidebar-header">
          <el-button text @click="goBack">
            <el-icon><ArrowLeft /></el-icon> 返回
          </el-button>
          <h3>{{ strategy.label }}创作台</h3>
        </div>
        <div class="chapter-list">
          <div
            v-for="chapter in chapters"
            :key="chapter.id"
            :class="['chapter-item', { active: currentChapterId === chapter.id }]"
            @click="selectChapter(chapter)"
          >
            <span class="chapter-num">
              第{{ chapter[strategy.getUnitNumberField()] }}{{ strategy.getUnitLabel() }}
            </span>
            <span class="chapter-status-dot" :style="{ background: getStatusColor(chapter.status) }" />
          </div>
        </div>
      </el-aside>

      <!-- 右侧：编辑区域 -->
      <el-main class="editor-area">
        <div v-if="currentChapter" class="editor-content">
          <h2 class="chapter-title">
            第{{ currentChapter[strategy.getUnitNumberField()] }}{{ strategy.getUnitLabel() }}:
            {{ currentChapter.chapter_title || '' }}
          </h2>
          <div class="editor-toolbar">
            <el-button type="primary" size="small" @click="generateContent">
              生成内容
            </el-button>
            <el-button size="small" @click="saveContent">保存</el-button>
          </div>
          <el-input
            v-model="editContent"
            type="textarea"
            :rows="25"
            placeholder="章节内容将在此生成..."
          />
        </div>
        <el-empty v-else description="请选择一个章节" />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/stores'
import { getWorkbenchStrategy } from '@/factories'
import { chapterApi } from '@/api'
import { ChapterStatusLabels } from '@/constants'

const props = defineProps({
  contentType: { type: String, required: true }
})

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()
const strategy = getWorkbenchStrategy(props.contentType)

const chapters = ref([])
const currentChapterId = ref(null)
const editContent = ref('')

const currentChapter = computed(() => {
  return chapters.value.find(c => c.id === currentChapterId.value)
})

function goBack() {
  router.push('/projects')
}

function getStatusColor(status) {
  const map = {
    completed: '#67C23A',
    drafting: '#409EFF',
    reviewing: '#E6A23C',
    failed: '#F56C6C',
    pending: '#909399',
  }
  return map[status] || '#909399'
}

function selectChapter(chapter) {
  currentChapterId.value = chapter.id
  editContent.value = chapter.final_content || chapter.draft_content || ''
}

async function generateContent() {
  if (!currentChapter.value) return
  // TODO: 调用后端API生成章节内容
  ElMessage.info('内容生成功能将对接后端API')
}

async function saveContent() {
  if (!currentChapter.value) return
  try {
    await chapterApi.update(currentChapter.value.id, {
      final_content: editContent.value
    })
    ElMessage.success('保存成功')
  } catch (e) {
    // 错误已在拦截器中处理
  }
}

onMounted(async () => {
  const projectId = route.query.id
  if (projectId) {
    await projectStore.fetchProject(projectId)
    try {
      const res = await chapterApi.list(projectId)
      chapters.value = res.data || []
    } catch (e) {
      // 忽略
    }
  }
})
</script>

<style scoped>
.workbench-page { height: 100vh; }
.chapter-sidebar { background: #fff; border-right: 1px solid #e4e7ed; overflow-y: auto; }
.sidebar-header { padding: 15px; border-bottom: 1px solid #e4e7ed; }
.sidebar-header h3 { margin: 10px 0 0; font-size: 16px; }
.chapter-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #f0f0f0; }
.chapter-item:hover { background: #f5f7fa; }
.chapter-item.active { background: #ecf5ff; }
.chapter-num { font-size: 14px; color: #303133; }
.chapter-status-dot { width: 8px; height: 8px; border-radius: 50%; }
.editor-area { padding: 20px; }
.chapter-title { font-size: 18px; margin-bottom: 15px; }
.editor-toolbar { margin-bottom: 15px; display: flex; gap: 10px; }
</style>
''')

print("\n=== Frontend Project Complete ===")
