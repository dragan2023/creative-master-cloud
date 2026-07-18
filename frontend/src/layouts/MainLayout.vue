<template>
  <el-container class="main-layout">
    <!-- 桌面端侧边栏 -->
    <el-aside v-if="!isMobile" :width="sidebarWidth" class="sidebar">
      <div class="logo">
        <div class="logo-icon-wrapper">
          <img src="/logo.png" alt="全能创意大师" class="logo-img" />
        </div>
        <span v-show="!collapsed" class="logo-text">全能创意大师</span>
      </div>

      <!-- 菜单数据与权限判断统一来自 menuConfig.js -->
      <MainNavMenu :collapsed="collapsed" />

      <!-- 版本信息 -->
      <div v-show="!collapsed" class="sidebar-footer">
        <span class="version-text">v{{ currentVersion }}</span>
      </div>
    </el-aside>

    <!-- 移动端抽屉导航（与桌面端共用同一份菜单数据） -->
    <el-drawer
      v-if="isMobile"
      v-model="mobileMenuVisible"
      direction="ltr"
      size="240px"
      :with-header="false"
      class="mobile-nav-drawer"
    >
      <div class="logo">
        <div class="logo-icon-wrapper">
          <img src="/logo.png" alt="全能创意大师" class="logo-img" />
        </div>
        <span class="logo-text">全能创意大师</span>
      </div>
      <MainNavMenu :collapsed="false" />
      <div class="sidebar-footer">
        <span class="version-text">v{{ currentVersion }}</span>
      </div>
    </el-drawer>
    
    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-button
            text
            class="collapse-btn"
            :aria-label="isMobile ? '打开主导航' : (collapsed ? '展开侧边栏' : '收起侧边栏')"
            @click="handleNavigationToggle"
          >
            <el-icon :size="20">
              <Menu v-if="isMobile" />
              <Fold v-else-if="!collapsed" />
              <Expand v-else />
            </el-icon>
          </el-button>
          
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentTitle">{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <div class="user-info">
              <el-avatar :size="32" class="avatar">
                {{ userStore.userInfo?.username?.charAt(0).toUpperCase() || 'U' }}
              </el-avatar>
              <span class="username">{{ userStore.userInfo?.nickname || userStore.userInfo?.username || '用户' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>个人设置
                </el-dropdown-item>
                <el-dropdown-item v-if="userStore.isSuperAdmin" command="admin">
                  <el-icon><Setting /></el-icon>管理后台
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
                <!-- 退出程序：仅本地桌面运行环境展示（自首页高频操作区迁入） -->
                <el-dropdown-item v-if="isLocalDesktopEnv" divided command="exit" :disabled="exiting">
                  <el-icon><CircleClose /></el-icon>退出程序
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <!-- 内容区 -->
      <el-main class="main-content">
        <!-- 可恢复运行时错误界面：子页面抛出异常时替代路由视图展示 -->
        <RuntimeError
          v-if="runtimeError"
          :error-id="runtimeError.errorId"
          @retry="retryCurrentView"
          @back-home="backToHome"
        />
        <router-view v-else v-slot="{ Component }">
          <!-- key 不含查询参数：查询变化不重挂载；路径变化或点击重试（viewKey 递增）时重新挂载 -->
          <component :is="Component" :key="`${route.path}::${viewKey}`" />
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, provide, onErrorCaptured, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore, useAppStore } from '@/stores'
import { Setting, SwitchButton, CircleClose, Menu, Fold, Expand, ArrowDown, User } from '@element-plus/icons-vue'
import { updateApi } from '@/api'
import { APP_VERSION } from '@/config/version'
import { getToken, getUserInfo } from '@/utils/authStorage'
import RuntimeError from '@/views/error/RuntimeError.vue'
import MainNavMenu from './components/MainNavMenu.vue'
import { useResponsiveLayout } from '@/composables/useResponsiveLayout'
import { useAppExit } from '@/composables/useAppExit'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const appStore = useAppStore()

// 统一响应式布局：断点唯一来源，移动端使用抽屉导航
const { isMobile, mobileMenuVisible, openMobileMenu, closeMobileMenu } = useResponsiveLayout()

// 退出程序：仅本地桌面运行环境展示入口
const { exiting, isLocalDesktopEnv, detectRuntimeEnvironment, confirmAndExit } = useAppExit()

// 当前版本号（从后端API获取，失败时使用本地版本）
const currentVersion = ref(APP_VERSION)

const collapsed = computed(() => appStore.sidebarCollapsed)
const sidebarWidth = computed(() => collapsed.value ? '64px' : '220px')
const currentTitle = computed(() => route.meta.title)

/** 导航开关：移动端打开抽屉，桌面端切换侧栏折叠 */
function handleNavigationToggle() {
  if (isMobile.value) {
    openMobileMenu()
  } else {
    appStore.toggleSidebar()
  }
}

// 获取当前版本号
async function fetchCurrentVersion() {
  try {
    const response = await updateApi.getCurrentVersion()
    currentVersion.value = response?.version || APP_VERSION
  } catch (error) {
    console.error('获取版本信息失败:', error)
    // 保持默认值
  }
}

async function handleCommand(command) {
  if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'admin') {
    router.push('/admin')
  } else if (command === 'logout') {
    userStore.logout()
  } else if (command === 'exit') {
    await confirmAndExit()
  }
}

