<template>
  <div class="home-page">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-text">
        <h1>欢迎回来，{{ userStore.userInfo?.username || '用户' }}</h1>
        <p>选择一个创意模块开始您的创作之旅</p>
        <div class="version-info">
          <span class="version-badge">v{{ currentVersion || '1.0.0' }}</span>
          <el-button 
            type="primary" 
            plain
            :loading="checkingUpdate"
            @click="checkUpdate"
            class="check-update-btn"
          >
            <el-icon v-if="!checkingUpdate"><Refresh /></el-icon>
            {{ checkingUpdate ? '检查中...' : '检查更新' }}
          </el-button>
        </div>
      </div>
      <div class="welcome-illustration">
        <el-icon :size="80" color="#409EFF"><MagicStick /></el-icon>
      </div>
    </div>
    
    <!-- 功能模块卡片 -->
    <div class="modules-section">
      <h2 class="section-title">创意生成模块</h2>
      <div class="module-grid">
        <div
          v-for="module in creativeModules"
          :key="module.key"
          class="module-card"
          :style="{ '--module-color': module.color }"
          @click="goToGenerate(module.key)"
        >
          <div class="module-icon">
            <el-icon :size="40">
              <component :is="module.icon" />
            </el-icon>
          </div>
          <div class="module-info">
            <h3>{{ module.title }}</h3>
            <p>{{ module.description }}</p>
          </div>
          <div class="module-action">
            <el-icon><ArrowRight /></el-icon>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 快捷操作 -->
    <div class="quick-actions">
      <h2 class="section-title">快捷操作</h2>
      <div class="action-grid">
        <div class="action-card" @click="router.push('/api-keys')">
          <el-icon :size="24"><Key /></el-icon>
          <span>API Key管理</span>
          <p>配置您的AI模型密钥</p>
        </div>
        <div class="action-card" @click="router.push('/knowledge')">
          <el-icon :size="24"><FolderOpened /></el-icon>
          <span>知识库管理</span>
          <p>上传和管理知识文件</p>
        </div>
        <div class="action-card" @click="router.push('/history')">
          <el-icon :size="24"><Clock /></el-icon>
          <span>历史记录</span>
          <p>查看创作历史</p>
        </div>
        <div class="action-card" @click="router.push('/profile')">
          <el-icon :size="24"><User /></el-icon>
          <span>个人设置</span>
          <p>管理账户信息</p>
        </div>
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
  </div>
</template>

<script setup>
import { ref, onMounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores'
import { historyApi } from '@/api'
import { CREATIVE_MODULES } from '@/config'
import { Refresh } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()

// 从父组件注入更新检查方法
const checkUpdate = inject('checkUpdate')
const checkingUpdate = inject('checkingUpdate')
const currentVersion = inject('currentVersion')

// 用于首页展示的创意模块
const creativeModules = CREATIVE_MODULES
const recentGenerations = ref([])

onMounted(async () => {
  await fetchRecentGenerations()
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

function goToGenerate(type) {
  router.push(`/generate/${type}`)
}

function viewHistory(id) {
  router.push(`/history?id=${id}`)
}

// 模块名称映射（后端返回下划线格式）
const moduleNameMap = {
  'short_video': '短视频脚本',
  'script': '剧本大纲',
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
    'script': 'success',
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, #409EFF 0%, #36D1DC 100%);
  border-radius: 16px;
  padding: 40px;
  margin-bottom: 30px;
  color: #fff;
  
  .welcome-text {
    h1 {
      font-size: 28px;
      margin-bottom: 10px;
    }
    
    p {
      opacity: 0.9;
      font-size: 16px;
      margin-bottom: 16px;
    }
    
    .version-info {
      display: flex;
      align-items: center;
      gap: 12px;
      
      .version-badge {
        background: rgba(255, 255, 255, 0.2);
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 13px;
        font-weight: 500;
      }
      
      .check-update-btn {
        background: rgba(255, 255, 255, 0.95);
        border-color: transparent;
        color: #409EFF;
        font-weight: 500;
        transition: all 0.3s;
        
        &:hover {
          background: #fff;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
      }
    }
  }
  
  .welcome-illustration {
    opacity: 0.3;
  }
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 20px;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
  
  .module-card {
    display: flex;
    align-items: center;
    background: #fff;
    border-radius: 12px;
    padding: 24px;
    cursor: pointer;
    transition: all 0.3s;
    border: 2px solid transparent;
    
    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.1);
      border-color: var(--module-color);
      
      .module-icon {
        background: var(--module-color);
        color: #fff;
      }
      
      .module-action {
        opacity: 1;
        transform: translateX(5px);
      }
    }
    
    .module-icon {
      width: 70px;
      height: 70px;
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(0, 0, 0, 0.05);
      color: var(--module-color);
      transition: all 0.3s;
      flex-shrink: 0;
    }
    
    .module-info {
      flex: 1;
      margin-left: 20px;
      
      h3 {
        font-size: 18px;
        color: #303133;
        margin-bottom: 6px;
      }
      
      p {
        font-size: 13px;
        color: #909399;
      }
    }
    
    .module-action {
      opacity: 0;
      transition: all 0.3s;
      color: var(--module-color);
    }
  }
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 30px;
  
  .action-card {
    background: #fff;
    border-radius: 12px;
    padding: 24px;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s;
    
    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.1);
      
      .el-icon {
        color: #409EFF;
      }
    }
    
    .el-icon {
      color: #909399;
      margin-bottom: 12px;
      transition: color 0.3s;
    }
    
    span {
      display: block;
      font-size: 15px;
      color: #303133;
      margin-bottom: 6px;
    }
    
    p {
      font-size: 12px;
      color: #909399;
    }
  }
}

.recent-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
}
</style>
