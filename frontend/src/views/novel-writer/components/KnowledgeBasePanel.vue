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
      <div class="kb-actions">
        <el-button
          type="primary"
          size="small"
          :disabled="!hasOutline"
          :loading="building"
          @click="$emit('build')"
        >
          构建知识库
        </el-button>
      </div>
      <div v-if="!hasOutline" class="kb-tip">请先上传大纲</div>
    </div>

    <!-- 构建中状态（P1增强：进度细分+预估时间） -->
    <div v-else-if="kbStatus.status === 'building'" class="kb-status building">
      <div class="kb-build-detail">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span class="stage-message">{{ kbStatus.progress?.message || '知识库构建中...' }}</span>
      </div>
      <el-progress
        :percentage="kbStatus.progress?.progress || 0"
        :stroke-width="8"
        :format="(p) => p + '%'"
      />
      <div class="kb-build-info">
        <span class="estimated-time">
          <el-icon><Timer /></el-icon>
          {{ kbStatus.progress?.estimated_remaining || '计算中...' }}
        </span>
      </div>
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
        <el-button size="small" type="warning" :loading="building" @click="$emit('rebuild-global')">重建知识库</el-button>
        <el-button size="small" type="danger" @click="$emit('delete')">删除</el-button>
      </div>
    </div>

    <!-- 构建失败状态 -->
    <div v-else-if="kbStatus.status === 'error'" class="kb-status error">
      <el-tag type="danger">构建失败</el-tag>
      <p class="error-msg">{{ kbStatus.error_message || '未知错误' }}</p>
      <div class="kb-tip">
        请前往创意生成页面重新构建知识图谱
      </div>
    </div>

    <!-- 重置中 -->
    <div v-else-if="resetting" class="kb-status">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>重置中...</span>
    </div>
  </el-card>
</template>

<script setup>
import { Refresh, Loading, Timer } from '@element-plus/icons-vue'

defineProps({
  kbStatus: { type: Object, default: null },
  hasOutline: { type: Boolean, default: false },
  loadingStatus: { type: Boolean, default: false },
  building: { type: Boolean, default: false },
  resetting: { type: Boolean, default: false }
})

defineEmits(['refresh', 'reset', 'delete', 'show-graph', 'unit-graph-command', 'build', 'rebuild-global'])
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

  // P1增强：进度显示样式
  .kb-build-detail {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-bottom: 12px;

    .stage-message {
      font-size: 14px;
      color: #409eff;
    }
  }

  .kb-build-info {
    display: flex;
    justify-content: center;
    margin-top: 8px;

    .estimated-time {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: #909399;
    }
  }

  .error-msg {
    font-size: 12px;
    color: #f56c6c;
    margin: 8px 0;
  }
}
</style>