// 提供给子组件使用
provide('currentVersion', currentVersion)

// 可恢复运行时错误状态：捕获子组件异常后展示错误界面，支持重试重新挂载
const runtimeError = ref(null)
const viewKey = ref(0)

onErrorCaptured((error, instance, info) => {
  const errorId = `UI-${Date.now().toString(36).toUpperCase()}`
  console.error(`[${errorId}]`, error, info)
  runtimeError.value = { errorId }
  // 阻止错误继续传播，防止界面卡死
  return false
})

/** 重试当前页面：清除错误并递增 viewKey 强制重新挂载路由视图 */
function retryCurrentView() {
  runtimeError.value = null
  viewKey.value += 1
}

/** 从错误界面返回首页 */
function backToHome() {
  runtimeError.value = null
  router.push('/')
}

// 路由切换时清除错误状态并关闭移动端抽屉
watch(() => route.path, () => {
  if (runtimeError.value) {
    runtimeError.value = null
  }
  closeMobileMenu()
})

onMounted(async () => {
  await fetchCurrentVersion()
  // 查询运行环境，决定是否展示“退出程序”入口
  detectRuntimeEnvironment()
  
  // 验证用户状态：如果 token 存在但 userInfo 不存在，尝试获取用户信息
  const token = getToken()
  const userInfoData = getUserInfo()
  if (token && !userInfoData) {
    console.log('[MainLayout] 检测到 token 存在但 userInfo 缺失，尝试获取用户信息')
    try {
      await userStore.fetchProfile()
    } catch (error) {
      console.error('[MainLayout] 获取用户信息失败:', error)
      // 如果获取失败，logout 会在 fetchProfile 内部被调用（当返回 401 时）
    }
  }
})
</script>

<style lang="scss" scoped>
.main-layout {
  height: 100%;
}

.sidebar {
  background: linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 4px 0 20px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
  
  // 科技感背景装饰
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: 
      radial-gradient(ellipse at 50% 0%, rgba(64, 158, 255, 0.1) 0%, transparent 50%),
      radial-gradient(ellipse at 50% 100%, rgba(0, 212, 170, 0.08) 0%, transparent 50%);
    pointer-events: none;
  }
  
  .logo {
    height: var(--header-height);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    border-bottom: 1px solid rgba(64, 158, 255, 0.2);
    position: relative;
    z-index: 1;
    
    .logo-icon-wrapper {
      width: 44px;
      height: 44px;
      display: flex;
      align-items: center;
      justify-content: center;
      
      .el-icon {
        color: #fff;
      }
      
      .logo-img {
        width: 36px;
        height: 36px;
        object-fit: contain;
        border-radius: 5px;
      }
    }
    
    .logo-text {
      font-size: 18px;
      font-weight: 700;
      background: linear-gradient(90deg, #fff 0%, #409EFF 50%, #00D4AA 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      white-space: nowrap;
      letter-spacing: 1px;
    }
  }
  
  .sidebar-footer {
    padding: 16px;
    border-top: 1px solid rgba(64, 158, 255, 0.2);
    text-align: center;
    position: relative;
    z-index: 1;
    
    .version-text {
      font-size: 12px;
      color: rgba(255, 255, 255, 0.4);
      letter-spacing: 1px;
    }
  }
}

