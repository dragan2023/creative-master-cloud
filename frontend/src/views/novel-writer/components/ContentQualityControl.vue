<!--
  ContentQualityControl.vue - 正文写作质控主组件
  
  功能：
  1. 单元列表质控状态概览
  2. 批量质控触发与进度监控
  3. 单单元质控触发
  4. 查看质控报告详情
  5. 修正预览与选择性应用
  
  作为正文写作的最后一道质量保障，
  遵循全面、客观、高效的铁律。
-->
<template>
  <el-dialog
    v-model="dialogVisible"
    title="正文质量管控"
    width="1000px"
    destroy-on-close
    top="3vh"
    class="content-qc-dialog"
  >
    <div class="content-qc-panel">
      <!-- 概览统计 -->
      <div class="qc-overview">
        <div class="stat-row">
          <div class="stat-item">
            <el-statistic title="已完成" :value="statValue(qcSummary.completed)">
              <template #suffix>
                <span class="stat-unit">/ {{ qcSummary.total }}单元</span>
              </template>
            </el-statistic>
          </div>
          <div class="stat-item">
            <el-statistic title="平均得分" :value="statValue(qcSummary.avgScore)">
              <template #suffix>
                <el-tag :type="getScoreTagType(qcSummary.avgScore)" size="small">分</el-tag>
              </template>
            </el-statistic>
          </div>
          <div class="stat-item pending">
            <el-statistic title="待质控" :value="statValue(qcSummary.pending)" />
          </div>
          <div class="stat-item failed">
            <el-statistic title="失败" :value="statValue(qcSummary.failed)" />
          </div>
        </div>

        <!-- 批量质控进度条 -->
        <div v-if="batchQCRunning" class="batch-progress">
          <el-progress
            :percentage="batchProgressPercent"
            :format="batchProgressFormat"
            :stroke-width="12"
          />
          <p class="progress-text">
            正在检测第 {{ batchQCProgress.currentUnit }} 单元...
          </p>
        </div>
      </div>

      <el-divider />

      <!-- 操作按钮区 -->
      <div class="qc-actions">
        <el-button
          type="primary"
          :loading="batchQCRunning || qcLoading"
          :disabled="unitsAvailableForQC.length === 0"
          @click="handleBatchQC"
        >
          <el-icon><Refresh /></el-icon>
          批量质控 ({{ unitsAvailableForQC.length }}单元待检测)
        </el-button>
        <el-button
          v-if="qcSummary.completed > 0"
          type="success"
          plain
          @click="showExportDialog = true"
        >
          <el-icon><Download /></el-icon>
          导出质控报告
        </el-button>
        <el-checkbox v-model="autoFixEnabled" label="自动修正高置信度问题" />
      </div>

      <el-divider />

      <!-- 单元列表 -->
      <div class="unit-qc-list">
        <el-table
          :data="unitQCTableData"
          stripe
          highlight-current-row
          @current-change="handleSelectUnit"
          max-height="400"
        >
          <el-table-column prop="unit_index" label="单元" width="80" />
          <el-table-column prop="unit_title" label="标题" min-width="120">
            <template #default="{ row }">
              <span class="unit-title-text">{{ row.unit_title || `第${row.unit_index}章` }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="生成状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getUnitStatusType(row.status)" size="small">
                {{ getUnitStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="质控状态" width="120">
            <template #default="{ row }">
              <div class="qc-status-cell">
                <el-icon v-if="row.qc_status === 'running'" class="is-loading"><Loading /></el-icon>
                <el-icon v-else-if="row.qc_status === 'completed'" color="#67c23a"><CircleCheckFilled /></el-icon>
                <el-icon v-else-if="row.qc_status === 'failed'" color="#f56c6c"><CircleCloseFilled /></el-icon>
                <el-icon v-else color="#909399"><Clock /></el-icon>
                <el-tag
                  v-if="row.qc_score"
                  :type="getScoreTagType(row.qc_score)"
                  size="small"
                  effect="plain"
                >
                  {{ row.qc_score }}分
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="问题/修正" width="100">
            <template #default="{ row }">
              <span class="issues-count">
                {{ row.qc_issues_count || 0 }} 问题
              </span>
              <span v-if="row.qc_fixed_count" class="fixed-count">
                / {{ row.qc_fixed_count }} 修正
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'completed' && row.qc_status === 'pending'"
                type="primary"
                size="small"
                link
                @click="handleTriggerUnitQC(row.unit_index)"
              >
                开始质控
              </el-button>
              <el-button
                v-if="row.qc_status === 'completed'"
                type="success"
                size="small"
                link
                @click="handleViewReport(row.unit_index)"
              >
                查看报告
              </el-button>
              <el-button
                v-if="row.qc_fixed_count > 0"
                type="warning"
                size="small"
                link
                @click="handleRevertFix(row.unit_index)"
              >
                撤销修正
              </el-button>
              <!-- v3.0: 双版本下载按钮 -->
              <el-dropdown
                v-if="row.qc_status === 'completed'"
                trigger="click"
                size="small"
              >
                <el-button type="info" size="small" link>
                  <el-icon><Download /></el-icon>
                  下载
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="handleDownload(row.unit_index, 'draft')">
                      📝 下载初稿
                    </el-dropdown-item>
                    <el-dropdown-item @click="handleDownload(row.unit_index, 'revised')">
                      ✅ 下载修正稿
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 报告详情面板 -->
      <div v-if="selectedUnitIndex" class="report-section">
        <el-divider content-position="left">
          第{{ selectedUnitIndex }}单元 质控报告
        </el-divider>
        <ContentQCReportPanel
          :report="selectedUnitReport"
          :unit-index="selectedUnitIndex"
          @preview-fix="handlePreviewFix"
          @apply-fix="handleApplyFix"
        />
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>

  <!-- 修正预览对话框 -->
  <ContentQCFixDialog
    v-model:visible="showFixDialog"
    :unit-index="fixDialogUnitIndex"
    :issue="fixDialogIssue"
    :original-content="fixDialogOriginal"
    :fixed-content="fixDialogFixed"
    :has-applied-fixes="fixDialogHasApplied"
    @apply-fixes="handleApplyFixes"
    @revert-fix="handleRevertFromDialog"
  />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import {
  Refresh, Download, Loading, CircleCheckFilled,
  CircleCloseFilled, Clock
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import ContentQCReportPanel from './ContentQCReportPanel.vue'
import ContentQCFixDialog from './ContentQCFixDialog.vue'
import {
  useContentQualityControl,
  getScoreColor,
  getSeverityType,
  getDimensionName
} from '../composables/useContentQualityControl'
import { useWritingTaskStore } from '@/stores/writingTask'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projectId: { type: [String, Number], default: null },
  taskId: { type: [String, Number], default: null },
  units: { type: Array, default: () => [] },
  project: { type: Object, default: null }
})

const emit = defineEmits(['update:visible', 'qc-complete', 'unit-updated'])

// 对话框可见性
const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

// 使用质控composable
const projectIdRef = computed(() => props.projectId)
const taskIdRef = computed(() => props.taskId)
const unitsRef = computed(() => props.units)
const projectRef = computed(() => props.project)

const qc = useContentQualityControl({
  projectId: projectIdRef,
  taskId: taskIdRef,
  units: unitsRef,
  project: projectRef
})

// 从composable解构状态和方法
const {
  qcLoading,
  batchQCRunning,
  batchQCProgress,
  qcSummary,
  unitsAvailableForQC,
  triggerUnitQC,
  triggerBatchQC,
  revertFix,
  applySelectedFixes,
  downloadContent,
  getScoreColor: qcGetScoreColor,
  getSeverityType: qcGetSeverityType,
  getDimensionName: qcGetDimensionName
} = qc

// BUG#6 修复: 监听 writingTaskStore 中 units 的质控更新
// 当 WebSocket 质控消息到达时，自动触发 content composable 的内容同步
const writingStore = useWritingTaskStore()
const processedQCUnits = new Set()  // 防止重复处理同一单元的质控消息
watch(
  () => writingStore.units,
  (newUnits) => {
    if (!newUnits || newUnits.length === 0) return
    for (const unit of newUnits) {
      const qcData = unit?.quality_control
      // 仅处理来自 WebSocket 的质控消息且尚未处理过的单元
      if (qcData?._from_ws && qcData.fixed_content && !processedQCUnits.has(unit.unit_index)) {
        processedQCUnits.add(unit.unit_index)
        qc.handleQCMessage('unit_quality_control', {
          unit_index: unit.unit_index,
          status: qcData.status,
          score: qcData.score,
          issues_count: qcData.issues_count,
          fixed_count: qcData.fixed_count,
          issues: qcData.issues,
          fixes_applied: qcData.fixes_applied,
          report: qcData.report,
          original_content: qcData.original_content,
          fixed_content: qcData.fixed_content
        })
      }
    }
  },
  { deep: true }
)

// 本地状态
const autoFixEnabled = ref(true)
const selectedUnitIndex = ref(null)
const selectedUnitReport = ref(null)
const showExportDialog = ref(false)
const showFixDialog = ref(false)
const fixDialogUnitIndex = ref(null)
const fixDialogIssue = ref(null)
const fixDialogOriginal = ref('')
const fixDialogFixed = ref('')
const fixDialogHasApplied = ref(false)

// 批量进度百分比
const batchProgressPercent = computed(() => {
  if (batchQCProgress.value.total === 0) return 0
  return Math.round((batchQCProgress.value.current / batchQCProgress.value.total) * 100)
})

// 批量进度格式化
function batchProgressFormat(percentage) {
  return `${batchQCProgress.value.current}/${batchQCProgress.value.total}`
}

// 单元表格数据
const unitQCTableData = computed(() => {
  return props.units.map(unit => ({
    unit_index: unit.unit_index,
    unit_title: unit.unit_title,
    status: unit.status,
    qc_status: unit.quality_control?.status || 'pending',
    qc_score: unit.quality_control?.score || null,
    qc_issues_count: unit.quality_control?.issues_count || 0,
    qc_fixed_count: unit.quality_control?.fixed_count || 0
  }))
})

// 获取单元状态类型
function getUnitStatusType(status) {
  const map = {
    pending: 'info',
    processing: 'primary',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

// 获取单元状态标签
function getUnitStatusLabel(status) {
  const map = {
    pending: '等待',
    processing: '生成中',
    completed: '完成',
    failed: '失败'
  }
  return map[status] || status
}

// 获取得分Tag类型
function getScoreTagType(score) {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

// Element Plus el-statistic 兼容：value=0 会导致 InvalidCharacterError
// 用此包装器确保传给组件的值永远不是裸数字 0
function statValue(val) {
  return val === 0 ? '0' : val
}

// 批量质控
async function handleBatchQC() {
  const options = {
    autoFix: autoFixEnabled.value,
    threshold: 0.8,
    depth: 'standard'
  }
  
  const result = await triggerBatchQC(options)
  if (result) {
    emit('qc-complete', result)
  }
}

// 单单元质控
async function handleTriggerUnitQC(unitIndex) {
  const options = {
    autoFix: autoFixEnabled.value,
    threshold: 0.8
  }
  
  const result = await triggerUnitQC(unitIndex, options)
  if (result) {
    // 自动查看报告
    handleViewReport(unitIndex)
  }
}

// 选择单元
function handleSelectUnit(row) {
  if (row) {
    selectedUnitIndex.value = row.unit_index
    // 获取单元报告
    const unit = props.units.find(u => u.unit_index === row.unit_index)
    if (unit?.quality_control?.report) {
      selectedUnitReport.value = unit.quality_control
    } else {
      selectedUnitReport.value = null
    }
  } else {
    selectedUnitIndex.value = null
    selectedUnitReport.value = null
  }
}

// 查看报告
function handleViewReport(unitIndex) {
  selectedUnitIndex.value = unitIndex
  handleSelectUnit({ unit_index: unitIndex })
}

// 预览修正
function handlePreviewFix(issue) {
  const unit = props.units.find(u => u.unit_index === selectedUnitIndex.value)
  if (!unit) return
  
  fixDialogUnitIndex.value = selectedUnitIndex.value
  fixDialogIssue.value = issue
  fixDialogOriginal.value = unit.original_content_before_fix || unit.final_content || ''
  fixDialogFixed.value = issue.auto_fix?.fixed || unit.final_content || ''
  fixDialogHasApplied.value = (unit.quality_control?.fixed_count || 0) > 0
  showFixDialog.value = true
}

// 应用修正
function handleApplyFix(issue) {
  // 单个修正应用
  handleApplyFixes({
    unitIndex: selectedUnitIndex.value,
    fixIds: [issue.id]
  })
}

// 应用多个修正
async function handleApplyFixes(data) {
  const result = await applySelectedFixes(data.unitIndex, data.fixIds)
  if (result) {
    showFixDialog.value = false
    // 更新单元报告
    handleViewReport(data.unitIndex)
    emit('unit-updated', { unitIndex: data.unitIndex, data: result })
  }
}

// 撤销修正
async function handleRevertFix(unitIndex) {
  const result = await revertFix(unitIndex)
  if (result) {
    handleViewReport(unitIndex)
    emit('unit-updated', { unitIndex, data: result })
  }
}

// 从对话框撤销修正
async function handleRevertFromDialog(data) {
  const result = await revertFix(data.unitIndex)
  if (result) {
    showFixDialog.value = false
    handleViewReport(data.unitIndex)
    emit('unit-updated', { unitIndex: data.unitIndex, data: result })
  }
}

// 下载单元内容（v3.0: 初稿/修正稿）
function handleDownload(unitIndex, version) {
  downloadContent(unitIndex, version)
}

// 对话框关闭时重置
watch(dialogVisible, (val) => {
  if (!val) {
    selectedUnitIndex.value = null
    selectedUnitReport.value = null
  }
})
</script>

<style lang="scss">
/* 非scoped：dialog teleport到body */
.content-qc-dialog {
  .content-qc-panel {
    .qc-overview {
      .stat-row {
        display: flex;
        gap: 24px;
        justify-content: space-around;
        padding: 12px 0;

        .stat-item {
          text-align: center;

          :deep(.el-statistic-title) {
            font-size: 12px;
            color: #909399;
          }

          :deep(.el-statistic-number) {
            font-size: 24px;
            font-weight: 700;
          }

          .stat-unit {
            font-size: 12px;
            color: #909399;
          }

          &.pending :deep(.el-statistic-number) { color: #e6a23c; }
          &.failed :deep(.el-statistic-number) { color: #f56c6c; }
        }
      }

      .batch-progress {
        margin-top: 16px;
        padding: 12px;
        background: #ecf5ff;
        border-radius: 6px;

        .progress-text {
          text-align: center;
          font-size: 13px;
          color: #409eff;
          margin-top: 8px;
        }
      }
    }

    .qc-actions {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 8px 0;
    }

    .unit-qc-list {
      .qc-status-cell {
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .issues-count {
        color: #606266;
        font-size: 12px;
      }

      .fixed-count {
        color: #67c23a;
        font-size: 12px;
      }
    }

    .report-section {
      margin-top: 16px;
      padding: 12px;
      background: #f5f7fa;
      border-radius: 6px;
    }
  }
}
</style>