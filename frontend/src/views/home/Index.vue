<template>
  <div class="home-page">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-content">
        <div class="welcome-text">
          <h1>欢迎回来，{{ userStore.userInfo?.username || '用户' }}</h1>
          <p>选择一个创意模块开始您的创作之旅</p>
          <div class="version-info">
            <span class="version-badge">v{{ currentVersion }}</span>
          </div>
        </div>
        <div class="welcome-illustration">
          <img src="/logo.png" alt="全能创意大师" class="welcome-logo-img" />
        </div>
      </div>
      <div class="welcome-decoration">
        <div class="deco-line"></div>
        <div class="deco-dot"></div>
      </div>
    </div>
    
    <!-- 功能模块卡片 -->
    <div class="modules-section">
      <h2 class="section-title">
        <span class="title-icon"></span>
        创意生成模块
      </h2>
      <div class="module-grid">
        <router-link
          v-for="module in creativeModules"
          :key="module.key"
          class="module-card"
          :to="`/generate/${module.key}`"
          :style="{ '--module-color': module.color }"
        >
          <div class="card-glow"></div>
          <div class="module-icon">
            <el-icon :size="36">
              <component :is="resolveElementIcon(module.icon)" />
            </el-icon>
          </div>
          <div class="module-info">
            <h3>{{ module.title }}</h3>
            <p>{{ module.description }}</p>
          </div>
          <div class="module-action">
            <el-icon><ArrowRight /></el-icon>
          </div>
        </router-link>
      </div>
    </div>
    
    <!-- 快捷操作 -->
    <div class="quick-actions">
      <h2 class="section-title">
        <span class="title-icon"></span>
        快捷操作
      </h2>
      <div class="action-grid">
        <router-link class="action-card" to="/api-keys">
          <div class="action-icon">
            <el-icon :size="22"><Key /></el-icon>
          </div>
          <span>API Key管理</span>
          <p>配置您的AI模型密钥</p>
        </router-link>
        <router-link class="action-card" to="/knowledge">
          <div class="action-icon">
            <el-icon :size="22"><FolderOpened /></el-icon>
          </div>
          <span>知识库管理</span>
          <p>上传和管理知识文件</p>
        </router-link>
        <router-link class="action-card" to="/history">
          <div class="action-icon">
            <el-icon :size="22"><Clock /></el-icon>
          </div>
          <span>历史记录</span>
          <p>查看创作历史</p>
        </router-link>
        <router-link class="action-card" to="/profile">
          <div class="action-icon">
            <el-icon :size="22"><User /></el-icon>
          </div>
          <span>个人设置</span>
          <p>管理账户信息</p>
        </router-link>
      </div>
    </div>
    
    <!-- 最近创作 -->
    <div class="recent-section" v-if="recentGenerations.length">
      <h2 class="section-title">最近创作</h2>
      <el-table :data="recentGenerations" style="width: 100%">
        <el-table-column prop="module" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getTagType(row.module)">{{ getTypeName(row.module) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ getTitle(row) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" text @click="viewHistory(row.id)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    
    <!-- 新手引导对话框 -->
    <OnboardingDialogs
      :show-welcome="onboarding.showWelcomeDialog.value"
      :show-api-guide="onboarding.showAPIGuideDialog.value"
      :show-celebration="onboarding.showFirstGenCelebration.value"
      @welcome-complete="onboarding.completeWelcome()"
      @api-guide-complete="onboarding.completeAPIGuide()"
      @skip-all="onboarding.skipAll()"
    />
    
    <!-- 资源链接 -->
    <div class="resources-section">
      <h2 class="section-title">
        <span class="title-icon"></span>
        资源链接
      </h2>
      <div class="resources-grid">
        <a 
          href="https://github.com/dragan2023/creative-master" 
          target="_blank" 
          rel="noopener noreferrer"
          class="resource-card github"
        >
          <div class="resource-icon">
            <el-icon :size="22"><Link /></el-icon>
          </div>
          <span>GitHub 项目地址</span>
          <p>查看源码、提交 Issue</p>
        </a>
        <a 
          href="https://pan.quark.cn/s/1333d8e42793?pwd=VP5u" 
          target="_blank" 
          rel="noopener noreferrer"
          class="resource-card quark"
        >
          <div class="resource-icon">
            <el-icon :size="22"><FolderOpened /></el-icon>
          </div>
          <span>夸克网盘下载</span>
          <p>提取码: VP5u</p>
        </a>
        <a 
          href="https://pan.baidu.com/s/1zg-BrlctdDMa7jA9VH8Q_g?pwd=wxbv" 
          target="_blank" 
          rel="noopener noreferrer"
          class="resource-card baidu"
        >
          <div class="resource-icon">
            <el-icon :size="22"><FolderOpened /></el-icon>
          </div>
          <span>百度网盘下载</span>
          <p>提取码: wxbv</p>
        </a>
      </div>
      <div class="author-info">
        <div class="author-item">
          <el-icon :size="16"><User /></el-icon>
          <span>作者 B站：</span>
          <a href="https://space.bilibili.com/" target="_blank" rel="noopener noreferrer">打卤阳春面</a>
        </div>
        <div class="author-item">
          <el-icon :size="16"><ChatDotRound /></el-icon>
          <span>联系 QQ：</span>
          <span class="qq-number">7527149</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Key, FolderOpened, Clock, User, Link, ChatDotRound } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores'
