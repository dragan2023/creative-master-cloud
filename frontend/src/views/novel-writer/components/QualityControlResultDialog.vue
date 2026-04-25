<template>
  <el-dialog v-model="dialogVisible" title="质控检测结果" width="700px" destroy-on-close>
    <div v-if="loading" class="qc-loading">
      <el-skeleton :rows="6" animated />
    </div>
    <div v-else-if="effectiveReport" class="qc-result">
      <div class="qc-score">
        <el-progress type="dashboard" :percentage="effectiveReport.overall_score || effectiveReport.score || 0" :color="scoreColor" :width="120">
          <template #default="{ percentage }">
            <span class="score-value">{{ percentage }}</span>
          </template>
        </el-progress>
        <div class="score-label">综合得分</div>
      </div>

      <el-divider />

      <!-- 消息提示 -->
      <el-alert v-if="message" :title="message" type="info" :closable="false" show-icon style="margin-bottom: 12px;" />

      <!-- 修正概要 -->
      <div v-if="revisionSummary && revisionSummary.length" class="revision-summary">
        <h4>修正概要 ({{ revisedCount }}处修正)</h4>
        <el-timeline>
          <el-timeline-item
            v-for="(rev, idx) in revisionSummary"
            :key="idx"
            :type="getRevisionType(rev.type)"
          >
            <div class="revision-item">
              <span class="rev-location">{{ rev.location || `修正 #${idx + 1}` }}</span>
              <span class="rev-type">{{ rev.type || '修改' }}</span>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>

      <div v-if="effectiveReport.issues && effectiveReport.issues.length" class="qc-issues">
        <h4>检测到的问题 ({{ effectiveReport.issues.length }})</h4>
        <el-collapse>
          <el-collapse-item v-for="(issue, idx) in effectiveReport.issues" :key="idx" :name="idx">
            <template #title>
              <div class="issue-header">
                <el-tag :type="getSeverityType(issue.severity)" size="small">{{ issue.severity }}</el-tag>
                <span class="issue-dimension">{{ issue.dimension }}</span>
                <span class="issue-desc">{{ issue.description?.slice(0, 50) }}...</span>
              </div>
            </template>
            <div class="issue-detail">
              <p>{{ issue.description }}</p>
              <p v-if="issue.suggestion"><strong>建议:</strong> {{ issue.suggestion }}</p>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
      <el-empty v-else description="未检测到问题" />
    </div>
    <el-empty v-else description="暂无质控结果" />
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  report: { type: Object, default: null },
  qualityReport: { type: Object, default: null },
  revisionSummary: { type: Array, default: () => [] },
  revisedCount: { type: Number, default: 0 },
  message: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

// 兼容两种prop命名: report 和 qualityReport
const effectiveReport = computed(() => props.qualityReport || props.report)

const scoreColor = computed(() => {
  const s = effectiveReport.value?.overall_score || effectiveReport.value?.score || 0
  if (s >= 80) return '#67c23a'
  if (s >= 60) return '#e6a23c'
  return '#f56c6c'
})

const getRevisionType = (type) => {
  if (type === 'replace' || type === '修改') return 'warning'
  if (type === 'insert' || type === '新增') return 'success'
  if (type === 'delete' || type === '删除') return 'danger'
  return 'primary'
}

const getSeverityType = (severity) => {
  if (severity === 'high' || severity === '严重') return 'danger'
  if (severity === 'medium' || severity === '中等') return 'warning'
  return 'info'
}
</script>

<style lang="scss" scoped>
.qc-result {
  .qc-score {
    text-align: center;
    padding: 16px 0;

    .score-value { font-size: 28px; font-weight: 700; }
    .score-label { font-size: 13px; color: #909399; margin-top: 4px; }
  }

  .revision-summary {
    h4 { margin-bottom: 12px; }

    .revision-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;

      .rev-location { font-weight: 500; }
      .rev-type { color: #909399; font-size: 12px; }
    }
  }

  .qc-issues {
    h4 { margin-bottom: 12px; }

    .issue-header {
      display: flex;
      align-items: center;
      gap: 8px;

      .issue-dimension { font-weight: 500; }
      .issue-desc { color: #909399; font-size: 13px; }
    }

    .issue-detail {
      padding: 8px 0;
      font-size: 13px;
      line-height: 1.6;
    }
  }
}
</style>
