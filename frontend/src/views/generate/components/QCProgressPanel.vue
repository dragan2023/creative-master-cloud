<template>
  <div v-if="qcProgress" class="qc-progress-panel" style="margin-top: 20px;">
    <el-card shadow="hover">
      <template #header>
        <div class="progress-header">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>质量检测进行中...</span>
        </div>
      </template>
      <div class="progress-content">
        <el-progress
          :percentage="qcProgress.progress || 0"
          :stroke-width="20"
          :text-inside="true"
          :color="getProgressColor(qcProgress.progress)"
          style="margin-bottom: 16px;"
        />
        <div class="progress-status">
          <el-tag :type="getProgressStatusType(qcProgress.status)">
            {{ qcProgress.message || '正在分析...' }}
          </el-tag>
          <span v-if="qcProgress.dimension" style="margin-left: 8px; color: #909399;">
            当前维度: {{ getDimensionName(qcProgress.dimension) }}
          </span>
        </div>
        <el-alert
          v-if="isReconnecting"
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 12px;"
        >
          <template #title>
            <el-icon class="is-loading" style="margin-right: 4px;"><Loading /></el-icon>
            {{ reconnectMessage }}
          </template>
        </el-alert>
        <div v-if="qcProgress.data?.dimensions" class="dimension-progress" style="margin-top: 16px;">
          <el-row :gutter="8">
            <el-col :span="6" v-for="dim in qcProgress.data.dimensions" :key="dim">
              <el-tag size="small" type="info">{{ getDimensionName(dim) }}</el-tag>
            </el-col>
          </el-row>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { getProgressColor, getProgressStatusType, getDimensionName } from '@/views/generate/utils/qcHelpers'

const props = defineProps({
  qcProgress: { type: Object, default: null }
})

const isReconnecting = computed(() => {
  return props.qcProgress?.status === 'reconnecting'
})

const reconnectMessage = computed(() => {
  return props.qcProgress?.message || '连接中断，正在重连...'
})
</script>
