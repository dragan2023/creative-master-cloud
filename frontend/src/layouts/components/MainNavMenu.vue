<template>
  <el-menu
    :default-active="activeMenu"
    :collapse="collapsed"
    :collapse-transition="false"
    router
    class="sidebar-menu"
  >
    <el-menu-item v-for="item in visibleMenuItems" :key="item.path" :index="item.path">
      <el-icon><component :is="resolveElementIcon(item.icon)" /></el-icon>
      <template #title>{{ item.title }}</template>
    </el-menu-item>
  </el-menu>
</template>

<script setup>
/**
 * 主导航菜单渲染组件
 * 桌面端侧栏与移动端抽屉共用，菜单数据与权限判断统一来自 menuConfig.js
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores'
import { getVisibleMenuItems } from '../menuConfig'
import { resolveElementIcon } from '@/utils/elementIcons'

defineProps({
  collapsed: {
    type: Boolean,
    default: false
  }
})

const route = useRoute()
const userStore = useUserStore()

const activeMenu = computed(() => route.path)
const visibleMenuItems = computed(() => getVisibleMenuItems(userStore.isSuperAdmin))
</script>

<style lang="scss" scoped>
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
      background: linear-gradient(180deg, #409EFF, #00D4AA);
      transform: scaleY(0);
      transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    &:hover {
      background: rgba(64, 158, 255, 0.15);
      color: #fff;
      transform: translateX(4px);

      &::before {
        transform: scaleY(1);
      }
    }

    &:focus-visible {
      outline: 2px solid #409EFF;
      outline-offset: -2px;
    }

    &.is-active {
      background: linear-gradient(90deg, rgba(64, 158, 255, 0.3) 0%, rgba(0, 212, 170, 0.1) 100%);
      color: #fff;
      box-shadow: 0 4px 15px rgba(64, 158, 255, 0.2);

      &::before {
        transform: scaleY(1);
      }

      .el-icon {
        color: #409EFF;
      }
    }

    .el-icon {
      font-size: 18px;
      transition: all 0.3s;
    }
  }
}
</style>