@keyframes logo-glow {
  0%, 100% {
    box-shadow: 0 4px 15px rgba(64, 158, 255, 0.4);
  }
  50% {
    box-shadow: 0 4px 25px rgba(64, 158, 255, 0.6), 0 0 40px rgba(0, 212, 170, 0.3);
  }
}

.header {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  z-index: 10;
  border-bottom: 1px solid rgba(64, 158, 255, 0.1);
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    
    .collapse-btn {
      padding: 8px;
      border-radius: 8px;
      transition: all 0.3s;
      
      &:hover {
        background: rgba(64, 158, 255, 0.1);
        color: #409EFF;
      }

      &:focus-visible {
        outline: 2px solid var(--primary-color, #409EFF);
        outline-offset: 2px;
      }
    }
    
    :deep(.el-breadcrumb) {
      font-size: 14px;
      
      .el-breadcrumb__item {
        .el-breadcrumb__inner {
          color: #606266;
          font-weight: 500;
          
          &.is-link:hover {
            color: #409EFF;
          }
        }
        
        &:last-child .el-breadcrumb__inner {
          color: #303133;
          font-weight: 600;
        }
      }
    }
  }
  
  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .user-info {
      display: flex;
      align-items: center;
      gap: 10px;
      cursor: pointer;
      padding: 6px 12px;
      border-radius: 24px;
      transition: all 0.3s;
      
      &:hover {
        background: rgba(64, 158, 255, 0.08);
      }
      
      .avatar {
        background: linear-gradient(135deg, #409EFF 0%, #00D4AA 100%);
        font-weight: 600;
        box-shadow: 0 2px 8px rgba(64, 158, 255, 0.3);
      }
      
      .username {
        font-size: 14px;
        color: #303133;
        font-weight: 500;
      }
      
      .el-icon {
        color: #909399;
        transition: transform 0.3s;
      }
      
      &:hover .el-icon {
        transform: rotate(180deg);
      }
    }
  }
}

.main-content {
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  padding: 24px;
  overflow-y: auto;
  min-height: calc(100vh - 60px);
}

@media (max-width: 768px) {
  .header {
    padding: 0 12px;

    // 窄屏下隐藏用户名，避免与面包屑互相挤压
    .header-right .user-info .username {
      display: none;
    }
  }
}
</style>

<style lang="scss">
// 移动端抽屉导航：与桌面端侧栏同一视觉主题（非 scoped：需覆盖 el-drawer 内部结构）
.mobile-nav-drawer {
  background: linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);

  .el-drawer__body {
    display: flex;
    flex-direction: column;
    padding: 0;
  }

  .logo {
    height: var(--header-height);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    border-bottom: 1px solid rgba(64, 158, 255, 0.2);
    flex-shrink: 0;

    .logo-icon-wrapper {
      width: 44px;
      height: 44px;
      display: flex;
      align-items: center;
      justify-content: center;

      .logo-img {
        width: 36px;
        height: 36px;
        object-fit: contain;
        border-radius: 5px;
      }
    }

    .logo-text {
      font-size: 18px;
      font-weight: 700;
      background: linear-gradient(90deg, #fff 0%, #409EFF 50%, #00D4AA 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      white-space: nowrap;
      letter-spacing: 1px;
    }
  }

  .sidebar-footer {
    padding: 16px;
    border-top: 1px solid rgba(64, 158, 255, 0.2);
    text-align: center;
    flex-shrink: 0;

    .version-text {
      font-size: 12px;
      color: rgba(255, 255, 255, 0.4);
      letter-spacing: 1px;
    }
  }
}
</style>
