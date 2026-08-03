<!--
  组件: IssuesDetailDialog
  质控审阅界面 - 展示"原文/建议/原因"三列，支持逐项应用/跳过/撤销与批量操作

  Phase 02 重构：从旧版折叠列表升级为统一审阅界面
  - 统一审阅项卡片（原文/建议/原因）
  - 逐项操作（应用/跳过/撤销）
  - 批量操作（应用低风险项、全部撤销）
  - 知识来源标注（知识库驱动 vs 模型推断）
  - 操作版本关联（版本号 + 质控报告ID）

  @date: 2026-07-24
  @version: v2.0 (Phase 02)
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="审阅问题详情"
    :width="dialogWidth"
    top="3vh"
    class="issues-review-dialog"
  >
    <!-- 顶部统计栏 -->
    <div class="review-toolbar">
      <div class="toolbar-stats">
        <el-tag type="danger" size="small">
          严重 {{ criticalCount }}
        </el-tag>
        <el-tag type="warning" size="small">
          重要 {{ majorCount }}
        </el-tag>
        <el-tag type="info" size="small">
          建议 {{ minorCount }}
        </el-tag>
        <el-tag v-if="appliedCount > 0" type="success" size="small">
          已应用 {{ appliedCount }}
        </el-tag>
        <span v-if="affectedChapters > 0" class="affected-info">
          影响 {{ affectedChapters }} 个章节
        </span>
      </div>

      <!-- 批量操作按钮 -->
      <div class="toolbar-actions">
        <el-button
          v-if="lowRiskPendingCount > 0"
          type="success"
          size="small"
          :disabled="!hasLowRiskContent"
          @click="handleBatchApplyLowRisk"
        >
          <el-icon><Select /></el-icon>
          应用所有低风险项 ({{ lowRiskPendingCount }})
        </el-button>
        <el-button
          v-if="appliedCount > 0"
          type="warning"
          size="small"
          @click="handleBatchUndo"
        >
          <el-icon><RefreshLeft /></el-icon>
          全部撤销
        </el-button>
      </div>
    </div>

    <!-- 审阅项列表 -->
    <div class="review-items-list">
      <ReviewItemCard
        v-for="(item, idx) in normalizedItems"
        :key="item.issue_id || idx"
        :item="item"
        :applying="applyingIssueId === item.issue_id"
        :show-actions="true"
        @apply="handleApplyItem"
        @skip="handleSkipItem"
        @undo="handleUndoItem"
      />
      <el-empty v-if="normalizedItems.length === 0" description="暂无审阅项" />
    </div>

    <!-- 底部版本信息 -->
    <div v-if="revisionVersionId" class="version-footer">
      <el-text type="info" size="small">
        本次修订版本: {{ revisionVersionId }}
        <template v-if="qcReportId">
          · 关联质控报告: #{{ qcReportId }}
        </template>
      </el-text>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Select, RefreshLeft } from '@element-plus/icons-vue'
import ReviewItemCard from './ReviewItemCard.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  qualityReport: { type: Object, default: null },
  applyingFixIndex: { type: Number, default: -1 }
})

const emit = defineEmits(['update:visible', 'apply-fix', 'feedback'])

// 响应式状态
const itemStatuses = ref({})  // { issue_id: 'pending' | 'applied' | 'skipped' | 'reverted' }
const applyingIssueId = ref(null)
const revisionVersionId = ref(null)

/** 弹窗宽度：桌面三列宽、窄屏自适应 */
const dialogWidth = computed(() => {
  if (typeof window === 'undefined') return '900px'
  return window.innerWidth < 768 ? '95%' : '1000px'
})

/** 质控报告ID */
const qcReportId = computed(() => {
  return props.qualityReport?.id || props.qualityReport?.report_id || null
})

/** 标准化审阅项：将旧版 issue 转为统一格式 */
const normalizedItems = computed(() => {
  const issues = props.qualityReport?.issues || []
  return issues.map((issue, idx) => {
    const autoFix = issue.auto_fix || {}
    const knowledgeSource = issue.knowledge_source || (
      issue.metadata?.source ? { source_type: 'knowledge_base', ...issue.metadata.source } : { source_type: 'model_inference' }
    )

    return {
      issue_id: issue.id || `qc-${idx}`,
      dimension: issue.dimension || issue.category || 'unknown',
      severity: issue.severity || 'minor',
      reason: issue.description || issue.detail || '',
      evidence: issue.evidence || '',
      before_text: autoFix.original || issue.before || '',
      after_text: autoFix.fixed || issue.after || '',
      suggestion: issue.suggestion || '',
      description: issue.description || '',
      category: issue.category || '',
      status: itemStatuses.value[issue.id] || 'pending',
      location: issue.location || null,
      knowledge_source: knowledgeSource,
      confidence: autoFix.confidence || 0,
    }
  })
})