import { historyApi } from '@/api'
import { CREATIVE_MODULES } from '@/config'
import { APP_VERSION } from '@/config/version'
import { resolveElementIcon } from '@/utils/elementIcons'
import { useOnboarding } from '@/composables/useOnboarding'
import OnboardingDialogs from './components/OnboardingDialogs.vue'

const router = useRouter()
const userStore = useUserStore()
const onboarding = useOnboarding()

// 从父组件注入版本号，失败时使用本地版本
const currentVersion = inject('currentVersion', ref(APP_VERSION))

// 用于首页展示的创意模块
const creativeModules = CREATIVE_MODULES
const recentGenerations = ref([])

onMounted(async () => {
  await fetchRecentGenerations()
  // 初始化新手引导（按用户隔离，判断前先确认 API Key 状态）
  await onboarding.initOnboarding(userStore.userInfo?.id)
})

async function fetchRecentGenerations() {
  try {
    const res = await historyApi.list({ page: 1, page_size: 5 })
    // 后端返回 {code, message, data: [...]} 列表
    recentGenerations.value = res.data || []
  } catch (error) {
    console.error('获取历史记录失败:', error)
  }
}

function viewHistory(id) {
  router.push(`/history?id=${id}`)
}

// 模块名称映射（后端返回下划线格式）
const moduleNameMap = {
  'short_video': '短视频脚本',
  'novel': '小说大纲',
  'print_ad': '平面广告',
  'tvc': 'TVC广告脚本'
}

function getTypeName(type) {
  return moduleNameMap[type] || type
}

function getTagType(type) {
  const typeMap = {
    'short_video': 'danger',
    'novel': 'primary',
    'print_ad': 'warning',
    'tvc': 'info'
  }
  return typeMap[type] || ''
}

function getTitle(row) {
  // 从 input_params 中提取标题
  const params = row?.input_params || {}
  return params.topic || params.theme || params.synopsis || params.title || '创意内容'
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}
</script>

<style lang="scss" scoped>
.home-page {
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-section {
  position: relative;
  border-radius: 20px;
  padding: 36px 40px;
  margin-bottom: 32px;
  background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  
  .welcome-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: relative;
    z-index: 2;
  }
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: 
      radial-gradient(ellipse at 20% 50%, rgba(64, 158, 255, 0.15) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 50%, rgba(0, 212, 170, 0.1) 0%, transparent 50%);
    pointer-events: none;
  }
  
  .welcome-text {
    h1 {
      font-size: 28px;
      margin-bottom: 10px;
      font-weight: 700;
      background: linear-gradient(90deg, #fff, #409EFF, #00D4AA);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    
    p {
      opacity: 0.8;
      font-size: 15px;
      color: rgba(255, 255, 255, 0.7);
      margin-bottom: 16px;
    }
    
    .version-info {
      display: flex;
      align-items: center;
      gap: 12px;
      
      .version-badge {
        background: rgba(64, 158, 255, 0.2);
        border: 1px solid rgba(64, 158, 255, 0.3);
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        color: #409EFF;
      }
    }
  }
  
  .welcome-illustration {
    position: relative;
    width: 120px;
    height: 120px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    
    .welcome-logo-img {
      width: 100px;
      height: 100px;
      object-fit: contain;
      border-radius: 6px;
      position: relative;
      z-index: 1;
    }
  }
  
  .welcome-decoration {
    position: absolute;
    bottom: 0;
    left: 40px;
    right: 40px;
    display: flex;
    align-items: center;
    gap: 10px;
    
    .deco-line {
      flex: 1;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(64, 158, 255, 0.3), transparent);
    }
    
    .deco-dot {
      width: 6px;
      height: 6px;
      background: #409EFF;
      border-radius: 50%;
    }
  }
}

