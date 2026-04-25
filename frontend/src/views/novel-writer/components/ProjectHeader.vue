<template>
  <div class="project-header" v-if="project">
    <div class="header-left">
      <el-button :icon="ArrowLeft" @click="onBack" text>返回</el-button>
      <h3 class="project-title">{{ project.title || '未命名项目' }}</h3>
    </div>
    <div class="header-right">
      <el-button :icon="Setting" @click="onSettings" text>设置</el-button>
      <el-button :icon="Download" @click="onExport" text>导出</el-button>
      <el-dropdown trigger="click">
        <el-button :icon="MoreFilled" text />
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="onSyncContentStatus">同步内容状态</el-dropdown-item>
            <el-dropdown-item @click="onClearAllOutlines">清空所有大纲</el-dropdown-item>
            <el-dropdown-item @click="onClearAllContent">清空所有内容</el-dropdown-item>
            <el-dropdown-item @click="onClearAll" divided>清空全部</el-dropdown-item>
            <el-dropdown-item @click="onDelete" divided style="color: #f56c6c;">删除项目</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { ArrowLeft, Setting, Download, MoreFilled } from '@element-plus/icons-vue'

defineProps({
  project: { type: Object, default: null },
  onBack: { type: Function, default: null },
  onSettings: { type: Function, default: null },
  onExport: { type: Function, default: null },
  onSyncContentStatus: { type: Function, default: null },
  onClearAllOutlines: { type: Function, default: null },
  onClearAllContent: { type: Function, default: null },
  onClearAll: { type: Function, default: null },
  onDelete: { type: Function, default: null }
})
</script>

<style lang="scss" scoped>
.project-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  margin-bottom: 12px;
  border-bottom: 1px solid #eee;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .project-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}
</style>
