<!--
  场景内容查看对话框组件
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="sceneTitle"
    width="800px"
    destroy-on-close
    class="scene-dialog"
  >
    <div v-if="scene" class="scene-content">
      <div class="scene-meta-info">
        <el-tag :type="getSceneStatusType(scene.status)">
          {{ getSceneStatusLabel(scene.status) }}
        </el-tag>
        <span v-if="scene.word_count > 0">
          <el-icon><Document /></el-icon>
          {{ scene.word_count }} 字
        </span>
        <span v-if="scene.token_count > 0">
          <el-icon><Coin /></el-icon>
          {{ formatNumber(scene.token_count) }} tokens
        </span>
      </div>
      <el-divider />
      <div class="content-body">
        <pre v-if="scene.final_content">{{ scene.final_content }}</pre>
        <el-empty v-else description="暂无内容" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { Document, Coin } from '@element-plus/icons-vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  scene: {
    type: Object,
    default: null
  },
  sceneTitle: {
    type: String,
    default: ''
  }
})

defineEmits(['update:visible'])

function getSceneStatusType(status) {
  const typeMap = {
    pending: 'info',
    writing: 'primary',
    reviewing: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return typeMap[status] || 'info'
}

function getSceneStatusLabel(status) {
  const labelMap = {
    pending: '等待中',
    writing: '写作中',
    reviewing: '审阅中',
    completed: '已完成',
    failed: '失败'
  }
  return labelMap[status] || status
}

function formatNumber(num) {
  if (!num) return '0'
  return num.toLocaleString()
}
</script>

<style lang="scss" scoped>
.scene-dialog {
  .scene-content {
    .scene-meta-info {
      display: flex;
      gap: 16px;
      align-items: center;
      margin-bottom: 12px;

      span {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        color: #606266;

        .el-icon {
          color: #409eff;
        }
      }
    }

    .content-body {
      max-height: 500px;
      overflow-y: auto;
      padding: 16px;
      background: #f5f7fa;
      border-radius: 8px;

      pre {
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
        font-family: inherit;
        font-size: 14px;
        line-height: 1.8;
        color: #303133;
      }
    }
  }
}
</style>