@keyframes pulse-glow {
  0%, 100% { transform: scale(1); opacity: 0.2; }
  50% { transform: scale(1.2); opacity: 0.3; }
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  
  .title-icon {
    width: 4px;
    height: 18px;
    background: linear-gradient(180deg, #409EFF, #00D4AA);
    border-radius: 2px;
  }
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
  
  .module-card {
    position: relative;
    display: flex;
    align-items: center;
    background: #fff;
    border-radius: var(--radius-lg);
    padding: 24px;
    cursor: pointer;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid rgba(64, 158, 255, 0.1);
    overflow: hidden;
    // router-link 渲染为 a 标签：去除默认链接样式
    text-decoration: none;
    color: inherit;
    
    .card-glow {
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(64, 158, 255, 0.05), rgba(0, 212, 170, 0.05));
      opacity: 0;
      transition: opacity 0.4s;
    }
    
    &:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    
    &:hover {
      transform: translateY(-6px);
      box-shadow: 0 12px 40px rgba(64, 158, 255, 0.15);
      border-color: var(--module-color);
      
      .card-glow {
        opacity: 1;
      }
      
      .module-icon {
        background: var(--module-color);
        box-shadow: 0 8px 24px rgba(64, 158, 255, 0.3);
        
        .el-icon {
          color: #fff;
        }
      }
      
      .module-action {
        opacity: 1;
        transform: translateX(6px);
      }
    }
    
    .module-icon {
      width: 64px;
      height: 64px;
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(64, 158, 255, 0.08);
      transition: all 0.4s;
      flex-shrink: 0;
      
      .el-icon {
        color: var(--module-color);
        transition: color 0.4s;
      }
    }
    
    .module-info {
      flex: 1;
      margin-left: 20px;
      
      h3 {
        font-size: 17px;
        color: #303133;
        margin-bottom: 6px;
        font-weight: 600;
      }
      
      p {
        font-size: 13px;
        color: #909399;
        line-height: 1.5;
      }
    }
    
    .module-action {
      opacity: 0;
      transition: all 0.4s;
      color: var(--module-color);
      font-size: 20px;
    }
  }
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 32px;
  
  .action-card {
    background: #fff;
    border-radius: var(--radius-lg);
    padding: 24px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid rgba(64, 158, 255, 0.08);
    // router-link 渲染为 a 标签：去除默认链接样式
    text-decoration: none;
    color: inherit;
    display: block;
    
    &:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    
    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 24px rgba(64, 158, 255, 0.12);
      border-color: rgba(64, 158, 255, 0.3);
      
      .action-icon {
        background: linear-gradient(135deg, #409EFF, #00D4AA);
        box-shadow: 0 4px 16px rgba(64, 158, 255, 0.3);
        
        .el-icon {
          color: #fff;
        }
      }
    }
    
    .action-icon {
      width: 48px;
      height: 48px;
      margin: 0 auto 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(64, 158, 255, 0.08);
      border-radius: 12px;
      transition: all 0.3s;
      
      .el-icon {
        color: #409EFF;
        transition: color 0.3s;
      }
    }
    
    span {
      display: block;
      font-size: 14px;
      color: #303133;
      margin-bottom: 6px;
      font-weight: 500;
    }
    
    p {
      font-size: 12px;
      color: #909399;
      margin: 0;
    }
  }
}

.recent-section {
  background: #fff;
  border-radius: var(--radius-lg);
  padding: 24px;
  margin-bottom: 32px;
  border: 1px solid rgba(64, 158, 255, 0.08);
}

.resources-section {
  background: #fff;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid rgba(64, 158, 255, 0.08);
  
  .resources-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 20px;
    
    .resource-card {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 20px;
      border-radius: var(--radius-md);
      text-decoration: none;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      cursor: pointer;
      position: relative;
      overflow: hidden;
      
      &:focus-visible {
        outline: 2px solid var(--primary-color);
        outline-offset: 2px;
      }
      
      &.github {
        background: linear-gradient(135deg, #24292e 0%, #363d44 100%);
        color: #fff;
        
        &:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 24px rgba(36, 41, 46, 0.4);
        }
      }
      
      &.quark {
        background: linear-gradient(135deg, #1890ff 0%, #36cfc9 100%);
        color: #fff;
        
        &:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 24px rgba(24, 144, 255, 0.4);
        }
      }
      
      &.baidu {
        background: linear-gradient(135deg, #06a7ff 0%, #2b6cb0 100%);
        color: #fff;
        
        &:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 24px rgba(6, 167, 255, 0.4);
        }
      }
      
      .resource-icon {
        width: 44px;
        height: 44px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(255, 255, 255, 0.15);
        border-radius: 10px;
        margin-bottom: 12px;
      }
      
      span {
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 4px;
      }
      
      p {
        font-size: 12px;
        opacity: 0.8;
        margin: 0;
      }
    }
  }
  
  .author-info {
    display: flex;
    gap: 32px;
    padding-top: 16px;
    border-top: 1px solid rgba(64, 158, 255, 0.08);
    
    .author-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: #606266;
      
      .el-icon {
        color: #909399;
      }
      
      a {
        color: #409eff;
        text-decoration: none;
        font-weight: 500;
        
        &:hover {
          color: #00D4AA;
        }
      }
      
      .qq-number {
        color: #409eff;
        font-weight: 600;
      }
    }
  }
}

// ============================================================
// 响应式适配：390px 单列 / 768px 自适应两列 / 桌面按可用宽度扩展
// 断点与 styles/responsive.scss 保持一致（768px）
// ============================================================
@media (max-width: 768px) {
  .welcome-section {
    padding: 24px 20px;

    .welcome-text h1 {
      font-size: 22px;
    }

    .welcome-illustration {
      width: 72px;
      height: 72px;

      .welcome-logo-img {
        width: 64px;
        height: 64px;
      }
    }

    .welcome-decoration {
      left: 20px;
      right: 20px;
    }
  }

  .module-grid {
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 14px;
  }

  .action-grid {
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 12px;
  }

  .resources-section {
    .resources-grid {
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    }

    .author-info {
      flex-wrap: wrap;
      gap: 12px;
    }
  }
}
</style>