const criticalCount = computed(() => normalizedItems.value.filter(i => i.severity === 'critical').length)
const majorCount = computed(() => normalizedItems.value.filter(i => i.severity === 'major').length)
const minorCount = computed(() => normalizedItems.value.filter(i => i.severity === 'minor').length)
const appliedCount = computed(() => normalizedItems.value.filter(i => i.status === 'applied').length)

const lowRiskPendingCount = computed(() =>
  normalizedItems.value.filter(i => i.severity === 'minor' && (i.status === 'pending' || i.status === 'reverted')).length
)

const hasLowRiskContent = computed(() =>
  normalizedItems.value.some(i => i.severity === 'minor' && (i.after_text || i.suggestion))
)

const affectedChapters = computed(() => {
  const chapters = new Set()
  normalizedItems.value.forEach(i => {
    if (i.location?.chapter_number) chapters.add(i.location.chapter_number)
  })
  return chapters.size
})

/** 逐项应用 */
async function handleApplyItem(item) {
  const issue = findOriginalIssue(item)
  if (!issue) return
  applyingIssueId.value = item.issue_id
  try {
    itemStatuses.value[item.issue_id] = 'applied'
    revisionVersionId.value = `rev-${Date.now()}-${appliedCount.value + 1}`
    if (issue) {
      emit('apply-fix', issue)
    }
    ElMessage.success('已应用此项修改')
  } catch (e) {
    itemStatuses.value[item.issue_id] = 'pending'
    ElMessage.error('应用失败: ' + (e.message || ''))
  } finally {
    applyingIssueId.value = null
  }
}

/** 逐项跳过 */
function handleSkipItem(item) {
  itemStatuses.value[item.issue_id] = 'skipped'
  ElMessage.info('已跳过此项')
}

/** 逐项撤销 */
function handleUndoItem(item) {
  itemStatuses.value[item.issue_id] = 'reverted'
  ElMessage.info('已撤销此项修改')
}

/** 批量应用低风险项 */
async function handleBatchApplyLowRisk() {
  const lowRiskItems = normalizedItems.value.filter(
    i => i.severity === 'minor' && (i.status === 'pending' || i.status === 'reverted') && (i.after_text || i.suggestion)
  )

  if (lowRiskItems.length === 0) {
    ElMessage.warning('没有可应用的低风险项')
    return
  }

  try {
    await ElMessageBox.confirm(
      `将应用 ${lowRiskItems.length} 个低风险项，影响 ${affectedChapters.value} 个章节。是否继续？`,
      '确认批量应用',
      { confirmButtonText: '应用', cancelButtonText: '取消', type: 'info' }
    )

    let appliedCount = 0
    for (const item of lowRiskItems) {
      try {
        itemStatuses.value[item.issue_id] = 'applied'
        const issue = findOriginalIssue(item)
        if (issue) emit('apply-fix', issue)
        appliedCount++
      } catch (e) {
        itemStatuses.value[item.issue_id] = 'pending'
      }
    }

    revisionVersionId.value = `batch-rev-${Date.now()}`
    ElMessage.success(`已批量应用 ${appliedCount} 个低风险项`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('批量应用失败')
  }
}

/** 全部撤销 */
async function handleBatchUndo() {
  const applied = normalizedItems.value.filter(i => i.status === 'applied')
  if (applied.length === 0) return

  try {
    await ElMessageBox.confirm(
      `将撤销 ${applied.length} 个已应用的修改。是否继续？`,
      '确认全部撤销',
      { confirmButtonText: '撤销', cancelButtonText: '取消', type: 'warning' }
    )

    applied.forEach(item => {
      itemStatuses.value[item.issue_id] = 'reverted'
    })
    revisionVersionId.value = null
    ElMessage.warning('已撤销所有修改')
  } catch (e) {
    // 用户取消
  }
}

/** 从原始 qualityReport.issues 中查找对应的 issue 对象 */
function findOriginalIssue(item) {
  const issues = props.qualityReport?.issues || []
  return issues.find(i => i.id === item.issue_id) || null
}
</script>

<style lang="scss" scoped>
.issues-review-dialog {
  :deep(.el-dialog__body) {
    padding: 16px 20px;
    max-height: 70vh;
    overflow-y: auto;
  }
}

.review-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;

  .toolbar-stats {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;

    .affected-info {
      color: #909399;
      font-size: 12px;
      margin-left: 4px;
    }
  }

  .toolbar-actions {
    display: flex;
    gap: 6px;
  }
}

.review-items-list {
  min-height: 100px;
}

.version-footer {
  margin-top: 12px;
  padding: 8px 14px;
  background: #fafcff;
  border-radius: 6px;
  border: 1px solid #ebeef5;
  text-align: right;
}

// 窄屏适配
@media (max-width: 768px) {
  .review-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
