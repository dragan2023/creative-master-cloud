<template>
  <el-card class="knowledge-base-panel">
    <template #header>
      <div class="panel-header">
        <span>知识库</span>
        <el-button size="small" :icon="Refresh" @click="$emit('refresh')" :loading="loadingStatus" text />
      </div>
    </template>

    <!-- 未构建状态 -->
    <div v-if="!kbStatus || kbStatus.status === 'not_built'" class="kb-status not-built">
      <el-empty description="知识库未构建" :image-size="60" />
      <el-button type="primary" @click="$emit('build')" :loading="building" :disabled="!hasOutline">
        构建知识库
      </el-button>
      <div v-if="!hasOutline" class="kb-tip">请先上传大纲</div>
    </div>

    <!-- 构建中状态 -->
    <div v-else-if="kbStatus.status === 'building'" class="kb-status building">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>知识库构建中...</span>
      <el-progress :percentage="kbStatus.progress || 0" :stroke-width="6" />
    </div>

    <!-- 已就绪状态 -->
    <div v-else-if="kbStatus.status === 'ready'" class="kb-status ready">
      <el-tag type="success">已就绪</el-tag>
      <div class="kb-stats">
        <span>文档: {{ kbStatus.document_count || 0 }}</span>
        <span>实体: {{ kbStatus.entity_count || 0 }}</span>
      </div>
      <div class="kb-actions">
        <el-button size="small" @click="$emit('show-graph')">查看图谱</el-button>
        <el-button size="small" type="warning" @click="$emit('rebuild-global')" :loading="building">重建</el-button>
        <el-button size="small" type="danger" @click="$emit('delete')">删除</el-button>
      </div>
    </div>

    <!-- 构建失败状态 -->
    <div v-else-if="kbStatus.status === 'error'" class="kb-status error">
      <el-tag type="danger">构建失败</el-tag>
      <p class="error-msg">{{ kbStatus.error_message || '未知错误' }}</p>
      <el-button size="small" type="primary" @click="$emit('build')" :loading="building">重试</el-button>
    </div>

    <!-- 重置中 -->
    <div v-else-if="resetting" class="kb-status">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>重置中...</span>
    </div>
  </el-card>
</template>

<script setup>
import { Refresh, Loading } from '@element-plus/icons-vue'

defineProps({
  kbStatus: { type: Object, default: null },
  hasOutline: { type: Boolean, default: false },
  loadingStatus: { type: Boolean, default: false },
  building: { type: Boolean, default: false },
  resetting: { type: Boolean, default: false }
})

defineEmits(['refresh', 'build', 'reset', 'delete', 'rebuild-global', 'show-graph', 'unit-graph-command'])
</script>

<style lang="scss" scoped>
.knowledge-base-panel {
  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .kb-status {
    text-align: center;
    padding: 12px 0;
  }

  .kb-stats {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin: 8px 0;
    font-size: 13px;
    color: #606266;
  }

  .kb-actions {
    display: flex;
    justify-content: center;
    gap: 8px;
    margin-top: 8px;
  }

  .kb-tip {
    font-size: 12px;
    color: #e6a23c;
    margin-top: 8px;
  }

  .error-msg {
    font-size: 12px;
    color: #f56c6c;
    margin: 8px 0;
  }
}
</style>
