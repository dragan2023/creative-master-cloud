<template>
  <el-container class="main-layout">
    <!-- 侧边栏 -->
    <el-aside :width="sidebarWidth" class="sidebar">
      <div class="logo">
        <div class="logo-icon-wrapper">
          <img src="/brand/ink-monkey-logo.png" alt="全能创意大师水墨金丝猴标志" class="logo-img" />
        </div>
        <span v-show="!collapsed" class="logo-text">全能创意大师</span>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <template #title>首页</template>
        </el-menu-item>
        
        <el-menu-item index="/generate">
          <el-icon><MagicStick /></el-icon>
          <template #title>创意生成</template>
        </el-menu-item>
        
        <el-menu-item index="/api-keys">
          <el-icon><Key /></el-icon>
          <template #title>API Key管理</template>
        </el-menu-item>
        
        <el-menu-item index="/knowledge">
          <el-icon><FolderOpened /></el-icon>
          <template #title>知识库</template>
        </el-menu-item>
        
        <el-menu-item index="/novel-writer">
          <el-icon><Edit /></el-icon>
          <template #title>小说/剧本生成</template>
        </el-menu-item>
        
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon>
          <template #title>历史记录</template>
        </el-menu-item>
        
        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <template #title>个人设置</template>
        </el-menu-item>
        
        <!-- 超级管理员入口 -->
        <el-menu-item v-if="userStore.isSuperAdmin" index="/admin">
          <el-icon><Setting /></el-icon>
          <template #title>管理后台</template>
        </el-menu-item>
      </el-menu>
      
      <!-- 版本信息 -->
      <div v-show="!collapsed" class="sidebar-footer">
        <span class="version-text">v{{ currentVersion }}</span>
      </div>
    </el-aside>
    
    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-button 
            text 
            @click="toggleSidebar"
            class="collapse-btn"
          >
            <el-icon :size="20">
              <Fold v-if="!collapsed" />
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
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <!-- 内容区 -->
      <el-main class="main-content">
        <router-view v-slot="{ Component, route }">
          <component :is="Component" :key="route.fullPath" />
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, provide, onErrorCaptured } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore, useAppStore } from '@/stores'
import { DocumentChecked, Setting, SwitchButton } from '@element-plus/icons-vue'
import { updateApi } from '@/api'
import { APP_VERSION } from '@/config/version'
import { getToken, getUserInfo } from '@/utils/authStorage'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const appStore = useAppStore()

// 当前版本号（从后端API获取，失败时使用本地版本）
const currentVersion = ref(APP_VERSION)

const collapsed = computed(() => appStore.sidebarCollapsed)
const sidebarWidth = computed(() => collapsed.value ? '64px' : '220px')
const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta.title)

function toggleSidebar() {
  appStore.toggleSidebar()
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
  }
}

// 提供给子组件使用
provide('currentVersion', currentVersion)

// 全局错误捕获：捕获子组件的错误，防止导致界面卡死
onErrorCaptured((error, instance, info) => {
  console.error('[MainLayout] 捕获到组件错误:', error, info)
  // 返回 false 阻止错误继续传播
  return false
})

onMounted(async () => {
  await fetchCurrentVersion()
  
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
  background: linear-gradient(180deg, #101a2e 0%, #17243a 58%, #1f2633 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 4px 0 20px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background:
      radial-gradient(ellipse at 0% 0%, rgba(211, 150, 75, 0.13) 0%, transparent 45%),
      radial-gradient(ellipse at 80% 100%, rgba(74, 99, 142, 0.18) 0%, transparent 54%);
    pointer-events: none;
  }
  
  .logo {
    height: var(--header-height);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    border-bottom: 1px solid rgba(236, 199, 132, 0.18);
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
        width: 38px;
        height: 38px;
        object-fit: cover;
        object-position: 50% 38%;
        border-radius: 10px;
        box-shadow: 0 5px 14px rgba(0, 0, 0, 0.28);
      }
    }
    
    .logo-text {
      font-size: 18px;
      font-weight: 700;
      color: #f8f0e5;
      white-space: nowrap;
      letter-spacing: 1px;
    }
  }
  
  .sidebar-menu {
    flex: 1;
    border-right: none;
    background: transparent;
    position: relative;
    z-index: 1;
    padding: 8px 0;
    
    :deep(.el-menu-item) {
      color: rgba(255, 255, 255, 0.7);
      margin: 4px 8px;
      border-radius: 8px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      overflow: hidden;
      
      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 3px;
        background: #d99a50;
        transform: scaleY(0);
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      }
      
      &:hover {
        background: rgba(211, 150, 75, 0.14);
        color: #fff;
        transform: translateX(4px);
        
        &::before {
          transform: scaleY(1);
        }
      }
      
      &.is-active {
        background: linear-gradient(90deg, rgba(190, 127, 52, 0.28) 0%, rgba(190, 127, 52, 0.04) 100%);
        color: #fff;
        box-shadow: 0 4px 15px rgba(20, 24, 35, 0.24);
        
        &::before {
          transform: scaleY(1);
        }
        
        .el-icon {
          color: #efc07a;
        }
      }
      
      .el-icon {
        font-size: 18px;
        transition: all 0.3s;
      }
    }
  }
  
  .sidebar-footer {
    padding: 16px;
    border-top: 1px solid rgba(236, 199, 132, 0.18);
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
</style>
