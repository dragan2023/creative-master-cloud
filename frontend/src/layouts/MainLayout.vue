<template>
  <el-container class="main-layout">
    <!-- 侧边栏 -->
    <el-aside :width="sidebarWidth" class="sidebar">
      <div class="logo">
        <el-icon :size="28" color="#409EFF"><MagicStick /></el-icon>
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
        
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon>
          <template #title>历史记录</template>
        </el-menu-item>
        
        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <template #title>个人设置</template>
        </el-menu-item>
      </el-menu>
      
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
          <!-- 检查更新按钮 -->
          <el-tooltip content="检查更新" placement="bottom">
            <el-button 
              text 
              circle
              :loading="checkingUpdate"
              @click="handleCheckUpdate"
              class="update-btn"
            >
              <el-icon :size="18"><Refresh /></el-icon>
            </el-button>
          </el-tooltip>
          
          <el-dropdown @command="handleCommand">
            <div class="user-info">
              <el-avatar :size="32" class="avatar">
                {{ userStore.userInfo?.username?.charAt(0).toUpperCase() || 'U' }}
              </el-avatar>
              <span class="username">{{ userStore.userInfo?.username || '用户' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>个人设置
                </el-dropdown-item>
                <el-dropdown-item command="checkUpdate">
                  <el-icon><Refresh /></el-icon>检查更新
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
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
    
    <!-- 更新检查组件 -->
    <UpdateChecker
      ref="updateCheckerRef"
      :auto-check="true"
      :auto-check-delay="5"
      :current-version="currentVersion"
      :show-manual-check="false"
      @update-available="onUpdateAvailable"
      @no-update="onNoUpdate"
    />
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore, useAppStore } from '@/stores'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import UpdateChecker from '@/components/UpdateChecker.vue'
import { updateApi } from '@/api'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const appStore = useAppStore()

// 更新检查相关
const updateCheckerRef = ref(null)
const checkingUpdate = ref(false)
const currentVersion = ref('1.0.0')

const collapsed = computed(() => appStore.sidebarCollapsed)
const sidebarWidth = computed(() => collapsed.value ? '64px' : '220px')
const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta.title)

function toggleSidebar() {
  appStore.toggleSidebar()
}

// 获取当前版本
async function fetchCurrentVersion() {
  try {
    const response = await updateApi.getCurrentVersion()
    currentVersion.value = response.data?.version || '1.0.0'
  } catch (error) {
    console.error('获取版本信息失败:', error)
  }
}

// 手动检查更新
async function handleCheckUpdate() {
  checkingUpdate.value = true
  try {
    if (updateCheckerRef.value) {
      await updateCheckerRef.value.checkUpdate()
    }
  } finally {
    checkingUpdate.value = false
  }
}

// 发现新版本回调
function onUpdateAvailable(updateInfo) {
  console.log('发现新版本:', updateInfo)
}

// 无新版本回调  
function onNoUpdate() {
  ElMessage.success('当前已是最新版本')
}

async function handleCommand(command) {
  if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'checkUpdate') {
    await handleCheckUpdate()
  } else if (command === 'logout') {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      type: 'warning'
    })
    userStore.logout()
    router.push('/login')
  }
}

// 提供给子组件使用
provide('checkUpdate', handleCheckUpdate)
provide('checkingUpdate', checkingUpdate)
provide('currentVersion', currentVersion)

onMounted(() => {
  fetchCurrentVersion()
})
</script>

<style lang="scss" scoped>
.main-layout {
  height: 100%;
}

.sidebar {
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  
  .logo {
    height: var(--header-height);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    
    .logo-text {
      font-size: 18px;
      font-weight: 600;
      color: #fff;
      white-space: nowrap;
    }
  }
  
  .sidebar-menu {
    flex: 1;
    border-right: none;
    background: transparent;
    
    :deep(.el-menu-item) {
      color: rgba(255, 255, 255, 0.7);
      
      &:hover {
        background: rgba(255, 255, 255, 0.1);
        color: #fff;
      }
      
      &.is-active {
        background: linear-gradient(90deg, #409EFF 0%, transparent 100%);
        color: #fff;
      }
    }
  }
}

.header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  z-index: 10;
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 15px;
    
    .collapse-btn {
      padding: 8px;
    }
  }
  
  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .update-btn {
      margin-right: 8px;
      
      &:hover {
        color: #409EFF;
      }
    }
    
    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      
      .avatar {
        background: linear-gradient(135deg, #409EFF, #36D1DC);
      }
      
      .username {
        font-size: 14px;
        color: #303133;
      }
    }
  }
}

.main-content {
  background: #f5f7fa;
  padding: 20px;
  overflow-y: auto;
}
</style>
