<!--
  组件: SceneContentDialog
  场景内容查看弹窗
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="title"
    width="800px"
    top="5vh"
    destroy-on-close
    class="scene-dialog"
  >
    <div v-if="scene" class="scene-content">
      <div class="scene-meta-info">
        <el-tag :type="statusType">
          {{ statusLabel }}
        </el-tag>
        <span v-if="scene.word_count > 0">
          <el-icon><Document /></el-icon>
          {{ scene.word_count }} 字
        </span>
        <span v-if="scene.token_count > 0">
          <el-icon><Coin /></el-icon>
          {{ formattedTokens }} tokens
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
import { computed } from 'vue'
import { Document, Coin } from '@element-plus/icons-vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  scene: { type: Object, default: null },
  title: { type: String, default: '' },
  statusType: { type: String, default: 'info' },
  statusLabel: { type: String, default: '' }
})

defineEmits(['update:visible'])

const formattedTokens = computed(() => {
  if (!props.scene?.token_count) return '0'
  return props.scene.token_count.toLocaleString()
})
</script>

<style lang="scss" scoped>
.scene-content {
  .scene-meta-info {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .content-body {
    max-height: 60vh;
    overflow-y: auto;
    padding: 16px;
    background: #f9f9f9;
    border-radius: 6px;

    pre {
      white-space: pre-wrap;
      word-wrap: break-word;
      word-break: break-all;
      overflow-wrap: break-word;
      font-family: inherit;
      line-height: 1.8;
      font-size: 14px;
      color: #303133;
      margin: 0;
    }
  }
}
</style>
