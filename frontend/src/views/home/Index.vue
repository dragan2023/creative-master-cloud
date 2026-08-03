<template>
  <div class="home-page">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-content">
        <div class="welcome-text">
          <span class="welcome-kicker">CREATIVE STUDIO</span>
          <h1>欢迎回来，{{ userStore.userInfo?.username || '用户' }}</h1>
          <p>让每一个念头，找到它的表达。</p>
          <div class="version-info">
            <span class="version-badge">v{{ currentVersion }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 功能模块卡片 -->
    <div class="modules-section">
      <h2 class="section-title">
        <span class="title-icon"></span>
        创意生成模块
      </h2>

      <!-- API Key 未配置时的醒目提示（在模块选择之前） -->
      <el-alert
        v-if="!onboarding.hasAPIKeys.value"
        title="⚡ 尚未配置 API Key"
        type="warning"
        :closable="false"
        show-icon
        class="api-key-notice"
      >
        <template #default>
          <p>AI 生成功能需要连接大语言模型。配置 API Key 后即可开始创作。</p>
        </template>
        <template #extra>
          <el-button type="primary" size="small" @click="router.push('/api-keys')" aria-label="前往配置 API Key">
            <el-icon><Key /></el-icon>前往配置
          </el-button>
        </template>
      </el-alert>

      <!-- 角色化快捷入口：三个核心目标 -->
      <div class="role-entries">
        <h3 class="role-entries-title">选择您想做的事情：</h3>
        <div class="role-entry-grid">
          <div class="role-entry-card quick" @click="router.push('/generate')" aria-label="快速生成一篇内容">
            <div class="role-entry-icon">
              <el-icon :size="28"><MagicStick /></el-icon>
            </div>
            <div class="role-entry-text">
              <strong>快速生成一篇内容</strong>
              <p>短视频脚本、广告文案、应用文等即时创作</p>
            </div>
            <el-icon class="role-entry-arrow"><ArrowRight /></el-icon>
          </div>
          <div class="role-entry-card project" @click="router.push('/novel-writer')" aria-label="开始长篇项目">
            <div class="role-entry-icon">
              <el-icon :size="28"><Edit /></el-icon>
            </div>
            <div class="role-entry-text">
              <strong>开始长篇项目</strong>
              <p>小说、剧本、剧集等多章节结构化创作</p>
            </div>
            <el-icon class="role-entry-arrow"><ArrowRight /></el-icon>
          </div>
          <div class="role-entry-card import" @click="router.push('/knowledge')" aria-label="导入已有资料">
            <div class="role-entry-icon">
              <el-icon :size="28"><Upload /></el-icon>
            </div>
            <div class="role-entry-text">
              <strong>导入已有资料</strong>
              <p>上传文档、大纲或知识库材料进行加工</p>
            </div>
            <el-icon class="role-entry-arrow"><ArrowRight /></el-icon>
          </div>
        </div>
      </div>

      <div class="module-grid">
        <div
          v-for="module in creativeModules"
          :key="module.key"
          class="module-card"
          :style="{ '--module-color': module.color }"
          @click="goToGenerate(module.key)"
        >
          <div class="card-glow"></div>
          <div class="module-icon">
            <el-icon :size="36">
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
      <h2 class="section-title">
        <span class="title-icon"></span>
        快捷操作
      </h2>
      <div class="action-grid">
        <div class="action-card" @click="router.push('/api-keys')">
          <div class="action-icon">
            <el-icon :size="22"><Key /></el-icon>
          </div>
          <span>API Key管理</span>
          <p>配置您的AI模型密钥</p>
        </div>
        <div class="action-card" @click="router.push('/knowledge')">
          <div class="action-icon">
            <el-icon :size="22"><FolderOpened /></el-icon>
          </div>
          <span>知识库管理</span>
          <p>上传和管理知识文件</p>
        </div>
        <div class="action-card" @click="router.push('/history')">
          <div class="action-icon">
            <el-icon :size="22"><Clock /></el-icon>
          </div>
          <span>历史记录</span>
          <p>查看创作历史</p>
        </div>
        <div class="action-card" @click="router.push('/profile')">
          <div class="action-icon">
            <el-icon :size="22"><User /></el-icon>
          </div>
          <span>个人设置</span>
          <p>管理账户信息</p>
        </div>
      </div>
    </div>
    
    <!-- 退出程序 -->
    <div class="exit-section">
      <el-button 
        type="danger" 
        size="large"
        @click="handleExit"
        :loading="exiting"
        class="exit-btn"
      >
        <el-icon><SwitchButton /></el-icon>
        <span>退出程序</span>
      </el-button>
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
      :onboarding-version="onboarding.onboardingVersion"
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
          <a href="https://space.bilibili.com/" target="_blank">打卤阳春面</a>
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
import { useUserStore } from '@/stores'
import { historyApi, systemApi } from '@/api'
import { CREATIVE_MODULES } from '@/config'
import { ElMessageBox, ElMessage } from 'element-plus'
import { APP_VERSION } from '@/config/version'
import { useOnboarding } from '@/composables/useOnboarding'
import OnboardingDialogs from './components/OnboardingDialogs.vue'
import { ArrowRight, Key, MagicStick, Edit, Upload } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()
const onboarding = useOnboarding()

// 从父组件注入版本号，失败时使用本地版本
const currentVersion = inject('currentVersion', ref(APP_VERSION))

// 用于首页展示的创意模块
const creativeModules = CREATIVE_MODULES
const recentGenerations = ref([])
const exiting = ref(false)

onMounted(async () => {
  await fetchRecentGenerations()
  // 初始化新手引导
  onboarding.initOnboarding()
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

// 退出程序
async function handleExit() {
  try {
    await ElMessageBox.confirm(
      '确定要退出程序吗？\n\n退出后将关闭所有服务，请确保已保存所有工作。',
      '退出确认',
      {
        confirmButtonText: '确定退出',
        cancelButtonText: '取消',
        type: 'warning',
        distinguishCancelAndClose: true
      }
    )
    
    exiting.value = true
    ElMessage.info('正在关闭程序，请稍候...')
    
    try {
      // 调用后端退出接口
      const response = await systemApi.exit()
      
      if (response.success) {
        // 后端已开始退出流程
        ElMessage.success('服务已关闭')
        
        // 尝试关闭窗口
        setTimeout(() => {
          // 尝试关闭当前窗口
          if (window.close) {
            try {
              window.close()
            } catch (e) {
              // 无法通过脚本关闭窗口（浏览器安全限制）
              showManualCloseTip()
            }
          } else {
            showManualCloseTip()
          }
        }, 500)
      }
    } catch (apiError) {
      // API调用失败，可能是后端已经退出导致连接中断
      console.log('后端已关闭:', apiError)
      ElMessage.success('服务已关闭')
      showManualCloseTip()
    }
    
  } catch (error) {
    // 用户取消或关闭对话框
    exiting.value = false
  }
}

// 显示手动关闭提示
function showManualCloseTip() {
  ElMessageBox.alert(
    '服务已成功关闭。\n\n由于浏览器安全限制，无法自动关闭窗口。\n请手动关闭此浏览器窗口或标签页。',
    '退出完成',
    {
      confirmButtonText: '我知道了',
      type: 'success',
      showClose: false,
      closeOnClickModal: false,
      closeOnPressEscape: false
    }
  ).finally(() => {
    exiting.value = false
  })
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
  min-height: 230px;
  padding: 40px;
  margin-bottom: 32px;
  background: #101f35 url('/brand/ink-monkey-banner.png') center / cover no-repeat;
  overflow: hidden;
  box-shadow: 0 12px 32px rgba(18, 27, 43, 0.2);
  
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
    background: linear-gradient(90deg, rgba(9, 22, 39, 0.78) 0%, rgba(11, 29, 47, 0.62) 37%, rgba(11, 29, 47, 0.08) 66%);
    pointer-events: none;
  }
  
  .welcome-text {
    .welcome-kicker {
      display: inline-block;
      color: #efc77d;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.16em;
      margin-bottom: 10px;
    }

    h1 {
      font-size: 28px;
      margin-bottom: 10px;
      font-weight: 700;
      color: #fffaf2;
    }
    
    p {
      opacity: 0.8;
      font-size: 15px;
      color: rgba(250, 242, 230, 0.78);
      margin-bottom: 16px;
    }
    
    .version-info {
      display: flex;
      align-items: center;
      gap: 12px;
      
      .version-badge {
        background: rgba(173, 103, 38, 0.18);
        border: 1px solid rgba(235, 190, 118, 0.34);
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        color: #f5d299;
      }
    }
  }
}

@media (max-width: 768px) {
  .welcome-section {
    min-height: 210px;
    padding: 30px 24px;
    background-position: 62% center;

    .welcome-text h1 {
      font-size: 24px;
    }
  }
}

/* API Key 未配置通知 */
.api-key-notice {
  margin-bottom: 20px;
  border-radius: var(--radius-lg);

  :deep(.el-alert__title) {
    font-size: 15px;
    font-weight: 600;
  }

  p {
    margin: 4px 0 0;
    font-size: 13px;
    color: var(--text-secondary);
  }
}

/* 角色化快捷入口 */
.role-entries {
  margin-bottom: 24px;

  .role-entries-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 14px;
  }

  .role-entry-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;

    @media (max-width: 768px) {
      grid-template-columns: 1fr;
    }
  }

  .role-entry-card {
    display: flex;
    align-items: center;
    gap: 14px;
    background: #fff;
    border-radius: 14px;
    padding: 20px 22px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid rgba(64, 158, 255, 0.08);
    position: relative;
    overflow: hidden;

    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 24px rgba(64, 158, 255, 0.12);

      .role-entry-arrow {
        opacity: 1;
        transform: translateX(4px);
      }

      .role-entry-icon {
        transform: scale(1.08);
      }
    }

    &.quick .role-entry-icon {
      background: rgba(249, 115, 22, 0.1);
      color: var(--color-tangerine-500);
    }

    &.project .role-entry-icon {
      background: rgba(99, 102, 241, 0.1);
      color: var(--color-indigo-500);
    }

    &.import .role-entry-icon {
      background: rgba(5, 150, 105, 0.1);
      color: var(--color-success);
    }

    .role-entry-icon {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.3s;
      flex-shrink: 0;
    }

    .role-entry-text {
      flex: 1;

      strong {
        display: block;
        font-size: 15px;
        color: var(--text-primary);
        margin-bottom: 4px;
      }

      p {
        font-size: 12px;
        color: var(--text-secondary);
        margin: 0;
        line-height: 1.4;
      }
    }

    .role-entry-arrow {
      opacity: 0.3;
      color: var(--text-secondary);
      transition: all 0.3s;
      flex-shrink: 0;
    }
  }
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
    border-radius: 16px;
    padding: 24px;
    cursor: pointer;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid rgba(64, 158, 255, 0.1);
    overflow: hidden;
    
    .card-glow {
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(64, 158, 255, 0.05), rgba(0, 212, 170, 0.05));
      opacity: 0;
      transition: opacity 0.4s;
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
    border-radius: 14px;
    padding: 24px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid rgba(64, 158, 255, 0.08);
    
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
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 32px;
  border: 1px solid rgba(64, 158, 255, 0.08);
}

.exit-section {
  text-align: center;
  padding: 20px 0;
  margin-bottom: 32px;
  
  .exit-btn {
    min-width: 180px;
    height: 48px;
    font-size: 15px;
    border-radius: 12px;
    background: linear-gradient(135deg, #f56c6c, #e6a23c);
    border: none;
    box-shadow: 0 4px 16px rgba(245, 108, 108, 0.3);
    transition: all 0.3s;
    
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 24px rgba(245, 108, 108, 0.4);
    }
    
    .el-icon {
      margin-right: 8px;
    }
  }
}

.resources-section {
  background: #fff;
  border-radius: 16px;
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
      border-radius: 12px;
      text-decoration: none;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      cursor: pointer;
      position: relative;
      overflow: hidden;
      
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
</style>
